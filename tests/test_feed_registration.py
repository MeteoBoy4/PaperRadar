"""数据库是 Feed 唯一身份登记权威。"""

from pathlib import Path

import pytest

from paper_radar.papers import PaperError, PaperFacts
from paper_radar.storage.database import upgrade_database


def test_feed_registration_preserves_path_query_and_is_idempotent(
    tmp_path: Path,
) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    first = service.register_feed("HTTPS://Feeds.Example:443/Path/%2F/?Q=A%2f&x=1")
    assert first.url == "https://feeds.example/Path/%2F/?Q=A%2f&x=1"
    assert service.register_feed(first.url) == first
    assert service.register_feed(first.url[:-1]).feed_id != first.feed_id
    assert (
        service.register_feed("http://Feeds.Example:80/a?").url
        == "http://feeds.example/a?"
    )
    assert (
        service.register_feed("https://feeds.example/a").feed_id
        != service.register_feed("https://feeds.example/a/").feed_id
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://u:p@feeds.example/f",
        "https://feeds.example/f#",
        "ftp://feeds.example/f",
        "https:///missing",
        "https://feeds.example:invalid/f",
        " https://feeds.example/f",
        "https://f\n.example/f",
    ],
)
def test_invalid_feed_registration_has_controlled_reason(
    tmp_path: Path, url: str
) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    with pytest.raises(PaperError, match="invalid_feed_url") as failure:
        PaperFacts(database).register_feed(url)
    assert failure.value.reason == "invalid_feed_url"


def test_feed_hostname_only_ascii_letters_are_lowercased(tmp_path: Path) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database)
    assert (
        service.register_feed("HTTPS://ÄBC.Example:443/Feed?A=1").url
        == "https://Äbc.example/Feed?A=1"
    )
    assert (
        service.register_feed("https://Äbc.example/Feed?A=1").feed_id
        != service.register_feed("https://äbc.example/Feed?A=1").feed_id
    )
