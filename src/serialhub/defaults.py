from __future__ import annotations

import re

DEFAULT_SCRIPT_SOURCE = (
    "# SerialHub script sample\n"
    "# send('7E A0 07 03 21 93 0F 01 7E', hex_mode=True)\n"
    "\n"
    "@on_pattern(r\"READY\")\n"
    "def when_ready(match, text, raw):\n"
    "    log(f\"READY seen: {text.strip()}\")\n"
    "\n"
    "def main():\n"
    "    log('Script started')\n"
)


def sanitize_log_filename(filename: str) -> str:
    safe_name = re.sub(r'[<>:\"/\\\\|?*]+', "_", filename).strip(" .")
    if not safe_name:
        safe_name = "serialhub-log"
    if not safe_name.lower().endswith(".txt"):
        safe_name += ".txt"
    return safe_name
