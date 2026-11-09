"""独立Read/Pi组合夹具;替身仅在供给进程边界与私有准入接缝。"""

import shutil
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from paper_radar.config import compile_config
from paper_radar.pi_execution.admission import AdmissionEvidence, EvidenceBinding
from paper_radar.pi_execution.resources import ExecutionRoots
from paper_radar.pi_supply import activate_supply, list_supplies
from paper_radar.read_execution import ReadExecution
from paper_radar.read_tasks import ReadTask
from paper_radar.runtime_logging import Sink
from paper_radar.runtime_logging.events import Clock
from tests.pi_execution_support import TOKEN
from tests.pi_rpc_source_support import RpcSupplyRun
from tests.read_tasks_support import ready


def allow_engineering_path(
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
        "paper_radar.pi_execution.admission_checkpoints.request_time_tick", lambda: True
    )
    monkeypatch.setattr(
        "paper_radar.pi_execution.admission_checkpoints.recheck_admission_request",
        lambda request, *, now: None,
    )


def setup(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mode: str = "normal",
    sink: Sink | None = None,
    clock: Clock | None = None,
) -> tuple[ReadExecution, ReadTask, Path]:
    from tests.pi_execution_service_support import deny_default_live_io

    deny_default_live_io(root, monkeypatch)
    import json

    peer = Path(__file__).with_name("read_execution_peer.py").read_text()
    peer = peer.replace("__MODE__", mode)
    peer = peer.replace("__DATABASE__", str(root / "db.sqlite3"))
    peer = peer.replace("__CREDENTIALS__", str(root / "credentials/auth.json"))
    original = RpcSupplyRun.run

    def run(
        self: RpcSupplyRun,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout: int,
        limit: int,
        pass_fds: tuple[int, ...] = (),
    ) -> bytes:
        result = original(
            self,
            argv,
            cwd=cwd,
            env=env,
            timeout=timeout,
            limit=limit,
            pass_fds=pass_fds,
        )
        if "ci" in argv:
            node = cwd.parent / "node/bin/node"
            node.chmod(0o755)
            shutil.copyfile(Path(sys.executable).resolve(), node)
            (
                cwd / "node_modules/@earendil-works/pi-coding-agent/dist/cli.js"
            ).write_text(peer)
        return result

    monkeypatch.setattr(RpcSupplyRun, "run", run)
    data, _, extraction = ready(root)
    source = data.settings.parent / "models/models-read-v1.yaml"
    models = yaml.safe_load(source.read_text())
    models.update(version="models-read-default-v1", format_version=2)
    for slot in ("screening", "reading"):
        models[slot].pop("temperature", None)
        models[slot].pop("top_p", None)
        models[slot]["sampling"] = "provider_default"
    (source.parent / "models-read-default-v1.yaml").write_text(yaml.safe_dump(models))
    data.settings.write_text(
        data.settings.read_text().replace("models-read-v1", "models-read-default-v1")
    )
    snapshot = compile_config(data.settings, data.database)
    supply = list_supplies(data.database)[0]
    activate_supply(data.database, supply.supply_id, snapshot.snapshot_id)
    cwd = root / "cwd"
    cwd.mkdir()
    credentials = root / "credentials"
    credentials.mkdir(mode=0o700)
    (credentials / "auth.json").write_text(json.dumps({"token": TOKEN}))
    monkeypatch.setattr("paper_radar.pi_execution.resources.EXECUTION_CWD", cwd)
    from paper_radar.pi_execution import isolation

    monkeypatch.setattr(
        isolation,
        "_RUNTIME_PATHS",
        (
            *isolation._RUNTIME_PATHS,
            Path(sys.base_prefix)
            / f"lib/python{sys.version_info.major}.{sys.version_info.minor}",
        ),
    )
    service = ReadExecution(
        data.database,
        data.data_root,
        roots=ExecutionRoots(
            data.data_root, data.settings.parent, root / "materials", root / "install"
        ),
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
        sink=sink,
        clock=clock,
    )
    task: ReadTask = service.tasks.register(
        data.paper_id,
        snapshot_id=snapshot.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="read",
    )
    return service, task, credentials
