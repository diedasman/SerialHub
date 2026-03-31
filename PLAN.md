# plan.md

## Project Overview
A cross-platform serial communication and terminal application with advanced protocol support (DLMS-first), scripting, logging, and multi-device visualization. The application should function as a full-featured terminal replacement while supporting structured protocol decoding and automation workflows.

---

## Core Objectives

- Build a **fully functional terminal application** for serial communication
- Support **USB/Serial device communication** with auto-detection
- Implement **DLMS protocol support (via GURUX - mandatory)**
- Provide **multi-device handling and visualization**
- Enable **user scripting (Python)** for automation and interaction
- Include **trace logging and session recording**
- Deliver a **Textual (TUI) interface** with a custom theme
- Ensure **cross-platform support (Linux + Windows)**

---

## Functional Requirements

### 1. Serial Communication Layer
- Detect available USB/Serial devices automatically
- Allow manual refresh of device list
- Support:
  - Baud rate selection
  - Parity configuration
  - Stop bits
  - Data bits
- Open/close connections dynamically
- Handle multiple simultaneous connections
- Robust error handling (disconnects, timeouts, invalid configs)

---

### 2. Protocol Support

#### DLMS (Primary Focus)
- Integrate GURUX DLMS library
- Support:
  - Meter reading
  - OBIS code parsing
  - Frame decoding
- Provide both:
  - Raw frame view
  - Parsed/structured view

#### Additional Protocols (Planned)
- Modbus (RTU/TCP)
- Generic ASCII/Binary parsing
- Custom protocol plugin system (extensible)

---

### 3. Terminal Functionality
- Real-time data stream display
- Send arbitrary user input over serial
- Support:
  - Line-based input
  - Hex mode (optional)
- Scrollable output buffer
- Timestamped messages (optional toggle)
- ANSI/ASCII-safe rendering

---

### 4. Multi-Device Handling
- Support multiple concurrent device connections
- UI approaches (to evaluate):
  - Tab-based per device
  - Split-pane views
  - Device selector panel
- Each device should have:
  - Independent terminal
  - Independent configuration
  - Independent logging

---

### 5. Visualization Layer
- Raw stream view (terminal-like)
- Structured protocol decoding view (for DLMS and others)
- Optional:
  - Graphing of numeric values (future scope)
  - Highlighting/filtering of incoming data

---

### 6. Scripting Engine (Python)
- Embedded scripting environment
- Allow:
  - Sending messages programmatically
  - Reacting to incoming data
  - Scheduling routines
- Event-driven triggers:
  - On message received
  - On pattern match
- Script execution control:
  - Start/stop scripts
  - Logging script output

---

### 7. Macro / Button System
- User-defined buttons
- Each button sends predefined message(s)
- Optional:
  - Delay sequences
  - Multi-step commands
- Integrate with scripting system (trigger buttons programmatically)

---

### 8. Logging System
- Save communication logs to `.txt`
- Include:
  - Timestamp
  - Device identifier
  - Direction (RX/TX)
- Support:
  - Start/stop logging per device
  - Log rotation (future)
- Optional structured logs for parsed protocols

---

### 9. Textual UI (TUI)
- Built using Textual framework
- Custom theme (no default themes)
- Exclude:
  - Command palette
  - Header
- UI Components:
  - Device list panel
  - Terminal view(s)
  - Configuration panel
  - Script editor window
  - Macro/button panel
- Responsive layout for multiple devices

---

### 10. Installation & Distribution
- Hosted on GitHub
- Install via:
  - Git clone + setup script
- Provide:
  - Linux install script
  - Windows install script
- Dependency management (virtualenv or similar)

---

## Architecture Overview

### Suggested Layers
- **Device Layer**
  - Serial communication handling
- **Protocol Layer**
  - DLMS (GURUX)
  - Future protocol plugins
- **Core Engine**
  - Message routing
  - Event system
- **UI Layer**
  - Textual-based interface
- **Scripting Engine**
  - Python runtime integration
- **Persistence Layer**
  - Logs
  - User configs

---

## Open Questions / Design Considerations

### Multi-Device UI
- Tabs vs split view vs hybrid
- Performance with many devices
- Clear separation of contexts

### Protocol Abstraction
- How to unify different protocol parsers
- Plugin architecture vs built-in modules

### Scripting Safety
- Sandbox vs full Python access
- Error isolation per script

### Performance
- Handling high-throughput serial streams
- UI responsiveness under load

---

## Future Enhancements (Out of Immediate Scope)

- TCP/IP communication support
- GUI version (beyond TUI)
- Plugin marketplace
- Data visualization (charts/graphs)
- Session replay system
- Export logs in structured formats (CSV/JSON)
- Remote device access

---

## Risks & Constraints

- GURUX integration complexity
- Cross-platform serial handling inconsistencies
- Managing concurrency for multiple devices
- UI complexity in Textual for advanced layouts
- Scripting engine stability and safety

---

## Summary

This project aims to go beyond a simple serial monitor and become a modular, extensible communication platform with strong DLMS support, automation capabilities, and multi-device management. The main challenge lies in balancing flexibility (scripting, protocols) with usability (clean TUI, performance, clarity).