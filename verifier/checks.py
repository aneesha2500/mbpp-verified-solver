"""Checks shared by the tool verifiers. Pure functions of their arguments and the files on disk."""

import hashlib
import json
import re

FIRST, LAST = 11, 510
SHA = re.compile(r"^[0-9a-f]{64}$")


def result(valid, message, *, score=None, **details):
    return {
        "valid": valid,
        "score": float(valid) if score is None else score,
        "message": message,
        "details": details,
    }


def task_id_problem(task_id):
    if not FIRST <= task_id <= LAST:
        return f"task_id must be an MBPP test-split id, {FIRST} to {LAST}"
    return None


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tests_sha256(setup, tests):
    """Mirrors plugin.problems.tests_sha256."""
    return sha256(json.dumps({"setup": setup, "tests": tests}, sort_keys=True, ensure_ascii=False))


def record_path(task_id, code_sha):
    return f"runs/{task_id}/{code_sha}.json"
