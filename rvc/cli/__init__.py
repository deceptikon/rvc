"""CLI package for RVC."""

from rvc.cli.main import main
from rvc.cli.commands import cmd_help
from rvc.cli.install import cmd_install

__all__ = ["main", "cmd_help", "cmd_install"]
