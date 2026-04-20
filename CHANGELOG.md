# Changelog

All notable changes to this project will be documented in this file.

---

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

- Connection/session management now supports both serial and TCP transports while preserving the current DLMS core code paths for future work.
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
- Added a tabbed `Connection` panel with `Serial`, `TCP/IP`, and `DLMS` sections.
- Added UI tests covering the script editor screen and workspace-tab persistence.

### Changed

- Workspace tabs now show the raw serial stream for each device instead of fixed `RAW`, `PARSED`, and `DLMS` panes.
- Disconnecting a device now preserves its workspace tab and captured output until the user closes that tab.
- Closing a live workspace tab now disconnects the device before removing the saved session.
- Moved scripting controls out of the main workspace and into their own screen while keeping the main UI state intact.
- Removed DLMS-specific notifications from the current UI flow while keeping the decoder code in place for future work.
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
- Mandatory GURUX DLMS decoder integration.
- Tabbed RAW/PARSED/DLMS visualization windows.
- Embedded Python scripting hooks (`on_message`, `on_pattern`).
- Per-device logging with optional custom filename and auto-log on connect.
- Cross-platform install scripts for Windows and Linux.
- Initial test suite and GitHub Actions CI.
