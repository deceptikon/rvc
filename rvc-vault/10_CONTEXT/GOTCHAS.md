# GOTCHAS — Non-obvious Bugs & Environment Traps (rvc-vault)

- **`rvc` on PATH** is the folder-as-state CLI (symlink → `~/X/TEAMFLOW/RVC/rvc-cli.py`).
  If that symlink ever points elsewhere (it used to target the parked plate-based "RVC 0-point"
  engine at `~/W/RVC_reload/rvc.py`), re-run `python3 rvc-cli.py install --force`.
  `session_bootstrap.sh`-style contracts should keep calling `$RVC_BIN` explicitly.
- **`rvc-vault/10_Issues` legacy paths are gone** — the repo's vault moved to the newvault tree
  (2026-09-13). Old links like `10_Issues/01_To_Do/...` resolve only through git history.
- **`find_vault_root` walks up 8 levels from CWD.** Running `rvc` inside a sibling vault can
  accidentally pick up that vault — verify with `--path` when unsure.