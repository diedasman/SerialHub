import asyncio
import json

from textual.widgets import Input

from serialhub.app import SerialHubApp, UserLoginScreen
from serialhub.config import ENV_DATA_DIR
from serialhub.user_profiles import (
    create_user_profile,
    get_remembered_username,
    get_user_command_config_path,
    get_user_message_history_path,
    get_user_profile_path,
    get_user_tcp_ip_history_path,
    get_user_tcp_port_history_path,
    load_command_configs,
    load_user_profile,
    set_remembered_username,
)


def test_create_user_profile_creates_expected_local_files(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))

    profile = create_user_profile("alice")

    assert profile.username == "alice"
    assert profile.command_configs == ["alice_cmds", "blank"]
    assert get_user_profile_path("alice").exists()
    assert get_user_command_config_path("alice", "alice_cmds").exists()
    assert get_user_command_config_path("alice", "blank").exists()


def test_load_command_configs_uses_profile_config_list(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    create_user_profile("alice")

    command_path = get_user_command_config_path("alice", "alice_cmds")
    command_path.write_text(
        json.dumps(
            {
                "NAME": "DEFAULTS",
                "COMMANDS": {
                    "PING": "ping\r\n",
                    "SET": {
                        "TIME": "set time\r\n",
                    },
                },
            },
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )

    profile = load_user_profile("alice")
    assert profile is not None

    configs = load_command_configs(profile)
    assert [config.key for config in configs] == ["alice_cmds", "blank"]
    assert configs[0].commands["PING"] == "ping\r\n"


def test_remembered_username_round_trip(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))

    set_remembered_username("alice")
    assert get_remembered_username() == "alice"

    set_remembered_username(None)
    assert get_remembered_username() is None


def test_login_screen_creates_user_and_updates_main_ui(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))

    async def scenario() -> None:
        app = SerialHubApp()

        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, UserLoginScreen)

            login_input = app.screen.query_one("#login-username", Input)
            login_input.value = "alice"

            await pilot.click("#login-new-user")
            await pilot.pause()

            assert app.current_user is not None
            assert app.current_user.username == "alice"
            assert get_user_profile_path("alice").exists()
            assert str(app.query_one("#current-user-summary").renderable) == "user: alice"

    asyncio.run(scenario())


def test_remembered_user_skips_login_screen(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    create_user_profile("alice")
    set_remembered_username("alice")

    async def scenario() -> None:
        app = SerialHubApp()

        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.current_user is not None
            assert app.current_user.username == "alice"
            assert not isinstance(app.screen, UserLoginScreen)

    asyncio.run(scenario())


def test_logout_shortcut_returns_to_login_screen(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")
    set_remembered_username("alice")

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)

        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.current_user is not None

            await pilot.press("ctrl+q")
            await pilot.pause()

            assert app.current_user is None
            assert isinstance(app.screen, UserLoginScreen)
            assert get_remembered_username() is None

    asyncio.run(scenario())


def test_message_input_history_navigation_uses_user_history(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")
    get_user_message_history_path("alice").write_text(
        "[2026-04-19 10:00:00] first\r\n[2026-04-19 10:05:00] second\r\n",
        encoding="utf-8",
    )

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)

        async with app.run_test() as pilot:
            tx_input = app.query_one("#tx-input", Input)
            tx_input.focus()
            tx_input.value = "draft"
            await pilot.pause()

            await pilot.press("up")
            await pilot.pause()
            assert tx_input.value == "second"

            await pilot.press("up")
            await pilot.pause()
            assert tx_input.value == "first"

            await pilot.press("down")
            await pilot.pause()
            assert tx_input.value == "second"

            await pilot.press("down")
            await pilot.pause()
            assert tx_input.value == "draft"

    asyncio.run(scenario())


def test_tcp_input_history_navigation_uses_user_history(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path))
    profile = create_user_profile("alice")
    get_user_tcp_ip_history_path("alice").write_text(
        "[2026-04-19 10:00:00] 10.0.0.1\r\n[2026-04-19 10:05:00] 10.0.0.2\r\n",
        encoding="utf-8",
    )
    get_user_tcp_port_history_path("alice").write_text(
        "[2026-04-19 10:00:00] 4001\r\n[2026-04-19 10:05:00] 4059\r\n",
        encoding="utf-8",
    )

    async def scenario() -> None:
        app = SerialHubApp(require_login=False, startup_user=profile)

        async with app.run_test() as pilot:
            app.query_one("#connection-tabs").active = "connection-tcp"

            ip_input = app.query_one("#ip-input", Input)
            ip_input.focus()
            ip_input.value = "draft-host"
            await pilot.pause()

            await pilot.press("up")
            await pilot.pause()
            assert ip_input.value == "10.0.0.2"

            await pilot.press("up")
            await pilot.pause()
            assert ip_input.value == "10.0.0.1"

            await pilot.press("down")
            await pilot.pause()
            assert ip_input.value == "10.0.0.2"

            await pilot.press("down")
            await pilot.pause()
            assert ip_input.value == "draft-host"

            port_input = app.query_one("#port-input", Input)
            port_input.focus()
            port_input.value = "9999"
            await pilot.pause()

            await pilot.press("up")
            await pilot.pause()
            assert port_input.value == "4059"

            await pilot.press("up")
            await pilot.pause()
            assert port_input.value == "4001"

            await pilot.press("down")
            await pilot.pause()
            assert port_input.value == "4059"

            await pilot.press("down")
            await pilot.pause()
            assert port_input.value == "9999"

    asyncio.run(scenario())
