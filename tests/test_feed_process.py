"""真实两进程竞争及业务发布边界强杀。"""

import json
import os
import subprocess
import sys
from contextlib import AbstractContextManager
from pathlib import Path

import pytest

from paper_radar.storage.artifacts import ArtifactStore
from tests.a3_process_support import paused_subprocess
from tests.feed_support import facts, item

WRITE = """from pathlib import Path
import sys
from paper_radar.papers import PaperFacts
from tests.feed_support import item
service = PaperFacts(Path(sys.argv[1]), Path(sys.argv[2]))
request = item(sys.argv[3], entry_id=sys.argv[4], doi=sys.argv[5] or None,
               payload=sys.argv[6].encode())
print(service.submit(request).model_dump_json())
"""


def paused(
    database: Path,
    feed_id: str,
    *,
    entry_id: str = "entry-1",
    doi: str = "",
    payload: str = "item",
    phase: str = "begin",
) -> AbstractContextManager[tuple[subprocess.Popen[str], int]]:
    return paused_subprocess(
        [
            sys.executable,
            "-c",
            WRITE,
            str(database),
            str(database.parent / "data"),
            feed_id,
            entry_id,
            doi,
            payload,
        ],
        Path(__file__).parent / "feed_process",
        {"FEED_PAUSE": phase},
        "Feed 进程未到达屏障",
        "Feed 进程提前退出",
    )


@pytest.mark.parametrize("case", ["duplicate", "cross_feed", "supplement"])
def test_concurrent_discovery_and_doi_supplement_have_one_complete_unique_result(
    tmp_path: Path, case: str
) -> None:
    service = facts(tmp_path)
    one = service.register_feed("https://feeds.example/one")
    two = service.register_feed("https://feeds.example/two")
    if case == "supplement":
        assert (
            service.submit(item(one.feed_id, payload=b"initial one")).status
            == "retained"
        )
        assert (
            service.submit(item(two.feed_id, payload=b"initial two")).status
            == "retained"
        )
    with (
        paused(service.database, one.feed_id, doi="10.1/shared") as (
            first,
            release_first,
        ),
        paused(
            service.database,
            one.feed_id if case == "duplicate" else two.feed_id,
            doi="10.1/shared",
            payload="item" if case == "duplicate" else "different item",
        ) as (second, release_second),
    ):
        os.write(release_first, b"G")
        os.write(release_second, b"G")
        output = [process.communicate(timeout=20) for process in (first, second)]
        assert first.returncode == second.returncode == 0, output
    results = [json.loads(pair[0]) for pair in output]
    if case == "duplicate":
        assert results[0] == results[1]
    elif case == "cross_feed":
        assert results[0]["paper_id"] == results[1]["paper_id"]
    else:
        assert sorted(result["status"] for result in results) == [
            "rejected",
            "retained",
        ]
        assert (
            next(result for result in results if result["status"] == "rejected")[
                "conflict"
            ]
            == "doi_owner_conflict"
        )
    kept = next(result for result in results if result["status"] == "retained")
    trace = service.trace(kept["paper_id"], verify_source_bytes=True)
    assert len(trace.discoveries) == (1 if case == "duplicate" else 2)
    service.validate_all()


@pytest.mark.parametrize("phase", ["published", "middle", "committed"])
def test_kill_at_business_boundaries_then_retry_has_complete_associations(
    tmp_path: Path, phase: str
) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f")
    with paused(service.database, feed.feed_id, phase=phase) as (process, _):
        assert service.data_root
        assert (
            len(ArtifactStore(service.database, service.data_root).list_artifacts())
            == 1
        )
        process.kill()
        process.wait(timeout=15)
    service.validate_all()
    result = service.submit(item(feed.feed_id, payload=b"item"))
    assert result.status == "retained" and result.paper_id
    trace = service.trace(result.paper_id, verify_source_bytes=True)
    assert (
        len(trace.discoveries)
        == len(trace.observations)
        == len(trace.acquisitions)
        == len(trace.revisions)
        == 1
    )
