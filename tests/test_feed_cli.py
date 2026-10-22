"""既有只读查询展示 Feed 历史与事实范围,默认不公开正文。"""

import json
from pathlib import Path

from tests.config_test_support import run_cli
from tests.feed_support import facts, item


def test_trace_shows_feed_history_and_text_is_concise_with_facts_only_scope(
    tmp_path: Path,
) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f?edition=1")
    result = service.submit(
        item(
            feed.feed_id,
            payload=b"SECRET-RAW-ITEM",
            fields={
                "title": {"value": "Original title", "locator": "title"},
                "abstract": {
                    "value": {
                        "text": "SECRET-ABSTRACT",
                        "is_truncated": None,
                        "rule": "fixture",
                    },
                    "locator": "abstract",
                },
            },
        )
    )
    assert result.paper_id
    for command in ("show", "trace"):
        for as_json in (False, True):
            query = run_cli(
                tmp_path,
                "paper",
                command,
                result.paper_id,
                "--database",
                str(service.database),
                *(["--json"] if as_json else []),
            )
            assert query.returncode == 0, query.stderr
            assert "Original title" in query.stdout
            assert "SECRET" not in query.stdout
            assert "仅覆盖论文事实" in query.stdout
            assert "尚未计算完整任务资格" in query.stdout
            if as_json:
                payload = json.loads(query.stdout)
                if command == "trace":
                    found = payload["discoveries"][0]
                    assert found["feed_id"] == feed.feed_id
                    assert found["entry_id"] == "entry-1"
                    assert found["first_seen"] == found["last_seen"]
                    assert payload["observations"][0]["parser_version"] == 1
                else:
                    assert "discoveries" not in payload
            else:
                assert "candidate_id" not in query.stdout
                assert len(query.stdout.splitlines()) < 16
                if command == "trace":
                    assert feed.feed_id in query.stdout and "entry-1" in query.stdout
                    assert "parser_version=1" in query.stdout
