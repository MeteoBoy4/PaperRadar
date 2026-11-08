"""#167 离线材料可复现及无授权边界。"""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.issue167_materials import generate


def test_six_cells_are_reproducible_sealed_and_unapproved(tmp_path: Path) -> None:
    first = generate(tmp_path / "first")
    second = generate(tmp_path / "second")
    assert first == second
    frozen = (
        Path(__file__).resolve().parents[1]
        / "intent/review/issue-167/synthetic-manifest.json"
    )
    assert first == json.loads(frozen.read_bytes())
    assert first["authorization"] == "not_granted"
    assert first["source_kind"] == "synthetic_canonical_not_docling_observation"
    cases = first["cases"]
    assert {(case["consumer"], case["thinking"]) for case in cases} == {
        (consumer, level)
        for consumer in ("boundary", "value", "read")
        for level in ("low", "high")
    }
    assert len({case["fingerprint"] for case in cases}) == 6
    for case in cases:
        folder = tmp_path / "first" / case["case"]
        for name, expected in case["sha256"].items():
            assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == expected
        descriptor = json.loads((folder / "description.json").read_bytes())
        assert descriptor["provider"] == "openai"
        assert descriptor["model"] == "gpt-6.1-sol"
        assert descriptor["sampling"] == "provider_default"
        assert descriptor["temperature"] is None
        assert descriptor["top_p"] is None
        assert (folder / "expected-valid-output.json").is_file()


def test_existing_seal_cannot_be_overwritten(tmp_path: Path) -> None:
    root = tmp_path / "sealed"
    root.mkdir()
    marker = root / "manifest.json"
    marker.write_bytes(b"unchanged")
    with pytest.raises(FileExistsError):
        generate(root)
    assert marker.read_bytes() == b"unchanged"
