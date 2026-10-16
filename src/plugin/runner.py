"""run_tests: run a candidate solution against a problem's official asserts, in a child process.

The child is `python -I` with a 10 s limit, in its own session so every process it starts is
killed afterwards. Each `assert left == right` is checked by evaluating both sides and requiring
the result to be made of the same built-in kinds as the expected value, so an object that claims
to equal anything does not pass. The run's record is written by this process, not the child: the
child runs in `.exec/`, and if it changed anything under `runs/` that change is undone and the run
fails.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

from contract import AssertResult, RunInput, RunOutput
from plugin.problems import problem, tests_sha256

TIMEOUT = 10.0
MAX_CODE = 20_000
MAX_ERROR = 300
MARKER = "@@MBPP-RESULT@@"

HARNESS = r'''
import ast, json, sys

MARKER = "@@MBPP-RESULT@@"
NUMBERS = (bool, int, float)
BUILTINS = (str, bytes, list, tuple, dict, set, frozenset, type(None), complex)


def kind(value):
    cls = type(value)
    if cls in NUMBERS:
        return "number"
    if cls in BUILTINS:
        return cls.__name__
    # The standard library's own subclasses (Counter, OrderedDict, defaultdict, namedtuple from
    # collections) count as their base; a user's subclass could override __eq__, so it does not.
    if cls.__module__ == "collections":
        for base in BUILTINS:
            if isinstance(value, base):
                return base.__name__
    return "custom:" + cls.__name__


def same_kind(actual, expected):
    if kind(actual) != kind(expected) or kind(expected).startswith("custom:"):
        return False
    if isinstance(expected, (list, tuple)):
        return len(actual) == len(expected) and all(same_kind(a, e) for a, e in zip(actual, expected))
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(same_kind(actual[k], expected[k]) for k in expected)
    return True


def short(error):
    text = f"{type(error).__name__}: {error}"
    return text[:300]


def check(test, namespace):
    node = ast.parse(test).body[0]
    if (isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare)
            and len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq)):
        actual = eval(compile(ast.Expression(node.test.left), "<test>", "eval"), namespace)
        expected = eval(compile(ast.Expression(node.test.comparators[0]), "<test>", "eval"), namespace)
        if not same_kind(actual, expected):
            return f"returned {kind(actual)} {actual!r:.120}, expected {kind(expected)} {expected!r:.120}"
        if not (expected == actual):
            return f"returned {actual!r:.150}, expected {expected!r:.150}"
        return ""
    exec(compile(test, "<test>", "exec"), namespace)
    return ""


def main():
    spec = json.loads(open("spec.json", encoding="utf-8").read())
    namespace = {"__name__": "__solution__"}
    out = {"load_error": "", "results": []}
    try:
        exec(compile(spec["code"] + "\n" + spec["setup"], "solution.py", "exec"), namespace)
    except BaseException as error:
        out["load_error"] = short(error)
    for test in spec["tests"]:
        if out["load_error"]:
            out["results"].append({"test": test, "passed": False, "error": "the code did not load"})
            continue
        try:
            problem = check(test, namespace)
        except BaseException as error:
            problem = short(error) if str(error) or not isinstance(error, AssertionError) else "AssertionError"
        out["results"].append({"test": test, "passed": not problem, "error": problem})
    sys.stdout.write("\n" + MARKER + json.dumps(out) + "\n")
    sys.stdout.flush()


main()
'''


def code_sha256(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _snapshot(folder: Path) -> dict[str, bytes]:
    if not folder.is_dir():
        return {}
    return {path.relative_to(folder).as_posix(): path.read_bytes() for path in folder.rglob("*") if path.is_file()}


def _restore(folder: Path, snapshot: dict[str, bytes]) -> None:
    if folder.exists():
        shutil.rmtree(folder)
    for name, data in snapshot.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def _execute(spec: dict, folder: Path) -> tuple[str, list[dict]]:
    """Run the harness in ``folder``; (load_error, results)."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    (folder / "harness.py").write_text(HARNESS, encoding="utf-8")
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONHASHSEED": "0"}
    process = subprocess.Popen(
        [sys.executable, "-I", "harness.py"],
        cwd=folder,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=env,
        start_new_session=True,
    )
    try:
        stdout, _ = process.communicate(timeout=TIMEOUT)
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
        stdout = b""
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        process.wait()
    if timed_out:
        return f"timed out after {TIMEOUT:g} s", [
            {"test": test, "passed": False, "error": "timed out"} for test in spec["tests"]
        ]
    text = stdout.decode("utf-8", errors="replace")
    if MARKER not in text:
        return "the process exited before reporting (exit() or a crash)", [
            {"test": test, "passed": False, "error": "no result"} for test in spec["tests"]
        ]
    report = json.loads(text.rsplit(MARKER, 1)[1].strip().splitlines()[0])
    if [row["test"] for row in report["results"]] != spec["tests"]:
        raise RuntimeError("the harness reported results for other tests")
    return report["load_error"], report["results"]


def run_tests(given: RunInput, workspace: Path) -> RunOutput:
    if not given.code.strip():
        raise ValueError("code must not be empty")
    if len(given.code) > MAX_CODE:
        raise ValueError(f"code must be at most {MAX_CODE} characters")
    row = problem(given.task_id)
    workspace = workspace.resolve()
    runs = workspace / "runs"
    before = _snapshot(runs)
    digest = code_sha256(given.code)
    scratch = workspace / ".exec" / digest
    spec = {"setup": row["test_setup_code"], "code": given.code, "tests": list(row["tests"])}
    try:
        load_error, results = _execute(spec, scratch)
    finally:
        shutil.rmtree(workspace / ".exec", ignore_errors=True)
    if _snapshot(runs) != before:
        _restore(runs, before)
        load_error = "the code changed files under runs/; the change was undone"
        results = [{"test": test, "passed": False, "error": "tampering"} for test in row["tests"]]

    results = [AssertResult(test=r["test"], passed=r["passed"], error=r["error"][:MAX_ERROR]) for r in results]
    passed = sum(r.passed for r in results)
    record = f"runs/{given.task_id}/{digest}.json"
    output = RunOutput(
        task_id=given.task_id,
        code_sha256=digest,
        tests_sha256=tests_sha256(row["test_setup_code"], row["tests"]),
        load_error=load_error,
        passed=passed,
        total=len(results),
        all_passed=bool(results) and passed == len(results),
        results=results,
        record=record,
    )
    path = workspace / record
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "task_id": output.task_id,
        "code_sha256": output.code_sha256,
        "tests_sha256": output.tests_sha256,
        "load_error": output.load_error,
        "passed": output.passed,
        "total": output.total,
        "all_passed": output.all_passed,
        "results": [{"test": r.test, "passed": r.passed, "error": r.error} for r in results],
    }
    path.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
    return output
