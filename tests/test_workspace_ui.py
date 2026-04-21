import asyncio
from types import SimpleNamespace

from textual.widgets import Button, Input, Select, TabbedContent, TextArea

from serialhub.app import ScriptEditorScreen, SerialHubApp
from serialhub.config import ENV_DATA_DIR
from serialhub.core.models import DeviceInfo, SerialEvent
from serialhub.user_profiles import (
    create_user_profile,
    get_user_tcp_ip_history_path,
    get_user_tcp_port_history_path,
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


def test_script_editor_shortcut_opens_and_closes_screen() -> None:
    async def scenario() -> None:
        app = SerialHubApp(require_login=False)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            tx_input = app.query_one("#tx-input", Input)
            tx_input.value = "draft"
            tx_input.cursor_position = 0
            tx_input.focus()
            await pilot.pause()

            await pilot.press("ctrl+e")
            await pilot.pause()
            assert isinstance(app.screen, ScriptEditorScreen)

            script_editor = app.screen.query_one("#script-editor", TextArea)
            script_editor.focus()
            await pilot.pause()

            await pilot.press("ctrl+e")
            await pilot.pause()
            assert not isinstance(app.screen, ScriptEditorScreen)

    asyncio.run(scenario())


def test_workspace_updates_continue_while_script_editor_screen_is_open() -> None:
    async def scenario() -> None:
        app = SerialHubApp(require_login=False)
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            app._connect_selected_device()
            await pilot.pause()

            app.action_toggle_script_editor()
            await pilot.pause()
            assert isinstance(app.screen, ScriptEditorScreen)

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
            assert str(app.query_one("#workspace-selection").renderable) == "Active workspace: COM1 (saved)"
            assert app.query_one("#close-active-workspace", Button).disabled is False

            app._close_workspace_for_device("COM1")
            await pilot.pause()

            assert "COM1" not in app.sessions
            assert app.active_device_id is None
            assert str(app.query_one("#workspace-selection").renderable) == "No device workspaces open."
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
            raw_log.scroll_to(y=0, animate=False, immediate=True)
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
            assert raw_log.size.height > 0

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
            assert str(app.query_one("#workspace-selection").renderable) == (
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
            assert str(app.query_one("#workspace-selection").renderable) == (
                "Active workspace: 192.168.0.10:4059 (saved)"
            )

    asyncio.run(scenario())
