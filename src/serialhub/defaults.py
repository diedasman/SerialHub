from __future__ import annotations

import re


def sanitize_log_filename(filename: str) -> str:
    safe_name = re.sub(r'[<>:\"/\\\\|?*]+', "_", filename).strip(" .")
    if not safe_name:
        safe_name = "serialhub-log"
    if not safe_name.lower().endswith(".txt"):
        safe_name += ".txt"
    return safe_name
