"""D1: public seal CLI carries only the original read-only epoch source."""

import subprocess
from pathlib import Path

import pytest

from tests.test_live_epoch_upgrade import (
    UpgradeCase,
)
from tests.test_live_epoch_upgrade import (
    source_root as source_root,
)
from tests.test_live_epoch_upgrade import (
    upgrade as upgrade,
)


def test_cli_candidate_derives_original_pair_and_epoch(upgrade: UpgradeCase) -> None:
    from scripts.seal_live_bundle import read_epoch_candidate

    source = upgrade.paths.ledger / "cli-original-epoch.json"
    source.write_bytes(upgrade.old_epoch)
    pair, descriptor = read_epoch_candidate(upgrade.paths.runtime, source, None)
    assert descriptor == upgrade.descriptor
    assert pair == (
        upgrade.descriptor.payload_sha256,
        upgrade.descriptor.runtime_manifest_sha256,
    )
    assert source.read_bytes() == upgrade.old_epoch


@pytest.mark.parametrize(
    "runtime,epoch,pair,reason",
    [
        (None, None, ("a" * 64, "b" * 64), "epoch_upgrade_required"),
        ("runtime", None, None, "epoch_upgrade_inputs_missing"),
        (None, "epoch", None, "epoch_upgrade_inputs_missing"),
    ],
)
def test_candidate_missing_source_refuses_before_file_read(
    tmp_path: Path,
    runtime: str | None,
    epoch: str | None,
    pair: tuple[str, str] | None,
    reason: str,
) -> None:
    from scripts.seal_live_bundle import read_epoch_candidate

    with pytest.raises(ValueError, match=reason):
        read_epoch_candidate(
            tmp_path / runtime if runtime else None,
            tmp_path / epoch if epoch else None,
            pair,
        )


def cold_cli(arguments: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    import sys

    script = Path(__file__).resolve().parents[1] / "scripts/seal_live_bundle.py"
    harness = (
        "import runpy,socket,sqlite3,sys\n"
        "def denied(*args,**kwargs): raise AssertionError('external I/O forbidden')\n"
        "socket.socket.connect=denied\n"
        "socket.create_connection=denied\n"
        "sqlite3.connect=sqlite3.dbapi2.connect=denied\n"
        "sys.argv=sys.argv[1:]\n"
        "runpy.run_path(sys.argv[0],run_name='__main__')\n"
    )
    return subprocess.run(
        (sys.executable, "-I", "-B", "-c", harness, str(script), *arguments),
        capture_output=True,
        text=True,
        check=False,
    )


def test_cold_help_explains_read_only_epoch_inputs_without_external_io() -> None:
    result = cold_cli(("--help",))
    assert result.returncode == 0
    assert "--epoch-from-runtime" in result.stdout
    assert "--epoch-source" in result.stdout
    assert "原部署epoch原字节" in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize(
    "extra,reason",
    [
        (
            ("--upgrade-from-payload", "a" * 64, "--upgrade-from-manifest", "b" * 64),
            "epoch_upgrade_required",
        ),
        (("--epoch-from-runtime", "/not-read/runtime"), "epoch_upgrade_inputs_missing"),
        (("--epoch-source", "/not-read/epoch"), "epoch_upgrade_inputs_missing"),
        (("--deployed-at", "2026-11-11T00:00:00Z"), "arguments_invalid"),
    ],
)
def test_cold_build_missing_source_or_free_time_refuses_without_external_io(
    tmp_path: Path, extra: tuple[str, ...], reason: str
) -> None:
    output = tmp_path / "review"
    result = cold_cli(
        (
            "build",
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


def test_explicit_pair_must_match_original_epoch_source(upgrade: UpgradeCase) -> None:
    from scripts.seal_live_bundle import read_epoch_candidate

    source = upgrade.paths.ledger / "cli-original-epoch.json"
    source.write_bytes(upgrade.old_epoch)
    with pytest.raises(ValueError, match="epoch_upgrade_source"):
        read_epoch_candidate(upgrade.paths.runtime, source, ("a" * 64, "b" * 64))
