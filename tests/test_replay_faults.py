"""B-E16 独立 D1:不信标志/同形目录、严格路径与具体缺损原因。"""

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.replay.contract import ReplayError
from paper_radar.replay.service import replay
from tests.replay_support import cli, replay_args, restored_demo


@pytest.mark.parametrize(
    "mutation, reason",
    [
        ("receipt-missing", "restore_provenance_invalid"),
        ("receipt-changed", "restore_provenance_invalid"),
        ("manifest", "invalid_manifest"),
        ("database-missing", "file_missing"),
        ("database-changed", "file_corrupt"),
        ("unknown-contents", "unexpected_entry"),
        ("unknown-views", "unexpected_entry"),
        ("unknown-container", "restore_provenance_invalid"),
        ("symlink", "unsafe_layout"),
        ("hardlink", "unsafe_layout"),
    ],
)
def test_changed_restore_refuses_without_private_diagnostics(
    tmp_path: Path, mutation: str, reason: str
) -> None:
    root, originals = restored_demo(tmp_path)
    if mutation == "receipt-missing":
        (root / "restore-receipt.json").unlink()
    elif mutation == "receipt-changed":
        receipt = json.loads((root / "restore-receipt.json").read_bytes())
        receipt["batch_id"] = "PRIVATE_FREE_TEXT"
        (root / "restore-receipt.json").write_text(json.dumps(receipt))
    elif mutation == "manifest":
        (root / "contents/manifest.json").write_bytes(b"PRIVATE_BAD_MANIFEST")
    elif mutation == "database-missing":
        (root / "contents/database.sqlite3").unlink()
    elif mutation == "database-changed":
        with (root / "contents/database.sqlite3").open("r+b") as stream:
            stream.seek(100)
            stream.write(b"PRIVATE_CHANGED_DATABASE")
    elif mutation == "symlink":
        (root / "views/escape").symlink_to(originals[2], target_is_directory=True)
    elif mutation == "hardlink":
        os.link(originals[0], root / "views/alias")
    else:
        namespace = {
            "unknown-container": root,
            "unknown-contents": root / "contents",
            "unknown-views": root / "views",
        }[mutation]
        (namespace / "PRIVATE_UNKNOWN").write_text("PRIVATE_FREE_TEXT")
    result = cli(*replay_args(root, originals))
    assert result.returncode == 2 and reason in result.stderr, (
        result.stdout + result.stderr
    )
    for private in (
        str(tmp_path),
        "PRIVATE_FREE_TEXT",
        "PRIVATE_UNKNOWN",
        "PRIVATE_BAD_MANIFEST",
    ):
        assert private not in result.stdout + result.stderr
    assert not (root / "logs").exists()


@pytest.mark.parametrize(
    "arguments", [(), ("--restored",), ("--PRIVATE_UNKNOWN", "PRIVATE_TEXT")]
)
def test_replay_arguments_do_not_echo_private_input(arguments: tuple[str, ...]) -> None:
    result = CliRunner().invoke(app, ["replay", *arguments])
    assert result.exit_code == 2 and "invalid_arguments" in result.output
    assert "PRIVATE" not in result.output


@pytest.mark.parametrize(
    "alias", ["same-root", "inside-restored", "source-symlink", "source-runtime"]
)
def test_unsafe_source_alias_or_runtime_overlap_is_rejected(
    tmp_path: Path, alias: str
) -> None:
    root, originals = restored_demo(tmp_path)
    target = {
        "same-root": root,
        "inside-restored": root / "contents/database.sqlite3",
        "source-runtime": Path(__file__).resolve().parents[1] / "src",
    }.get(alias)
    if target is None:
        target = tmp_path / "source-alias"
        target.symlink_to(originals[2])
    replaced = (originals[0], originals[1], target, *originals[3:])
    result = cli(*replay_args(root, replaced))
    assert result.returncode == 2 and "unsafe_layout" in result.stderr


def test_missing_isolation_capability_never_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, originals = restored_demo(tmp_path)
    # 仅服务故障接缝:OS 能力不可用时不能执行无隔离业务。
    import subprocess

    def unavailable(*args: object, **kwargs: object) -> None:
        raise subprocess.SubprocessError("PRIVATE_OS_ERROR")

    monkeypatch.setattr(subprocess, "run", unavailable)
    with pytest.raises(ReplayError, match="isolation_unavailable"):
        replay(root, originals)
    assert list((root / "views").iterdir()) == []


def test_unverified_worker_summary_is_controlled_and_never_leaks_free_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    root, originals = restored_demo(tmp_path)

    def forged(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            [],
            0,
            json.dumps(
                {"isolation": "verified", "PRIVATE_FIELD": "PRIVATE_CONTENT"}
            ).encode(),
        )

    monkeypatch.setattr(subprocess, "run", forged)
    with pytest.raises(ReplayError, match="isolation_verification_failed"):
        replay(root, originals)
    assert list((root / "views").iterdir()) == []


def test_replay_interrupt_has_fixed_code_and_safe_next_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import paper_radar.replay.service as service

    root, originals = restored_demo(tmp_path)

    def interrupt(*args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(service, "replay", interrupt)
    result = CliRunner().invoke(app, list(replay_args(root, originals)))
    assert (
        result.exit_code == 130
        and "interrupted" in result.output
        and "重试" in result.output
    )
    assert str(tmp_path) not in result.output


def test_worker_free_text_cannot_enter_success_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    root, originals = restored_demo(tmp_path)
    fields = {
        "isolation": "verified",
        "originals_denied": "PRIVATE_CONTENT",
        "missing_originals": 0,
        "descendant": "verified",
        "sockets_denied": 3,
        "direct_connect_denied": True,
        "reports": 0,
        "analyses": 0,
        "evidence_slices": 0,
        "exposures": 0,
    }

    def forged(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess([], 0, json.dumps(fields).encode())

    monkeypatch.setattr(subprocess, "run", forged)
    with pytest.raises(ReplayError, match="isolation_verification_failed"):
        replay(root, originals)


def test_actual_worker_refuses_if_os_boundary_was_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.replay.isolation import ReplayBoundary

    root, originals = restored_demo(tmp_path)
    monkeypatch.setattr(ReplayBoundary, "__call__", lambda self: None)
    with pytest.raises(ReplayError, match="isolation_verification_failed"):
        replay(root, originals)
    assert list((root / "views").iterdir()) == []


def test_standard_restore_is_not_a_replay_provenance_container(tmp_path: Path) -> None:
    _, originals = restored_demo(tmp_path)
    (batch,) = (tmp_path / "backups").iterdir()
    standard = tmp_path / "standard-restore"
    result = cli("restore", "verify", str(batch), "--target", str(standard))
    assert result.returncode == 0, result.stdout + result.stderr
    refused = cli(*replay_args(standard, originals))
    assert refused.returncode == 2 and "restore_provenance_invalid" in refused.stderr
    assert {path.name for path in standard.iterdir()} == {
        "database.sqlite3",
        "manifest.json",
    }


def test_cleanup_failure_does_not_replace_the_controlled_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    root, originals = restored_demo(tmp_path)
    original_unlink = Path.unlink

    def cleanup_failure(path: Path, missing_ok: bool = False) -> None:
        if path.name.startswith(".replay-escape-"):
            raise OSError("PRIVATE_CLEANUP_ERROR")
        original_unlink(path, missing_ok=missing_ok)

    def unavailable(*args: object, **kwargs: object) -> None:
        raise subprocess.SubprocessError("PRIVATE_OS_ERROR")

    monkeypatch.setattr(Path, "unlink", cleanup_failure)
    monkeypatch.setattr(subprocess, "run", unavailable)
    with pytest.raises(ReplayError, match="isolation_unavailable"):
        replay(root, originals)
