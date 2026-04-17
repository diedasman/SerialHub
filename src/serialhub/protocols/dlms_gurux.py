from __future__ import annotations

import re
from typing import Any

from serialhub.protocols.base import DecodeResult, ProtocolDecoder

try:
    from gurux_dlms import GXDLMSConverter, GXDLMSTranslator # type: ignore
    from gurux_dlms.enums import TranslatorOutputType # type: ignore

    _GURUX_AVAILABLE = True
    _GURUX_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - import guard
    GXDLMSConverter = None  # type: ignore[assignment]
    GXDLMSTranslator = None  # type: ignore[assignment]
    TranslatorOutputType = None  # type: ignore[assignment]
    _GURUX_AVAILABLE = False
    _GURUX_IMPORT_ERROR = str(exc)


_OBIS_PATTERN = re.compile(r"\b\d{1,3}[\.:]\d{1,3}[\.:]\d{1,3}[\.:]\d{1,3}[\.:]\d{1,3}[\.:]\d{1,3}\b")


class GuruxDlmsDecoder(ProtocolDecoder):
    name = "dlms-gurux"

    def __init__(self) -> None:
        self.available = _GURUX_AVAILABLE
        self.import_error = _GURUX_IMPORT_ERROR

        self._translator: Any = None
        self._converter: Any = None

        if self.available:
            self._translator = GXDLMSTranslator(TranslatorOutputType.SIMPLE_XML)
            self._converter = GXDLMSConverter()

    def decode(self, payload: bytes) -> DecodeResult:
        if not payload:
            return DecodeResult(protocol=self.name, lines=[])

        lines: list[str] = []

        if not self.available:
            lines.append(f"GURUX unavailable: {self.import_error}")
            return DecodeResult(protocol=self.name, lines=lines)

        try:
            xml = self._translator.messageToXml(payload)
            lines.append("GURUX XML:")
            xml_lines = [line.strip() for line in str(xml).splitlines() if line.strip()]
            lines.extend(xml_lines[:14])
            if len(xml_lines) > 14:
                lines.append("... (truncated)")
        except Exception as exc:
            lines.append(f"GURUX frame decode failed: {exc}")

        obis_codes = self._extract_obis(payload)
        if obis_codes:
            lines.append("OBIS hints:")
            for code in obis_codes:
                lines.append(f"{code} -> {self._describe_obis(code)}")

        return DecodeResult(protocol=self.name, lines=lines)

    def _extract_obis(self, payload: bytes) -> list[str]:
        text = payload.decode("latin-1", errors="ignore")
        found = set()
        for match in _OBIS_PATTERN.findall(text):
            normalized = match.replace(":", ".")
            found.add(normalized)
        return sorted(found)

    def _describe_obis(self, logical_name: str) -> str:
        if not self._converter:
            return "converter not initialized"
        try:
            descriptions = self._converter.getDescription(logical_name)
            if descriptions:
                return str(descriptions[0]).replace("\r", " ").replace("\n", " ")
            return "No standard description found"
        except Exception as exc:
            return f"Lookup failed: {exc}"
