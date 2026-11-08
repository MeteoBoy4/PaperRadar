"""Independent D1 artifact checks, no root/service/nft/network execution."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts.issue167_h1_network_bundle import PROJECT, SOURCES, create_bundle, units
from scripts.issue167_h1_phase import Plan


def test_complete_review_bundle_seals_all_code_and_wizard_library(
    tmp_path: Path,
) -> None:
    plan = Plan("167abcdef123", os.getuid(), os.getgid())
    root = create_bundle(tmp_path / "review", plan)
    manifest = json.loads((root / "manifest.json").read_text())
    assert set(manifest) == {"kind", "members", "tools"}
    assert len(manifest["tools"]) == 3
    for name, expected in manifest["members"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
    for name, source in SOURCES.items():
        assert (root / name).read_bytes() == (PROJECT / source).read_bytes()
    assert (
        json.loads((root / "plan.json").read_text())["authorization"] == "not_granted"
    )
    assert (root / "create.nft").read_text().startswith("create table inet ")
    assert "flush ruleset" not in (root / "create.nft").read_text()
    assert "38167" in (root / "phase-a.nft").read_text()
    assert "38169" in (root / "phase-b.nft").read_text()
    wizard = (root / "owner-wizard.sh").read_text()
    template = (PROJECT / ".agents/skills/wizard/template.sh").read_text()
    library = template[: template.index("# STAGES: author this section.")]
    assert wizard.startswith(library)
    assert "TOTAL_STAGES=6" in wizard
    subprocess.run(["bash", "-n", str(root / "owner-wizard.sh")], check=True)
    assert list((root / "results").iterdir()) == []


def test_units_keep_scope_no_mount_no_auto_enable_and_no_credentials() -> None:
    plan = Plan("167abcdef123", 1000, 1000)
    rendered = units(plan)
    worker = rendered[plan.unit]
    guardian = rendered[plan.guardian_unit]
    assert f"BindsTo={plan.guardian_unit}" in worker
    assert "RuntimeMaxSec=180s" in guardian
    assert "\nUser=" not in guardian  # Same root system-service identity, implicit UID.
    assert "Group=root" in guardian
    assert "CAP_CHOWN" in guardian  # root guardian必须将新worker目录归属给计划uid/gid。
    assert "User=1000" in worker
    for body in rendered.values():
        for expected in (
            "LimitCORE=0",
            "Delegate=no",
            "Restart=no",
            "KillMode=control-group",
            "IPAddressDeny=any",
            "IPAddressAllow=127.0.0.1/32 ::1/128",
        ):
            assert expected in body
        for forbidden in (
            "[Install]",
            "RootDirectory=",
            "PrivateTmp=",
            "ProtectSystem=",
            "NODE_OPTIONS",
            "OPENAI_API_KEY",
            "EnvironmentFile=",
            "--import",
        ):
            assert forbidden not in body


def test_existing_package_is_not_overwritten(tmp_path: Path) -> None:
    target = tmp_path / "review"
    target.mkdir()
    marker = target / "manifest.json"
    marker.write_text("historical")
    with pytest.raises(FileExistsError):
        create_bundle(target, Plan("167abcdef123", os.getuid(), os.getgid()))
    assert marker.read_text() == "historical"


def test_generator_rejects_uid_drift_and_shell_interpolation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"^review_identity_changed$"):
        create_bundle(
            tmp_path / "review", Plan("167abcdef123", os.getuid() + 1, os.getgid())
        )
    with pytest.raises(ValueError, match=r"^review_path_invalid$"):
        create_bundle(
            tmp_path / "bad%name", Plan("167abcdef123", os.getuid(), os.getgid())
        )
