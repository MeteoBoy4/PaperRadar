"""独立进程只消费恢复后的明确历史引用。原位置访问被审计哨兵拒绝。"""

import json
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from paper_radar.config import load_config_snapshot
from paper_radar.stage_inputs import (
    ReplayReason,
    StageInputError,
    compare_stage_inputs,
    replay_stage_input,
)
from paper_radar.storage.artifacts import ArtifactStore
from tests.stage_input_recovery_support import rebuild_inputs


def main() -> None:
    request = json.loads(Path(sys.argv[1]).read_bytes())
    expected = json.loads(Path(sys.argv[2]).read_bytes())
    denied = request["denied_roots"]

    def deny_original_roots(event: str, arguments: tuple[object, ...]) -> None:
        candidate = arguments[0] if arguments else None
        if event in {
            "open",
            "sqlite3.connect",
            "os.listdir",
            "os.scandir",
        } and isinstance(candidate, str):
            assert not any(root in candidate for root in denied), (
                "恢复消费者不应读取原位置"
            )

    sys.addaudithook(deny_original_roots)
    root = Path(request["root"])
    database = root / "database.sqlite3"
    before = database.read_bytes()
    snapshot = load_config_snapshot(database, request["snapshot_id"])
    other = load_config_snapshot(database, request["other_snapshot_id"])
    assert {topic.id for topic in snapshot.enabled_topics} == {"active", "inactive"}
    # 纯 fixture 只改变集合枚举方式。显式反转保证两个变体实际不同。
    topics = snapshot.enabled_topics
    snapshot = replace(
        snapshot,
        enabled_topics=tuple(reversed(topics)) if request.get("reverse") else topics,
    )
    store = ArtifactStore(database, root)
    # 进程输入没有旧成员哈希。每个角色都从恢复后的真实 get_artifact 重新取得。
    members = {
        case: {member.role: member.sha256 for member in store.get_artifact(id_).members}
        for case, id_ in request["artifact_ids"].items()
    }
    inputs = rebuild_inputs(
        snapshot, members, request, reverse=request.get("reverse", False)
    )
    # 另经 hashseed 控制的 frozenset 迭代重建。不依赖特定 Python 的 set 顺序。
    seeded_inputs = rebuild_inputs(
        replace(snapshot, enabled_topics=tuple(frozenset(snapshot.enabled_topics))),
        members,
        request,
        reverse=request.get("reverse", False),
    )
    for case, value in inputs.items():
        payload = expected[case]["payload"].encode("utf-8")
        fingerprint = expected[case]["fingerprint"]
        assert value.payload_bytes == payload
        assert value.fingerprint == fingerprint
        assert seeded_inputs[case].payload_bytes == payload
        assert seeded_inputs[case].fingerprint == fingerprint
        replayed = replay_stage_input(payload, fingerprint, snapshot=snapshot)
        assert compare_stage_inputs(value, replayed).status == "same"
        try:
            replay_stage_input(payload, fingerprint, snapshot=other)
        except StageInputError as error:
            assert error.reason is ReplayReason.PROJECTION_MISMATCH
            assert error.__context__ is None
        else:
            raise AssertionError("错误历史配置应拒绝")
        if case == "value":
            assert value.value_prediction_context(
                snapshot, original_title_is_zh=False
            ).enabled_topic_ids == frozenset({"active", "inactive"})
        elif case in {"structured", "body"}:
            assert dict(value.reuse_assessment_context().excerpt_kinds) == {
                "availability-1": "availability",
                "methods-1": "methods",
            }
    # 同一进程重建依然保留语义次序与精确文本。不隐式排序或归一化。
    changed = deepcopy(request)
    changed["excerpts"].reverse()
    reordered = rebuild_inputs(snapshot, members, changed)
    for case in ("structured", "body"):
        assert compare_stage_inputs(
            inputs[case], reordered[case]
        ).changed_components == ("excerpts", "excerpt_sources")
    nfc, nfd = deepcopy(request), deepcopy(request)
    nfc["screening"]["title"] = "café\r\n"
    nfd["screening"]["title"] = "cafe\u0301\n"
    nfc["excerpts"][0]["text"] = "café "
    nfd["excerpts"][0]["text"] = "cafe\u0301"
    first = rebuild_inputs(snapshot, members, nfc)
    second = rebuild_inputs(snapshot, members, nfd)
    for case in ("boundary", "value", "structured", "body"):
        assert first[case].fingerprint != second[case].fingerprint
    assert database.read_bytes() == before
    print(
        json.dumps(
            {
                "status": "passed",
                "topic_order": [topic.id for topic in snapshot.enabled_topics],
                "construction_order": list(inputs),
            }
        )
    )


if __name__ == "__main__":
    main()
