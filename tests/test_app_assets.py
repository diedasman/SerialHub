from serialhub import __version__
from serialhub.app import SerialHubApp, load_app_css, load_ascii_logo, load_manual_markdown


def test_packaged_logo_is_available() -> None:
    logo = load_ascii_logo()

    assert logo
    assert len(logo.splitlines()) >= 2


def test_workspace_placeholder_uses_packaged_logo() -> None:
    app = SerialHubApp(require_login=False)

    assert app._workspace_placeholder_text() == app._logo_content
    assert app._logo_content


def test_app_version_text_matches_package_version() -> None:
    app = SerialHubApp(require_login=False)

    assert app._app_version_text() == f"v{__version__}"


def test_packaged_css_is_available() -> None:
    css = load_app_css()

    assert css
    assert "Screen {" in css
    assert SerialHubApp.CSS == css


def test_packaged_manual_is_available() -> None:
    manual = load_manual_markdown("connection.md")

    assert manual
    assert "## Connection" in manual


def test_packaged_monitor_manual_is_available() -> None:
    manual = load_manual_markdown("monitor.md")

    assert manual
    assert "The **MONITOR** panel" in manual


def test_packaged_functions_manual_is_available() -> None:
    manual = load_manual_markdown("functions.md")

    assert manual
    assert "## User Functions" in manual
    assert "Config Editor" in manual
