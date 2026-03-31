from serialhub.app import SerialHubApp


def test_app_uses_custom_theme() -> None:
    app = SerialHubApp()
    assert app.theme == "serialhub"
    assert "serialhub" in app.available_themes
