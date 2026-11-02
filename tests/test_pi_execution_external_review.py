"""#140 外部审阅新增公共边界回归;不扩展旧195/冻结回执分母。"""

from pathlib import Path

import pytest


def test_new_execution_audit_has_versioned_prompt_only_channel(tmp_path: Path) -> None:
    from paper_radar.screening_tasks import ScreeningTasks, SuccessReceipt
    from tests.a8_call_support import request_for
    from tests.pi_rpc_source_support import NOW, candidate, source_archive

    data, supplied = source_archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    proposed = candidate(data, supplied)
    assert proposed.execution_audit is not None
    assert proposed.execution_audit.channel == "prompt_only"
    assert "protocol" not in proposed.execution_audit.model_dump()
    success = tasks.run_once(receipt.receipt_id, lambda *_: proposed)
    assert isinstance(success, SuccessReceipt)
    audit = tasks.load_success(success.success_id).audit
    assert audit["format_version"] == 3
    assert audit["channel"] == "prompt_only"
    assert "protocol" not in audit


@pytest.mark.parametrize(
    "damage", [None, "channel", "both", "version", "missing", "float"]
)
def test_literal_legacy_audit_queries_and_restores_with_exact_old_identity(
    tmp_path: Path, damage: str | None
) -> None:
    import hashlib
    import json
    import sqlite3
    from contextlib import closing

    from paper_radar.backup import BackupError, create_backup
    from paper_radar.backup.restore import restore_backup
    from paper_radar.screening_tasks import (
        ScreeningTasks,
        SuccessReceipt,
        TaskError,
        TaskReason,
    )
    from tests.a8_call_support import request_for
    from tests.pi_rpc_source_support import NOW, RAW, candidate, source_archive

    data, supplied = source_archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    success = tasks.run_once(receipt.receipt_id, lambda *_: candidate(data, supplied))
    assert isinstance(success, SuccessReceipt)
    # 独立的历史格式字面量;只替换本次档案注册拥有的两个标识符。
    historical = (
        Path("tests/fixtures/pi_rpc/legacy-format2-audit.json")
        .read_text()
        .strip()
        .replace("INSTALL_ID", supplied.install_id)
        .replace("SUPPLY_ID", supplied.supply_id)
    )
    audit = json.loads(historical)
    if damage == "channel":
        audit["channel"] = audit.pop("protocol")
    elif damage == "both":
        audit["channel"] = "prompt_only"
    elif damage == "version":
        audit["format_version"] = 3
    elif damage == "missing":
        del audit["protocol"]
    elif damage == "float":
        audit["format_version"] = 2.0
    stored = json.dumps(
        audit, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    digest = hashlib.sha256(
        json.dumps(
            {"raw_sha256": hashlib.sha256(RAW).hexdigest(), "audit": audit},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    with closing(sqlite3.connect(data.database)) as connection:
        connection.execute(
            "UPDATE screening_successes SET audit_json=?,submission_sha256=?",
            (stored, digest),
        )
        connection.commit()
    restarted = ScreeningTasks(data.database, data.data_root)
    if damage is not None:
        for operation in (
            lambda: restarted.load_success(success.success_id),
            lambda: restarted.query_successes(
                paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
            ),
            restarted.validate_all,
        ):
            with pytest.raises(TaskError) as rejected:
                operation()
            assert rejected.value.reason == TaskReason.CORRUPT_REFERENCE
        with pytest.raises(BackupError) as backup_rejected:
            create_backup(data.database, data.data_root, tmp_path / "backups")
        assert backup_rejected.value.reason == "registration_invalid"
        return
    assert stored == historical
    assert restarted.load_success(success.success_id).audit == audit
    assert (
        restarted.query_successes(
            paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
        )[0].receipt
        == success
    )
    restarted.validate_all()
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    restored_tasks = ScreeningTasks(
        restored.target_dir / "database.sqlite3", restored.target_dir
    )
    restored_tasks.validate_all()
    assert restored_tasks.load_success(success.success_id).audit == audit
    # 不做审计迁移,幂等提交摘要也保持历史原值。
    with closing(
        sqlite3.connect(restored.target_dir / "database.sqlite3")
    ) as connection:
        assert connection.execute(
            "SELECT audit_json,submission_sha256 FROM screening_successes"
        ).fetchone() == (historical, digest)


@pytest.mark.parametrize("field", ["attempt_timeout", "auth_timeout"])
@pytest.mark.parametrize("value", [True, False, 0, -1, float("nan"), float("inf"), "1"])
def test_launch_invalid_timeout_never_refreshes_or_creates_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    from paper_radar.pi_execution import ExecutionError, prepare_launch
    from tests.pi_execution_support import launch_inputs

    database, description, roots, credentials, _ = launch_inputs(tmp_path, monkeypatch)

    def forbidden_process(*args: object, **kwargs: object) -> None:
        pytest.fail("invalid timeout started auth or model process")

    monkeypatch.setattr("subprocess.Popen", forbidden_process)
    with (
        pytest.raises(ExecutionError, match="timeout_invalid"),
        prepare_launch(
            database,
            description,
            roots=roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
            **{field: value},  # type: ignore[arg-type]
        ),
    ):
        pytest.fail("invalid timeout admitted")
    assert not (credentials / "auth-observed.json").exists()


@pytest.mark.parametrize(
    "field", ["initialization", "total", "close", "terminate", "poll"]
)
@pytest.mark.parametrize("value", [0, True, float("nan"), float("inf"), 10000])
def test_service_invalid_limits_preserve_preclaim_zero_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: float
) -> None:
    from dataclasses import replace

    from paper_radar.llm.rpc_types import DEFAULT_LIMITS
    from paper_radar.pi_execution import ExecutionError
    from tests.pi_execution_service_support import allow_synthetic, service_inputs

    service, receipt, credentials = service_inputs(tmp_path, monkeypatch)
    allow_synthetic(monkeypatch)

    def forbidden_process(*args: object, **kwargs: object) -> None:
        pytest.fail("invalid limits started auth or model process")

    monkeypatch.setattr("subprocess.Popen", forbidden_process)
    with pytest.raises(ExecutionError, match="timeout_invalid"):
        service.run_attempt(
            receipt.receipt_id, limits=replace(DEFAULT_LIMITS, **{field: value})
        )
    assert service.tasks.status(receipt.receipt_id).used_attempts == 0
    assert not (credentials / "auth-observed.json").exists()


def test_prepared_launch_cannot_create_a_second_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.llm.rpc_types import RpcProblem, RpcReason
    from paper_radar.pi_execution import prepare_launch
    from tests.pi_execution_support import launch_inputs, observed

    database, description, roots, credentials, _ = launch_inputs(tmp_path, monkeypatch)
    with prepare_launch(
        database,
        description,
        roots=roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
        proxy="http://localhost:8080",
    ) as prepared:
        identity = prepared.identity
        assert identity.auth_mode == "chatgpt_subscription"
        assert identity.credential_provider == "openai"
        assert identity.credential_source == "owner_provisioned_dir"
        assert identity.proxy_used is True and identity.proxy_port == 8080
        session = prepared(description)
        result = observed(session)
        settings = result["settings"]
        assert isinstance(settings, dict)
        assert settings["httpProxy"] == "http://localhost:8080"
        session.terminate(5)
        with pytest.raises(RpcProblem) as rejected:
            prepared(description)
        assert rejected.value.reason == RpcReason.STARTUP_ERROR
        assert prepared.identity == identity
