"""run_tests (each call) and the solve-problem task's outcome check.

The verifier cannot run code, so it trusts run_tests' record, which only the plugin writes:
runs/<task_id>/<sha256 of the code>.json in the workspace. It checks that the record belongs to
exactly the submitted code and to the official tests pinned before the agent started.
"""

import json
from pathlib import Path

from .checks import SHA, record_path, result, sha256, task_id_problem

MAX_CODE = 20_000


def verify_input(value):
    problem = task_id_problem(value.task_id)
    if problem:
        return result(False, problem)
    if not value.code.strip():
        return result(False, "code must not be empty")
    if len(value.code) > MAX_CODE:
        return result(False, f"code must be at most {MAX_CODE} characters")
    return result(True, "input is valid")


def _read_record(workspace, relative):
    path = Path(workspace) / relative
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def verify_output(input_value, output_value, workspace):
    digest = sha256(input_value.code)
    if output_value.task_id != input_value.task_id or output_value.code_sha256 != digest:
        return result(False, "output is for another task or other code")
    if output_value.record != record_path(input_value.task_id, digest):
        return result(False, "record is not runs/<task_id>/<code_sha256>.json")
    if output_value.total != len(output_value.results) or output_value.passed != sum(
        row.passed for row in output_value.results
    ):
        return result(False, "passed/total do not match the per-assert results")
    if output_value.all_passed != (output_value.total > 0 and output_value.passed == output_value.total):
        return result(False, "all_passed does not match passed and total")
    record = _read_record(workspace, output_value.record)
    if record is None:
        return result(False, "the run record is missing or unreadable")
    reported = {
        "task_id": output_value.task_id,
        "code_sha256": output_value.code_sha256,
        "tests_sha256": output_value.tests_sha256,
        "load_error": output_value.load_error,
        "passed": output_value.passed,
        "total": output_value.total,
        "all_passed": output_value.all_passed,
    }
    for name, value in reported.items():
        if record.get(name) != value:
            return result(False, f"the run record's {name} differs from the output")
    return result(True, f"{output_value.passed}/{output_value.total} asserts passed")


def verify_task(arguments, output, reference, workspace):
    """``output``: a contract SolutionOutput; ``reference``: the pinned OfficialOutput."""
    if output.task_id != arguments.task_id:
        return result(False, f"the solution is for task {output.task_id}, not {arguments.task_id}", score=0.0)
    if not output.code.strip():
        return result(False, "the submitted code is empty", score=0.0)
    digest = sha256(output.code)
    if not SHA.fullmatch(digest):
        return result(False, "could not hash the code", score=0.0)
    relative = record_path(arguments.task_id, digest)
    record = _read_record(workspace, relative)
    if record is None:
        return result(
            False,
            "the submitted code was never run with run_tests (submit exactly the code you ran)",
            score=0.0,
            expected_record=relative,
        )
    if record.get("task_id") != arguments.task_id or record.get("code_sha256") != digest:
        return result(False, "the run record belongs to another task or other code", score=0.0)
    if record.get("tests_sha256") != reference.tests_sha256:
        return result(False, "the run record was not made with the official tests", score=0.0)
    total, passed = record.get("total"), record.get("passed")
    if total != len(reference.tests) or not isinstance(passed, int) or not 0 <= passed <= total:
        return result(False, "the run record does not cover every official test", score=0.0)
    score = passed / total
    failing = [row["test"] for row in record.get("results", []) if not row.get("passed")]
    if passed != total or record.get("load_error"):
        return result(
            False,
            f"{passed}/{total} official asserts pass",
            score=score,
            failing=failing,
            load_error=record.get("load_error", ""),
        )
    return result(True, f"all {total} official asserts pass", score=1.0, record=relative)
