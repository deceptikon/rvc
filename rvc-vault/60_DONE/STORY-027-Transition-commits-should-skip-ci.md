---
id: STORY-027
type: story
priority: P2
created: 2026-09-16
domain: workflow_meta
domain_tags: ["rvc", "ci", "git", "cost"]
imported-from: "ADLAI STORY-108 (checkbox 1)"
---

# STORY-027: Vault-transition commits should say `[skip ci]`

**Why this is here and not in ADLAI:** the file to change is `rvc-cli.py`, which is this repo. The
*other half* of ADLAI's original story — the `.gitlab-ci.yml` guard and the `rules:changes` footgun
analysis — stayed in ADLAI, because that is their pipeline and their correctness problem. A commit
message minted here should not be specified in a product vault, and vice versa.

---

Every `rvc issue <ID> <verb>` that auto-commits produces a commit touching only `.md` files in a
vault. Downstream projects that watch `**/*.md` in their CI will build a Docker image and redeploy a
VPS because an issue moved folders. ADLAI's CI is one of those projects.

## Acceptance criteria

1. Transition and creation commit messages minted by `rvc` carry `[skip ci]`
   (`sync_after` call sites and `cmd_create`).
2. The skip is **opt-out-able** per invocation, because a commit that mixes a vault move with a code
   change must still run CI — and `rvc` cannot see the rest of the user's index.
3. Document the honest limit: `[skip ci]` suppresses the pipeline, it does not prove the commit was
   docs-only. The safety net that proves it belongs in the consuming project's CI, not here — which
   is why ADLAI kept `test_ci_rules.py` in its own suite rather than graduating it.
4. Never silently skip a commit that touched a non-markdown path.

## Verification

- Unit test: a transition commit message contains the skip token; with `--no-skip-ci` it does not.
- Manual: `rvc issue <ID> start` in a scratch repo, inspect the minted message.
