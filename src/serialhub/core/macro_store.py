from __future__ import annotations

import json
from pathlib import Path

from serialhub.core.models import MacroDefinition


class MacroStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[MacroDefinition]:
        if not self.path.exists():
            return []

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

        if not isinstance(data, list):
            return []

        macros: list[MacroDefinition] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            macro = MacroDefinition.from_dict(entry)
            if macro.name and macro.payload:
                macros.append(macro)
        return macros

    def save(self, macros: list[MacroDefinition]) -> None:
        payload = [macro.to_dict() for macro in macros]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
