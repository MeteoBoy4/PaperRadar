"""Independent D1: preparation only; no root/service/auth/model execution."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from scripts import issue167_live_runtime, issue167_materials, issue167_node_diag_supply
from scripts import issue167_live_signal_bundle as bundle
from scripts import issue167_live_signal_case as case
from scripts.issue167_resolver_bundle import PROJECT


def required(source: str) -> set[str]:
    tree = ast.parse(source)
    function = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "source_bytes"
    )
    assignment = next(
        n
        for n in ast.walk(function)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "required" for t in n.targets)
    )
    value = ast.literal_eval(assignment.value)
    assert type(value) is set
    result: set[str] = set()
    for entry in value:
        assert type(entry) is str
        result.add(entry)
    return result


def test_preparation_stays_closed_before_allocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bundle, "PREPARATION_READY", False)
    destination = tmp_path / "blocked"
    with pytest.raises(ValueError, match="signal_preparation_not_ready"):
        bundle.create_bundle(destination, tmp_path / "no-profile")
    assert not destination.exists()


def test_single_material_replays_public_chain_with_new_fingerprint(
    tmp_path: Path,
) -> None:
    from paper_radar.config import StageName, compile_config, upgrade_database
    from paper_radar.llm import build_call, render_request
    from paper_radar.stage_inputs import replay_stage_input

    seed = tmp_path / "seed"
    old = issue167_materials.generate(seed)
    files = bundle.material_files(seed)
    manifest = json.loads(files["manifest.json"])
    assert manifest["kind"] == "synthetic_E01_value_low_only"
    assert len(manifest["cases"]) == 1
    cell = manifest["cases"][0]
    assert (cell["case"], cell["consumer"], cell["thinking"]) == (
        "value-low-E01",
        "value",
        "low",
    )
    assert set(cell["sha256"]) == {
        "stage-input.json",
        "description.json",
        "system.txt",
        "user.txt",
        "expected-valid-output.json",
    }
    assert len(files) == 23
    assert not any("high" in n or n.endswith(".sqlite3") for n in files)
    assert cell["fingerprint"] not in {x["fingerprint"] for x in old["cases"]}
    tree = tmp_path / "replayed"
    for name, raw in files.items():
        p = tree / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
    database = tmp_path / "replay.sqlite3"
    upgrade_database(database)
    snapshot = compile_config(tree / "config/settings-low.yaml", database)
    stage = replay_stage_input(
        files["value-low-E01/stage-input.json"], cell["fingerprint"], snapshot=snapshot
    )
    assert stage.stage is StageName.VALUE
    description = build_call(stage, snapshot, snapshot)
    assert description.provider == "openai" and description.model == "gpt-6.1-sol"
    assert description.thinking_level == "low"
    assert render_request(description) == files["value-low-E01/user.txt"]


def test_required_member_specialization_keeps_generic_unchanged() -> None:
    generic = (PROJECT / "scripts/issue167_h1_auto_bootstrap.py").read_text()
    updated = bundle.specialize_bootstrap(generic)
    assert "issue167_h1_network_worker.py" in required(generic)
    assert "issue167_h1_network_worker.py" not in required(updated)
    assert {
        "issue167_live_signal_case.py",
        "issue167_live_signal_owner.py",
        "issue167_live_signal_worker.py",
        "issue167_live_signal_cleanup.py",
    } <= required(updated)
    assert 'len(manifest["members"]) > 40' in updated
    assert (PROJECT / "scripts/issue167_h1_auto_bootstrap.py").read_text() == generic
    with pytest.raises(ValueError, match="signal_bootstrap_shape_unknown"):
        bundle.specialize_bootstrap(generic + generic)


@pytest.mark.parametrize(
    "state,code",
    [
        ("observed_expected_and_restored", 0),
        ("not_triggered_and_restored", 0),
        ("unknown", 1),
    ],
)
def test_real_local_result_reader_preserves_distinct_terminals(
    tmp_path: Path, state: str, code: int
) -> None:
    temporary = tmp_path / "owner-output"
    result_dir = tmp_path / "results"
    result_dir.mkdir()
    payload = {
        "scope": "h1_owner_automation_only",
        "run_id": case.RUN,
        "manifest_sha256": "a" * 64,
        "owner_result": state,
        "preflight_result": {"scope": case.SCOPE, "result": state},
    }
    temporary.write_text(json.dumps(payload))
    temporary.chmod(0o600)
    output = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-",
            str(tmp_path),
            str(temporary),
            str(code),
        ],
        input=bundle.result_reader(case.RUN, "a" * 64).encode(),
        capture_output=True,
        check=False,
    )
    value = json.loads((result_dir / "owner-run.json").read_text())
    assert value == payload
    assert output.returncode == (0 if state == "observed_expected_and_restored" else 1)
    assert not temporary.exists()
    if state == "not_triggered_and_restored":
        assert b"not_triggered_and_restored" in output.stdout


@pytest.mark.parametrize(
    "mutation", ["run", "sha", "scope", "inner", "code", "missing", "oversize"]
)
def test_reader_rejects_contradictions_as_unknown(
    tmp_path: Path, mutation: str
) -> None:
    temporary = tmp_path / "owner-output"
    (tmp_path / "results").mkdir()
    payload: dict[str, object] = {
        "scope": "h1_owner_automation_only",
        "run_id": case.RUN,
        "manifest_sha256": "a" * 64,
        "owner_result": "observed_expected_and_restored",
        "preflight_result": {
            "scope": case.SCOPE,
            "result": "observed_expected_and_restored",
        },
    }
    if mutation in {"run", "sha", "scope"}:
        payload[
            {"run": "run_id", "sha": "manifest_sha256", "scope": "scope"}[mutation]
        ] = "unexpected"
    elif mutation == "inner":
        payload["preflight_result"] = {
            "scope": case.SCOPE,
            "result": "not_triggered_and_restored",
        }
    elif mutation == "missing":
        payload.pop("run_id")
    raw = json.dumps(payload).encode()
    if mutation == "oversize":
        raw += b" " * 131073
    temporary.write_bytes(raw)
    temporary.chmod(0o600)
    output = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-",
            str(tmp_path),
            str(temporary),
            "1" if mutation == "code" else "0",
        ],
        input=bundle.result_reader(case.RUN, "a" * 64).encode(),
        capture_output=True,
        check=False,
    )
    result = json.loads((tmp_path / "results/owner-run.json").read_text())
    assert output.returncode == 1
    assert (
        result["owner_result"] == "unknown"
        and result["failure_stage"] == "owner_output_unknown"
    )


def test_new_core_has_exact_runtime_closure_rules_and_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import issue167_service_egress as egress
    from tests.test_issue167_live_runtime import fixture_binding

    seed = tmp_path / "seed"
    issue167_materials.generate(seed)
    app = fixture_binding(tmp_path)
    monkeypatch.setattr(bundle, "PREPARATION_READY", True)
    monkeypatch.setattr(issue167_live_runtime, "prepare_binding", lambda: app)
    monkeypatch.setattr(
        issue167_node_diag_supply, "prepare_binding", lambda: {"fixture": "no-real-DB"}
    )
    root = bundle.create_bundle(
        tmp_path / "candidate",
        PROJECT / "intent/review/issue-167/real-exit-plan-v1.json",
        material_source=seed,
    )
    manifest = json.loads((root / "manifest.json").read_text())
    members = set(manifest["members"])
    assert len(members) == 40
    assert (
        not any(n.endswith(".nft") for n in members) and "members.sha256" not in members
    )
    assert required((root / "issue167_h1_auto_bootstrap.py").read_text()) <= members
    assert (
        root / "issue167_h1_auto_bootstrap.py"
    ).read_text() == bundle.specialize_bootstrap(
        (PROJECT / "scripts/issue167_h1_auto_bootstrap.py").read_text()
    )
    context = json.loads((root / "live-context.json").read_text())
    assert (
        issue167_live_runtime.load_binding(
            root / "live-context.json", key="application_runtime"
        )
        == app
    )
    assert (
        len(context) == 8
        and context["auth_input_declaration"] == case.AUTH_INPUT_REQUIREMENTS
    )
    plan = case.Case.from_dict(json.loads((root / "plan.json").read_text()))
    profile = egress.FrozenEgress.from_profile(
        plan.base_plan(),
        (root / "profile.json").read_bytes(),
        plan.profile_sha256,
        json.loads((root / "host-context.json").read_text()),
    )
    rules = json.loads((root / "review-rules.json").read_text())
    assert rules == {
        "create": egress.render_create(profile),
        "activate": egress.render_activate(profile),
        "clear": egress.render_clear(profile),
        "delete": egress.render_delete(profile),
    }
    seal = json.loads((root / "review-seal.json").read_text())
    assert (
        seal["driver_sha256"]
        == hashlib.sha256((root / "owner-wizard.sh").read_bytes()).hexdigest()
    )
    assert (
        seal["manifest_sha256"]
        == hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()
    )
    guard = (root / "owner-wizard.sh").read_text().split("run_owner_auto()", 1)[
        0
    ] + "printf 'guard-ok\\n'\n"
    flags = [
        "--owner-config-confirmed",
        "--owner-dns-unknown-confirmed",
        "--owner-real-calls-confirmed",
        "--owner-external-sigint-confirmed",
    ]
    for omitted in range(4):
        out = subprocess.run(
            ["bash", "-c", guard, "guard", *(flags[:omitted] + flags[omitted + 1 :])],
            capture_output=True,
            check=False,
        )
        assert out.returncode == 2
    out = subprocess.run(
        ["bash", "-c", guard, "guard", *flags], capture_output=True, check=False
    )
    assert out.returncode == 0 and out.stdout == b"guard-ok\n"
    assert not list((root / "results").iterdir())
    # Import the actual sealed owner/worker closure, without either main, under
    # isolated stdlib Python. No writable application package may be imported.
    loader = """import importlib,json,sys,types
from pathlib import Path
root=Path(sys.argv[1]).resolve()
package=types.ModuleType('scripts');package.__path__=[str(root)]
sys.modules['scripts']=package
for name in ('issue167_live_signal_owner','issue167_live_signal_worker'):
    module=importlib.import_module('scripts.'+name)
    assert module.__file__==str(root/(name+'.py'))
assert not any(n=='paper_radar' or n.startswith('paper_radar.') for n in sys.modules)
print('sealed-closure-loaded-without-main-or-app')
"""
    loaded = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-", str(root)],
        input=loader.encode(),
        capture_output=True,
        check=False,
        timeout=5,
    )
    assert loaded.returncode == 0 and loaded.stderr == b""
    assert loaded.stdout == b"sealed-closure-loaded-without-main-or-app\n"
    assert bundle.isolated_snapshot_control(root) == {
        "scope": "isolated_sealed_module_synthetic_snapshot_control",
        "main_calls": 0,
        "application_imports": 0,
        "snapshot_nodes": 7,
        "integrity": "complete",
        "regular_credential_contents_opened": 0,
        "helper_source": "same_prepared_copy_only",
    }


def test_generated_cleanup_loads_exact_boundary_and_parser(tmp_path: Path) -> None:
    raw = bundle.cleanup_source()
    module = types.ModuleType("issue167_e01_cleanup_fixture")
    module.__file__ = "<sealed-E01-cleanup-fixture>"
    sys.modules[module.__name__] = module
    try:
        exec(compile(raw, module.__file__, "exec"), module.__dict__)
        assert not {"main", "perform", "RUN", "CODE", "RUNTIME", "LEDGER"} & set(
            module.__dict__
        )
        assert module.ProbeRejected is module.CleanupRejected
        for filename, (sha, names) in bundle.SOURCE_PINS.items():
            proof = module.SOURCE_CHUNKS[filename]
            assert proof["sha256"] == sha
            source = (PROJECT / "scripts" / filename).read_text()
            lines = source.splitlines(keepends=True)
            tree = ast.parse(source)
            for name in names:
                node = next(
                    n
                    for n in tree.body
                    if (
                        isinstance(n, (ast.FunctionDef, ast.ClassDef))
                        and n.name == name
                    )
                    or (
                        isinstance(n, ast.Assign)
                        and any(
                            isinstance(t, ast.Name) and t.id == name for t in n.targets
                        )
                    )
                )
                first = (
                    min([node.lineno, *(d.lineno for d in node.decorator_list)])
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                    else node.lineno
                )
                chunk = "".join(lines[first - 1 : node.end_lineno]).encode()
                assert proof["segments"][name] == hashlib.sha256(chunk).hexdigest()
                assert chunk in raw
        root = tmp_path / "tree"
        root.mkdir(mode=0o755)
        (root / "worker").mkdir(mode=0o700)
        (root / "worker/control.json").write_bytes(b"synthetic")
        (root / "worker/control.json").chmod(0o600)
        inventory = {
            "": module.identity(root.lstat()),
            "worker": module.identity((root / "worker").lstat()),
            "worker/control.json": module.identity(
                (root / "worker/control.json").lstat()
            ),
        }
        tree = module.Tree(root, inventory, os.getuid(), os.getuid())
        try:
            tree.inspect()
            assert (
                tree.read_metadata("worker/control.json", uid=os.getuid(), mode=0o600)
                == b"synthetic"
            )
            outside = module.mount_points(
                b"1 0 0:1 mnt:[123] /outside rw - nsfs nsfs rw\n"
            )
            module.check_mounts((root,), outside)
            with pytest.raises(module.CleanupRejected, match="artifact_mount_unknown"):
                module.check_mounts((root,), {root / "worker"})
            with pytest.raises(module.CleanupRejected, match="mount_metadata_unknown"):
                module.mount_points(b"1 0 0:1 mnt:[123] //outside rw - nsfs nsfs rw\n")
            assert tree.remove() == 3
        finally:
            tree.close()
        assert not root.exists()
    finally:
        sys.modules.pop(module.__name__, None)


def test_cleanup_source_drift_blocks_generation_before_use(tmp_path: Path) -> None:
    source_dir = tmp_path / "scripts"
    source_dir.mkdir()
    for filename in bundle.SOURCE_PINS:
        (source_dir / filename).write_bytes(
            (PROJECT / "scripts" / filename).read_bytes()
        )
    changed = source_dir / "issue167_live_artifact_cleanup.py"
    changed.write_bytes(changed.read_bytes() + b"\n# changed\n")
    with pytest.raises(ValueError, match="signal_cleanup_source_changed"):
        bundle.cleanup_source(tmp_path)


@pytest.mark.parametrize("length", [131071, 131072, 131073])
def test_actual_local_reader_keeps_exact_existing_byte_cap(
    tmp_path: Path, length: int
) -> None:
    (tmp_path / "results").mkdir()
    temporary = tmp_path / "owner-output"
    payload = {
        "scope": "h1_owner_automation_only",
        "run_id": case.RUN,
        "manifest_sha256": "a" * 64,
        "owner_result": "observed_expected_and_restored",
        "preflight_result": {
            "scope": case.SCOPE,
            "result": "observed_expected_and_restored",
        },
    }
    raw = json.dumps(payload).encode()
    temporary.write_bytes(raw + b" " * (length - len(raw)))
    temporary.chmod(0o600)
    output = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-", str(tmp_path), str(temporary), "0"],
        input=bundle.result_reader(case.RUN, "a" * 64).encode(),
        capture_output=True,
        check=False,
    )
    result = json.loads((tmp_path / "results/owner-run.json").read_text())
    assert output.returncode == (0 if length <= 131072 else 1)
    assert result["owner_result"] == (
        "observed_expected_and_restored" if length <= 131072 else "unknown"
    )


def test_actual_local_reader_refuses_duplicate_json_keys(tmp_path: Path) -> None:
    (tmp_path / "results").mkdir()
    temporary = tmp_path / "owner-output"
    temporary.write_bytes(
        b'{"owner_result":"unknown","owner_result":"observed_expected_and_restored"}'
    )
    temporary.chmod(0o600)
    output = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-", str(tmp_path), str(temporary), "0"],
        input=bundle.result_reader(case.RUN, "a" * 64).encode(),
        capture_output=True,
        check=False,
    )
    result = json.loads((tmp_path / "results/owner-run.json").read_text())
    assert output.returncode == 1 and result["failure_stage"] == "owner_output_unknown"


@pytest.mark.parametrize("alias", ["symlink", "hardlink"])
def test_local_reader_rejects_alias_even_when_target_is_valid_result(
    tmp_path: Path, alias: str
) -> None:
    (tmp_path / "results").mkdir()
    target = tmp_path / "synthetic-target"
    target.write_text(
        json.dumps(
            {
                "scope": "h1_owner_automation_only",
                "run_id": case.RUN,
                "manifest_sha256": "a" * 64,
                "owner_result": "observed_expected_and_restored",
                "preflight_result": {
                    "scope": case.SCOPE,
                    "result": "observed_expected_and_restored",
                },
            }
        )
    )
    target.chmod(0o600)
    temporary = tmp_path / "owner-output"
    if alias == "symlink":
        temporary.symlink_to(target)
    else:
        os.link(target, temporary)
    output = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-", str(tmp_path), str(temporary), "0"],
        input=bundle.result_reader(case.RUN, "a" * 64).encode(),
        capture_output=True,
        check=False,
        timeout=3,
    )
    result = json.loads((tmp_path / "results/owner-run.json").read_text())
    assert output.returncode == 1 and result["failure_stage"] == "owner_output_unknown"
    assert target.exists()


def test_real_near_cap_owner_envelope_survives_actual_local_reader(
    tmp_path: Path,
) -> None:
    from tests.test_issue167_live_signal_owner import near_cap_owner_envelope

    envelope = near_cap_owner_envelope()
    encoded = json.dumps(envelope, sort_keys=True).encode()
    assert len(encoded) < 131072
    root_result = envelope["preflight_result"]
    assert len(root_result["rules"]["snapshots"]) == 8
    assert len(json.dumps(root_result["worker_result"]).encode()) < 65536
    (tmp_path / "results").mkdir()
    temporary = tmp_path / "owner-output"
    temporary.write_bytes(encoded)
    temporary.chmod(0o600)
    out = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-", str(tmp_path), str(temporary), "0"],
        input=bundle.result_reader(case.RUN, "a" * 64).encode(),
        capture_output=True,
        check=False,
    )
    assert out.returncode == 0 and out.stderr == b""
    assert json.loads((tmp_path / "results/owner-run.json").read_bytes()) == envelope
