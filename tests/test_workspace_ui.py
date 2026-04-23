import asyncio
import json
from types import SimpleNamespace

from textual.widgets import Button, Input, Select, Sparkline, Static, TabbedContent

from serialhub.app import (
    ConfigEditorScreen,
    ConnectionStatusSwitch,
    SerialHubApp,
    UserSettingsScreen,
    WorkspaceActivityIndicator,
)
from serialhub.config import ENV_DATA_DIR
from serialhub.core.models import DeviceInfo, SerialEvent
from serialhub.user_profiles import (
    create_user_profile,
    get_user_command_config_path,
    get_user_tcp_ip_history_path,
    get_user_tcp_port_history_path,
    load_user_profile,
    upsert_tcp_favorite,
)


def static_text(widget: Static) -> str:
    renderable = getattr(widget, "renderable", None)
    if renderable is not None:
        return str(renderable)
    try:
        return str(widget.render())
    except Exception:
        return str(
            getattr(
                widget,
                "_content",
                getattr(widget, "_Static__content", ""),
            )
        )


class FakeDeviceManager:
    def __init__(self) -> None:
        self.connected: set[str] = set()
        self.devices = [DeviceInfo(port="COM1", description="Demo Device", hwid="HWID-1")]

    def scan_devices(self) -> list[DeviceInfo]:
        return self.devices

    def connect(self, port: str, config, event_callback):
        self.connected.add(port)
        return SimpleNamespace(is_open=True)

    def connect_tcp(self, config, event_callback):
        self.connected.add(config.device_id)
        return SimpleNamespace(is_open=True)

    def disconnect(self, device_id: str) -> None:
        self.connected.discard(device_id)

    def disconnect_all(self) -> None:
        self.connected.clear()

    def get_connection(self, device_id: str):
        return SimpleNamespace(is_open=device_id in self.connected, send=lambda payload: len(payload))

    def connected_ports(self) -> list[str]:
        return sorted(self.connected)


class MultiDeviceManager(FakeDeviceManager):
    def __init__(self) -> None:
        super().__init__()
        self.devices = [
            DeviceInfo(port="COM1", description="Demo Device 1", hwid="HWID-1"),
            DeviceInfo(port="COM2", description="Demo Device 2", hwid="HWID-2"),
        ]


class EmptyDeviceManager(FakeDeviceManager):
    def __init__(self) -> None:
        super().__init__()
        self.devices = []


def test_config_editor_button_opens_and_closes_screen(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            await pilot.pause()

            await pilot.click("#config-editor-btn")
            await pilot.pause()
            assert isinstance(app.screen, ConfigEditorScreen)

            preview = app.screen.query_one("#config-editor-preview", Static)
            assert static_text(preview) == ""
            assert app.screen.query_one("#config-save", Button).disabled is True

            app.screen.action_close_config_editor()
            await pilot.pause()
            assert not isinstance(app.screen, ConfigEditorScreen)

    asyncio.run(scenario())


def test_user_settings_button_opens_and_closes_screen(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            await pilot.pause()

            app.query_one("#user-settings-btn", Button).press()
            await pilot.pause()
            assert isinstance(app.screen, UserSettingsScreen)

            app.screen.action_close_settings()
            await pilot.pause()
            assert not isinstance(app.screen, UserSettingsScreen)

    asyncio.run(scenario())


def test_config_editor_loads_focused_file_into_structured_form(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")
    command_path = get_user_command_config_path("alice", "alice_cmds")
    command_path.write_text(
        json.dumps(
            {
                "NAME": "DEFAULTS",
                "COMMANDS": {
                    "PING": "ping\r\n",
                    "SET": {
                        "TIME": "set time + % &\r\n",
                    },
                },
            },
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            await pilot.click("#config-editor-btn")
            await pilot.pause()

            assert isinstance(app.screen, ConfigEditorScreen)
            app.screen._display_document_for_path(command_path)
            await pilot.pause()
            await pilot.pause()

            assert app.screen.query_one("#config-name-input", Input).value == "DEFAULTS"
            assert app.screen.query_one("#config-command-label-1", Input).value == "PING"
            assert app.screen.query_one("#config-command-value-1", Input).value == "ping\\r\\n"
            assert app.screen.query_one("#config-command-label-2", Input).value == "SET / TIME"
            assert app.screen.query_one("#config-command-value-2", Input).value == "set time + % &\\r\\n"

            preview = app.screen.query_one("#config-editor-preview", Static)
            assert '"TIME": "set time + % &\\r\\n"' in static_text(preview)

    asyncio.run(scenario())


def test_config_editor_new_flow_adds_command_rows_and_saves_form_data(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            await pilot.click("#config-editor-btn")
            await pilot.pause()

            assert isinstance(app.screen, ConfigEditorScreen)
            app.screen.query_one("#config-new", Button).press()
            await pilot.pause()

            name_input = app.screen.query_one("#config-name-input", Input)
            label_1 = app.screen.query_one("#config-command-label-1", Input)
            value_1 = app.screen.query_one("#config-command-value-1", Input)
            name_input.value = "field_setup"
            label_1.value = "SET / DATE"
            value_1.value = "set date\\r\\n"
            await pilot.pause()

            app.screen.query_one("#config-add-command", Button).press()
            await pilot.pause()
            await pilot.pause()
            label_2 = app.screen.query_one("#config-command-label-2", Input)
            value_2 = app.screen.query_one("#config-command-value-2", Input)
            label_2.value = "GET / STATUS"
            value_2.value = "get status + 100% & ok\\r\\n"
            await pilot.pause()

            preview = app.screen.query_one("#config-editor-preview", Static)
            assert '"SET"' in static_text(preview)
            assert '"STATUS": "get status + 100% & ok\\r\\n"' in static_text(preview)
            editor_region = app.screen.query_one("#config-command-editor").region
            row_1_region = app.screen.query_one("#config-command-row-1").region
            row_2_region = app.screen.query_one("#config-command-row-2").region
            assert editor_region.x <= row_1_region.x
            assert row_1_region.right <= editor_region.right
            assert editor_region.x <= row_2_region.x
            assert row_2_region.right <= editor_region.right

            app.screen.query_one("#config-save", Button).press()
            await pilot.pause()

            saved_payload = json.loads(
                get_user_command_config_path("alice", "field_setup").read_text(encoding="utf-8")
            )
            assert saved_payload["NAME"] == "field_setup"
            assert saved_payload["COMMANDS"]["SET"]["DATE"] == "set date\r\n"
            assert saved_payload["COMMANDS"]["GET"]["STATUS"] == "get status + 100% & ok\r\n"
            assert "field_setup" in app.current_user.command_configs
            assert "field_setup" in app._command_configs

    asyncio.run(scenario())

def test_config_editor_delete_button_removes_command_row(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")
    command_path = get_user_command_config_path("alice", "alice_cmds")
    command_path.write_text(
        json.dumps(
            {
                "NAME": "DEFAULTS",
                "COMMANDS": {
                    "PING": "ping\r\n",
                    "GET": {
                        "STATUS": "status\r\n",
                    },
                },
            },
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            await pilot.click("#config-editor-btn")
            await pilot.pause()

            assert isinstance(app.screen, ConfigEditorScreen)
            app.screen._display_document_for_path(command_path)
            await pilot.pause()
            await pilot.pause()

            delete_button = app.screen.query_one("#config-command-delete-1", Button)
            assert delete_button.label.plain.strip() == "X"
            assert delete_button.region.width <= 5

            app.screen.query_one("#config-command-delete-1", Button).press()
            await pilot.pause()
            await pilot.pause()

            assert app.screen.query_one("#config-command-label-1", Input).value == "GET / STATUS"
            assert app.screen.query_one("#config-command-row-2").display is False

            app.screen.query_one("#config-save", Button).press()
            await pilot.pause()

            saved_path = get_user_command_config_path("alice", "DEFAULTS")
            saved_payload = json.loads(saved_path.read_text(encoding="utf-8"))
            assert "PING" not in saved_payload["COMMANDS"]
            assert saved_payload["COMMANDS"]["GET"]["STATUS"] == "status\r\n"

    asyncio.run(scenario())


def test_config_editor_delete_button_removes_selected_file_after_confirmation(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")
    command_path = get_user_command_config_path("alice", "alice_cmds")

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            await pilot.click("#config-editor-btn")
            await pilot.pause()

            assert isinstance(app.screen, ConfigEditorScreen)
            app.screen._display_document_for_path(command_path)
            await pilot.pause()
            await pilot.pause()

            await pilot.click("#config-delete")
            await pilot.pause()

            assert "alice_cmds.json" in static_text(app.screen.query_one("#config-delete-message", Static))

            await pilot.click("#config-delete-yes")
            await pilot.pause()
            await pilot.pause()

            assert isinstance(app.screen, ConfigEditorScreen)
            assert command_path.exists() is False
            assert "alice_cmds" not in app.current_user.command_configs

    asyncio.run(scenario())


def test_config_editor_resets_input_view_when_loading_new_values(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")
    first_path = get_user_command_config_path("alice", "first")
    second_path = get_user_command_config_path("alice", "second")
    first_path.write_text(
        json.dumps(
            {
                "NAME": "FIRST",
                "COMMANDS": {
                    "LONG": "ffff\r\n",
                },
            },
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )
    second_path.write_text(
        json.dumps(
            {
                "NAME": "SECOND",
                "COMMANDS": {
                    "SHORT": "CMD",
                },
            },
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            await pilot.click("#config-editor-btn")
            await pilot.pause()

            assert isinstance(app.screen, ConfigEditorScreen)
            app.screen._display_document_for_path(first_path)
            await pilot.pause()

            value_input = app.screen.query_one("#config-command-value-1", Input)
            value_input.cursor_position = len(value_input.value)
            value_input.view_position = 4

            app.screen._display_document_for_path(second_path)
            await pilot.pause()

            next_input = app.screen.query_one("#config-command-value-1", Input)
            assert next_input.value == "CMD"
            assert next_input.cursor_position == 0
            assert next_input.view_position == 0

    asyncio.run(scenario())


def test_config_editor_edits_existing_file_without_raw_json_changes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")
    command_path = get_user_command_config_path("alice", "alice_cmds")

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            await pilot.click("#config-editor-btn")
            await pilot.pause()
            assert isinstance(app.screen, ConfigEditorScreen)

            app.screen._display_document_for_path(command_path)
            await pilot.pause()
            await pilot.pause()

            app.screen.query_one("#config-name-input", Input).value = "Updated Defaults"
            app.screen.query_one("#config-command-label-1", Input).value = "PING"
            app.screen.query_one("#config-command-value-1", Input).value = "ping now\\r\\n"
            await pilot.pause()

            app.screen.query_one("#config-save", Button).press()
            await pilot.pause()
            await pilot.pause()

            saved_path = get_user_command_config_path("alice", "Updated Defaults")
            saved_payload = json.loads(saved_path.read_text(encoding="utf-8"))
            assert saved_payload["NAME"] == "Updated Defaults"
            assert saved_payload["COMMANDS"]["PING"] == "ping now\r\n"
            assert not command_path.exists()
            assert app._command_configs["Updated Defaults"].name == "Updated Defaults"

    asyncio.run(scenario())


def test_workspace_updates_continue_while_config_editor_screen_is_open(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            app._connect_selected_device()
            await pilot.pause()

            app.action_open_config_editor()
            await pilot.pause()
            assert isinstance(app.screen, ConfigEditorScreen)

            app._handle_serial_event_ui(
                SerialEvent(device_id="COM1", port="COM1", direction="RX", payload=b"hello-from-device")
            )
            await pilot.pause()

            assert app.active_device_id == "COM1"
            assert "COM1" in app._workspace_logs
            assert len(app.sessions["COM1"].raw_events) >= 1

    asyncio.run(scenario())


def test_disconnect_preserves_workspace_until_close() -> None:
    async def scenario() -> None:
        app = SerialHubApp(require_login=False)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            app._connect_selected_device()
            await pilot.pause()

            app._handle_serial_event_ui(
                SerialEvent(device_id="COM1", port="COM1", direction="RX", payload=b"hello")
            )
            await pilot.pause()

            app._disconnect_device("COM1")
            await pilot.pause()

            assert "COM1" in app.sessions
            assert app.active_device_id == "COM1"
            assert static_text(app.query_one("#workspace-selection", Static)) == (
                "Active workspace: COM1 (saved)"
            )
            assert app.query_one("#close-active-workspace", Button).disabled is False

            app._close_workspace_for_device("COM1")
            await pilot.pause()

            assert "COM1" not in app.sessions
            assert app.active_device_id is None
            assert static_text(app.query_one("#workspace-selection", Static)) == "No device workspaces open."
            assert app.query_one("#close-active-workspace", Button).disabled is True

    asyncio.run(scenario())


def test_toolbar_close_button_closes_active_workspace() -> None:
    async def scenario() -> None:
        app = SerialHubApp(require_login=False)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            app._connect_selected_device()
            await pilot.pause()

            await pilot.click("#close-active-workspace")
            await pilot.pause()

            assert "COM1" not in app.sessions
            assert app.active_device_id is None

    asyncio.run(scenario())


def test_workspace_log_scroll_does_not_jump_when_user_is_reading_history() -> None:
    async def scenario() -> None:
        app = SerialHubApp(require_login=False)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            app._connect_selected_device()

            for index in range(80):
                app._handle_serial_event_ui(
                    SerialEvent(
                        device_id="COM1",
                        port="COM1",
                        direction="RX",
                        payload=f"line-{index}".encode(),
                    )
                )
            await pilot.pause()

            raw_log = app._workspace_logs["COM1"]
            raw_log.auto_scroll = False
            raw_log.scroll_to(y=0, animate=False, immediate=True, force=True)
            await pilot.pause()
            await pilot.pause()
            assert raw_log.scroll_y == 0

            app._handle_serial_event_ui(
                SerialEvent(device_id="COM1", port="COM1", direction="RX", payload=b"latest-line")
            )
            await pilot.pause()

            assert raw_log.scroll_y == 0
            assert raw_log.max_scroll_y > 0

    asyncio.run(scenario())


def test_second_connected_device_keeps_workspace_log_visible() -> None:
    async def scenario() -> None:
        app = SerialHubApp(require_login=False)
        app.device_manager = MultiDeviceManager()

        async with app.run_test() as pilot:
            app.selected_port = "COM1"
            app._connect_selected_device()
            await pilot.pause()

            app.selected_port = "COM2"
            app._connect_selected_device()
            await pilot.pause()
            await pilot.pause()

            raw_log = app._workspace_logs["COM2"]
            assert app.active_device_id == "COM2"
            assert raw_log.region.height > 0
            assert raw_log.region.width > 0

    asyncio.run(scenario())


def test_left_panel_actions_row_is_docked_to_bottom() -> None:
    async def scenario() -> None:
        app = SerialHubApp(require_login=False)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            await pilot.pause()
            action_row = app.query_one("#left-panel-actions")
            assert str(action_row.styles.dock) == "bottom"

    asyncio.run(scenario())


def test_command_config_select_is_blank_without_user() -> None:
    async def scenario() -> None:
        app = SerialHubApp(require_login=False)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            await pilot.pause()
            select = app.query_one("#command-config-select", Select)
            assert select.is_blank() is True
            assert select.disabled is True
            assert app.query_one("#config-editor-btn", Button).disabled is True
            assert app.query_one("#user-settings-btn", Button).disabled is True

    asyncio.run(scenario())


def test_command_config_select_stays_blank_for_signed_in_user_until_the_user_picks_one(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            await pilot.pause()
            select = app.query_one("#command-config-select", Select)
            assert select.disabled is False
            assert select.is_blank() is True

    asyncio.run(scenario())


def test_user_settings_save_persists_startup_command_theme_and_log_folder(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")
    custom_logs = tmp_path / "custom-logs"
    custom_logs.mkdir()

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            await pilot.pause()

            app.query_one("#user-settings-btn", Button).press()
            await pilot.pause()
            assert isinstance(app.screen, UserSettingsScreen)

            app.screen.query_one("#settings-startup-command", Select).value = "alice_cmds"
            app.screen.query_one("#settings-theme", Select).value = "light"
            app.screen.query_one("#settings-log-folder", Input).value = str(custom_logs)
            await pilot.pause()

            app.screen.query_one("#settings-save", Button).press()
            await pilot.pause()
            await pilot.pause()

            assert not isinstance(app.screen, UserSettingsScreen)
            assert app.theme_mode == "light"
            assert app.theme == "app-light"
            assert app.query_one("#log-filepath", Input).value == str(custom_logs)
            assert app.query_one("#command-config-select", Select).value == "alice_cmds"

            reloaded_profile = load_user_profile("alice")
            assert reloaded_profile is not None
            assert reloaded_profile.startup_command_config == "alice_cmds"
            assert reloaded_profile.theme == "app-light"
            assert reloaded_profile.log_folder == str(custom_logs)

        reloaded_profile = load_user_profile("alice")
        assert reloaded_profile is not None

        reopened_app = SerialHubApp(require_login=False, startup_user=reloaded_profile)
        reopened_app.device_manager = FakeDeviceManager()
        async with reopened_app.run_test() as reopened_pilot:
            await reopened_pilot.pause()
            assert reopened_app.query_one("#command-config-select", Select).value == "alice_cmds"
            assert reopened_app.theme_mode == "light"
            assert reopened_app.query_one("#log-filepath", Input).value == str(custom_logs)

    asyncio.run(scenario())


def test_clear_console_button_clears_active_workspace_history() -> None:
    async def scenario() -> None:
        app = SerialHubApp(require_login=False)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            app._connect_selected_device()
            app._handle_serial_event_ui(
                SerialEvent(device_id="COM1", port="COM1", direction="RX", payload=b"hello")
            )
            await pilot.pause()

            await pilot.click("#clear-console-btn")
            await pilot.pause()

            assert app.sessions["COM1"].raw_events == []
            assert app.query_one("#clear-console-btn", Button).disabled is False

    asyncio.run(scenario())


def test_current_user_summary_is_positioned_below_workspace_selection(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            await pilot.pause()
            workspace = app.query_one("#workspace-selection")
            summary = app.query_one("#current-user-summary")
            assert abs(summary.region.x - workspace.region.x) <= 2
            assert summary.region.y > workspace.region.y

    asyncio.run(scenario())


def test_workspace_status_container_sits_at_bottom_of_center_panel(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            await pilot.pause()
            center_panel = app.query_one("#center-panel")
            workspace_tabs = app.query_one("#workspace-tabs")
            function_row = app.query_one("#function-buttons-row")
            status = app.query_one("#workspace-status")
            assert status.region.y > function_row.region.y
            assert status.region.bottom <= center_panel.region.bottom
            assert abs(status.region.x - workspace_tabs.region.x) <= 2
            assert abs(status.region.width - workspace_tabs.region.width) <= 2

    asyncio.run(scenario())


def test_connection_switch_reflects_active_workspace_connection_state() -> None:
    async def scenario() -> None:
        app = SerialHubApp(require_login=False)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            connection_switch = app.query_one("#connection-status-led", ConnectionStatusSwitch)
            assert connection_switch.value is False
            assert connection_switch.can_focus is False

            await pilot.click("#connection-status-led")
            await pilot.pause()
            assert connection_switch.value is False

            app._connect_selected_device()
            await pilot.pause()
            assert connection_switch.value is True

            await pilot.click("#connection-status-led")
            await pilot.pause()
            assert connection_switch.value is True

            app._disconnect_device("COM1")
            await pilot.pause()
            assert connection_switch.value is False

    asyncio.run(scenario())


def test_workspace_activity_indicators_and_combined_sparkline_follow_rx_tx_activity_and_flatten_when_idle(
) -> None:
    async def scenario() -> None:
        app = SerialHubApp(require_login=False)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            connection_widget = app.query_one("#workspace-connection-widget")
            rule = app.query_one("#connection-status-rule")
            data_widget = app.query_one("#workspace-data-widget")
            sparkline = app.query_one("#workspace-io-sparkline", Sparkline)
            rx_label = app.query_one("#workspace-rx-label", Static)
            tx_label = app.query_one("#workspace-tx-label", Static)
            rx_activity = app.query_one("#workspace-rx-activity", WorkspaceActivityIndicator)
            tx_activity = app.query_one("#workspace-tx-activity", WorkspaceActivityIndicator)
            assert data_widget.border_title == " ACTIVITY "
            assert rule.region.height > 0
            assert rx_label.region.height > 0
            assert tx_label.region.height > 0
            assert rx_label.region.bottom <= connection_widget.region.bottom
            assert tx_label.region.bottom <= connection_widget.region.bottom
            assert all(value == 0.0 for value in list(sparkline.data or []))
            assert rx_label.has_class("-off") is True
            assert tx_label.has_class("-off") is True
            assert rx_activity.value is False
            assert tx_activity.value is False
            assert rx_activity.can_focus is False
            assert tx_activity.can_focus is False

            app._connect_selected_device()
            app._handle_serial_event_ui(
                SerialEvent(device_id="COM1", port="COM1", direction="RX", payload=b"hello")
            )
            app._handle_serial_event_ui(
                SerialEvent(device_id="COM1", port="COM1", direction="TX", payload=b"ok")
            )
            await pilot.pause()

            data = list(sparkline.data or [])
            assert max(data or [0.0]) >= 5.0
            assert min(data or [0.0]) <= -2.0
            assert rx_label.has_class("-on") is True
            assert tx_label.has_class("-on") is True
            assert rx_activity.value is True
            assert tx_activity.value is True

            for _ in range(40):
                app._advance_workspace_datastreams()
            await pilot.pause()

            assert all(value == 0.0 for value in list(sparkline.data or []))
            assert rx_label.has_class("-off") is True
            assert tx_label.has_class("-off") is True
            assert rx_activity.value is False
            assert tx_activity.value is False

    asyncio.run(scenario())


def test_device_select_is_blank_when_no_devices_are_found() -> None:
    async def scenario() -> None:
        app = SerialHubApp(require_login=False)
        app.device_manager = EmptyDeviceManager()

        async with app.run_test() as pilot:
            await pilot.pause()
            select = app.query_one("#device-list", Select)
            assert app.selected_port is None
            assert select.is_blank() is True

    asyncio.run(scenario())


def test_tcp_tab_connects_workspace_from_ip_and_port() -> None:
    async def scenario() -> None:
        app = SerialHubApp(require_login=False)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            connection_tabs = app.query_one("#connection-tabs", TabbedContent)
            connection_tabs.active = "connection-tcp"
            app.query_one("#ip-input", Input).value = "192.168.0.10"
            app.query_one("#port-input", Input).value = "4059"
            await pilot.pause()

            await pilot.click("#connect-btn")
            await pilot.pause()

            assert "192.168.0.10:4059" in app.sessions
            assert app.sessions["192.168.0.10:4059"].transport == "tcp"
            assert app.active_device_id == "192.168.0.10:4059"
            assert "192.168.0.10:4059" in app._workspace_logs
            assert static_text(app.query_one("#workspace-selection", Static)) == (
                "Active workspace: 192.168.0.10:4059 (connected)"
            )

    asyncio.run(scenario())


def test_tcp_connect_persists_user_ip_and_port_history(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            connection_tabs = app.query_one("#connection-tabs", TabbedContent)
            connection_tabs.active = "connection-tcp"
            app.query_one("#ip-input", Input).value = "192.168.0.10"
            app.query_one("#port-input", Input).value = "4059"
            await pilot.pause()

            await pilot.click("#connect-btn")
            await pilot.pause()

            ip_history = get_user_tcp_ip_history_path("alice").read_text(encoding="utf-8")
            port_history = get_user_tcp_port_history_path("alice").read_text(encoding="utf-8")
            assert "192.168.0.10" in ip_history
            assert "4059" in port_history

    asyncio.run(scenario())


def test_tcp_clear_button_resets_ip_and_port_inputs() -> None:
    async def scenario() -> None:
        app = SerialHubApp(require_login=False)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            connection_tabs = app.query_one("#connection-tabs", TabbedContent)
            connection_tabs.active = "connection-tcp"
            app.query_one("#ip-input", Input).value = "192.168.0.10"
            app.query_one("#port-input", Input).value = "4059"
            await pilot.pause()

            app.query_one("#clear-tcp-inputs", Button).press()
            await pilot.pause()

            assert app.query_one("#ip-input", Input).value == ""
            assert app.query_one("#port-input", Input).value == ""

    asyncio.run(scenario())


def test_tcp_disconnect_preserves_workspace_until_closed() -> None:
    async def scenario() -> None:
        app = SerialHubApp(require_login=False)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            connection_tabs = app.query_one("#connection-tabs", TabbedContent)
            connection_tabs.active = "connection-tcp"
            app.query_one("#ip-input", Input).value = "192.168.0.10"
            app.query_one("#port-input", Input).value = "4059"
            await pilot.pause()

            await pilot.click("#connect-btn")
            await pilot.pause()

            app._disconnect_active_device()
            await pilot.pause()

            assert "192.168.0.10:4059" in app.sessions
            assert app.active_device_id == "192.168.0.10:4059"
            assert static_text(app.query_one("#workspace-selection", Static)) == (
                "Active workspace: 192.168.0.10:4059 (saved)"
            )

    asyncio.run(scenario())


def test_disconnect_button_targets_active_workspace_not_left_panel_selection() -> None:
    async def scenario() -> None:
        app = SerialHubApp(require_login=False)
        app.device_manager = MultiDeviceManager()

        async with app.run_test() as pilot:
            app.selected_port = "COM1"
            app._connect_selected_device()
            await pilot.pause()

            app.selected_port = "COM2"
            app._connect_selected_device()
            await pilot.pause()

            app._set_active_workspace("COM1")
            await pilot.pause()

            app.query_one("#disconnect-btn", Button).press()
            await pilot.pause()

            assert app._is_device_connected("COM1") is False
            assert app._is_device_connected("COM2") is True
            assert static_text(app.query_one("#workspace-selection", Static)) == (
                "Active workspace: COM1 (saved)"
            )

    asyncio.run(scenario())


def test_tcp_favorites_button_persists_current_ip_and_port_to_user_profile(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            connection_tabs = app.query_one("#connection-tabs", TabbedContent)
            connection_tabs.active = "connection-tcp"
            app.query_one("#ip-input", Input).value = "192.168.0.10"
            app.query_one("#port-input", Input).value = "4059"
            await pilot.pause()

            app.query_one("#tcp-favorites-btn", Button).press()
            await pilot.pause()

            reloaded_profile = load_user_profile("alice")
            assert reloaded_profile is not None
            assert len(reloaded_profile.tcp_favorites) == 1
            assert reloaded_profile.tcp_favorites[0].host == "192.168.0.10"
            assert reloaded_profile.tcp_favorites[0].port == 4059

    asyncio.run(scenario())


def test_tcp_favorites_select_lists_saved_connections_and_populates_inputs(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")

    upsert_tcp_favorite(profile, "192.168.0.10", 4059)
    upsert_tcp_favorite(profile, "10.0.0.8", 9000)
    reloaded_profile = load_user_profile("alice")
    assert reloaded_profile is not None

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=reloaded_profile)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            await pilot.pause()
            favorites = app.query_one("#tcp-favorites-list", Select)
            assert favorites.disabled is False
            assert favorites.is_blank() is True

            favorites.value = "10.0.0.8:9000"
            await pilot.pause()

            assert app.query_one("#ip-input", Input).value == "10.0.0.8"
            assert app.query_one("#port-input", Input).value == "9000"

    asyncio.run(scenario())


def test_tcp_favorites_button_warns_and_skips_save_when_inputs_are_blank(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")
    notifications: list[tuple[str, str | None]] = []

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)
        app.device_manager = FakeDeviceManager()
        app.notify = lambda message, severity=None, **kwargs: notifications.append((str(message), severity))

        async with app.run_test() as pilot:
            connection_tabs = app.query_one("#connection-tabs", TabbedContent)
            connection_tabs.active = "connection-tcp"
            await pilot.pause()

            app.query_one("#tcp-favorites-btn", Button).press()
            await pilot.pause()

            reloaded_profile = load_user_profile("alice")
            assert reloaded_profile is not None
            assert reloaded_profile.tcp_favorites == []
            assert notifications[-1] == (
                "Enter both IP address and TCP port before saving a favorite.",
                "warning",
            )

    asyncio.run(scenario())
