from textual.theme import Theme

SERIALHUB_THEME = Theme(
    name="serialhub",
    primary="#EB8F3C",
    secondary="#83D0C9",
    accent="#95BDB9",
    foreground="#F4F1E8",
    background="#0E1418",
    success="#4CAF50",
    warning="#F0B03F",
    error="#D65D5D",
    surface="#132028",
    panel="#0D171D",
    dark=True,
    variables={
        "block-cursor-text-style": "none",
        "footer-key-foreground": "#EB8F3C",
        "input-selection-background": "#83D0C9 35%",
    },
)
