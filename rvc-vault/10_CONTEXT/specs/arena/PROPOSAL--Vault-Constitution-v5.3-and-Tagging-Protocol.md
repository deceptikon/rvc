---
type: proposal
title: Vault Constitution v5.3 Refinements & Unified @mention Attention Mechanism
author: Gemini (Antigravity)
created: 2026-09-13
status: draft
target_issue: STORY-106
tags: [governance, constitution, tagging, notifications, inbox, glasnost]
---

# PROPOSAL: Vault Constitution v5.3 Refinements & Unified @mention Attention Mechanism

> **Context:** Feedback and structural improvements following the STORY-106 review exchange,
> addressing intra-file rule duplication, the status of `00_INBOX/` (Glasnost), the review eviction gate,
> and introducing an automated `@mention` notification protocol for humans and AI devs.

---

## 1. Glasnost in `00_INBOX/` (The Open Drop-Box Rule)

### The Problem
Historically, `ROUTING.md` stated: *"The inbox must be empty at session end."*
In practice, this caused agents (Qwen, Big-Pickle) to treat any raw file, note, or incoming feedback
in `00_INBOX/` as an error state or an urgent trash fire to either immediately move, delete, or reject.
This creates a "dictatorship of the workflow" where neither humans nor external reviewers can drop raw,
unstructured thinking into the vault without breaking an agent's session boundary.

### The Refinement
1. **`00_INBOX/` is the sovereign front porch of the vault.**
   - Anyone—human owner, collaborator (Salwa), or any AI dev—may deposit raw memos, audit reports,
     chat transcripts, or drafts here at any time.
   - It is the **only un-gated write zone** in the vault.
2. **Session Gate Adjustment:**
   - An active agent is required to **scan and acknowledge** inbox items during SYNC, but an existing
     unprocessed discussion memo does **not** fail the SYNC gate.
   - Only actionable tickets/issues must be triaged into `20_NEXT` / `50_DEFERRED` / `40_DECIDE`.
     Discussion artifacts and raw inputs can remain in `00_INBOX/` until their respective author or
     triager files them deliberately.

---

## 2. Elimination of Intra-File Dual Truth in `ROUTING.md`

### The Problem
v5.1 merged `AGENTS.md` into `ROUTING.md` as Part II. While this killed inter-file drift, it introduced
**intra-file duplication**:
- **§4 vs. §15:** Both sections explain lifecycle bucket mechanics, transition commands (`git mv`),
  and RVC CLI commands.
- **§5 vs. §16:** The §5 table defines the WRAP phase; §16 defines "End-of-Session Handover" with an
  almost identical checklist.

### The Refinement
Enforce the law: **One rule, one section, one truth.**
- **Part I is the exhaustive Law.** All bucket definitions, transitions, eviction checks, and phase
  rituals live in §§1–6.
- **Part II is the Developer Orientation & Operational Map.**
  - **§15** becomes a lightweight map and cross-link:
    > *"Issue states are purely folder-derived. See §4 for transition mechanics and eviction gates."*
  - **§16** becomes a single operational summary pointing to §5 WRAP:
    > *"Follow the WRAP ritual (§5). Append discoveries to `DECISIONS.md` or `GOTCHAS.md` per §16.1 caps."*

---

## 3. Pure Folder-as-State for Debates (Abolishing `status: open|resolved`)

### The Problem
`ROUTING.md` states: *"The state of any issue is its folder. There is no second state."*
Yet debate templates and debate files enforce frontmatter `status: open` / `status: resolved`, while
simultaneously requiring `git mv` to `90_ARCHIVE/done/`.
This is a textbook dual-truth leak. If an agent moves the file but misses frontmatter, or vice-versa,
tools and humans see conflicting signals.

### The Refinement
- **Drop `status:` from debate frontmatter.**
- **Bucket location is the sole state truth:**
  - `40_DECIDE/debates/*.md` = **Active / Open Debate**.
  - `90_ARCHIVE/done/*.md` = **Resolved / Archived Debate**.
- When a debate reaches consensus, the concluding agent appends the `## VERDICT` section, logs one entry
  to `10_CONTEXT/DECISIONS.md`, and runs `git mv` to `90_ARCHIVE/done/`.

---

## 4. Fixing the Review Eviction Precondition Gate

### The Trap Discovered in `Q-STORY-106-review-loop`
The preliminary agreement between Q and D stated:
> *"At eviction time, a `60_DONE` item carrying a `❌` review section with no newer author-reply section
> fails the 'no reopen' precondition and is not evicted."*

**The Loophole:**
If a reviewer posts `❌ Blocking`, and the author simply appends `## Re: Review:` saying *"I disagree,
won't fix"*, a "newer author-reply section" now exists! Under that literal phrasing, the issue would
pass eviction and be archived into cold storage (`90_ARCHIVE/done/`) with an active, unverified defect.

### The Refined Eviction Rule
A `60_DONE` item carrying a `❌ Blocking` review fails the eviction precondition **regardless of author rebuttals**.
It can only be cleared for eviction via one of three doors:
1. **Reviewer Sign-off:** The reviewer posts a subsequent `## Review:` section with `✅ Pass` or `⚠️ Pass-with-deltas`.
2. **Escalation to Arena:** The issue is formally moved (`git mv`) to `40_DECIDE` for structured deliberation.
3. **Human Gate Override:** The human owner (`@deceptikon`) explicitly posts an approval section overriding the block.

---

## 5. Unified Attention & `@mention` Protocol

### Rationale
Human developers and AI agents need an unambiguous, low-overhead way to signal: *"I need your input on this."*
File-invites (`INVITE--to-*.md`) create orphaned files without clear lifecycles, and scanning every file's
`author:`/`invite:` frontmatter causes false alarms.

### Canonical Identity Map
To prevent string-matching bugs across different tools and models:

| Entity | Role | Canonical Tag | CLI Token / Env | Full Identity / Model |
|---|---|---|---|---|
| **Lexx** | Project Owner / Lead | `@deceptikon` | `deceptikon` | Human Owner |
| **Salwa** | Ingestion Lead | `@salwa` | `salwa` | Human Ingestion Engineer (`s.essid@alfoadia.com.sa`) |
| **Qwen** | Sovereign / Algo Dev | `@qwen` | `Q` | `Qwen Code` |
| **Big-Pickle** | Systems Dev | `@pickle` | `D` | `opencode/big-pickle` |
| **Gemini** | Architectural Dev | `@gemini` | `G` | `Antigravity / Gemini 3.8` |
| **Claude** | Ingestion Dev | `@claude` | `C` | `Anthropic / Claude Code` |

### The Attention Mechanism: Markdown Checkboxes
Instead of mutating markdown body text (e.g. replacing `@deceptikon` with `@@deceptikon`, which corrupts
historic sections and causes git merge conflicts), actionable requests for attention use native
**Markdown action items**:

```markdown
- [ ] @deceptikon: Human gate sign-off needed for schema migration in [[STORY-100]]
- [ ] @qwen: Verify RRF fusion key test cases
```

When completed, the tagged party simply checks the box (or the replying agent's tool checks it):
```markdown
- [x] @deceptikon: Approved 2026-09-13 (VERDICT logged)
```

### The Attention Scanner (`scripts/scan_mentions.sh`)
A lightweight bash script callable manually or via cron/hook:
1. Greps `00_INBOX`, `20_NEXT`, `30_ACTIVE`, and `40_DECIDE` for `- [ ] @<me>`.
2. In `40_DECIDE/debates/`, checks the **last section header** (`## <Author>@<date>`):
   - If the last header is **not** you, and you are listed as a participant or tagged in the question block,
     it flags: `Debate <slug> — YOUR TURN`.
   - If the last header **is** you: It flags: `Debate <slug> — Waiting on <OtherDev>`.
3. **Notification Routing:**
   - For **humans** (`@deceptikon`, `@salwa`): Sends a system notification (`notify-send`, Dunst, or terminal alert).
   - For **AI devs**: Prints clean status to `session_bootstrap.sh` during the SYNC phase, or feeds the debate turn-runner.

---

## 6. Summary of Proposed Constitutional Edits

1. **§1 (The Tree):** Define `00_INBOX` as open drop-box; triage duty is acknowledge-and-route, not erase-or-die.
2. **§4 (Eviction Check):** Add the tightened `❌ Blocking` review eviction gate (author rebuttal alone cannot bypass).
3. **§5.1 (Debates Arena):**
   - Remove frontmatter `status:`.
   - Turn detection derives from the last `## Author@date` header.
   - Replace standalone `INVITE--to-*.md` files with inline `- [ ] @mention` tasks.
4. **§§15–16:** Convert into thin pointers back to §§4–5 to enforce single-source-of-truth.
