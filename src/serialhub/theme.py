from __future__ import annotations

from textual.theme import Theme  # type: ignore

DEFAULT_THEME_MODE = "dark"

APP_THEME_DARK = Theme(
    name="app-dark",
    primary="#15A24A",
    secondary="#3F4A4A",
    accent="#15A24A",
    foreground="#E6EDF3",
    background="#0F1419",
    surface="#151B22",
    panel="#1C232B",
    success="#3FAE66",
    warning="#E0A93A",
    error="#E06C75",
    dark=True,
    variables={
        "block-cursor-text-style": "none",
        "footer-key-foreground": "#EB8F3C",
        "input-selection-background": "#83D0C9 35%",
    },
)

APP_THEME_LIGHT = Theme(
    name="app-light",
    primary="#15A24A",
    secondary="#4D5C5C",
    accent="#15A24A",
    foreground="#00080E",
    background="#EFECE6",
    surface="#FFFFFF",
    panel="#D8D3CC",
    success="#2F8F4E",
    warning="#C98A1E",
    error="#C24B4B",
    dark=False,
    variables={
        "block-cursor-text-style": "none",
        "footer-key-foreground": "#15A24A",
        "input-selection-background": "#15A24A 25%",
    },
)

APP_THEMES = {
    "dark": APP_THEME_DARK,
    "light": APP_THEME_LIGHT,
}


def normalize_theme_mode(value: object | None) -> str:
    if isinstance(value, str) and value.lower() in APP_THEMES:
        return value.lower()
    return DEFAULT_THEME_MODE


def resolve_textual_theme_name(mode: str) -> str:
    return APP_THEMES[normalize_theme_mode(mode)].name


def toggle_theme_mode(mode: str) -> str:
    return "light" if normalize_theme_mode(mode) == "dark" else "dark"
