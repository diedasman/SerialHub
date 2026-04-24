from serialhub.windows_terminal import (
    SIZED_TERMINAL_ENV,
    SKIP_SIZED_TERMINAL_ENV,
    build_sized_powershell_command,
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
