import pytest

from serialhub import __version__, cli


def test_parser_accepts_web_options() -> None:
    parser = cli.build_parser()
    args_run = parser.parse_args([])
    args_web = parser.parse_args(["--web", "--host", "0.0.0.0", "--port", "9001"])

    assert args_run.web is False
    assert args_run.host == "localhost"
    assert args_run.port == 8000
    assert args_web.web is True
    assert args_web.host == "0.0.0.0"
    assert args_web.port == 9001


def test_parser_reports_version(capsys: pytest.CaptureFixture[str]) -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])

    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"serialhub {__version__}"


def test_main_version_does_not_import_terminal_app(capsys: pytest.CaptureFixture[str]) -> None:
    import sys

    sys.modules.pop("serialhub.app", None)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--version"])

    assert exc_info.value.code == 0
    assert "serialhub.app" not in sys.modules
    assert capsys.readouterr().out.strip() == f"serialhub {__version__}"


def test_main_dispatches_to_terminal_mode(monkeypatch) -> None:
    called: list[str] = []

    monkeypatch.setattr(cli, "run_terminal_app", lambda: called.append("run"))
    monkeypatch.setattr(cli, "run_browser_app", lambda **_: called.append("web"))

    assert cli.main([]) == 0
    assert called == ["run"]


def test_main_accepts_legacy_run_command(monkeypatch) -> None:
    called: list[str] = []

    monkeypatch.setattr(cli, "run_terminal_app", lambda: called.append("run"))
    monkeypatch.setattr(cli, "run_browser_app", lambda **_: called.append("web"))

    assert cli.main(["run"]) == 0
    assert called == ["run"]


def test_main_dispatches_to_web_mode(monkeypatch) -> None:
    called: list[tuple[str, str, int]] = []

    def fake_run_web_app(*, host: str, port: int) -> None:
        called.append(("web", host, port))

    monkeypatch.setattr(cli, "run_terminal_app", lambda: called.append(("terminal", "", 0)))
    monkeypatch.setattr(cli, "run_browser_app", fake_run_web_app)

    assert cli.main(["--web", "--host", "0.0.0.0", "--port", "9001"]) == 0
    assert called == [("web", "0.0.0.0", 9001)]
