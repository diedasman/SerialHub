from __future__ import annotations

import argparse
import sys

from serialhub.app import SerialHubApp
from serialhub.web import DEFAULT_WEB_HOST, DEFAULT_WEB_PORT, run_web_app
from serialhub.windows_terminal import maybe_relaunch_in_sized_powershell


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
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args[:1] == ["run"]:
        raw_args = raw_args[1:]

    parser = build_parser()
    args = parser.parse_args(raw_args)

    if not args.web and maybe_relaunch_in_sized_powershell(raw_args):
        return 0

    if args.web:
        run_web_app(host=args.host, port=args.port)
        return 0

    app = SerialHubApp()
    app.run()
    return 0
