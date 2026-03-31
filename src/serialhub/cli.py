from __future__ import annotations

import argparse

from serialhub.app import SerialHubApp
from serialhub.updater import update_from_git_checkout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="serialhub", description="SerialHub terminal and protocol tool")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("run", help="Start the SerialHub application")
    subparsers.add_parser("update", help="Update SerialHub from the git checkout")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in (None, "run"):
        app = SerialHubApp()
        app.run()
        return 0

    if args.command == "update":
        return update_from_git_checkout()

    parser.print_help()
    return 1
