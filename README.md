# SerialHub

SerialHub is a cross-platform serial tool with two local launch modes: the native Textual terminal UI and the same Textual app served in a browser from your machine. It is focused on practical multi-device serial workflows, local user profiles, persistent per-device workspaces, automation scripts, and per-device logging while keeping the DLMS integration in the codebase for upcoming UI work.

```
                                                                                                    
 ::::::::  :::::::::: :::::::::  :::::::::::     :::     :::        :::    ::: :::    ::: :::::::::  
:+:    :+: :+:        :+:    :+:     :+:       :+: :+:   :+:        :+:    :+: :+:    :+: :+:    :+: 
+:+        +:+        +:+    +:+     +:+      +:+   +:+  +:+        +:+    +:+ +:+    +:+ +:+    +:+ 
+#++:++#++ +#++:++#   +#++:++#:      +#+     +#++:++#++: +#+        +#++:++#++ +#+    +:+ +#++:++#+  
       +#+ +#+        +#+    +#+     +#+     +#+     +#+ +#+        +#+    +#+ +#+    +#+ +#+    +#+ 
#+#    #+# #+#        #+#    #+#     #+#     #+#     #+# #+#        #+#    #+# #+#    #+# #+#    #+# 
 ########  ########## ###    ### ########### ###     ### ########## ###    ###  ########  #########  
 
```

Right now the app is focused on a raw serial workflow:

- Detect USB/serial devices and connect with configurable serial settings
- Sign in with a local SerialHub user profile and optional remember-me startup
- Create a dedicated workspace tab for each connected serial device
- Preserve disconnected device tabs and captured stream history until the user closes them
- Open a dedicated script editor screen without losing the main workspace state
- Trigger user-defined command buttons from per-user JSON config files
- Log sessions per device with timestamp and data stream

## Tamble of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [How To Run](#how-to-run)
- [Updating SerialHub](#updating-serialhub)
- [First-Time Setup In The App](#first-time-setup-in-the-app)
- [Using The Main Workflow](#using-the-main-workflow)
- [Generated Output Structure](#generated-output-structure)
- [User Data and Loggin](#user-data-and-logging)
- [Development Commands](#development-commands)
- [Repository Standards](#repository-standards)

## Features

- Dual launch modes:
  - Textual terminal UI via `serialhub`
  - The same Textual app in a browser via `serialhub --web`
- Cross-platform serial tooling (Windows + Linux)
- Username-based login screen with `Remember Me` and `New User`
- Local per-user storage under the SerialHub application-data directory
- Multi-device management with independent sessions
- Manual refresh and auto-discovery of available serial ports
- Connection panel tabs for `Serial` and `TCP/IP`
- Device selection via dynamic dropdown list
- Serial configuration control:
  - Baud rate
  - Parity
  - Stop bits
  - Data bits
- Real-time send/receive terminal flow
- Hex TX mode via checkbox toggle
- Dynamic workspace tabs with one raw stream view per device
- Workspace tabs stay available after disconnect until manually closed
- Closing a live workspace tab also disconnects the device
- DLMS parsing backend remains installed through `gurux_dlms` for future UI work
- Textual browser mode via `textual-serve` with automatic browser launch
- Dedicated script editor screen with:
  - `on_message`
  - `on_pattern`
  - `send`, `sleep`, `wait_for`, `log`
- Per-device start/stop logging to `.txt`
- Log destination input accepts either:
  - an existing folder path, which generates `<device-id>-YYYYMMDD-HHMMSS.txt`
  - an explicit `.txt` path, which is used as-is
- Optional auto-logging on connect (checkbox toggle)
- Right-side `Functions` panel with:
  - command-config dropdown sourced from the active user's `COMMAND_CONFIGS`
  - dynamically generated buttons from nested `COMMANDS` JSON objects
- Timestamp display toggle via checkbox
- Keyboard shortcuts for message focus, connect/disconnect, logging toggle, script editor, and theme toggle
- Built-in dark and light themes

## Requirements

- Python `3.12` or newer
- `pip`
- A terminal that can run Textual apps for CLI mode
- A modern web browser for browser mode
- Serial permissions/access on your OS
- `gurux_dlms` (installed automatically via project dependencies)

## Installation

### 1. Clone the repository

```powershell
git clone https://github.com/diedasman/SerialHub.git
```
```powershell
cd SerialHub
```

Important: every install command below assumes your terminal is inside the project root, the folder that contains `pyproject.toml`.

### 2. Create a virtual environment

#### Windows PowerShell:

```powershell
python -m venv .venv
```
```powershell
.venv\Scripts\Activate.ps1
```

#### Windows Command Prompt:

```bat
python -m venv .venv
```
```bat
.venv\Scripts\activate.bat
```

#### Linux:

```bash
python3 -m venv .venv
```
```bash
source .venv/bin/activate
```

### 3. Install the project

```powershell
python -m pip install --upgrade pip
```
```powershell
python -m pip install -e .
```

This installs the `serialhub` command from the local source tree in editable mode.

#### 4. Summary (Powershell)

```bash
git clone https://github.com/diedasman/SerialHub.git
cd SerialHub
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
serialhub
```

Browser mode is available immediately after install:

```powershell
serialhub --web
```

## VS Code Setup

If you are opening the project in VS Code, select the virtual environment interpreter after installation:

1. Open the command palette.
2. Run `Python: Select Interpreter`.
3. Choose `.venv\Scripts\python.exe` on Windows or `.venv/bin/python` on Linux.

This helps VS Code resolve imports from Textual, pyserial, and the local `src` package.

## How To Run

### CLI mode

From anywhere after installation:

```powershell
serialhub
```

Alternative:

```powershell
python -m serialhub
```

### Web mode

Serve the Textual app in your browser:

```powershell
serialhub --web
```

Alternative:

```powershell
python -m serialhub --web
```

Browser mode serves the Textual app itself on `http://localhost:8000` by default and opens your browser automatically.

To bind a different interface or port:

```powershell
serialhub --web --host 0.0.0.0 --port 8000
```

By default SerialHub stores local app data in a per-user application data folder:

- Windows: `%LOCALAPPDATA%\SerialHub`
- Linux: `$XDG_DATA_HOME/SerialHub` or `~/.local/share/SerialHub`

You can override the storage location by setting `SERIALHUB_DATA_DIR` before launch.

## Updating SerialHub

If SerialHub was installed from a git checkout as documented above, update with:

```powershell
serialhub update
```

The update command:

- verifies SerialHub is backed by a git checkout
- stops if there are local uncommitted changes
- runs `git pull --ff-only`
- refreshes the editable install

If SerialHub was not installed from a git checkout, re-clone and reinstall with:

```powershell
python -m pip install -e .
```

## First-Time Setup In The App

When the app opens:

1. Enter a username on the login screen.
2. Optional: enable `Remember Me` to sign back into that local profile automatically next time.
3. Use `New User` once to generate the local user folder and starter JSON files if the profile does not exist yet.
4. Click `Refresh` to load serial ports.
5. Select a port from the `Serial` tab in the `Connection` panel.
6. Set your connection parameters in the `Connection` panel.
7. Press `Connect`.
8. Optional: paste an existing log folder path or a full `.txt` log path into `Log filepath`, then enable auto-logging if needed.
9. Optional: pick a command config in the `Functions` panel to load user-defined message buttons.
10. Start sending or receiving data.
11. Close a workspace tab when you want to remove its saved session history.

Browser mode exposes the same Textual workflow through the browser by serving `SerialHubApp` itself, rather than maintaining a separate HTML frontend.

## Using The Main Workflow

1. Pick a serial device from the `Serial` connection tab and connect it.
2. Work in the device's raw-stream workspace tab.
3. Use the TX input field to send text payloads.
4. Enable `HEX TX` when sending raw hex payloads.
5. Toggle `Timestamps` when needed.
6. Paste a log folder or full `.txt` file path into `Log filepath` when you want logs written outside the app data folder.
7. Use `Start Logging` / `Stop Logging` for the active workspace.
8. Pick a command config from the `Functions` panel and press a generated button to send its payload to the active device.
9. Open `Script Editor` when you want to automate the active device.

### CLI Keyboard Shortcuts

- `M`: focus the TX message input field
- `D`: connect/disconnect the currently selected device
- `L`: start/stop logging for the active device session
- `Ctrl+E`: open or close the script editor screen
- `Ctrl+T`: toggle between dark and light themes

### Scripting

- Open the dedicated script editor screen to automate traffic without losing the main workspace.
- Click `Run Script` to start and `Stop Script` to stop for the active device.
- Click `Close`, press `Esc`, or press `Ctrl+E` to leave the editor and return to the main screen.
- Supported helper functions in script scope:
  - `send(...)`
  - `sleep(...)`
  - `wait_for(...)`
  - `log(...)`
  - `on_message`
  - `on_pattern`
  - `stop_requested()`

## Generated Output Structure

SerialHub now keeps runtime user files under the local application-data directory. For a user `alice`, the generated structure looks like:

```text
<SerialHub data dir>/
  users/
    alice/
      alice.json
      alice_cmds.json
      blank.json
      logs/
        COM3-20260418-210000.txt
      message_history.txt
```

Notes:

- If `Log filepath` points to an existing folder, SerialHub generates the filename automatically.
- If `Log filepath` points to a `.txt` file, SerialHub writes to that exact file.

## User Data And Logging

SerialHub stores local metadata and user content in its data directory:

- `users/<username>/<username>.json`
  - the active user's profile metadata (`THEME`, `LOG_FOLDER`, `COMMAND_CONFIGS`)
- `users/<username>/*.json`
  - command config files referenced by `COMMAND_CONFIGS`
- `users/<username>/logs/*.txt`
  - fallback per-device communication logs when no external log folder is supplied
- `users/<username>/message_history.txt`
  - sent-message history for that user

The `LOG_FOLDER` value is mirrored in the `Log filepath` field and may be either a directory path or an explicit `.txt` path.

Example override:

```powershell
$env:SERIALHUB_DATA_DIR = "D:\SerialHubData"
serialhub
```

## Development Commands

Run tests:

```powershell
python -m pytest
```

Run lint checks:

```powershell
python -m ruff check src tests
```

Quick syntax/compile check:

```powershell
python -m compileall src tests
```

## Repository Standards

- License: `GPLv3` ([LICENSE](LICENSE))
- Contribution guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- CI: GitHub Actions workflow at `.github/workflows/ci.yml`

---
