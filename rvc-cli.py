#!/usr/bin/env python3
"""RVC CLI - Vault Context Interface & Backward-Compatibility Façade.

This module serves as the primary CLI entrypoint and re-exports all primitives
from the modular `rvc` package (`core`, `git`, `issues`, `context`, `plate`, `doctor`, `cli`).
Existing test suites and scripts importing `rvc_cli` remain 100% compatible.
"""

import os
import sys
import gc
import types

# Ensure repository root is in sys.path when invoked directly or via symlink
REPO_DIR = os.path.dirname(os.path.realpath(__file__))
if REPO_DIR not in sys.path:
    sys.path.insert(0, REPO_DIR)

import rvc.core as _core
import rvc.git as _git
import rvc.context as _context
import rvc.plate as _plate
import rvc.doctor as _doctor
import rvc.issues as _issues
import rvc.cli.commands as _commands
import rvc.cli.install as _install
from rvc.cli.main import main

_SUBMODULES = (_core, _git, _context, _plate, _doctor, _issues, _commands, _install)

# Populate module namespace with all public and private attributes from submodules
for mod in _SUBMODULES:
    for k, v in mod.__dict__.items():
        if not (k.startswith("__") and k.endswith("__")):
            globals()[k] = v

globals()["main"] = main


# ── Monkeypatch Forwarding & Dynamic Delegation for Test Compatibility ────────
class _FacadeModule(type(sys)):
    """Propagates runtime attribute lookups and assignments across submodules."""
    def __getattr__(self, name):
        if name == "main":
            return main
        for mod in _SUBMODULES:
            if hasattr(mod, name):
                return getattr(mod, name)
        raise AttributeError(f"module 'rvc_cli' has no attribute '{name}'")

    def __setattr__(self, name, val):
        super().__setattr__(name, val)
        for mod in _SUBMODULES:
            if hasattr(mod, name):
                setattr(mod, name, val)


_mod = sys.modules.get(__name__) or next(
    (obj for obj in gc.get_objects()
     if isinstance(obj, types.ModuleType) and getattr(obj, '__name__', None) == __name__ and obj.__dict__ is globals()),
    None
)
if _mod is not None:
    _mod.__class__ = _FacadeModule


if __name__ == "__main__":
    sys.exit(main())
