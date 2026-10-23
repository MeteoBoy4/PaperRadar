"""A7 value 的已知合法原始候选与真实非空主题档案。"""

import json
from pathlib import Path

from paper_radar.config import compile_config
from paper_radar.papers import PaperFacts
from tests.a7_registration_support import Archive
from tests.config_test_support import value_inputs
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation


def value_payload(**changes: object) -> bytes:
    return json.dumps(
        {
            "research_value": 4,
            "research_value_reason_zh": "该方法能改进区域降水诊断。",
            "reuse_feasibility": 3,
            "reuse_feasibility_reason_zh": "需要调整现有 ERA5 数据处理流程。",
            "reuse_feasibility_inferable": True,
            "value_types": ["method"],
            "topic_ids": [],
            "abstract_brief_zh": "研究提出一种新的极端降水诊断方法。",
            "why_it_may_matter_zh": "可用于改进当前的区域降水分析。",
            "display_title_zh": None,
            **changes,
        },
        ensure_ascii=False,
    ).encode()


def value_archive(root: Path) -> Archive:
    settings, database = value_inputs(
        root,
        "\n  - id: extreme-rainfall\n    name: 极端降水\n"
        "    description: 区域极端降水诊断\n    enabled: true\n"
        "  - id: disabled-topic\n    name: 未启用主题\n"
        "    description: 不供本次模型使用\n    enabled: false\n",
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
