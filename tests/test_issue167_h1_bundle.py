"""独立D1:仅渲染审阅包/合成worker结果,不执行服务或root动作。"""

import errno
import hashlib
import json
import os
import resource
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import issue167_h1_worker as worker
from scripts.issue167_h1_bundle import PROJECT, create_bundle


def test_bundle_is_sealed_no_network_and_preserves_wizard_library(
    tmp_path: Path,
) -> None:
    root = create_bundle(
        tmp_path / "review",
        python=Path(sys.executable),
        uid=os.getuid(),
        unit_name="paperradar-167-preflight-a51db59cf820.service",
    )
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["authorization"] == "not_granted"
    for name, expected in manifest["members"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
    unit = (root / manifest["unit"]).read_text()
    for required in (
        "LimitCORE=0",
        "RestrictAddressFamilies=none",
        "IPAddressDeny=any",
        "NoNewPrivileges=yes",
        "Delegate=no",
        "Restart=no",
        "KillMode=control-group",
    ):
        assert required in unit
    for forbidden in (
        "PrivateTmp=",
        "ProtectSystem=",
        "RootDirectory=",
        "[Install]",
        "OPENAI_API_KEY",
        "NODE_OPTIONS",
        "sudo ",
        "EnvironmentFile=",
    ):
        assert forbidden not in unit
    template = (PROJECT / ".agents/skills/wizard/template.sh").read_text()
    library = template[: template.index("# STAGES: author this section.")]
    wizard = (root / "owner-wizard.sh").read_text()
    assert wizard.startswith(library)
    assert "TOTAL_STAGES=4" in wizard
    assert "sudo systemctl start" in wizard  # 只是say的字符串,不是执行命令。
    subprocess.run(["bash", "-n", str(root / "owner-wizard.sh")], check=True)
    assert not (root / "results/receipt.json").exists()


def test_bundle_never_overwrites_old_package(tmp_path: Path) -> None:
    destination = tmp_path / "review"
    destination.mkdir()
    marker = destination / "manifest.json"
    marker.write_text("old")
    with pytest.raises(FileExistsError):
        create_bundle(destination, python=Path(sys.executable), uid=os.getuid())
    assert marker.read_text() == "old"


@pytest.mark.parametrize("uid", [0, True, os.getuid() + 1])
def test_bundle_refuses_root_or_changed_uid(tmp_path: Path, uid: int) -> None:
    with pytest.raises(ValueError, match=r"^nonroot_uid_required$"):
        create_bundle(tmp_path / "review", python=Path(sys.executable), uid=uid)
    assert not (tmp_path / "review").exists()


def test_bundle_refuses_shell_or_unit_path_interpolation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"^review_path_invalid$"):
        create_bundle(
            tmp_path / "bad%name", python=Path(sys.executable), uid=os.getuid()
        )


def test_bundle_refuses_missing_interpreter_source(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"^python_source_invalid$"):
        create_bundle(
            tmp_path / "review", python=tmp_path / "missing-python", uid=os.getuid()
        )


def test_worker_result_only_uses_metadata_and_never_starts_pi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(resource, "getrlimit", lambda _key: (0, 0))
    monkeypatch.setattr(Path, "read_text", lambda _path: "NoNewPrivs:\t1\n")
    monkeypatch.setattr(os, "getcwd", lambda: "/srv/pi-cwd")

    def child(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        assert argv[0] == sys.executable
        assert kwargs["env"] == {}
        return subprocess.CompletedProcess(
            argv, 0, json.dumps([os.getuid(), [0, 0]]).encode(), b""
        )

    monkeypatch.setattr(subprocess, "run", child)
    monkeypatch.setattr(worker, "socket_denials", lambda: {"test": "denied"})
    result = worker.collect(expected_uid=os.getuid())
    assert result["result"] == "observed_expected"
    assert result["auth_calls"] == result["model_calls"] == 0
    assert worker.collect(expected_uid=os.getuid() + 1)["result"] == "unknown"
    monkeypatch.setattr(resource, "getrlimit", lambda _key: (0, -1))
    assert worker.collect(expected_uid=os.getuid())["result"] == "unknown"


@pytest.mark.parametrize(
    "observed_errno, expected", [(errno.EPERM, "denied"), (errno.EINVAL, "unknown")]
)
def test_socket_check_only_allocates_and_records_controlled_reason(
    monkeypatch: pytest.MonkeyPatch, observed_errno: int, expected: str
) -> None:
    def denied(_family: int, _kind: int) -> None:
        raise OSError(observed_errno, "must-not-be-exported")

    monkeypatch.setattr(socket, "socket", denied)
    result = worker.socket_denials()
    assert len(result) == 5
    assert set(result.values()) == {expected}
    assert "must-not-be-exported" not in repr(result)


def test_existing_service_receipt_blocks_before_any_collect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import runpy

    receipt = tmp_path / "receipt.json"
    receipt.write_text('{"result":"old"}')

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("must reserve receipt before any child/socket operation")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(
        sys, "argv", ["worker.py", "--expected-uid", str(os.getuid()), str(receipt)]
    )
    with pytest.raises(FileExistsError):
        runpy.run_path(
            str(PROJECT / "scripts/issue167_h1_worker.py"), run_name="__main__"
        )
    assert json.loads(receipt.read_text()) == {"result": "old"}


def test_interrupted_service_retains_reservation_and_never_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = tmp_path / "receipt.json"
    calls = []

    def interrupted(**kwargs: object) -> dict[str, object]:
        calls.append(1)
        raise KeyboardInterrupt

    monkeypatch.setattr(worker, "collect", interrupted)
    with pytest.raises(KeyboardInterrupt):
        worker.run_once(receipt)
    assert json.loads(receipt.read_text())["result"] == "reserved_unknown"
    with pytest.raises(FileExistsError):
        worker.run_once(receipt)
    assert calls == [1]
