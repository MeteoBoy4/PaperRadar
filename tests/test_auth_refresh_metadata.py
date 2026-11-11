"""D1: 认证公开元数据边界;合成输入不读取现场凭据。"""

import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from paper_radar.pi_execution.auth_metadata import parse_auth_metadata


def test_auth_metadata_accepts_only_fixed_nonsecret_projection() -> None:
    raw = json.dumps(
        {
            "format_version": 1,
            "source_id": "pi-auth-refresh-1.4.0-v1",
            "pid": 123,
            "started_at": "2026-11-11T00:00:00.000Z",
            "completed_at": "2026-11-11T00:00:01.000Z",
            "refresh_at": "2026-11-11T00:00:00.500Z",
            "need_refresh": True,
            "was_expired_by_pi": False,
            "refresh_called": True,
            "refresh_succeeded": True,
            "store_committed": True,
        }
    ).encode()
    result = parse_auth_metadata(raw, pid=123)
    assert result.store_committed is True
    assert result.was_expired_by_pi is False
    for field, value in [
        ("access", "secret"),
        ("source_id", "arbitrary"),
        ("pid", 124),
        ("need_refresh", "true"),
    ]:
        changed = json.loads(raw) | {field: value}
        with pytest.raises(ValueError, match="auth_metadata_invalid"):
            parse_auth_metadata(json.dumps(changed).encode(), pid=123)


def test_auth_metadata_does_not_promote_partial_or_inconsistent_events() -> None:
    from paper_radar.pi_execution.auth_metadata import AuthRefreshMetadata

    event = AuthRefreshMetadata(
        format_version=1,
        source_id="pi-auth-refresh-1.4.0-v1",
        pid=123,
        started_at=datetime.fromisoformat("2026-11-11T00:00:00Z"),
        completed_at=datetime.fromisoformat("2026-11-11T00:00:01Z"),
        refresh_at=datetime.fromisoformat("2026-11-11T00:00:00.500Z"),
        need_refresh=True,
        was_expired_by_pi="unknown",
        refresh_called=True,
        refresh_succeeded=True,
        store_committed="unknown",
    )
    assert event.store_committed == "unknown"
    with pytest.raises(ValidationError, match="auth_metadata_invalid"):
        AuthRefreshMetadata.model_validate(
            event.model_dump() | {"refresh_called": False}
        )


def test_shared_prepare_reports_metadata_bound_to_the_released_auth_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.pi_execution import prepare_launch
    from paper_radar.pi_execution.auth_metadata import AuthRefreshMetadata
    from tests.pi_execution_support import TOKEN, launch_inputs

    database, description, roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch
    )
    targets: list[int] = []
    metadata: list[AuthRefreshMetadata] = []
    with prepare_launch(
        database,
        description,
        roots=roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
        before_auth=lambda pid, start, unit: targets.append(pid),
        observe_auth=metadata.append,
    ):
        assert len(metadata) == 1
        assert metadata[0].pid == targets[0]
        assert metadata[0].refresh_called is False
        assert metadata[0].store_committed == "unknown"
        assert TOKEN not in metadata[0].model_dump_json()


def test_new_worker_wire_requires_an_explicit_version() -> None:
    from paper_radar.live_evidence.model_ipc import WorkerMessage, WorkerMessageV2

    old = WorkerMessage(
        case_id="synthetic-case",
        sequence=1,
        stage="auth",
        binding_sha256="a" * 64,
        material_sha256="b" * 64,
    )
    with pytest.raises(ValidationError, match="format_version"):
        WorkerMessageV2.model_validate(old.model_dump())
