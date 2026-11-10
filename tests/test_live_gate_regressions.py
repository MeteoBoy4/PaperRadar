"""D1: 门禁回归的公开宿主元数据边界,不读取现场账本或凭据。"""

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from paper_radar.live_evidence.types import BindingComponent as B
from paper_radar.pi_execution import resources
from paper_radar.pi_execution.site_binding import site_binding_components


def test_kernel_identity_uses_native_fields_without_spawning_a_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.setattr(resources, "EXECUTION_CWD", cwd)
    native = os.uname_result(("Linux", "fixture", "6.8.0-fixture", "#1", "x86_64"))
    monkeypatch.setattr(os, "uname", lambda: native)
    # Python 的 uname 结果会懒求 processor,必须从冷缓存覆盖此隐藏 subprocess。
    monkeypatch.setattr("platform._uname_cache", None)

    def denied(*args: Any, **kwargs: Any) -> None:
        pytest.fail("host metadata must not launch an external process")

    monkeypatch.setattr(subprocess, "Popen", denied)
    components = site_binding_components()
    assert (
        components[B.KERNEL]
        == "beaab7cc9dfdccc94b4c4ae79f76ae27bbed43f5f79c83e820594c5bb76cc1d4"
    )


def test_v12_source_vector_keeps_old_anchors_and_matches_current_sources() -> None:
    root = Path(__file__).resolve().parents[1]
    raw = (root / "tests/fixtures/live-admission-source-guard-v12.json").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "cd2bb0f609180552ad722c5e5f3e9f8f0c76ada71cfd59a218a3e5fa9290cef6"
    )
    vector = json.loads(raw)
    assert vector["policies"]["admission"] == "pi-admission-v12"
    assert vector["policies"]["launch"] == "pi-launch-1.4.0-v8"
    assert len(vector["files"]) == 71
    for name, expected in vector["files"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
