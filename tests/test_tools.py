from __future__ import annotations

from pathlib import Path

import pytest

from contract import ProblemInput, RunInput
from plugin import get_problem, official_tests, run_tests
from plugin.problems import problems


def test_get_problem_returns_the_mbpp_record() -> None:
    problem = get_problem(ProblemInput(task_id=11), Path("."))
    assert problem.entry_point == "remove_Occ" and len(problem.tests) == 3
    assert official_tests(ProblemInput(task_id=11), Path(".")).tests == problem.tests


@pytest.mark.parametrize("task_id", [0, 10, 511, 974])
def test_ids_outside_the_test_split_are_refused(task_id: int) -> None:
    with pytest.raises(ValueError):
        get_problem(ProblemInput(task_id=task_id), Path("."))


def test_every_reference_solution_passes_a_sample(tmp_path: Path) -> None:
    for task_id in (11, 40, 88, 367, 510):  # includes Counter results and the one setup-code problem
        output = run_tests(RunInput(task_id=task_id, code=problems()[task_id]["reference_code"]), tmp_path)
        assert output.all_passed, (task_id, output.results)


def test_the_record_is_written_and_scratch_removed(tmp_path: Path) -> None:
    output = run_tests(RunInput(task_id=11, code=problems()[11]["reference_code"]), tmp_path)
    assert (tmp_path / output.record).is_file()
    assert not (tmp_path / ".exec").exists()
