"""get_problem and official_tests: the problem returned is the one asked for, and well formed."""

from .checks import result, task_id_problem, tests_sha256


def verify_input(value):
    problem = task_id_problem(value.task_id)
    return result(False, problem) if problem else result(True, "input is valid")


def _problem_problem(input_value, output_value):
    if output_value.task_id != input_value.task_id:
        return "output is for another task"
    if not output_value.tests or not output_value.entry_point:
        return "the problem has no tests or no entry point"
    if not all(test.lstrip().startswith("assert") for test in output_value.tests):
        return "every test must be an assert statement"
    if not any(output_value.entry_point + "(" in test for test in output_value.tests):
        return "no test calls the entry point"
    return None


def verify_output(input_value, output_value, workspace):
    problem = _problem_problem(input_value, output_value)
    return result(False, problem) if problem else result(True, "problem is well formed")


def verify_official(input_value, output_value, workspace):
    problem = _problem_problem(input_value, output_value)
    if problem:
        return result(False, problem)
    if output_value.tests_sha256 != tests_sha256(output_value.test_setup_code, output_value.tests):
        return result(False, "tests_sha256 is not the digest of the setup code and tests")
    return result(True, "official tests are well formed", tests=len(output_value.tests))
