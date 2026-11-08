"""Independent D1: offline bundle bytes; never installs or starts anything."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.issue167_resolver_bundle import PROJECT, SOURCES, create_bundle
from scripts.issue167_resolver_case import Case
from scripts.issue167_service_egress import EgressRejected

PROFILE = PROJECT / "intent/review/issue-167/real-exit-plan-v1.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_bundle_is_closed_no_network_and_source_sealed(tmp_path: Path) -> None:
    root = create_bundle(tmp_path / "review", "a6f0a1b2c3d4", PROFILE)
    case = Case.from_dict(json.loads((root / "plan.json").read_text()))
    manifest = json.loads((root / "manifest.json").read_text())
    seal = json.loads((root / "review-seal.json").read_text())
    assert all(
        sha(root / name) == digest for name, digest in manifest["members"].items()
    )
    assert seal["manifest_sha256"] == sha(root / "manifest.json")
    assert seal["driver_sha256"] == sha(root / "owner-wizard.sh")
    assert not {"owner-wizard.sh", "review-seal.json"} & set(manifest["members"])
    for name, source in SOURCES.items():
        assert (root / name).read_bytes() == (PROJECT / source).read_bytes()
    unit = (root / case.unit).read_text()
    assert f"BindReadOnlyPaths={case.install_root}/resolv.conf:/etc/resolv.conf" in unit
    for line in [
        "RestrictAddressFamilies=none",
        "IPAddressDeny=any",
        "RemainAfterExit=yes",
        "CapabilityBoundingSet=",
        "LimitCORE=0",
    ]:
        assert line + "\n" in unit
    assert not list((root / "results").iterdir())
    assert json.loads((root / "plan.json").read_text())["network_operations"] == 0
    assert (root / "profile.json").read_bytes() == PROFILE.read_bytes()
    assert "sudo -S" not in (root / "owner-wizard.sh").read_text()


def test_changed_pool_is_not_packaged_even_with_new_digest(tmp_path: Path) -> None:
    data = json.loads(PROFILE.read_text())
    data["accepted_policy"]["pool_cidr"] = "0.0.0.0/0"
    profile = tmp_path / "bad.json"
    profile.write_text(json.dumps(data))
    target = tmp_path / "review"
    with pytest.raises(EgressRejected, match=r"^egress_profile_unknown$"):
        create_bundle(target, "a6f0a1b2c3d4", profile)
    assert not target.exists()


def test_existing_destination_is_never_reused(tmp_path: Path) -> None:
    target = tmp_path / "review"
    target.mkdir()
    (target / "user-file").write_bytes(b"fixed-user-fixture")
    with pytest.raises(FileExistsError):
        create_bundle(target, "a6f0a1b2c3d4", PROFILE)
    assert (target / "user-file").read_bytes() == b"fixed-user-fixture"


def test_real_generator_cli_only_creates_unexecuted_review(tmp_path: Path) -> None:
    root = tmp_path / "review"
    subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "scripts.issue167_resolver_bundle",
            str(root),
            "--run-id",
            "b6f0a1b2c3d4",
        ],
        check=True,
        capture_output=True,
        timeout=10,
    )
    assert (
        json.loads((root / "plan.json").read_text())["authorization"] == "not_granted"
    )
    assert not list((root / "results").iterdir())
