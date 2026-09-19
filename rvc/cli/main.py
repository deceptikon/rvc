"""Main CLI entry point for RVC."""

import sys
from rvc.cli.commands import build_parser, cmd_help


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv == ["-h"] or argv == ["--help"]:
        cmd_help()
        return 0

    # Universal subcommand help interceptor: rvc <cmd> help, rvc <cmd> --help, rvc help <cmd>
    if len(argv) >= 2:
        cmd, sub = argv[0], argv[1]
        if sub in ("help", "--help", "-h") and not cmd.startswith("-"):
            cmd_help(cmd)
            return 0
        if cmd == "help" and not sub.startswith("-"):
            cmd_help(sub)
            return 0

    # Commands requiring arguments: show help if invoked bare instead of error
    if len(argv) == 1 and argv[0] in ("issue", "project", "context", "create", "feedback", "get", "search", "git-commit-all"):
        cmd_help(argv[0])
        return 0

    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "help", False):
        cmd_help(getattr(args, "command", None))
        return 0

    if hasattr(args, "handler"):
        args.handler(args)
    else:
        cmd_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
