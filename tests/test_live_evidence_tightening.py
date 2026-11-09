"""收紧 helper 的动作白名单与产品零授予路径。"""

from pathlib import Path

import pytest

from paper_radar.live_evidence import service, tightening
from paper_radar.live_evidence.evidence import ExecutionBinding
from paper_radar.live_evidence.lifecycle import use_for_id
from paper_radar.live_evidence.types import BindingComponent
from tests.live_evidence_ledger_support import NOW, receipt


@pytest.mark.parametrize(
    "arguments",
    [
        ["activate"],
        ["receive"],
        ["restore"],
        ["initialize"],
        ["tick", "--now", "future"],
        ["revoke", "bad", "boundary-low", "unknown", ""],
        ["revoke", "a" * 16, "undefined", "unknown", ""],
        ["revoke", "a" * 16, "boundary-low", "/arbitrary/path", ""],
        ["revoke", "a" * 16, "boundary-low", "unknown", "grant"],
    ],
)
def test_helper_rejects_every_non_tightening_or_uncontrolled_argument(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
) -> None:
    def forbidden() -> None:
        raise AssertionError("非法操作不应打开账本")

    monkeypatch.setattr(tightening, "EvidenceLedger", forbidden)
    assert tightening.tightening_main(arguments) == 2


def test_missing_ledger_still_persists_pending_revocation_across_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.screening_live_admission_support import protected_admission

    ledger, _, _ = protected_admission(tmp_path / "evidence", monkeypatch)
    ledger.database.unlink()
    monkeypatch.setattr(service, "_run_helper", lambda args: False)
    assert (
        service.request_revocation(receipt().receipt_id, "boundary-low", now=NOW)
        is False
    )
    request = service.AdmissionRequest(
        use_for_id("boundary-low"),
        ExecutionBinding(tuple(receipt().binding.items())),
        frozenset(BindingComponent),
    )
    result = service.load_admission_evidence(request, now=NOW)
    assert not result.decision.executable
    assert result.pending_revocation is True
    assert [reason.token for reason in result.decision.reasons] == ["ledger_untrusted"]
