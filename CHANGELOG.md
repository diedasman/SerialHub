# Changelog

All notable changes to this project will be documented in this file.

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
