"""一次尝试驱动的公共前置条件,非法调用不领取或启动执行者。"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from paper_radar.screening_tasks import (
    ScreeningTasks,
    SuccessCandidate,
    TaskError,
    TaskReason,
)
from paper_radar.storage.artifact_contract import ArtifactError, ArtifactReason
from tests.a7_registration_support import archive, request_for


def test_noncallable_executor_does_not_consume_attempt(tmp_path: Path) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    invalid: Any = None
    with pytest.raises(TaskError) as error:
        service.run_once(receipt.receipt_id, invalid)
    assert error.value.reason == TaskReason.INVALID_REQUEST
    assert service.status(receipt.receipt_id).used_attempts == 0


def test_missing_store_configuration_does_not_start_executor(tmp_path: Path) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    calls: list[int] = []

    def executor(*args: object) -> SuccessCandidate:
        calls.append(1)
        return SuccessCandidate(
            b'{"boundary":"in_scope","reason_zh":"Weather prediction is studied."}'
        )

    with pytest.raises(TaskError) as error:
        service.run_once(receipt.receipt_id, executor)
    assert error.value.reason == TaskReason.DATA_ROOT_REQUIRED
    assert calls == []
    assert service.status(receipt.receipt_id).used_attempts == 0


@pytest.mark.parametrize("obstruction", ["root_file", "tmp_link", "blobs_file"])
def test_invalid_store_path_does_not_start_executor(
    tmp_path: Path, obstruction: str
) -> None:
    data = archive(tmp_path)
    root = tmp_path / "output"
    if obstruction == "root_file":
        root.write_text("file")
    else:
        root.mkdir()
        if obstruction == "tmp_link":
            (root / "tmp").symlink_to(data.data_root, target_is_directory=True)
        else:
            (root / "blobs").write_text("file")
    service = ScreeningTasks(
        data.database, root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    calls: list[int] = []

    def executor(*args: object) -> SuccessCandidate:
        calls.append(1)
        return SuccessCandidate(
            b'{"boundary":"in_scope","reason_zh":"Weather prediction is studied."}'
        )

    with pytest.raises(ArtifactError) as error:
        service.run_once(receipt.receipt_id, executor)
    assert error.value.reason == ArtifactReason.UNSAFE_PATH
    assert calls == []
    assert service.status(receipt.receipt_id).used_attempts == 0


def test_storage_failure_after_claim_conservatively_consumes_attempt(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    root = tmp_path / "output"
    service = ScreeningTasks(
        data.database, root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    calls: list[int] = []

    def executor(*args: object) -> SuccessCandidate:
        assert service.status(receipt.receipt_id).state == "running"
        calls.append(1)
        (root / "tmp").rmdir()
        (root / "tmp").write_text("unexpected obstruction after preflight")
        return SuccessCandidate(
            b'{"boundary":"in_scope","reason_zh":"Weather prediction is studied."}'
        )

    with pytest.raises(ArtifactError) as error:
        service.run_once(receipt.receipt_id, executor)
    assert error.value.reason == ArtifactReason.UNSAFE_PATH
    assert calls == [1]
    assert service.status(receipt.receipt_id).used_attempts == 1
    assert service.status(receipt.receipt_id).state == "running"


def test_driver_passes_correction_for_attempt_recovered_during_claim(
    tmp_path: Path,
) -> None:
    from paper_radar.screening_tasks import FailureKind, FailureReport

    data = archive(tmp_path)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: now)
    receipt = service.register(request_for(data))
    first = service.claim(receipt.receipt_id)
    now = first.expires_at
    corrections: list[str | None] = []

    def executor(
        stage_input: object, correction: str | None, handle: str
    ) -> FailureReport:
        corrections.append(correction)
        return FailureReport(FailureKind.TIMEOUT)

    result = service.run_once(receipt.receipt_id, executor)
    assert corrections == ["上次执行结果未知,请重新完成本次冻结输入。"]
    assert result.kind == FailureKind.TIMEOUT
    assert service.status(receipt.receipt_id).used_attempts == 2


@pytest.mark.parametrize("readonly_directory", ["namespace", "existing_shard"])
def test_unwritable_publication_directory_does_not_start_executor(
    tmp_path: Path, readonly_directory: str
) -> None:
    from hashlib import sha256

    data = archive(tmp_path)
    root = tmp_path / "output"
    namespace = root / "blobs/sha256"
    namespace.mkdir(parents=True)
    raw = b'{"boundary":"in_scope","reason_zh":"Weather prediction is studied."}'
    blocked = namespace
    if readonly_directory == "existing_shard":
        blocked = namespace / sha256(raw).hexdigest()[:2]
        blocked.mkdir()
    blocked.chmod(0o500)
    service = ScreeningTasks(
        data.database, root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    calls: list[int] = []

    def executor(*args: object) -> SuccessCandidate:
        calls.append(1)
        return SuccessCandidate(raw)

    try:
        with pytest.raises(ArtifactError) as error:
            service.run_once(receipt.receipt_id, executor)
        assert error.value.reason == ArtifactReason.PUBLICATION_FAILED
        assert calls == []
        assert service.status(receipt.receipt_id).used_attempts == 0
        assert list((root / "tmp").iterdir()) == []
        assert list(namespace.rglob(".publish-check-*")) == []
    finally:
        blocked.chmod(0o700)
