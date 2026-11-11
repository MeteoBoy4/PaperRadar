"""D1:失败准备退役的只读宿主idle接缝;proc/systemd均为显式OS模型。"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from paper_radar.live_evidence.live_host import LinuxLiveHost
from paper_radar.live_evidence.live_install import InstallationPaths
from tests.site_collector_support import site_configuration


@pytest.mark.parametrize(
    "executable", ["anchor", "placement-pre", "placement-post", "python/bin/python3"]
)
def test_idle_accepts_only_authenticated_anchor_in_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, executable: str
) -> None:
    paths = InstallationPaths.for_model(tmp_path)
    target = paths.runtime / executable
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"OS metadata fixture only; never executed")
    proc = tmp_path / "proc/123"
    proc.mkdir(parents=True)
    (proc / "exe").symlink_to(target)
    original = Path.iterdir
    monkeypatch.setattr(
        Path,
        "iterdir",
        lambda path: iter((proc,)) if path == Path("/proc") else original(path),
    )
    monkeypatch.setattr(
        "paper_radar.live_evidence.live_host.process_identity",
        lambda pid: (9, "/synthetic-anchor-cgroup"),
    )
    host = LinuxLiveHost(paths)
    monkeypatch.setattr(host, "preflight", lambda site: None)
    monkeypatch.setattr(
        host,
        "_preflight_target",
        lambda: SimpleNamespace(anchor_pid=123, anchor_start=9),
    )
    if executable == "anchor":
        host.verify_preparation_idle(site_configuration(tmp_path))
    else:
        with pytest.raises(ValueError, match=r"^failed_preparation_process_active$"):
            host.verify_preparation_idle(site_configuration(tmp_path))
