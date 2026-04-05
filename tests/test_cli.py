from serialhub import cli


def test_parser_accepts_commands() -> None:
    parser = cli.build_parser()
    args_run = parser.parse_args(["run"])
    args_update = parser.parse_args(["update"])
    args_web = parser.parse_args(["--web", "--host", "0.0.0.0", "--port", "9001"])

    assert args_run.command == "run"
    assert args_update.command == "update"
    assert args_web.command == "run"
    assert args_web.web is True
    assert args_web.host == "0.0.0.0"
    assert args_web.port == 9001


def test_main_dispatches_to_terminal_mode(monkeypatch) -> None:
    called: list[str] = []

    class DummyApp:
        def run(self) -> None:
            called.append("run")

    monkeypatch.setattr(cli, "SerialHubApp", DummyApp)
    monkeypatch.setattr(cli, "run_web_app", lambda **_: called.append("web"))

    assert cli.main([]) == 0
    assert called == ["run"]


def test_main_dispatches_to_web_mode(monkeypatch) -> None:
    called: list[tuple[str, str, int]] = []

    class DummyApp:
        def run(self) -> None:
            called.append(("terminal", "", 0))

    def fake_run_web_app(*, host: str, port: int) -> None:
        called.append(("web", host, port))

    monkeypatch.setattr(cli, "SerialHubApp", DummyApp)
    monkeypatch.setattr(cli, "run_web_app", fake_run_web_app)

    assert cli.main(["--web", "--host", "0.0.0.0", "--port", "9001"]) == 0
    assert called == [("web", "0.0.0.0", 9001)]
