"""Pi 来源接收的合成供给;不启动 Pi 或接触真实认证。"""

from datetime import UTC, datetime
from pathlib import Path

from paper_radar.config import compile_config
from paper_radar.papers import PaperFacts
from paper_radar.pi_supply import prepare_supply
from paper_radar.pi_supply.models import PrepareResult
from paper_radar.screening_tasks import PiRpcExecutionAudit, SuccessCandidate
from tests.a8_call_support import Archive
from tests.pi_supply_support import Run, inputs
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation

NOW = datetime(2026, 1, 1, tzinfo=UTC)
RAW = b'{"boundary":"in_scope","reason_zh":"Atmospheric processes."}'


class RpcSupplyRun(Run):
    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout: int,
        limit: int,
        pass_fds: tuple[int, ...] = (),
    ) -> bytes:
        result = super().run(
            argv, cwd=cwd, env=env, timeout=timeout, limit=limit, pass_fds=pass_fds
        )
        if "ci" in argv:
            package = cwd / "node_modules/@earendil-works/pi-coding-agent/package.json"
            package.write_bytes(package.read_bytes().replace(b"1.3.0", b"1.4.0"))
        return result.replace(b"1.3.0", b"1.4.0")


def source_archive(root: Path) -> tuple[Archive, PrepareResult]:
    database, _, request, download, _ = inputs(root)
    # inputs 使用真实配置编译;目录位置由配置夹具固定。
    settings = next(root.rglob("settings.yaml"))
    adapter = settings.parent / "adapters/pi-v1.yaml"
    adapter.write_bytes(
        adapter.read_bytes()
        .replace(b"1.3.0", b"1.4.0")
        .replace(b"version: pi-v1", b"version: pi-rpc-source-v1")
    )
    adapter.rename(adapter.with_name("pi-rpc-source-v1.yaml"))
    settings.write_text(settings.read_text().replace("pi-v1", "pi-rpc-source-v1"))
    models = settings.parent / "models/models-v1.yaml"
    models.write_text(
        models.read_text()
        .replace("models-v1", "models-source-v1")
        .replace("provider-a", "openai")
    )
    models.rename(models.with_name("models-source-v1.yaml"))
    settings.write_text(settings.read_text().replace("models-v1", "models-source-v1"))
    snapshot = compile_config(settings, database)
    download.content = {
        key.replace("1.3.0", "1.4.0"): raw.replace(b"1.3.0", b"1.4.0")
        if "nodejs.org" not in key
        else raw
        for key, raw in download.content.items()
    }
    supplied = prepare_supply(
        database,
        snapshot.snapshot_id,
        "screening",
        request,
        root / "install",
        data_root=root / "data",
        config_root=settings.parent,
        material_root=root / "materials",
        downloader=download,
        runner=RpcSupplyRun(),
    )
    saved = PaperFacts(database, root / "data").submit(
        observation(fields=screening_fields())
    )
    assert saved.paper_id and saved.version_id
    data = Archive(
        settings,
        database,
        root / "data",
        snapshot.snapshot_id,
        saved.paper_id,
        saved.version_id,
    )
    return data, supplied


def candidate(
    data: Archive, supplied: PrepareResult, raw: bytes = RAW
) -> SuccessCandidate:
    return SuccessCandidate(
        raw,
        executor_kind="pi_rpc",
        reported_provider="openai",
        reported_model="real-model",
        input_tokens=42,
        output_tokens=7,
        execution_audit=PiRpcExecutionAudit(
            supply_id=supplied.supply_id,
            install_id=supplied.install_id,
            pi_version="1.4.0",
            node_version="22.19.0",
            adapter_version="transport-v1",
            protocol_profile="pi-rpc-1.4.0-v1",
            launch_policy_version="pi-launch-v1",
            isolation_policy_version="landlock-v1",
            channel="prompt_only",
            auth_mode="chatgpt_subscription",
            credential_provider="openai",
            credential_source="owner_provisioned_dir",
            proxy_used=False,
            proxy_port=None,
        ),
    )
