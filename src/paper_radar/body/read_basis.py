"""历史 Read 领取依据的固定键集;不编码 JSON、不解释当前资格。"""

from dataclasses import asdict, dataclass, fields
from typing import Self

from paper_radar.body.models import BodyError


@dataclass(frozen=True, slots=True)
class ReadBasis:
    root_id: str | None
    purpose: str | None
    decision_id: str | None
    pdf_id: str | None
    sample_id: str | None
    quality_basis: str | None
    review_id: str | None
    execution_source: str | None
    recorded_at: str | None

    def encode(self) -> dict[str, str | None]:
        return asdict(self)

    @classmethod
    def decode(cls, value: object) -> Self:
        if (
            type(value) is not dict
            or set(value) != {f.name for f in fields(cls)}
            or any(v is not None and type(v) is not str for v in value.values())
        ):
            raise BodyError("corrupt_reference")
        return cls(**value)
