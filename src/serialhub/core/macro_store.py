from __future__ import annotations

import json
from pathlib import Path

from serialhub.core.models import MacroDefinition


class MacroStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[MacroDefinition]:
        if self.path.is_dir():
            return self._load_directory()
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
            if macro.name and macro.commands:
                macros.append(macro)
        return macros

    def save(self, macros: list[MacroDefinition]) -> None:
        if self.path.suffix:
            payload = [
                {
                    **macro.to_dict(),
                    "hex_mode": macro.hex_mode,
                    "delay_ms": macro.delay_ms,
                }
                for macro in macros
            ]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return

        self.path.mkdir(parents=True, exist_ok=True)
        for macro in macros:
            if not macro.name:
                continue
            target = self.path / f"{macro.name}.json"
            self.save_macro(target, macro)

    def _load_directory(self) -> list[MacroDefinition]:
        macros: list[MacroDefinition] = []
        for path in sorted(self.path.glob("*.json")):
            macro = self.load_macro(path)
            if macro is not None and macro.name and macro.commands:
                macros.append(macro)
        return macros

    @staticmethod
    def load_macro(path: Path) -> MacroDefinition | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        macro = MacroDefinition.from_dict(data)
        macro.path = path
        return macro

    @staticmethod
    def save_macro(path: Path, macro: MacroDefinition) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(macro.to_dict(), indent=4) + "\n", encoding="utf-8")
