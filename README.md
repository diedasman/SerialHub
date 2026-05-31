# SerialHub

SerialHub is a cross-platform serial and TCP terminal built with Textual. It runs either as a native terminal app or as the same Textual UI served locally in a browser, with local user profiles, persistent device workspaces, command-config buttons, and per-device session logging.

![SerialHub terminal mode screenshot](src/serialhub/assets/home.png)

## Features

- Serial and TCP/IP connection workflows in one app
- Native terminal mode and browser-served Textual mode
- Local username-based profiles with optional remember-me startup
- Persistent per-device workspace tabs and stream history
- Per-user command-config JSON files and a built-in config editor
- Per-device logging with automatic filename generation
- Theme toggle plus keyboard shortcuts for common actions

---

## Requirements

- Python `3.12` or newer for development or source-based runs
- A terminal that can run Textual apps for terminal mode
- A modern browser for browser mode
- Serial permissions or device access on your OS

## Releases

Windows executable builds are produced locally. Cloud CI does not build release binaries for this repo.

- Build on Windows with `scripts\build_release.ps1`. The output is a single `.exe` named `SerialHub-v#`, where `#` is the release version.
- On Linux, build the same Windows `.exe` with Docker using `./scripts/build_release_docker.sh 2.0`.
- By default, the script uses the package version. Pass `-Version 2.0` to build a specific release version.
- Use `-InstallDependencies` when the local environment still needs PyInstaller installed.
- Commit the release executable as `dist/SerialHub-v*.exe` before pushing a `v*` tag.
- Tags matching `v*` publish the committed local executable to GitHub Releases when the file is present.
- To brand the Windows executable, place a Windows `.ico` file at `src/serialhub/assets/app.ico`; the local PyInstaller step will use it automatically when present.

End users on Windows can download `SerialHub-v*.exe` from the GitHub release assets or from the repository `dist/` folder, then run the executable directly. No Python installation or source checkout is required for normal end-user use.

For now, Linux usage is source-based rather than distributed as a packaged executable.

## Development Setup

Use a local virtual environment for development and testing.

Windows PowerShell shortcut from the project root:

```powershell
. .\scripts\dev_setup.ps1
```

Manual setup:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

Linux manual setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

If you use VS Code, point it at the virtual-environment interpreter so imports resolve correctly.

## Running From Source

Terminal mode:

```powershell
python -m serialhub
```

Browser mode:

```powershell
python -m serialhub --web
```

To bind a different browser host or port:

```powershell
python -m serialhub --web --host 0.0.0.0 --port 8000
```

By default SerialHub stores local app data in a per-user application-data folder:

- Windows: `%LOCALAPPDATA%\SerialHub`
- Linux: `$XDG_DATA_HOME/SerialHub` or `~/.local/share/SerialHub`

Override the storage location with `SERIALHUB_DATA_DIR` if needed.

## First-Time App Setup

1. Enter a username on the login screen.
2. Optional: enable `Remember Me` to sign back into that local profile automatically next time.
3. Use `New User` once to create the local profile and starter command files.
4. Refresh ports, choose a `Serial` or `TCP/IP` connection, and connect.
5. Optional: set a log folder or explicit `.txt` log path.
6. Optional: choose a command config in the `Functions` panel.
7. Start sending and receiving data in the workspace tab for that device.

Browser mode serves the same Textual app locally; it is not a separate frontend.

## Main Workflow

1. Select a serial device or TCP target and connect.
2. Work in that device's raw-stream workspace tab.
3. Use the TX input to send payloads, or enable `HEX TX` for hex data.
4. Toggle timestamps and logging as needed.
5. Use the `Functions` panel to send configured commands.
6. Open `CONFIG EDITOR` to edit or preview command-config JSON files.

Keyboard shortcuts:

- `M`: focus the TX message input
- `D`: connect or disconnect the selected device
- `L`: start or stop logging for the active session
- `Ctrl+Q`: log out
- `Ctrl+T`: toggle theme

## User Data And Logging

Runtime user data lives under the SerialHub data directory. For a user named `alice`, the layout looks like this:

```text
<SerialHub data dir>/
  users/
    alice/
      alice.json
      configs/
        alice_cmds.json
        blank.json
      logs/
        COM3-20260418-210000.txt
      message_history.txt
```

Important behaviors:

- If `Log filepath` points to an existing folder, SerialHub generates the filename automatically.
- If `Log filepath` points to a `.txt` file, SerialHub writes to that exact file.
- `LOG_FOLDER` in the user profile is mirrored into the app's `Log filepath` input.

Example override:

```powershell
$env:SERIALHUB_DATA_DIR = "D:\SerialHubData"
python -m serialhub
```

## Development Commands

```powershell
python -m pytest
python -m ruff check src tests
python -m compileall src tests
.\scripts\build_release.ps1 -Version 2.0 -InstallDependencies
./scripts/build_release_docker.sh 2.0
```

## Repository Layout

- `src/serialhub/`: application source
- `tests/`: automated tests
- `tools/`: optional development and manual-testing helpers
- `scripts/dev_setup.ps1`: Windows development bootstrap helper

## Repository Standards

- License: `GPLv3` ([LICENSE](LICENSE))
- Contribution guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- CI and release upload automation: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)
