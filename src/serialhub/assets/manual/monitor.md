## Table of Contents

- [Workspace Tabs](#workspace-tabs)
- [Status And Activity](#status-and-activity)
- [Sending Data](#sending-data)
- [Display And Logging](#display-and-logging)

The **MONITOR** panel is the center of SerialHub. It is where connected device sessions become workspace tabs, where serial or TCP traffic is displayed, and where outgoing messages are sent. Each connected device gets its own workspace tab. Switching tabs changes the active device for sending, logging, clearing, copying, and disconnecting.

Compact view of the monitor area:

```text
╭──────────────────────────────── MONITOR ─────────────────────────────╮
│ ╭──────────────╮ ╭─ ACTIVITY ───────────────────────╮ ╭─────────╮    │
│ │ CONNECTED  ● │ │                                  │ │  Clear  │    │
│ │ ▁▁▁▁▁▁▁▁▁▁▁▁ │ │ TX ▁▁▃▇▂▁▁▁▁▁▁▁▁▁▁▁▁▁▃▇▂▁▁▁▁▁▁▁▁ │ ╰─────────╯    │
│ │              │ │                                  │ ╭─────────╮    │
│ │ RX ●   TX ○  │ │ RX ▁▂▆▃▁▁▁▂▆▃▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▂▆▃▁ │ │  Close  │    │
│ ╰──────────────╯ ╰──────────────────────────────────╯ ╰─────────╯    │
│                                                                      │
│ ╭─[Workspace]─[COM3]─[192.168.1.50:502]───────────────────────╮      │
│ │                                                             │      │
│ │ 12:04:08 <<  device output appears here                     │      │
│ │ 12:04:10 >>  outgoing messages appear here                  │      │
│ │                                                             │      │
│ ╰─────────────────────────────────────────────────────────────╯      │
│                                                                      │
│ ╭───────────────────────────────────────╮ ╭───────╮ ╭──────╮         │
│ │ Type message or hex payload...        │ │ None ▾│ │ Send │ [ HEX ] │
│ ╰───────────────────────────────────────╯ ╰───────╯ ╰──────╯         │
│                             ╭───────────────╮ ╭────────╮ ╭──────╮    │
│ [ Timestamps ] [ Chevrons ] │ Log filepat...│ │  Save  │ │ Copy │    │
│                             ╰───────────────╯ ╰────────╯ ╰──────╯    │
│                                                                      │
╰──────────────────────────────────────────────────────────────────────╯
```

### Workspace Tabs

SerialHub opens a workspace tab after a successful serial or TCP connection. The active tab controls which device receives messages from the TX input.

Use **Close** to close the active workspace tab. If that device is still connected, SerialHub disconnects it before removing the tab.

Use **Clear** to clear the visible console history for the active workspace.

### Status And Activity

The toolbar at the top of the monitor shows the active connection state and RX/TX activity indicators.

- **CONNECTION** shows whether the active workspace is currently connected.
- **RX** flashes when data is received.
- **TX** flashes when data is transmitted.
- The activity sparklines provide a compact visual hint of recent receive and transmit volume.

### Sending Data

Type outgoing data in the TX input at the bottom of the monitor and press **Send**.

The line-ending selector controls what SerialHub appends to the outgoing message:

- **None** sends the text exactly as typed.
- **CR** appends carriage return.
- **LF** appends line feed.
- **CRLF** appends carriage return and line feed.

Enable **HEX** when you want the TX input to be interpreted as hexadecimal bytes instead of plain text.

### Display And Logging

Use **Timestamps** to show or hide timestamps on workspace events.

Use **Chevrons** to show or hide direction markers around RX and TX lines.

Use **Save Log** to start or stop logging for the active workspace. If the log path points to a folder, SerialHub creates a device-specific log filename automatically. If it points to a `.txt` file, SerialHub writes to that exact file.

Use **Copy Workspace** to copy the active workspace contents to the clipboard.
