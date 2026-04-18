from serialhub.app import SerialHubApp


def test_app_uses_dark_theme_by_default() -> None:
    app = SerialHubApp()
    assert app.theme_mode == "dark"
    assert app.theme == "app-dark"
    assert "app-dark" in app.available_themes
    assert "app-light" in app.available_themes


def test_toggle_theme_switches_between_dark_and_light() -> None:
    app = SerialHubApp()
    app.action_toggle_theme()
    assert app.theme_mode == "light"
    assert app.theme == "app-light"

    app.action_toggle_theme()
    assert app.theme_mode == "dark"
    assert app.theme == "app-dark"
