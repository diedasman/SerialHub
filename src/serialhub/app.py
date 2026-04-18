from __future__ import annotations

from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult  # type: ignore
from textual.binding import Binding  # type: ignore
from textual.containers import Horizontal, Vertical  # type: ignore
from textual.screen import Screen  # type: ignore
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
from serialhub.theme import APP_THEMES, DEFAULT_THEME_MODE, resolve_textual_theme_name, toggle_theme_mode


class ScriptEditorScreen(Screen[None]):
    BINDINGS = [
        Binding("ctrl+e", "close_script_editor", "Close Editor"),
        Binding("escape", "close_script_editor", "Close Editor"),
    ]

    def compose(self) -> ComposeResult:
        app = self.app
        active_device = app.active_device_id or "No workspace selected"
        with Vertical(id="script-screen"):
            with Horizontal(id="script-screen-toolbar"):
                yield Static("SCRIPT EDITOR", classes="section-title")
                yield Static(f"Active device: {active_device}", id="script-active-device", classes="hint")
                yield Button("Run Script", id="script-start")
                yield Button("Stop Script", id="script-stop")
                yield Button("Close", id="script-close", variant="primary")

            yield TextArea(
                app.script_source,
                id="script-editor",
                language="python",
                show_line_numbers=True,
            )
        yield Footer(id="script-editor-footer")

    def action_close_script_editor(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "script-start":
            self.app._start_script_for_active_device()
            return
        if button_id == "script-stop":
            self.app._stop_script_for_active_device()
            return
        if button_id == "script-close":
            self.app.pop_screen()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "script-editor":
            self.app.script_source = event.text_area.text


class SerialHubApp(App[None]):
    CSS_PATH = "serialhub.tcss"
    ENABLE_COMMAND_PALETTE = False
    WORKSPACE_PLACEHOLDER_ID = "workspace-empty"
    BINDINGS = [
        Binding("r", "refresh_devices", "Refresh Devices"),
        Binding("m", "focus_message_input", "Message"),
        Binding("d", "toggle_connect_disconnect", "Dis/Connect"),
        Binding("l", "toggle_logging_shortcut", "Logging"),
        Binding("ctrl+e", "toggle_script_editor", "Script Editor"),
        Binding("ctrl+t", "toggle_theme", "Theme"),
        Binding("ctrl+c", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()

        self.theme_mode = DEFAULT_THEME_MODE
        for theme in APP_THEMES.values():
            self.register_theme(theme)
        self.theme = resolve_textual_theme_name(self.theme_mode)

        self.device_manager = DeviceManager()
        self.script_engine = ScriptEngine()

        self.discovered_devices: list[DeviceInfo] = []
        self.selected_port: str | None = None
        self.active_device_id: str | None = None
        self.script_source = DEFAULT_SCRIPT_SOURCE

        self.sessions: dict[str, DeviceSession] = {}
        self._shutting_down = False

        self._workspace_counter = 0
        self._workspace_placeholder_visible = True
        self._workspace_panes: dict[str, str] = {}
        self._workspace_devices_by_pane: dict[str, str] = {}
        self._workspace_logs: dict[str, RichLog] = {}
        self._workspace_statuses: dict[str, Static] = {}

        self._ascii_decoder = AsciiBinaryDecoder()
        self._dlms_decoder = GuruxDlmsDecoder()

    def compose(self) -> ComposeResult:
        with Horizontal(id="app-layout"):
            with Vertical(id="left-panel", classes="panel"):
                with TabbedContent(initial="connection-serial", id="connection-tabs"):
                    with TabPane("Serial", id="connection-serial"):
                        yield Button("Refresh", id="refresh-devices", classes="wide-btn")
                        yield Select([], id="device-list", prompt="Select serial device", allow_blank=True)

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
                        value="9600",
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

                        yield Static("Select a port to connect.", id="device-meta", classes="hint")

                    with TabPane("TCP/IP", id="connection-tcp"):
                        yield Static("TCP/IP tools will land here in a later update.", classes="hint")

                    with TabPane("DLMS", id="connection-dlms"):
                        yield Static("DLMS tools will return in a later update.", classes="hint")
                
                with Horizontal(classes="stack-row"):
                    yield Button("Connect", id="connect-btn", variant="success")
                    yield Button("Disconnect", id="disconnect-btn", variant="warning")

            with Vertical(id="center-panel", classes="panel"):
                with Horizontal(id="workspace-toolbar"):
                    
                    yield Static("No device workspaces open.", id="workspace-selection", classes="hint")

                with TabbedContent(initial=self.WORKSPACE_PLACEHOLDER_ID, id="workspace-tabs"):
                    with TabPane("Workspace", id=self.WORKSPACE_PLACEHOLDER_ID):
                        yield Static(
                            "Connect a serial device to create a raw stream workspace tab.",
                            id="workspace-placeholder",
                            classes="hint",
                        )

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

                yield Checkbox("Timestamps", value=True, id="timestamp-checkbox")
                yield Button("Script Editor", id="open-script-editor")

            with Vertical(id="right-panel", classes="panel"):
                

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
        self._sync_active_device_from_workspace()
        self._refresh_logging_button()

    def action_refresh_devices(self) -> None:
        self._refresh_devices_ui()

    def action_focus_message_input(self) -> None:
        self.query_one("#tx-input", Input).focus()

    def action_toggle_connect_disconnect(self) -> None:
        if not self.selected_port:
            self.notify("Select a device first.", severity="warning")
            return

        if self._is_device_connected(self.selected_port):
            self._disconnect_device(self.selected_port)
            return

        self._connect_selected_device()

    def action_toggle_logging_shortcut(self) -> None:
        self._toggle_logging_for_active_session()

    def action_toggle_script_editor(self) -> None:
        if isinstance(self.screen, ScriptEditorScreen):
            self.pop_screen()
            return
        self.push_screen(ScriptEditorScreen())

    def action_toggle_theme(self) -> None:
        self.theme_mode = toggle_theme_mode(self.theme_mode)
        self.theme = resolve_textual_theme_name(self.theme_mode)
        self.notify(f"Theme changed to {self.theme_mode}.")

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

        if button_id == "open-script-editor":
            self.action_toggle_script_editor()
            return

        if button_id.startswith("close-tab--"):
            pane_id = button_id.removeprefix("close-tab--")
            device_id = self._workspace_devices_by_pane.get(pane_id)
            if device_id:
                self._close_workspace_for_device(device_id)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "device-list":
            return

        value = event.value
        if value is Select.BLANK:
            self.selected_port = None
            self.query_one("#device-meta", Static).update("Select a port to connect.")
            return

        self.selected_port = str(value)
        self._update_device_meta(self.selected_port)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id != "timestamp-checkbox":
            return

        enabled = event.value
        for session in self.sessions.values():
            session.timestamps_enabled = enabled
        for device_id in self.sessions:
            self._render_workspace_session(device_id)

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.tabbed_content.id == "workspace-tabs":
            self._sync_active_device_from_workspace()

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
            return

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

        session = self.sessions.get(self.selected_port)
        if session is None:
            session = DeviceSession(
                device_id=self.selected_port,
                port=self.selected_port,
                config=config,
                logger=None,
                timestamps_enabled=self.query_one("#timestamp-checkbox", Checkbox).value,
            )
            self.sessions[self.selected_port] = session
        else:
            session.config = config
            session.timestamps_enabled = self.query_one("#timestamp-checkbox", Checkbox).value

        try:
            self.device_manager.connect(self.selected_port, config, self._on_serial_event)
        except Exception as exc:
            self.notify(f"Connection failed: {exc}", severity="error")
            return

        self._ensure_workspace_for_device(self.selected_port)
        self._set_active_workspace(self.selected_port)

        if self.query_one("#auto-log-checkbox", Checkbox).value:
            self._start_logging_for_session(session, notify=False)

        self._refresh_workspace_state(self.selected_port)
        self.notify(f"Connected to {self.selected_port}")

    def _disconnect_active_device(self) -> None:
        target = self.active_device_id or self.selected_port
        if not target:
            self.notify("No device selected.", severity="warning")
            return
        self._disconnect_device(target)

    def _disconnect_device(self, target: str) -> None:
        if not self._is_device_connected(target):
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
            return

        self._refresh_workspace_state(target)
        self._sync_active_device_from_workspace()

    def _close_workspace_for_device(self, device_id: str) -> None:
        if self._is_device_connected(device_id):
            self._disconnect_device(device_id)

        self.script_engine.stop(device_id)

        session = self.sessions.pop(device_id, None)
        if session and session.logger:
            session.logger.stop()

        pane_id = self._workspace_panes.pop(device_id, None)
        self._workspace_logs.pop(device_id, None)
        self._workspace_statuses.pop(device_id, None)

        if pane_id:
            self._workspace_devices_by_pane.pop(pane_id, None)
            self.query_one("#workspace-tabs", TabbedContent).remove_pane(pane_id)

        if not self._workspace_panes:
            self._ensure_workspace_placeholder()

        self._sync_active_device_from_workspace()
        self.notify(f"Closed workspace tab for {device_id}")

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
            self.notify("No active workspace selected.", severity="warning")
            return

        if session.logger and session.logger.is_running:
            session.logger.stop()
            self.notify(f"Logging stopped for {session.device_id}")
            self._refresh_workspace_state(session.device_id)
            return

        if not self._is_device_connected(session.device_id):
            self.notify("Connect the active device before starting logging.", severity="warning")
            return

        self._start_logging_for_session(session, notify=True)
        self._refresh_workspace_state(session.device_id)

    def _refresh_logging_button(self) -> None:
        button = self.query_one("#toggle-logging", Button)
        session = self._get_active_session()
        if not session:
            button.label = "Start Logging"
            button.disabled = True
            return

        if session.logger and session.logger.is_running:
            button.label = "Stop Logging"
            button.disabled = False
            return

        button.label = "Start Logging"
        button.disabled = not self._is_device_connected(session.device_id)

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

        self._refresh_workspace_state(event.device_id)

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

    def _start_script_for_active_device(self) -> None:
        device_id = self.active_device_id
        if not device_id:
            self.notify("No active device selected.", severity="warning")
            return

        if not self._is_device_connected(device_id):
            self.notify("Connect the active device before starting a script.", severity="warning")
            return

        script = self.script_source
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

    def _ensure_workspace_for_device(self, device_id: str) -> None:
        existing_pane = self._workspace_panes.get(device_id)
        if existing_pane:
            self._refresh_workspace_state(device_id)
            return

        self._remove_workspace_placeholder()

        self._workspace_counter += 1
        pane_id = f"workspace-pane-{self._workspace_counter}"
        status = Static(classes="workspace-status")
        close_button = Button("Close Tab", id=f"close-tab--{pane_id}", classes="workspace-close-btn")
        raw_log = RichLog(wrap=True, highlight=True, markup=False)

        pane = TabPane(
            self._workspace_tab_label(device_id),
            Vertical(
                Horizontal(status, close_button, classes="workspace-pane-toolbar"),
                raw_log,
                classes="workspace-pane",
            ),
            id=pane_id,
        )

        self._workspace_panes[device_id] = pane_id
        self._workspace_devices_by_pane[pane_id] = device_id
        self._workspace_logs[device_id] = raw_log
        self._workspace_statuses[device_id] = status

        tabs = self.query_one("#workspace-tabs", TabbedContent)
        tabs.add_pane(pane)
        tabs.active = pane_id
        self.call_after_refresh(self._refresh_workspace_state, device_id)

    def _render_workspace_session(self, device_id: str) -> None:
        session = self.sessions.get(device_id)
        raw_log = self._workspace_logs.get(device_id)
        if not session or raw_log is None:
            return

        raw_log.clear()
        if not session.raw_events:
            if self._is_device_connected(device_id):
                raw_log.write(f"Session ready for {device_id}.")
            else:
                raw_log.write(f"Saved session for {device_id}. Reconnect to continue streaming.")
            return

        for event in session.raw_events:
            for line in self._render_raw_event_lines(session, event):
                raw_log.write(line)

    def _refresh_workspace_state(self, device_id: str) -> None:
        self._render_workspace_session(device_id)
        self._update_workspace_tab_label(device_id)
        self._update_workspace_status(device_id)
        self._sync_active_device_from_workspace()

    def _update_workspace_tab_label(self, device_id: str) -> None:
        pane_id = self._workspace_panes.get(device_id)
        if not pane_id:
            return
        tab = self.query_one("#workspace-tabs", TabbedContent).get_tab(pane_id)
        tab.label = self._workspace_tab_label(device_id)

    def _update_workspace_status(self, device_id: str) -> None:
        status = self._workspace_statuses.get(device_id)
        if status is None:
            return

        connection_text = "Connected" if self._is_device_connected(device_id) else "Disconnected"
        logging_text = ""
        session = self.sessions.get(device_id)
        if session and session.logger and session.logger.is_running:
            logging_text = " | Logging"
        status.update(f"{device_id} | {connection_text}{logging_text}")

    def _workspace_tab_label(self, device_id: str) -> str:
        state = "live" if self._is_device_connected(device_id) else "saved"
        return f"{device_id} [{state}]"

    def _set_active_workspace(self, device_id: str | None) -> None:
        if not device_id:
            self.active_device_id = None
            self._update_workspace_summary()
            self._refresh_logging_button()
            return

        pane_id = self._workspace_panes.get(device_id)
        if pane_id:
            self.query_one("#workspace-tabs", TabbedContent).active = pane_id
        self.active_device_id = device_id
        self._update_workspace_summary()
        self._refresh_logging_button()

    def _sync_active_device_from_workspace(self) -> None:
        tabs = self.query_one("#workspace-tabs", TabbedContent)
        self.active_device_id = self._workspace_devices_by_pane.get(tabs.active)
        self._update_workspace_summary()
        self._refresh_logging_button()

    def _update_workspace_summary(self) -> None:
        summary = self.query_one("#workspace-selection", Static)
        if not self.active_device_id:
            summary.update("No device workspaces open.")
            return

        state = "connected" if self._is_device_connected(self.active_device_id) else "saved"
        summary.update(f"Active workspace: {self.active_device_id} ({state})")

    def _remove_workspace_placeholder(self) -> None:
        if not self._workspace_placeholder_visible:
            return
        self.query_one("#workspace-tabs", TabbedContent).remove_pane(self.WORKSPACE_PLACEHOLDER_ID)
        self._workspace_placeholder_visible = False

    def _ensure_workspace_placeholder(self) -> None:
        if self._workspace_placeholder_visible:
            return

        pane = TabPane(
            "Workspace",
            Static(
                "Connect a serial device to create a raw stream workspace tab.",
                id="workspace-placeholder",
                classes="hint",
            ),
            id=self.WORKSPACE_PLACEHOLDER_ID,
        )
        tabs = self.query_one("#workspace-tabs", TabbedContent)
        tabs.add_pane(pane)
        tabs.active = self.WORKSPACE_PLACEHOLDER_ID
        self._workspace_placeholder_visible = True

    def _is_device_connected(self, device_id: str) -> bool:
        return device_id in self.device_manager.connected_ports()
