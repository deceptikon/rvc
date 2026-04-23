#!/usr/bin/env python3
"""rvcd — RVC MCP Global Daemon

A FastMCP server that exposes rvc-cli subcommands as MCP tools.
All tools accept `project_path` and delegate to the CLI via subprocess.

Usage:
    pip install fastmcp
    python rvcd.py              # stdio transport (default for MCP clients)
    python rvcd.py --sse       # SSE transport on default port
    python rvcd.py --sse --port 8080  # SSE on port 8080
"""

import subprocess
import json
import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Resolve the location of the companion rvc-cli.py
# ---------------------------------------------------------------------------
RVC_CLI = str(Path(__file__).resolve().parent / "rvc-cli.py")

if not Path(RVC_CLI).exists():
    raise RuntimeError(f"rvc-cli.py not found at {RVC_CLI}")

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="RVC Protocol Server",
    instructions=(
        "Global MCP daemon for the RVC (Reglament of Vault Context) protocol. "
        "Exposes issue-tracking tools backed by rvc-cli.py. "
        "Pass the absolute project_path to target a specific vault."
    ),
)


# ---------------------------------------------------------------------------
# Helper: run a CLI command and return (stdout, stderr, returncode)
# ---------------------------------------------------------------------------
def _rvc(cmd: list[str], project_path: str = ".") -> tuple[str, str, int]:
    """Execute rvc-cli.py with the given arguments and return output tuple."""
    try:
        result = subprocess.run(
            ["python3", RVC_CLI, "--path", project_path, *cmd],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out after 30s", -1
    except FileNotFoundError:
        return "", f"rvc-cli.py not found at {RVC_CLI}", -1
    except Exception as exc:
        return "", str(exc), -1


def _ok(stdout: str) -> dict:
    """Build a success result dict."""
    return {"success": True, "output": stdout}


def _err(stderr: str, code: int = -1) -> dict:
    """Build an error result dict."""
    return {"success": False, "error": stderr, "exit_code": code}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def rvc_get_issue(project_path: str, issue_id: str) -> dict:
    """Retrieve an issue file from the vault by its ID.

    Args:
        project_path: Absolute path to the project / vault root.
        issue_id: Issue identifier (e.g. 'ISSUE-042' or 'STORY-003').
    """
    stdout, stderr, code = _rvc(["get", issue_id], project_path)
    if code != 0:
        return _err(f"rvc get {issue_id} failed (exit {code}): {stderr}", code)
    return _ok(stdout)


@mcp.tool()
def rvc_get_context(project_path: str, issue_id: str) -> dict:
    """Get the full context for an issue, including all [[linked]] references.

    Args:
        project_path: Absolute path to the project / vault root.
        issue_id: Issue identifier (e.g. 'ISSUE-042' or 'STORY-003').
    """
    stdout, stderr, code = _rvc(["context", issue_id], project_path)
    if code != 0:
        return _err(f"rvc context {issue_id} failed (exit {code}): {stderr}", code)
    return _ok(stdout)


@mcp.tool()
def rvc_issue_start(project_path: str, issue_id: str) -> dict:
    """Transition an issue to 'start' status.

    Args:
        project_path: Absolute path to the project / vault root.
        issue_id: Issue identifier (e.g. 'ISSUE-042').
    """
    stdout, stderr, code = _rvc(["issue", issue_id, "start"], project_path)
    if code != 0:
        return _err(f"rvc issue {issue_id} start failed (exit {code}): {stderr}", code)
    return _ok(stdout)


@mcp.tool()
def rvc_issue_review(project_path: str, issue_id: str) -> dict:
    """Transition an issue to 'review' status.

    Args:
        project_path: Absolute path to the project / vault root.
        issue_id: Issue identifier (e.g. 'ISSUE-042').
    """
    stdout, stderr, code = _rvc(["issue", issue_id, "review"], project_path)
    if code != 0:
        return _err(f"rvc issue {issue_id} review failed (exit {code}): {stderr}", code)
    return _ok(stdout)


@mcp.tool()
def rvc_issue_done(project_path: str, issue_id: str) -> dict:
    """Transition an issue to 'done' status.

    Args:
        project_path: Absolute path to the project / vault root.
        issue_id: Issue identifier (e.g. 'ISSUE-042').
    """
    stdout, stderr, code = _rvc(["issue", issue_id, "done"], project_path)
    if code != 0:
        return _err(f"rvc issue {issue_id} done failed (exit {code}): {stderr}", code)
    return _ok(stdout)


@mcp.tool()
def rvc_issue_list(project_path: str, status: str = "") -> dict:
    """List issues filtered by status (e.g., 'backlog', 'to_do', 'active', 'review', 'done').

    Args:
        project_path: Absolute path to the project / vault root.
        status: Optional status filter. Empty string lists all.
    """
    if status:
        cmd = ["issue", "list", status]
    else:
        cmd = ["issue", "list"]
    stdout, stderr, code = _rvc(cmd, project_path)
    if code != 0:
        return _err(f"rvc issue list '{status}' failed (exit {code}): {stderr}", code)
    return _ok(stdout)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="RVC Global MCP Daemon")
    parser.add_argument(
        "--sse",
        action="store_true",
        help="Run in SSE transport mode (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE transport (default: 8000)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Bind address for SSE transport (default: 0.0.0.0)",
    )
    args = parser.parse_args()

    if args.sse:
        print(f"[rvcd] Starting RVC MCP server on SSE https://{args.host}:{args.port}")
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        print("[rvcd] Starting RVC MCP server on stdio")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
