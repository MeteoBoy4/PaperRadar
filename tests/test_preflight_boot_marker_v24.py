"""D1: v24 binds the authenticated real boot marker, never an empty replacement."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest

from paper_radar.live_evidence import placement_policy as owner
from tests.test_preflight_system_bus import PreflightModel


class BootMarkerModel(PreflightModel):
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        super().__init__(tmp_path, monkeypatch)
        marker = self.host_run / "systemd/system"
        marker.mkdir(parents=True)
        marker.chmod(0o755)
        marker.parent.chmod(0o755)
        (marker / "real-origin").write_bytes(b"authenticated host directory")
        self.marker_damage = ""

    def opened(
        self, path: Any, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        logical = os.fsdecode(path)
        if dir_fd in self.fd_paths:
            logical = str(Path(self.fd_paths[dir_fd]) / logical)
        if logical in ("/run/systemd", "/run/systemd/system"):
            assert not self.hidden and not self.product
            assert flags & os.O_NOFOLLOW and flags & os.O_CLOEXEC
            if self.marker_damage == "missing" and logical.endswith("/system"):
                raise FileNotFoundError("SECRET host marker")
            fd = self.original_open(self.mapped(logical), flags, mode)
            self.fd_paths[fd] = logical
            return fd
        return super().opened(path, flags, mode, dir_fd=dir_fd)

    def fstat(self, fd: int) -> os.stat_result:
        info = super().fstat(fd)
        if self.fd_paths.get(fd) in ("/run/systemd", "/run/systemd/system"):
            values = list(info)
            values[4] = 1000 if self.marker_damage == "owner" else 0
            if self.marker_damage == "writable":
                values[0] = stat.S_IFDIR | 0o777
            if self.marker_damage == "file":
                values[0] = stat.S_IFREG | 0o644
            return os.stat_result(values)
        return info

    def mount(self, source: bytes | None, target: bytes, *args: Any) -> int:
        if source is None and os.fsdecode(target) == str(
            self.private_run / "systemd/system"
        ):
            self.event("marker-readonly", flags=getattr(args[1], "value", args[1]))
        return super().mount(source, target, *args)

    def manager_command(
        self, argv: tuple[str, ...], **kwargs: Any
    ) -> subprocess.CompletedProcess[bytes]:
        if argv[0] == "/usr/bin/loginctl":
            assert (
                self.private_run / "systemd/system/real-origin"
            ).read_bytes() == b"authenticated host directory"
        return super().manager_command(argv, **kwargs)

    def run_v24(self) -> None:
        try:
            owner.native_preflight(
                self.stage,
                self.site,
                self.sealed,
                target=self.target,
                preserve_boot_marker=True,
            )
        finally:
            self.original_close(self.lock)


def test_v24_preserves_real_protected_boot_marker_readonly_and_closes_setup_fds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = BootMarkerModel(tmp_path, monkeypatch)
    model.run_v24()
    assert {
        "event": "bind",
        "target": "/run/systemd/system",
        "flags": 4096,
    } in model.events
    assert {
        "event": "marker-readonly",
        "flags": 4096 | 32 | 1 | 2 | 4 | 8,
    } in model.events
    assert {"event": "scope-boundary"} in model.events
    assert (
        model.host_run / "systemd/system/real-origin"
    ).read_bytes() == b"authenticated host directory"


@pytest.mark.parametrize("damage", ["missing", "owner", "writable", "file"])
def test_v24_rejects_untrusted_boot_marker_before_product_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    model = BootMarkerModel(tmp_path, monkeypatch)
    model.marker_damage = damage
    with pytest.raises(ValueError, match=r"^placement_preflight_refused$"):
        model.run_v24()
    assert not any(event["event"] == "product" for event in model.events)


@pytest.mark.parametrize("checkpoint", ["entry_core", "pre_post", "post_exec_python"])
def test_native_checkpoint_reaches_root_parent_without_arbitrary_error_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    checkpoint: str,
) -> None:
    from paper_radar.pi_execution import placement_preflight as probe

    model = BootMarkerModel(tmp_path, monkeypatch)

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise probe.NativePreflightError(checkpoint)

    monkeypatch.setattr(probe.PREFLIGHT_PLATFORM, "spawn", fail)
    with pytest.raises(ValueError, match=r"^placement_preflight_refused$") as caught:
        model.run_v24()
    assert caught.value.checkpoint == checkpoint
    assert (
        capsys.readouterr().err
        == f"放置预检拒绝：阶段=native/{checkpoint}；原因=执行链失败。\n"
    )


@pytest.mark.parametrize(
    ("damage", "check"),
    [
        ("nonrunning", "manager_state"),
        ("linger", "linger"),
        ("inactive", "anchor_active"),
    ],
)
def test_v24_private_manager_queries_do_not_short_circuit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    damage: str,
    check: str,
) -> None:
    model = BootMarkerModel(tmp_path, monkeypatch)
    model.fail = damage
    with pytest.raises(ValueError, match=r"^placement_preflight_refused$") as caught:
        model.run_v24()
    assert len([event for event in model.events if event["event"] == "manager"]) == 3
    assert caught.value.manager_checks == (check,)
    assert (
        capsys.readouterr().err
        == f"放置预检拒绝：阶段=产品 manager/{check}；原因=依赖不可用。\n"
    )
