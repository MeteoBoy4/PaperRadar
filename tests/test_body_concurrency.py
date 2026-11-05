"""Body D1:真实根 flock 的等待、中断、重核和持有者失联。"""

import fcntl
import os
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from paper_radar.body import BodyError
from paper_radar.body.extraction import LOCK_FILENAME
from paper_radar.body.models import ParserResult
from paper_radar.config import StageName, load_config_snapshot
from paper_radar.config.extraction import ExtractionSemantics
from paper_radar.stage_inputs import ExtractionFacts, build_stage_input
from tests.a7_registration_support import Archive
from tests.body_support import PDF, Parser, prepared


def test_waiting_request_spends_no_attempt_and_reuses_committed_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    saved, service, second = prepared(tmp_path)
    entered, release, preflight = Event(), Event(), Event()

    class Slow(Parser):
        def convert(self, pdf: bytes, semantics: ExtractionSemantics) -> ParserResult:
            entered.set()
            assert release.wait(15)
            return super().convert(pdf, semantics)

    class Waiter(Parser):
        def preflight(self, semantics: ExtractionSemantics) -> None:
            super().preflight(semantics)
            preflight.set()

    first, second = Slow(), Waiter()
    with ThreadPoolExecutor(2) as pool:
        active = pool.submit(
            service.extract, saved.paper_id, snapshot_id=saved.snapshot_id, parser=first
        )
        assert entered.wait(10)
        waiting = pool.submit(
            service.extract,
            saved.paper_id,
            snapshot_id=saved.snapshot_id,
            parser=second,
        )
        assert preflight.wait(10)
        assert not waiting.done()
        release.set()
        result = active.result(timeout=15)
        assert waiting.result(timeout=15) == result
    assert first.calls == 1 and second.calls == 0
    assert len(result.attempts) == 1
    assert capsys.readouterr().err.count("另一个 Docling 转换正在进行") <= 1


def test_waiter_rechecks_changed_pdf_before_claim(tmp_path: Path) -> None:
    saved, service, parser = prepared(tmp_path)
    entered = Event()

    class Waiting(Parser):
        def preflight(self, semantics: ExtractionSemantics) -> None:
            entered.set()

    lock = saved.data_root / LOCK_FILENAME
    with lock.open("w") as held, ThreadPoolExecutor(1) as pool:
        fcntl.flock(held, fcntl.LOCK_EX)
        future = pool.submit(
            service.extract,
            saved.paper_id,
            snapshot_id=saved.snapshot_id,
            parser=Waiting(),
        )
        assert entered.wait(10)
        service.attach_pdf(saved.paper_id, PDF + b"changed", request_id="changed")
        fcntl.flock(held, fcntl.LOCK_UN)
        with pytest.raises(BodyError) as error:
            future.result(timeout=15)
    assert error.value.reason == "facts_changed"
    assert parser.calls == 0


WORKER = r"""
import sys, signal
from pathlib import Path
from paper_radar.body import BodyService
from tests.body_support import Parser
class Worker(Parser):
    def preflight(self, semantics):
        print('preflight', flush=True)
    def convert(self, pdf, semantics):
        print('claimed', flush=True)
        signal.pause()
service = BodyService(Path(sys.argv[1]),Path(sys.argv[2]))
service.extract(sys.argv[3],snapshot_id=sys.argv[4],parser=Worker())
"""


def start_worker(saved: Archive, root: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            "-c",
            WORKER,
            str(saved.database),
            str(saved.data_root),
            saved.paper_id,
            saved.snapshot_id,
        ],
        cwd=root,
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).parents[1])
            + os.pathsep
            + str(Path(__file__).parents[1] / "src"),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_interrupting_waiter_leaves_no_attempt_or_failure(tmp_path: Path) -> None:
    saved, service, parser = prepared(tmp_path)
    pdf = service.current_pdf(saved.paper_id)
    assert pdf
    stage = build_stage_input(
        load_config_snapshot(saved.database, saved.snapshot_id),
        StageName.EXTRACTION,
        ExtractionFacts(pdf_sha256=pdf.pdf_sha256),
    )
    with (saved.data_root / LOCK_FILENAME).open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        process = start_worker(saved, tmp_path)
        try:
            assert process.stdout and process.stderr
            assert process.stdout.readline().strip() == "preflight"
            assert "另一个 Docling 转换正在进行" in process.stderr.readline()
            assert service.extraction(stage.fingerprint) is None
            process.send_signal(signal.SIGINT)
            process.communicate(timeout=10)
            assert process.returncode != 0
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=10)
    assert service.extraction(stage.fingerprint) is None
    assert parser.calls == 0


def test_killed_holder_is_settled_unknown_without_refunding_attempt(
    tmp_path: Path,
) -> None:
    saved, service, parser = prepared(tmp_path)
    process = start_worker(saved, tmp_path)
    try:
        assert process.stdout
        assert process.stdout.readline().strip() == "preflight"
        assert process.stdout.readline().strip() == "claimed"
        process.kill()
        process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
    result = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    assert [a.failure for a in result.attempts] == ["outcome_unknown", None]
    assert result.remaining_attempts == 0 and result.artifact_id
    service.validate_all()


def test_symlink_lock_does_not_claim(tmp_path: Path) -> None:
    saved, service, parser = prepared(tmp_path)
    target = tmp_path / "unrelated"
    target.write_text("untouched")
    (saved.data_root / LOCK_FILENAME).symlink_to(target)
    with pytest.raises(BodyError) as error:
        service.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
    assert error.value.reason == "unsafe_lock"
    assert target.read_text() == "untouched" and parser.calls == 0
