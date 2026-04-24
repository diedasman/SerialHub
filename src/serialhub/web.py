from __future__ import annotations

import os
import subprocess
import sys
import threading
import webbrowser

from serialhub.windows_terminal import SKIP_SIZED_TERMINAL_ENV

DEFAULT_WEB_HOST = "localhost"
DEFAULT_WEB_PORT = 8000


def build_web_command() -> str:
    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([sys.executable])
    return subprocess.list2cmdline([sys.executable, "-m", "serialhub"])


def build_browser_url(host: str, port: int) -> str:
    browse_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    return f"http://{browse_host}:{port}/"


def run_web_app(
    host: str = DEFAULT_WEB_HOST,
    port: int = DEFAULT_WEB_PORT,
    *,
    open_browser: bool = True,
) -> None:
    try:
        from textual_serve.server import Server  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on installed extras
        raise RuntimeError(
            "Browser mode requires `textual-serve`. Reinstall SerialHub dependencies and try again."
        ) from exc

    command = build_web_command()
    launch_url = build_browser_url(host, port)

    print(f"SerialHub Web serving the Textual app on http://{host}:{port}/")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(launch_url)).start()
        print(f"Opening {launch_url}")

    previous_skip_value = os.environ.get(SKIP_SIZED_TERMINAL_ENV)
    os.environ[SKIP_SIZED_TERMINAL_ENV] = "1"
    try:
        Server(command=command, host=host, port=port, title="SerialHub").serve()
    finally:
        if previous_skip_value is None:
            os.environ.pop(SKIP_SIZED_TERMINAL_ENV, None)
        else:
            os.environ[SKIP_SIZED_TERMINAL_ENV] = previous_skip_value
