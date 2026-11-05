"""D1:受限执行审计/预算的真实双环境备份闭包。"""

import os
import subprocess
from pathlib import Path

from tests.docling_execution_recovery_case import produce
from tests.no_extra_runtime import no_extra_python as no_extra_python


def test_success_and_failure_recover_in_actual_no_extra_process(
    tmp_path: Path,
    no_extra_python: Path,
) -> None:
    root = tmp_path / "case"
    produce(root)
    repository = Path(__file__).parents[1]
    result = subprocess.run(
        [
            str(no_extra_python),
            "-B",
            "-m",
            "tests.docling_execution_recovery_case",
            "verify",
            str(root),
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": str(repository) + os.pathsep + str(repository / "src"),
        },
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stderr
    assert (
        result.stdout.strip()
        == "audited extraction recovered without extra, SDK or original roots"
    )


def test_changed_attempt_audit_is_rejected_by_public_closure_check(
    tmp_path: Path,
) -> None:
    import sqlite3

    import pytest

    from paper_radar.body import BodyError
    from paper_radar.fulltext.normalization import canonical_json
    from tests.docling_executor_support import prepared_docling

    saved, service, parser = prepared_docling(tmp_path, failure="executor_error")
    result = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    audit = result.attempts[0].executor_audit
    assert audit
    altered = audit.model_dump(mode="json")
    altered["model_artifacts_hash"] = "e" * 64
    with sqlite3.connect(saved.database) as connection:
        connection.execute(
            "UPDATE body_extraction_attempts SET executor_audit_json=?",
            (canonical_json(altered).decode(),),
        )
    with pytest.raises(BodyError) as error:
        service.validate_all()
    assert error.value.reason == "corrupt_reference"
