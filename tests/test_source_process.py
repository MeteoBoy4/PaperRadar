"""公共服务的真实竞争、三点中断与一致读。"""

import json
import os
import subprocess
import sys
from contextlib import AbstractContextManager
from pathlib import Path

import pytest

from paper_radar.papers import PaperFacts
from tests.a3_process_support import paused_subprocess
from tests.feed_support import facts
from tests.test_manual_corrections import correction
from tests.test_paper_service import observation

WRITE = """from pathlib import Path
import sys
from paper_radar.papers import PaperFacts
from tests.test_manual_corrections import correction
from tests.test_paper_service import observation
service = PaperFacts(Path(sys.argv[1]), Path(sys.argv[2]))
mode, paper_id, version_id, request_id = sys.argv[3:]
if mode == 'manual':
    result = service.correct(correction(version_id, request_id=request_id))
elif mode == 'registry':
    result = service.submit(observation(
        source_kind='registry', provider='crossref', query_key='10.1234/abc',
        target_paper_id=paper_id, target_version_id=version_id,
        payload=request_id.encode(),
        fields={'title': {'value': 'Registry', 'locator': 'message/title'}},
    ))
elif mode == 'publisher':
    result = service.submit(observation(
        payload=request_id.encode(),
        fields={'title': {'value': 'Publisher', 'locator': 'title'}},
    ))
else:
    result = service.revision(version_id, 1)
print(result.model_dump_json())
"""


def paused(
    service: PaperFacts,
    mode: str,
    paper_id: str,
    version_id: str,
    request_id: str = "request-1",
    phase: str = "begin",
) -> AbstractContextManager[tuple[subprocess.Popen[str], int]]:
    return paused_subprocess(
        [
            sys.executable,
            "-c",
            WRITE,
            str(service.database),
            str(service.data_root),
            mode,
            paper_id,
            version_id,
            request_id,
        ],
        Path(__file__).parent / "source_process",
        {"SOURCE_PAUSE": phase},
        "来源进程未到达屏障",
        "来源进程提前退出",
    )


@pytest.mark.parametrize(
    "case", ["duplicate", "two_manual", "manual_publisher", "manual_registry"]
)
def test_concurrent_sources_append_unique_complete_revisions(
    tmp_path: Path, case: str
) -> None:
    service = facts(tmp_path)
    first = service.submit(observation())
    assert first.paper_id and first.version_id
    other_mode = {
        "duplicate": "manual",
        "two_manual": "manual",
        "manual_publisher": "publisher",
        "manual_registry": "registry",
    }[case]
    with (
        paused(service, "manual", first.paper_id, first.version_id) as (
            one,
            release_one,
        ),
        paused(
            service,
            other_mode,
            first.paper_id,
            first.version_id,
            "request-1" if case == "duplicate" else "request-2",
        ) as (two, release_two),
    ):
        os.write(release_one, b"G")
        os.write(release_two, b"G")
        outputs = [process.communicate(timeout=20) for process in (one, two)]
        assert one.returncode == two.returncode == 0, outputs
    results = [json.loads(pair[0]) for pair in outputs]
    assert all(result["status"] == "retained" for result in results)
    if case == "duplicate":
        assert results[0] == results[1]
    trace = service.trace(first.paper_id, verify_source_bytes=True)
    assert trace.current.fields["title"].value == "人工题名"
    assert len(trace.corrections) == (2 if case == "two_manual" else 1)
    assert [revision.revision_no for revision in trace.revisions] == list(
        range(1, len(trace.revisions) + 1)
    )
    event_nos = [
        event.event_no for event in trace.acquisitions if event.event_no is not None
    ]
    assert sorted(event_nos) == list(range(1, len(trace.acquisitions) + 1))
    service.validate_all()


@pytest.mark.parametrize("mode", ["manual", "registry"])
@pytest.mark.parametrize("phase", ["published", "middle", "committed"])
def test_kill_then_retry_keeps_exact_result_without_half_revision(
    tmp_path: Path, mode: str, phase: str
) -> None:
    service = facts(tmp_path)
    first = service.submit(observation())
    assert first.paper_id and first.version_id
    with paused(service, mode, first.paper_id, first.version_id, phase=phase) as (
        process,
        _,
    ):
        process.kill()
        process.wait(timeout=15)
    service.validate_all()
    request = (
        correction(first.version_id)
        if mode == "manual"
        else observation(
            source_kind="registry",
            provider="crossref",
            query_key="10.1234/abc",
            target_paper_id=first.paper_id,
            target_version_id=first.version_id,
            payload=b"request-1",
            fields={"title": {"value": "Registry", "locator": "message/title"}},
        )
    )
    result = service.correct(request) if mode == "manual" else service.submit(request)
    assert result.status == "retained"
    assert (
        service.correct(request) if mode == "manual" else service.submit(request)
    ) == result
    trace = service.trace(first.paper_id, verify_source_bytes=True)
    assert len(trace.acquisitions) == 2
    assert len(trace.corrections) == (1 if mode == "manual" else 0)


def test_history_read_cannot_mix_a_manual_commit_between_selects(
    tmp_path: Path,
) -> None:
    service = facts(tmp_path)
    first = service.submit(observation())
    assert first.paper_id and first.version_id
    with paused(service, "history", first.paper_id, first.version_id, phase="read") as (
        reader,
        release,
    ):
        assert service.correct(correction(first.version_id)).status == "retained"
        os.write(release, b"G")
        stdout, stderr = reader.communicate(timeout=20)
        assert reader.returncode == 0, stderr
    result = json.loads(stdout)
    assert result["revision_no"] == 1
    assert result["fields"]["title"]["value"] == "Original\nTitle"
    assert service.show(first.paper_id).fields["title"].value == "人工题名"
