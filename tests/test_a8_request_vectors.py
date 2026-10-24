"""独立 render_format=1 字节向量;不从被测渲染器生成期望。"""

import json
from pathlib import Path

import pytest

from paper_radar.config import StageName, load_config_snapshot
from paper_radar.llm import build_call, render_request
from paper_radar.stage_inputs import ScreeningFacts, build_stage_input
from tests.a8_call_support import archive

VECTORS = json.loads(
    (Path(__file__).parent / "fixtures/pi_rpc/1.4.0/request-vectors.json").read_text()
)["vectors"]


@pytest.mark.parametrize("vector", VECTORS, ids=[item["id"] for item in VECTORS])
def test_exact_request_bytes_preserve_only_bound_semantics(
    tmp_path: Path, vector: dict[str, object]
) -> None:
    data = archive(tmp_path)
    snapshot = load_config_snapshot(data.database, data.snapshot_id)
    paper = vector["paper"]
    assert isinstance(paper, dict)
    stage = vector["stage"]
    assert isinstance(stage, str)
    stage_input = build_stage_input(snapshot, StageName(stage), ScreeningFacts(**paper))
    description = build_call(stage_input, snapshot, snapshot)
    correction = vector["correction"]
    assert correction is None or isinstance(correction, str)
    actual = render_request(description, correction)
    expected = vector["request_utf8"]
    assert isinstance(expected, str)
    assert actual == expected.encode("utf-8")
    for forbidden in (
        "pi-v1",
        "transport-v1",
        "profile-v1",
        "models-v1",
        "manifest",
        "HIDDEN_TOPIC_SECRET",
        "original_title_is_zh",
        "fingerprint",
        "snapshot_id",
        "journal",
        "weight",
    ):
        assert forbidden.encode() not in actual
    assert "Frozen effective Pi system prompt" not in actual.decode()


@pytest.mark.parametrize("seed", ["1", "917"])
def test_historical_requests_match_vector_across_processes(
    tmp_path: Path, seed: str
) -> None:
    import hashlib
    import os
    import shutil
    import subprocess
    import sys

    from paper_radar.screening_tasks import ScreeningTasks
    from tests.a8_call_support import request_for

    data = archive(tmp_path)
    receipt = ScreeningTasks(data.database).register(request_for(data))
    shutil.rmtree(data.settings.parent)
    shutil.rmtree(tmp_path / "prompts")
    root = Path(__file__).parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.a8_call_worker",
            str(data.database),
            receipt.receipt_id,
        ],
        cwd=tmp_path,
        env={
            "PYTHONPATH": os.pathsep.join(
                (str(root / "tests/deny_network"), str(root))
            ),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": seed,
        },
        capture_output=True,
        check=False,
        timeout=10,
    )
    expected = VECTORS[0]["request_utf8"].encode("utf-8")
    assert result.returncode == 0
    assert result.stdout == (hashlib.sha256(expected).hexdigest() + "\n").encode()
    assert result.stderr == b""
