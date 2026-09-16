"""Command definitions, argument schemas, and help generation for RVC CLI."""

import os
import sys
import re
import argparse

from rvc.core import (
    find_vault_root, resolve_tree, cmd_init, cmd_project_init, run_cmd
)
from rvc.git import cmd_git_commit_all
from rvc.issues import (
    cmd_get, cmd_issue_action, cmd_issue_list, cmd_create_issue, cmd_search
)
from rvc.context import (
    cmd_context, context_cache_update, CONTEXT_DEFAULT_TOP_K,
    CONTEXT_DEFAULT_BUDGET, CONTEXT_CACHE_NAME
)
from rvc.plate import cmd_plate
from rvc.doctor import cmd_doctor
from rvc.cli.install import cmd_install
_orig_print = print


def _color_line(line: str) -> str:
    BOLD = "\033[1m"
    CYAN = "\033[1;36m"
    YELLOW = "\033[1;33m"
    GREEN = "\033[1;32m"
    DIM = "\033[90m"
    RESET = "\033[0m"

    if line.startswith("rvc") and (" — " in line or " - " in line):
        parts = line.split(" — ", 1) if " — " in line else line.split(" - ", 1)
        sep = " — " if " — " in line else " - "
        return f"{CYAN}{parts[0]}{RESET}{sep}{BOLD}{parts[1]}{RESET}"
    elif (line.endswith(":") or line.endswith(":)")) and not line.startswith(" "):
        return f"{YELLOW}{line}{RESET}"
    elif re.match(r"^\s{2}[a-z-]+(?:\s|$)", line):
        m = re.match(r"^(\s{2})([a-z-]+)(.*)$", line)
        return f"{m.group(1)}{GREEN}{m.group(2)}{RESET}{m.group(3)}"
    else:
        l = re.sub(r"(--[a-zA-Z0-9-]+)", f"{CYAN}\\1{RESET}", line)
        l = re.sub(r"(\(default:[^\)]+\))", f"{DIM}\\1{RESET}", l)
        return l


def _styled_print(*args, **kwargs):
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        _orig_print(*args, **kwargs)
        return
    text = " ".join(str(a) for a in args)
    styled = "\n".join(_color_line(l) for l in text.splitlines())
    _orig_print(styled, **kwargs)


def cmd_help(subgroup=None):
    """Print the nested command reference (derived from COMMANDS.md).

    Works without a vault — pure static text, exits 0.
    Subgroups: None (top-level), "issue", "project", "context", "create", etc.
    """
    print = _styled_print

    if subgroup == "issue":
        print("rvc issue — list, transition, and create issues")
        print()
        print("Usage:")
        print("  rvc issue list [⟨status|bucket⟩] [--dir ⟨bucket⟩]")
        print("  rvc issue ⟨ID⟩ ⟨action⟩ [--skip-ci]")
        print()
        print("Actions (valid set comes from the vault's tree in .rvc-root):")
        print("  triage        move to triage/next bucket")
        print("  start         move to active bucket")
        print("  block         move to blocked/decide bucket")
        print("  defer         move to deferred/parked bucket")
        print("  review        move to review bucket")
        print("  done          move to done bucket")
        print("  evict         move to archive/done")
        print("  supersede     move to archive/superseded")
        print("  create        create a new issue via the tree verb")
        print()
        print("Arguments:")
        print("  list          list issues; optional positional filters by status alias or bucket")
        print("                --dir <bucket>    list a specific configured bucket (e.g. --dir 30_ACTIVE)")
        print("  <ID> <action> transition the issue through the vault's tree (git mv + commit)")
        print("  --skip-ci     disable [skip ci] in commit message (default: enabled)")
        print()
        print("Note: viewing an issue is done with  rvc get <ID>  — the issue command")
        print("  handles listing and transitions only.")
    elif subgroup == "context":
        print("rvc context — assemble an issue's context (target + hard links + soft matches)")
        print()
        print("Usage:")
        print("  rvc context ⟨ID⟩ [--top-k ⟨N⟩] [--budget ⟨CHARS⟩] [--mode summary|full]")
        print("                   [--deep] [--no-semantic] [--reindex]")
        print()
        print("Arguments:")
        print("  <ID>           issue or note id; unpadded resolves too (STORY-32 ≡ STORY-033)")
        print("  --top-k        semantic matches to retrieve (default: 3)")
        print("  --budget       total output character budget (default: 12000); over-budget")
        print("                 output drops the lowest-ranked items first, with a notice")
        print("  --mode         compact summary vs full text (default: summary)")
        print("  --deep         deep/full context mode (alias for --mode full --budget 40000)")
        print("  --no-semantic  resolve only explicit [[wikilinks]] (legacy behavior)")
        print("  --reindex      force a full rebuild of .rvc-context-cache.json")
        print()
        print("Note: the stdlib BM25 ranker indexes all .md files; archive buckets are")
        print("  indexed but never suggested, and the vault's knowledge dir ranks first.")
    elif subgroup == "project":
        print("rvc project — initialize a project with a vault subdirectory")
        print()
        print("Usage:")
        print("  rvc project init [⟨dir⟩] [--vault-name ⟨name⟩] [--tree legacy|newvault]")
        print("  rvc project info [⟨dir⟩]")
        print()
        print("Arguments:")
        print("  init           create a project with a vault subdirectory (not flat)")
        print("    <dir>            target directory (default: current)")
        print("    --vault-name     vault directory name (default: vault)")
        print("    --tree           bucket layout preset: legacy | newvault (default: legacy)")
        print("  info           print vault info and ROADMAP.md contents if present")
        print("    <dir>            project directory (default: current)")
        print()
        print("Note: 'rvc init' creates a flat vault directly; 'rvc project init' wraps it")
        print("  in a <vault-name>/ subdirectory. Use project init for multi-repo projects.")
    elif subgroup == "create":
        print("rvc create — create a new issue")
        print()
        print("Usage:")
        print("  rvc create ⟨title⟩ [--prefix ⟨PREFIX⟩] [--type story|bug|task|epic]")
        print("             [--priority P0|P1|P2|P3|Low|Medium|High|Critical]")
        print("             [--body ⟨text⟩] [--dir ⟨bucket⟩] [--epic ⟨EPIC-XX⟩] [--skip-ci]")
        print()
        print("Arguments:")
        print("  ⟨title⟩      issue title")
        print("  --prefix     ID prefix (default: STORY)")
        print("  --type       issue type (default: story)")
        print("  --priority   priority (default: Medium; newvault trees sort P0-P3)")
        print("  --body       initial issue body text")
        print("  --dir        destination bucket (default: this vault's create/triage bucket)")
        print("  --epic       parent epic name (e.g. EPIC-05)")
        print("  --skip-ci    disable [skip ci] in the commit message (default: enabled)")
    elif subgroup == "get":
        print("rvc get — print the raw issue file")
        print()
        print("Usage:")
        print("  rvc get ⟨ID⟩")
        print()
        print("Arguments:")
        print("  ⟨ID⟩         issue id (e.g. STORY-032); unpadded STORY-32 also resolves")
    elif subgroup == "plate":
        print("rvc plate — render the attention plate")
        print()
        print("Usage:")
        print("  rvc plate [--as ⟨handle⟩] [--format text|json] [--stale-days ⟨N⟩]")
        print()
        print("Arguments:")
        print("  --as         canonicalize this handle for the owed-turn lane (e.g. --as D)")
        print("  --format     output format (default: text)")
        print("  --stale-days overdue threshold in days (default: 7)")
    elif subgroup == "doctor":
        print("rvc doctor — audit the vault against its constitution")
        print()
        print("Usage:")
        print("  rvc doctor [--fix]")
        print()
        print("Arguments:")
        print("  --fix        strip status: and fold priorities in place (block-bucket trees)")
    elif subgroup == "rescan":
        print("rvc rescan — broad vault normalization and cache rebuild")
        print()
        print("Usage:")
        print("  rvc rescan [--dry-run]")
        print()
        print("Arguments:")
        print("  --dry-run    show what would change without writing")
    elif subgroup == "search":
        print("rvc search — case-insensitive grep over every .md file in the vault")
        print()
        print("Usage:")
        print("  rvc search ⟨query⟩")
        print()
        print("Arguments:")
        print("  ⟨query⟩      search text")
    elif subgroup == "git-commit-all":
        print("rvc git-commit-all — commit across dirty submodules and parent repo")
        print()
        print("Usage:")
        print("  rvc git-commit-all ⟨message⟩ [--dry-run] [--no-push] [--push]")
        print()
        print("Arguments:")
        print("  ⟨message⟩    commit message (e.g. 'feat: something (STORY-XX)')")
        print("  --dry-run    show plan without making changes")
        print("  --no-push    commit but do not push")
        print("  --push       commit and push (opt-in)")
    elif subgroup == "init":
        print("rvc init — initialize a new flat vault")
        print()
        print("Usage:")
        print("  rvc init [⟨dir⟩] [--tree legacy|newvault]")
        print()
        print("Arguments:")
        print("  ⟨dir⟩        target directory (default: current)")
        print("  --tree       bucket layout preset (default: legacy)")
    elif subgroup == "install":
        print("rvc install — install rvc on PATH")
        print()
        print("Usage:")
        print("  rvc install [--dir ⟨dir⟩] [--force] [--check]")
        print()
        print("Arguments:")
        print("  --dir        install directory (default: ~/.local/bin)")
        print("  --force      overwrite an unrelated existing file at target")
        print("  --check      verify installation and exit without changes")
    elif subgroup == "list":
        print("rvc list — list issues (alias for 'rvc issue list')")
        print()
        print("Usage:")
        print("  rvc list [⟨status|bucket⟩] [--dir ⟨bucket⟩]")
        print()
        print("Arguments:")
        print("  ⟨status⟩     filter by status alias or bucket (optional)")
        print("  --dir        list a specific configured bucket")
    elif subgroup == "reindex":
        print("rvc reindex — rebuild the semantic context cache")
        print()
        print("Usage:")
        print("  rvc reindex")
        print()
        print("Arguments:")
        print("  (none)       forces full rebuild of .rvc-context-cache.json")
    else:
        print("rvc — folder-as-state issue tracker & context engine")
        print()
        print("Usage:")
        print("  rvc [options] <command> [args...]")
        print()
        print("Options:")
        print("  --path <path>    project or vault path to operate on (default: .)")
        print()
        print("Commands:")
        print()
        print("  init [⟨dir⟩] [--tree legacy|newvault]")
        print("      Initialize a new flat vault (no vault/ subdirectory). Works without a vault.")
        print("      ⟨dir⟩        target directory (default: .)")
        print("      --tree       bucket layout preset (default: legacy)")
        print()
        print("  project")
        print("      Initialize a project with a vault subdirectory; or print vault info.")
        print("      Subcommands: init, info — use 'rvc project help' for details.")
        print()
        print("  install [--dir ⟨dir⟩] [--force] [--check]")
        print("      Install this script as 'rvc' on PATH (symlink). Works without a vault.")
        print("      --dir        install directory (default: ~/.local/bin)")
        print("      --force      overwrite an unrelated existing file at the target")
        print("      --check      verify installation and exit without changes")
        print()
        print("  create ⟨title⟩ [--prefix ⟨PREFIX⟩] [--type story|bug|task|epic]")
        print("             [--priority P0|P1|P2|P3|Low|Medium|High|Critical]")
        print("             [--body ⟨text⟩] [--dir ⟨bucket⟩] [--epic ⟨EPIC-XX⟩] [--skip-ci]")
        print("      Create a new issue: mints the next ID and lands in the create bucket.")
        print("      ⟨title⟩      issue title")
        print("      --prefix     ID prefix (default: STORY)")
        print("      --type       issue type (default: story)")
        print("      --priority   priority (default: Medium; newvault trees sort P0-P3)")
        print("      --body       initial issue body text")
        print("      --dir        destination bucket (default: this vault's create/triage bucket)")
        print("      --epic       parent epic name (e.g. EPIC-05)")
        print("      --skip-ci    disable [skip ci] in the commit message (default: enabled)")
        print()
        print("  issue")
        print("      Subcommands: list; ⟨ID⟩ ⟨action⟩ transitions — use 'rvc issue help'.")
        print("      Viewing an issue is done with 'rvc get ⟨ID⟩'.")
        print()
        print("  get ⟨ID⟩")
        print("      Print the raw issue file for ⟨ID⟩.")
        print("      ⟨ID⟩         issue id (e.g. STORY-032)")
        print()
        print("  context ⟨ID⟩ [--top-k ⟨N⟩] [--budget ⟨CHARS⟩] [--mode summary|full]")
        print("                   [--deep] [--no-semantic] [--reindex]")
        print("      Assemble context: target issue + explicit [[wikilinks]] + Top-K BM25 matches.")
        print("      ⟨ID⟩         issue id (e.g. STORY-032); unpadded STORY-32 also resolves")
        print("      --top-k      semantic matches to retrieve (default: 3)")
        print("      --budget     total output character budget (default: 12000)")
        print("      --mode       compact summary vs full text (default: summary)")
        print("      --deep       deep/full context mode (alias for --mode full --budget 40000)")
        print("      --no-semantic  resolve only explicit [[wikilinks]] (legacy behavior)")
        print("      --reindex    force a full rebuild of .rvc-context-cache.json")
        print()
        print("  list [⟨status⟩] [--dir ⟨bucket⟩]")
        print("      List issues (alias for 'rvc issue list').")
        print("      ⟨status⟩     filter by status alias or bucket (optional)")
        print("      --dir        list a specific configured bucket")
        print()
        print("  search ⟨query⟩")
        print("      Case-insensitive grep over every .md file in the vault.")
        print("      ⟨query⟩      search text")
        print()
        print("  plate [--as ⟨handle⟩] [--format text|json] [--stale-days ⟨N⟩]")
        print("      Render the plate: lanes computed from folders, priorities and open asks.")
        print("      --as         canonicalize this handle for the owed-turn lane")
        print("      --format     output format (default: text)")
        print("      --stale-days overdue threshold in days (default: 7)")
        print()
        print("  doctor [--fix]")
        print("      Audit the vault against its constitution (status:, priority vocabulary).")
        print("      --fix        strip status: and fold priorities in place")
        print("      Note: surgical repair; 'rescan' is the broader rewrite.")
        print()
        print("  rescan [--dry-run]")
        print("      Broad normalization: fix frontmatter, add wikilinks, infer tags,")
        print("      and rebuild .rvc-context-cache.json (the semantic context cache).")
        print("      --dry-run    show changes without writing")
        print("      Note: broader than 'doctor --fix' (constitution repair only).")
        print()
        print("  reindex")
        print("      Force a full rebuild of .rvc-context-cache.json (the semantic context cache).")
        print()
        print("  git-commit-all ⟨message⟩ [--dry-run] [--no-push] [--push]")
        print("      Commit across all dirty submodules plus the parent repo (safe incremental).")
        print("      --dry-run    show the plan without making changes")
        print("      --no-push    commit but do not push")
        print("      --push       commit and push (opt-in)")
        print()
        print("Commands that work without a vault: install, init, project init, help.")
        print()
        print("For command details, use 'rvc <command> help' or 'rvc <command> --help'.")
        print("Full reference: 10_CONTEXT/specs/COMMANDS.md (source of truth).")


# ── Command Handlers ─────────────────────────────────────────────────────────

def _require_vault(path):
    vault_root = find_vault_root(path)
    if not vault_root:
        print("Error: Could not find a 'vault' directory in this path or its parents.")
        sys.exit(1)
    return vault_root


def handle_get(args):
    if args.id in ("help", "--help", "-h"):
        cmd_help("get")
        return
    vault = _require_vault(args.path)
    cmd_get(vault, args.id)


def handle_context(args):
    if args.id in ("help", "--help", "-h"):
        cmd_help("context")
        return
    vault = _require_vault(args.path)
    mode = "full" if getattr(args, "deep", False) else args.mode
    budget = 40000 if getattr(args, "deep", False) and args.budget == CONTEXT_DEFAULT_BUDGET else args.budget
    cmd_context(vault, args.id, top_k=args.top_k, budget=budget,
                mode=mode, no_semantic=args.no_semantic, reindex=args.reindex)


def handle_issue(args):
    if args.action_or_id in ("help", "--help", "-h"):
        cmd_help("issue")
        return
    vault = _require_vault(args.path)
    if args.action_or_id == "list":
        cmd_issue_list(vault, args.action_or_status, list_dir=args.list_dir)
    elif not args.action_or_status:
        cmd_get(vault, args.action_or_id)
    else:
        cmd_issue_action(vault, args.action_or_id, args.action_or_status, skip_ci=args.skip_ci)


def handle_list(args):
    if args.status in ("help", "--help", "-h"):
        cmd_help("list")
        return
    vault = _require_vault(args.path)
    cmd_issue_list(vault, args.status, list_dir=args.list_dir)


def handle_plate(args):
    vault = _require_vault(args.path)
    log_count = 0 if getattr(args, "no_log", False) else getattr(args, "log_count", 5)
    cmd_plate(vault, as_alias=args.as_alias, fmt=args.format, stale_days=args.stale_days, log_count=log_count)


def handle_create(args):
    if args.title in ("help", "--help", "-h"):
        cmd_help("create")
        return
    vault = _require_vault(args.path)
    cmd_create_issue(
        vault,
        title=args.title,
        prefix=args.prefix,
        issue_type=args.issue_type,
        priority=args.priority,
        body=args.body,
        directory=args.directory,
        epic=args.epic,
        skip_ci=args.skip_ci,
    )


def handle_search(args):
    if args.query in ("help", "--help", "-h"):
        cmd_help("search")
        return
    vault = _require_vault(args.path)
    cmd_search(vault, args.query)


def handle_rescan(args):
    vault = _require_vault(args.path)
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    restructure_script = os.path.join(repo_root, "vault-restructure.py")
    cmd = ["python3", restructure_script, vault]
    if getattr(args, "dry_run", False):
        cmd.append("--dry-run")

    rc, out, err = run_cmd(" ".join(cmd))
    print(out)
    if err:
        print(f"[rescan] stderr: {err}", file=sys.stderr)
    if rc == 0 and not getattr(args, "dry_run", False):
        context_cache_update(vault, force=True)
        print(f"[RVC] Context cache rebuilt: {CONTEXT_CACHE_NAME}")


def handle_doctor(args):
    vault = _require_vault(args.path)
    report = cmd_doctor(vault, fix=args.fix)
    for v in report["violations"]:
        print(f"[doctor] VIOLATION: {v}")
    for w in report["warnings"]:
        print(f"[doctor] warning:   {w}")
    for fx in report["fixed"]:
        print(f"[doctor] fixed:     {fx}")
    if report["violations"]:
        print(f"[doctor] {len(report['violations'])} violation(s) found — "
              f"run `rvc doctor --fix` on a block-bucket tree")
        sys.exit(1)
    if report["newvault"]:
        print(f"[doctor] OK — {len(report['fixed'])} fixed, "
              f"{len(report['warnings'])} warning(s), 0 violations")
    else:
        print("[doctor] OK — legacy tree (no block bucket); status/priority conventions untouched")


def handle_git_commit_all(args):
    vault = _require_vault(args.path)
    cmd_git_commit_all(vault, args.message,
                       dry_run=getattr(args, "dry_run", False),
                       no_push=getattr(args, "no_push", False),
                       push=getattr(args, "push", False))


def handle_init(args):
    cmd_init(args.target_path or ".", args.tree)


def handle_project(args):
    if args.action == "help":
        cmd_help("project")
        return
    if args.action == "init":
        cmd_project_init(args.target_path or ".", args.vault_name, args.tree)
        return
    if args.action == "info":
        vault = _require_vault(args.path)
        print("# Vault Info")
        print(f"  Path: {vault}")
        print(f"  Name: {os.path.basename(vault)}")
        tree = resolve_tree(vault)
        roadmap = os.path.join(vault, tree.get("roadmap", "00_Project"), "ROADMAP.md")
        if os.path.exists(roadmap):
            print("\n--- ROADMAP.md ---")
            with open(roadmap, 'r') as f:
                print(f.read())
        else:
            print("  ROADMAP.md: not found")


def handle_reindex(args):
    vault = _require_vault(args.path)
    print(f"[RVC] Rebuilding semantic context cache ({CONTEXT_CACHE_NAME})...")
    cache = context_cache_update(vault, force=True)
    count = len(cache.get("docs", {}))
    print(f"[RVC] Success: Rebuilt cache with {count} documents indexed in {vault}")


def handle_install(args):
    sys.exit(cmd_install(args.dir, force=args.force, check=args.check))


def handle_help_cmd(args):
    cmd_help(args.subgroup)


# ── Parser Definition ────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(description="RVC CLI - Vault Context Interface", add_help=False)
    parser.add_argument("--path", default=".", help="Path to project or vault")
    parser.add_argument("-h", "--help", action="store_true", help="Show help")

    subparsers = parser.add_subparsers(dest="command")

    get_p = subparsers.add_parser("get", add_help=False)
    get_p.add_argument("id")
    get_p.set_defaults(handler=handle_get)

    context_p = subparsers.add_parser("context", add_help=False)
    context_p.add_argument("id")
    context_p.add_argument("--top-k", type=int, default=CONTEXT_DEFAULT_TOP_K,
                           help="Semantic/BM25 matches to retrieve (default: 3)")
    context_p.add_argument("--budget", type=int, default=CONTEXT_DEFAULT_BUDGET,
                           help=f"Total output character budget (default: {CONTEXT_DEFAULT_BUDGET})")
    context_p.add_argument("--mode", choices=("summary", "full"), default="summary",
                           help="compact summary vs full text (default: summary)")
    context_p.add_argument("--deep", action="store_true",
                           help="Deep context mode (alias for --mode full --budget 40000)")
    context_p.add_argument("--no-semantic", action="store_true", dest="no_semantic",
                           help="Resolve only explicit [[wikilinks]] (legacy behavior)")
    context_p.add_argument("--reindex", action="store_true",
                           help="Force a full rebuild of .rvc-context-cache.json")
    context_p.set_defaults(handler=handle_context)

    issue_p = subparsers.add_parser("issue", add_help=False)
    issue_p.add_argument("action_or_id")
    issue_p.add_argument("action_or_status", nargs="?")
    issue_p.add_argument("--dir", dest="list_dir", default=None,
                         help="List a specific configured bucket (e.g. --dir 30_ACTIVE)")
    issue_p.add_argument("--skip-ci", action="store_false", dest="skip_ci", default=True,
                         help="Disable [skip ci] in commit message (default: enabled)")
    issue_p.set_defaults(handler=handle_issue)

    list_p = subparsers.add_parser("list", add_help=False)
    list_p.add_argument("status", nargs="?", default=None)
    list_p.add_argument("--dir", dest="list_dir", default=None,
                        help="List a specific configured bucket (e.g. --dir 20_NEXT)")
    list_p.set_defaults(handler=handle_list)

    plate_p = subparsers.add_parser("plate", add_help=False)
    plate_p.add_argument("--as", dest="as_alias", default=None,
                         help="Canonicalize this handle for the owed-turn lane (e.g. --as D).")
    plate_p.add_argument("--format", choices=("text", "json"), default="text")
    plate_p.add_argument("--stale-days", type=int, default=7,
                         help="Overdue threshold in days without a new section (default: 7)")
    plate_p.add_argument("--log-count", type=int, default=5,
                         help="Number of recent vault commits to show (default: 5, 0 to disable)")
    plate_p.add_argument("--no-log", action="store_true",
                         help="Disable recent activity git log")
    plate_p.set_defaults(handler=handle_plate)

    create_p = subparsers.add_parser("create", add_help=False)
    create_p.add_argument("title", help="Issue title")
    create_p.add_argument("--prefix", default="STORY", help="ID prefix (default: STORY)")
    create_p.add_argument("--type", default="story", dest="issue_type",
                          choices=["story", "bug", "task", "epic"],
                          help="Issue type (default: story)")
    create_p.add_argument(
        "--priority",
        default="Medium",
        choices=["P0", "P1", "P2", "P3", "Low", "Medium", "High", "Critical"],
        help="Priority (default: Medium)",
    )
    create_p.add_argument("--body", default="", help="Initial issue body text")
    create_p.add_argument("--dir", default=None, dest="directory",
                          help="Bucket for the new issue")
    create_p.add_argument("--epic", default="", help="Parent epic name")
    create_p.add_argument("--skip-ci", action="store_false", dest="skip_ci", default=True,
                          help="Disable [skip ci] in commit message (default: enabled)")
    create_p.set_defaults(handler=handle_create)

    search_p = subparsers.add_parser("search", add_help=False)
    search_p.add_argument("query", help="Search query")
    search_p.set_defaults(handler=handle_search)

    commit_p = subparsers.add_parser("git-commit-all", add_help=False)
    commit_p.add_argument("message", help="Commit message")
    commit_p.add_argument("--dry-run", action="store_true", help="Show plan without making changes")
    commit_p.add_argument("--no-push", action="store_true", help="Commit but do not push")
    commit_p.add_argument("--push", action="store_true", help="Commit and push (opt-in)")
    commit_p.set_defaults(handler=handle_git_commit_all)

    rescan_p = subparsers.add_parser("rescan", add_help=False)
    rescan_p.add_argument("--dry-run", action="store_true", help="Show what would change")
    rescan_p.set_defaults(handler=handle_rescan)

    reindex_p = subparsers.add_parser("reindex", add_help=False)
    reindex_p.set_defaults(handler=handle_reindex)

    doctor_p = subparsers.add_parser("doctor", add_help=False)
    doctor_p.add_argument("--fix", action="store_true", help="Strip status: and fold priorities")
    doctor_p.set_defaults(handler=handle_doctor)

    init_p = subparsers.add_parser("init", add_help=False)
    init_p.add_argument("target_path", nargs="?", default=".", help="Directory to initialize")
    init_p.add_argument("--tree", choices=["legacy", "newvault"], default="legacy")
    init_p.set_defaults(handler=handle_init)

    project_p = subparsers.add_parser("project", add_help=False)
    project_p.add_argument("action", choices=["init", "info", "help"])
    project_p.add_argument("target_path", nargs="?")
    project_p.add_argument("--vault-name", default="vault")
    project_p.add_argument("--tree", choices=["legacy", "newvault"], default="legacy")
    project_p.set_defaults(handler=handle_project)

    install_p = subparsers.add_parser("install", add_help=False)
    install_p.add_argument("--dir", default=None)
    install_p.add_argument("--force", action="store_true")
    install_p.add_argument("--check", action="store_true")
    install_p.set_defaults(handler=handle_install)

    help_p = subparsers.add_parser("help", add_help=False)
    help_p.add_argument("subgroup", nargs="?", default=None)
    help_p.set_defaults(handler=handle_help_cmd)

    return parser
