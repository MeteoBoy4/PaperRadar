"""S3 独立档案/生产服务组合;只在测试私有注入 Cwd/Live 合成事实。"""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from paper_radar.config import compile_config
from paper_radar.papers import PaperFacts
from paper_radar.pi_execution.admission import AdmissionEvidence, EvidenceBinding
from paper_radar.pi_execution.service import PiExecution
from paper_radar.screening_tasks import RequestReceipt
from tests.config_adapter_support import adapter_inputs
from tests.pi_execution_support import launch_inputs
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation


def deny_default_live_io(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """未显式替换的真实OS来源必须拒绝;不覆盖已安装的protected fixture。"""
    from paper_radar.live_evidence import service
    from paper_radar.live_evidence.intents import ProtectedIntentLog
    from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError

    if (
        getattr(service._run_helper, "__module__", None),
        getattr(service._run_helper, "__name__", None),
    ) != (
        "paper_radar.live_evidence.service",
        "_run_helper",
    ):
        return

    def unavailable_refresh() -> None:
        raise LedgerError("observation_unavailable")

    monkeypatch.setattr(
        "paper_radar.pi_execution.admission_checkpoints.request_observation_refresh",
        unavailable_refresh,
    )
    missing = EvidenceLedger(root / "absent-live-evidence")
    monkeypatch.setattr(service, "_ledger", lambda: missing)
    monkeypatch.setattr(
        service,
        "_intents",
        lambda: ProtectedIntentLog(root / "absent-intents/pending.jsonl"),
    )
    monkeypatch.setattr(service, "_run_helper", lambda args: False)
    monkeypatch.setattr(
        "paper_radar.pi_execution.current_binding.EvidenceLedger", lambda: missing
    )


def allow_synthetic(
    monkeypatch: pytest.MonkeyPatch,
    evidence: Callable[[EvidenceBinding], AdmissionEvidence | None] | None = None,
) -> None:
    """工程测试显式替换准入边界;没有产品可调用的合成证据入口。"""
    from paper_radar.live_evidence.evaluator import AdmissionDecision
    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.service import AdmissionProjection, AdmissionRequest
    from paper_radar.live_evidence.types import AdmissionUse, BindingComponent
    from paper_radar.pi_execution.admission import admit
    from paper_radar.pi_execution.errors import ExecutionError

    def request(
        database: Path,
        binding: EvidenceBinding,
        *,
        use: AdmissionUse,
        credentials_dir: Path,
        now: datetime,
    ) -> AdmissionRequest:
        result = (
            evidence(binding)
            if evidence is not None
            else AdmissionEvidence(binding, True, True, True)
        )
        reason = admit(binding, result)
        if reason is not None:
            raise ExecutionError(reason)
        return AdmissionRequest(
            use,
            ExecutionBinding(
                tuple((component, "b" * 64) for component in BindingComponent)
            ),
            frozenset(BindingComponent),
        )

    monkeypatch.setattr(
        "paper_radar.pi_execution.admission_checkpoints.build_admission_request",
        request,
    )
    monkeypatch.setattr(
        "paper_radar.pi_execution.admission_guard.load_admission_evidence",
        lambda request, *, now: AdmissionProjection(
            AdmissionDecision(request.use, "live-admission-v1", (), ()), now, False
        ),
    )
    monkeypatch.setattr(
        "paper_radar.pi_execution.admission_checkpoints.request_observation_refresh",
        lambda: None,
    )
    monkeypatch.setattr(
        "paper_radar.pi_execution.admission_checkpoints.request_time_tick", lambda: True
    )
    monkeypatch.setattr(
        "paper_radar.pi_execution.admission_checkpoints.recheck_admission_request",
        lambda request, *, now: None,
    )


def service_inputs(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mode: str = "normal",
    legacy: bool = False,
    thinking_level: str = "low",
) -> tuple[PiExecution, RequestReceipt, Path]:
    deny_default_live_io(root, monkeypatch)
    peer = (
        Path(__file__)
        .with_name("pi_execution_rpc_peer.py")
        .read_text()
        .replace("__MODE__", mode)
    )
    peer = peer.replace("__DATABASE__", str(root / "db.sqlite3")).replace(
        "__CREDENTIALS__", str(root / "credentials/auth.json")
    )
    from tests import pi_supply_support

    original_inputs = adapter_inputs

    def registered_tier(path: Path) -> tuple[Path, Path, Path]:
        settings, adapter, database = original_inputs(path)
        content = yaml.safe_load(adapter.read_text())
        content["thinking_level"] = thinking_level
        adapter.write_text(yaml.safe_dump(content))
        return settings, adapter, database

    monkeypatch.setattr(pi_supply_support, "adapter_inputs", registered_tier)
    database, _, roots, credentials, _ = launch_inputs(root, monkeypatch, peer=peer)
    settings = root / "config/settings.yaml"
    source = root / "config/models/models-v1.yaml"
    models = yaml.safe_load(source.read_text())
    models["version"] = "models-v2"
    models["screening"]["provider"] = "openai"
    if not legacy:
        models["format_version"] = 2
        models["screening"].pop("temperature", None)
        models["screening"].pop("top_p", None)
        models["screening"]["sampling"] = "provider_default"
    (source.parent / "models-v2.yaml").write_text(yaml.safe_dump(models))
    settings.write_text(settings.read_text().replace("models-v1", "models-v2"))
    snapshot = compile_config(settings, database)
    paper = PaperFacts(database, root / "data").submit(
        observation(fields=screening_fields())
    )
    service = PiExecution(
        database,
        root / "data",
        roots=roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
    )
    receipt = service.tasks.register(
        dict(
            paper_id=paper.paper_id,
            snapshot_id=snapshot.snapshot_id,
            stage="boundary",
            source="scheduled",
            scheduled_day="2026-01-01",
        )
    )
    return service, receipt, credentials
