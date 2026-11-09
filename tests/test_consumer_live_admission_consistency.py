"""同一冻结账本驱动两个正式消费者;同格同源,格与档不借证据。"""

from datetime import datetime
from pathlib import Path

import pytest

from paper_radar.live_evidence.evidence import ExecutionBinding
from paper_radar.live_evidence.lifecycle import EvidenceLifecycle, use_for_id
from paper_radar.live_evidence.receipt import UseId
from paper_radar.live_evidence.service import AdmissionProjection, AdmissionRequest
from paper_radar.live_evidence.types import BindingComponent, Consumer
from paper_radar.pi_execution.admission import load_admission_evidence
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.read_tasks import ReadAnalysis
from paper_radar.screening_tasks import SuccessReceipt
from tests.live_evidence_ledger_support import NOW
from tests.read_execution_support import setup
from tests.screening_live_admission_support import product_inputs, protected_admission


@pytest.mark.parametrize(
    ("uses", "activate", "revoke_read", "expected"),
    [
        (("boundary-low", "read-low"), True, False, (True, True)),
        (("boundary-low",), True, False, (True, False)),
        (("read-low",), True, False, (False, True)),
        (("boundary-high", "read-high"), True, False, (False, False)),
        (("boundary-low", "read-low"), False, False, (False, False)),
        (("boundary-low", "read-low"), True, True, (True, False)),
    ],
)
def test_same_ledger_authority_and_independent_consumer_cells(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    uses: tuple[UseId, ...],
    activate: bool,
    revoke_read: bool,
    expected: tuple[bool, bool],
) -> None:
    from paper_radar.pi_execution import admission_guard

    ledger, evidence_receipt, components = protected_admission(
        tmp_path / "evidence", monkeypatch, uses=uses, activate=activate
    )
    if revoke_read:
        EvidenceLifecycle(ledger).tighten(
            evidence_receipt.receipt_id, "read-low", now=NOW
        )
    load = load_admission_evidence
    binding = ExecutionBinding(tuple(components.items()))
    requests = tuple(
        AdmissionRequest(use_for_id(use), binding, frozenset(BindingComponent))
        for use in ("boundary-low", "read-low")
    )
    frozen = tuple(load(request, now=NOW) for request in requests)
    assert tuple(projection.decision.executable for projection in frozen) == expected
    observed: list[tuple[AdmissionRequest, AdmissionProjection]] = []

    def capture(request: AdmissionRequest, *, now: datetime) -> AdmissionProjection:
        projection = load(request, now=now)
        observed.append((request, projection))
        return projection

    monkeypatch.setattr(admission_guard, "load_admission_evidence", capture)
    screening, receipt, _ = product_inputs(tmp_path / "screening", monkeypatch)
    screening._now = lambda: NOW
    if expected[0]:
        assert isinstance(screening.run_attempt(receipt.receipt_id), SuccessReceipt)
    else:
        with pytest.raises(ExecutionError, match="evidence_missing"):
            screening.run_attempt(receipt.receipt_id)
    reading, task, _ = setup(tmp_path / "reading", monkeypatch)
    reading._now = lambda: NOW
    if expected[1]:
        assert isinstance(reading.run_attempt(task.task_id), ReadAnalysis)
    else:
        with pytest.raises(ExecutionError, match="evidence_missing"):
            reading.run_attempt(task.task_id)
    for consumer, request, projection in zip(
        (Consumer.BOUNDARY, Consumer.READ), requests, frozen, strict=True
    ):
        actual = [entry for entry in observed if entry[0].use.consumer is consumer]
        assert actual
        actual_request, actual_projection = actual[0]
        assert actual_request.use == request.use
        assert dict(actual_request.binding.components) == components
        assert actual_request.checked_components == frozenset(BindingComponent)
        assert actual_projection == projection
    if expected[0] == expected[1] and not revoke_read:
        assert frozen[0].decision.capabilities == frozen[1].decision.capabilities
        assert frozen[0].decision.reasons == frozen[1].decision.reasons
    assert reading.tasks.task(task.task_id).remaining_attempts == (
        1 if expected[1] else 2
    )
