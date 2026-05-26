## Table of Contents

- [Connection](#connection)
- [Serial Devices](#serial-devices)
- [TCP/IP Devices](#tcpip-devices)
- [Connect And Disconnect](#connect-and-disconnect)
- [What Happens After Connecting](#what-happens-after-connecting)
- [Quick Reference](#quick-reference)

## Connection
>The **CONNECTION** panel is the left side of SerialHub. Use it to choose how SerialHub connects to a device, configure the details, and open or close the active device session. When a connection succeeds, SerialHub creates a workspace tab for that device in the monitor area and makes it active. Received and transmitted data for that device appears in that workspace.

SerialHub supports two connection types:

1. **Serial** for USB, UART, and virtual COM ports.
2. **TCP/IP** for raw socket devices available at an IP address and port.

```text
╭──────── CONNECTION ────────╮                              ╭──────── CONNECTION ────────╮
│                            │                              │                            │
│ Serial   TCP/IP            │                              │ Serial   TCP/IP            │
│ ══════   ──────            │                              │ ──────   ══════            │
│ ╭────────────────────────╮ │                              │ ╭────────────────────────╮ │
│ │         Refresh        │ │ ← refresh devices            │ │       IP Address       │ │ ← Device IP address input
│ ╰────────────────────────╯ │                              │ ╰────────────────────────╯ │
│ ╭────────────────────────╮ │                              │ ╭────────────────────────╮ │
│ │Select serial device ▼  │ │ ← device selector            │ │          Port          │ │ ← Device TCP port input
│ ╰────────────────────────╯ │                              │ ╰────────────────────────╯ │
│ ╭────────────────────────╮ │                              │ ╭────────────────────────╮ │
│ │       Baud Rate     ▼  │ │ ← set Baud Rate              │ │   Connection Label     │ │ ← User Label (Optional)
│ ╰────────────────────────╯ │                              │ ╰────────────────────────╯ │
│ ╭────────────────────────╮ │                              │ ╭────────────────────────╮ │
│ │         Parity      ▼  │ │ ← set Parity                 │ │          Clear         │ │ ← Clear Inputs
│ ╰────────────────────────╯ │                              │ ╰────────────────────────╯ │
│ ╭────────────────────────╮ │                              │ ╭────────────────────────╮ │
│ │        Stop Bits    ▼  │ │ ← set Stop Bits              │ │   Add to Favorites     │ │ ← Add to Favorites
│ ╰────────────────────────╯ │                              │ ╰────────────────────────╯ │
│ ╭────────────────────────╮ │                              │ ╭────────────────────────╮ │
│ │       Data Bits     ▼  │ │ ← set Data Bits              │ │   Saved Connections ▼  │ │ ← Saved Connections Dropdown
│ ╰────────────────────────╯ │                              │ ╰────────────────────────╯ │
│                            │                              │                            │
│ ╭───────────╮╭───────────╮ │                              │ ╭───────────╮╭───────────╮ │
│ │  Connect  ││Disconnect │ │                              │ │  Connect  ││Disconnect │ │
│ ╰───────────╯╰───────────╯ │                              │ ╰───────────╯╰───────────╯ │
╰────────────────────────────╯                              ╰────────────────────────────╯
```

### Serial Devices

>Open the **Serial** tab when you want to connect to a local serial port. Use **Refresh** to scan for connected serial devices. Choose the device from **Select serial device**, then set the serial parameters to match the hardware you are talking to. The device selector below it is populated with the detected ports. If no ports are found, the panel shows:

```text
No serial devices detected.
```

Available serial settings:

- **Baud rate**: `1200`, `2400`, `4800`, `9600`, `19200`, `38400`, `57600`, `115200`, `230400`, `460800`, or `921600`.
- **Parity**: `None (N)`, `Even (E)`, `Odd (O)`, `Mark (M)`, or `Space (S)`.
- **Stop Bits**: `1`, `1.5`, or `2`.
- **Data Bits**: `8`, `7`, `6`, or `5`.

The default serial setup is:

```text
Baud rate: 9600
Parity: None (N)
Stop Bits: 1
Data Bits: 8
```

>After selecting a port and confirming the settings, press **Connect**. SerialHub opens the port, creates a workspace for it, and switches the monitor to that workspace.

### TCP/IP Devices

Open the **TCP/IP** tab when you want to connect to a network device using a raw TCP socket.

Fill in:

- **IP Address**: the target IPv4 or IPv6 address.
- **TCP Port**: the target port number, from `1` to `65535`.
- **Connection Label**: optional text used to make the connection easier to recognize.

>Press **Connect** to open the socket. You can also press **Enter** while focused in the IP address, port, or label input to connect. Use **Clear** to empty the TCP/IP fields. Use **Add to Favorites** to save the current IP address, port, and label for the signed-in user. Saved connections appear in **Select saved Connections** and can be selected later instead of typing the details again. SerialHub validates TCP details before connecting. The IP address is required, the port must be a whole number, and the port must be between `1` and `65535`.

#### Connect And Disconnect

The **Connect** and **Disconnect** buttons at the bottom of the panel apply to the current selection and active workspace.

- **Connect** uses the selected tab. If the Serial tab is active, it connects to the selected serial port. If the TCP/IP tab is active, it connects to the entered TCP target.
- **Disconnect** closes the currently active workspace connection.

You can also press **D** to connect or disconnect. If the selected device is already connected, the shortcut disconnects it. Otherwise, it starts a new connection from the active connection tab.

#### What Happens After Connecting

After a successful connection:

- A workspace tab is created for the device.
- The new workspace becomes active.
- The monitor area begins showing RX and TX data for that device.
- The connection status indicator in the monitor toolbar updates.

If a connection fails, SerialHub shows an error notification and leaves the existing workspace state unchanged.

#### Quick Reference

```text
Serial tab
  Refresh -> choose port -> choose baud/parity/stop bits/data bits -> Connect

TCP/IP tab
  Enter IP address -> enter port -> optional label -> Connect

Disconnect
  Select the active workspace -> Disconnect

Shortcut
  D toggles connect/disconnect for the selected or active device
```
