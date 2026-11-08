"""Independent D1 regression: real mkdir under service umask, no services/root."""

import io
import os
import stat
from pathlib import Path
from typing import cast

import pytest

from scripts import issue167_h1_guardian as guard
from scripts.issue167_h1_phase import Plan


class TempPlan(Plan):
    __test__ = False
    directory: Path

    @property
    def runtime_root(self) -> Path:
        return self.directory


@pytest.mark.parametrize("mask", [0o077, 0o022])
def test_runtime_traversal_mode_is_explicit_despite_service_umask(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mask: int
) -> None:
    plan = TempPlan("6e70b5a31d42", os.getuid(), os.getgid())
    object.__setattr__(plan, "directory", tmp_path / "runtime")
    monkeypatch.setattr(guard, "claim_anchor", lambda *_args: io.StringIO())
    monkeypatch.setattr(guard, "protected_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(os, "chown", lambda *_args: None)
    operations = guard.LiveOperations(plan, cast(guard.Commands, object()))
    old = os.umask(mask)
    try:
        operations.reserve()
    finally:
        os.umask(old)
    assert stat.S_IMODE(plan.runtime_root.stat().st_mode) == 0o755
    assert stat.S_IMODE((plan.runtime_root / "worker").stat().st_mode) == 0o700
    assert stat.S_IMODE((plan.runtime_root / "started.json").stat().st_mode) == 0o644


@pytest.mark.parametrize("stage", ["peer_start", "worker_ready"])
def test_raw_startup_failure_reports_only_closed_stage_and_errno(stage: str) -> None:
    import errno

    from tests.test_issue167_h1_guardian import FakeOps
    from tests.test_issue167_h1_guardian import plan as sample_plan

    operations = FakeOps()

    def denied(*args: object) -> object:
        raise PermissionError(errno.EACCES, "synthetic-text-must-not-leak")

    if stage == "peer_start":
        operations.start_peer = denied  # type: ignore[assignment]
    else:
        operations.wait = denied  # type: ignore[assignment]
    result = guard.run_guardian(sample_plan(), operations)
    assert result["result"] == "unknown"
    assert result["failure_stage"] == stage
    assert result["os_error_category"] == "permission_denied"
    assert result["cleanup_complete"] is True
    assert "synthetic-text" not in repr(result)


@pytest.mark.parametrize("missing", [None, "dac_read_search", "setuid"])
def test_guardian_self_diagnostics_only_exposes_selected_metadata(
    monkeypatch: pytest.MonkeyPatch, missing: str | None
) -> None:
    import resource

    mapping = {
        "chown": 0,
        "dac_read_search": 2,
        "kill": 5,
        "setgid": 6,
        "setuid": 7,
        "net_admin": 12,
    }
    bits = sum(1 << bit for name, bit in mapping.items() if name != missing)
    raw = f"Name: python\nUid:\t0 0 0 0\nNoNewPrivs:\t1\nCapEff:\t{bits:016x}\n"
    monkeypatch.setattr(Path, "open", lambda *args, **kwargs: io.BytesIO(raw.encode()))
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(resource, "getrlimit", lambda _key: (0, 0))
    result = guard.guardian_runtime_metadata()
    assert set(result) == {"uid_is_root", "core_limits", "no_new_privs", "capabilities"}
    assert result["uid_is_root"] is True
    assert result["core_limits"] == [0, 0]
    assert result["capabilities"] == {name: name != missing for name in mapping}
