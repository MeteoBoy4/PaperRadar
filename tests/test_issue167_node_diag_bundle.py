"""Independent D1: offline node bundle and pre-sudo confirmation flags."""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts import issue167_node_diag_bundle as bundle

PROFILE = Path(__file__).parents[1] / "intent/review/issue-167/real-exit-plan-v1.json"


@pytest.mark.parametrize(
    "flags", [[], ["--owner-config-confirmed"], ["--owner-dns-unknown-confirmed"]]
)
def test_missing_either_confirmation_rejects_before_reserve_or_sudo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    flags: list[str],
) -> None:
    monkeypatch.setattr(
        "scripts.issue167_node_diag_supply.prepare_binding", lambda: {"synthetic": True}
    )
    root = bundle.create_bundle(tmp_path / "review", "b62d4a90e713", PROFILE)
    result = subprocess.run(
        ["/bin/bash", str(root / "owner-wizard.sh"), *flags],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert list((root / "results").iterdir()) == []
    assert "--owner-dns-unknown-confirmed" in result.stderr.decode()
    subprocess.run(["/bin/bash", "-n", str(root / "owner-wizard.sh")], check=True)


def test_node_package_seals_source_mapping_and_independent_budget(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "scripts.issue167_node_diag_supply.prepare_binding", lambda: {"synthetic": True}
    )
    root = bundle.create_bundle(tmp_path / "review", "b62d4a90e713", PROFILE)
    manifest = json.loads((root / "manifest.json").read_text())
    seal = json.loads((root / "review-seal.json").read_text())

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    assert seal["manifest_sha256"] == digest(root / "manifest.json")
    assert seal["driver_sha256"] == digest(root / "owner-wizard.sh")
    assert len(manifest["members"]) == 39
    for name, sha in manifest["members"].items():
        assert digest(root / name) == sha
        if name.endswith(".py"):
            compile((root / name).read_bytes(), name, "exec")
    for role in ("case", "worker", "owner", "supply"):
        name = f"issue167_node_diag_{role}.py"
        assert (root / name).read_bytes() == (
            Path(__file__).parents[1] / "scripts" / name
        ).read_bytes()
    value = json.loads((root / "plan.json").read_text())
    assert value["network_limits"]["node_execs"] == 4
    assert value["network_limits"]["os_dns_queries"] == "unknown"
    assert "node_pi" not in value
    assert not (root / "network-worker-entry.py").exists()
    source = (root / "issue167_h1_owner_run.py").read_text()
    assert source.index("for name,sha in") < source.index("importlib.import_module")
    assert "scripts.issue167_node_diag_owner" in source
