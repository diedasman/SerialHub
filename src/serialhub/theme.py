from textual.theme import Theme  # type: ignore

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

# New Theme template for future use
# NEW_THEME = Theme(
#     name="new_theme",
#     primary="#000000",
#     secondary="#000000",
#     accent="#000000",
#     foreground="#000000",
#     background="#000000",
#     success="#000000",
#     warning="#000000",
#     error="#000000",
#     surface="#000000",
#     panel="#000000",
#     dark=False,
#     variables={
#         "block-cursor-text-style": "none",
#         "footer-key-foreground": "#000000",
#         "input-selection-background": "#000000 35%",
#     },
# )
