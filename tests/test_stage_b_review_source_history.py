"""#185 独立 D1:原 v28 manifest 的独立历史保护。"""

import hashlib
import json
from pathlib import Path

from tests.test_live_admission_source_guard import V28_SOURCE_FILES


def test_original_v28_manifest_retains_original_bytes_and_274_sources() -> None:
    path = Path(__file__).parent / "fixtures/live-admission-source-guard-v28.json"
    raw = path.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "cd6ad7bb74b954002e40db4d5c6e7bb861f0be7108811b1b3a80607bb89d044e"
    )
    manifest = json.loads(raw)
    assert manifest["policies"]["admission"] == "pi-admission-v28"
    assert len(manifest["files"]) == 274
    assert set(manifest["files"]) == set(V28_SOURCE_FILES)
