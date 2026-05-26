## Table of Contents

- [Application Windows](#application-windows)
- [User Functions](#user-functions)
- [Command Config Files](#command-config-files)
- [Config Editor Workflow](#config-editor-workflow)
- [Function Button Layout](#function-button-layout)
- [Command History](#command-history)
- [Quick Reference](#quick-reference)

---

## Application Windows

The **FUNCTIONS** panel is the right side of SerialHub. It gives signed-in users quick access to saved command buttons, command history, and the screens used to manage the app.

Use the launcher buttons at the top of the panel:

- **Editor** opens the **Config Editor**, where user function files are created, edited, previewed, saved, and deleted.
- **Manual** opens this manual screen.
- **Settings** opens user preferences, including the startup command file setting.

Below the launcher, the panel has two command tabs:

- **Functions** shows command buttons from the selected command config file.
- **History** shows recently sent messages and user function commands.

---

## User Functions

User functions are saved commands that can be sent to the active device with one click. They are useful for setup commands, repeated queries, calibration steps, diagnostic messages, and any command string you send often.

To use a function:

1. Connect to a serial or TCP/IP device.
2. Open the **Functions** tab in the right panel.
3. Choose a command config from **Select command config**.
4. Press a function button to send that command to the active workspace.

SerialHub sends the command text exactly as it is stored in the config file. If the device expects a line ending, include it in the command value in the Config Editor, such as `\r`, `\n`, or `\r\n`.

```text
╭───────────── FUNCTIONS ──────────────╮
│ ╭──────────╮╭──────────╮╭──────────╮ │
│ │  Editor  ││  Manual  ││ Settings │ │ ← User Screens Launcher
│ ╰──────────╯╰──────────╯╰──────────╯ │
│ Functions   History                  │ ← Command Tabs (Functions)
│ ═════════   ───────                  │
│ ╭──────────────────────────────────╮ │
│ │  User Functions Selector    ▼    │ │ ← command file selector
│ ╰──────────────────────────────────╯ │
│ ╭──────────────────────────────────╮ │
│ │╭─────────────╮ ╭─────────────╮   │ │
│ ││  Button 1   │ │  Button 2   │   │ │ ← ungrouped buttons
│ │╰─────────────╯ ╰─────────────╯   │ │
│ │                                  │ │
│ ││GROUP LABEL                      │ │ ← group label (optional)
│ ││╭─────────────╮╭─────────────╮   │ │
│ │││  Button 1   ││  Button 2   │   │ │ ← grouped in rows of two
│ ││╰─────────────╯╰─────────────╯   │ │
│ ││╭─────────────╮╭─────────────╮   │ │
│ │││  Button 1   ││  Button 2   │   │ │ ← next row
│ ││╰─────────────╯╰─────────────╯   │ │
│ │╰───────────────────────────────  │ │
│ │ ...                              │ │
│ │                                  │ │
│ │ > Additional function buttons    │ │
│ │   generate here in groups or     │ │
│ │   individually                   │ │
│ │                                  │ │
│ ╰──────────────────────────────────╯ │
╰──────────────────────────────────────╯
```
---

## Command Config Files

Function buttons come from command config files owned by the current user. Each file appears in the **User Functions Selector** on the **Functions** tab.

A command config contains:

- **NAME**: the display name shown in the selector.
- **COMMANDS**: the commands that become function buttons.

Commands can be stored as simple label-to-string entries:

```json
{
    "NAME": "DEFAULTS",
    "COMMANDS": {
        "PING": "ping\r\n",
        "STATUS": "status\r\n"
    }
}
```

Commands can also be grouped by nesting them under a group name:

```json
{
    "NAME": "FIELD SETUP",
    "COMMANDS": {
        "SET": {
            "DATE": "set date\r\n",
            "TIME": "set time\r\n"
        },
        "GET": {
            "STATUS": "get status\r\n"
        }
    }
}
```

When SerialHub renders the file, top-level commands become ungrouped buttons and nested objects become group sections. Each group title is shown above its buttons.

For button colors, a command can use a detailed object with `VALUE` and `COLOR`:

```json
{
    "NAME": "COLORED",
    "COMMANDS": {
        "PING": {
            "VALUE": "ping\r\n",
            "COLOR": "success"
        }
    }
}
```

Available colors in the Config Editor are **Blue**, **Yellow**, **Red**, **Neutral**, and **Success**. Blue is the default.

## Config Editor Workflow

Use **Editor** to open the **Config Editor**. This is the safest way to create and update user functions because it keeps the JSON structure valid while showing a live preview of the file.

The Config Editor has three areas:

- **Command File Browser**: create a new file, select an existing file, or delete a file.
- **Command Builder**: edit the config name and command rows.
- **File Editor Preview**: inspect the JSON that will be saved.

To create a command file:

1. Press **Editor**.
2. Press **New**.
3. Enter a file name in **NAME**.
4. Fill in each command row.
5. Press **Add Command** for more rows.
6. Choose a group or create a new group when commands should appear together.
7. Choose a button color when a command needs visual emphasis.
8. Review the JSON preview.
9. Press **Save**.

Each command row has:

- **LABEL**: the text shown on the function button.
- **STRING**: the command text SerialHub sends.
- **GROUP**: optional grouping for related commands.
- **COLOR**: optional button color.

Use escaped line endings in the **STRING** field when needed:

- `\r` for carriage return.
- `\n` for line feed.
- `\r\n` for carriage return plus line feed.

After saving, SerialHub refreshes the command config selector. Select the saved file in the Functions tab to display its buttons.

## Function Button Layout

Function buttons are displayed in rows of two where space allows. Ungrouped commands appear first, followed by grouped commands. Groups can be nested in the JSON, but the panel is intended for quick access, so keep command labels short and group names clear.

Pressing a function button sends its stored command to the active device. If no workspace is active, SerialHub asks you to connect and select a device first. Empty commands are not sent.

## Command History

The **History** tab shows previously sent messages and user function commands, with the most recent command at the top.

Use history when you want to repeat or adjust a previous command:

- Select a history item to place it back into the TX input.
- Press **Send** from the monitor to transmit it again.
- Commands sent from function buttons are also added to history.

History is stored per user, so each local profile keeps its own recent commands.

```text
╭───────────── FUNCTIONS ──────────────╮
│ ╭──────────╮╭──────────╮╭──────────╮ │
│ │  Editor  ││  Manual  ││ Settings │ │ ← User Screens Launcher
│ ╰──────────╯╰──────────╯╰──────────╯ │
│ Functions   History                  │ ← Command Tabs (History)
│ ─────────   ═══════                  │
│ ╭──────────────────────────────────╮ │
│ │last_command                      │ │   list of previous commands,
│ │──────────────────────────────────│ │ ← most recent at the top
│ │serial_command                    │ │   Press Enter to execute again
│ │──────────────────────────────────│ │
│ │tcp_command                       │ │
│ │──────────────────────────────────│ │
│ │other_command                     │ │
│ │──────────────────────────────────│ │
│ │. . .                             │ │
│ │──────────────────────────────────│ │
│ │first_command                     │ │
│ │──────────────────────────────────│ │
│ ╰──────────────────────────────────╯ │
╰──────────────────────────────────────╯

```
---

## Quick Reference

```text
Create or edit functions
  Editor -> New or select a file -> add command rows -> Save

Use functions
  Connect a device -> Functions tab -> select command config -> press a button

Group functions
  In the Config Editor, choose a group for related command rows

Add line endings
  Use \r, \n, or \r\n in the command STRING field

Repeat commands
  History tab -> select previous command -> Send

Startup command file
  Settings -> choose startup command file -> Save
```

---
