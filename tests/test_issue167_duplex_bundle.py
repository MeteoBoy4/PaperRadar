"""Independent D1: pure bundle/reader controls, never a host/network experiment."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import issue167_duplex_bundle as bundle
from scripts import issue167_duplex_probe as probe
from tests.test_issue167_duplex_probe import FakeOps

SHA = "1" * 64
ROOT_SHA = "2" * 64


def result() -> dict[str, Any]:
    return {
        "scope": probe.SCOPE,
        "run_id": probe.RUN,
        "result": "observed_expected_and_restored",
        "limits": dict(probe.LIMITS),
        "installed_manifest_sha256": ROOT_SHA,
        "restoration": {
            "unit_absent": True,
            "table_absent": True,
            "cgroup_empty": True,
            "peer_reaped": True,
            "ledger_retained": True,
        },
        "artifacts": {"code_runtime_removed": True, "ledger_retained": True},
    }


def run_reader(tmp_path: Path, raw: bytes, status: int) -> tuple[int, dict[str, Any]]:
    output = tmp_path / "output.json"
    output.write_bytes(raw)
    output.chmod(0o600)
    (tmp_path / "results").mkdir(mode=0o700)
    process = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-",
            str(tmp_path),
            str(output),
            str(status),
        ],
        input=bundle.local_result_source(SHA, ROOT_SHA).encode(),
        capture_output=True,
        check=False,
        timeout=5,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    assert process.stderr == b""
    return process.returncode, json.loads(
        (tmp_path / "results/owner-run.json").read_bytes()
    )


def test_worker_entry_is_closed_and_only_calls_synthetic_role() -> None:
    raw = bundle.worker_entry()
    parsed = ast.parse(raw)
    assert not any(
        isinstance(n, ast.ImportFrom) and (n.module or "").startswith("paper_radar")
        for n in ast.walk(parsed)
    )
    assert b"worker_main" in raw and b"client" in raw and b"peer" in raw
    assert b"O_NOFOLLOW" in raw and b"sha256" in raw


def test_actual_local_reader_keeps_complete_positive(tmp_path: Path) -> None:
    value = result()
    rc, actual = run_reader(tmp_path, (json.dumps(value) + "\n").encode(), 0)
    assert rc == 0
    assert actual == {**value, "owner_exit_status": 0, "manifest_sha256": SHA}


def test_actual_local_reader_keeps_unknown(tmp_path: Path) -> None:
    value = result()
    value["result"] = "unknown"
    value["failure_reason"] = "closed_reason"
    rc, actual = run_reader(tmp_path, (json.dumps(value) + "\n").encode(), 1)
    assert rc == 1 and actual["result"] == "unknown"
    assert actual["failure_reason"] == "closed_reason"


@pytest.mark.parametrize(
    "mutation", ["wrong_run", "wrong_root", "bool_limit", "bad_restore", "wrong_exit"]
)
def test_actual_reader_mismatch_becomes_unknown(tmp_path: Path, mutation: str) -> None:
    value = result()
    status = 0
    if mutation == "wrong_run":
        value["run_id"] = "0" * 12
    elif mutation == "wrong_root":
        value["installed_manifest_sha256"] = "9" * 64
    elif mutation == "bool_limit":
        value["limits"]["active_connect_entries"] = True
    elif mutation == "bad_restore":
        value["restoration"]["table_absent"] = 1
    else:
        status = 1
    rc, actual = run_reader(tmp_path, json.dumps(value).encode(), status)
    assert rc == 1 and actual["result"] == "unknown"
    assert actual["failure_reason"] == "owner_output_unknown"


@pytest.mark.parametrize(
    "raw",
    [b'{"scope":"x","scope":"y"}', b"not-json", b" " * 131073],
    ids=["duplicate", "invalid", "oversize"],
)
def test_actual_reader_bad_input_never_echoes_raw(tmp_path: Path, raw: bytes) -> None:
    rc, actual = run_reader(tmp_path, raw, 0)
    assert rc == 1 and actual["failure_reason"] == "owner_output_unknown"


@pytest.mark.parametrize(
    "number",
    [float("nan"), float("inf"), -float("inf")],
    ids=["nan", "infinity", "negative_infinity"],
)
def test_actual_reader_rejects_non_json_numeric_constants(
    tmp_path: Path, number: float
) -> None:
    value = result()
    value["observation"] = number
    rc, actual = run_reader(tmp_path, json.dumps(value).encode(), 0)
    assert rc == 1 and actual["failure_reason"] == "owner_output_unknown"


@pytest.mark.parametrize("alias", ["symlink", "hardlink"])
def test_actual_reader_refuses_symlink_and_multilink(
    tmp_path: Path, alias: str
) -> None:
    (tmp_path / "results").mkdir(mode=0o700)
    original = tmp_path / "original.json"
    original.write_text(json.dumps(result()))
    output = tmp_path / "output.json"
    if alias == "symlink":
        output.symlink_to(original)
    else:
        os.link(original, output)
    process = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-", str(tmp_path), str(output), "0"],
        input=bundle.local_result_source(SHA, ROOT_SHA).encode(),
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert process.returncode == 1 and process.stderr == b""
    assert (
        json.loads((tmp_path / "results/owner-run.json").read_bytes())["failure_reason"]
        == "owner_output_unknown"
    )


def test_driver_requires_explicit_approval_before_reserving() -> None:
    files = {n: b"public synthetic source" for n in probe.CORE_NAMES}
    config = {
        "scope": probe.SCOPE,
        "run_id": probe.RUN,
        "members": {n: bundle.digest(v) for n, v in files.items()},
        "tools": {},
    }
    files["scope.json"] = bundle.encoded(config)
    raw = bundle.render_driver(config, files, SHA)
    assert raw.index(b"--owner-duplex-synthetic-confirmed") < raw.index(
        b"execution-started.json"
    )
    assert raw.count(b"/usr/bin/sudo ") == 1
    assert b"sudo -S" not in raw and b"read -s" not in raw


def fake_tools() -> dict[str, dict[str, str]]:
    return {
        name: {"path": "/usr/bin/python3", "sha256": "3" * 64}
        for name in ("python", "systemctl", "nft", "systemd_analyze")
    }


def test_preparation_guard_precedes_even_public_metadata_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bundle, "PREPARATION_READY", False)

    def forbidden() -> dict[str, dict[str, str]]:
        raise AssertionError("metadata read before readiness")

    monkeypatch.setattr(bundle, "prepare_tools", forbidden)
    with pytest.raises(ValueError, match="duplex_preparation_not_ready"):
        bundle.build_package(tmp_path / "out", bundle.PROJECT)
    assert not (tmp_path / "out").exists()


def test_real_builder_keeps_root_and_review_manifests_acyclic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bundle, "PREPARATION_READY", True)
    monkeypatch.setattr(bundle, "prepare_tools", fake_tools)
    monkeypatch.setattr(probe, "host_context", lambda: {"public": "synthetic"})
    destination = tmp_path / "out"
    identity = bundle.build_package(destination, bundle.PROJECT)
    outer = json.loads((destination / "manifest.json").read_bytes())
    root = json.loads((destination / "installed-manifest.json").read_bytes())
    config = json.loads((destination / "scope.json").read_bytes())
    assert len(config["members"]) == 7
    assert len(root["members"]) == 8
    assert len(outer["members"]) == 10
    assert "scope.json" not in config["members"]
    assert "manifest.json" not in root["members"]
    assert "owner-review.md" not in root["members"]
    assert root["members"]["scope.json"] == bundle.digest(
        (destination / "scope.json").read_bytes()
    )
    assert outer["root_manifest_sha256"] == bundle.digest(
        (destination / "installed-manifest.json").read_bytes()
    )
    for name, want in outer["members"].items():
        assert bundle.digest((destination / name).read_bytes()) == want
    assert identity["review_seal_sha256"] == bundle.digest(
        (destination / "review-seal.json").read_bytes()
    )
    assert not list((destination / "results").iterdir())
    assert (destination / "owner-wizard.sh").read_bytes() == bundle.render_driver(
        config,
        {n: (destination / n).read_bytes() for n in root["members"]},
        identity["manifest_sha256"],
    )


@pytest.mark.parametrize("limit", [131071, 131072, 131073])
def test_actual_reader_exact_size_boundary(tmp_path: Path, limit: int) -> None:
    raw = json.dumps(result(), separators=(",", ":")).encode()
    raw += b" " * (limit - len(raw))
    rc, value = run_reader(tmp_path, raw, 0)
    if limit <= bundle.MAX_RESULT_BYTES:
        assert rc == 0 and value["result"] == "observed_expected_and_restored"
    else:
        assert rc == 1 and value["failure_reason"] == "owner_output_unknown"


def test_actual_complete_root_envelope_roundtrip_without_padding(
    tmp_path: Path,
) -> None:
    class BoundFakeOps(FakeOps):
        installed_manifest_sha256 = ROOT_SHA

    ops = BoundFakeOps()
    value = probe.run_owner(ops)
    assert value["result"] == "observed_expected_and_restored"
    assert len(value["rules"]) == 7  # type: ignore[arg-type]
    raw = bundle.encoded(value)
    assert len(raw) < bundle.MAX_RESULT_BYTES
    rc, saved = run_reader(tmp_path, raw, 0)
    assert rc == 0
    assert saved == {**value, "manifest_sha256": SHA, "owner_exit_status": 0}
    assert saved["limits"]["expected_application_send_entries"] == 10


def test_actual_literal_five_module_load_with_only_main_removed() -> None:
    files = {
        short + ".py": (bundle.PROJECT / "scripts" / (short + ".py")).read_bytes()
        for short in bundle.MODULE_ORDER
        if short != "issue167_duplex_cleanup"
    }
    files["issue167_duplex_cleanup.py"] = bundle.cleanup_source()
    files["worker-entry.py"] = bundle.worker_entry()
    files["probe.service"] = probe.render_unit(
        probe.Case(), "/usr/bin/python3"
    ).encode()
    config = {
        "scope": probe.SCOPE,
        "run_id": probe.RUN,
        "tools": fake_tools(),
        "members": {n: bundle.digest(v) for n, v in files.items()},
    }
    files["scope.json"] = bundle.encoded(config)
    payload = bundle.encoded(
        {
            "config": config,
            "files": {
                n: __import__("base64").b64encode(v).decode() for n, v in files.items()
            },
            "root_manifest": __import__("base64")
            .b64encode(probe.installed_manifest(config, files))
            .decode(),
        }
    )
    code = ast.parse(bundle.root_literal(payload, ROOT_SHA))
    removed = 0
    for node in ast.walk(code):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "owner"
            and node.value.func.attr == "owner_main"
        ):
            node.value = ast.Constant(0)
            removed += 1
    assert removed == 1
    program = """import json,os,signal,socket,sqlite3,subprocess,sys
calls=[]
def forbidden(*args,**kwargs):
    calls.append(True);raise AssertionError('active operation')
subprocess.Popen=forbidden;socket.socket=forbidden;sqlite3.connect=forbidden
signal.pidfd_send_signal=forbidden;os.kill=forbidden;os.killpg=forbidden
try:
    exec(SOURCE)
except SystemExit as e:
    assert e.code==0
assert not calls
assert not any(n=='paper_radar' or n.startswith('paper_radar.') for n in sys.modules)
assert len([n for n in sys.modules if n.startswith('scripts.')])==5
print('five_modules_loaded_main_zero')
""".replace("SOURCE", repr(ast.unparse(ast.fix_missing_locations(code))))
    actual = subprocess.run(
        ["/usr/bin/python3", "-I", "-S", "-B", "-"],
        input=program.encode(),
        capture_output=True,
        check=False,
        timeout=10,
        cwd="/tmp",
    )
    assert actual.returncode == 0 and actual.stderr == b""
    assert actual.stdout == b"five_modules_loaded_main_zero\n"
