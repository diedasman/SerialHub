from __future__ import annotations

from serialhub.protocols.base import DecodeResult, ProtocolDecoder


class AsciiBinaryDecoder(ProtocolDecoder):
    name = "ascii-binary"

    def decode(self, payload: bytes) -> DecodeResult:
        if not payload:
            return DecodeResult(protocol=self.name, lines=[])

        ascii_line = "".join(chr(b) if 32 <= b < 127 else "." for b in payload)
        hex_line = payload.hex(" ").upper()
        return DecodeResult(protocol=self.name, lines=[f"ASCII: {ascii_line}", f"HEX: {hex_line}"])
