"""历史回放证明等级只描述实际可复核的材料范围。"""

from typing import Literal

from paper_radar.fixture_audit.abstract_models import AbstractAuditView
from paper_radar.fixture_audit.models import FrozenModel


class ReplayProof(FrozenModel):
    execution_id: str
    level: Literal["material_reparsed", "execution_facts_only"]
    outcome_unknown: bool = False


class AuditReplay(FrozenModel):
    status: Literal["verified"] = "verified"
    view: AbstractAuditView
    semantic_sha256: str
    proofs: tuple[ReplayProof, ...]
