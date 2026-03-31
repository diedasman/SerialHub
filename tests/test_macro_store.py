from __future__ import annotations

from pathlib import Path

from serialhub.core.macro_store import MacroStore
from serialhub.core.models import MacroDefinition


def test_macro_store_roundtrip(tmp_path: Path) -> None:
    store = MacroStore(tmp_path / "macros.json")
    macros = [
        MacroDefinition(name="Ping", payload="PING", hex_mode=False, delay_ms=0),
        MacroDefinition(name="HexCmd", payload="7E A0 01", hex_mode=True, delay_ms=25),
    ]

    store.save(macros)
    loaded = store.load()

    assert [m.name for m in loaded] == ["Ping", "HexCmd"]
    assert loaded[1].hex_mode is True
    assert loaded[1].delay_ms == 25
