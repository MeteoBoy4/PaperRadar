"""封印采集器与所有者入口之间的短时现场观察,不赋予证据资格。"""

from datetime import datetime, timedelta
from typing import Self

from pydantic import model_validator

from paper_radar.live_evidence.evidence import ExecutionBinding
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
from paper_radar.live_evidence.receipt import Digest, WireModel, canonical_bytes
from paper_radar.live_evidence.time_policy import clock_reason
from paper_radar.live_evidence.types import BindingComponent

OBSERVATION_FILENAME = "current-observation.json"
OBSERVATION_MAX_AGE = timedelta(seconds=60)


class CurrentObservation(WireModel):
    observed_at: datetime
    binding: dict[BindingComponent, Digest]
    checked_components: tuple[BindingComponent, ...]

    @model_validator(mode="after")
    def complete_binding(self) -> Self:
        ExecutionBinding(tuple(self.binding.items()))
        if len(set(self.checked_components)) != len(self.checked_components):
            raise ValueError("observation_component_duplicate")
        if self.observed_at.tzinfo is None:
            raise ValueError("evidence_time_invalid")
        return self

    def validate_time(self, *, now: datetime) -> None:
        invalid = clock_reason(now, None)
        if invalid is not None:
            raise LedgerError.clock(invalid)
        if self.observed_at > now:
            raise LedgerError("evidence_time_future")
        if now - self.observed_at > OBSERVATION_MAX_AGE:
            raise LedgerError("observation_stale")


def load_current_observation(
    ledger: EvidenceLedger, *, now: datetime
) -> CurrentObservation:
    from pydantic import ValidationError

    data = ledger._read_source(ledger.root / "inbox" / OBSERVATION_FILENAME)
    try:
        observation = CurrentObservation.model_validate_json(data)
    except ValidationError as error:
        raise LedgerError("observation_invalid") from error
    if canonical_bytes(observation) != data:
        raise LedgerError("source_integrity")
    observation.validate_time(now=now)
    return observation
