"""A3 备份独立合成材料与外部可观察状态。"""

from pathlib import Path

from paper_radar.config import compile_config
from paper_radar.storage.artifacts import ArtifactStore
from tests.config_test_support import boundary_inputs


def populated(root: Path) -> tuple[Path, Path, str]:
    settings, database = boundary_inputs(root)
    snapshot = compile_config(settings, database)
    data_root = root / "data"
    store = ArtifactStore(database, data_root)
    store.publish_single("original_pdf", (b"SECRET shared payload",))
    store.publish_single("source_snapshot", (b"SECRET shared payload",))
    store.publish_single("model_success_response", (b"SECRET model response",))
    return database, data_root, snapshot.snapshot_id


def tree(root: Path) -> dict[str, bytes | None]:
    return {
        str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
        for path in root.rglob("*")
    }
