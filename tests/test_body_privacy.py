"""Body D1:默认静默和注入安全日志,不保存业务内容。"""

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from paper_radar.body import BodyService
from tests.body_support import prepared


class Capture:
    def __init__(self) -> None:
        self.events: list[Mapping[str, object]] = []

    def emit(self, event: Mapping[str, object]) -> None:
        self.events.append(event)


def test_default_null_sink_and_injected_log_keep_private_material_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    saved, service, parser = prepared(tmp_path)
    result = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    assert capsys.readouterr() == ("", "") and not caplog.records
    sink = Capture()
    logged = BodyService(saved.database, saved.data_root, sink=sink)
    assert (
        logged.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
        == result
    )
    encoded = json.dumps(sink.events, ensure_ascii=False)
    assert sink.events and {e["component"] for e in sink.events} == {"body"}
    assert any(e["event"] == "succeeded" for e in sink.events)
    for private in (
        "Exact source",
        "Results",
        str(saved.data_root),
        "%PDF-",
        "researcher",
    ):
        assert private not in encoded
    assert all(
        set(e)
        <= {
            "format_version",
            "event",
            "component",
            "run_id",
            "paper_id",
            "fingerprint",
            "elapsed_ms",
            "timestamp",
            "category",
        }
        for e in sink.events
    )
