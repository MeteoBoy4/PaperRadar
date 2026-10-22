"""原始 item 的边界与完整解释声明。"""

from pathlib import Path

import pytest

from tests.feed_support import facts, item


@pytest.mark.parametrize(
    "change",
    [
        {"entry_id": None},
        {"entry_id": ""},
        {"entry_id": " \t"},
        {"payload_scope": None},
        {"payload": b""},
        {"payload": b"x" * (8 * 1024 * 1024 + 1)},
        {"payload": bytearray(b"item")},
        {"parser_version": 0},
        {"parser_version": True},
        {"interpretation": "partial"},
        {"interpretation": "economical"},
        {"payload": b"<?xml version='1.0'?><rss><channel><item/></channel></rss>"},
        {"payload": b"<feed xmlns='http://www.w3.org/2005/Atom'><entry/></feed>"},
        {"payload": b"<item><guid>one</guid></item><item><guid>two</guid></item>"},
    ],
)
def test_invalid_item_is_controlled_and_creates_no_business_facts(
    tmp_path: Path, change: dict[str, object]
) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f")
    result = service.submit(item(feed.feed_id, **change))
    expected = "missing_entry_id" if "entry_id" in change else "invalid_observation"
    assert (result.status, result.reason) == ("rejected", expected)
    service.validate_all()


@pytest.mark.parametrize("size", [1, 8 * 1024 * 1024])
def test_single_item_inclusive_byte_boundaries_keep_exact_payload(
    tmp_path: Path, size: int
) -> None:
    from paper_radar.storage.artifacts import ArtifactStore

    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f")
    result = service.submit(item(feed.feed_id, payload=b"x" * size))
    assert result.status == "retained" and result.paper_id and service.data_root
    discovery = service.trace(result.paper_id, verify_source_bytes=True).discoveries[0]
    assert (
        ArtifactStore(service.database, service.data_root).read_artifact(
            discovery.artifact_id
        )["payload"]
        == b"x" * size
    )


def test_identical_item_bytes_cannot_be_claimed_as_another_entry(
    tmp_path: Path,
) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f")
    result = service.submit(item(feed.feed_id))
    assert result.paper_id
    before = service.trace(result.paper_id)
    bad = service.submit(item(feed.feed_id, entry_id="another"))
    assert (bad.status, bad.reason) == ("rejected", "invalid_observation")
    assert service.trace(result.paper_id) == before


def test_unknown_feed_uuid_is_rejected_without_creating_an_identity(
    tmp_path: Path,
) -> None:
    service = facts(tmp_path)
    result = service.submit(item("00000000-0000-0000-0000-000000000000"))
    assert (result.status, result.reason) == ("rejected", "invalid_observation")
    service.validate_all()
