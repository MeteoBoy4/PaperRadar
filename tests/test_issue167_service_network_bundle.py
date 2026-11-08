"""Independent D1: only offline package generation and local flag rejection."""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts import issue167_service_network_bundle as bundle
from scripts import issue167_service_network_case as contract

PROFILE = Path(__file__).parents[1] / "intent/review/issue-167/real-exit-plan-v1.json"


def test_network_package_seals_actual_members_sources_and_explicit_flag(
    tmp_path: Path,
) -> None:
    root = bundle.create_bundle(tmp_path / "review", "f287c9ad630e", PROFILE)
    manifest = json.loads((root / "manifest.json").read_text())
    seal = json.loads((root / "review-seal.json").read_text())

    def digest(raw: bytes) -> str:
        return hashlib.sha256(raw).hexdigest()

    assert seal["manifest_sha256"] == digest((root / "manifest.json").read_bytes())
    assert seal["driver_sha256"] == digest((root / "owner-wizard.sh").read_bytes())
    for name, sha in manifest["members"].items():
        assert digest((root / name).read_bytes()) == sha
        if name.endswith(".py"):
            compile((root / name).read_bytes(), name, "exec")
    for name in ("case", "worker", "owner"):
        filename = f"issue167_service_network_{name}.py"
        assert (root / filename).read_bytes() == (
            Path(__file__).parents[1] / "scripts" / filename
        ).read_bytes()
    value = contract.Case.from_dict(json.loads((root / "plan.json").read_text()))
    assert (root / value.unit).read_text() == contract.render_unit(value)
    assert list((root / "results").iterdir()) == []
    refused = subprocess.run(
        ["/bin/bash", str(root / "owner-wizard.sh")], capture_output=True, check=False
    )
    assert refused.returncode == 2
    assert "--owner-config-confirmed" in refused.stderr.decode()
    assert list((root / "results").iterdir()) == []
    subprocess.run(["/bin/bash", "-n", str(root / "owner-wizard.sh")], check=True)


@pytest.mark.parametrize("owner", [True, False])
def test_entry_verifies_every_member_before_importing_siblings(owner: bool) -> None:
    source = bundle.entry(
        "issue167_service_network_owner"
        if owner
        else "issue167_service_network_worker",
        owner=owner,
    )
    assert source.index("for name,sha in") < source.index("importlib.import_module")
    assert "os.O_NOFOLLOW|os.O_NONBLOCK" in source
    assert "info.st_uid!=0" in source
    assert "info.st_nlink!=1" in source
    assert "64*1024*1024" in source
    assert "package.__path__=[str(root)]" in source
