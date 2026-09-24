"""存储层使用的版本记录。它独立于配置编译类型。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VersionRecord:
    kind: str
    name: str
    version: str
    raw: bytes

    @property
    def raw_sha256(self) -> str:
        return hashlib.sha256(self.raw).hexdigest()
