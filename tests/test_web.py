import os
import sys
import types

from serialhub import web
from serialhub.windows_terminal import SKIP_SIZED_TERMINAL_ENV


def test_build_browser_url_uses_loopback_for_wildcard_host() -> None:
    assert web.build_browser_url("0.0.0.0", 8000) == "http://127.0.0.1:8000/"


def test_build_web_command_uses_module_entrypoint(monkeypatch) -> None:
    monkeypatch.setattr(sys, "executable", r"C:\Program Files\Python312\python.exe")
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert web.build_web_command() == r'"C:\Program Files\Python312\python.exe" -m serialhub'


def test_build_web_command_uses_frozen_executable(monkeypatch) -> None:
    monkeypatch.setattr(sys, "executable", r"C:\Program Files\SerialHub\SerialHub.exe")
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    assert web.build_web_command() == r'"C:\Program Files\SerialHub\SerialHub.exe"'


def test_run_web_app_serves_textual_app(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeServer:
        def __init__(self, command: str, host: str, port: int, title: str) -> None:
            captured["command"] = command
            captured["host"] = host
            captured["port"] = port
            captured["title"] = title

        def serve(self) -> None:
            captured["skip_sized_terminal"] = os.environ.get(SKIP_SIZED_TERMINAL_ENV)
            captured["served"] = True

    monkeypatch.setitem(sys.modules, "textual_serve.server", types.SimpleNamespace(Server=FakeServer))
    monkeypatch.delenv(SKIP_SIZED_TERMINAL_ENV, raising=False)
    monkeypatch.setattr(web, "build_web_command", lambda: "python -m serialhub")

    web.run_web_app(host="localhost", port=8000, open_browser=False)

    assert captured == {
        "command": "python -m serialhub",
        "host": "localhost",
        "port": 8000,
        "title": "SerialHub",
        "skip_sized_terminal": "1",
        "served": True,
    }
    assert SKIP_SIZED_TERMINAL_ENV not in os.environ
