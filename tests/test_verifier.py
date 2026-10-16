from __future__ import annotations

import json
from pathlib import Path

import pytest
from slimconfig import build_output, plain_output

import verifier
from contract import TASKS, TOOLS, OfficialOutput, ProblemInput, RunInput, Task, Tool
from plugin import official_tests, run_tests
from plugin.problems import problems

TASK = 11  # "Write a python function to remove first and last occurrence of a given character from the string."
GOOD = problems()[TASK]["reference_code"]
WRONG = "def remove_Occ(s, ch):\n    return s[1:-1]\n"  # passes 2 of the 3 asserts


def built(value: dict, cls):
    """The verifier gets contract instances, as NanoAgent's sandbox builds them from JSON."""
    return build_output(plain_output(value) if not isinstance(value, dict) else value, cls)


def reference(task_id: int = TASK) -> OfficialOutput:
    return built(plain_output(official_tests(ProblemInput(task_id=task_id), Path("."))), OfficialOutput)


def verify_task(workspace: Path, code: str, task_id: int = TASK, ref: OfficialOutput | None = None) -> dict:
    given, made = TASKS[Task.SOLVE_PROBLEM]
    return verifier.verify_task(
        "solve-problem",
        build_output({"task_id": TASK}, given),
        build_output({"task_id": task_id, "code": code}, made),
        ref or reference(),
        str(workspace),
    )


def run(workspace: Path, code: str, task_id: int = TASK):
    return run_tests(RunInput(task_id=task_id, code=code), workspace)


# --- correct ---------------------------------------------------------------------------------


def test_approves_code_that_passed_every_official_assert(tmp_path: Path) -> None:
    output = run(tmp_path, GOOD)
    assert output.all_passed and output.passed == output.total == 3
    given, made = TOOLS[Tool.RUN_TESTS]
    check = verifier.verify_output(
        "run_tests", build_output({"task_id": TASK, "code": GOOD}, given), built(output, made), str(tmp_path)
    )
    assert check["valid"] is True
    verdict = verify_task(tmp_path, GOOD)
    assert verdict["valid"] is True and verdict["score"] == 1.0


# --- incorrect -------------------------------------------------------------------------------


def test_refuses_code_that_fails_asserts_with_partial_score(tmp_path: Path) -> None:
    run(tmp_path, WRONG)
    verdict = verify_task(tmp_path, WRONG)
    assert verdict["valid"] is False
    assert verdict["score"] == pytest.approx(2 / 3) and len(verdict["details"]["failing"]) == 1


def test_refuses_a_solution_for_another_task(tmp_path: Path) -> None:
    run(tmp_path, GOOD)
    verdict = verify_task(tmp_path, GOOD, task_id=12)
    assert verdict["valid"] is False and "not 11" in verdict["message"]


# --- missing ---------------------------------------------------------------------------------


def test_refuses_code_that_was_never_run(tmp_path: Path) -> None:
    verdict = verify_task(tmp_path, GOOD)
    assert verdict["valid"] is False and "never run" in verdict["message"]


def test_refuses_code_edited_after_its_passing_run(tmp_path: Path) -> None:
    run(tmp_path, GOOD)
    verdict = verify_task(tmp_path, GOOD + "\n# edited")
    assert verdict["valid"] is False and "never run" in verdict["message"]


def test_refuses_an_empty_submission(tmp_path: Path) -> None:
    assert verify_task(tmp_path, "   ")["valid"] is False


# --- malformed -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ({"task_id": 11, "code": "def f(): pass"}, True),
        ({"task_id": 10, "code": "def f(): pass"}, False),
        ({"task_id": 511, "code": "def f(): pass"}, False),
        ({"task_id": 11, "code": "  \n"}, False),
        ({"task_id": 11, "code": "x" * 20_001}, False),
    ],
)
def test_checks_run_tests_input(value: dict, valid: bool) -> None:
    assert verifier.verify_input("run_tests", build_output(value, RunInput))["valid"] is valid


def test_refuses_a_corrupted_or_rewritten_record(tmp_path: Path) -> None:
    output = run(tmp_path, WRONG)
    record = tmp_path / output.record
    body = json.loads(record.read_text())
    body.update(passed=body["total"], all_passed=True)
    record.write_text(json.dumps(body))
    given, made = TOOLS[Tool.RUN_TESTS]
    check = verifier.verify_output(
        "run_tests", build_output({"task_id": TASK, "code": WRONG}, given), built(output, made), str(tmp_path)
    )
    assert check["valid"] is False
    record.write_text("{not json")
    assert verify_task(tmp_path, WRONG)["valid"] is False


def test_refuses_a_record_made_with_other_tests(tmp_path: Path) -> None:
    run(tmp_path, GOOD)
    other = reference()
    other.tests_sha256 = "0" * 64
    verdict = verify_task(tmp_path, GOOD, ref=other)
    assert verdict["valid"] is False and "official tests" in verdict["message"]


def test_official_tests_digest_is_checked() -> None:
    ref = reference()
    assert verifier.verify_output("official_tests", ProblemInput(task_id=TASK), ref, ".")["valid"] is True
    ref.tests = ref.tests[:2]
    assert verifier.verify_output("official_tests", ProblemInput(task_id=TASK), ref, ".")["valid"] is False


# --- boundary: code that tries to pass without solving -----------------------------------------


ALWAYS_EQUAL = """
class Anything:
    def __eq__(self, other):
        return True
def remove_Occ(s, ch):
    return Anything()
"""

FORGER = """
import json, pathlib, hashlib
good = {good!r}
sha = hashlib.sha256(good.encode()).hexdigest()
path = pathlib.Path("../../runs/11") / (sha + ".json")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps({{"task_id": 11, "code_sha256": sha, "passed": 3, "total": 3, "all_passed": True}}))
def remove_Occ(s, ch):
    return s
"""


def test_an_object_equal_to_everything_does_not_pass(tmp_path: Path) -> None:
    output = run(tmp_path, ALWAYS_EQUAL)
    assert output.passed == 0
    assert verify_task(tmp_path, ALWAYS_EQUAL)["valid"] is False


def test_an_endless_loop_times_out(tmp_path: Path) -> None:
    code = "def remove_Occ(s, ch):\n    while True:\n        pass\n"
    output = run(tmp_path, code)
    assert output.passed == 0 and "timed out" in output.load_error


def test_exit_during_load_is_a_failure(tmp_path: Path) -> None:
    output = run(tmp_path, "import sys\nsys.exit(0)\n")
    assert output.passed == 0 and output.load_error


def test_syntax_error_is_a_failure(tmp_path: Path) -> None:
    output = run(tmp_path, "def remove_Occ(s, ch)\n    return s")
    assert output.passed == 0 and "SyntaxError" in output.load_error
    assert verify_task(tmp_path, "def remove_Occ(s, ch)\n    return s")["valid"] is False


def test_code_that_forges_a_record_is_undone(tmp_path: Path) -> None:
    code = FORGER.format(good=GOOD)
    output = run(tmp_path, code)
    assert output.passed == 0 and "runs/" in output.load_error
    assert verify_task(tmp_path, GOOD)["valid"] is False  # the forged record for GOOD is gone
