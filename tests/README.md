# RVC local test suite

A zero-dependency, stdlib-only test suite for `rvc-cli.py`. It is an independent
tool: no pytest, no network, no conductor/ADLAI fixtures — plain `python3`.

## Run

```bash
cd ~/X/TEAMFLOW/RVC
python3 tests/run_tests.py          # everything
python3 tests/run_tests.py plate    # only modules matching 'plate'
python3 tests/run_tests.py -v       # verbose: name every test
```

Exit code is 0 when every test passes, 1 otherwise.

## Layout

| File | What it covers |
|------|----------------|
| `run_tests.py` | Runner — discovers `test_*.py`, runs every `test_*` callable |
| `helpers.py` | Scaffolds scratch newvault trees in `/tmp/opencode`, loads `rvc-cli.py` in-process |
| `test_create_mints_id.py` | STORY-028 — `rvc create` mints `id:`/`title:`, stable high-water-mark padding |
| `test_plate_decide.py` | STORY-031 — `rvc plate` renders `40_DECIDE` root stories in WAITING |

## Why this exists

- The repo previously had **no local tests**; the suite covering `rvc-cli.py` lived in
  `~/X/TEAMFLOW/conductor/tests/test_rvc_cli.py` (external). STORY-028 AC4 and STORY-031 AC3
  require regression tests, so the harness is deliberately local and dependency-free.
- Scratch vaults are created under `/tmp/opencode` with **no `.git`**, so
  `sync_after`/`find_git_root` no-op inside tests — a failing test can never commit.
- Tests call CLI functions in-process via `importlib` (the filename `rvc-cli.py`
  is not a valid module name, so the loader in `helpers.py` names it `rvc_cli`).

## Adding a test

```python
# tests/test_my_story.py
from helpers import make_vault, rvc_cli

def test_something():
    _, vault = make_vault()
    assert rvc_cli._next_id(vault, "STORY") == "STORY-01"
```

Plain `assert` — the runner catches exceptions and reports the failing file/test
with a traceback.