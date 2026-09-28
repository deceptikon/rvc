#!/usr/bin/env python3
"""avatar — the vault's Telegram presence, v0 (STORY-040, EPIC-004).

Outbound only, personal channel: the bot DMs seats who owe a turn on the
plate. No group needed — the owner subscribes to the bot in a private chat.

  avatar updates              who wrote to the bot? (chat_id bootstrap)
  avatar notify --vault V     owed turns on the plate -> per-seat DM digest
  avatar send "text"          message the first (or --chat N) subscriber

No token -> dry-run: messages print instead of sending. Stdlib only.

Config: avatar/config.json (token, seats) or ~/.config/avatar/config.json.
    {
      "token": "<from @BotFather>",
      "seats": {"@deceptikon": {"chat_id": 111111111}, "@salwa": {}}
    }
A seat with a chat_id gets a DM; without one it is listed in the run summary
(add their chat_id after they /start the bot and run `avatar updates`).
"""

import datetime
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(REPO, ".avatar-state.json")
CONFIG_CANDIDATES = [
    os.path.join(REPO, "config.json"),
    os.path.expanduser("~/.config/avatar/config.json"),
]


def load_config():
    for path in CONFIG_CANDIDATES:
        if os.path.exists(path):
            with open(path) as f:
                cfg = json.load(f)
            cfg["token"] = os.environ.get("AVATAR_TG_TOKEN", cfg.get("token", ""))
            return cfg
    example = os.path.join(REPO, "config.example.json")
    sys.exit(f"no config — copy {example} to {CONFIG_CANDIDATES[0]}")


def tg(cfg, method, **params):
    if not cfg["token"]:
        print(f"[dry] {method} → chat {params.get('chat_id')}:\n{params.get('text', '')}\n")
        return None
    url = f"https://api.telegram.org/bot{cfg['token']}/{method}"
    data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=15) as r:
            return json.load(r)
    except Exception as exc:
        print(f"[avatar] {method} failed: {exc}", file=sys.stderr)
        return None


def owed_turns(vault, handle):
    """(path, ask) rows in the YOU OWE A TURN lane, via the rvc CLI surface."""
    out = subprocess.run(
        ["rvc", "--path", os.path.dirname(os.path.abspath(vault)),
         "plate", "--as", handle.lstrip("@"), "--format", "json"],
        capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        return []
    rows = json.loads(out.stdout).get("lanes", {}).get("owes_turn", [])
    return [(r.get("path", "?"), r.get("ask", "")) for r in rows]


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f)
    return {}


def cmd_updates(cfg):
    """Print recent senders with their chat_ids — the subscription bootstrap."""
    res = tg(cfg, "getUpdates")
    if not res or not res.get("ok"):
        print("no updates (or no token — dry mode only works for local verbs)")
        return
    seen = {}
    for u in res.get("result", []):
        msg = u.get("message") or u.get("edited_message") or {}
        chat, frm = msg.get("chat", {}), msg.get("from", {})
        key = chat.get("id")
        if key is not None:
            seen[key] = f"{frm.get('username') or frm.get('first_name', '?')} → chat_id {key} ({chat.get('type', '?')})"
    if not seen:
        print("no messages yet — write anything to the bot in Telegram, then rerun")
    for line in seen.values():
        print(line)


def cmd_notify(cfg, vault, force=False):
    state = load_state()
    today = datetime.date.today().isoformat()
    if state.get("today") != today:
        state = {"today": today, "sent": {}}
    for handle, seat in cfg.get("seats", {}).items():
        owed = owed_turns(vault, handle)
        fresh = [(p, a) for p, a in owed if force or f"{handle}|{p}|{a}" not in state["sent"]]
        if not fresh:
            continue
        lines = [f"⏰ @{handle.lstrip('@')} — {len(fresh)} turn(s) owed on the "
                 f"{os.path.basename(os.path.abspath(vault))} plate:"]
        lines += [f"• {os.path.basename(p)}" + (f" — {a}" if a else "") for p, a in fresh]
        chat = seat.get("chat_id")
        if chat:
            res = tg(cfg, "sendMessage", chat_id=chat, text="\n".join(lines))
        else:
            res = None
            print(f"[skip] @{handle.lstrip('@')} owes {len(fresh)} but has no chat_id yet "
                  f"(they must /start the bot; then `avatar updates`)")
        # Only delivered messages count as sent — a dry-run must never poison
        # the dedupe state, or the first real run skips the real ping.
        if res and res.get("ok"):
            for p, a in fresh:
                state["sent"][f"{handle}|{p}|{a}"] = today
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=1)


HOOK_MARKER = "# avatar:"


def cmd_hook(vault):
    """Install a fire-and-forget post-commit hook (the 'crutch', STORY-041)."""
    vault = os.path.abspath(vault)
    # Resolve through git itself: vaults live in worktrees and submodules,
    # where .git is a file and hooks live in the real git dir.
    res = subprocess.run(["git", "-C", vault, "rev-parse", "--absolute-git-dir"],
                         capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"not a git repo: {vault}")
    hooks_dir = os.path.join(res.stdout.strip(), "hooks")
    script = os.path.abspath(__file__)
    block = (f"{HOOK_MARKER} crutch — a commit changed vault state; ping NEW owed turns.\n"
             f"(python3 {script} notify --vault {vault} >> /tmp/avatar.log 2>&1 &)\n")
    path = os.path.join(hooks_dir, "post-commit")
    if os.path.exists(path):
        with open(path) as f:
            if HOOK_MARKER in f.read():
                print(f"[avatar] post-commit hook already wired: {path}")
                return
        with open(path, "a") as f:
            f.write("\n" + block)
    else:
        with open(path, "w") as f:
            f.write("#!/bin/sh\n" + block)
    os.chmod(path, 0o755)
    print(f"[avatar] wired {path} -> notify on every commit")


def cmd_send(cfg, text, chat=None):
    chat = chat or next((s.get("chat_id") for s in cfg.get("seats", {}).values()
                         if s.get("chat_id")), None)
    if not chat:
        sys.exit("no chat: pass --chat N or set a seat's chat_id")
    tg(cfg, "sendMessage", chat_id=chat, text=text)


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "help"
    rest = args[1:]
    cfg = load_config()

    if cmd == "notify":
        vault = rest[rest.index("--vault") + 1] if "--vault" in rest else None
        if not vault:
            sys.exit("usage: avatar notify --vault <vault-path>")
        cmd_notify(cfg, vault, force="--force" in rest)
    elif cmd == "send":
        chat = None
        if "--chat" in rest:
            i = rest.index("--chat")
            chat = int(rest[i + 1])
            del rest[i:i + 2]
        cmd_send(cfg, " ".join(rest), chat)
    elif cmd == "hook":
        if not rest:
            sys.exit("usage: avatar hook <vault-path>")
        cmd_hook(rest[0])
    elif cmd == "updates":
        cmd_updates(cfg)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
