"""D1:明确的只读准备恢复构建输入与三摘要描述。"""

import json
import tarfile
from pathlib import Path

import pytest

from paper_radar.live_evidence.epoch_lineage import EpochUpgrade
from paper_radar.live_evidence.live_bundle import build_live_bundle
from paper_radar.live_evidence.model_manifest import parse_manifest
from paper_radar.live_evidence.preparation_retirement import (
    describe_preparation_recovery,
)
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from tests.preparation_recovery_support import assert_preserved, recovery_case
from tests.test_live_bundle_seal_cli import cold_cli


def test_builder_seals_one_hop_descriptor_before_final_payload_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    root = model.gate.staged
    spec = json.loads((root / "deployment.json").read_bytes())
    descriptor = describe_preparation_recovery(
        model.source.staged, root, model.source.journal.read_bytes()
    )
    assert descriptor.model_dump(mode="json") == spec["preparation_recovery"]
    assert set(spec["preparation_recovery"]) == {
        "payload_sha256",
        "runtime_manifest_sha256",
        "journal_sha256",
    }
    site = SiteConfiguration.model_validate_json((root / "site.json").read_bytes())
    manifest = parse_manifest((root / "model-manifest.json").read_bytes())
    output = tmp_path / "recovery-review"
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
        failed_preparation_runtime=model.original.old.root,
        preparation_recovery_runtime=model.source.staged,
        preparation_recovery_journal=model.source.journal,
    )
    with tarfile.open(output / "payload.tar") as archive:
        member = archive.extractfile("deployment.json")
        assert member is not None
        sealed = json.loads(member.read())
    assert sealed["preparation_recovery"] == spec["preparation_recovery"]
    assert sealed["failed_preparation"] == spec["failed_preparation"]
    assert_preserved(model)


@pytest.mark.parametrize(
    "action,extra,reason",
    [
        (
            "build",
            ("--preparation-recovery-runtime", "/must-not-read/runtime"),
            "preparation_recovery_inputs_missing",
        ),
        (
            "build",
            ("--preparation-recovery-journal", "/must-not-read/journal"),
            "preparation_recovery_inputs_missing",
        ),
        (
            "build",
            (
                "--preparation-recovery-runtime",
                "/must-not-read/runtime",
                "--preparation-recovery-journal",
                "/must-not-read/journal",
            ),
            "preparation_recovery_requires_retirement",
        ),
        (
            "derive",
            (
                "--preparation-recovery-runtime",
                "/must-not-read/runtime",
                "--preparation-recovery-journal",
                "/must-not-read/journal",
            ),
            "preparation_recovery_build_only",
        ),
    ],
)
def test_cli_rejects_unpaired_or_derive_recovery_inputs_before_reading(
    tmp_path: Path, action: str, extra: tuple[str, ...], reason: str
) -> None:
    output = tmp_path / "review"
    result = cold_cli(
        (
            action,
            "--baseline",
            "/must-not-read/baseline",
            "--baseline-sha256",
            "a" * 64,
            "--output",
            str(output),
            *extra,
        )
    )
    assert result.returncode == 2
    assert "Live构建拒绝 [" + reason + "]" in result.stderr
    assert "Traceback" not in result.stderr
    assert not output.exists()


def test_cold_help_explains_explicit_data_only_recovery_inputs() -> None:
    result = cold_cli(("--help",))
    assert result.returncode == 0 and result.stderr == ""
    assert "--preparation-recovery-runtime" in result.stdout
    assert "--preparation-recovery-journal" in result.stdout
    assert "原preparing日志原字节" in result.stdout
