import sys
import types

from serialhub import web


def test_build_browser_url_uses_loopback_for_wildcard_host() -> None:
    assert web.build_browser_url("0.0.0.0", 8000) == "http://127.0.0.1:8000/"


def test_build_web_command_uses_module_entrypoint(monkeypatch) -> None:
    monkeypatch.setattr(sys, "executable", r"C:\Program Files\Python312\python.exe")

    assert web.build_web_command() == r'"C:\Program Files\Python312\python.exe" -m serialhub run'


def test_run_web_app_serves_textual_app(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeServer:
        def __init__(self, command: str, host: str, port: int, title: str) -> None:
            captured["command"] = command
            captured["host"] = host
            captured["port"] = port
            captured["title"] = title

        def serve(self) -> None:
            captured["served"] = True

    monkeypatch.setitem(sys.modules, "textual_serve.server", types.SimpleNamespace(Server=FakeServer))
    monkeypatch.setattr(web, "build_web_command", lambda: "python -m serialhub run")

    web.run_web_app(host="localhost", port=8000, open_browser=False)

    assert captured == {
        "command": "python -m serialhub run",
        "host": "localhost",
        "port": 8000,
        "title": "SerialHub",
        "served": True,
    }
