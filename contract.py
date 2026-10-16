"""Each tool's and task's typed input and output (see nanoagent.plugin.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    GET_PROBLEM = "get_problem"
    RUN_TESTS = "run_tests"
    OFFICIAL_TESTS = "official_tests"


class Task(Enum):
    SOLVE_PROBLEM = "solve-problem"


TASK_ID = "An MBPP test-split task id, 11 to 510"
TESTS = "The problem's assert statements, in MBPP's order"
SETUP = "Code MBPP runs after the solution and before the tests (usually empty)"
CODE_SHA = "The SHA-256 hex digest of the code's UTF-8 bytes"
TESTS_SHA = "The SHA-256 hex digest of the problem's setup code and tests (see official_tests)"


@dataclass
class ProblemInput(Output):
    task_id: Annotated[int, TASK_ID]


@dataclass
class ProblemOutput(Output):
    task_id: Annotated[int, TASK_ID]
    text: Annotated[str, "The problem statement, as MBPP words it"]
    entry_point: Annotated[str, "The name of the function the tests call"]
    test_setup_code: Annotated[str, SETUP]
    tests: Annotated[list[str], TESTS]


@dataclass
class AssertResult(Output):
    test: Annotated[str, "The assert statement"]
    passed: Annotated[bool, "Whether the assert held"]
    error: Annotated[str, "Why it failed, or empty when it passed"]


@dataclass
class RunInput(Output):
    task_id: Annotated[int, TASK_ID]
    code: Annotated[str, "Python source defining the entry-point function (at most 20000 characters)"]


@dataclass
class RunOutput(Output):
    task_id: Annotated[int, TASK_ID]
    code_sha256: Annotated[str, CODE_SHA]
    tests_sha256: Annotated[str, TESTS_SHA]
    load_error: Annotated[str, "Why the code could not be loaded, or empty when it loaded"]
    passed: Annotated[int, "How many asserts held"]
    total: Annotated[int, "How many asserts ran"]
    all_passed: Annotated[bool, "Whether every assert held"]
    results: Annotated[list[AssertResult], "One result per assert, in order"]
    record: Annotated[str, "The run record, runs/<task_id>/<code_sha256>.json in the workspace"]


@dataclass
class OfficialOutput(Output):
    task_id: Annotated[int, TASK_ID]
    entry_point: Annotated[str, "The name of the function the tests call"]
    test_setup_code: Annotated[str, SETUP]
    tests: Annotated[list[str], TESTS]
    tests_sha256: Annotated[str, TESTS_SHA]


@dataclass
class SolutionOutput(Output):
    task_id: Annotated[int, TASK_ID]
    code: Annotated[str, "Exactly the code the last passing run_tests call ran, character for character"]


TOOLS = {
    Tool.GET_PROBLEM: (ProblemInput, ProblemOutput),
    Tool.RUN_TESTS: (RunInput, RunOutput),
    Tool.OFFICIAL_TESTS: (ProblemInput, OfficialOutput),
}
TASKS = {Task.SOLVE_PROBLEM: (ProblemInput, SolutionOutput)}
