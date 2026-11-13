"""B-E5 独立 D1:真实 CLI 授权与无执行的静态预检。"""

import json
from pathlib import Path
from typing import IO, NoReturn

import pytest
from typer.testing import CliRunner, Result

from paper_radar.cli import app
from paper_radar.config import RuntimeConfigSnapshot
from paper_radar.experiment.egress import EgressAuthorization


def invoke(*args: str) -> Result:
    return CliRunner().invoke(app, ["experiment", *args])


def test_owner_can_append_and_revoke_root_bound_egress_without_echoing_reason(
    tmp_path: Path,
) -> None:
    from paper_radar.config import compile_config
    from tests.config_adapter_support import adapter_inputs

    settings, _, _ = adapter_inputs(tmp_path)
    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    snapshot = compile_config(settings, root / "paper-radar.sqlite3")
    missing = invoke("egress-status", "--root", str(root))
    assert missing.exit_code == 0, missing.output
    assert json.loads(missing.stdout)["enabled"] is False
    arguments = [
        "--root",
        str(root),
        "--snapshot",
        snapshot.snapshot_id,
        "--stage",
        "boundary",
        "--reason",
        "PRIVATE_OWNER_REASON",
    ]
    allowed = invoke("egress-authorize", *arguments)
    assert allowed.exit_code == 0, allowed.output
    status = json.loads(invoke("egress-status", "--root", str(root)).stdout)
    assert status["enabled"] is True and status["version"] == 1
    assert status["grants"][0]["stage"] == "boundary"
    revoked = invoke("egress-authorize", *arguments, "--disabled")
    assert revoked.exit_code == 0, revoked.output
    assert json.loads(revoked.stdout)["version"] == 2
    assert json.loads(revoked.stdout)["enabled"] is False
    assert "PRIVATE_OWNER_REASON" not in allowed.output + revoked.output
    assert "PRIVATE_OWNER_REASON" not in (root / "logs/runtime.jsonl").read_text()


def test_check_refuses_missing_stage_changed_model_and_copied_root(
    tmp_path: Path,
) -> None:
    import shutil

    import yaml

    from paper_radar.config import compile_config
    from tests.config_adapter_support import adapter_inputs

    settings, _, _ = adapter_inputs(tmp_path)
    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    database = root / "paper-radar.sqlite3"
    snapshot = compile_config(settings, database)

    def check(path: Path, ref: str, stage: str) -> Result:
        return invoke(
            "egress-check", "--root", str(path), "--snapshot", ref, "--stage", stage
        )

    missing = check(root, snapshot.snapshot_id, "boundary")
    assert missing.exit_code == 2 and "egress_not_authorized" in missing.output
    grant = invoke(
        "egress-authorize",
        "--root",
        str(root),
        "--snapshot",
        snapshot.snapshot_id,
        "--stage",
        "boundary",
        "--reason",
        "owner consent",
    )
    assert grant.exit_code == 0, grant.output
    assert check(root, snapshot.snapshot_id, "boundary").exit_code == 0
    assert "egress_scope_mismatch" in check(root, snapshot.snapshot_id, "value").output
    copied = tmp_path / "copy"
    shutil.copytree(root, copied)
    assert (
        "egress_scope_mismatch"
        in check(copied, snapshot.snapshot_id, "boundary").output
    )
    models_path = settings.parent / "models/models-v1.yaml"
    models = yaml.safe_load(models_path.read_text())
    models["version"] = "models-new"
    models["screening"]["model"] = "different-model"
    (models_path.parent / "models-new.yaml").write_text(yaml.safe_dump(models))
    settings.write_text(settings.read_text().replace("models-v1", "models-new"))
    changed = compile_config(settings, database)
    assert (
        "egress_model_mismatch" in check(root, changed.snapshot_id, "boundary").output
    )


def test_preflight_lists_both_slots_and_all_missing_resources_without_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.config import compile_config
    from tests.config_adapter_support import adapter_inputs
    from tests.test_doctor_process import inventory, logical

    settings, _, _ = adapter_inputs(tmp_path)
    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    snapshot = compile_config(settings, root / "paper-radar.sqlite3")
    from paper_radar.pi_execution.errors import ExecutionError

    def unavailable() -> NoReturn:
        raise ExecutionError("placement_unavailable")

    monkeypatch.setattr(
        "paper_radar.doctor.pi_exec.check_placement_readiness", unavailable
    )
    cwd = tmp_path / "cwd"
    monkeypatch.setattr("paper_radar.doctor.pi_exec.EXECUTION_CWD", cwd)
    monkeypatch.setattr("paper_radar.pi_execution.resources.EXECUTION_CWD", cwd)
    before = inventory(tmp_path), logical(root / "paper-radar.sqlite3")
    result = invoke(
        "preflight",
        "--root",
        str(root),
        "--snapshot",
        snapshot.snapshot_id,
        "--credentials-dir",
        str(tmp_path / "absent-credentials"),
        "--material-root",
        str(tmp_path / "materials"),
        "--install-root",
        str(tmp_path / "install"),
        "--attempt-root",
        str(tmp_path / "attempt"),
        "--model-root",
        str(tmp_path / "models"),
    )
    assert result.exit_code == 2, result.output
    for fragment in (
        "screening.supply",
        "reading.supply",
        "reading.adapter",
        "reading.admission",
        "egress.boundary",
        "egress.value",
        "egress.read",
        "docling",
        "host.memory",
        "model_snapshot_disk",
        "cgroup_v2",
        "memory_peak",
        "credentials_missing",
        "selection_missing",
    ):
        assert fragment in result.output
    assert "reading_configuration_missing" in result.output
    assert "egress_not_authorized" in result.output
    assert "自动配额=0" in result.output
    assert (inventory(tmp_path), logical(root / "paper-radar.sqlite3")) == before
    assert not (root / "logs").exists()


@pytest.mark.parametrize(
    "damage", ["hash", "format", "version", "previous", "kind", "reason"]
)
def test_damaged_authorization_chain_is_never_missing_or_default(
    tmp_path: Path, damage: str
) -> None:
    import sqlite3
    from contextlib import closing
    from hashlib import sha256

    from paper_radar.config import compile_config
    from tests.config_adapter_support import adapter_inputs

    settings, _, _ = adapter_inputs(tmp_path)
    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    database = root / "paper-radar.sqlite3"
    snapshot = compile_config(settings, database)
    args = [
        "--root",
        str(root),
        "--snapshot",
        snapshot.snapshot_id,
        "--stage",
        "boundary",
    ]
    assert (
        invoke("egress-authorize", *args, "--reason", "PRIVATE_REASON").exit_code == 0
    )
    with closing(sqlite3.connect(database)) as connection:
        raw = connection.execute(
            "SELECT raw_content FROM config_versions WHERE kind='experiment_egress'"
        ).fetchone()[0]
        value = json.loads(raw)
        if damage == "hash":
            connection.execute(
                "UPDATE config_versions SET raw_sha256=? "
                "WHERE kind='experiment_egress'",
                ("0" * 64,),
            )
        elif damage == "kind":
            connection.execute(
                "UPDATE config_versions SET kind='foreign' WHERE "
                "kind='experiment_egress'"
            )
        else:
            if damage == "format":
                value["format_version"] = True
            elif damage == "version":
                value["version"] = 2
            elif damage == "previous":
                value["previous_sha256"] = "0" * 64
            elif damage == "reason":
                value["reason"] = " "
            changed = json.dumps(value).encode()
            connection.execute(
                "UPDATE config_versions SET raw_content=?,raw_sha256=? "
                "WHERE kind='experiment_egress'",
                (changed, sha256(changed).hexdigest()),
            )
        connection.commit()
    for command in (
        ["egress-status", "--root", str(root)],
        ["egress-check", *args],
        ["egress-authorize", *args, "--reason", "new reason"],
    ):
        result = invoke(*command)
        assert result.exit_code == 2 and "egress_history_invalid" in result.output
        assert "PRIVATE_REASON" not in result.output


@pytest.mark.parametrize(
    "stage,provider,model,categories,reason",
    [
        (
            "reuse_assessment",
            "provider-a",
            "real-model",
            ("profile",),
            "egress_scope_mismatch",
        ),
        (
            "boundary",
            "different",
            "real-model",
            ("profile", "title_abstract"),
            "egress_model_mismatch",
        ),
        (
            "boundary",
            "provider-a",
            "real-model",
            ("profile",),
            "egress_category_mismatch",
        ),
        (
            "boundary",
            "provider-a",
            "real-model",
            ("profile", "title_abstract", "legal_body"),
            "egress_category_mismatch",
        ),
    ],
)
def test_fault_injected_call_scope_is_denied_before_any_execution(
    tmp_path: Path,
    stage: str,
    provider: str,
    model: str,
    categories: tuple[str, ...],
    reason: str,
) -> None:
    from paper_radar.config import compile_config
    from paper_radar.experiment.egress import EgressError, require_egress_authorization
    from paper_radar.experiment.root import ExperimentRoot
    from paper_radar.storage.database import DatabaseMode, open_database
    from tests.config_adapter_support import adapter_inputs
    from tests.test_doctor_process import logical

    settings, _, _ = adapter_inputs(tmp_path)
    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    database = root / "paper-radar.sqlite3"
    snapshot = compile_config(settings, database)
    assert (
        invoke(
            "egress-authorize",
            "--root",
            str(root),
            "--snapshot",
            snapshot.snapshot_id,
            "--stage",
            "boundary",
            "--reason",
            "owner consent",
        ).exit_code
        == 0
    )
    before = logical(database)
    engine = open_database(database, mode=DatabaseMode.READ_WRITE)
    try:
        with engine.begin() as connection:
            with pytest.raises(EgressError) as rejected:
                require_egress_authorization(
                    ExperimentRoot(root),
                    stage=stage,
                    provider=provider,
                    model=model,
                    categories=categories,
                    connection=connection,
                )
            assert rejected.value.reason == reason
    finally:
        engine.dispose()
    assert logical(database) == before


@pytest.mark.parametrize(
    "command", ["egress-authorize", "egress-status", "egress-check", "preflight"]
)
def test_new_help_does_not_access_network_sqlite_or_create_directories(
    tmp_path: Path, command: str
) -> None:
    from tests.config_test_support import run_cli

    result = run_cli(tmp_path, "experiment", command, "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    for fragment in (
        "参数",
        "副作用",
        "自动配额",
        "输出去向",
        "常见失败",
        "示例",
        "130",
    ):
        assert fragment in result.stdout
    assert list(tmp_path.iterdir()) == []


def prepared_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, RuntimeConfigSnapshot, list[str]]:
    from hashlib import sha256

    import yaml

    from paper_radar.body import BodyService
    from paper_radar.config import compile_config
    from paper_radar.experiment.preflight import HostPaths
    from paper_radar.pi_supply import activate_supply
    from tests import pi_supply_support
    from tests.config_extraction_support import EXTRACTION_YAML
    from tests.docling_runtime_support import environment

    environment(monkeypatch)
    monkeypatch.setattr(pi_supply_support, "PI", "1.4.0")
    source = pi_supply_support.inputs(tmp_path)
    settings = tmp_path / "config/settings.yaml"
    model_file = settings.parent / "models/models-v1.yaml"
    models = yaml.safe_load(model_file.read_text())
    models.update(version="models-b", format_version=2)
    models["screening"].update(provider="openai", sampling="provider_default")
    models["screening"].pop("temperature", None)
    models["screening"].pop("top_p", None)
    models["reading"] = {**models["screening"], "model": "independent-reading-model"}
    (model_file.parent / "models-b.yaml").write_text(yaml.safe_dump(models))
    values = yaml.safe_load(settings.read_text())
    values["models"] = "models-b"
    values["extraction"] = "extraction-v1"
    from paper_radar.contracts import export_frozen_contract

    values["read"] = "read-v1"
    values["prompts"]["reading"] = "v1"
    values["contracts"]["read"] = "v1"
    (settings.parent / "read").mkdir()
    (settings.parent / "read/read-v1.yaml").write_text(
        "version: read-v1\nchunking_version: v1\n"
    )
    (tmp_path / "prompts/reading").mkdir()
    (tmp_path / "prompts/reading/v1.md").write_text("Synthetic reading prompt\n")
    export_frozen_contract("read", "v1", tmp_path / "contracts")
    (settings.parent / "extraction").mkdir()
    extraction = yaml.safe_load(EXTRACTION_YAML)
    extraction["toolchain"] = "docling-2.135.0-cpu-v2"
    repos = {
        "layout": "docling-project/docling-layout-egret-medium",
        "table": "docling-project/docling-models",
        "formula": "docling-project/CodeFormulaV2",
    }
    deployment = []
    model_root = tmp_path / "models"
    for stage, model in extraction["models"].items():
        for member in model["files"]:
            path = model_root / repos[stage].replace("/", "--") / member["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic model member")
            member["sha256"] = sha256(b"synthetic model member").hexdigest()
        deployment.append(
            dict(
                repo_id=repos[stage],
                commit_sha=model["commit_sha"],
                files=sorted(model["files"], key=lambda member: member["path"]),
            )
        )
    (model_root / "deployment.json").write_text(
        json.dumps(dict(format_version=1, models=deployment))
    )
    (settings.parent / "extraction/extraction-v1.yaml").write_text(
        yaml.safe_dump(extraction)
    )
    settings.write_text(yaml.safe_dump(values))
    snapshot = compile_config(settings, source[0])
    prepared = pi_supply_support.prepare(
        tmp_path, (source[0], snapshot.snapshot_id, *source[2:])
    )
    activate_supply(source[0], prepared.supply_id, snapshot.snapshot_id)
    root = tmp_path / "experiment"
    root.mkdir()
    BodyService(source[0], root).register_root("experiment")
    source[0].rename(root / "paper-radar.sqlite3")
    assert invoke("init", "--root", str(root)).exit_code == 0
    waiver = CliRunner().invoke(
        app,
        [
            "live-evidence",
            "owner-waiver",
            "--database",
            str(root / "paper-radar.sqlite3"),
            "--enable",
            "--reason",
            "PRIVATE_WAIVER_REASON",
        ],
    )
    assert waiver.exit_code == 0, waiver.output
    allowed = invoke(
        "egress-authorize",
        "--root",
        str(root),
        "--snapshot",
        snapshot.snapshot_id,
        "--stage",
        "boundary",
        "--stage",
        "value",
        "--stage",
        "read",
        "--reason",
        "PRIVATE_EGRESS_REASON",
    )
    assert allowed.exit_code == 0, allowed.output
    credentials = tmp_path / "credentials"
    credentials.mkdir(mode=0o700)
    (credentials / "auth.json").write_bytes(b"PRIVATE_AUTH_CONTENT_NEVER_READ")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.setattr("paper_radar.doctor.pi_exec.EXECUTION_CWD", cwd)
    monkeypatch.setattr("paper_radar.pi_execution.resources.EXECUTION_CWD", cwd)
    monkeypatch.setattr("paper_radar.doctor.pi_exec.isolation_capability", lambda: 6)
    host = tmp_path / "host"
    host.mkdir()
    (host / "meminfo").write_text("MemAvailable: 16777216 kB\n")
    (host / "membership").write_text("0::/user-test\n")
    cgroup = host / "cgroups"
    (cgroup / "user-test").mkdir(parents=True)
    (cgroup / "cgroup.controllers").write_text("memory\n")
    for name, value in (
        ("memory.max", "8589934592"),
        ("memory.swap.max", "0"),
        ("cgroup.procs", ""),
        ("memory.peak", "4096"),
    ):
        (cgroup / "user-test" / name).write_text(value)
    monkeypatch.setattr(
        "paper_radar.experiment.preflight.HOST_PATHS",
        HostPaths(host / "meminfo", host / "membership", cgroup),
    )
    monkeypatch.setattr(
        "paper_radar.experiment.preflight.MIN_AVAILABLE_MEMORY_BYTES", 8 * 1024**3
    )
    # 任何读取凭据内容/启动进程/联网均使本测试失败;只允许 stat 元数据。
    original_open = Path.open

    def guarded_open(
        path: Path,
        mode: str = "r",
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> IO[bytes] | IO[str]:
        assert path != credentials / "auth.json", "静态预检读取了凭据内容"
        return original_open(path, mode, buffering, encoding, errors, newline)

    monkeypatch.setattr(Path, "open", guarded_open)

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("静态预检启动了外部动作")

    monkeypatch.setattr("subprocess.Popen", forbidden)
    monkeypatch.setattr("socket.socket", forbidden)
    args = [
        "--root",
        str(root),
        "--snapshot",
        snapshot.snapshot_id,
        "--credentials-dir",
        str(credentials),
        "--material-root",
        str(tmp_path / "materials"),
        "--install-root",
        str(tmp_path / "install"),
        "--attempt-root",
        str(tmp_path / "attempt"),
        "--model-root",
        str(model_root),
    ]
    return root, snapshot, args


def test_preflight_checks_independent_read_selection_and_preserves_waived_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_doctor_process import logical

    root, _, args = prepared_preflight(tmp_path, monkeypatch)
    before = preflight_inventory(tmp_path), logical(root / "paper-radar.sqlite3")
    result = invoke("preflight", *args)
    assert result.exit_code == 0, result.output
    assert (
        "check=screening.admission result=passed"
        " reason=owner_evidence_prerequisite_waived" in result.output
    )
    assert (
        "check=reading.admission result=passed"
        " reason=owner_evidence_prerequisite_waived" in result.output
    )
    assert "check=reading.admission_evidence result=not_assessed" in result.output
    assert "check=reading.adapter result=passed" in result.output
    assert "check=host.model_snapshot_disk result=passed" in result.output
    assert "check=host.memory result=passed" in result.output
    assert (
        preflight_inventory(tmp_path),
        logical(root / "paper-radar.sqlite3"),
    ) == before
    for forbidden in ("PRIVATE_", "independent-reading-model", str(root)):
        assert forbidden not in result.output


def preflight_inventory(
    root: Path,
) -> tuple[tuple[str, int, int | None, bytes | None], ...]:
    return tuple(
        sorted(
            (
                str(path.relative_to(root)),
                path.stat().st_mode,
                path.stat().st_size if path.is_file() else None,
                path.read_bytes()
                if path.is_file() and path.name != "auth.json"
                else None,
            )
            for path in root.rglob("*")
            if not path.name.endswith(("-shm", "-wal", "-journal"))
        )
    )


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("cwd", "cwd_missing"),
        ("credentials", "credentials_missing"),
        ("permissions", "credentials_invalid"),
        ("isolation", "isolation_unavailable"),
        ("waiver", "owner_waiver_history_invalid"),
        ("egress", "egress_not_authorized"),
        ("memory", "host_memory_insufficient"),
        ("cgroup", "cgroup_v2_unavailable"),
        ("peak", "memory_peak_unknown"),
        ("disk", "model_snapshot_space_insufficient"),
        ("deployment", "model_deployment_missing"),
        ("attempt", "attempt_root_overlap"),
        ("credential_root", "credentials_root_overlap"),
        ("install_root", "install_root_mismatch"),
    ],
)
def test_static_preflight_reports_each_blocker_without_calls_or_business_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str, reason: str
) -> None:
    import sqlite3
    from contextlib import closing
    from types import SimpleNamespace

    from paper_radar.pi_execution.errors import ExecutionError
    from tests.test_doctor_process import logical

    root, _, args = prepared_preflight(tmp_path, monkeypatch)
    if fault == "cwd":
        (tmp_path / "cwd").rmdir()
    elif fault == "credentials":
        (tmp_path / "credentials/auth.json").unlink()
    elif fault == "permissions":
        (tmp_path / "credentials").chmod(0o755)
    elif fault == "isolation":

        def unavailable() -> NoReturn:
            raise ExecutionError("isolation_unavailable")

        monkeypatch.setattr(
            "paper_radar.doctor.pi_exec.isolation_capability", unavailable
        )
    elif fault in {"waiver", "egress"}:
        kind = "owner_waiver" if fault == "waiver" else "experiment_egress"
        with closing(sqlite3.connect(root / "paper-radar.sqlite3")) as connection:
            if fault == "waiver":
                connection.execute(
                    "UPDATE config_versions SET raw_sha256='broken' WHERE kind=?",
                    (kind,),
                )
            else:
                connection.execute("DELETE FROM config_versions WHERE kind=?", (kind,))
            connection.commit()
        if fault == "waiver":

            def placement_missing() -> NoReturn:
                raise ExecutionError("placement_unavailable")

            monkeypatch.setattr(
                "paper_radar.doctor.pi_exec.check_placement_readiness",
                placement_missing,
            )
    elif fault == "memory":
        (tmp_path / "host/meminfo").write_text("MemAvailable: 1 kB\n")
    elif fault == "cgroup":
        (tmp_path / "host/cgroups/cgroup.controllers").unlink()
    elif fault == "peak":
        (tmp_path / "host/cgroups/user-test/memory.peak").unlink()
    elif fault == "disk":
        monkeypatch.setattr(
            "os.statvfs", lambda path: SimpleNamespace(f_bavail=0, f_frsize=4096)
        )
    elif fault == "deployment":
        (tmp_path / "models/deployment.json").unlink()
    elif fault == "attempt":
        args[args.index("--attempt-root") + 1] = str(root / "tmp")
    elif fault == "credential_root":
        args[args.index("--material-root") + 1] = str(tmp_path / "credentials")
    elif fault == "install_root":
        args[args.index("--install-root") + 1] = str(tmp_path / "different-install")
    before = preflight_inventory(tmp_path), logical(root / "paper-radar.sqlite3")
    result = invoke("preflight", *args)
    assert result.exit_code == (0 if fault == "peak" else 2), result.output
    assert reason in result.output
    assert (
        preflight_inventory(tmp_path),
        logical(root / "paper-radar.sqlite3"),
    ) == before
    assert "PRIVATE_" not in result.output


def test_read_slot_cannot_borrow_screening_provider_or_auth_compatibility(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import yaml

    from paper_radar.config import compile_config

    root, _, args = prepared_preflight(tmp_path, monkeypatch)
    settings = tmp_path / "config/settings.yaml"
    models = yaml.safe_load((settings.parent / "models/models-b.yaml").read_text())
    models["version"] = "models-reading-other"
    models["reading"]["provider"] = "other-provider"
    (settings.parent / "models/models-reading-other.yaml").write_text(
        yaml.safe_dump(models)
    )
    settings.write_text(
        settings.read_text().replace("models-b", "models-reading-other")
    )
    snapshot = compile_config(settings, root / "paper-radar.sqlite3")
    args[args.index("--snapshot") + 1] = snapshot.snapshot_id
    result = invoke("preflight", *args)
    assert (
        "check=screening.admission result=passed"
        " reason=owner_evidence_prerequisite_waived" in result.output
    )
    assert (
        "check=reading.admission result=invalid reason=auth_mode_unsupported"
        in result.output
    )
    assert (
        "check=egress.read result=invalid reason=egress_model_mismatch" in result.output
    )


def test_relocated_copy_can_validate_history_but_cannot_reuse_authorization(
    tmp_path: Path,
) -> None:
    import shutil

    from paper_radar.config import compile_config
    from paper_radar.experiment.egress import egress_authorization
    from tests.config_adapter_support import adapter_inputs

    settings, _, _ = adapter_inputs(tmp_path)
    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    snapshot = compile_config(settings, root / "paper-radar.sqlite3")
    args = ["--snapshot", snapshot.snapshot_id, "--stage", "boundary"]
    assert (
        invoke(
            "egress-authorize", "--root", str(root), *args, "--reason", "owner consent"
        ).exit_code
        == 0
    )
    copied = tmp_path / "restored"
    shutil.copytree(root, copied)
    assert egress_authorization(copied / "paper-radar.sqlite3") == egress_authorization(
        root / "paper-radar.sqlite3"
    )
    denied = invoke("egress-check", "--root", str(copied), *args)
    assert denied.exit_code == 2 and "egress_scope_mismatch" in denied.output


def test_concurrent_owner_actions_append_one_complete_chain(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from datetime import UTC, datetime

    from paper_radar.config import compile_config
    from paper_radar.experiment.egress import (
        egress_authorization,
        record_egress_authorization,
    )
    from paper_radar.experiment.root import ExperimentRoot
    from tests.config_adapter_support import adapter_inputs

    settings, _, _ = adapter_inputs(tmp_path)
    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    snapshot = compile_config(settings, root / "paper-radar.sqlite3")
    assert (
        invoke(
            "egress-authorize",
            "--root",
            str(root),
            "--snapshot",
            snapshot.snapshot_id,
            "--stage",
            "boundary",
            "--reason",
            "owner consent",
        ).exit_code
        == 0
    )
    original = egress_authorization(root / "paper-radar.sqlite3")
    now = datetime.now(UTC)

    def append(enabled: bool) -> EgressAuthorization:
        return record_egress_authorization(
            ExperimentRoot(root),
            enabled=enabled,
            reason="concurrent owner action",
            grants=original.grants,
            now=now,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        states = list(pool.map(append, [True, False]))
    assert sorted(state.version for state in states) == [2, 3]
    assert egress_authorization(root / "paper-radar.sqlite3").version == 3
