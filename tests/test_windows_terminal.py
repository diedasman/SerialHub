from serialhub.windows_terminal import (
    DEFAULT_TERMINAL_COLUMNS,
    DEFAULT_TERMINAL_LINES,
    PYINSTALLER_RESET_ENV,
    SIZED_TERMINAL_ENV,
    SKIP_SIZED_TERMINAL_ENV,
    TERMINAL_COLUMNS_ENV,
    TERMINAL_LINES_ENV,
    build_sized_powershell_command,
    maybe_relaunch_in_sized_powershell,
    resolve_sized_terminal_geometry,
    should_relaunch_in_sized_powershell,
)


def test_build_sized_powershell_command_sets_window_size_and_runs_executable() -> None:
    command = build_sized_powershell_command(
        r"C:\Program Files\SerialHub\serialhub.exe",
        ["run", "--flag's"],
        columns=120,
        lines=36,
    )

    assert command[:4] == ["powershell.exe", "-NoExit", "-ExecutionPolicy", "Bypass"]
    assert "mode.com con: cols=120 lines=36" in command[-1]
    assert "& 'C:\\Program Files\\SerialHub\\serialhub.exe' 'run' '--flag''s'" in command[-1]


def test_should_relaunch_only_for_unsized_windows_frozen_app() -> None:
    assert should_relaunch_in_sized_powershell(
        frozen=True,
        platform="win32",
        environ={},
    )
    assert not should_relaunch_in_sized_powershell(
        frozen=True,
        platform="linux",
        environ={},
    )
    assert not should_relaunch_in_sized_powershell(
        frozen=False,
        platform="win32",
        environ={},
    )
    assert not should_relaunch_in_sized_powershell(
        frozen=True,
        platform="win32",
        environ={SIZED_TERMINAL_ENV: "1"},
    )
    assert not should_relaunch_in_sized_powershell(
        frozen=True,
        platform="win32",
        environ={SKIP_SIZED_TERMINAL_ENV: "1"},
    )


def test_resolve_sized_terminal_geometry_reads_env_and_clamps_small_values() -> None:
    assert resolve_sized_terminal_geometry(
        {
            TERMINAL_COLUMNS_ENV: "110",
            TERMINAL_LINES_ENV: "32",
        }
    ) == (110, 32)

    assert resolve_sized_terminal_geometry(
        {
            TERMINAL_COLUMNS_ENV: "bad",
            TERMINAL_LINES_ENV: "12",
        }
    ) == (DEFAULT_TERMINAL_COLUMNS, 24)


def test_maybe_relaunch_sets_pyinstaller_reset_environment(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "serialhub.windows_terminal.should_relaunch_in_sized_powershell",
        lambda: True,
    )
    monkeypatch.setattr(
        "serialhub.windows_terminal.build_sized_powershell_command",
        lambda executable, args, *, columns, lines: ["powershell.exe", executable, str(columns), str(lines), *args],
    )
    monkeypatch.setattr(
        "serialhub.windows_terminal.sys.executable",
        r"C:\Program Files\SerialHub\SerialHub.exe",
    )
    monkeypatch.setattr(
        "serialhub.windows_terminal.sys.argv",
        [r"C:\Program Files\SerialHub\SerialHub.exe", "--demo"],
    )
    monkeypatch.setenv(TERMINAL_COLUMNS_ENV, "110")
    monkeypatch.setenv(TERMINAL_LINES_ENV, "32")

    def fake_popen(command: list[str], env: dict[str, str]) -> None:
        captured["command"] = command
        captured["env"] = env

    monkeypatch.setattr("serialhub.windows_terminal.subprocess.Popen", fake_popen)

    assert maybe_relaunch_in_sized_powershell() is True
    assert captured["command"] == [
        "powershell.exe",
        r"C:\Program Files\SerialHub\SerialHub.exe",
        "110",
        "32",
        "--demo",
    ]
    assert captured["env"][SIZED_TERMINAL_ENV] == "1"
    assert captured["env"][PYINSTALLER_RESET_ENV] == "1"
