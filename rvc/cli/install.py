"""CLI installation handler: transparent and straightforward launcher shim."""

import os
import sys

SHIM_TEMPLATE = '''#!/usr/bin/env python3
# rvc - transparent launcher shim
# Target Repository: {repo_root}
import os
import sys
import runpy

repo_root = "{repo_root}"
source = "{source}"

if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

sys.argv[0] = source
runpy.run_path(source, run_name="__main__")
'''


def _is_our_target(target, repo_root, source):
    """Check if target is already our symlink or launcher shim."""
    if os.path.islink(target):
        return os.path.realpath(target) == source
    if os.path.isfile(target):
        try:
            with open(target, "r", errors="replace") as f:
                content = f.read()
            return (repo_root in content) and ("rvc" in content)
        except OSError:
            return False
    return False


def cmd_install(install_dir=None, force=False, check=False):
    """Install: create a transparent launcher shim as `rvc` on PATH (default ~/.local/bin).

    Idempotent — a second run verifies and returns 0. --check verifies only.
    Refuses to clobber an existing unrelated file unless --force.
    """
    install_dir = install_dir or os.path.expanduser("~/.local/bin")
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    source = os.path.join(repo_root, "rvc-cli.py")
    target = os.path.join(install_dir, "rvc")

    if check:
        if _is_our_target(target, repo_root, source):
            print(f"OK: {target} -> {source}")
            return 0
        print(f"NOT INSTALLED: {target} -> {source}")
        return 1

    if os.path.lexists(target):
        if _is_our_target(target, repo_root, source):
            # Already points to this repo; refresh shim cleanly
            if not os.path.islink(target):
                print(f"Already installed: {target} -> {source}")
                return 0
        elif not force:
            print(f"Refusing to overwrite {target} (not this rvc). Pass --force to override.",
                  file=sys.stderr)
            return 1

    os.makedirs(install_dir, exist_ok=True)
    if os.path.lexists(target):
        try:
            os.remove(target)
        except OSError as e:
            print(f"Error removing existing {target}: {e}", file=sys.stderr)
            return 1

    shim_content = SHIM_TEMPLATE.format(repo_root=repo_root, source=source)
    try:
        with open(target, "w") as f:
            f.write(shim_content)
        os.chmod(target, 0o755)
    except OSError as e:
        print(f"Error writing launcher shim to {target}: {e}", file=sys.stderr)
        return 1

    print(f"Installed launcher shim: {target} -> {source}")
    print("Install dir must be on PATH. Next: `rvc project init <dir>` to RVC-fy a project.")
    return 0
