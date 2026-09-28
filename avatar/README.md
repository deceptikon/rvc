# avatar — the vault's Telegram presence (v0)

One bot, personal channel: the vault pings people who owe a turn on the plate.
Group/dev–dev talks are later stories (see `rvc-vault/20_NEXT/EPIC-004`).

## Setup (one time)

1. **Bot**: talk to [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.
2. **Config**: `cp avatar/config.example.json avatar/config.json`, paste the token.
3. **Subscribe**: write anything to your bot in Telegram (a DM — that's the whole channel).
4. **Link yourself**: `python3 avatar/avatar.py updates` → prints `… → chat_id 111111111`.
   Put that number into `config.json` under your seat.
5. **Fire**: `python3 avatar/avatar.py notify --vault /home/lexx/X/ADLAI/adlai-vault`

## Cron (when it proves itself)

```
17 9,18 * * *  python3 /home/lexx/X/TEAMFLOW/RVC/avatar/avatar.py notify --vault /home/lexx/X/ADLAI/adlai-vault >> /tmp/avatar.log 2>&1
```

## Verbs

| verb | what |
|---|---|
| `updates` | list chat_ids of everyone who wrote to the bot (bootstrap) |
| `notify --vault V [--force]` | owed-turn digests, deduped per day via `.avatar-state.json` |
| `send "text" [--chat N]` | message a subscriber (default: first seat with a chat_id) |
| `hook <vault-path>` | wire a post-commit hook: every commit checks for new owed turns (STORY-041) |

No token → dry-run: every message prints to stdout instead of sending.
Token can come from `AVATAR_TG_TOKEN` env instead of the config file.
`config.json` and `.avatar-state.json` are gitignored — the token never lands in git.
