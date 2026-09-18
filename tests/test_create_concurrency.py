#!/usr/bin/env python3
"""Concurrent-`create` safety: the ID mint + file creation critical section is
serialized by a cross-process flock (`vault_create_lock`).

Race being pinned: two creates scanning for the max ID concurrently both mint
`STORY-XXX+1` and one overwrites the other's file. With the lock, N concurrent
creates on a fresh vault must yield exactly N distinct sequential IDs.
"""

import multiprocessing
import os

import helpers
from helpers import make_vault, rvc_cli

CONCURRENCY = 8


def _create_one(vault, title, out_q):
    try:
        path = rvc_cli.cmd_create_issue(vault, title, priority="P1")
        out_q.put(("ok", os.path.basename(path)))
    except Exception as e:  # noqa: BLE001 — child processes report back via queue
        out_q.put(("err", repr(e)))


def test_concurrent_creates_mint_unique_ids():
    """N parallel creates mint N distinct sequential IDs (no duplicates, no clobber)."""
    _, vault = make_vault()

    ctx = multiprocessing.get_context("fork")
    q = ctx.Queue()
    procs = [
        ctx.Process(target=_create_one, args=(vault, f"Concurrent {i}", q))
        for i in range(CONCURRENCY)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
        assert p.exitcode == 0, f"child create failed with exit {p.exitcode}"

    results = [q.get(timeout=5) for _ in procs]
    errors = [r for r in results if r[0] == "err"]
    assert not errors, f"concurrent creates errored: {errors}"

    ids = [r[1] for r in results]
    assert len(ids) == CONCURRENCY
    assert len(set(ids)) == CONCURRENCY, f"duplicate IDs minted: {sorted(ids)}"

    # Sequential from STORY-01: exactly the set {01..NN}.
    nums = sorted(int(i.split("-")[1]) for i in ids)
    assert nums == list(range(1, CONCURRENCY + 1)), f"non-sequential IDs: {nums}"

    # Every minted file physically exists and carries a unique id: frontmatter.
    for fname in ids:
        path = os.path.join(vault, "00_INBOX", fname)
        assert os.path.exists(path), f"missing minted file: {path}"
        fm = helpers.read_frontmatter(path)
        assert fm["id"] == fname.split("-")[0] + "-" + fname.split("-")[1].split(".")[0]


def test_lock_file_cleaned_up_after_success():
    """STORY-130: a successful create removes `.rvc-create.lock` — no residue.

    The old contract left the marker file behind forever; it accumulated
    untracked at the vault root with a stale `pid=` that read as an active lock.
    """
    _, vault = make_vault()
    rvc_cli.cmd_create_issue(vault, "Lock Probe", priority="P1")
    lock = os.path.join(vault, rvc_cli.LOCK_FILE_NAME)
    assert not os.path.exists(lock), \
        f"lock must be cleaned up on success, still present: {lock}"


def test_lock_reclaims_stale_pid_from_dead_process():
    """STORY-130: a leftover lock naming a dead process is reclaimed, not held."""
    import subprocess as _sp
    import sys as _sys
    probe = _sp.Popen([_sys.executable, "-c", "pass"])
    dead_pid = probe.pid
    assert probe.wait() == 0

    _, vault = make_vault()
    lock = os.path.join(vault, rvc_cli.LOCK_FILE_NAME)
    with open(lock, "w") as f:
        f.write(f"pid={dead_pid}\n")

    path = rvc_cli.cmd_create_issue(vault, "Stale Probe", priority="P1")
    assert os.path.exists(path), "create must succeed over a stale lock"
    assert not os.path.exists(lock), "stale lock must be reclaimed and removed"


def test_pid_alive_distinguishes_live_dead_garbage():
    """Liveness probe: live pid True, dead pid False, garbage False."""
    import subprocess as _sp
    import sys as _sys
    assert rvc_cli._pid_alive(os.getpid()) is True
    probe = _sp.Popen([_sys.executable, "-c", "pass"])
    dead_pid = probe.pid
    assert probe.wait() == 0
    assert rvc_cli._pid_alive(dead_pid) is False
    assert rvc_cli._pid_alive("not-a-pid") is False
    assert rvc_cli._pid_alive("0") is False
    assert rvc_cli._pid_alive("-5") is False


def test_lock_degrades_gracefully_without_primitives():
    """With neither fcntl nor msvcrt (portability fallback), create still works.

    Pins the cross-platform contract from STORY-013 AC4: the CLI must load and
    mint on a platform with no locking module, never hard-fail.
    """
    _, vault = make_vault()
    saved = (rvc_cli._fcntl, rvc_cli._msvcrt)
    rvc_cli._fcntl = None
    rvc_cli._msvcrt = None
    try:
        path = rvc_cli.cmd_create_issue(vault, "No-primitive Probe", priority="P1")
    finally:
        rvc_cli._fcntl, rvc_cli._msvcrt = saved
    assert os.path.basename(path).startswith("STORY-01-")