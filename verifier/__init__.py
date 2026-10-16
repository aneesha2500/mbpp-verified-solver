"""The deterministic verifier: each tool's checks live in its own module, on contract instances."""

from contract import Task, Tool

from . import problem, run


class _Official:
    verify_input = staticmethod(problem.verify_input)
    verify_output = staticmethod(problem.verify_official)


TOOLS = {Tool.GET_PROBLEM: problem, Tool.RUN_TESTS: run, Tool.OFFICIAL_TESTS: _Official}
# task -> its output's check, verify_task(arguments, output, reference, workspace)
TASKS = {Task.SOLVE_PROBLEM: run.verify_task}


def verify_input(tool, value):
    return TOOLS[Tool(tool)].verify_input(value)


def verify_output(tool, input_value, output_value, workspace):
    return TOOLS[Tool(tool)].verify_output(input_value, output_value, workspace)


def verify_task(task, arguments, output, reference, workspace):
    return TASKS[Task(task)](arguments, output, reference, workspace)
