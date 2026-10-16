# MBPP Verified Solver

A `nanoagent.plugin/v1` plugin, built with the structure of NanoAgent's
reference plugin, [arxiv-source](https://github.com/zeyuyang8/arxiv-source).
An agent solves a problem from MBPP's test split (task ids 11 to 510), and the
answer only counts when the exact submitted code has a run on record that
passed every one of the problem's official asserts.

## Tools

| Tool | Does | Code |
|---|---|---|
| `get_problem` | Returns an MBPP problem's statement, entry-point function name, setup code and assert tests | `src/plugin/problems.py` |
| `run_tests` | Runs code against the problem's asserts in a `python -I` child process (10 s limit), and writes the run record `runs/<task_id>/<sha256 of code>.json` | `src/plugin/runner.py` |
| `official_tests` | Returns the official tests and their SHA-256 digest; the `solve-problem` reference | `src/plugin/problems.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `solve-problem` | Writes a Python solution to an MBPP problem that passes its official tests | `agent`, with `get_problem` and `run_tests`; reference `official_tests` |

### How the verdict is decided

The verifier may not run code, so the evidence is the run record that only
`run_tests` writes. `verifier/run.py` hashes the submitted code, reads
`runs/<task_id>/<hash>.json` from the workspace and approves only when:

- the record exists (code that was never run, or was edited after its run, has no record);
- it is for the requested task and exactly this code;
- its `tests_sha256` equals the digest pinned by `official_tests` before the agent started;
- it covers every official assert, and every one passed with no load error.

The score is the fraction of official asserts that passed. `run_tests` is
hardened against ways of passing without solving the problem:

- **Always-equal objects.** For an `assert f(x) == y` test, both sides are
  evaluated and the result must be made of the same built-in kinds as the
  expected value. A custom object whose `__eq__` returns `True` fails. The
  standard library's own `collections` subclasses (such as `Counter`) count as
  their base type.
- **Endless loops** time out, and the whole process group is killed.
- **`exit()`** during loading or a test counts as a failure.
- **Forged records.** The child runs in `.exec/`. If it changes anything under
  `runs/`, that change is undone and the run fails.

Every one of the 500 MBPP reference solutions passes `run_tests`.

Data: MBPP, Austin et al., *Program Synthesis with Large Language Models*
(2021), [google-research/mbpp](https://github.com/google-research/google-research/tree/master/mbpp),
CC BY 4.0, bundled in `src/plugin/data/mbpp_test.json`.

## Layout

```text
.
├── nanoagent.yaml   # manifest (a slimconfig ManifestConfig): id, runtime, permissions, tools, tasks
├── contract.py      # each tool's and task's typed input and output: slimconfig Output classes
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # environment variable NAMEs this plugin needs (none)
├── run.sh           # exits 0 when this environment can run the plugin
├── src/plugin/      # the MCP server (__main__.py, IMPLEMENTATIONS), problems.py, runner.py, data/
├── tests/           # test_verifier.py (correct, wrong, missing, malformed, boundary) and test_tools.py
├── ui/              # outputs drawn from their JSON Schema: renderers.js and renderers.css
├── product/         # the product page a catalog shows: product.yaml and icon.svg
└── verifier/        # deterministic verifier package: problem.py, run.py, checks.py
```

`contract.py` is the one place a value's shape is declared. Its `Output`
classes are the JSON Schemas the server offers and the agent sees. The
verifier imports only the standard library and `contract`.

## Develop and run

```bash
uv sync --extra dev
uv run pytest
```

Run the task with an agent through NanoAgent (`nanoagent plugin agent`), or on
RUSH Lab by asking the plugin's chat, for example "solve MBPP task 11".
