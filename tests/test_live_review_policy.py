"""D1: 历史 v11/v10 独立冻结锚;当前源码另由后继向量核验。"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V11_SHA256 = "b3209a6f797248e9db7d2a4469e62bb31b5aa6d1cfeb82ff320ee6a866987da7"


def test_v11_source_vector_matches_independent_review_anchor() -> None:
    raw = (ROOT / "tests/fixtures/live-admission-source-guard-v11.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == V11_SHA256
    vector = json.loads(raw)
    assert vector["policies"]["admission"] == "pi-admission-v11"
    assert vector["policies"]["launch"] == "pi-launch-1.4.0-v8"
    assert len(vector["files"]) == 71


def test_previous_v10_review_vector_is_not_rebound() -> None:
    raw = (ROOT / "tests/fixtures/live-admission-source-guard-v10.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "0636c8c80653df4c62b40c02d27411a4b48c0371318279b35234141113e61e2d"
    )
    assert json.loads(raw)["policies"]["admission"] == "pi-admission-v10"
