from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping, Sequence

DEFAULT_TERMINAL_COLUMNS = 132
DEFAULT_TERMINAL_LINES = 42
SIZED_TERMINAL_ENV = "SERIALHUB_SIZED_TERMINAL"
SKIP_SIZED_TERMINAL_ENV = "SERIALHUB_SKIP_SIZED_TERMINAL"
PYINSTALLER_RESET_ENV = "PYINSTALLER_RESET_ENVIRONMENT"


def powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_sized_powershell_command(
    executable: str,
    args: Sequence[str] = (),
    *,
    columns: int = DEFAULT_TERMINAL_COLUMNS,
    lines: int = DEFAULT_TERMINAL_LINES,
) -> list[str]:
    command = " ".join([f"& {powershell_quote(executable)}", *[powershell_quote(arg) for arg in args]])
    resize = f"mode.com con: cols={columns} lines={lines}"
    return [
        "powershell.exe",
        "-NoExit",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        f"{resize}; {command}",
    ]


def should_relaunch_in_sized_powershell(
    *,
    frozen: bool | None = None,
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> bool:
    env = os.environ if environ is None else environ
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    current_platform = sys.platform if platform is None else platform
    return (
        current_platform.startswith("win")
        and is_frozen
        and env.get(SIZED_TERMINAL_ENV) != "1"
        and env.get(SKIP_SIZED_TERMINAL_ENV) != "1"
    )


def maybe_relaunch_in_sized_powershell(argv: Sequence[str] | None = None) -> bool:
    if not should_relaunch_in_sized_powershell():
        return False

    args = list(sys.argv[1:] if argv is None else argv)
    env = os.environ.copy()
    env[SIZED_TERMINAL_ENV] = "1"
    # PyInstaller one-file apps need a reset when they relaunch themselves,
    # otherwise the new process may inherit a temporary extraction directory
    # that is cleaned up when the current process exits.
    env[PYINSTALLER_RESET_ENV] = "1"
    subprocess.Popen(build_sized_powershell_command(sys.executable, args), env=env)  # noqa: S603
    return True
