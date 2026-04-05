# Changelog

All notable changes to this project will be documented in this file.

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
