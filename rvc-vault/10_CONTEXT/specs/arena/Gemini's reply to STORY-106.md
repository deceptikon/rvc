Here is my professional review on the vault protocol, the debate arena, and the tooling layer. As requested, this review is strictly read-only: no files or git state have been touched.

---

### 1. The Single-Context-File Fold (`ROUTING.md` v5.1)

* **The Win:** Folding `AGENTS.md` into `ROUTING.md` (Part I = Law, Part II = Guide) and repointing all root symlinks (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `QWEN.md`) directly to `adlai-vault/10_CONTEXT/ROUTING.md` successfully eliminates the historical drift between `AGENTS.md` and `ROUTING.md`.
* **The Internal Dual-Truth Leak:** While inter-file drift was killed, **intra-file dual truth was created**:
  * **§4 vs. §15:** Part I §4 defines lifecycle mechanics (`git mv`, eviction checks, RVC CLI verbs). Part II §15 re-explains the exact same lifecycle mechanics and transition rules under "Issue Lifecycle — folder = state".
  * **§5 vs. §16:** Part I §5 table defines the WRAP phase (commit, transition to `60_DONE`, append `DECISIONS.md`/`GOTCHAS.md`). Part II §16 re-defines "End-of-Session Handover" with an identical 4-step checklist.
  * *Why this bites:* When a rule evolves (e.g., adding review precondition gates to eviction in §4), someone will update §4 and forget §15, or vice-versa.
* **Recommendation:** Strip §15 and §16 down to pure one-line cross-references pointing back to §4 and §5. In a constitution, **every rule must appear exactly once**.

---

### 2. The Debates Arena (§5.1) & Dual Truth in Debate Files

* **The Leak — `status: open|resolved` vs. Folder-as-State:**
  * The constitutional axiom is: *"The state of any issue is its folder. There is no second state. Frontmatter `status:` on `STORY-*`/`EPIC-*` files is forbidden."*
  * Yet `_TEMPLATE--debate.md` and all debate files introduce `status: open` in frontmatter, and their closing ritual requires editing `status: resolved` **and** executing a `git mv` to `90_ARCHIVE/done/`.
  * `session_bootstrap.sh` line 90 even reveals the contradiction in its comment:
    `if ! grep -qi '^status: *open' "$debate"; then continue; fi   # resolved debates exit anyway`
  * *Failure mode:* If a debate file is moved to `90_ARCHIVE/done/` but someone forgets to flip frontmatter, or if frontmatter is changed but `git mv` is omitted, the two sources of truth diverge immediately.
* **Recommendation:** Abolish `status:` in debate frontmatter completely.
  * Residing in `40_DECIDE/debates/` **is** the open state.
  * Moving to `90_ARCHIVE/done/` with a `## VERDICT` section **is** the resolved state. Folder = state everywhere, without exception.

---

### 3. The `INVITE--to-<name>.md` Ghost Alert & Dual-Invite Leak

* **The Leak:** An invitation currently lives in two places simultaneously:
  1. The debate file frontmatter (`invite: D`)
  2. A standalone markdown file (`40_DECIDE/debates/INVITE--to-D.md`)
* **The Mechanical Trap:**
  * `INVITE--to-*.md` has no closing ritual, no transition verb, and no eviction rule anywhere in the vault.
  * In `session_bootstrap.sh` (lines 98–105), the script loops over `"$DEBATES_DIR"/INVITE--to-*.md` and alerts the agent whenever the file exists.
  * *Live bug:* `INVITE--to-D.md` is sitting in the vault right now referencing both `Q-STORY-106-review-loop` and `Q-STORY-106-live-turns`. Even after `review-loop` converged, `INVITE--to-D.md` remains in `debates/`, permanently shouting at D on every single bootstrap run until a human manually removes it.
* **Recommendation:** Eliminate separate `INVITE--to-*.md` files. The debate file itself carries `invite: <who>` and is already parsed by the scan. Having a separate invite file is a duplicate artifact with no automated lifecycle.

---

### 4. `session_bootstrap.sh` DECIDE-QUEUE Scan: Static Matching vs. Dynamic Turns

* **The Flaw — Indiscriminate Owner Matching:**
  * Lines 91–95 read:
    ```bash
    owners=$(grep -iE '^(invite|author):' "$debate" | tr '[:upper:]' '[:lower:]')
    if echo "$owners" | grep -qiF "$ME_ID"; then
      DECIDE_QUEUE+="- $dbase — open, awaiting $ME_ID's verdict"$'\n'
    fi
    ```
  * *Failure mode:* If Q creates `Q-STORY-106-live-turns.md` (`author: Q`, `invite: D`), `owners` contains both `Q` and `D`. When Q runs `session_bootstrap.sh`, it matches Q and prints:
    `- Q-STORY-106-live-turns.md — open, awaiting Q's verdict`!
    Q is waiting on D, yet the script tells Q that Q is blocking on Q's own verdict. The scan has no concept of whose turn it is; both participants are permanently alerted until the debate exits.
* **The Identity Mismatch Trap:**
  * Line 83 extracts `ME_ID=${ME%%[ (]*}`. If `STATE.json` has `"agent": "Qwen Code"`, `ME_ID` becomes `Qwen`. But the debate files use `author: Q`. Matching `Qwen` against `q` fails.
  * Similarly, if an OpenCode session passes `AGENT=big-pickle`, matching `big-pickle` against `invite: d` fails. The decide queue silently drops the debate unless the user remembers to pass the exact 1-letter token `AGENT=D`.
* **Recommendation:**
  1. **Turn detection must inspect the last section header:**
     Parse the last section in the debate file: `last_author=$(grep -oE '^## [A-Za-z0-9_-]+@' "$debate" | tail -1 | tr -d '#@ ')`.
     * If `last_author == ME_ID`: You already spoke. Status: *Waiting on other dev* (do not block SYNC).
     * If `last_author != ME_ID` (or file only has Question Block): Status: *Your turn to speak*.
  2. **Canonical identity aliasing:** Normalize identities explicitly (`D` = `big-pickle`, `Q` = `Qwen`, etc.) so the scan doesn't silently break on standard agent strings.

---

### 5. Input on `Q-STORY-106-live-turns.md` (Live Dev-to-Dev Chat)

* **Stress-testing Q's Option A (`rvc debate say/wait/log`):**
  * **The "Wait" Fallacy:** Option A asserts: *"Agents loop wait → read → say → wait... No daemon, no server — git stays the only state."*
    * This is mechanically impossible for headless agents. An LLM agent is not a persistent daemon. When agent Q appends a turn and runs `rvc debate wait`, **agent D is not running**. Nothing wakes D up unless an orchestrator launches D's process. Without an orchestrator, Q simply sits in a blocking wait loop until timeout and exits with error.
  * **Violation of Decisions & Domain Separation (§7):**
    * The logged decision for STORY-106 (in `10_CONTEXT/DECISIONS.md`, 2026-09-13) explicitly states: *"decide-queue scan lives in `session_bootstrap.sh`... NOT the RVC CLI — the CLI stays identity-free and tree-config-only (STORY-105 law)."*
    * Adding `--as Q|D` and debate-turn transport to `rvc-cli` directly breaks that decision and couples RVC to agent identity.
* **The Realistic Mechanism for Zero Owner Relaying:**
  * The owner does not need in-agent blocking waits; the owner needs a **local turn-runner loop** on the host machine (e.g. `scripts/debate_runner.sh <debate-file>` or in TEAMFLOW):
    1. Reads the debate file to see who owes the next turn (from the last `## <Agent>@...` header).
    2. Invokes that agent's headless command (e.g. `opencode run --model ...` with a prompt containing previous turns).
    3. The agent writes its section and exits cleanly.
    4. Runner detects the append, commits it, and loops to the other agent.
    5. Stops automatically when a `## VERDICT` section appears or `max_turns` is reached, then pings the owner for human-gate sign-off.
  * *Verdict on deltas:*
    * **Delta 1 (Grammar):** Shared Markdown headers (`## <Author>@<date>`) only. Zero HTML comments.
    * **Delta 2 (Where wait lives):** Reject CLI `wait`. Use an external turn-runner script that invokes each agent in turn.
    * **Delta 3 (Domain boundary):** Keep RVC CLI identity-free; keep debate-running mechanics in tooling scripts / TEAMFLOW, keeping only debate law in ADLAI.

---

### 6. Critical Catch on Review Eviction Gate (`Q-STORY-106-review-loop.md`)

* **The Trap in Amendment 2 / Q's Nit:**
  * In `Q-STORY-106-review-loop.md`, Q and D agreed that at milestone close, a `60_DONE` issue carrying a `❌ Blocking` review section with **no newer author-reply section (`## Re: Review:`)** fails eviction.
  * *Look closely at what that phrasing implies:*
    1. Reviewer posts: `## Review: D@2026-09-13` → `❌ Blocking` (e.g., severe defect).
    2. Author appends: `## Re: Review: Q@2026-09-13` → *"I disagree, leaving as is."*
    3. The reviewer never accepted this rebuttal. The dispute is completely unresolved.
    4. Milestone eviction runs. It checks: *"Does this issue have a ❌ with no newer author reply?"*
    5. Because the author appended `## Re: Review:`, the check evaluates to **false**, and the issue **is evicted into cold storage (`90_ARCHIVE/done/`) with an active, unverified defect!**
* **Recommendation:**
  * An author rebuttal section must **not** clear the eviction block by itself.
  * An issue carrying a `❌ Blocking` review can only be evicted if:
    1. The reviewer posts a subsequent `## Review:` with `✅ Pass` or `⚠️ Pass-with-deltas`, OR
    2. The issue is moved to `40_DECIDE` (escalated to a debate), OR
    3. The human owner explicitly signs off an override.

---

### 7. Status of Active Issues & Verification

* `STORY-106` is currently in `60_DONE/` awaiting verification by `big-pickle + @deceptikon`.
* The live debate in `Q-STORY-106-review-loop.md` has converged cleanly. Once the review-loop debate is archived to `90_ARCHIVE/done/` and logged to `DECISIONS.md`, D can execute the agreed convention by appending its `## Review: big-pickle@2026-09-13` under `STORY-106`'s `### Verification` block, leaving the final sign-off section for `@deceptikon`.


***Note by deceptikon:***
***I strongly support PoV stated in this doc***