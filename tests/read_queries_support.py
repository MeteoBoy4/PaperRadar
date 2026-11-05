"""查询组合材料;配置均经真实历史快照编译。"""

import json
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from paper_radar.read_queries import ReadQueries

from paper_radar.config import compile_config
from paper_radar.read_tasks import ReadAnalysis, ReadTasks
from tests.a8_call_support import Archive
from tests.config_projection_support import new_yaml_version
from tests.read_tasks_support import valid_candidate


def successful(
    tasks: ReadTasks,
    data: Archive,
    fingerprint: str,
    request: str,
    *,
    snapshot_id: str | None = None,
    language: Literal["zh", "en"] = "zh",
) -> ReadAnalysis:
    task = tasks.register(
        data.paper_id,
        snapshot_id=snapshot_id or data.snapshot_id,
        extraction_fingerprint=fingerprint,
        request_id=request,
        output_language=language,
    )
    raw = valid_candidate()
    if language == "en":
        output = json.loads(raw)
        for key in (
            "one_sentence_conclusion",
            "research_question",
            "methods_summary",
            "data_summary",
            "why_it_matters",
            "next_action",
        ):
            output[key] = "The study compares independent observations."
        for key in ("research_value_reason", "reuse_feasibility_reason"):
            output[key]["statement"] = "The method provides a comparison."
        output["output_language"] = "en"
        raw = json.dumps(output).encode()
    result = tasks.submit_test(tasks.claim(task.task_id), raw)
    assert isinstance(result, ReadAnalysis)
    return result


def changed_profile(data: Archive) -> str:
    new_yaml_version(
        data.settings, "profile", lambda c: c.update(background="PRIVATE NEW PROFILE")
    )
    return compile_config(data.settings, data.database).snapshot_id


def query_projection(
    query: "ReadQueries", paper_id: str, snapshot_id: str
) -> dict[str, object]:
    from dataclasses import asdict

    current = query.current(paper_id, snapshot_id=snapshot_id)
    return {
        "state": current.state,
        "identity": asdict(current.identity) if current.identity else None,
        "analyses": [
            {
                "id": a.analysis_id,
                "language": a.output_language,
                "body": a.body_status,
                "config": a.config_status,
                "components": list(a.changed_components),
                "discards": [asdict(c) for c in a.discard_counts],
                "warning": a.restricted_content_warning,
                "output": a.output.model_dump(mode="json"),
            }
            for a in current.analyses
        ],
        "old": [
            {**asdict(a), "changed_components": list(a.changed_components)}
            for a in query.old_configurations((paper_id,), snapshot_id=snapshot_id)
        ],
        "unknown_old": list(query.old_configurations((paper_id,))),
        "history": [a.analysis_id for a in query.history(paper_id)],
    }
