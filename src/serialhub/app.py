from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from importlib.resources import files
from pathlib import Path

from textual.app import App, ComposeResult  # type: ignore
from textual.binding import Binding  # type: ignore
from textual.containers import Horizontal, Vertical, VerticalScroll  # type: ignore
from textual.css.query import NoMatches  # type: ignore
from textual.screen import ModalScreen, Screen  # type: ignore
from textual.widget import Widget  # type: ignore
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

from serialhub.config import get_data_dir, get_logs_dir
from serialhub.core.device_manager import DeviceManager
from serialhub.core.models import DeviceInfo, DeviceTransport, SerialConfig, SerialEvent, TcpConfig
from serialhub.core.session import DeviceSession
from serialhub.defaults import DEFAULT_SCRIPT_SOURCE
from serialhub.logging.paths import resolve_log_destination
from serialhub.logging.session_logger import SessionLogger
from serialhub.protocols import AsciiBinaryDecoder
from serialhub.scripting.engine import ScriptEngine
from serialhub.theme import (
    APP_THEMES,
    DEFAULT_THEME_MODE,
    normalize_theme_mode,
    resolve_textual_theme_name,
    toggle_theme_mode,
)
from serialhub.user_profiles import (
    CommandConfig,
    UserProfile,
    create_user_profile,
    get_remembered_username,
    get_user_default_logs_dir,
    get_user_message_history_path,
    get_user_tcp_ip_history_path,
    get_user_tcp_port_history_path,
    load_command_configs,
    load_user_profile,
    normalize_username,
    save_user_profile,
    set_remembered_username,
)


INPUT_HISTORY_MESSAGE = "message"
INPUT_HISTORY_TCP_IP = "tcp-ip"
INPUT_HISTORY_TCP_PORT = "tcp-port"

_INPUT_HISTORY_SELECTORS = {
    INPUT_HISTORY_MESSAGE: "#tx-input",
    INPUT_HISTORY_TCP_IP: "#ip-input",
    INPUT_HISTORY_TCP_PORT: "#port-input",
}

_INPUT_HISTORY_FALLBACK_FILENAMES = {
    INPUT_HISTORY_MESSAGE: "message_history.txt",
    INPUT_HISTORY_TCP_IP: "tcp_ip_history.txt",
    INPUT_HISTORY_TCP_PORT: "tcp_port_history.txt",
}


def load_ascii_logo() -> str:
    """Load the packaged ASCII logo text."""
    try:
        return files("serialhub").joinpath("assets").joinpath("logo.txt").read_text(encoding="utf-8").strip()
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return ""


@dataclass(slots=True)
class CommandButtonSpec:
    label: str
    payload: str


@dataclass(slots=True)
class InputHistoryState:
    cache: list[str] = field(default_factory=list)
    index: int | None = None
    draft: str = ""
    ignore_next_change: bool = False


class HistoryInput(Input):
    BINDINGS = [
        *Input.BINDINGS,
        Binding("up", "history_previous", show=False),
        Binding("down", "history_next", show=False),
    ]

    def __init__(self, *args, history_id: str, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.history_id = history_id

    def action_history_previous(self) -> None:
        app = getattr(self, "app", None)
        if app is not None and hasattr(app, "_navigate_input_history"):
            app._navigate_input_history(self.history_id, -1)

    def action_history_next(self) -> None:
        app = getattr(self, "app", None)
        if app is not None and hasattr(app, "_navigate_input_history"):
            app._navigate_input_history(self.history_id, 1)


class UserLoginScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    UserLoginScreen {
        align: center middle;
    }

    #login-modal {
        width: 48;
        max-width: 72;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }

    #login-message {
        color: $accent;
        margin-bottom: 1;
    }

    #login-username {
        margin-bottom: 1;
    }

    #login-actions {
        height: auto;
        margin-top: 1;
    }

    #login-submit,
    #login-new-user {
        width: 1fr;
    }
    """

    BINDINGS = [
        Binding("enter", "submit_login", "Login"),
        Binding("escape", "cancel_login", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="login-modal"):
            yield Static("SERIALHUB LOGIN", classes="section-title")
            yield Static(
                "Enter a username to sign in, or create a new local profile from this screen.",
                id="login-message",
            )
            yield Input(placeholder="Username", id="login-username")
            yield Checkbox("Remember Me", id="login-remember")
            with Horizontal(id="login-actions"):
                yield Button("Login", id="login-submit", variant="primary")
                yield Button("New User", id="login-new-user", variant="success")

    def on_mount(self) -> None:
        self.query_one("#login-username", Input).focus()

    def action_submit_login(self) -> None:
        self._submit("login")

    def action_cancel_login(self) -> None:
        self.app.exit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "login-submit":
            self._submit("login")
            return
        if button_id == "login-new-user":
            self._submit("new-user")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "login-username":
            self._submit("login")

    def _submit(self, action: str) -> None:
        username = self.query_one("#login-username", Input).value.strip()
        remember_me = self.query_one("#login-remember", Checkbox).value
        self.app.handle_login_action(action, username, remember_me)


class ScriptEditorScreen(Screen[None]):
    BINDINGS = [
        Binding("ctrl+e", "close_script_editor", "Close Editor", priority=True),
        Binding("escape", "close_script_editor", "Close Editor"),
    ]

    def compose(self) -> ComposeResult:
        app = self.app
        active_device = app.active_device_id or "No workspace selected"

        with Horizontal(id="script-editor-layout"):

            with Vertical(id="script-list", classes="panel"):
                yield Button("Close", id="script-list-close", variant="primary")

            with Vertical(id="script-screen", classes="panel"):
                with Horizontal(id="script-screen-toolbar"):
                    # yield Static("SCRIPT EDITOR", classes="section-title")
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

    def on_mount(self) -> None:
        self.query_one("#script-editor", TextArea).focus()
        self._set_panel_border_titles()

    def _set_panel_border_titles(self) -> None:
        self.query_one("#script-list", Vertical).border_title = " Script List "
        self.query_one("#script-screen", Vertical).border_title = " Script Editor "

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
        if button_id in {"script-list-close", "script-close"}:
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
        Binding("ctrl+e", "toggle_script_editor", "Script Editor", priority=True),
        Binding("ctrl+t", "toggle_theme", "Theme"),
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+q", "logout", "Logout", priority=True),
    ]

    def __init__(
        self,
        *,
        require_login: bool = True,
        startup_user: UserProfile | None = None,
    ) -> None:
        super().__init__()

        self.require_login = require_login
        self.current_user = startup_user

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

        self._command_button_counter = 0
        self._command_configs: dict[str, CommandConfig] = {}
        self._command_buttons: dict[str, CommandButtonSpec] = {}
        self._refreshing_command_configs = False
        self._input_history_states = {
            history_id: InputHistoryState()
            for history_id in _INPUT_HISTORY_SELECTORS
        }

        self._ascii_decoder = AsciiBinaryDecoder()

        self._logo_content = self._load_logo()

    def _load_logo(self) -> str:
        """Load the packaged ASCII logo."""
        return load_ascii_logo()

    def _workspace_placeholder_text(self) -> str:
        return self._logo_content or "SerialHub"

    def _query_ui(self, selector: str, expect_type: type[Widget]) -> Widget:
        for screen in reversed(tuple(self.screen_stack)):
            try:
                return screen.query_one(selector, expect_type)
            except NoMatches:
                continue
        return self.query_one(selector, expect_type)

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
                            [
                                ("Data Bits 8", "8"),
                                ("Data Bits 7", "7"),
                                ("Data Bits 6", "6"),
                                ("Data Bits 5", "5"),
                            ],
                            id="databits-select",
                            value="8",
                            allow_blank=False,
                        )
                        yield Checkbox("Auto-logging on connect", value=False, id="auto-log-checkbox")
                        yield Static("Select a port to connect.", id="device-meta", classes="hint")

                    with TabPane("TCP/IP", id="connection-tcp"):
                        yield Static(
                            "Enter a device IP address and TCP port to open a raw socket session.",
                            id="tcp-meta",
                            classes="hint",
                        )
                        yield HistoryInput(
                            placeholder="IP Address",
                            id="ip-input",
                            history_id=INPUT_HISTORY_TCP_IP,
                        )
                        yield HistoryInput(
                            placeholder="TCP Port",
                            id="port-input",
                            history_id=INPUT_HISTORY_TCP_PORT,
                        )
                        yield Button("Clear", id="clear-tcp-inputs")

                with Horizontal(id="left-panel-actions", classes="stack-row"):
                    yield Button("Connect", id="connect-btn", variant="success")
                    yield Button("Disconnect", id="disconnect-btn", variant="warning")

            with Vertical(id="center-panel", classes="panel"):
                with Horizontal(id="workspace-toolbar"):
                    yield Static("No device workspaces open.", id="workspace-selection", classes="hint")
                    yield Button("Close Tab", id="close-active-workspace", variant="error", disabled=True)

                with TabbedContent(initial=self.WORKSPACE_PLACEHOLDER_ID, id="workspace-tabs"):
                    with TabPane("Workspace", id=self.WORKSPACE_PLACEHOLDER_ID):
                        yield Vertical(
                            Static(
                                " " + self._workspace_placeholder_text(),
                                id="workspace-placeholder",
                                classes="workspace-content workspace-placeholder-text",
                            ),
                            classes="workspace-pane",
                        )
                    
                with Horizontal(id="tx-row"):
                    yield HistoryInput(
                        placeholder="Type message or hex payload...",
                        id="tx-input",
                        history_id=INPUT_HISTORY_MESSAGE,
                    )
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
                    yield Button("Send", variant="success", id="send-btn")
                    yield Checkbox("HEX", id="tx-hex-checkbox")

                with Horizontal(id="function-buttons-row"):
                    yield Checkbox("Timestamps", value=True, id="timestamp-checkbox")
                    yield Input(placeholder="Log folder or .txt path", id="log-filepath")
                    yield Button("Start Logging", id="toggle-logging")
                    yield Button("Script Editor", id="open-script-editor")

            with Vertical(id="right-panel", classes="panel"):

                with Horizontal(id="label-row"):
                    # yield Static("USER DEFINED", classes="section-title")
                    yield Static("No user.", id="current-user-summary", classes="section-title")
                
                yield Select([], id="command-config-select", prompt="Select command config", allow_blank=True)
                # yield Static(
                #     "Sign in to load your command config files.",
                #     id="command-config-hint",
                #     classes="hint",
                # )
                yield VerticalScroll(id="command-buttons-scroll")

        with Horizontal(id="footer-row"):
            yield Footer(id="app-footer")
            # yield Static("SerialHub - by @diedasman", id="footer-brand")

    def on_mount(self) -> None:
        self._set_panel_border_titles()
        self._refresh_devices_ui()
        self._sync_active_device_from_workspace()
        self._refresh_logging_button()
        self._refresh_user_dependent_ui()

        if self.current_user:
            self._activate_user_profile(self.current_user, remember=None, show_notification=False)
            return

        if self.require_login:
            self.call_after_refresh(self._show_startup_login)

    def action_refresh_devices(self) -> None:
        self._refresh_devices_ui()

    def action_focus_message_input(self) -> None:
        tx_input = self._query_ui("#tx-input", Input)
        tx_input.focus()
        self._set_input_history_draft(INPUT_HISTORY_MESSAGE, tx_input.value)

    def action_toggle_connect_disconnect(self) -> None:
        if self._active_connection_tab() == "connection-tcp":
            try:
                device_id = self._build_tcp_config_from_inputs().device_id
            except Exception as exc:
                self.notify(f"Invalid TCP config: {exc}", severity="error")
                return
        else:
            device_id = self.selected_port
            if not device_id:
                self.notify("Select a device first.", severity="warning")
                return

        if self._is_device_connected(device_id):
            self._disconnect_device(device_id)
            return

        self._connect_selected_device()

    def action_toggle_logging_shortcut(self) -> None:
        self._toggle_logging_for_active_session()

    def action_toggle_script_editor(self) -> None:
        if isinstance(self.screen, UserLoginScreen):
            return
        if isinstance(self.screen, ScriptEditorScreen):
            self.pop_screen()
            return
        self.push_screen(ScriptEditorScreen())

    def action_logout(self) -> None:
        if isinstance(self.screen, UserLoginScreen):
            return

        if isinstance(self.screen, ScriptEditorScreen):
            self.pop_screen()

        self.current_user = None
        self.theme_mode = DEFAULT_THEME_MODE
        self.theme = resolve_textual_theme_name(self.theme_mode)
        set_remembered_username(None)
        self._reset_all_input_history_states()
        self._set_tx_input_value("")
        self._clear_tcp_details_inputs(focus=False)
        self._refresh_user_dependent_ui()
        self._show_login_screen()
        self.notify("Logged out.")

    def action_toggle_theme(self) -> None:
        self.theme_mode = toggle_theme_mode(self.theme_mode)
        self.theme = resolve_textual_theme_name(self.theme_mode)
        self._persist_theme_preference()
        self.notify(f"Theme changed to {self.theme_mode}.")

    def handle_login_action(self, action: str, username: str, remember_me: bool) -> None:
        try:
            normalized = normalize_username(username)
        except ValueError as exc:
            self.notify(str(exc), severity="warning")
            return

        if action == "new-user":
            try:
                profile = create_user_profile(normalized)
            except FileExistsError as exc:
                self.notify(str(exc), severity="warning")
                return
            notice = f"Created user profile for {profile.username}."
        else:
            profile = load_user_profile(normalized)
            if not profile:
                self.notify(
                    f"User '{normalized}' was not found. Use New User to create it.",
                    severity="warning",
                )
                return
            notice = f"Signed in as {profile.username}."

        if isinstance(self.screen, UserLoginScreen):
            self.pop_screen()
            self.call_after_refresh(self._complete_login, profile, remember_me, notice)
            return

        self._complete_login(profile, remember_me, notice)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""

        command_button = self._command_buttons.get(button_id)
        if command_button:
            self._send_user_defined_command(command_button)
            return

        if button_id == "refresh-devices":
            self._refresh_devices_ui()
            return

        if button_id == "connect-btn":
            self._connect_selected_device()
            return

        if button_id == "disconnect-btn":
            self._disconnect_active_device()
            return

        if button_id == "clear-tcp-inputs":
            self._clear_tcp_details_inputs()
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

        if button_id == "close-active-workspace" and self.active_device_id:
            self._close_workspace_for_device(self.active_device_id)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "tx-input":
            self._send_current_input()
            return
        if event.input.id in {"ip-input", "port-input"}:
            self._connect_selected_device()

    def on_input_changed(self, event: Input.Changed) -> None:
        history_id = self._history_id_for_input(event.input.id or "")
        if history_id:
            state = self._input_history_state(history_id)
            if state.ignore_next_change:
                state.ignore_next_change = False
                return
            state.index = None
            state.draft = event.input.value
            return

        if event.input.id != "log-filepath" or not self.current_user:
            return
        self.current_user.log_folder = event.input.value.strip()
        save_user_profile(self.current_user)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "device-list":
            value = event.value
            if event.select.is_blank():
                self.selected_port = None
                if not isinstance(self.screen, UserLoginScreen):
                    self._query_ui("#device-meta", Static).update("Select a port to connect.")
                return

            self.selected_port = str(value)
            if isinstance(self.screen, UserLoginScreen):
                return
            self._update_device_meta(self.selected_port)
            return

        if event.select.id == "command-config-select":
            if self._refreshing_command_configs:
                return
            if event.select.is_blank():
                self._render_command_buttons(None)
                return
            self._render_command_buttons(str(event.value))

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id != "timestamp-checkbox":
            return

        enabled = event.value
        for session in self.sessions.values():
            session.timestamps_enabled = enabled
        for device_id in self.sessions:
            self._render_workspace_session(device_id, preserve_scroll=True)

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

    def _show_startup_login(self) -> None:
        remembered = get_remembered_username()
        if remembered:
            profile = load_user_profile(remembered)
            if profile:
                self._activate_user_profile(profile, remember=True, show_notification=False)
                self.notify(f"Signed in as {profile.username}.")
                return
            set_remembered_username(None)
        self._show_login_screen()

    def _show_login_screen(self) -> None:
        if isinstance(self.screen, UserLoginScreen):
            return
        self.push_screen(UserLoginScreen())

    def _complete_login(self, profile: UserProfile, remember_me: bool, notice: str) -> None:
        self._activate_user_profile(profile, remember=remember_me, show_notification=False)
        self.notify(notice)

    def _activate_user_profile(
        self,
        profile: UserProfile,
        *,
        remember: bool | None,
        show_notification: bool,
    ) -> None:
        self.current_user = profile
        self.theme_mode = normalize_theme_mode(profile.theme)
        self.theme = resolve_textual_theme_name(profile.theme)
        self._reset_all_input_history_states()
        self._refresh_user_dependent_ui()

        if remember is True:
            set_remembered_username(profile.username)
        elif remember is False:
            set_remembered_username(None)

        if show_notification:
            self.notify(f"Signed in as {profile.username}.")

    def _persist_theme_preference(self) -> None:
        if not self.current_user:
            return
        self.current_user.theme = self.theme
        save_user_profile(self.current_user)

    def _refresh_user_dependent_ui(self) -> None:
        summary = self._query_ui("#current-user-summary", Static)
        log_input = self._query_ui("#log-filepath", Input)

        if self.current_user:
            summary.update(f"user: {self.current_user.username}")
            log_input.value = self.current_user.log_folder
        else:
            summary.update("No user.")
            log_input.value = ""

        self._refresh_command_configs()

    def _refresh_command_configs(self) -> None:
        select = self._query_ui("#command-config-select", Select)
        # hint = self._query_ui("#command-config-hint", Static)
        current_value = None if select.is_blank() else str(select.value)

        self._refreshing_command_configs = True
        try:
            self._command_configs = {}
            if not self.current_user:
                select.set_options([])
                select.clear()
                select.disabled = True
                # hint.update("Sign in to load your command config files.")
                self._render_command_buttons(None, placeholder="Sign in to load function buttons.")
                return

            configs = load_command_configs(self.current_user)
            self._command_configs = {config.key: config for config in configs}
            options = [(config.name, config.key) for config in configs]
            select.set_options(options)
            select.disabled = not options

            if not options:
                select.clear()
                # hint.update("No command config files were found for this user.")
                self._render_command_buttons(
                    None,
                    placeholder="No command config files were found for this user.",
                )
                return

            active_key = (
                current_value
                if current_value in self._command_configs
                else options[0][1]
            )
            # hint.update("Select a function button to send its configured message.")
            select.value = active_key
            self._render_command_buttons(active_key)
        finally:
            self._refreshing_command_configs = False

    def _render_command_buttons(self, config_key: str | None, placeholder: str | None = None) -> None:
        scroll = self._query_ui("#command-buttons-scroll", VerticalScroll)
        self._command_buttons.clear()

        for child in list(scroll.children):
            child.remove()

        if not config_key or config_key not in self._command_configs:
            scroll.mount(
                Static(
                    placeholder or "Select a command config to populate the function buttons.",
                    classes="hint",
                )
            )
            return

        config = self._command_configs[config_key]
        widgets = self._build_command_widgets(config.commands)
        if widgets:
            scroll.mount_all(widgets)
            return

        scroll.mount(Static("This command config does not define any commands.", classes="hint"))

    def _build_command_widgets(
        self,
        commands: dict[str, object],
        *,
        path: tuple[str, ...] = (),
        depth: int = 0,
    ) -> list[Widget]:
        widgets: list[Widget] = []
        pending_buttons: list[Widget] = []
        for name, value in commands.items():
            if isinstance(value, dict):
                widgets.extend(self._build_command_rows(pending_buttons))
                pending_buttons = []
                nested_widgets = self._build_command_widgets(value, path=path + (name,), depth=depth + 1)
                if nested_widgets:
                    widgets.append(
                        Vertical(
                            Static(name, classes="command-group-title"),
                            *nested_widgets,
                            classes=f"command-group command-depth-{min(depth + 1, 3)}",
                        )
                    )
                continue
            
            self._command_button_counter += 1
            button_id = f"command-button-{self._command_button_counter}"
            self._command_buttons[button_id] = CommandButtonSpec(
                label=" / ".join(path + (name,)),
                payload=str(value),
            )
            pending_buttons.append(
                Button(
                    name,
                    id=button_id,
                    classes=f"command-button command-depth-{min(depth, 3)}",
                    variant="primary",
                )
            )
        widgets.extend(self._build_command_rows(pending_buttons))
        return widgets

    def _build_command_rows(self, buttons: list[Widget]) -> list[Widget]:
        rows: list[Widget] = []
        for index in range(0, len(buttons), 2):
            rows.append(Horizontal(*buttons[index:index + 2], classes="command-row"))
        return rows

    def _refresh_devices_ui(self) -> None:
        self.discovered_devices = self.device_manager.scan_devices()

        device_list = self._query_ui("#device-list", Select)
        options = [(item.label, item.port) for item in self.discovered_devices]
        device_list.set_options(options)

        if not self.discovered_devices:
            self.selected_port = None
            device_list.clear()
            self._query_ui("#device-meta", Static).update(
                "No serial devices detected. Use the TCP/IP tab to connect by IP."
            )
            self.notify("No serial devices found. TCP/IP connections are still available.")
            return

        known_ports = {device.port for device in self.discovered_devices}
        preferred_port = (
            self.selected_port
            if self.selected_port in known_ports
            else self.discovered_devices[0].port
        )
        self.selected_port = preferred_port
        device_list.value = preferred_port
        self._update_device_meta(preferred_port)
        self.notify(f"Detected {len(self.discovered_devices)} serial device(s).")

    def _set_panel_border_titles(self) -> None:
        self._query_ui("#left-panel", Vertical).border_title = " Connection "
        self._query_ui("#center-panel", Vertical).border_title = " Monitor "
        self._query_ui("#right-panel", Vertical).border_title = " Functions "

    def _update_device_meta(self, selected_port: str) -> None:
        selected = next((device for device in self.discovered_devices if device.port == selected_port), None)
        if not selected:
            self._query_ui("#device-meta", Static).update(selected_port)
            return
        details = selected.label
        if selected.hwid:
            details += f"\n{selected.hwid}"
        self._query_ui("#device-meta", Static).update(details)

    def _active_connection_tab(self) -> str:
        active = self._query_ui("#connection-tabs", TabbedContent).active
        return active if isinstance(active, str) and active else "connection-serial"

    def _build_serial_config_from_inputs(self) -> SerialConfig:
        baud_text = str(self._query_ui("#baud-select", Select).value)
        parity = str(self._query_ui("#parity-select", Select).value)
        stop_bits = str(self._query_ui("#stopbits-select", Select).value)
        data_bits = int(str(self._query_ui("#databits-select", Select).value))

        config = SerialConfig(
            baudrate=int(baud_text),
            parity=parity,
            stopbits=stop_bits,
            databits=data_bits,
            timeout=0.2,
        )
        config.validate()
        return config

    def _build_tcp_config_from_inputs(self) -> TcpConfig:
        host = self._query_ui("#ip-input", Input).value.strip()
        port_text = self._query_ui("#port-input", Input).value.strip()
        if not port_text:
            raise ValueError("TCP port is required.")
        try:
            port = int(port_text)
        except ValueError as exc:
            raise ValueError("TCP port must be a whole number.") from exc

        config = TcpConfig(host=host, port=port, timeout=10.0)
        config.validate()
        return config

    def _upsert_session(
        self,
        *,
        device_id: str,
        transport: DeviceTransport,
        config: SerialConfig | TcpConfig,
    ) -> DeviceSession:
        timestamps_enabled = self._query_ui("#timestamp-checkbox", Checkbox).value
        session = self.sessions.get(device_id)
        if session is None:
            session = DeviceSession(
                device_id=device_id,
                port=device_id,
                transport=transport,
                config=config,
                logger=None,
                timestamps_enabled=timestamps_enabled,
            )
            self.sessions[device_id] = session
            return session

        session.port = device_id
        session.transport = transport
        session.config = config
        session.timestamps_enabled = timestamps_enabled
        return session

    def _connect_selected_device(self) -> None:
        if self._active_connection_tab() == "connection-tcp":
            self._connect_selected_tcp_device()
            return

        self._connect_selected_serial_device()

    def _connect_selected_serial_device(self) -> None:
        if not self.selected_port:
            self.notify("Select a device first.", severity="warning")
            return

        try:
            config = self._build_serial_config_from_inputs()
        except Exception as exc:
            self.notify(f"Invalid serial config: {exc}", severity="error")
            return

        session = self._upsert_session(
            device_id=self.selected_port,
            transport="serial",
            config=config,
        )

        try:
            self.device_manager.connect(self.selected_port, config, self._on_serial_event)
        except Exception as exc:
            self.notify(f"Connection failed: {exc}", severity="error")
            return

        self._ensure_workspace_for_device(self.selected_port)
        self._set_active_workspace(self.selected_port)

        if self._query_ui("#auto-log-checkbox", Checkbox).value:
            self._start_logging_for_session(session, notify=False)

        self._refresh_workspace_state(self.selected_port)
        self.notify(f"Connected to {self.selected_port}")

    def _connect_selected_tcp_device(self) -> None:
        try:
            config = self._build_tcp_config_from_inputs()
        except Exception as exc:
            self.notify(f"Invalid TCP config: {exc}", severity="error")
            return

        device_id = config.device_id
        session = self._upsert_session(device_id=device_id, transport="tcp", config=config)

        try:
            self.device_manager.connect_tcp(config, self._on_serial_event)
        except Exception as exc:
            self.notify(f"Connection failed: {exc}", severity="error")
            return

        self._save_to_input_history(INPUT_HISTORY_TCP_IP, config.host)
        self._save_to_input_history(INPUT_HISTORY_TCP_PORT, str(config.port))
        self._reset_input_history_state(INPUT_HISTORY_TCP_IP)
        self._reset_input_history_state(INPUT_HISTORY_TCP_PORT)

        self._ensure_workspace_for_device(device_id)
        self._set_active_workspace(device_id)

        if self._query_ui("#auto-log-checkbox", Checkbox).value:
            self._start_logging_for_session(session, notify=False)

        self._refresh_workspace_state(device_id)
        self.notify(f"Connected to {device_id}")

    def _clear_tcp_details_inputs(self, *, focus: bool = True) -> None:
        self._reset_input_history_state(INPUT_HISTORY_TCP_IP)
        self._reset_input_history_state(INPUT_HISTORY_TCP_PORT)
        self._set_history_input_value(INPUT_HISTORY_TCP_IP, "")
        self._set_history_input_value(INPUT_HISTORY_TCP_PORT, "")
        if focus:
            self._query_ui("#ip-input", Input).focus()

    def _disconnect_active_device(self) -> None:
        target = self._resolve_disconnect_target()
        if not target:
            self.notify("No device selected.", severity="warning")
            return
        self._disconnect_device(target)

    def _resolve_disconnect_target(self) -> str | None:
        tcp_target: str | None = None
        try:
            tcp_target = self._build_tcp_config_from_inputs().device_id
        except Exception:
            tcp_target = None

        if (
            self._active_connection_tab() == "connection-tcp"
            and tcp_target
            and self._is_device_connected(tcp_target)
        ):
            return tcp_target

        return self.active_device_id or self.selected_port or tcp_target

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

        if pane_id:
            self._workspace_devices_by_pane.pop(pane_id, None)
            self._query_ui("#workspace-tabs", TabbedContent).remove_pane(pane_id)

        if not self._workspace_panes:
            self._ensure_workspace_placeholder()

        self._sync_active_device_from_workspace()
        self.notify(f"Closed workspace tab for {device_id}")

    def _send_current_input(self) -> None:
        device_id = self.active_device_id
        if not device_id:
            self.notify("Connect and select an active device first.", severity="warning")
            return

        raw_input = self._query_ui("#tx-input", Input).value
        is_hex = self._is_tx_hex_mode()
        terminator = str(self._query_ui("#tx-terminate-option", Select).value)

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
        self._save_to_message_history(raw_input)
        self._reset_message_history_state()
        self._set_tx_input_value("")

    def _send_user_defined_command(self, command: CommandButtonSpec) -> None:
        device_id = self.active_device_id
        if not device_id:
            self.notify("Connect and select an active device first.", severity="warning")
            return

        payload = command.payload.encode("utf-8")
        if not payload:
            self.notify(f"Command '{command.label}' is empty.", severity="warning")
            return

        self._send_payload(device_id, payload)
        self._save_to_message_history(command.payload)
        self._invalidate_input_history_cache(INPUT_HISTORY_MESSAGE)

    def _send_payload(self, device_id: str, payload: bytes) -> None:
        conn = self.device_manager.get_connection(device_id)
        if not conn or not conn.is_open:
            self.notify(f"Device {device_id} is not connected.", severity="warning")
            return

        try:
            conn.send(payload)
        except Exception as exc:
            self.notify(f"Send failed: {exc}", severity="error")

    def _input_history_state(self, history_id: str) -> InputHistoryState:
        return self._input_history_states[history_id]

    def _history_id_for_input(self, input_id: str) -> str | None:
        for history_id, selector in _INPUT_HISTORY_SELECTORS.items():
            if selector.removeprefix("#") == input_id:
                return history_id
        return None

    def _input_selector_for_history(self, history_id: str) -> str:
        return _INPUT_HISTORY_SELECTORS[history_id]

    def _set_input_history_draft(self, history_id: str, value: str) -> None:
        self._input_history_state(history_id).draft = value

    def _invalidate_input_history_cache(self, history_id: str) -> None:
        self._input_history_state(history_id).cache = []

    def _save_to_input_history(self, history_id: str, value: str) -> None:
        try:
            history_path = self._get_input_history_path(history_id)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with history_path.open("a", encoding="utf-8") as history_file:
                history_file.write(f"[{timestamp}] {value}\n")
            self._invalidate_input_history_cache(history_id)
        except Exception:
            pass

    def _get_input_history_path(self, history_id: str) -> Path:
        if self.current_user:
            if history_id == INPUT_HISTORY_MESSAGE:
                return get_user_message_history_path(self.current_user.username)
            if history_id == INPUT_HISTORY_TCP_IP:
                return get_user_tcp_ip_history_path(self.current_user.username)
            if history_id == INPUT_HISTORY_TCP_PORT:
                return get_user_tcp_port_history_path(self.current_user.username)
        base = get_data_dir()
        base.mkdir(parents=True, exist_ok=True)
        return base / _INPUT_HISTORY_FALLBACK_FILENAMES[history_id]

    def _reset_input_history_state(self, history_id: str) -> None:
        state = self._input_history_state(history_id)
        state.cache = []
        state.index = None
        state.draft = ""
        state.ignore_next_change = False

    def _reset_all_input_history_states(self) -> None:
        for history_id in _INPUT_HISTORY_SELECTORS:
            self._reset_input_history_state(history_id)

    def _load_input_history(self, history_id: str) -> list[str]:
        state = self._input_history_state(history_id)
        if state.cache:
            return state.cache

        history_path = self._get_input_history_path(history_id)
        if not history_path.exists():
            return []

        values: list[str] = []
        try:
            for line in history_path.read_text(encoding="utf-8").splitlines():
                text = line.strip()
                if not text:
                    continue
                if text.startswith("[") and "] " in text:
                    _, _, text = text.partition("] ")
                values.append(text)
        except Exception:
            return []

        state.cache = values
        return values

    def _set_history_input_value(self, history_id: str, value: str) -> None:
        input_widget = self._query_ui(self._input_selector_for_history(history_id), Input)
        state = self._input_history_state(history_id)
        state.ignore_next_change = True
        input_widget.value = value
        input_widget.cursor_position = len(value)

    def _navigate_input_history(self, history_id: str, direction: int) -> None:
        input_widget = self._query_ui(self._input_selector_for_history(history_id), Input)
        history = self._load_input_history(history_id)
        if not history:
            return

        state = self._input_history_state(history_id)
        if state.index is None:
            if direction > 0:
                return
            state.draft = input_widget.value
            state.index = len(history) - 1
            self._set_history_input_value(history_id, history[state.index])
            return

        next_index = state.index + direction
        if next_index < 0:
            next_index = 0

        if next_index >= len(history):
            state.index = None
            self._set_history_input_value(history_id, state.draft)
            return

        state.index = next_index
        self._set_history_input_value(history_id, history[state.index])

    def _save_to_message_history(self, message: str) -> None:
        self._save_to_input_history(INPUT_HISTORY_MESSAGE, message)

    def _get_message_history_path(self) -> Path:
        return self._get_input_history_path(INPUT_HISTORY_MESSAGE)

    def _reset_message_history_state(self) -> None:
        self._reset_input_history_state(INPUT_HISTORY_MESSAGE)

    def _load_message_history(self) -> list[str]:
        return self._load_input_history(INPUT_HISTORY_MESSAGE)

    def _set_tx_input_value(self, value: str) -> None:
        self._set_history_input_value(INPUT_HISTORY_MESSAGE, value)

    def _navigate_message_history(self, direction: int) -> None:
        self._navigate_input_history(INPUT_HISTORY_MESSAGE, direction)

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
        button = self._query_ui("#toggle-logging", Button)
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

            session.add_parsed_line(f"{prefix}{event.direction} {ascii_result.protocol}")
            for line in ascii_result.lines:
                session.add_parsed_line(f"  {line}")

            if event.direction == "RX":
                self.script_engine.publish_rx(event.device_id, event.payload)
        else:
            info_text = event.text or ""
            session.add_parsed_line(f"{prefix}{event.direction} {info_text}")

        self._append_workspace_event(event.device_id, event)
        self._update_workspace_tab_label(event.device_id)
        self._sync_active_device_from_workspace()

    def _format_prefix(self, session: DeviceSession, timestamp: datetime) -> str:
        if not session.timestamps_enabled:
            return ""
        return f"[{timestamp.strftime('%H:%M:%S.%f')[:-3]}] "

    def _render_raw_event_lines(self, session: DeviceSession, event: SerialEvent) -> list[str]:
        prefix = self._format_prefix(session, event.timestamp)
        if event.direction in {"RX", "TX"} and event.payload is not None:
            formatted = event.payload.decode("utf-8", errors="replace")
            lines = formatted.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            return [f"{prefix}{line}" for line in lines if line or len(lines) == 1]
        return [f"{prefix}{event.direction} {event.text or ''}"]

    def _is_tx_hex_mode(self) -> bool:
        return self._query_ui("#tx-hex-checkbox", Checkbox).value

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

    def _start_logging_for_session(self, session: DeviceSession, notify: bool = True) -> bool:
        if session.logger and session.logger.is_running:
            return True

        try:
            log_path = self._resolve_log_path(session.device_id)
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return False

        session.logger = SessionLogger(log_path)
        session.logger.start()
        if notify:
            self.notify(f"Logging started for {session.device_id}: {session.logger.log_path.name}")
        return True

    def _resolve_log_path(self, device_id: str) -> Path:
        configured_path = self._query_ui("#log-filepath", Input).value.strip()
        if self.current_user:
            self.current_user.log_folder = configured_path
            save_user_profile(self.current_user)

        fallback_dir = (
            get_user_default_logs_dir(self.current_user.username)
            if self.current_user
            else get_logs_dir()
        )
        return resolve_log_destination(
            configured_path,
            device_id=device_id,
            fallback_dir=fallback_dir,
        )

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
        raw_log = RichLog(wrap=True, highlight=True, markup=False, auto_scroll=False)

        pane = TabPane(
            self._workspace_tab_label(device_id),
            Vertical(raw_log, classes="workspace-pane"),
            id=pane_id,
        )

        self._workspace_panes[device_id] = pane_id
        self._workspace_devices_by_pane[pane_id] = device_id
        self._workspace_logs[device_id] = raw_log

        tabs = self._query_ui("#workspace-tabs", TabbedContent)
        tabs.add_pane(pane)
        tabs.active = pane_id
        self.call_after_refresh(self._refresh_workspace_state, device_id)

    def _render_workspace_session(self, device_id: str, preserve_scroll: bool = False) -> None:
        session = self.sessions.get(device_id)
        raw_log = self._workspace_logs.get(device_id)
        if not session or raw_log is None:
            return

        scroll_x = raw_log.scroll_x
        scroll_y = raw_log.scroll_y
        follow_stream = self._should_follow_log(raw_log)

        raw_log.clear()
        if not session.raw_events:
            if self._is_device_connected(device_id):
                raw_log.write(f"Session ready for {device_id}.", scroll_end=follow_stream)
            else:
                raw_log.write(
                    f"Saved session for {device_id}. Reconnect to continue streaming.",
                    scroll_end=follow_stream,
                )
            if preserve_scroll and not follow_stream:
                self.call_after_refresh(
                    raw_log.scroll_to,
                    x=scroll_x,
                    y=min(scroll_y, raw_log.max_scroll_y),
                    animate=False,
                    immediate=True,
                )
            return

        for event in session.raw_events:
            for line in self._render_raw_event_lines(session, event):
                raw_log.write(line, scroll_end=follow_stream)

        if preserve_scroll and not follow_stream:
            self.call_after_refresh(
                raw_log.scroll_to,
                x=scroll_x,
                y=min(scroll_y, raw_log.max_scroll_y),
                animate=False,
                immediate=True,
            )

    def _append_workspace_event(self, device_id: str, event: SerialEvent) -> None:
        session = self.sessions.get(device_id)
        raw_log = self._workspace_logs.get(device_id)
        if not session or raw_log is None:
            return

        follow_stream = self._should_follow_log(raw_log)
        for line in self._render_raw_event_lines(session, event):
            raw_log.write(line, scroll_end=follow_stream)

    def _refresh_workspace_state(self, device_id: str) -> None:
        self._render_workspace_session(device_id, preserve_scroll=True)
        self._update_workspace_tab_label(device_id)
        self._sync_active_device_from_workspace()

    def _update_workspace_tab_label(self, device_id: str) -> None:
        pane_id = self._workspace_panes.get(device_id)
        if not pane_id:
            return
        tab = self._query_ui("#workspace-tabs", TabbedContent).get_tab(pane_id)
        tab.label = self._workspace_tab_label(device_id)

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
            self._query_ui("#workspace-tabs", TabbedContent).active = pane_id
        self.active_device_id = device_id
        self._update_workspace_summary()
        self._refresh_logging_button()

    def _sync_active_device_from_workspace(self) -> None:
        tabs = self._query_ui("#workspace-tabs", TabbedContent)
        self.active_device_id = self._workspace_devices_by_pane.get(tabs.active)
        self._update_workspace_summary()
        self._refresh_logging_button()

    def _update_workspace_summary(self) -> None:
        summary = self._query_ui("#workspace-selection", Static)
        close_button = self._query_ui("#close-active-workspace", Button)
        if not self.active_device_id:
            summary.update("No device workspaces open.")
            close_button.disabled = True
            return

        state = "connected" if self._is_device_connected(self.active_device_id) else "saved"
        summary.update(f"Active workspace: {self.active_device_id} ({state})")
        close_button.disabled = False

    def _remove_workspace_placeholder(self) -> None:
        if not self._workspace_placeholder_visible:
            return
        self._query_ui("#workspace-tabs", TabbedContent).remove_pane(self.WORKSPACE_PLACEHOLDER_ID)
        self._workspace_placeholder_visible = False

    def _ensure_workspace_placeholder(self) -> None:
        if self._workspace_placeholder_visible:
            return

        pane = TabPane(
            "Workspace",
            Vertical(
                Static(
                    " " + self._workspace_placeholder_text(),
                    id="workspace-placeholder",
                    classes="workspace-content workspace-placeholder-text",
                ),
                classes="workspace-pane",
            ),
            id=self.WORKSPACE_PLACEHOLDER_ID,
        )
        tabs = self._query_ui("#workspace-tabs", TabbedContent)
        tabs.add_pane(pane)
        tabs.active = self.WORKSPACE_PLACEHOLDER_ID
        self._workspace_placeholder_visible = True

    def _is_device_connected(self, device_id: str) -> bool:
        return device_id in self.device_manager.connected_ports()

    def _should_follow_log(self, raw_log: RichLog) -> bool:
        return raw_log.max_scroll_y <= 0 or raw_log.scroll_y >= raw_log.max_scroll_y
