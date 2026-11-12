"""D1: sealed preflight protocol selects marker preservation for every new candidate."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from paper_radar.live_evidence import placement_policy
from paper_radar.live_evidence.live_host import LinuxLiveHost
from paper_radar.live_evidence.live_install import InstallationPaths


@pytest.mark.parametrize("version", ["historical_missing", 2])
def test_prepare_and_installed_verify_select_sealed_protocol(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version: Any
) -> None:
    root = tmp_path / "stage"
    root.mkdir()
    (root / "deployment.json").write_text(
        json.dumps(
            {}
            if version == "historical_missing"
            else {"placement_preflight_version": version}
        )
    )
    host = LinuxLiveHost(InstallationPaths.for_model(tmp_path), source=root)
    sealed = object()
    lifecycle = SimpleNamespace(
        sealed=sealed,
        prepare=lambda callback, **kwargs: callback(),
        verify=lambda: None,
    )
    monkeypatch.setattr(host, "_placement_lifecycle", lambda root: lifecycle)
    target = object()
    monkeypatch.setattr(host, "_preflight_target", lambda: target)
    calls = []
    monkeypatch.setattr(
        placement_policy,
        "native_preflight",
        lambda *args, **kwargs: calls.append(kwargs),
    )
    host.prepare_placement(root, SimpleNamespace())
    host.verify_target_preflight(root, SimpleNamespace())
    if version == 2:
        assert len(calls) == 2 and all(
            call["preserve_boot_marker"] is True for call in calls
        )
    else:
        assert len(calls) == 2 and all(
            "preserve_boot_marker" not in call for call in calls
        )


@pytest.mark.parametrize("version", [True, False, 2.0, "2", 1, 3, None])
def test_unknown_or_inexact_protocol_is_refused_before_policy_prepare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version: Any
) -> None:
    root = tmp_path / "stage"
    root.mkdir()
    (root / "deployment.json").write_text(
        json.dumps({"placement_preflight_version": version})
    )
    host = LinuxLiveHost(InstallationPaths.for_model(tmp_path), source=root)
    calls = []
    monkeypatch.setattr(
        host, "_placement_lifecycle", lambda root: calls.append("policy")
    )
    with pytest.raises(ValueError, match=r"^placement_preflight_protocol$"):
        host.prepare_placement(root, SimpleNamespace())
    assert calls == []
