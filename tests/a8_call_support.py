"""A8 独立档案库与领取前描述接线;只使用既有公开服务。"""

from dataclasses import dataclass
from pathlib import Path

from paper_radar.config import compile_config, load_config_snapshot
from paper_radar.llm import CallDescription
from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import ScreeningTasks, TaskError, TaskReason
from tests.config_adapter_support import adapter_inputs
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation


@dataclass(frozen=True)
class Archive:
    settings: Path
    database: Path
    data_root: Path
    snapshot_id: str
    paper_id: str
    version_id: str


def archive(root: Path, *, pi_version: str = "1.4.0") -> Archive:
    settings, adapter, database = adapter_inputs(root)
    adapter.write_text(adapter.read_text().replace("1.1.0", pi_version))
    (settings.parent / "topics/topics-v1.yaml").write_text(
        "version: topics-v1\ntopics:\n"
        "  - {id: zeta, name: 主题二, description: Z semantic topic, enabled: true}\n"
        "  - {id: hidden, name: 隐藏, "
        "description: HIDDEN_TOPIC_SECRET, enabled: false}\n"
        "  - {id: alpha, name: 主题一, description: A semantic topic, enabled: true}\n"
    )
    snapshot = compile_config(settings, database)
    data_root = root / "data"
    saved = PaperFacts(database, data_root).submit(
        observation(fields=screening_fields())
    )
    assert saved.paper_id and saved.version_id
    return Archive(
        settings,
        database,
        data_root,
        snapshot.snapshot_id,
        saved.paper_id,
        saved.version_id,
    )


def request_for(data: Archive, **changes: object) -> dict[str, object]:
    return {
        "paper_id": data.paper_id,
        "snapshot_id": data.snapshot_id,
        "stage": "boundary",
        "source": "scheduled",
        "scheduled_day": "2026-01-01",
        **changes,
    }


def prepare_call(tasks: ScreeningTasks, receipt_id: str) -> CallDescription:
    from paper_radar.llm import CallDescriptionError, DescriptionReason, build_call

    receipt = tasks.get_receipt(receipt_id)
    frozen = tasks.load_input(receipt_id)
    audit = load_config_snapshot(tasks.database, receipt.snapshot_id)
    try:
        return build_call(frozen.stage_input, frozen.snapshot, audit)
    except CallDescriptionError as error:
        reasons = {
            DescriptionReason.INVALID_CONTEXT: TaskReason.INVALID_CONTEXT,
            DescriptionReason.PROJECTION_MISMATCH: TaskReason.CONTEXT_CONFLICT,
            DescriptionReason.CORRUPT_REFERENCE: TaskReason.CORRUPT_REFERENCE,
        }
        raise TaskError(reasons[error.reason]) from None
