"""校准可见性公共 seam:合成消费者,不代表产品展示面接线。"""

import pytest

from paper_radar.calibration.visibility import (
    HiddenCondition,
    VisibilityCapability,
    VisibilityPermission,
    evaluate_visibility,
)


def test_hidden_paper_keeps_facts_and_tasks_but_blocks_agent_and_actions() -> None:
    visibility = evaluate_visibility(frozenset({HiddenCondition.WAITING_CALIBRATION}))

    assert {
        capability.value: visibility.permission(capability).value
        for capability in VisibilityCapability
    } == {
        "paper_facts": "allowed",
        "task_details": "allowed",
        "agent_content": "denied",
        "set_decision": "denied",
        "reading_request": "denied",
        "calibration_review": "dedicated_path",
    }
    assert visibility.hidden_conditions == frozenset(
        {HiddenCondition.WAITING_CALIBRATION}
    )
    assert (
        visibility.permission(VisibilityCapability.CALIBRATION_REVIEW)
        is VisibilityPermission.DEDICATED_PATH
    )


def test_empty_hidden_set_restores_ordinary_permissions() -> None:
    visibility = evaluate_visibility(frozenset())

    assert {
        capability.value: visibility.permission(capability).value
        for capability in VisibilityCapability
    } == {
        "paper_facts": "allowed",
        "task_details": "allowed",
        "agent_content": "allowed",
        "set_decision": "allowed",
        "reading_request": "allowed",
        "calibration_review": "dedicated_path",
    }
    assert visibility.hidden_conditions == frozenset()


@pytest.mark.parametrize(
    ("conditions", "expected"),
    [
        (frozenset(), VisibilityPermission.ALLOWED),
        (
            frozenset({HiddenCondition.WAITING_CALIBRATION}),
            VisibilityPermission.DENIED,
        ),
        (frozenset({HiddenCondition.UNREVEALED}), VisibilityPermission.DENIED),
        (
            frozenset(
                {HiddenCondition.WAITING_CALIBRATION, HiddenCondition.UNREVEALED}
            ),
            VisibilityPermission.DENIED,
        ),
    ],
)
def test_each_hidden_condition_independently_restricts_ordinary_capabilities(
    conditions: frozenset[HiddenCondition], expected: VisibilityPermission
) -> None:
    visibility = evaluate_visibility(conditions)

    assert visibility.hidden_conditions == conditions
    assert visibility.permission(VisibilityCapability.AGENT_CONTENT) is expected
    assert visibility.permission(VisibilityCapability.SET_DECISION) is expected
    assert visibility.permission(VisibilityCapability.READING_REQUEST) is expected
    assert (
        visibility.permission(VisibilityCapability.PAPER_FACTS)
        is VisibilityPermission.ALLOWED
    )
    assert (
        visibility.permission(VisibilityCapability.TASK_DETAILS)
        is VisibilityPermission.ALLOWED
    )


@pytest.mark.parametrize(
    "remaining",
    [HiddenCondition.WAITING_CALIBRATION, HiddenCondition.UNREVEALED],
)
def test_partial_release_including_reveal_keeps_other_conditions_and_history(
    remaining: HiddenCondition,
) -> None:
    original = evaluate_visibility(
        frozenset({HiddenCondition.WAITING_CALIBRATION, HiddenCondition.UNREVEALED})
    )
    partial = evaluate_visibility(frozenset({remaining}))
    released = evaluate_visibility(frozenset())

    assert (
        original.permission(VisibilityCapability.AGENT_CONTENT)
        is VisibilityPermission.DENIED
    )
    assert partial.hidden_conditions == frozenset({remaining})
    assert (
        partial.permission(VisibilityCapability.AGENT_CONTENT)
        is VisibilityPermission.DENIED
    )
    assert (
        released.permission(VisibilityCapability.AGENT_CONTENT)
        is VisibilityPermission.ALLOWED
    )
    assert original.hidden_conditions == frozenset(
        {HiddenCondition.WAITING_CALIBRATION, HiddenCondition.UNREVEALED}
    )


@pytest.mark.parametrize("hidden", [False, True])
def test_synthetic_material_consumer_projects_only_permitted_content(
    hidden: bool,
) -> None:
    # 合成消费示例;真实 DTO 的字段归类和裁剪仍由 B/C/D/H 组合测试负责。
    materials = {
        "title": (VisibilityCapability.PAPER_FACTS, "合成论文"),
        "task_exists": (VisibilityCapability.TASK_DETAILS, "yes"),
        "stage": (VisibilityCapability.TASK_DETAILS, "value"),
        "attempt": (VisibilityCapability.TASK_DETAILS, "2"),
        "failure_kind": (VisibilityCapability.TASK_DETAILS, "invalid_output"),
        "failure_queue": (VisibilityCapability.TASK_DETAILS, "model_failures"),
        "screening_suggestion": (VisibilityCapability.AGENT_CONTENT, "accepted"),
        "value_prediction": (VisibilityCapability.AGENT_CONTENT, "high_value"),
        "score": (VisibilityCapability.AGENT_CONTENT, "4"),
        "reuse_prediction": (VisibilityCapability.AGENT_CONTENT, "high_reuse"),
        "artifact": (VisibilityCapability.AGENT_CONTENT, "synthetic-full-payload"),
    }
    visibility = evaluate_visibility(
        frozenset({HiddenCondition.UNREVEALED}) if hidden else frozenset()
    )
    projected = {
        field: value
        for field, (capability, value) in materials.items()
        if visibility.permission(capability) is VisibilityPermission.ALLOWED
    }

    expected = {
        "title": "合成论文",
        "task_exists": "yes",
        "stage": "value",
        "attempt": "2",
        "failure_kind": "invalid_output",
        "failure_queue": "model_failures",
    }
    if not hidden:
        expected.update(
            screening_suggestion="accepted",
            value_prediction="high_value",
            score="4",
            reuse_prediction="high_reuse",
            artifact="synthetic-full-payload",
        )
    assert projected == expected
    assert materials["artifact"][1] == "synthetic-full-payload"


def test_synthetic_actions_reject_before_write_with_controlled_receipts() -> None:
    visibility = evaluate_visibility(frozenset({HiddenCondition.UNREVEALED}))
    writes: list[str] = []
    receipts: dict[str, object] = {}
    for capability in (
        VisibilityCapability.SET_DECISION,
        VisibilityCapability.READING_REQUEST,
        VisibilityCapability.CALIBRATION_REVIEW,
    ):
        permission = visibility.permission(capability)
        if permission is VisibilityPermission.ALLOWED:
            writes.append(capability.value)
        receipts[capability.value] = {
            "permission": permission.value,
            "hidden_conditions": sorted(visibility.hidden_conditions),
        }

    assert writes == []
    assert receipts == {
        "set_decision": {"permission": "denied", "hidden_conditions": ["unrevealed"]},
        "reading_request": {
            "permission": "denied",
            "hidden_conditions": ["unrevealed"],
        },
        "calibration_review": {
            "permission": "dedicated_path",
            "hidden_conditions": ["unrevealed"],
        },
    }
