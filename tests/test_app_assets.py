from serialhub.app import SerialHubApp, load_ascii_logo


def test_packaged_logo_is_available() -> None:
    logo = load_ascii_logo()

    assert logo
    assert "::::::::" in logo


def test_workspace_placeholder_uses_packaged_logo() -> None:
    app = SerialHubApp(require_login=False)

    assert app._workspace_placeholder_text() == app._logo_content
    assert app._logo_content
