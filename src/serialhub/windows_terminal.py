from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping, Sequence

DEFAULT_TERMINAL_COLUMNS = 120
DEFAULT_TERMINAL_LINES = 36
MIN_TERMINAL_COLUMNS = 80
MIN_TERMINAL_LINES = 24
SIZED_TERMINAL_ENV = "SERIALHUB_SIZED_TERMINAL"
SKIP_SIZED_TERMINAL_ENV = "SERIALHUB_SKIP_SIZED_TERMINAL"
PYINSTALLER_RESET_ENV = "PYINSTALLER_RESET_ENVIRONMENT"
TERMINAL_COLUMNS_ENV = "SERIALHUB_TERMINAL_COLUMNS"
TERMINAL_LINES_ENV = "SERIALHUB_TERMINAL_LINES"


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


def _resolve_terminal_dimension(
    env_name: str,
    *,
    default: int,
    minimum: int,
    environ: Mapping[str, str] | None = None,
) -> int:
    env = os.environ if environ is None else environ
    raw_value = env.get(env_name, "").strip()
    if not raw_value:
        return default

    try:
        parsed = int(raw_value)
    except ValueError:
        return default

    return max(parsed, minimum)


def resolve_sized_terminal_geometry(
    environ: Mapping[str, str] | None = None,
) -> tuple[int, int]:
    return (
        _resolve_terminal_dimension(
            TERMINAL_COLUMNS_ENV,
            default=DEFAULT_TERMINAL_COLUMNS,
            minimum=MIN_TERMINAL_COLUMNS,
            environ=environ,
        ),
        _resolve_terminal_dimension(
            TERMINAL_LINES_ENV,
            default=DEFAULT_TERMINAL_LINES,
            minimum=MIN_TERMINAL_LINES,
            environ=environ,
        ),
    )


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
    columns, lines = resolve_sized_terminal_geometry(env)
    env[SIZED_TERMINAL_ENV] = "1"
    # PyInstaller one-file apps need a reset when they relaunch themselves,
    # otherwise the new process may inherit a temporary extraction directory
    # that is cleaned up when the current process exits.
    env[PYINSTALLER_RESET_ENV] = "1"
    subprocess.Popen(
        build_sized_powershell_command(sys.executable, args, columns=columns, lines=lines),
        env=env,
    )  # noqa: S603
    return True
