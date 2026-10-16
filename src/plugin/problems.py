"""MBPP's test split (task ids 11 to 510), bundled in data/mbpp_test.json.

MBPP: Austin et al., "Program Synthesis with Large Language Models" (2021),
https://github.com/google-research/google-research/tree/master/mbpp, CC BY 4.0.
"""

from __future__ import annotations

import hashlib
import json
from functools import cache
from pathlib import Path

from contract import OfficialOutput, ProblemInput, ProblemOutput

DATA = Path(__file__).with_name("data") / "mbpp_test.json"
FIRST, LAST = 11, 510


@cache
def problems() -> dict[int, dict]:
    return {row["task_id"]: row for row in json.loads(DATA.read_text(encoding="utf-8"))}


def problem(task_id: int) -> dict:
    if not FIRST <= task_id <= LAST:
        raise ValueError(f"task_id must be an MBPP test-split id, {FIRST} to {LAST}")
    return problems()[task_id]


def tests_sha256(setup: str, tests: list[str]) -> str:
    """The digest every run record and the reference carry: setup code and tests, as canonical JSON."""
    payload = json.dumps({"setup": setup, "tests": tests}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_problem(given: ProblemInput, workspace: Path) -> ProblemOutput:
    row = problem(given.task_id)
    return ProblemOutput(
        task_id=row["task_id"],
        text=row["text"],
        entry_point=row["entry_point"],
        test_setup_code=row["test_setup_code"],
        tests=list(row["tests"]),
    )


def official_tests(given: ProblemInput, workspace: Path) -> OfficialOutput:
    """The solve-problem reference: the official tests and their digest, pinned before the agent runs."""
    row = problem(given.task_id)
    return OfficialOutput(
        task_id=row["task_id"],
        entry_point=row["entry_point"],
        test_setup_code=row["test_setup_code"],
        tests=list(row["tests"]),
        tests_sha256=tests_sha256(row["test_setup_code"], row["tests"]),
    )
