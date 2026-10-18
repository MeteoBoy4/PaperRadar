"""公开 tree-v1 独立向量与真实小文件树。"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from paper_radar.pi_supply import SupplyError
from paper_radar.pi_supply.filesystem import tree_hash

VECTOR = "3ba7d3e8a26699a27360c5f3575eee704abe8cb77f572e0a21f768a798b96573"


def tiny_tree(root: Path) -> None:
    (root / "bin").mkdir(parents=True)
    (root / "bin/run").write_bytes(b"hi\n")
    (root / "bin/run").chmod(0o755)
    (root / "run").symlink_to("bin/run")


def test_tree_independent_literal_vector_across_location_umask_and_mtime(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "stage-one", tmp_path / "other-stage"
    before = os.umask(0o022)
    try:
        tiny_tree(first)
        os.umask(0o077)
        tiny_tree(second)
    finally:
        os.umask(before)
    os.utime(second / "bin/run", (1, 1))
    assert tree_hash(first) == VECTOR
    assert tree_hash(second) == VECTOR
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path;import sys;"
            "from paper_radar.pi_supply.filesystem import tree_hash;"
            "print(tree_hash(Path(sys.argv[1])))",
            str(second),
        ],
        env={},
        capture_output=True,
        text=True,
        check=True,
    )
    assert process.stdout.strip() == VECTOR
    (second / "bin/run").write_bytes(b"bye\n")
    assert tree_hash(second) != VECTOR
    (second / "bin/run").write_bytes(b"hi\n")
    (second / "bin/run").chmod(0o644)
    assert tree_hash(second) != VECTOR


@pytest.mark.parametrize("target", ["../outside", "missing"])
def test_tree_rejects_broken_or_escaping_links(tmp_path: Path, target: str) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    (tmp_path / "outside").write_bytes(b"outside")
    (root / "link").symlink_to(target)
    with pytest.raises(SupplyError):
        tree_hash(root)


def test_manifest_independent_jq_canonical_hash_vector() -> None:
    from paper_radar.pi_supply.models import SupplyManifest

    fixture = Path(__file__).parent / "fixtures/pi_supply/manifest-vector.json"
    manifest = SupplyManifest.model_validate(json.loads(fixture.read_bytes()))
    assert (
        manifest.supply_id
        == "a68a0964d1913cabfd75b49034162096e24c9a0ee5dc428e69760c3d053f2ea7"
    )
    assert not manifest.canonical_bytes.endswith(b"\n")
