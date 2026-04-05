from __future__ import annotations

import argparse

from serialhub.app import SerialHubApp
from serialhub.updater import update_from_git_checkout
from serialhub.web import DEFAULT_WEB_HOST, DEFAULT_WEB_PORT, run_web_app


def parse_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:  # pragma: no cover - argparse formatting path
        raise argparse.ArgumentTypeError("Port must be an integer.") from exc

    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 1 and 65535.")
    return port


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="serialhub", description="SerialHub terminal and protocol tool")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("run", "update"),
        default="run",
        help="Command to run (default: run)",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Serve the Textual app in a local browser instead of the terminal",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_WEB_HOST,
        help=f"Host to bind in web mode (default: {DEFAULT_WEB_HOST})",
    )
    parser.add_argument(
        "--port",
        type=parse_port,
        default=DEFAULT_WEB_PORT,
        help=f"Port to bind in web mode (default: {DEFAULT_WEB_PORT})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "update":
        return update_from_git_checkout()

    if args.web:
        run_web_app(host=args.host, port=args.port)
        return 0

    app = SerialHubApp()
    app.run()
    return 0
