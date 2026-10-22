"""只读 CLI 投影来源仲裁及人工版本边界。"""

import json
from pathlib import Path

from tests.config_test_support import run_cli
from tests.feed_support import facts
from tests.test_manual_corrections import correction
from tests.test_paper_service import observation


def test_trace_explains_history_and_manual_scope_while_abstracts_stay_explicit(
    tmp_path: Path,
) -> None:
    service = facts(tmp_path)
    first = service.submit(
        observation(
            fields={
                "abstract": {
                    "value": {
                        "text": "PRIVATE ABSTRACT",
                        "is_truncated": None,
                        "rule": "fixture",
                    },
                    "locator": "abstract",
                }
            }
        )
    )
    assert first.paper_id and first.version_id
    service.correct(correction(first.version_id))
    args = ("paper", "trace", first.paper_id, "--database", str(service.database))
    text = run_cli(tmp_path, *args)
    assert text.returncode == 0, text.stderr
    assert "获选依据" in text.stdout and "人工修正绑定版本" in text.stdout
    assert "修订 1" in text.stdout and "修订 2" in text.stdout
    assert "PRIVATE ABSTRACT" not in text.stdout
    as_json = run_cli(tmp_path, *args, "--json")
    assert as_json.returncode == 0, as_json.stderr
    payload = json.loads(as_json.stdout)
    assert payload["corrections"][0]["request_id"] == "request-1"
    assert "PRIVATE ABSTRACT" not in as_json.stdout
    expanded = run_cli(tmp_path, *args, "--show-abstract")
    assert expanded.returncode == 0 and "PRIVATE ABSTRACT" in expanded.stdout
    for forbidden in ("metadata_ready", "model_status", "calibration"):
        assert forbidden not in payload
