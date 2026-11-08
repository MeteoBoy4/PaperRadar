"""Independent D1: source checkpoint cannot become a runnable batch implicitly."""

import ast
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts import issue167_live_bundle as bundle
from scripts import issue167_live_runtime as live_runtime
from scripts.issue167_resolver_bundle import PROJECT


def required_bootstrap_members(source: str) -> set[str]:
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
    assert type(value) is set and all(type(x) is str for x in value)
    return value


def test_disabled_preparation_blocks_before_allocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "unapproved-batch"
    monkeypatch.setattr(bundle, "PREPARATION_READY", False)
    with pytest.raises(ValueError, match="live_preparation_not_ready"):
        bundle.create_bundle(destination, "e93f7b82c461", tmp_path / "unused-profile")
    assert not destination.exists()


def test_existing_synthetic_manifest_still_has_exact_explicit_members(
    tmp_path: Path,
) -> None:
    from scripts.issue167_materials import generate

    source = tmp_path / "synthetic"
    generate(source)
    values = bundle.material_files(source)
    assert len(values) == 66 and "manifest.json" in values
    assert not any(name.endswith(".sqlite3") for name in values)


def test_generated_bundle_has_closed_bootstrap_members_and_embedded_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import issue167_node_diag_supply as supply
    from tests.test_issue167_live_runtime import fixture_binding

    app = fixture_binding(tmp_path)
    monkeypatch.setattr(bundle, "PREPARATION_READY", True)
    monkeypatch.setattr(live_runtime, "prepare_binding", lambda: app)
    monkeypatch.setattr(supply, "prepare_binding", lambda: {"fixture": "no-real-DB"})
    root = bundle.create_bundle(
        tmp_path / "candidate",
        "e93f7b82c461",
        PROJECT / "intent/review/issue-167/real-exit-plan-v1.json",
    )
    manifest = json.loads((root / "manifest.json").read_bytes())
    assert len(manifest["members"]) == 40
    copied = (root / "issue167_h1_auto_bootstrap.py").read_text()
    assert required_bootstrap_members(copied) <= set(manifest["members"])
    generic = (PROJECT / "scripts/issue167_h1_auto_bootstrap.py").read_text()
    assert "issue167_h1_network_worker.py" in required_bootstrap_members(generic)
    assert "issue167_live_worker.py" in required_bootstrap_members(copied)
    assert copied == bundle.specialize_bootstrap(generic)
    driver = (root / "owner-wizard.sh").read_text()
    assert copied.rstrip() in driver
    assert "application-runtime-binding.json" not in manifest["members"]
    assert (
        live_runtime.load_binding(root / "live-context.json", key="application_runtime")
        == app
    )
    assert not list((root / "results").iterdir())
    seal = json.loads((root / "review-seal.json").read_bytes())
    assert seal["driver_sha256"] == hashlib.sha256(driver.encode()).hexdigest()
    # Run only the argument guard prefix, with no owner function/sudo/root code.
    guard = driver.split("run_owner_auto()", 1)[0] + "printf 'guard-ok\\n'\n"
    flags = [
        "--owner-config-confirmed",
        "--owner-dns-unknown-confirmed",
        "--owner-real-calls-confirmed",
    ]
    for omitted in range(3):
        result = subprocess.run(
            ["bash", "-c", guard, "guard", *(flags[:omitted] + flags[omitted + 1 :])],
            capture_output=True,
            check=False,
        )
        assert result.returncode == 2
    allowed = subprocess.run(
        ["bash", "-c", guard, "guard", *flags], capture_output=True, check=False
    )
    assert allowed.returncode == 0 and allowed.stdout == b"guard-ok\n"
    assert not list((root / "results").iterdir())
