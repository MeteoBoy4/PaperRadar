"""三态关系的只读中文/JSON出口及成功退出码。"""

import json
from pathlib import Path

import pytest

from paper_radar.papers import PaperFacts
from paper_radar.storage.database import upgrade_database
from tests.config_test_support import run_cli
from tests.test_paper_service import observation
from tests.test_version_relations import relation


@pytest.mark.parametrize(
    "state,label",
    [
        ("endpoint_missing", "端点尚未出现"),
        ("requires_merge", "未生效版本关系（等待合并）"),
        ("effective", "已生效"),
    ],
)
def test_relation_trace_is_queryable_success_in_text_and_json(
    tmp_path: Path, state: str, label: str
) -> None:
    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    pre = service.submit(
        observation(
            doi="10.1/pre",
            version_kind="preprint",
            relations=relation() if state != "requires_merge" else (),
            payload=b"PRIVATE_RAW_RESPONSE",
        )
    )
    assert pre.paper_id
    if state != "endpoint_missing":
        service.submit(observation(doi="10.1/journal"))
    if state == "requires_merge":
        result = service.submit(
            observation(
                doi="10.1/pre",
                version_kind="preprint",
                relations=relation(),
                payload=b"PRIVATE_RELATION_RESPONSE",
            )
        )
        assert result.status == "retained" and result.reason == "requires_merge"
    args = ("paper", "trace", pre.paper_id, "--database", str(db))
    text = run_cli(tmp_path, *args)
    assert text.returncode == 0, text.stderr
    assert label in text.stdout and "relation[0]" in text.stdout
    assert "publisher.example" in text.stdout
    assert "PRIVATE" not in text.stdout
    encoded = run_cli(tmp_path, *args, "--json")
    assert encoded.returncode == 0, encoded.stderr
    payload = json.loads(encoded.stdout)
    assert payload["relations"][0]["state"] == state
    assert "PRIVATE" not in encoded.stdout
    if state == "endpoint_missing":
        assert payload["relations"][0]["journal_paper_id"] is None
    if state == "effective":
        assert [selection["reason"] for selection in payload["selections"]] == [
            "initial",
            "journal_upgrade",
        ]
