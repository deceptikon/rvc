#!/usr/bin/env python3
"""RVC local test runner — zero-dependency, stdlib only.

The suite is an independent tool: it needs no pytest, no network, no external
fixtures. It discovers `test_*.py` modules next to this file, runs every
`test_*` callable in each, and reports a pass/fail summary.

Usage:
    python3 tests/run_tests.py              # run everything
    python3 tests/run_tests.py plate        # only modules whose name contains 'plate'
    python3 tests/run_tests.py -v plate     # verbose: print each test name
"""

import importlib.util
import pathlib
import sys
import traceback

VERBOSE = "-v" in sys.argv
FILTER = next((a for a in sys.argv[1:] if not a.startswith("-")), "")


def discover_modules(tests_dir):
    """All test_*.py files in tests_dir, as (name, path)."""
    return [
        (p.stem, p)
        for p in sorted(tests_dir.glob("test_*.py"))
        if p.is_file()
    ]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_file(path):
    """Run one test module. Returns (passed, failed, failures)."""
    mod = load_module(path.stem, path)
    tests = [
        (name, fn)
        for name, fn in sorted(vars(mod).items())
        if name.startswith("test_") and callable(fn)
    ]
    passed, failed, failures = 0, 0, []
    for name, fn in tests:
        if VERBOSE:
            print(f"  {path.name}::{name}")
        try:
            fn()
        except Exception:
            failed += 1
            failures.append((path.name, name, traceback.format_exc()))
        else:
            passed += 1
    return passed, failed, failures


def main():
    tests_dir = pathlib.Path(__file__).resolve().parent
    modules = discover_modules(tests_dir)
    if FILTER:
        modules = [(n, p) for n, p in modules if FILTER in n]
    if not modules:
        print(f"No test modules found in {tests_dir}" + (f" matching '{FILTER}'" if FILTER else ""))
        return 1

    total_pass, total_fail, all_failures = 0, 0, []
    for name, path in modules:
        passed, failed, failures = run_file(path)
        total_pass += passed
        total_fail += failed
        all_failures.extend(failures)
        status = "ok" if failed == 0 else "FAIL"
        print(f"[{status}] {path.name}: {passed} passed, {failed} failed")

    print(f"\nTotal: {total_pass} passed, {total_fail} failed")
    for fname, test, tb in all_failures:
        print(f"\n--- {fname}::{test} ---")
        print(tb.rstrip())
    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())