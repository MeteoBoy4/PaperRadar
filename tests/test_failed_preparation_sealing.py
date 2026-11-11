"""D1:显式failed runtime候选派生与公开离线封印入口。"""

import hashlib
import json
import tarfile
from pathlib import Path

import pytest

from paper_radar.live_evidence.live_bundle import build_live_bundle
from paper_radar.live_evidence.preparation_retirement import describe_failed_preparation
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from tests.preparation_retirement_support import case, reseal


def test_public_builder_seals_explicit_failed_runtime_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = case(tmp_path, monkeypatch)
    root = model.gate.staged
    site = SiteConfiguration.model_validate_json((root / "site.json").read_bytes())
    spec = json.loads((root / "deployment.json").read_bytes())
    from paper_radar.live_evidence.epoch_lineage import EpochUpgrade
    from paper_radar.live_evidence.model_manifest import parse_manifest

    manifest = parse_manifest((root / "model-manifest.json").read_bytes())
    output = tmp_path / "explicit-review"
    build_live_bundle(
        output,
        site,
        starts_at=manifest.network.starts_at,
        ends_at=manifest.network.ends_at,
        source_root=Path(__file__).resolve().parents[1],
        network_input=json.loads(
            (root / "network-owner-confirmation.json").read_bytes()
        )["owner_input"],
        upgrade_from=tuple(spec["upgrade_from"]),
        epoch_upgrade=EpochUpgrade.model_validate(spec["epoch_upgrade"]),
        failed_preparation_runtime=model.old.root,
    )
    with tarfile.open(output / "payload.tar") as archive:
        member = archive.extractfile("deployment.json")
        assert member is not None
        sealed = json.loads(member.read())
    assert sealed["failed_preparation"] == spec["failed_preparation"]
    assert set(sealed["failed_preparation"]) == {
        "format_version",
        "payload_sha256",
        "runtime_manifest_sha256",
        "placement_identity",
        "binary_sha256",
        "source_sha256",
        "marker_sha256",
        "new_placement_identity",
        "upgrade_from",
        "epoch_upgrade_sha256",
        "continuity_sha256",
    }


@pytest.mark.parametrize("change", ["native", "source", "build", "site", "upgrade"])
def test_derivation_refuses_noncanonical_change_or_broken_continuity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    model = case(tmp_path, monkeypatch)
    root = model.gate.staged
    build_path = root / "placement/build.json"
    build = json.loads(build_path.read_bytes())
    reason = "failed_preparation_policy_change"
    if change == "native":
        path = root / "placement-pre"
        path.write_bytes(path.read_bytes() + b"different native")
        build["native_sha256"]["pre"] = hashlib.sha256(path.read_bytes()).hexdigest()
    elif change == "source":
        path = root / "placement/apparmor.source"
        path.write_bytes(path.read_bytes() + b"# different policy\n")
        build["source_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    elif change == "build":
        build["compiler_specs_sha256"] = "f" * 64
    elif change == "site":
        path = root / "site.json"
        site = json.loads(path.read_bytes())
        site["product_gid"] += 1
        path.write_text(json.dumps(site))
        reason = "failed_preparation_continuity"
    else:
        path = root / "deployment.json"
        spec = json.loads(path.read_bytes())
        spec["upgrade_from"][0] = "f" * 64
        path.write_text(json.dumps(spec))
        reason = "failed_preparation_continuity"
    build_path.write_text(json.dumps(build))
    with pytest.raises(ValueError, match=reason):
        describe_failed_preparation(model.old.root, root)


def test_caller_cannot_replace_old_full_manifest_identity_with_selected_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = case(tmp_path, monkeypatch)
    (model.old.root / "entry.py").write_bytes(b"unsealed old source")
    with pytest.raises(ValueError, match=r"^runtime_member_identity$"):
        describe_failed_preparation(model.old.root, model.gate.staged)
    reseal(model.old.root)
    # Candidate可读,但root重读必须仍与已封descriptor的旧完整manifest完全相等。
    with pytest.raises(ValueError, match=r"^runtime_manifest_identity$"):
        model.gate.check()


def test_descriptor_preserves_other_deployment_host_tool_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = case(tmp_path, monkeypatch)
    path = model.gate.staged / "deployment.json"
    spec = json.loads(path.read_bytes())
    spec["host_tools"]["/usr/bin/busctl"]["sha256"] = "f" * 64
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match=r"^failed_preparation_continuity$"):
        describe_failed_preparation(model.old.root, model.gate.staged)
