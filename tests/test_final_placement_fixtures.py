"""D1: 最终源码fixture、真实冻结输入与有限历史layout兼容。"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from paper_radar.live_evidence.live_host import LinuxLiveHost
from paper_radar.live_evidence.placement_build import verify_static_elf
from paper_radar.live_evidence.placement_policy import read_placement_policy
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from tests.live_bundle_support import alternate_python_input, bundle_model


def test_alternate_os_freezer_input_is_a_real_executable_python(tmp_path: Path) -> None:
    path = alternate_python_input(tmp_path)
    assert path.read_bytes() != Path(sys.executable).resolve().read_bytes()
    result = subprocess.run(
        (str(path), "-I", "-S", "-B", "-c", "print('freezer input executable')"),
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0 and result.stderr == b""
    assert result.stdout == b"freezer input executable\n"


def test_real_freezer_after_model_build_keeps_complete_current_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, _ = bundle_model(tmp_path, monkeypatch)
    site = SiteConfiguration.model_validate_json((first / "site.json").read_bytes())
    next_root = tmp_path / "real-build"
    next_root.mkdir()
    staged, _ = bundle_model(
        next_root, monkeypatch, real_freeze=True, site_override=site
    )
    assert (staged / "python/bin/python3").read_bytes() == Path(
        sys.executable
    ).resolve().read_bytes()
    source = Path(__file__).resolve().parents[1] / "src/paper_radar"
    for name in (
        "live_evidence/epoch_lineage.py",
        "live_evidence/live_apparmor_kernel.py",
        "live_evidence/placement_build.py",
        "live_evidence/placement_policy.py",
        "pi_execution/placement_protocol.py",
        "pi_execution/placement_preflight.py",
        "pi_execution/placement_native.c",
    ):
        assert (staged / "site-packages/paper_radar" / name).read_bytes() == (
            source / name
        ).read_bytes()
    old_policy, policy = read_placement_policy(first), read_placement_policy(staged)
    assert old_policy is not None and policy is not None
    assert old_policy.identity == policy.identity
    for name in ("placement-pre", "placement-post"):
        verify_static_elf(staged / name)
    old = json.loads((first / "model-manifest.json").read_bytes())
    new = json.loads((staged / "model-manifest.json").read_bytes())
    assert old["collector_sha256"] != new["collector_sha256"]


@pytest.mark.parametrize(
    "tool", ["/usr/sbin/apparmor_parser", "/usr/bin/true", "/usr/bin/systemd-run"]
)
@pytest.mark.parametrize("field", ["resolved", "sha256"])
def test_new_host_tool_identity_refuses_before_any_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool: str, field: str
) -> None:
    staged, paths = bundle_model(tmp_path, monkeypatch)
    path = staged / "deployment.json"
    specification = json.loads(path.read_bytes())
    expected = {
        "resolved": str(Path(tool).resolve()),
        "sha256": hashlib.sha256(Path(tool).read_bytes()).hexdigest(),
    }
    assert specification["host_tools"][tool] == expected
    specification["host_tools"][tool][field] = (
        "/synthetic-unreviewed-tool" if field == "resolved" else "0" * 64
    )
    path.write_text(json.dumps(specification))

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("host command must not run")

    monkeypatch.setattr(subprocess, "run", forbidden)
    site = SiteConfiguration.model_validate_json((staged / "site.json").read_bytes())
    with pytest.raises(ValueError, match=r"^host_tool_identity$"):
        LinuxLiveHost(paths, source=staged).preflight(site)


@pytest.mark.parametrize("format_version", [None, 1, 2, 3])
def test_historical_layout_without_placement_feature_stays_compatible(
    tmp_path: Path, format_version: int | None
) -> None:
    # 仅合成旧layout的metadata;不配旧guard/pin,不声称是旧可执行源码。
    if format_version is not None:
        (tmp_path / "source-identity.json").write_text(
            json.dumps(
                {
                    "format_version": format_version,
                    "source_auxiliary_sha256": {
                        "pi_execution/auth_helper.mjs": "a" * 64
                    },
                }
            )
        )
    assert read_placement_policy(tmp_path) is None
