from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from importlib.resources import files
from pathlib import Path

from textual.app import App, ComposeResult  # type: ignore
from textual.binding import Binding  # type: ignore
from textual.containers import Horizontal, Vertical, VerticalScroll  # type: ignore
from textual.css.query import NoMatches  # type: ignore
from textual.reactive import reactive  # type: ignore
from textual.screen import ModalScreen, Screen  # type: ignore
from textual.widget import Widget  # type: ignore
from textual.widgets import (  # type: ignore
    Button,
    Checkbox,
    DirectoryTree,
    Footer,
    Input,
    ListItem,
    ListView,
    MarkdownViewer,
    RichLog,
    Rule,
    Select,
    Sparkline,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)

from serialhub import __version__
from serialhub.config import get_data_dir, get_logs_dir
from serialhub.core.device_manager import DeviceManager
from serialhub.core.macro_store import MacroStore
from serialhub.core.models import (
    DeviceInfo,
    DeviceTransport,
    MacroCommandDefinition,
    MacroDefinition,
    SerialConfig,
    SerialEvent,
    TcpConfig,
    build_tcp_device_id,
)
from serialhub.core.session import WORKSPACE_DATASTREAM_WINDOW, DeviceSession
from serialhub.logging.paths import resolve_log_destination
from serialhub.protocols import AsciiBinaryDecoder
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
    delete_command_config_document,
    escape_command_value_for_editor,
    get_remembered_username,
    get_user_command_configs_dir,
    get_user_default_logs_dir,
    get_user_dir,
    get_user_macro_path,
    get_user_macros_dir,
    get_user_message_history_path,
    get_user_tcp_ip_history_path,
    get_user_tcp_port_history_path,
    load_command_config_document,
    load_command_configs,
    load_user_profile,
    normalize_command_config_name,
    normalize_username,
    save_command_config_document,
    save_user_profile,
    set_remembered_username,
    unescape_command_value_from_editor,
    upsert_tcp_favorite,
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

_CONFIG_COMMAND_SEPARATOR = " / "
_NEW_CONFIG_DOCUMENT_KEY = "__new__"
_NEW_MACRO_DOCUMENT_KEY = "__new_macro__"
_NO_STARTUP_COMMAND_CONFIG = "__none__"
_CONFIG_GROUP_NONE = "__none__"
_CONFIG_GROUP_NEW = "__new__"
_WORKSPACE_IDLE_TICK_SECONDS = 0.75
_COMMAND_VALUE_KEY = "VALUE"
_COMMAND_COLOR_KEY = "COLOR"
_DEFAULT_COMMAND_COLOR = "blue"
_COMMAND_COLOR_OPTIONS = [
    ("Blue", "blue"),
    ("White", "off-white"),
    ("Yellow", "warning"),
    ("Red", "error"),
    ("Neutral", "default"),
    ("Success", "success"),
]
_COMMAND_COLOR_VALUES = {value for _label, value in _COMMAND_COLOR_OPTIONS}


def load_ascii_logo() -> str:
    """Load the packaged ASCII logo text."""
    try:
        return files("serialhub").joinpath("assets").joinpath("logo.txt").read_text(encoding="utf-8").strip()
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return ""


def load_app_css() -> str:
    """Load the packaged app stylesheet."""
    try:
        return files("serialhub").joinpath("serialhub.tcss").read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return ""


def load_manual_markdown(filename: str = "connection.md") -> str:
    """Load a packaged SerialHub manual markdown document."""
    try:
        return (
            files("serialhub")
            .joinpath("assets")
            .joinpath("manual")
            .joinpath(filename)
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return f"# SerialHub Manual\n\nThe packaged manual document `{filename}` could not be loaded."


@dataclass(slots=True)
class CommandButtonSpec:
    label: str
    payload: str
    color: str = _DEFAULT_COMMAND_COLOR


@dataclass(slots=True)
class MacroButtonSpec:
    name: str
    label: str
    commands: list[MacroCommandDefinition]
    path: Path | None = None


@dataclass(slots=True)
class InputHistoryState:
    cache: list[str] = field(default_factory=list)
    index: int | None = None
    draft: str = ""
    ignore_next_change: bool = False


@dataclass(slots=True)
class ConfigCommandDraft:
    label: str = ""
    value: str = ""
    group: str = ""
    color: str = _DEFAULT_COMMAND_COLOR
    delay_ms: int = 0


@dataclass(slots=True)
class ConfigEditorDocument:
    name: str = ""
    commands: list[ConfigCommandDraft] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    path: Path | None = None
    kind: str = "config"


@dataclass(slots=True)
class ConfigCommandRowWidgets:
    row: Horizontal
    label_input: Input
    value_input: Input
    group_select: Select
    color_select: Select
    delete_button: Button


@dataclass(slots=True)
class MacroCommandRowWidgets:
    row: Horizontal
    label: Static
    value_input: Input
    delay_input: Input
    delete_button: Button


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


class Led(Static):
    OFF_GLYPH = "○"
    ON_GLYPH = "●"
    active = reactive(False)

    def __init__(self, active: bool = False, *args, **kwargs) -> None:
        super().__init__(self.OFF_GLYPH, *args, **kwargs)
        self.active = active

    @property
    def value(self) -> bool:
        return self.active

    def watch_active(self, active: bool) -> None:
        self.update(self.ON_GLYPH if active else self.OFF_GLYPH)
        self.set_class(active, "-on")
        self.set_class(not active, "-off")

    def on_mount(self) -> None:
        self.watch_active(self.active)


class ConnectionStatusLed(Led):
    pass


class WorkspaceActivityLed(Led):
    pass


# Compatibility aliases for the previous toolbar widget names.
ConnectionStatusSwitch = ConnectionStatusLed
WorkspaceActivityIndicator = WorkspaceActivityLed


class CommandConfigDirectoryTree(DirectoryTree):
    def filter_paths(self, paths: list[Path]) -> list[Path]:
        root = Path(self.path).resolve()
        allowed_dirs = {"configs", "macros"}
        filtered: list[Path] = []
        for path in paths:
            resolved = path.resolve()
            if resolved == root:
                filtered.append(path)
                continue
            try:
                relative = resolved.relative_to(root)
            except ValueError:
                continue
            parts = relative.parts
            if len(parts) == 1 and path.is_dir() and parts[0] in allowed_dirs:
                filtered.append(path)
                continue
            if len(parts) == 2 and parts[0] in allowed_dirs and path.suffix.lower() == ".json":
                filtered.append(path)
        return filtered


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
        border-title-align: center;
        padding: 1 2;
        height: auto;
        
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
            # yield Static("SERIALHUB LOGIN", classes="section-title")
            yield Static(
                "Enter a username to sign in, or create a new local profile from this screen.",
                id="login-message",
            )
            yield Input(placeholder="Username", id="login-username")
            yield Checkbox("Remember Me", id="login-remember")
            with Horizontal(id="login-actions"):
                yield Button("Login", id="login-submit", variant="primary")
                yield Button("New User", id="login-new-user", variant="default")

        yield Footer(id="login-footer")

    def on_mount(self) -> None:
        self.query_one("#login-modal", Vertical).border_title = " SERIALHUB LOGIN "
        self.call_after_refresh(self._focus_username_input)

    def _focus_username_input(self) -> None:
        try:
            self.query_one("#login-username", Input).focus()
        except NoMatches:
            return

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


class UserSettingsScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    UserSettingsScreen {
        align: center middle;
    }

    #settings-modal {
        width: 56;
        max-width: 84;
        background: $surface;
        border: round $primary;
        border-title-align: center;
        padding: 1 2;
        height: auto;
    }

    #settings-message {
        color: $accent;
        margin-bottom: 1;
    }

    #settings-user-row {
        height: auto;
        border: round $secondary;
        padding: 0 1;
        margin-bottom: 1;
    }

    #settings-current-user {
        width: 1fr;
        color: $accent;
    }

    .settings-field-row {
        height: auto;
        margin-bottom: 1;
    }

    .settings-input-label {
        width: 22;
        height: 3;
        content-align: left middle;
        color: $secondary;
    }

    .settings-toggle-label {
        width: auto;
        height: 3;
        content-align: left middle;
        color: $secondary;
        margin-right: 1;
    }

    Switch {
        margin-right: 3;
    }

    #settings-startup-command,
    #settings-theme,
    #settings-log-folder {
        width: 1fr;
    }

    #settings-actions {
        height: auto;
        margin-top: 1;
    }

    #settings-save,
    #settings-close {
        width: 1fr;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "save_settings", "Save"),
        Binding("escape", "close_settings", "Close"),
    ]

    def __init__(
        self,
        *,
        command_configs: Sequence[CommandConfig],
        startup_command_config: str,
        theme_mode: str,
        log_folder: str,
        show_activity_widget: bool,
        show_bottom_status_bar: bool,
        username: str,
    ) -> None:
        super().__init__()
        self._command_configs = tuple(command_configs)
        self._startup_command_config = startup_command_config
        self._theme_mode = normalize_theme_mode(theme_mode)
        self._log_folder = log_folder
        self._show_activity_widget = show_activity_widget
        self._show_bottom_status_bar = show_bottom_status_bar
        self._username = username

    def compose(self) -> ComposeResult:
        startup_options = [("Do not auto-load a command file", _NO_STARTUP_COMMAND_CONFIG)]
        startup_options.extend((config.path.name, config.key) for config in self._command_configs)

        startup_value = (
            self._startup_command_config
            if self._startup_command_config and any(
                config.key == self._startup_command_config for config in self._command_configs
            )
            else _NO_STARTUP_COMMAND_CONFIG
        )

        with Vertical(id="settings-modal"):
            yield Static(
                "Set the defaults used when this user profile signs in.",
                id="settings-message",
            )
            with Horizontal(id="settings-user-row"):
                yield Static(f"user: {self._username}", id="settings-current-user")
            with Horizontal(classes="settings-field-row"):
                yield Static("UI SETTINGS", classes="settings-input-label")
                yield Static("Activity", classes="settings-toggle-label")
                yield Switch(value=self._show_activity_widget, id="settings-activity-widget")
                yield Static("Status Bar", classes="settings-toggle-label")
                yield Switch(value=self._show_bottom_status_bar, id="settings-bottom-status-bar")

            with Horizontal(classes="settings-field-row"):
                yield Static("DEFAULT THEME", classes="settings-input-label")
                yield Select(
                    [("Dark", "dark"), ("Light", "light")],
                    value=self._theme_mode,
                    allow_blank=False,
                    id="settings-theme",
                )
            
            with Horizontal(classes="settings-field-row"):
                yield Static("STARTUP COMMAND FILE", classes="settings-input-label")
                yield Select(
                    startup_options,
                    value=startup_value,
                    allow_blank=False,
                    id="settings-startup-command",
                )
            
            with Horizontal(classes="settings-field-row"):
                yield Static("DEFAULT LOG FOLDER", classes="settings-input-label")
                yield Input(
                    value=self._log_folder,
                    placeholder="Leave blank to use the per-user logs folder",
                    id="settings-log-folder",
                )
            with Horizontal(id="settings-actions"):
                yield Button("Save and Exit", id="settings-save", variant="success")
                yield Button("Close", id="settings-close", variant="default")

        yield Footer(id="settings-footer")

    def on_mount(self) -> None:
        self.query_one("#settings-modal", Vertical).border_title = " USER SETTINGS "
        self.call_after_refresh(self._focus_startup_command)

    def _focus_startup_command(self) -> None:
        try:
            self.query_one("#settings-startup-command", Select).focus()
        except NoMatches:
            return

    def action_save_settings(self) -> None:
        self._save()

    def action_close_settings(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "settings-save":
            self._save()
            return
        if button_id == "settings-close":
            self.dismiss(None)

    def _save(self) -> None:
        startup_value = str(self.query_one("#settings-startup-command", Select).value)
        startup_command_config = "" if startup_value == _NO_STARTUP_COMMAND_CONFIG else startup_value
        theme_mode = normalize_theme_mode(self.query_one("#settings-theme", Select).value)
        log_folder = self.query_one("#settings-log-folder", Input).value
        show_activity_widget = self.query_one("#settings-activity-widget", Switch).value
        show_bottom_status_bar = self.query_one("#settings-bottom-status-bar", Switch).value

        if self.app.save_user_settings(
            startup_command_config=startup_command_config,
            theme_mode=theme_mode,
            log_folder=log_folder,
            show_activity_widget=show_activity_widget,
            show_bottom_status_bar=show_bottom_status_bar,
        ):
            self.dismiss(None)


class DeleteConfigConfirmScreen(ModalScreen[bool]):
    DEFAULT_CSS = """
    DeleteConfigConfirmScreen {
        align: center middle;
    }

    #config-delete-modal {
        width: 56;
        max-width: 80;
        background: $surface;
        border: round $error;
        padding: 1 2;
    }

    #config-delete-message {
        margin: 1 0;
    }

    #config-delete-actions {
        height: auto;
        margin-top: 1;
    }

    #config-delete-yes,
    #config-delete-no {
        width: 1fr;
    }
    """

    BINDINGS = [
        Binding("y", "confirm", show=False),
        Binding("n", "cancel", show=False),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, filename: str) -> None:
        super().__init__()
        self.filename = filename

    def compose(self) -> ComposeResult:
        with Vertical(id="config-delete-modal"):
            yield Static("DELETE CONFIG", classes="section-title")
            yield Static(
                f"Are you sure you want to delete {self.filename}?",
                id="config-delete-message",
            )
            with Horizontal(id="config-delete-actions"):
                yield Button("Yes", id="config-delete-yes", variant="error")
                yield Button("No", id="config-delete-no", variant="primary")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "config-delete-yes":
            self.dismiss(True)
            return
        if button_id == "config-delete-no":
            self.dismiss(False)


class ConfigGroupScreen(ModalScreen[str | None]):
    DEFAULT_CSS = """
    ConfigGroupScreen {
        align: center middle;
    }

    #config-group-modal {
        width: 64;
        max-width: 88;
        height: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }

    #config-group-list {
        height: 8;
        border: solid $secondary;
        margin-bottom: 1;
    }

    #config-group-name {
        margin-bottom: 1;
    }

    #config-group-actions {
        height: auto;
    }

    #config-group-cancel,
    #config-group-save {
        width: 1fr;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(self, groups: Sequence[str]) -> None:
        super().__init__()
        self.groups = list(groups)

    def compose(self) -> ComposeResult:
        with Vertical(id="config-group-modal"):
            yield Static("COMMAND GROUPS", classes="section-title")
            with ListView(id="config-group-list"):
                if not self.groups:
                    yield ListItem(Static("No groups yet.", classes="hint"), disabled=True)
                for group in self.groups:
                    item = ListItem(Static(group))
                    setattr(item, "group_name", group)
                    yield item
            yield Input(placeholder="New group name", id="config-group-name")
            with Horizontal(id="config-group-actions"):
                yield Button("Cancel", id="config-group-cancel", variant="default")
                yield Button("Save & Exit", id="config-group-save", variant="success")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        self._save_group()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "config-group-cancel":
            self.dismiss(None)
            return
        if button_id == "config-group-save":
            self._save_group()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "config-group-name":
            self._save_group()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "config-group-list":
            return
        group = getattr(event.item, "group_name", "")
        if not isinstance(group, str) or not group:
            return
        input_widget = self.query_one("#config-group-name", Input)
        input_widget.value = group
        input_widget.cursor_position = len(group)
        input_widget.focus()

    def _save_group(self) -> None:
        group = self.query_one("#config-group-name", Input).value.strip()
        if not group:
            self.app.notify("Enter a group name before saving.", severity="warning")
            return
        self.dismiss(group)


class ManualScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "close_manual", "Close Manual"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="manual-screen", classes="panel"):
            with TabbedContent(initial="manual-connection-tab", id="manual-tabs"):
                with TabPane("Connection", id="manual-connection-tab"):
                    yield MarkdownViewer(
                        load_manual_markdown("connection.md"),
                        show_table_of_contents=False,
                        open_links=False,
                        id="manual-connection-viewer",
                    )
                with TabPane("Monitor", id="manual-monitor-tab"):
                    yield MarkdownViewer(
                        load_manual_markdown("monitor.md"),
                        show_table_of_contents=False,
                        open_links=False,
                        id="manual-monitor-viewer",
                    )
                with TabPane("Functions", id="manual-functions-tab"):
                    yield MarkdownViewer(
                        load_manual_markdown("functions.md"),
                        show_table_of_contents=False,
                        open_links=False,
                        id="manual-functions-viewer",
                    )

        yield Footer(id="manual-footer")

    def on_mount(self) -> None:
        self.query_one("#manual-screen", Vertical).border_title = " SERIALHUB MANUAL "
        self.query_one("#manual-connection-viewer", MarkdownViewer).focus()

    def action_close_manual(self) -> None:
        self.app.pop_screen()


class ConfigEditorScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "close_config_editor", "Close Editor"),
        Binding("ctrl+s", "save_config_document", "Save File"),
    ]

    def __init__(self, initial_path: Path | None = None) -> None:
        super().__init__()
        self.initial_path = initial_path
        self.selected_path: Path | None = None
        self._active_document_key: str | None = None
        self._document_drafts: dict[str, ConfigEditorDocument] = {}
        self._command_row_ids: list[int] = []
        self._active_command_row_ids: list[int] = []
        self._command_row_widgets: dict[int, ConfigCommandRowWidgets] = {}
        self._command_row_counter = 0
        self._macro_command_row_ids: list[int] = []
        self._active_macro_command_row_ids: list[int] = []
        self._macro_command_row_widgets: dict[int, MacroCommandRowWidgets] = {}
        self._macro_command_row_counter = 0
        self._rendering_form = False
        self._focus_request_counter = 0

    def compose(self) -> ComposeResult:
        app = self.app
        config_root = get_user_dir(app.current_user.username)
        get_user_command_configs_dir(app.current_user.username)
        get_user_macros_dir(app.current_user.username)

        with Horizontal(id="config-editor-layout"):
            with Vertical(id="config-file-browser", classes="panel"):
                with Horizontal(id="config-browser-actions"):
                    yield Button("New Config", id="config-new", variant="success")
                    yield Button("New Macro", id="macro-new", variant="success")
                yield CommandConfigDirectoryTree(config_root, id="config-file-tree")

            with Vertical(id="config-command-editor", classes="panel"):
                with Vertical(id="config-editor-form"):
                    with Horizontal(id="config-name-row"):
                        yield Static("NAME", classes="config-input-label")
                        yield Input(placeholder="config file name", id="config-name-input")
                        yield Button("Add Command", id="config-add-command", variant="primary")
                    with VerticalScroll(id="config-editor-scroll"):
                        yield Vertical(id="config-command-rows")

                with Vertical(id="macro-editor-form"):
                    with Horizontal(id="macro-label-row"):
                        yield Static("LABEL", classes="config-input-label")
                        yield Input(placeholder="macro label", id="macro-label-input")
                        yield Button("Add Command", id="macro-add-command", variant="primary")
                    with VerticalScroll(id="macro-editor-scroll"):
                        yield Vertical(id="macro-command-rows")

                with Horizontal(id="config-editor-actions"):
                    yield Button("Save", id="config-save", variant="success", disabled=True)
                    yield Button("Close", id="config-close", variant="warning")
                    yield Button("Delete", id="config-delete", variant="error")

            with Vertical(id="config-file-preview", classes="panel"):
                with VerticalScroll(id="config-preview-scroll"):
                    yield Static("", id="config-editor-preview", markup=False)

        yield Footer(id="config-editor-footer")

    def on_mount(self) -> None:
        self._set_panel_border_titles()
        tree = self.query_one("#config-file-tree", CommandConfigDirectoryTree)
        if self.initial_path is None:
            tree.focus()
        self._render_empty_editor()
        self.call_after_refresh(self._expand_file_tree_roots)
        if self.initial_path is not None:
            self._display_document_for_path(self.initial_path)

    def _expand_file_tree_roots(self) -> None:
        tree = self.query_one("#config-file-tree", CommandConfigDirectoryTree)
        tree.root.expand()
        for node in tree.root.children:
            path = getattr(node.data, "path", None)
            if isinstance(path, Path) and path.name in {"configs", "macros"}:
                node.expand()

    def _set_panel_border_titles(self) -> None:
        self.query_one("#config-file-browser", Vertical).border_title = " COMMAND FILE BROWSER "
        self.query_one("#config-command-editor", Vertical).border_title = " COMMAND BUILDER "
        self.query_one("#config-file-preview", Vertical).border_title = " FILE EDITOR PREVIEW "

    def action_close_config_editor(self) -> None:
        self.app.pop_screen()
        self.app.call_after_refresh(self.app._refresh_user_command_assets)

    def action_save_config_document(self) -> None:
        self._save_active_document()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "config-new":
            self._open_new_document()
            return
        if button_id == "macro-new":
            self._open_new_macro_document()
            return
        if button_id == "config-delete":
            self._confirm_delete_selected_document()
            return
        if button_id == "config-add-command":
            self._add_command_row()
            return
        if button_id == "macro-add-command":
            self._add_macro_command_row()
            return
        if button_id == "config-save":
            self._save_active_document()
            return
        if button_id == "config-close":
            self.action_close_config_editor()
            return
        if button_id.startswith("config-command-delete-"):
            try:
                row_id = int(button_id.rsplit("-", 1)[-1])
            except ValueError:
                return
            self._delete_command_row(row_id)
            return
        if button_id.startswith("macro-command-delete-"):
            try:
                row_id = int(button_id.rsplit("-", 1)[-1])
            except ValueError:
                return
            self._delete_macro_command_row(row_id)

    def on_tree_node_highlighted(self, event: DirectoryTree.NodeHighlighted) -> None:
        if event.control.id != "config-file-tree":
            return
        path = getattr(event.node.data, "path", None)
        if not isinstance(path, Path) or path.suffix.lower() != ".json":
            if self._active_document_key is None:
                self._render_empty_editor()
            return
        self._display_document_for_path(path)

    def on_input_changed(self, event: Input.Changed) -> None:
        input_id = event.input.id or ""
        if self._rendering_form:
            return
        if (
            input_id == "config-name-input"
            or input_id.startswith("config-command-")
            or input_id == "macro-label-input"
            or input_id.startswith("macro-command-")
        ):
            self._update_active_document_from_form()

    def on_select_changed(self, event: Select.Changed) -> None:
        if self._rendering_form:
            return
        select_id = event.select.id or ""
        if select_id.startswith("config-command-group-"):
            try:
                row_id = int(select_id.rsplit("-", 1)[-1])
            except ValueError:
                return
            if event.value == _CONFIG_GROUP_NEW:
                self._restore_group_select(row_id)
                self._open_group_screen(row_id)
                return
            self._update_active_document_from_form()
            return
        if select_id.startswith("config-command-color-"):
            self._update_active_document_from_form()

    def _open_new_document(self) -> None:
        self._store_active_document_draft()
        document = self._document_drafts.get(
            _NEW_CONFIG_DOCUMENT_KEY,
            ConfigEditorDocument(commands=[ConfigCommandDraft()], kind="config"),
        )
        if not document.commands:
            document.commands = [ConfigCommandDraft()]
        document.path = None
        document.kind = "config"
        self._document_drafts[_NEW_CONFIG_DOCUMENT_KEY] = document
        self.selected_path = None
        self._active_document_key = _NEW_CONFIG_DOCUMENT_KEY
        self._render_document(document, focus_target="#config-name-input")

    def _open_new_macro_document(self) -> None:
        self._store_active_document_draft()
        document = self._document_drafts.get(
            _NEW_MACRO_DOCUMENT_KEY,
            ConfigEditorDocument(
                commands=[ConfigCommandDraft(label="Command 1", delay_ms=0)],
                kind="macro",
            ),
        )
        if not document.commands:
            document.commands = [ConfigCommandDraft(label="Command 1", delay_ms=0)]
        document.path = None
        document.kind = "macro"
        self._document_drafts[_NEW_MACRO_DOCUMENT_KEY] = document
        self.selected_path = None
        self._active_document_key = _NEW_MACRO_DOCUMENT_KEY
        self._render_document(document, focus_target="#macro-label-input")

    def _display_document_for_path(self, path: Path) -> None:
        if path.suffix.lower() != ".json":
            self._render_empty_editor()
            return

        key = self._document_key_for_path(path)
        if self.selected_path == path and self._active_document_key == key:
            return

        self._store_active_document_draft()
        document = self._document_drafts.get(key)
        if document is None:
            try:
                payload = load_command_config_document(path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self.app.notify(f"Unable to load {path.name}: {exc}", severity="error")
                return
            document = self._document_from_payload(path, payload)
            self._document_drafts[key] = document

        self.selected_path = path
        self._active_document_key = key
        self._render_document(document)

    def _confirm_delete_selected_document(self) -> None:
        path = self.selected_path
        if path is None or path.suffix.lower() != ".json":
            self.app.notify("Focus a command file before deleting it.", severity="warning")
            return

        self.app.push_screen(
            DeleteConfigConfirmScreen(path.name),
            callback=lambda confirmed: self._handle_delete_selected_document(path, confirmed),
        )

    def _handle_delete_selected_document(self, path: Path, confirmed: bool | None) -> None:
        if not confirmed:
            return
        if self.app.current_user is None:
            self.app.notify("Sign in before deleting command files.", severity="warning")
            return

        try:
            if self._is_macro_path(path):
                path.unlink()
            else:
                delete_command_config_document(self.app.current_user, path)
        except FileNotFoundError:
            self.app.notify(f"{path.name} was already removed.", severity="warning")
            return
        except OSError as exc:
            self.app.notify(f"Delete failed: {exc}", severity="error")
            return

        deleted_key = self._document_key_for_path(path)
        self._document_drafts.pop(deleted_key, None)
        self.selected_path = None
        if self._active_document_key == deleted_key:
            self._render_empty_editor()
        self.query_one("#config-file-tree", CommandConfigDirectoryTree).reload()
        self.call_after_refresh(self._expand_file_tree_roots)
        self.app._refresh_user_command_assets()
        self.app.notify(f"Deleted {path.name}")

    def _document_key_for_path(self, path: Path) -> str:
        return str(path.resolve())

    def _is_macro_path(self, path: Path | None) -> bool:
        if path is None or self.app.current_user is None:
            return False
        try:
            path.resolve().relative_to(get_user_macros_dir(self.app.current_user.username).resolve())
        except ValueError:
            return False
        return True

    def _document_from_payload(self, path: Path, payload: dict[str, object]) -> ConfigEditorDocument:
        if self._is_macro_path(path) or "commands" in payload or "cmd_delay" in payload:
            macro = MacroDefinition.from_dict(payload)
            entries = [
                ConfigCommandDraft(
                    label=command.label or f"Command {index}",
                    value=escape_command_value_for_editor(command.command),
                    delay_ms=command.delay_ms,
                )
                for index, command in enumerate(macro.commands, start=1)
            ]
            if not entries:
                entries = [ConfigCommandDraft(label="Command 1", delay_ms=0)]
            return ConfigEditorDocument(
                name=macro.label or macro.name or path.stem,
                commands=entries,
                groups=[],
                path=path,
                kind="macro",
            )

        commands = payload.get("COMMANDS", {})
        if not isinstance(commands, dict):
            raise ValueError(f"Command config '{path.name}' must contain an object under COMMANDS.")
        entries = self._flatten_command_entries(commands)
        if not entries:
            entries = [ConfigCommandDraft()]
        return ConfigEditorDocument(
            name=str(payload.get("NAME", path.stem)).strip() or path.stem,
            commands=entries,
            groups=self._groups_from_entries(entries),
            path=path,
            kind="config",
        )

    def _flatten_command_entries(
        self,
        commands: dict[str, object],
        *,
        path: tuple[str, ...] = (),
    ) -> list[ConfigCommandDraft]:
        entries: list[ConfigCommandDraft] = []
        for key, value in commands.items():
            if isinstance(value, dict):
                if self._is_command_definition(value):
                    entries.append(
                        ConfigCommandDraft(
                            label=key,
                            value=escape_command_value_for_editor(str(value.get(_COMMAND_VALUE_KEY, ""))),
                            group=_CONFIG_COMMAND_SEPARATOR.join(path),
                            color=self._normalize_command_color(value.get(_COMMAND_COLOR_KEY)),
                        )
                    )
                    continue
                entries.extend(self._flatten_command_entries(value, path=path + (key,)))
                continue
            entries.append(
                ConfigCommandDraft(
                    label=key,
                    value=escape_command_value_for_editor(str(value)),
                    group=_CONFIG_COMMAND_SEPARATOR.join(path),
                )
            )
        return entries

    def _groups_from_entries(self, entries: Sequence[ConfigCommandDraft]) -> list[str]:
        groups: list[str] = []
        for entry in entries:
            group = entry.group.strip()
            if group and group not in groups:
                groups.append(group)
        return groups

    def _render_empty_editor(self) -> None:
        self._active_document_key = None
        self.selected_path = None
        self._active_command_row_ids = []
        self._active_macro_command_row_ids = []
        self.query_one("#config-save", Button).disabled = True
        self.query_one("#config-editor-preview", Static).update("")
        self._set_editor_input_value(self.query_one("#config-name-input", Input), "")
        self._set_editor_input_value(self.query_one("#macro-label-input", Input), "")
        for row_id, widgets in self._command_row_widgets.items():
            self._set_editor_input_value(widgets.label_input, "")
            self._set_editor_input_value(widgets.value_input, "")
            self._set_group_select_options(widgets.group_select, [], _CONFIG_GROUP_NONE)
            widgets.row.display = False
        for row_id, widgets in self._macro_command_row_widgets.items():
            widgets.label.update("")
            self._set_editor_input_value(widgets.value_input, "")
            self._set_editor_input_value(widgets.delay_input, "")
            widgets.row.display = False
        self.query_one("#config-editor-form", Vertical).display = False
        self.query_one("#macro-editor-form", Vertical).display = False

    def _render_document(self, document: ConfigEditorDocument, *, focus_target: str | None = None) -> None:
        self._rendering_form = True
        if document.kind == "macro":
            self._populate_macro_document_body(document)
        else:
            self._populate_config_document_body(document)
        self._rendering_form = False
        if focus_target:
            self._focus_request_counter += 1
            request_id = self._focus_request_counter
            self._focus_input_if_current(focus_target, request_id)
            self.call_after_refresh(self._focus_input_if_current, focus_target, request_id)
            self.set_timer(0.01, lambda: self._focus_input_if_current(focus_target, request_id))

    def _populate_config_document_body(self, document: ConfigEditorDocument) -> None:
        entries = document.commands or [ConfigCommandDraft()]
        document.groups = self._merged_document_groups(document)
        self._ensure_command_rows(len(entries))
        self._active_command_row_ids = self._command_row_ids[: len(entries)]
        self._active_macro_command_row_ids = []
        self.query_one("#config-editor-form", Vertical).display = True
        self.query_one("#macro-editor-form", Vertical).display = False
        self._set_editor_input_value(self.query_one("#config-name-input", Input), document.name)

        for index, row_id in enumerate(self._command_row_ids):
            widgets = self._command_row_widgets[row_id]
            if index < len(entries):
                entry = entries[index]
                self._set_editor_input_value(widgets.label_input, entry.label)
                self._set_editor_input_value(widgets.value_input, entry.value)
                group = entry.group.strip()
                self._set_group_select_options(
                    widgets.group_select,
                    document.groups,
                    group if group else _CONFIG_GROUP_NONE,
                )
                widgets.color_select.value = self._normalize_command_color(entry.color)
                widgets.row.display = True
                continue
            self._set_editor_input_value(widgets.label_input, "")
            self._set_editor_input_value(widgets.value_input, "")
            self._set_group_select_options(widgets.group_select, document.groups, _CONFIG_GROUP_NONE)
            widgets.color_select.value = _DEFAULT_COMMAND_COLOR
            widgets.row.display = False

        self.query_one("#config-save", Button).disabled = False
        self._refresh_preview(document)

    def _populate_macro_document_body(self, document: ConfigEditorDocument) -> None:
        entries = document.commands or [ConfigCommandDraft()]
        self._ensure_macro_command_rows(len(entries))
        self._active_command_row_ids = []
        self._active_macro_command_row_ids = self._macro_command_row_ids[: len(entries)]
        self.query_one("#config-editor-form", Vertical).display = False
        self.query_one("#macro-editor-form", Vertical).display = True
        self._set_editor_input_value(self.query_one("#macro-label-input", Input), document.name)

        for index, row_id in enumerate(self._macro_command_row_ids):
            widgets = self._macro_command_row_widgets[row_id]
            if index < len(entries):
                entry = entries[index]
                widgets.label.update(f"Command {index + 1}")
                self._set_editor_input_value(widgets.value_input, entry.value)
                self._set_editor_input_value(widgets.delay_input, str(max(0, entry.delay_ms)))
                widgets.row.display = True
                continue
            widgets.label.update("")
            self._set_editor_input_value(widgets.value_input, "")
            self._set_editor_input_value(widgets.delay_input, "")
            widgets.row.display = False

        self.query_one("#config-save", Button).disabled = False
        self._refresh_preview(document)

    def _set_editor_input_value(self, input_widget: Input, value: str) -> None:
        input_widget.value = value
        input_widget.view_position = 0
        input_widget.cursor_position = 0

    def _ensure_command_rows(self, count: int) -> None:
        container = self.query_one("#config-command-rows", Vertical)
        while len(self._command_row_ids) < count:
            self._mount_command_row(container)

    def _ensure_macro_command_rows(self, count: int) -> None:
        container = self.query_one("#macro-command-rows", Vertical)
        while len(self._macro_command_row_ids) < count:
            self._mount_macro_command_row(container)

    def _mount_command_row(self, container: Vertical) -> None:
        self._command_row_counter += 1
        row_id = self._command_row_counter
        label_input = Input(
            placeholder="button label",
            id=f"config-command-label-{row_id}",
            classes="config-command-input config-command-label-input",
        )
        value_input = Input(
            placeholder="string sent over the connection",
            id=f"config-command-value-{row_id}",
            classes="config-command-input config-command-value-input",
        )
        group_select = Select(
            self._group_select_options([]),
            value=_CONFIG_GROUP_NONE,
            allow_blank=False,
            id=f"config-command-group-{row_id}",
            classes="config-command-group-select",
        )
        color_select = Select(
            _COMMAND_COLOR_OPTIONS,
            value=_DEFAULT_COMMAND_COLOR,
            allow_blank=False,
            id=f"config-command-color-{row_id}",
            classes="config-command-color-select",
        )
        delete_button = Button(
            " X ",
            id=f"config-command-delete-{row_id}",
            variant="warning",
            classes="config-command-delete",
        )
        row = Horizontal(
            Static("LABEL", classes="config-input-label"),
            label_input,
            Static("STRING", classes="config-input-label"),
            value_input,
            group_select,
            color_select,
            delete_button,
            id=f"config-command-row-{row_id}",
            classes="config-command-row",
        )
        row.display = False
        self._command_row_ids.append(row_id)
        self._command_row_widgets[row_id] = ConfigCommandRowWidgets(
            row=row,
            label_input=label_input,
            value_input=value_input,
            group_select=group_select,
            color_select=color_select,
            delete_button=delete_button,
        )
        container.mount(row)

    def _mount_macro_command_row(self, container: Vertical) -> None:
        self._macro_command_row_counter += 1
        row_id = self._macro_command_row_counter
        label = Static(
            "",
            id=f"macro-command-label-{row_id}",
            classes="config-input-label macro-command-label",
        )
        value_input = Input(
            placeholder="serial string sent by this macro step",
            id=f"macro-command-value-{row_id}",
            classes="macro-command-input",
        )
        delay_input = Input(
            placeholder="delay ms",
            id=f"macro-command-delay-{row_id}",
            classes="macro-command-delay-input",
        )
        delete_button = Button(
            " X ",
            id=f"macro-command-delete-{row_id}",
            variant="warning",
            classes="config-command-delete",
        )
        row = Horizontal(
            label,
            # Static("STRING", classes="config-input-label"),
            value_input,
            Static("DELAY", classes="config-input-label"),
            delay_input,
            delete_button,
            id=f"macro-command-row-{row_id}",
            classes="macro-command-row",
        )
        row.display = False
        self._macro_command_row_ids.append(row_id)
        self._macro_command_row_widgets[row_id] = MacroCommandRowWidgets(
            row=row,
            label=label,
            value_input=value_input,
            delay_input=delay_input,
            delete_button=delete_button,
        )
        container.mount(row)

    def _group_select_options(self, groups: Sequence[str]) -> list[tuple[str, str]]:
        options = [("None", _CONFIG_GROUP_NONE), ("New...", _CONFIG_GROUP_NEW)]
        options.extend((group, group) for group in groups if group.strip())
        return options

    def _set_group_select_options(self, select: Select, groups: Sequence[str], value: str) -> None:
        options = self._group_select_options(groups)
        try:
            select.set_options(options)
        except NoMatches:
            # Newly-mounted Select widgets compose their overlay on the next refresh.
            select._setup_variables_for_options(options)
        option_values = {option_value for _label, option_value in options}
        select.value = value if value in option_values else _CONFIG_GROUP_NONE

    def _normalize_command_group(self, group: object) -> str:
        value = str(group or "").strip()
        if value in {"", _CONFIG_GROUP_NONE, _CONFIG_GROUP_NEW}:
            return ""
        return value

    def _merge_groups(self, *group_lists: Sequence[str]) -> list[str]:
        groups: list[str] = []
        for group_list in group_lists:
            for group in group_list:
                normalized = self._normalize_command_group(group)
                if normalized and normalized not in groups:
                    groups.append(normalized)
        return groups

    def _merged_document_groups(self, document: ConfigEditorDocument) -> list[str]:
        return self._merge_groups(document.groups, self._groups_from_entries(document.commands))

    def _restore_group_select(self, row_id: int) -> None:
        widgets = self._command_row_widgets.get(row_id)
        if widgets is None:
            return
        previous_group = ""
        document = self._document_drafts.get(self._active_document_key or "")
        if document is not None and row_id in self._active_command_row_ids:
            index = self._active_command_row_ids.index(row_id)
            if index < len(document.commands):
                previous_group = document.commands[index].group
        self._rendering_form = True
        widgets.group_select.value = previous_group.strip() or _CONFIG_GROUP_NONE
        self._rendering_form = False

    def _open_group_screen(self, row_id: int) -> None:
        document = self._document_from_form()
        if document is None:
            return
        groups = self._merged_document_groups(document)
        self.app.push_screen(
            ConfigGroupScreen(groups),
            callback=lambda group: self._handle_group_screen_result(row_id, group),
        )

    def _handle_group_screen_result(self, row_id: int, group: str | None) -> None:
        if not group:
            return
        document = self._document_from_form()
        if document is None or row_id not in self._active_command_row_ids:
            return
        normalized_group = self._normalize_command_group(group)
        if not normalized_group:
            return
        index = self._active_command_row_ids.index(row_id)
        if index >= len(document.commands):
            return
        document.groups = self._merge_groups(document.groups, [normalized_group])
        document.commands[index].group = normalized_group
        if self._active_document_key is not None:
            self._document_drafts[self._active_document_key] = document
        self._render_document(document, focus_target=self._command_focus_selector(index))

    def _add_command_row(self) -> None:
        document = self._document_from_form()
        if document is None:
            self.app.notify("Press New or focus a command file first.", severity="warning")
            return

        document.commands.append(ConfigCommandDraft())
        if self._active_document_key is not None:
            self._document_drafts[self._active_document_key] = document
        next_index = len(document.commands) - 1
        self._ensure_command_rows(len(document.commands))
        focus_target = self._command_value_focus_selector(next_index)
        self._render_document(document, focus_target=focus_target)

    def _add_macro_command_row(self) -> None:
        document = self._document_from_form()
        if document is None:
            self.app.notify("Focus a macro file first.", severity="warning")
            return

        document.commands.append(ConfigCommandDraft())
        if self._active_document_key is not None:
            self._document_drafts[self._active_document_key] = document
        next_index = len(document.commands) - 1
        self._ensure_macro_command_rows(len(document.commands))
        self._render_document(document, focus_target=self._macro_command_focus_selector(next_index))

    def _delete_command_row(self, row_id: int) -> None:
        if row_id not in self._active_command_row_ids:
            return

        document = self._document_from_form()
        if document is None:
            return

        index = self._active_command_row_ids.index(row_id)
        if index >= len(document.commands):
            return

        document.commands.pop(index)
        if self._active_document_key is not None:
            self._document_drafts[self._active_document_key] = document

        if not document.commands:
            self._render_document(document, focus_target="#config-name-input")
            return

        target_index = min(index, len(document.commands) - 1)
        self._render_document(document, focus_target=self._command_focus_selector(target_index))

    def _delete_macro_command_row(self, row_id: int) -> None:
        if row_id not in self._active_macro_command_row_ids:
            return

        document = self._document_from_form()
        if document is None:
            return

        index = self._active_macro_command_row_ids.index(row_id)
        if index >= len(document.commands):
            return

        document.commands.pop(index)
        if self._active_document_key is not None:
            self._document_drafts[self._active_document_key] = document

        if not document.commands:
            self._render_document(document, focus_target="#macro-label-input")
            return

        target_index = min(index, len(document.commands) - 1)
        self._render_document(document, focus_target=self._macro_command_focus_selector(target_index))

    def _focus_input(self, selector: str) -> None:
        try:
            self.query_one(selector, Input).focus()
        except NoMatches:
            return

    def _focus_input_if_current(self, selector: str, request_id: int) -> None:
        if request_id != self._focus_request_counter:
            return
        self._focus_input(selector)

    def _command_focus_selector(self, index: int) -> str:
        if index < 0 or index >= len(self._command_row_ids):
            return "#config-name-input"
        return f"#config-command-label-{self._command_row_ids[index]}"

    def _command_value_focus_selector(self, index: int) -> str:
        if index < 0 or index >= len(self._command_row_ids):
            return "#config-name-input"
        return f"#config-command-value-{self._command_row_ids[index]}"

    def _macro_command_focus_selector(self, index: int) -> str:
        if index < 0 or index >= len(self._macro_command_row_ids):
            return "#macro-label-input"
        return f"#macro-command-value-{self._macro_command_row_ids[index]}"

    def _document_from_form(self) -> ConfigEditorDocument | None:
        kind = "macro" if self._is_macro_path(self.selected_path) else "config"
        if self._active_document_key is not None:
            stored = self._document_drafts.get(self._active_document_key)
            if stored is not None:
                kind = stored.kind

        if kind == "macro":
            return self._macro_document_from_form()

        return self._config_document_from_form()

    def _config_document_from_form(self) -> ConfigEditorDocument | None:
        try:
            name_input = self.query_one("#config-name-input", Input)
        except NoMatches:
            return None

        commands: list[ConfigCommandDraft] = []
        for row_id in self._active_command_row_ids:
            widgets = self._command_row_widgets.get(row_id)
            if widgets is None:
                continue
            commands.append(
                ConfigCommandDraft(
                    label=widgets.label_input.value,
                    value=widgets.value_input.value,
                    group=self._normalize_command_group(widgets.group_select.value),
                    color=self._normalize_command_color(widgets.color_select.value),
                )
            )

        groups = self._groups_from_entries(commands)
        if self._active_document_key is not None:
            stored = self._document_drafts.get(self._active_document_key)
            if stored is not None:
                groups = self._merge_groups(groups, stored.groups)

        return ConfigEditorDocument(
            name=name_input.value,
            commands=commands,
            groups=groups,
            path=self.selected_path,
            kind="config",
        )

    def _macro_document_from_form(self) -> ConfigEditorDocument | None:
        try:
            label_input = self.query_one("#macro-label-input", Input)
        except NoMatches:
            return None

        commands: list[ConfigCommandDraft] = []
        for index, row_id in enumerate(self._active_macro_command_row_ids, start=1):
            widgets = self._macro_command_row_widgets.get(row_id)
            if widgets is None:
                continue
            delay_text = widgets.delay_input.value.strip()
            try:
                delay_ms = max(0, int(float(delay_text or 0)))
            except ValueError:
                delay_ms = -1
            commands.append(
                ConfigCommandDraft(
                    label=f"Command {index}",
                    value=widgets.value_input.value,
                    delay_ms=delay_ms,
                )
            )

        return ConfigEditorDocument(
            name=label_input.value,
            commands=commands,
            groups=[],
            path=self.selected_path,
            kind="macro",
        )

    def _store_active_document_draft(self) -> None:
        if self._active_document_key is None:
            return
        document = self._document_from_form()
        if document is None:
            return
        self._document_drafts[self._active_document_key] = document

    def _update_active_document_from_form(self) -> None:
        if self._active_document_key is None:
            return
        document = self._document_from_form()
        if document is None:
            return
        self._document_drafts[self._active_document_key] = document
        self._refresh_preview(document)

    def _refresh_preview(self, document: ConfigEditorDocument) -> None:
        payload, _warnings = self._build_payload(document, strict=False)
        self.query_one("#config-editor-preview", Static).update(json.dumps(payload, indent=4) + "\n")

    def _build_payload(
        self,
        document: ConfigEditorDocument,
        *,
        strict: bool,
    ) -> tuple[dict[str, object], list[str]]:
        if document.kind == "macro":
            return self._build_macro_payload(document, strict=strict)

        payload: dict[str, object] = {
            "NAME": document.name.strip(),
            "COMMANDS": {},
        }
        commands = payload["COMMANDS"]
        assert isinstance(commands, dict)

        errors: list[str] = []
        for index, entry in enumerate(document.commands, start=1):
            label = entry.label.strip()
            value = unescape_command_value_from_editor(entry.value)

            if not label and not value:
                continue

            if not label or value == "":
                errors.append(f"Command row {index} needs both LABEL and STRING.")
                continue

            group = entry.group.strip()
            parts = [label]
            if group:
                parts = [part.strip() for part in group.split("/") if part.strip()] + parts

            joined_label = _CONFIG_COMMAND_SEPARATOR.join(parts)
            try:
                self._insert_command_value(commands, parts, value, joined_label, entry.color)
            except ValueError as exc:
                errors.append(f"Command row {index}: {exc}")

        if strict and not document.name.strip():
            errors.insert(0, "Enter a NAME before saving.")

        return payload, errors

    def _build_macro_payload(
        self,
        document: ConfigEditorDocument,
        *,
        strict: bool,
    ) -> tuple[dict[str, object], list[str]]:
        label = document.name.strip()
        try:
            name = normalize_command_config_name(label) if label else ""
        except ValueError as exc:
            name = ""
            errors = [str(exc)]
        else:
            errors = []
        commands: list[dict[str, object]] = []

        for index, entry in enumerate(document.commands, start=1):
            value = unescape_command_value_from_editor(entry.value)
            if not entry.label.strip() and not value:
                continue
            command_label = entry.label.strip() or f"Command {index}"
            if value == "":
                errors.append(f"Command row {index} needs a STRING.")
                continue
            if entry.delay_ms < 0:
                errors.append(f"Command row {index} needs a DELAY greater than or equal to zero.")
                continue
            commands.append(
                {
                    "label": command_label,
                    "command": value,
                    "delay_ms": entry.delay_ms,
                }
            )

        if strict and not label:
            errors.insert(0, "Enter a NAME before saving.")
        if strict and not commands:
            errors.append("Add at least one macro command before saving.")

        return (
            {
                "name": name,
                "label": label,
                "commands": commands,
            },
            errors,
        )

    def _insert_command_value(
        self,
        commands: dict[str, object],
        parts: list[str],
        value: str,
        display_path: str,
        color: str,
    ) -> None:
        current = commands
        for part in parts[:-1]:
            existing = current.get(part)
            if existing is None:
                current[part] = {}
                existing = current[part]
            if not isinstance(existing, dict):
                raise ValueError(f"'{part}' is already a command, so '{display_path}' cannot be nested.")
            current = existing

        leaf = parts[-1]
        existing_leaf = current.get(leaf)
        if isinstance(existing_leaf, dict):
            raise ValueError(f"'{display_path}' already exists as a command group.")
        if existing_leaf is not None:
            raise ValueError(f"Duplicate LABEL '{display_path}'.")
        normalized_color = self._normalize_command_color(color)
        current[leaf] = (
            value
            if normalized_color == _DEFAULT_COMMAND_COLOR
            else {
                _COMMAND_VALUE_KEY: value,
                _COMMAND_COLOR_KEY: normalized_color,
            }
        )

    def _is_command_definition(self, value: dict[str, object]) -> bool:
        return _COMMAND_VALUE_KEY in value

    def _normalize_command_color(self, color: object) -> str:
        value = str(color or _DEFAULT_COMMAND_COLOR).strip()
        if value == "primary":
            return "blue"
        return value if value in _COMMAND_COLOR_VALUES else _DEFAULT_COMMAND_COLOR

    def _save_active_document(self) -> None:
        if self.app.current_user is None:
            self.app.notify("Sign in before saving command files.", severity="warning")
            return

        document = self._document_from_form()
        if document is None:
            self.app.notify("Press New or focus a command file first.", severity="warning")
            return

        payload, errors = self._build_payload(document, strict=True)
        if errors:
            self.app.notify(errors[0], severity="error")
            return

        previous_path = self.selected_path
        try:
            if document.kind == "macro":
                macro_name = str(payload.get("name", "")).strip()
                saved_path = get_user_macro_path(self.app.current_user.username, macro_name)
                if previous_path is not None and previous_path != saved_path and saved_path.exists():
                    raise FileExistsError(f"Macro '{saved_path.name}' already exists.")
                MacroStore.save_macro(saved_path, MacroDefinition.from_dict(payload))
                if previous_path is not None and previous_path != saved_path and previous_path.exists():
                    previous_path.unlink()
            else:
                saved_path = save_command_config_document(
                    self.app.current_user,
                    document.name,
                    payload,
                    previous_path=previous_path,
                )
        except FileExistsError as exc:
            self.app.notify(str(exc), severity="error")
            return
        except OSError as exc:
            self.app.notify(f"Save failed: {exc}", severity="error")
            return

        saved_document = self._document_from_payload(saved_path, payload)
        new_key = self._document_key_for_path(saved_path)
        if self._active_document_key and self._active_document_key != new_key:
            self._document_drafts.pop(self._active_document_key, None)
        self._document_drafts[new_key] = saved_document
        self.selected_path = saved_path
        self._active_document_key = new_key
        self._render_document(saved_document)
        self.query_one("#config-file-tree", CommandConfigDirectoryTree).reload()
        self.call_after_refresh(self._expand_file_tree_roots)
        self.app._sync_command_config_cache()
        self.app._refresh_macros()
        self.app.notify(f"Saved {saved_path.name}")


class SerialHubApp(App[None]):
    CSS = load_app_css()
    ENABLE_COMMAND_PALETTE = False
    TITLE = "SerialHub"
    SUB_TITLE = f"v{__version__}"
    WORKSPACE_PLACEHOLDER_ID = "workspace-empty"
    BINDINGS = [
        Binding("ctrl+r", "refresh_devices", "Refresh Devices"),
        Binding("ctrl+m", "focus_message_input", "Message"),
        Binding("ctrl+d", "toggle_connect_disconnect", "Dis/Connect"),
        Binding("ctrl+l", "toggle_logging_shortcut", "Save Log"),
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

        self.discovered_devices: list[DeviceInfo] = []
        self.selected_port: str | None = None
        self.active_device_id: str | None = None

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
        self._macros: dict[str, MacroButtonSpec] = {}
        self._macro_run_buttons: dict[str, str] = {}
        self._macro_edit_buttons: dict[str, str] = {}
        self._macro_button_counter = 0
        self._refreshing_command_configs = False
        self._refreshing_tcp_favorites = False
        self._tcp_favorites: dict[str, tuple[str, int, str]] = {}
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

    def _log_path_placeholder(self) -> str:
        if self.current_user:
            return str(get_user_default_logs_dir(self.current_user.username))
        return str(get_logs_dir())

    def _app_version_text(self) -> str:
        return f"v{__version__}"

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
                                ("Parity: None (N)", "N"),
                                ("Parity: Even (E)", "E"),
                                ("Parity: Odd (O)", "O"),
                                ("Parity: Mark (M)", "M"),
                                ("Parity: Space (S)", "S"),
                            ],
                            id="parity-select",
                            value="N",
                            allow_blank=False,
                        )
                        yield Select(
                            [("Stop Bits: 1", "1"), ("Stop Bits: 1.5", "1.5"), ("Stop Bits: 2", "2")],
                            id="stopbits-select",
                            value="1",
                            allow_blank=False,
                        )
                        yield Select(
                            [
                                ("Data Bits: 8", "8"),
                                ("Data Bits: 7", "7"),
                                ("Data Bits: 6", "6"),
                                ("Data Bits: 5", "5"),
                            ],
                            id="databits-select",
                            value="8",
                            allow_blank=False,
                        )
                        yield Static("Select a port to connect.", id="device-meta", classes="hint")

                    with TabPane("TCP/IP", id="connection-tcp"):
                        yield Static(
                            "Enter a device IP address and TCP port to open a session.",
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
                        yield Input(
                            placeholder="Connection Label",
                            id="tcp-label-input",
                        )
                        yield Button("Clear", id="clear-tcp-inputs")
                        yield Button("Add to Favorites", id="tcp-favorites-btn")
                        yield Select(
                            [],
                            id="tcp-favorites-list",
                            prompt="Select saved Connections",
                            allow_blank=True,
                        )


                with Horizontal(id="left-panel-actions", classes="stack-row"):
                    yield Button("Connect", id="connect-btn", variant="success")
                    yield Button("Disconnect", id="disconnect-btn", variant="warning")

            with Vertical(id="center-panel", classes="panel"):
                with Horizontal(id="workspace-toolbar"):
                    with Vertical(id="workspace-connection-widget", classes="workspace-toolbar-widget"):
                        with Horizontal(id="connection-status-row"):
                            yield Static("CONNECTION", id="connection-status-title")
                            yield ConnectionStatusLed(id="connection-status-led")
                        yield Rule(line_style="heavy", id="connection-status-rule")
                        with Horizontal(id="workspace-status-indicators"):
                            yield Static("RX", id="workspace-rx-label", classes="workspace-indicator-label")
                            yield WorkspaceActivityLed(
                                id="workspace-rx-activity",
                                classes="workspace-activity workspace-activity-rx",
                            )
                            yield Static("TX", id="workspace-tx-label", classes="workspace-indicator-label")
                            yield WorkspaceActivityLed(
                                id="workspace-tx-activity",
                                classes="workspace-activity workspace-activity-tx",
                            )

                    with Vertical(id="workspace-data-widget", classes="workspace-toolbar-widget"):
                        yield Sparkline(
                            [0.0] * WORKSPACE_DATASTREAM_WINDOW,
                            id="workspace-rx-sparkline",
                            classes="workspace-direction-sparkline -idle",
                        )
                        yield Sparkline(
                            [0.0] * WORKSPACE_DATASTREAM_WINDOW,
                            id="workspace-tx-sparkline",
                            classes="workspace-direction-sparkline -idle",
                        )

                    with Horizontal(id="workspace-toolbar-buttons"):
                        yield Button(
                            "Clear",
                            id="clear-console-btn",
                            variant="warning",
                            disabled=True,
                            # compact=True,
                        )
                        yield Button(
                            "Close",
                            id="close-active-workspace",
                            variant="error",
                            disabled=True,
                            # compact=True,
                            # flat=True,
                        )

                with TabbedContent(initial=self.WORKSPACE_PLACEHOLDER_ID, id="workspace-tabs"):
                    with TabPane("Workspace", id=self.WORKSPACE_PLACEHOLDER_ID):
                        yield Vertical(
                            Static(
                                self._workspace_placeholder_text(),
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
                    yield Checkbox("Time", value=True, id="timestamp-checkbox")
                    yield Checkbox("<</>>", value=True, id="chevron-checkbox")
                    yield Input(placeholder=self._log_path_placeholder(), id="log-filepath")
                    yield Button("Save Log", id="toggle-logging")

                    yield Button("Copy Workspace", id="copy-workspace-btn", variant="default", disabled=True)

                with Horizontal(id="workspace-status"):
                    yield Static("No device workspaces open.", id="workspace-selection", classes="hint")
                    yield Static("No user.", id="current-user-summary", classes="hint")

            with Vertical(id="right-panel", classes="panel"):
                with Horizontal(id="right-panel-header"):
                    # yield Static("", id="right-panel-spacer")
                    yield Button("Editor", id="config-editor-btn", variant="warning")
                    yield Button("Manual", id="manual-btn", variant="primary")
                    yield Button("Settings", id="user-settings-btn", variant="default")
                
                with TabbedContent(initial="command-functions-tab", id="command-panel-tabs"):
                    with TabPane("Functions", id="command-functions-tab"):
                        yield Select(
                            [],
                            id="command-config-select",
                            prompt="Select command config",
                            allow_blank=True,
                        )
                        yield VerticalScroll(id="command-buttons-scroll")
                    with TabPane("History", id="command-history-tab"):
                        yield ListView(id="command-history-list", classes="command-history-list")
                    with TabPane("Macros", id="command-macros-tab"):
                        yield VerticalScroll(id="macro-list-scroll")

        with Horizontal(id="footer-row"):
            yield Footer(id="app-footer")
            yield Static(self._app_version_text(), id="app-version")

    def on_mount(self) -> None:
        self._set_panel_border_titles()
        self._refresh_devices_ui()
        self._sync_active_device_from_workspace()
        self._refresh_logging_button()
        self._refresh_user_dependent_ui()
        self.set_interval(_WORKSPACE_IDLE_TICK_SECONDS, self._advance_workspace_datastreams)

        if self.current_user:
            self._activate_user_profile(self.current_user, remember=None, show_notification=False)
            return

        if self.require_login:
            self._show_startup_login()

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
        self._save_active_workspace_log()

    def action_open_config_editor(self) -> None:
        if isinstance(self.screen, UserLoginScreen):
            return
        if not self.current_user:
            self.notify("Sign in to edit command files.", severity="warning")
            return
        if isinstance(self.screen, ConfigEditorScreen):
            return
        self.push_screen(ConfigEditorScreen())

    def action_open_manual(self) -> None:
        if isinstance(self.screen, UserLoginScreen):
            return
        if isinstance(self.screen, ManualScreen):
            return
        self.push_screen(ManualScreen())

    def action_open_user_settings(self) -> None:
        if isinstance(self.screen, UserLoginScreen):
            return
        if not self.current_user:
            self.notify("Sign in to edit user settings.", severity="warning")
            return
        if isinstance(self.screen, UserSettingsScreen):
            return
        self._sync_command_config_cache()
        self.push_screen(
            UserSettingsScreen(
                command_configs=list(self._command_configs.values()),
                startup_command_config=self.current_user.startup_command_config,
                theme_mode=self.theme_mode,
                log_folder=self.current_user.log_folder,
                show_activity_widget=self.current_user.show_activity_widget,
                show_bottom_status_bar=self.current_user.show_bottom_status_bar,
                username=self.current_user.username,
            )
        )

    def action_logout(self) -> None:
        if isinstance(self.screen, UserLoginScreen):
            return

        if isinstance(self.screen, ConfigEditorScreen):
            self.pop_screen()
        if isinstance(self.screen, ManualScreen):
            self.pop_screen()
        if isinstance(self.screen, UserSettingsScreen):
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

        macro_key = self._macro_run_buttons.get(button_id)
        if macro_key:
            self._run_macro(macro_key)
            return

        macro_key = self._macro_edit_buttons.get(button_id)
        if macro_key:
            self._edit_macro(macro_key)
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

        if button_id == "tcp-favorites-btn":
            self._save_tcp_favorite_from_inputs()
            return

        if button_id == "send-btn":
            self._send_current_input()
            return

        if button_id == "toggle-logging":
            self._save_active_workspace_log()
            return

        if button_id == "copy-workspace-btn":
            self._copy_active_workspace_to_clipboard()
            return

        if button_id == "config-editor-btn":
            self.action_open_config_editor()
            return

        if button_id == "manual-btn":
            self.action_open_manual()
            return

        if button_id == "user-settings-btn":
            self.action_open_user_settings()
            return

        if button_id == "clear-console-btn":
            self._clear_active_workspace_console()
            return

        if button_id == "close-active-workspace" and self.active_device_id:
            self._close_workspace_for_device(self.active_device_id)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "tx-input":
            self._send_current_input()
            return
        if event.input.id in {"ip-input", "port-input", "tcp-label-input"}:
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
            return

        if event.select.id == "tcp-favorites-list":
            if self._refreshing_tcp_favorites or event.select.is_blank():
                return
            favorite = self._tcp_favorites.get(str(event.value))
            if favorite is None:
                return
            host, port, label = favorite
            self._set_history_input_value(INPUT_HISTORY_TCP_IP, host)
            self._set_history_input_value(INPUT_HISTORY_TCP_PORT, str(port))
            label_input = self._query_ui("#tcp-label-input", Input)
            label_input.value = label
            label_input.cursor_position = len(label)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id not in {"timestamp-checkbox", "chevron-checkbox"}:
            return

        enabled = event.value
        if event.checkbox.id == "timestamp-checkbox":
            for session in self.sessions.values():
                session.timestamps_enabled = enabled
        else:
            for session in self.sessions.values():
                session.chevrons_enabled = enabled
        for device_id in self.sessions:
            self._render_workspace_session(device_id, preserve_scroll=True)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "command-history-list":
            return
        value = getattr(event.item, "command_value", "")
        if not isinstance(value, str) or not value:
            return
        self._set_tx_input_value(value)
        self._query_ui("#tx-input", Input).focus()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.tabbed_content.id == "workspace-tabs":
            self._sync_active_device_from_workspace()

    def on_unmount(self) -> None:
        self._shutting_down = True
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

    def save_user_settings(
        self,
        *,
        startup_command_config: str,
        theme_mode: str,
        log_folder: str,
        show_activity_widget: bool,
        show_bottom_status_bar: bool,
    ) -> bool:
        if not self.current_user:
            return False

        self._sync_command_config_cache()
        normalized_startup = startup_command_config.strip()
        if normalized_startup and normalized_startup not in self._command_configs:
            self.notify("Select a valid startup command file.", severity="warning")
            return False

        try:
            normalized_log_folder = self._normalize_log_destination_setting(log_folder)
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return False

        self.theme_mode = normalize_theme_mode(theme_mode)
        self.theme = resolve_textual_theme_name(self.theme_mode)
        self.current_user.theme = self.theme
        self.current_user.log_folder = normalized_log_folder
        self.current_user.show_activity_widget = show_activity_widget
        self.current_user.show_bottom_status_bar = show_bottom_status_bar
        self.current_user.startup_command_config = normalized_startup
        save_user_profile(self.current_user)

        self._refresh_user_dependent_ui()
        if normalized_startup:
            self._refresh_command_configs(selected_key=normalized_startup)
        self.notify("User settings saved.")
        return True

    def _refresh_user_dependent_ui(self) -> None:
        summary = self._query_ui("#current-user-summary", Static)
        log_input = self._query_ui("#log-filepath", Input)
        config_button = self._query_ui("#config-editor-btn", Button)
        settings_button = self._query_ui("#user-settings-btn", Button)
        log_input.placeholder = self._log_path_placeholder()

        if self.current_user:
            summary.update(f"user: {self.current_user.username}")
            log_input.value = self.current_user.log_folder
            config_button.disabled = False
            settings_button.disabled = False
        else:
            summary.update("No user.")
            log_input.value = ""
            config_button.disabled = True
            settings_button.disabled = True

        self._apply_ui_visibility_preferences()
        self._refresh_tcp_favorites()
        self._refresh_user_command_assets()

    def _refresh_user_command_assets(self) -> None:
        self._refresh_command_configs()
        self._refresh_command_history_list()
        self._refresh_macros()

    def _show_activity_widget_enabled(self) -> bool:
        if not self.current_user:
            return True
        return self.current_user.show_activity_widget

    def _show_bottom_status_bar_enabled(self) -> bool:
        if not self.current_user:
            return True
        return self.current_user.show_bottom_status_bar

    def _apply_ui_visibility_preferences(self) -> None:
        self._query_ui("#workspace-data-widget", Vertical).display = self._show_activity_widget_enabled()
        self._query_ui("#workspace-status", Horizontal).display = self._show_bottom_status_bar_enabled()

    def _refresh_tcp_favorites(self, *, selected_key: str | None = None) -> None:
        select = self._query_ui("#tcp-favorites-list", Select)

        self._refreshing_tcp_favorites = True
        try:
            if not self.current_user:
                self._tcp_favorites = {}
                select.set_options([])
                select.clear()
                select.disabled = True
                return

            options: list[tuple[str, str]] = []
            mapping: dict[str, tuple[str, int, str]] = {}
            for favorite in self.current_user.tcp_favorites:
                key = build_tcp_device_id(favorite.host, favorite.port)
                label = favorite.label.strip()
                display = f"{label} ({key})" if label else key
                options.append((display, key))
                mapping[key] = (favorite.host, favorite.port, label)

            self._tcp_favorites = mapping
            select.set_options(options)
            select.disabled = not options

            if not options:
                select.clear()
                return

            current_value = None if select.is_blank() else str(select.value)
            active_key = (
                selected_key
                if selected_key in mapping
                else current_value
                if current_value in mapping
                else None
            )

            if active_key is None:
                select.clear()
                return

            select.value = active_key
        finally:
            self._refreshing_tcp_favorites = False

    def _refresh_command_configs(self, *, selected_key: str | None = None) -> None:
        select = self._query_ui("#command-config-select", Select)
        # hint = self._query_ui("#command-config-hint", Static)
        current_value = None if select.is_blank() else str(select.value)

        self._refreshing_command_configs = True
        try:
            if not self.current_user:
                self._command_configs = {}
                select.set_options([])
                select.clear()
                select.disabled = True
                # hint.update("Sign in to load your command config files.")
                self._render_command_buttons(None, placeholder="Sign in to load function buttons.")
                return

            self._sync_command_config_cache()
            options = [(config.name, config.key) for config in self._command_configs.values()]
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

            active_key = None
            if selected_key and selected_key in self._command_configs:
                active_key = selected_key
            elif current_value in self._command_configs:
                active_key = current_value
            elif self.current_user.startup_command_config in self._command_configs:
                active_key = self.current_user.startup_command_config

            if active_key is not None:
                select.value = active_key
                self._render_command_buttons(active_key)
                return

            select.clear()
            self._render_command_buttons(None)
        finally:
            self._refreshing_command_configs = False

    def _sync_command_config_cache(self) -> None:
        if not self.current_user:
            self._command_configs = {}
            return
        configs = load_command_configs(self.current_user)
        self._command_configs = {config.key: config for config in configs}

    def _refresh_macros(self) -> None:
        try:
            scroll = self._query_ui("#macro-list-scroll", VerticalScroll)
        except NoMatches:
            return

        self._macros.clear()
        self._macro_run_buttons.clear()
        self._macro_edit_buttons.clear()
        for child in list(scroll.children):
            child.remove()

        if not self.current_user:
            scroll.mount(Static("Sign in to load macros.", classes="hint"))
            return

        macros_dir = get_user_macros_dir(self.current_user.username)
        macros = MacroStore(macros_dir).load()
        if not macros:
            scroll.mount(Static("No macro files were found for this user.", classes="hint"))
            return

        rows: list[Widget] = []
        for macro in macros:
            if macro.path is None:
                continue
            self._macro_button_counter += 1
            macro_key = str(macro.path.resolve())
            run_id = f"macro-run-{self._macro_button_counter}"
            edit_id = f"macro-edit-{self._macro_button_counter}"
            self._macros[macro_key] = MacroButtonSpec(
                name=macro.name,
                label=macro.label or macro.name,
                commands=macro.commands,
                path=macro.path,
            )
            self._macro_run_buttons[run_id] = macro_key
            self._macro_edit_buttons[edit_id] = macro_key
            rows.append(
                Horizontal(
                    Vertical(
                        Static(macro.label or macro.name, classes="macro-label"),
                        Static(self._macro_command_summary(macro.commands), classes="macro-command-summary"),
                        classes="macro-summary",
                    ),
                    Button("Run", id=run_id, variant="success", classes="macro-action"),
                    Button("Edit", id=edit_id, variant="warning", classes="macro-action"),
                    classes="macro-row",
                )
            )

        if rows:
            scroll.mount_all(rows)
            return
        scroll.mount(Static("No valid macro files were found for this user.", classes="hint"))

    def _macro_command_summary(self, commands: Sequence[MacroCommandDefinition]) -> str:
        values = [
            command.command.replace("\r", "\\r").replace("\n", "\\n")
            for command in commands
            if command.command
        ]
        if not values:
            return "No commands"
        return "\n".join(values)

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

    def _refresh_command_history_list(self) -> None:
        try:
            history_list = self._query_ui("#command-history-list", ListView)
        except NoMatches:
            return

        for child in list(history_list.children):
            child.remove()
        history = list(reversed(self._load_message_history()))
        if not history:
            history_list.mount(ListItem(Static("No command history yet.", classes="hint")))
            history_list.disabled = True
            return

        history_list.disabled = False
        seen: set[str] = set()
        for value in history:
            if value in seen:
                continue
            seen.add(value)
            item = ListItem(Static(value, classes="command-history-item"))
            setattr(item, "command_value", value)
            history_list.mount(item)

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
                if self._is_command_definition(value):
                    payload = str(value.get(_COMMAND_VALUE_KEY, ""))
                    color = self._normalize_command_color(value.get(_COMMAND_COLOR_KEY))
                    pending_buttons.append(self._make_command_button(name, path, payload, color, depth))
                    continue
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
            
            pending_buttons.append(
                self._make_command_button(name, path, str(value), _DEFAULT_COMMAND_COLOR, depth)
            )
        widgets.extend(self._build_command_rows(pending_buttons))
        return widgets

    def _make_command_button(
        self,
        name: str,
        path: tuple[str, ...],
        payload: str,
        color: str,
        depth: int,
    ) -> Button:
        self._command_button_counter += 1
        button_id = f"command-button-{self._command_button_counter}"
        normalized_color = self._normalize_command_color(color)
        self._command_buttons[button_id] = CommandButtonSpec(
            label=" / ".join(path + (name,)),
            payload=payload,
            color=normalized_color,
        )
        variant = (
            normalized_color
            if normalized_color in {"default", "warning", "error", "success"}
            else "default"
        )
        color_class = f"command-color-{normalized_color}"
        return Button(
            name,
            id=button_id,
            classes=f"command-button command-depth-{min(depth, 3)} {color_class}",
            variant=variant,
        )

    def _is_command_definition(self, value: dict[str, object]) -> bool:
        return _COMMAND_VALUE_KEY in value

    def _normalize_command_color(self, color: object) -> str:
        value = str(color or _DEFAULT_COMMAND_COLOR).strip()
        if value == "primary":
            return "blue"
        return value if value in _COMMAND_COLOR_VALUES else _DEFAULT_COMMAND_COLOR

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
                "No serial devices detected."
            )
            self.notify("No serial devices found.")
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
        self._query_ui("#left-panel", Vertical).border_title = " CONNECTION "
        self._query_ui("#center-panel", Vertical).border_title = " MONITOR "
        self._query_ui("#right-panel", Vertical).border_title = " FUNCTIONS "
        self._query_ui("#workspace-data-widget", Vertical).border_title = " ACTIVITY "

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

    def _tcp_label_from_inputs(self) -> str:
        return self._query_ui("#tcp-label-input", Input).value.strip()

    def _upsert_session(
        self,
        *,
        device_id: str,
        transport: DeviceTransport,
        config: SerialConfig | TcpConfig,
        label: str = "",
    ) -> DeviceSession:
        timestamps_enabled = self._query_ui("#timestamp-checkbox", Checkbox).value
        chevrons_enabled = self._query_ui("#chevron-checkbox", Checkbox).value
        session = self.sessions.get(device_id)
        if session is None:
            session = DeviceSession(
                device_id=device_id,
                port=device_id,
                transport=transport,
                config=config,
                logger=None,
                timestamps_enabled=timestamps_enabled,
                chevrons_enabled=chevrons_enabled,
                label=label,
            )
            self.sessions[device_id] = session
            return session

        session.port = device_id
        session.transport = transport
        session.config = config
        session.timestamps_enabled = timestamps_enabled
        session.chevrons_enabled = chevrons_enabled
        session.label = label
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

        self._upsert_session(
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

        self._refresh_workspace_state(self.selected_port)
        self.notify(f"Connected to {self.selected_port}")

    def _connect_selected_tcp_device(self) -> None:
        try:
            config = self._build_tcp_config_from_inputs()
        except Exception as exc:
            self.notify(f"Invalid TCP config: {exc}", severity="error")
            return

        device_id = config.device_id
        label = self._tcp_label_from_inputs()
        self._upsert_session(device_id=device_id, transport="tcp", config=config, label=label)

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

        self._refresh_workspace_state(device_id)
        self.notify(f"Connected to {device_id}")

    def _clear_tcp_details_inputs(self, *, focus: bool = True) -> None:
        self._reset_input_history_state(INPUT_HISTORY_TCP_IP)
        self._reset_input_history_state(INPUT_HISTORY_TCP_PORT)
        self._set_history_input_value(INPUT_HISTORY_TCP_IP, "")
        self._set_history_input_value(INPUT_HISTORY_TCP_PORT, "")
        label_input = self._query_ui("#tcp-label-input", Input)
        label_input.value = ""
        label_input.cursor_position = 0
        if focus:
            self._query_ui("#ip-input", Input).focus()

    def _disconnect_active_device(self) -> None:
        if not self.active_device_id:
            self.notify("No active workspace selected.", severity="warning")
            return
        self._disconnect_device(self.active_device_id)

    def _disconnect_device(self, target: str) -> None:
        if not self._is_device_connected(target):
            self.notify(f"{target} is not connected.", severity="warning")
            return

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

    def _clear_active_workspace_console(self) -> None:
        session = self._get_active_session()
        if not session:
            self.notify("No active workspace selected.", severity="warning")
            return

        session.raw_events.clear()
        session.parsed_lines.clear()
        self._refresh_workspace_state(session.device_id)
        self.notify(f"Cleared console for {session.device_id}")

    def _copy_active_workspace_to_clipboard(self) -> None:
        session = self._get_active_session()
        if not session:
            self.notify("No active workspace selected.", severity="warning")
            return

        workspace_text = self._active_workspace_text(session)
        if not workspace_text:
            self.notify("Active workspace has no data to copy.", severity="warning")
            return

        self.copy_to_clipboard(workspace_text)
        self.notify(f"Copied workspace for {session.device_id}.")

    def _active_workspace_text(self, session: DeviceSession) -> str:
        lines: list[str] = []
        for event in session.raw_events:
            lines.extend(self._render_raw_event_lines(session, event))
        return "\n".join(lines)

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
        self._refresh_command_history_list()
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
        self._refresh_command_history_list()

    def _run_macro(self, macro_key: str) -> None:
        macro = self._macros.get(macro_key)
        if macro is None:
            self.notify("Macro was not found.", severity="warning")
            self._refresh_macros()
            return

        device_id = self.active_device_id
        if not device_id:
            self.notify("Connect and select an active device first.", severity="warning")
            return

        commands = [command for command in macro.commands if command.command]
        if not commands:
            self.notify(f"Macro '{macro.label}' has no commands.", severity="warning")
            return

        conn = self.device_manager.get_connection(device_id)
        if not conn or not conn.is_open:
            self.notify(f"Device {device_id} is not connected.", severity="warning")
            return

        elapsed_seconds = 0.0
        for index, command in enumerate(commands):
            if index == 0:
                self._send_macro_command(device_id, command)
                elapsed_seconds += max(0, command.delay_ms) / 1000
                continue
            if elapsed_seconds <= 0:
                self._send_macro_command(device_id, command)
                elapsed_seconds += max(0, command.delay_ms) / 1000
                continue
            self.set_timer(
                elapsed_seconds,
                lambda command=command: self._send_macro_command(device_id, command),
            )
            elapsed_seconds += max(0, command.delay_ms) / 1000
        self.notify(f"Running macro '{macro.label}' ({len(commands)} command(s)).")

    def _send_macro_command(self, device_id: str, command: MacroCommandDefinition) -> None:
        payload = command.command.encode("utf-8")
        if not payload:
            return
        self._send_payload(device_id, payload)
        self._save_to_message_history(command.command)
        self._invalidate_input_history_cache(INPUT_HISTORY_MESSAGE)
        self._refresh_command_history_list()

    def _edit_macro(self, macro_key: str) -> None:
        macro = self._macros.get(macro_key)
        if macro is None or macro.path is None:
            self.notify("Macro was not found.", severity="warning")
            self._refresh_macros()
            return
        if isinstance(self.screen, ConfigEditorScreen):
            self.screen._display_document_for_path(macro.path)
            return
        self.push_screen(ConfigEditorScreen(initial_path=macro.path))

    def _send_payload(self, device_id: str, payload: bytes) -> None:
        conn = self.device_manager.get_connection(device_id)
        if not conn or not conn.is_open:
            self.notify(f"Device {device_id} is not connected.", severity="warning")
            return

        try:
            conn.send(payload)
        except Exception as exc:
            self.notify(f"Send failed: {exc}", severity="error")

    def _save_tcp_favorite_from_inputs(self) -> None:
        if not self.current_user:
            self.notify("Sign in before saving TCP favorites.", severity="warning")
            return

        host = self._query_ui("#ip-input", Input).value.strip()
        port_text = self._query_ui("#port-input", Input).value.strip()
        if not host or not port_text:
            self.notify("Enter both IP address and TCP port before saving a favorite.", severity="warning")
            return

        try:
            config = self._build_tcp_config_from_inputs()
        except Exception as exc:
            self.notify(f"Invalid TCP favorite: {exc}", severity="error")
            return

        label = self._query_ui("#tcp-label-input", Input).value.strip()
        added = upsert_tcp_favorite(self.current_user, config.host, config.port, label)
        self._refresh_tcp_favorites(selected_key=config.device_id)
        if added:
            self.notify(f"Saved {config.device_id} to favorites.")
            return
        self.notify(f"Updated favorite {config.device_id}.")

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

    def _save_active_workspace_log(self) -> None:
        session = self._get_active_session()
        if not session:
            self.notify("No active workspace selected.", severity="warning")
            return

        self._sync_session_output_format_from_widgets(session)
        workspace_text = self._active_workspace_text(session)
        if not workspace_text:
            self.notify("Active workspace has no data to save.", severity="warning")
            return

        try:
            log_path = self._resolve_log_path(session.device_id)
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return

        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(workspace_text + "\n", encoding="utf-8")
        except OSError as exc:
            self.notify(f"Save failed: {exc}", severity="error")
            return

        self.notify(f"Saved log for {session.device_id}: {log_path.name}")
        self._refresh_workspace_state(session.device_id)

    def _sync_session_output_format_from_widgets(self, session: DeviceSession) -> None:
        session.timestamps_enabled = self._query_ui("#timestamp-checkbox", Checkbox).value
        session.chevrons_enabled = self._query_ui("#chevron-checkbox", Checkbox).value

    def _refresh_logging_button(self) -> None:
        button = self._query_ui("#toggle-logging", Button)
        session = self._get_active_session()
        button.label = "Save Log"
        if not session:
            button.disabled = True
            return

        button.disabled = not bool(session.raw_events)

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

        merged_into_previous = session.add_raw_event(event)
        session.workspace_datastream.record_event(event)

        prefix = self._format_prefix(session, event.timestamp)
        if event.direction in {"RX", "TX"} and event.payload is not None:
            ascii_result = self._ascii_decoder.decode(event.payload)

            session.add_parsed_line(f"{prefix}{event.direction} {ascii_result.protocol}")
            for line in ascii_result.lines:
                session.add_parsed_line(f"  {line}")
        else:
            info_text = event.text or ""
            session.add_parsed_line(f"{prefix}{event.direction} {info_text}")

        if merged_into_previous:
            self._refresh_workspace_state(event.device_id)
            return

        self._append_workspace_event(event.device_id, event)
        self._update_workspace_tab_label(event.device_id)
        self._sync_active_device_from_workspace()

    def _format_prefix(self, session: DeviceSession, timestamp: datetime) -> str:
        if not session.timestamps_enabled:
            return ""
        return f"[{timestamp.strftime('%H:%M:%S.%f')[:-3]}] "

    def _format_direction_marker(self, session: DeviceSession, direction: str) -> str:
        if not session.chevrons_enabled:
            return ""
        if direction == "RX":
            return "<< "
        if direction == "TX":
            return ">> "
        return ""

    def _render_raw_event_lines(self, session: DeviceSession, event: SerialEvent) -> list[str]:
        prefix = self._format_prefix(session, event.timestamp)
        if event.direction in {"RX", "TX"} and event.payload is not None:
            prefix = f"{prefix}{self._format_direction_marker(session, event.direction)}"
            formatted = event.payload.decode("utf-8", errors="replace")
            lines = formatted.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            return [f"{prefix}{line}" for line in lines if line or len(lines) == 1]
        return [f"{prefix}{event.direction} {event.text or ''}"]

    def _is_tx_hex_mode(self) -> bool:
        return self._query_ui("#tx-hex-checkbox", Checkbox).value

    def _normalize_log_destination_setting(self, configured_path: str) -> str:
        normalized = configured_path.strip()
        if not normalized:
            return ""

        target = Path(normalized).expanduser()
        if target.suffix.lower() == ".txt":
            return normalized
        if not target.exists():
            raise ValueError("The selected log folder does not exist.")
        if not target.is_dir():
            raise ValueError("Log destination must be a folder or a .txt file path.")
        return normalized

    def _resolve_log_path(self, device_id: str) -> Path:
        configured_path = self._normalize_log_destination_setting(
            self._query_ui("#log-filepath", Input).value
        )
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

    def _empty_workspace_feed(self) -> list[float]:
        return [0.0] * WORKSPACE_DATASTREAM_WINDOW

    def _line_has_recent_activity(self, samples: Sequence[float], window: int = 4) -> bool:
        return any(value >= 1.0 for value in samples[-window:])

    def _set_workspace_datastream_row_state(self, sparkline: Sparkline, active: bool) -> None:
        sparkline.set_class(active, "-active")
        sparkline.set_class(not active, "-idle")

    def _advance_workspace_datastreams(self) -> None:
        if self._shutting_down or not self.sessions:
            return

        for session in self.sessions.values():
            session.workspace_datastream.tick()

        self._refresh_workspace_toolbar()

    def _refresh_workspace_toolbar(self) -> None:
        try:
            connection_title = self._query_ui("#connection-status-title", Static)
            connection_led = self._query_ui("#connection-status-led", ConnectionStatusLed)
            rx_label = self._query_ui("#workspace-rx-label", Static)
            tx_label = self._query_ui("#workspace-tx-label", Static)
            rx_activity = self._query_ui("#workspace-rx-activity", WorkspaceActivityLed)
            tx_activity = self._query_ui("#workspace-tx-activity", WorkspaceActivityLed)
            rx_sparkline = self._query_ui("#workspace-rx-sparkline", Sparkline)
            tx_sparkline = self._query_ui("#workspace-tx-sparkline", Sparkline)
        except NoMatches:
            return

        if not self.active_device_id:
            connection_title.set_class(False, "-on")
            connection_title.set_class(True, "-off")
            connection_led.active = False
            rx_label.set_class(False, "-on")
            rx_label.set_class(True, "-off")
            tx_label.set_class(False, "-on")
            tx_label.set_class(True, "-off")
            rx_activity.active = False
            tx_activity.active = False
            rx_sparkline.data = self._empty_workspace_feed()
            tx_sparkline.data = self._empty_workspace_feed()
            self._set_workspace_datastream_row_state(rx_sparkline, False)
            self._set_workspace_datastream_row_state(tx_sparkline, False)
            return

        session = self.sessions.get(self.active_device_id)
        if not session:
            connection_title.set_class(False, "-on")
            connection_title.set_class(True, "-off")
            connection_led.active = False
            rx_label.set_class(False, "-on")
            rx_label.set_class(True, "-off")
            tx_label.set_class(False, "-on")
            tx_label.set_class(True, "-off")
            rx_activity.active = False
            tx_activity.active = False
            rx_sparkline.data = self._empty_workspace_feed()
            tx_sparkline.data = self._empty_workspace_feed()
            self._set_workspace_datastream_row_state(rx_sparkline, False)
            self._set_workspace_datastream_row_state(tx_sparkline, False)
            return

        connected = self._is_device_connected(self.active_device_id)
        rx_recent = self._line_has_recent_activity(session.workspace_datastream.rx_samples)
        tx_recent = self._line_has_recent_activity(session.workspace_datastream.tx_samples)
        connection_title.set_class(connected, "-on")
        connection_title.set_class(not connected, "-off")
        connection_led.active = connected
        rx_label.set_class(rx_recent, "-on")
        rx_label.set_class(not rx_recent, "-off")
        tx_label.set_class(tx_recent, "-on")
        tx_label.set_class(not tx_recent, "-off")
        rx_activity.active = rx_recent
        tx_activity.active = tx_recent
        rx_sparkline.data = list(session.workspace_datastream.rx_samples)
        tx_sparkline.data = list(session.workspace_datastream.tx_samples)
        self._set_workspace_datastream_row_state(rx_sparkline, rx_recent)
        self._set_workspace_datastream_row_state(tx_sparkline, tx_recent)

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
        session = self.sessions.get(device_id)
        display_name = session.label if session and session.label else device_id
        return f"{display_name} [{state}]"

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
        if self._shutting_down:
            return
        try:
            tabs = self._query_ui("#workspace-tabs", TabbedContent)
        except NoMatches:
            self.active_device_id = None
            return
        self.active_device_id = self._workspace_devices_by_pane.get(tabs.active)
        self._update_workspace_summary()
        self._refresh_logging_button()

    def _update_workspace_summary(self) -> None:
        try:
            summary = self._query_ui("#workspace-selection", Static)
            clear_button = self._query_ui("#clear-console-btn", Button)
            close_button = self._query_ui("#close-active-workspace", Button)
            copy_button = self._query_ui("#copy-workspace-btn", Button)
        except NoMatches:
            return
        if not self.active_device_id:
            summary.update("No device workspaces open.")
            clear_button.disabled = True
            close_button.disabled = True
            copy_button.disabled = True
            self._refresh_workspace_toolbar()
            return

        state = "connected" if self._is_device_connected(self.active_device_id) else "saved"
        summary.update(f"Active workspace: {self.active_device_id} ({state})")
        clear_button.disabled = False
        close_button.disabled = False
        copy_button.disabled = False
        self._refresh_workspace_toolbar()

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
                    self._workspace_placeholder_text(),
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
