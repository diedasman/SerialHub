# Changelog

All notable changes to this project will be documented in this file.

---

## [2.0] - 2026-05-31

### Added

- Added user macros with a Macros tab, run/edit actions, per-command delays, and editable macro JSON files.
- Added generated macro command labels in the Command Builder so macro steps are indexed by row order.
- Added local Windows executable release publishing from committed `dist/SerialHub-v*.exe` assets.

### Changed

- Updated the Command Builder layout with clearer row borders and improved Add Command focus behavior.
- Updated macro command summaries and Macros tab styling for easier command scanning.
- Switched release automation to publish locally built executables on pushed `v*` tags.

### Fixed

- Stabilized config-editor file focus when opening macro files from the Macros tab.
- Added regression coverage for macro loading, editing, execution, command color handling, and Command Builder focus.

---

## [1.9.2] - 2026-05-31

### Changed

- Updated macro command summaries to render each command string on its own line for easier scanning.
- Tightened Macros tab spacing and added secondary borders around macro rows.
- Renamed the Off White command-button color option to White while keeping the same off-white styling.

---

## [1.9.1] - 2026-05-31

### Added

- Added user macros with a Macros tab, run/edit actions, per-command delays, and editable macro JSON files.
- Added generated macro command labels in the Command Builder so macro steps are indexed by row order.
- Added an Off White command-button color option.
- Added local Windows release build documentation and a local PyInstaller release script.

### Changed

- Updated the Command Builder layout with clearer row borders and improved Add Command focus behavior.
- Updated the Macros tab to show each macro's command strings in the secondary theme color.
- Changed release automation so GitHub Actions no longer builds the Windows executable in the cloud; tagged releases publish a locally built `dist/SerialHub-v*.exe` when committed.

### Fixed

- Added regression coverage for macro loading, macro editing, macro execution, command color handling, and Command Builder focus.

---

## [Unreleased] - 2026-04-25

### Changed

- Removed the packaged Windows PowerShell relaunch path so the executable starts directly in the original console session.
- Added a conditional Windows build icon hook that uses `src/serialhub/assets/app.ico` when the file is present.

### Fixed

- Removed the extra packaged-app startup hop that could delay the full UI becoming visible after the console window opened.

---

## [Unreleased] - 2026-04-24

### Added

- Added the active username to the `User Settings` screen in a bordered summary row.
- Added a `Copy Workspace` action that copies the active workspace stream to Textual's clipboard.

### Changed

- Reworked `User Settings` labels into horizontal label/control rows.
- Smoothed workspace activity sparklines by decaying samples toward idle between events.
- Updated sparkline idle coloring so old TX/RX samples do not keep the baseline painted as active.

### Fixed

- Fixed TX sparkline coloring by using positive magnitudes for TX-only activity and signed values only when RX and TX are both active.

---

## [Unreleased] - 2026-04-23

### Added

- Added a confirmation modal for deleting the focused command-config file from the `Config Editor`.
- Added per-user TCP favorites storage plus regression coverage for saving favorite IP/port pairs from the `TCP/IP` panel.
- Added a saved-connections `Select` under the `Add to Favorites` button so users can browse and reuse stored TCP endpoints.

### Changed

- The workspace toolbar now uses an `ACTIVITY` border title for the sparkline widget instead of the old inline `LINE ACTIVITY` label.
- RX and TX toolbar labels now change color dynamically based on recent activity in the active workspace.
- The functions-panel command-config selector now stays blank until the user explicitly chooses a config instead of auto-loading the first available file.

### Fixed

- Fixed the main `Disconnect` action so it disconnects the active workspace device instead of using the left-panel connection details as the target.
- Added regression coverage for active-workspace disconnect behavior, config-file deletion, and the updated toolbar activity states.
- Restored the RX/TX toolbar labels so they remain visible with the new 5-row toolbar height and the added connection-status rule widget.

## [Unreleased] - 2026-04-22

### Added

- Added compact glyph-based LED indicators for connection, RX, and TX activity in the workspace toolbar.
- Added a combined live RX/TX sparkline to the workspace toolbar, backed by a session datastream model that the UI can query directly.
- Added regression coverage for the moved workspace status block and the refined toolbar connection/activity widgets.

### Changed

- Moved the workspace status container to the bottom of the center panel while keeping it inside the panel border and full-width with the workspace content.
- Reworked the workspace toolbar layout so the `CONNECTION` label follows the LED state color, the LED glyphs keep their natural width, and `Clear`/`Close` use compact side-by-side buttons sized to fit inside the toolbar action widget.

## [Unreleased] - 2026-04-21

### Added

- Added a packaged ASCII logo asset under `src/serialhub/assets/logo.txt`.
- Added regression coverage for packaged logo loading and workspace placeholder content.
- Added a `scripts/dev_setup.ps1` helper for returning to an editable Windows development environment quickly.
- Added a user-scoped `Config Editor` screen for browsing and editing command JSON files from `users/<username>/configs/`.
- Added a form-based command builder in the `Config Editor` for creating and editing command buttons without hand-editing JSON.
- Added regression coverage for config-editor loading/saving, workspace console clearing, and the updated user-summary placement.

### Changed

- Switched the end-user installation flow and helper scripts to a `pipx`-first setup so `serialhub` is available on the terminal `PATH` without activating a virtual environment.
- Moved user command-config storage into a dedicated per-user `configs/` folder with legacy-file migration for existing profiles.
- Moved the current-user summary below the workspace label and docked the `CONFIG EDITOR` button to the top-right of the functions panel.
- Reworked the `Config Editor` into a three-panel browser, structured command editor, and JSON preview layout.

### Fixed

- Fixed logo loading for non-editable installs by switching from repo-root file discovery to packaged resources.
- Wired the `Clear Console` button so it clears the active workspace stream without closing the saved session.

### Removed

- Removed the built-in external protocol decoder dependency and its remaining code, tests, and documentation references from the base application.
- Removed the main-screen `Script Editor` entry point in favor of the scoped config-editor workflow.
- Removed the deprecated `serialhub.scripting` package and its remaining runtime hooks.

## [Unreleased] - 2026-04-20

### Added

- Added per-user TCP IP and TCP port history files with up/down recall in the connection form.
- Added a `Clear` button under the TCP port field to reset the TCP connection details quickly.
- Added regression coverage for TCP input history recall, persisted TCP history files, and the TCP clear action.

### Fixed

- Fixed delayed TCP disconnect UI refreshes by bounding socket shutdown waits and aborting stalled writer closes.

## [Unreleased] - 2026-04-19

### Added

- Added raw TCP/IP device connections from the existing `TCP/IP` tab using an IP address and port.
- Added an asyncio-driven TCP transport service that keeps socket I/O out of the Textual UI flow.
- Added regression coverage for TCP socket send/receive behavior and TCP workspace creation/disconnect flow.
- Added `Ctrl+Q` logout support that returns the app to the login screen and clears the remembered user.
- Added up/down TX message history recall backed by each user's `message_history.txt`.

### Changed

- Connection/session management now supports both serial and TCP transports while preserving room for future protocol plugins.
- Workspace and serial-device empty states now make it clear that TCP/IP connections remain available even when no serial ports are detected.
- Reworked the left-panel connection actions to use a docked bottom action row instead of percentage-based spacing.

### Fixed

- Fixed serial RX burst coalescing so the first character of a device message is no longer emitted as its own event when the port wakes from idle.
- Added a regression test covering the leading-byte split seen on live serial traffic.
- Fixed the `Ctrl+E` script editor shortcut so it works even when the focused widget would normally consume that key.

## [Unreleased] - 2026-04-18

### Added

- Added a startup login screen with username entry, `Remember Me`, and `New User`.
- Added local per-user profile storage under the SerialHub app-data directory.
- Added automatic user-folder generation with starter profile and command-config JSON files.
- Added a dynamic `Functions` panel that loads command-config choices from the active user's `COMMAND_CONFIGS`.
- Added generated function buttons for nested user command JSON structures.
- Added tests covering user-profile storage, remembered login state, and the login screen flow.

### Changed

- Logging now accepts either an existing folder path or an explicit `.txt` path in the `Log filepath` input.
- Directory-based logging now generates filenames from the device identifier and timestamp.
- Theme preference, log path, command-config references, and message history are now stored per user.
- Updated README documentation for the new login, user storage, logging, and functions-panel workflow.

## [Unreleased] - 2026-04-17

### Added

- Added dynamic per-device workspace tabs that are created as devices connect.
- Added a dedicated script editor screen with a toolbar button plus `Ctrl+E` and `Esc` shortcuts.
- Added a connected dark/light theme toggle on `Ctrl+T`.
- Added a tabbed `Connection` panel with `Serial` and `TCP/IP` sections.
- Added UI tests covering the script editor screen and workspace-tab persistence.

### Changed

- Workspace tabs now show the raw serial stream for each device instead of fixed `RAW` and parsed multi-pane layouts.
- Disconnecting a device now preserves its workspace tab and captured output until the user closes that tab.
- Closing a live workspace tab now disconnects the device before removing the saved session.
- Moved scripting controls out of the main workspace and into their own screen while keeping the main UI state intact.
- Removed protocol-specific notifications from the current UI flow while keeping room for future decoder work.
- Updated README documentation to reflect the new workspace, scripting, and theme behavior.

## [Unreleased] - 2026-04-05

### Added

- Added a local browser mode launched with `serialhub --web`.
- Added optional `--host` and `--port` arguments for browser mode hosting.

### Changed

- Switched project licensing from MIT to GPLv3.
- Browser mode now serves the existing Textual app through `textual-serve` instead of using a separate HTML frontend.
- Updated packaging metadata and README usage docs for the new browser workflow.

## [Unreleased] - 2026-04-01

### Changed

- Replaced the left-panel device `OptionList` with a dynamic `Select` dropdown.
- Replaced timestamp and auto-log controls from `Switch` widgets to `Checkbox` widgets.
- Added border titles to the three main panels (`left-panel`, `center-panel`, `right-panel`).
- Added keyboard shortcuts:
  - `M` to focus the TX message input
  - `D` to connect/disconnect the selected device
  - `L` to toggle logging for the active session

### Removed

- Suppressed `HEX Output` UI and related RAW log hex-rendering path.

## [0.1.0] - 2026-03-31

### Added

- Textual TUI for multi-device serial workflows.
- Initial structured protocol decoder integration.
- Tabbed RAW/PARSED visualization windows.
- Embedded Python scripting hooks (`on_message`, `on_pattern`).
- Per-device logging with optional custom filename and auto-log on connect.
- Cross-platform install scripts for Windows and Linux.
- Initial test suite and GitHub Actions CI.
