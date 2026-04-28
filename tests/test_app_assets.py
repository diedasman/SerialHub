from serialhub import __version__
from serialhub.app import SerialHubApp, load_app_css, load_ascii_logo


def test_packaged_logo_is_available() -> None:
    logo = load_ascii_logo()

    assert logo
    assert "::::::::" in logo


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
