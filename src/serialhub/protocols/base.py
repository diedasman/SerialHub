from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(slots=True)
class DecodeResult:
    protocol: str
    lines: list[str] = field(default_factory=list)


class ProtocolDecoder(ABC):
    name: str = "base"

    @abstractmethod
    def decode(self, payload: bytes) -> DecodeResult:
        raise NotImplementedError
