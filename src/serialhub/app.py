from __future__ import annotations

from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult  # type: ignore
from textual.binding import Binding  # type: ignore
from textual.containers import Horizontal, Vertical  # type: ignore
from textual.widgets import (  # type: ignore
    Button,
    Checkbox,
    Footer,
    Input,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from serialhub.config import get_logs_dir
from serialhub.core.device_manager import DeviceManager
from serialhub.core.models import DeviceInfo, SerialConfig, SerialEvent
from serialhub.core.session import DeviceSession
from serialhub.defaults import DEFAULT_SCRIPT_SOURCE, sanitize_log_filename
from serialhub.logging.session_logger import SessionLogger
from serialhub.protocols import AsciiBinaryDecoder, GuruxDlmsDecoder
from serialhub.scripting.engine import ScriptEngine
from serialhub.theme import SERIALHUB_THEME


class SerialHubApp(App[None]):
    CSS_PATH = "serialhub.tcss"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding("r", "refresh_devices", "Refresh Devices"),
        Binding("m", "focus_message_input", "Message"),
        Binding("d", "toggle_connect_disconnect", "Dis/Connect"),
        Binding("l", "toggle_logging_shortcut", "Logging"),
        Binding("ctrl+c", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.register_theme(SERIALHUB_THEME)
        self.theme = SERIALHUB_THEME.name

        self.device_manager = DeviceManager()
        self.script_engine = ScriptEngine()

        self.discovered_devices: list[DeviceInfo] = []
        self.selected_port: str | None = None
        self.active_device_id: str | None = None

        self.sessions: dict[str, DeviceSession] = {}
        self._shutting_down = False

        self._ascii_decoder = AsciiBinaryDecoder()
        self._dlms_decoder = GuruxDlmsDecoder()

    def compose(self) -> ComposeResult:
        with Horizontal(id="app-layout"):
            
            with Vertical(id="left-panel", classes="panel"):

                yield Button("Refresh", id="refresh-devices", classes="wide-btn")
                yield Select([], id="device-list", prompt="Select serial device", allow_blank=True)
                yield Static("Select a port to connect.", id="device-meta", classes="hint")

            with Vertical(id="center-panel", classes="panel"):
                with Horizontal(id="active-row"):
                    # yield Static("ACTIVE DEVICE", classes="section-title")
                    yield Select([], id="active-device", prompt="No active sessions", allow_blank=True)

                with TabbedContent(initial="tab-raw", id="viz-tabs"):
                    with TabPane("RAW", id="tab-raw"):
                        yield RichLog(id="raw-log", wrap=True, highlight=True, markup=False)

                    with TabPane("PARSED", id="tab-parsed"):
                        yield RichLog(id="parsed-log", wrap=True, highlight=True, markup=False)

                    with TabPane("DLMS", id="tab-dlms"):
                        yield RichLog(id="dlms-log", wrap=True, highlight=True, markup=False)

                with Horizontal(id="tx-row"):
                    yield Input(placeholder="Type message or hex payload...", id="tx-input")

                    yield Select(
                        id="tx-terminate-option",
                        value="none",
                        options=[
                            ("None", "none"),
                            ("CR", "cr"),
                            ("LF", "lf"),
                            ("CRLF", "crlf"),
                        ],
                        allow_blank=False,
                    )
                    yield Checkbox("HEX", id="tx-hex-checkbox")
                    yield Button("Send", variant="primary", id="send-btn")

                with Horizontal(id="script-control-row"):
                    yield Button("Run Script", id="script-start")
                    yield Button("Stop Script", id="script-stop")
                    yield Checkbox("Timestamps", value=True, id="timestamp-checkbox")

                yield Static("SCRIPT EDITOR", classes="section-title")
                yield TextArea(
                    DEFAULT_SCRIPT_SOURCE,
                    id="script-editor",
                    language="python",
                    show_line_numbers=True,
                )

            with Vertical(id="right-panel", classes="panel"):
                yield Select(
                    [
                        ("1200", "1200"),
                        ("2400", "2400"),
                        ("4800", "4800"),
                        ("9600", "9600"),
                        ("19200", "19200"),
                        ("38400", "38400"),
                        ("57600", "57600"),
                        ("115200", "115200"),
                        ("230400", "230400"),
                        ("460800", "460800"),
                        ("921600", "921600"),
                    ],
                    id="baud-select",
                    value="115200",
                    allow_blank=False,
                )
                yield Select(
                    [
                        ("Parity None (N)", "N"),
                        ("Parity Even (E)", "E"),
                        ("Parity Odd (O)", "O"),
                        ("Parity Mark (M)", "M"),
                        ("Parity Space (S)", "S"),
                    ],
                    id="parity-select",
                    value="N",
                    allow_blank=False,
                )
                yield Select(
                    [("Stop Bits 1", "1"), ("Stop Bits 1.5", "1.5"), ("Stop Bits 2", "2")],
                    id="stopbits-select",
                    value="1",
                    allow_blank=False,
                )
                yield Select(
                    [("Data Bits 8", "8"), ("Data Bits 7", "7"), ("Data Bits 6", "6"), ("Data Bits 5", "5")],
                    id="databits-select",
                    value="8",
                    allow_blank=False,
                )

                with Horizontal(classes="stack-row"):
                    yield Button("Connect", id="connect-btn", variant="success")
                    yield Button("Disconnect", id="disconnect-btn", variant="warning")

                yield Static("LOGGING", classes="section-title")
                yield Input(placeholder="Log filename (optional, .txt)", id="log-filename")
                with Horizontal(classes="stack-row"):
                    yield Checkbox("Auto-logging on connect", value=False, id="auto-log-checkbox")
                yield Button("Start Logging", id="toggle-logging")

        with Horizontal(id="footer-row"):
            yield Footer(id="app-footer")
            yield Static("SerialHub - by @diedasman", id="footer-brand")

    def on_mount(self) -> None:
        self._set_panel_border_titles()
        self._refresh_devices_ui()

        if not self._dlms_decoder.available:
            self.notify(
                "GURUX DLMS is unavailable. Install `gurux_dlms` for mandatory DLMS decoding.",
                severity="error",
            )
        else:
            self.notify("GURUX DLMS decoder ready.")

    def action_refresh_devices(self) -> None:
        self._refresh_devices_ui()

    def action_focus_message_input(self) -> None:
        self.query_one("#tx-input", Input).focus()

    def action_toggle_connect_disconnect(self) -> None:
        if not self.selected_port:
            self.notify("Select a device first.", severity="warning")
            return

        if self.selected_port in self.device_manager.connected_ports():
            self._disconnect_device(self.selected_port)
            return

        self._connect_selected_device()

    def action_toggle_logging_shortcut(self) -> None:
        self._toggle_logging_for_active_session()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""

        if button_id == "refresh-devices":
            self._refresh_devices_ui()
            return

        if button_id == "connect-btn":
            self._connect_selected_device()
            return

        if button_id == "disconnect-btn":
            self._disconnect_active_device()
            return

        if button_id == "send-btn":
            self._send_current_input()
            return

        if button_id == "toggle-logging":
            self._toggle_logging_for_active_session()
            return

        if button_id == "script-start":
            self._start_script_for_active_device()
            return

        if button_id == "script-stop":
            self._stop_script_for_active_device()
            return

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "device-list":
            value = event.value
            if value is Select.BLANK:
                self.selected_port = None
                self.query_one("#device-meta", Static).update("Select a port to connect.")
                return
            self.selected_port = str(value)
            self._update_device_meta(self.selected_port)
            return

        if event.select.id == "active-device":
            value = event.value
            if value is Select.BLANK:
                self.active_device_id = None
                self._render_active_logs()
                return
            self.active_device_id = str(value)
            self._render_active_logs()
            self._refresh_logging_button()
            return

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "timestamp-checkbox":
            enabled = event.value
            for session in self.sessions.values():
                session.timestamps_enabled = enabled
            self._render_active_logs()

    def on_unmount(self) -> None:
        self._shutting_down = True
        self.script_engine.stop_all()
        for session in self.sessions.values():
            if session.logger:
                session.logger.stop()
        self.device_manager.disconnect_all()

    def _refresh_devices_ui(self) -> None:
        self.discovered_devices = self.device_manager.scan_devices()

        device_list = self.query_one("#device-list", Select)
        options = [(item.label, item.port) for item in self.discovered_devices]
        device_list.set_options(options)

        if not self.discovered_devices:
            self.selected_port = None
            device_list.value = Select.BLANK
            self.query_one("#device-meta", Static).update("No serial devices detected.")
            self.notify("No serial devices found.")
        else:
            known_ports = {device.port for device in self.discovered_devices}
            if self.selected_port in known_ports:
                preferred_port = self.selected_port
            else:
                preferred_port = self.discovered_devices[0].port
            self.selected_port = preferred_port
            device_list.value = preferred_port
            self._update_device_meta(preferred_port)
            self.notify(f"Detected {len(self.discovered_devices)} serial device(s).")

    def _set_panel_border_titles(self) -> None:
        self.query_one("#left-panel", Vertical).border_title = " Connection "
        self.query_one("#center-panel", Vertical).border_title = " Workspace "
        self.query_one("#right-panel", Vertical).border_title = " Logging "

    def _update_device_meta(self, selected_port: str) -> None:
        selected = next((device for device in self.discovered_devices if device.port == selected_port), None)
        if not selected:
            self.query_one("#device-meta", Static).update(selected_port)
            return
        details = selected.label
        if selected.hwid:
            details += f"\n{selected.hwid}"
        self.query_one("#device-meta", Static).update(details)

    def _build_serial_config_from_inputs(self) -> SerialConfig:
        baud_text = str(self.query_one("#baud-select", Select).value)
        parity = str(self.query_one("#parity-select", Select).value)
        stop_bits = str(self.query_one("#stopbits-select", Select).value)
        data_bits = int(str(self.query_one("#databits-select", Select).value))

        config = SerialConfig(
            baudrate=int(baud_text),
            parity=parity,
            stopbits=stop_bits,
            databits=data_bits,
            timeout=0.2,
        )
        config.validate()
        return config

    def _connect_selected_device(self) -> None:
        if not self.selected_port:
            self.notify("Select a device first.", severity="warning")
            return

        try:
            config = self._build_serial_config_from_inputs()
        except Exception as exc:
            self.notify(f"Invalid serial config: {exc}", severity="error")
            return

        if self.selected_port not in self.sessions:
            session = DeviceSession(
                device_id=self.selected_port,
                port=self.selected_port,
                config=config,
                logger=None,
                timestamps_enabled=self.query_one("#timestamp-checkbox", Checkbox).value,
            )
            self.sessions[self.selected_port] = session
        else:
            self.sessions[self.selected_port].config = config

        try:
            self.device_manager.connect(self.selected_port, config, self._on_serial_event)
            self._refresh_active_device_select(preferred=self.selected_port)
            if self.query_one("#auto-log-checkbox", Checkbox).value:
                session = self.sessions[self.selected_port]
                self._start_logging_for_session(session, notify=False)
            self.notify(f"Connected to {self.selected_port}")
        except Exception as exc:
            self.notify(f"Connection failed: {exc}", severity="error")

    def _disconnect_active_device(self) -> None:
        target = self.active_device_id or self.selected_port
        if not target:
            self.notify("No device selected.", severity="warning")
            return
        self._disconnect_device(target)

    def _disconnect_device(self, target: str) -> None:
        if target not in self.device_manager.connected_ports():
            self.notify(f"{target} is not connected.", severity="warning")
            return

        self.script_engine.stop(target)

        session = self.sessions.get(target)
        if session and session.logger:
            session.logger.stop()

        try:
            self.device_manager.disconnect(target)
        except Exception as exc:
            self.notify(f"Disconnect error: {exc}", severity="error")

        connected = self.device_manager.connected_ports()
        if target not in connected:
            self.sessions.pop(target, None)

        preferred = connected[0] if connected else None
        self._refresh_active_device_select(preferred=preferred)

        if not connected:
            self.active_device_id = None
            self._render_active_logs()

    def _refresh_active_device_select(self, preferred: str | None = None) -> None:
        connected = self.device_manager.connected_ports()
        select = self.query_one("#active-device", Select)
        select.set_options([(device_id, device_id) for device_id in connected])

        if not connected:
            self.active_device_id = None
            select.value = Select.BLANK
            self._refresh_logging_button()
            return

        next_device = preferred if preferred in connected else connected[0]
        self.active_device_id = next_device
        select.value = next_device
        self._render_active_logs()
        self._refresh_logging_button()

    def _send_current_input(self) -> None:
        device_id = self.active_device_id
        if not device_id:
            self.notify("Connect and select an active device first.", severity="warning")
            return

        raw_input = self.query_one("#tx-input", Input).value
        is_hex = self._is_tx_hex_mode()
        terminator = str(self.query_one("#tx-terminate-option", Select).value)

        try:
            if is_hex:
                payload = bytes.fromhex(raw_input.strip())
            else:
                payload = raw_input.encode("utf-8")

            if terminator == "cr":
                payload += b"\r"
            elif terminator == "lf":
                payload += b"\n"
            elif terminator == "crlf":
                payload += b"\r\n"

            if not payload:
                self.notify("Nothing to send.", severity="warning")
                return
        except Exception as exc:
            self.notify(f"Invalid TX payload: {exc}", severity="error")
            return

        self._send_payload(device_id, payload)
        self.query_one("#tx-input", Input).value = ""

    def _send_payload(self, device_id: str, payload: bytes) -> None:
        conn = self.device_manager.get_connection(device_id)
        if not conn or not conn.is_open:
            self.notify(f"Device {device_id} is not connected.", severity="warning")
            return

        try:
            conn.send(payload)
        except Exception as exc:
            self.notify(f"Send failed: {exc}", severity="error")

    def _toggle_logging_for_active_session(self) -> None:
        session = self._get_active_session()
        if not session:
            self.notify("No active session selected.", severity="warning")
            return

        if session.logger and session.logger.is_running:
            session.logger.stop()
            self.notify(f"Logging stopped for {session.device_id}")
        else:
            self._start_logging_for_session(session, notify=True)
        self._refresh_logging_button()

    def _refresh_logging_button(self) -> None:
        button = self.query_one("#toggle-logging", Button)
        session = self._get_active_session()
        if not session or not session.logger or not session.logger.is_running:
            button.label = "Start Logging"
            return
        button.label = "Stop Logging"

    def _on_serial_event(self, event: SerialEvent) -> None:
        if self._shutting_down:
            return
        try:
            self.call_from_thread(self._handle_serial_event_ui, event)
        except RuntimeError:
            self._handle_serial_event_ui(event)

    def _handle_serial_event_ui(self, event: SerialEvent) -> None:
        if self._shutting_down:
            return
        session = self.sessions.get(event.device_id)
        if not session:
            return

        session.add_raw_event(event)

        if session.logger and session.logger.is_running:
            session.logger.log_event(event)

        prefix = self._format_prefix(session, event.timestamp)

        if event.direction in {"RX", "TX"} and event.payload is not None:
            ascii_result = self._ascii_decoder.decode(event.payload)
            dlms_result = self._dlms_decoder.decode(event.payload)

            session.add_parsed_line(f"{prefix}{event.direction} {ascii_result.protocol}")
            for line in ascii_result.lines:
                session.add_parsed_line(f"  {line}")

            session.add_dlms_line(f"{prefix}{event.direction} {dlms_result.protocol}")
            for line in dlms_result.lines:
                session.add_dlms_line(f"  {line}")

            if event.direction == "RX":
                self.script_engine.publish_rx(event.device_id, event.payload)

        else:
            info_text = event.text or ""
            session.add_parsed_line(f"{prefix}{event.direction} {info_text}")
            session.add_dlms_line(f"{prefix}{event.direction} {info_text}")

        if self.active_device_id == event.device_id:
            self._render_active_logs()

    def _format_prefix(self, session: DeviceSession, timestamp: datetime) -> str:
        if not session.timestamps_enabled:
            return ""
        return f"[{timestamp.strftime('%H:%M:%S.%f')[:-3]}] "

    def _render_raw_event_lines(self, session: DeviceSession, event: SerialEvent) -> list[str]:
        prefix = self._format_prefix(session, event.timestamp)
        if event.direction in {"RX", "TX"} and event.payload is not None:
            formatted = event.payload.decode("utf-8", errors="replace")
            lines = formatted.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            return [f"{prefix}{event.direction} {line}" for line in lines if line or len(lines) == 1]
        return [f"{prefix}{event.direction} {event.text or ''}"]

    def _is_tx_hex_mode(self) -> bool:
        return self.query_one("#tx-hex-checkbox", Checkbox).value

    def _render_active_logs(self) -> None:
        raw_log = self.query_one("#raw-log", RichLog)
        parsed_log = self.query_one("#parsed-log", RichLog)
        dlms_log = self.query_one("#dlms-log", RichLog)
        raw_log.clear()
        parsed_log.clear()
        dlms_log.clear()

        session = self._get_active_session()
        if not session:
            raw_log.write("No active device.")
            parsed_log.write("No active device.")
            dlms_log.write("No active device.")
            return

        if not session.raw_events:
            raw_log.write(f"Session ready for {session.device_id}.")
        else:
            for event in session.raw_events:
                for line in self._render_raw_event_lines(session, event):
                    raw_log.write(line)

        if not session.parsed_lines:
            parsed_log.write("Parsed output will appear here.")
        else:
            for line in session.parsed_lines:
                parsed_log.write(line)

        if not session.dlms_lines:
            dlms_log.write("DLMS output will appear here when frames are decoded.")
        else:
            for line in session.dlms_lines:
                dlms_log.write(line)

    def _start_script_for_active_device(self) -> None:
        device_id = self.active_device_id
        if not device_id:
            self.notify("No active device selected.", severity="warning")
            return

        script = self.query_one("#script-editor", TextArea).text
        if not script.strip():
            self.notify("Script is empty.", severity="warning")
            return

        def sender(payload: bytes) -> None:
            self.call_from_thread(self._send_payload, device_id, payload)

        def logger(message: str) -> None:
            event = SerialEvent(device_id=device_id, port=device_id, direction="SCRIPT", text=message)
            self.call_from_thread(self._handle_serial_event_ui, event)

        self.script_engine.start(device_id, script, sender=sender, logger=logger)
        self.notify(f"Script started for {device_id}")

    def _stop_script_for_active_device(self) -> None:
        device_id = self.active_device_id
        if not device_id:
            self.notify("No active device selected.", severity="warning")
            return

        self.script_engine.stop(device_id)
        self.notify(f"Script stopped for {device_id}")

    def _start_logging_for_session(self, session: DeviceSession, notify: bool = True) -> None:
        if session.logger and session.logger.is_running:
            return
        session.logger = SessionLogger(self._resolve_log_path(session.device_id))
        session.logger.start()
        if notify:
            self.notify(f"Logging started for {session.device_id}: {session.logger.log_path.name}")

    def _resolve_log_path(self, device_id: str) -> Path:
        custom_name = self.query_one("#log-filename", Input).value.strip()
        if custom_name:
            safe_name = sanitize_log_filename(custom_name)
            return get_logs_dir() / safe_name

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_device = device_id.replace("/", "_").replace("\\", "_").replace(":", "_")
        return get_logs_dir() / f"{safe_device}-{stamp}.txt"

    def _get_active_session(self) -> DeviceSession | None:
        if not self.active_device_id:
            return None
        return self.sessions.get(self.active_device_id)
