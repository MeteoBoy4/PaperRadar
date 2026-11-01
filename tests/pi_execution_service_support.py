"""S3 独立档案/生产服务组合;只在测试私有注入 Cwd/Live 合成事实。"""

from pathlib import Path

import pytest
import yaml

from paper_radar.config import compile_config
from paper_radar.papers import PaperFacts
from paper_radar.pi_execution.admission import AdmissionEvidence, EvidenceBinding
from paper_radar.pi_execution.service import PiExecution
from paper_radar.screening_tasks import RequestReceipt
from tests.pi_execution_support import launch_inputs
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation


def allow_synthetic(monkeypatch: pytest.MonkeyPatch) -> None:
    def evidence(binding: EvidenceBinding) -> AdmissionEvidence:
        return AdmissionEvidence(binding, True, True, True)

    monkeypatch.setattr("paper_radar.pi_execution.service._evidence_for", evidence)


def service_inputs(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mode: str = "normal",
    legacy: bool = False,
) -> tuple[PiExecution, RequestReceipt, Path]:
    peer = (
        Path(__file__)
        .with_name("pi_execution_rpc_peer.py")
        .read_text()
        .replace("__MODE__", mode)
    )
    peer = peer.replace("__DATABASE__", str(root / "db.sqlite3")).replace(
        "__CREDENTIALS__", str(root / "credentials/auth.json")
    )
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
