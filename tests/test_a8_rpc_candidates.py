"""公共调用 seam 的完整消息、冗余副本与审计边界。"""

import copy
from dataclasses import replace
from typing import Any

import pytest

from paper_radar.llm import CallDescription
from paper_radar.llm.rpc import run_call
from paper_radar.llm.rpc_types import RpcCandidate, RpcCategory, RpcFailure, RpcReason
from tests.a8_rpc_support import FakeFactory, wire
from tests.test_a8_rpc_protocol import description as description
from tests.test_a8_rpc_protocol import invoke


@pytest.mark.parametrize("location", ["turn", "aggregate"])
@pytest.mark.parametrize("field,value", [("input", True), ("timestamp", False)])
def test_redundant_final_copy_requires_json_type_identity(
    description: CallDescription, location: str, field: str, value: object
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            message = records[8]["message"]
            message["usage"].update(input=1, totalTokens=4)
            message["timestamp"] = 0
            # 独立副本,不让 fixture 的别名掩盖矛盾。
            target = copy.deepcopy(records[8]["message"])
            records[9]["message"] = copy.deepcopy(target)
            records[10]["messages"][-1] = copy.deepcopy(target)
            target = (
                records[9]["message"]
                if location == "turn"
                else records[10]["messages"][-1]
            )
            if field == "timestamp":
                target[field] = value
            else:
                target["usage"][field] = value
        return records

    assert invoke(description, FakeFactory(mutate=mutate)) == RpcFailure(
        RpcReason.MESSAGE_MISMATCH
    )


@pytest.mark.parametrize(
    "block",
    [
        {"type": "text", "text": "{}", "textSignature": 1},
        {"type": "thinking", "thinking": "", "thinkingSignature": False},
        {"type": "thinking", "thinking": "", "redacted": 0},
    ],
)
def test_known_optional_content_metadata_is_type_checked(
    description: CallDescription, block: dict[str, Any]
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            records[8]["message"]["content"].append(block)
        return records

    assert invoke(description, FakeFactory(mutate=mutate)) == RpcFailure(
        RpcReason.MESSAGE_SHAPE
    )


@pytest.mark.parametrize(
    "kind",
    [
        "text_start",
        "text_delta",
        "text_end",
        "thinking_start",
        "thinking_delta",
        "thinking_end",
    ],
)
def test_stream_updates_are_allowed_but_never_supply_candidate_or_usage(
    description: CallDescription, kind: str
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            usage = copy.deepcopy(records[8]["message"]["usage"])
            usage.update(input=90, totalTokens=93)
            records.insert(
                8,
                {
                    "type": "message_update",
                    "usage": usage,
                    "assistantMessageEvent": {
                        "type": kind,
                        "contentIndex": 0,
                        "delta": "STREAM_SECRET",
                        "content": "STREAM_SECRET",
                    },
                },
            )
        return records

    result = invoke(description, FakeFactory(mutate=mutate))
    assert isinstance(result, RpcCandidate)
    assert result.input_tokens == 5 and result.output_tokens == 2
    assert b"STREAM_SECRET" not in result.raw_response


@pytest.mark.parametrize(
    "kind",
    [
        "toolcall_start",
        "toolcall_delta",
        "toolcall_end",
        "start",
        "done",
        "error",
        "unknown",
        [],
        {},
    ],
)
def test_forbidden_and_unknown_stream_update_types_fail_closed(
    description: CallDescription, kind: object
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            records.insert(
                8, {"type": "message_update", "assistantMessageEvent": {"type": kind}}
            )
        return records

    assert invoke(description, FakeFactory(mutate=mutate)) == RpcFailure(
        RpcReason.EVENT_NOT_ALLOWED
    )


@pytest.mark.parametrize(
    "kind",
    [
        "tool_execution_start",
        "tool_execution_update",
        "tool_execution_end",
        "auto_retry_start",
        "auto_retry_end",
        "compaction_start",
        "compaction_end",
        "summarization_retry_scheduled",
        "summarization_retry_attempt_start",
        "summarization_retry_finished",
        "queue_update",
        "entry_appended",
        "session_info_changed",
        "thinking_level_changed",
        "extension_error",
        "extension_ui_request",
        "bash_execution_update",
        "session",
        "unknown",
        [],
        {},
        None,
    ],
)
def test_runtime_event_blacklist_includes_even_empty_queue_notifications(
    description: CallDescription, kind: object
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            records.insert(8, {"type": kind, "steering": [], "followUp": []})
        return records

    factory = FakeFactory(mutate=mutate)
    result = invoke(description, factory)
    assert result == RpcFailure(RpcReason.EVENT_NOT_ALLOWED)
    assert result.category.value == "protocol"
    assert factory.sessions[0].closed and factory.sessions[0].terminated


@pytest.mark.parametrize(
    "role",
    [
        "toolResult",
        "custom",
        "bashExecution",
        "branchSummary",
        "compactionSummary",
        "unknown",
        [],
        {},
        None,
    ],
)
def test_non_assistant_roles_cannot_supply_final_candidate(
    description: CallDescription, role: object
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            records[8]["message"]["role"] = role
        return records

    assert invoke(description, FakeFactory(mutate=mutate)) == RpcFailure(
        RpcReason.MESSAGE_SHAPE
    )


@pytest.mark.parametrize(
    "stop",
    [
        "pending",
        "length",
        "toolUse",
        "error",
        "aborted",
        "deferred",
        "unknown",
        [],
        {},
        None,
    ],
)
def test_only_normal_stop_yields_candidate_and_deferred_is_not_polled(
    description: CallDescription, stop: object
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            records[8]["message"]["stopReason"] = stop
        return records

    factory = FakeFactory(mutate=mutate)
    assert invoke(description, factory) == RpcFailure(RpcReason.STOP_REASON)
    assert len(factory.sessions[0].commands) == 9


@pytest.mark.parametrize("index", [1, 2, 3, 5, 7, 8, 9, 10, 11])
def test_duplicate_run_turn_message_or_ending_cannot_create_second_candidate(
    description: CallDescription, index: int
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            records.insert(index + 1, copy.deepcopy(records[index]))
        return records

    assert invoke(description, FakeFactory(mutate=mutate)) == RpcFailure(
        RpcReason.EVENT_SEQUENCE
    )


@pytest.mark.parametrize("index", [4, 6, 8, 9, 10, 11])
def test_missing_ending_never_returns_partial_candidate(
    description: CallDescription, index: int
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            del records[index:]
        return records

    assert invoke(
        description, FakeFactory(mutate=mutate, exit_when_drained=True)
    ) == RpcFailure(RpcReason.EOF)


@pytest.mark.parametrize(
    "scenario,reason",
    [
        ("sections", RpcReason.SYSTEM_MISMATCH),
        ("preamble", RpcReason.SYSTEM_MISMATCH),
        ("content", RpcReason.SYSTEM_MISMATCH),
        ("toolsAdded", RpcReason.SYSTEM_MISMATCH),
        ("toolsRemoved", RpcReason.SYSTEM_MISMATCH),
        ("cwd", RpcReason.SYSTEM_MISMATCH),
        ("user", RpcReason.USER_MISMATCH),
        ("toolResults", RpcReason.MESSAGE_MISMATCH),
        ("willRetry", RpcReason.EVENT_SEQUENCE),
        ("aborted", RpcReason.EVENT_SEQUENCE),
    ],
)
def test_system_user_and_run_guards_have_precise_reasons(
    description: CallDescription, scenario: str, reason: RpcReason
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name != "prompt":
            return records
        system = records[3]["message"]
        if scenario == "sections":
            system["sections"]["project_context"] = "PRIVATE_CONTEXT"
        elif scenario in {"preamble", "cwd"}:
            system["sections"][scenario] = None if scenario == "cwd" else "CHANGED"
        elif scenario == "content":
            system["content"] = "NONEMPTY"
        elif scenario in {"toolsAdded", "toolsRemoved"}:
            system[scenario] = []
        elif scenario == "user":
            records[5]["message"]["content"][0]["text"] = "TRANSFORMED"
        elif scenario == "toolResults":
            records[9]["toolResults"] = [{"role": "toolResult"}]
        elif scenario == "willRetry":
            records[10][scenario] = True
        else:
            records[11][scenario] = True
        return records

    assert invoke(description, FakeFactory(mutate=mutate)) == RpcFailure(reason)


@pytest.mark.parametrize(
    "field", ["api", "provider", "model", "timestamp", "content", "usage"]
)
def test_final_required_fields_cannot_be_missing(
    description: CallDescription, field: str
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            del records[8]["message"][field]
        return records

    reason = RpcReason.USAGE_SHAPE if field == "usage" else RpcReason.MESSAGE_SHAPE
    assert invoke(description, FakeFactory(mutate=mutate)) == RpcFailure(reason)


@pytest.mark.parametrize(
    "content,reason",
    [
        ([], RpcReason.CHANNEL),
        ([{"type": "thinking", "thinking": "PRIVATE"}], RpcReason.CHANNEL),
        ([{"type": "image"}], RpcReason.CHANNEL),
        ([{"type": "toolCall"}], RpcReason.CHANNEL),
        ([{"type": "unknown"}], RpcReason.CHANNEL),
        ([{"type": {}}], RpcReason.CHANNEL),
        ([{"type": "text", "text": 1}], RpcReason.MESSAGE_SHAPE),
    ],
)
def test_final_channel_requires_at_least_one_text_block(
    description: CallDescription, content: object, reason: RpcReason
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            records[8]["message"]["content"] = content
        return records

    assert invoke(description, FakeFactory(mutate=mutate)) == RpcFailure(reason)


def test_multiblock_text_preserves_whitespace_and_known_extra_fields_are_allowed(
    description: CallDescription,
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for record in records:
            record["futureExtra"] = {"version": 1}
        if name == "prompt":
            final = records[8]["message"]
            final.update(
                providerThinkingLevel="provider-specific-effort",
                diagnostics=[],
                endTurn=True,
                responseId="RESPONSE_SECRET",
            )
            final["futureExtra"] = {"runtimeVersion": 1}
            final["content"] = [
                {"type": "text", "text": " \n{", "textSignature": "SIGNATURE_SECRET"},
                {
                    "type": "thinking",
                    "thinking": "THINKING_SECRET",
                    "thinkingSignature": "ENCRYPTED_SECRET",
                },
                {
                    "type": "thinking",
                    "thinking": "",
                    "redacted": True,
                    "thinkingSignature": "REDACTED_SECRET",
                },
                {"type": "text", "text": "}\n "},
            ]
        return records

    result = invoke(description, FakeFactory(mutate=mutate))
    assert isinstance(result, RpcCandidate)
    assert result.raw_response == b" \n{}\n "
    assert "SECRET" not in repr(result)


@pytest.mark.parametrize(
    "field", ["input", "output", "cacheRead", "cacheWrite", "totalTokens"]
)
@pytest.mark.parametrize("value", [True, -1, 1.0, "1", None, [], {}])
def test_usage_token_shape_is_strict(
    description: CallDescription, field: str, value: object
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            records[8]["message"]["usage"][field] = value
        return records

    assert invoke(description, FakeFactory(mutate=mutate)) == RpcFailure(
        RpcReason.USAGE_SHAPE
    )


@pytest.mark.parametrize(
    "location",
    ["system_end", "user_end", "aggregate_system", "aggregate_user", "aggregate_final"],
)
def test_all_complete_message_copies_include_unknown_fields_in_consistency_check(
    description: CallDescription, location: str
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name != "prompt":
            return records
        if location in {"system_end", "user_end"}:
            index = 4 if location == "system_end" else 6
            records[index]["message"] = copy.deepcopy(records[index]["message"])
            records[index]["message"]["futureExtra"] = "COPY_SECRET"
        else:
            index = {"aggregate_system": 0, "aggregate_user": 1, "aggregate_final": 2}[
                location
            ]
            records[10]["messages"] = copy.deepcopy(records[10]["messages"])
            records[10]["messages"][index]["futureExtra"] = "COPY_SECRET"
        return records

    assert invoke(description, FakeFactory(mutate=mutate)) == RpcFailure(
        RpcReason.MESSAGE_MISMATCH
    )


@pytest.mark.parametrize(
    "field", ["input", "output", "cacheRead", "cacheWrite", "total"]
)
@pytest.mark.parametrize("value", [True, -1, "0", None, [], {}])
def test_usage_cost_shape_is_checked_but_cost_is_not_exported(
    description: CallDescription, field: str, value: object
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            records[8]["message"]["usage"]["cost"][field] = value
        return records

    assert invoke(description, FakeFactory(mutate=mutate)) == RpcFailure(
        RpcReason.USAGE_SHAPE
    )


def test_response_model_takes_priority_and_absent_canonical_level_is_allowed(
    description: CallDescription,
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            final = records[8]["message"]
            final.update(
                model="REQUEST_ECHO",
                responseModel="PROVIDER_OBSERVATION",
                providerThinkingLevel="vendor-effort",
            )
            del final["thinkingLevel"]
        return records

    result = invoke(description, FakeFactory(mutate=mutate))
    assert isinstance(result, RpcCandidate)
    assert result.provider == "provider-a" and result.model == "PROVIDER_OBSERVATION"


def test_near_request_candidate_and_aggregate_frame_limits_allow_three_echoes(
    description: CallDescription,
) -> None:
    # DERIVED-04/11: agent_end 包含完整 system+user+assistant,不是单份回答。
    bounded = replace(description, system_prompt=b"S" * (1024 * 1024))
    overhead = len(wire([{"id": "rpc-9", "type": "prompt", "message": ""}]))
    message = b"U" * (256 * 1024 - overhead)
    raw = "T" * (64 * 1024)

    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            final = records[8]["message"]
            final["content"].append(
                {"type": "thinking", "thinking": "", "thinkingSignature": ""}
            )
            size = len(wire([records[10]]))
            final["content"][-1]["thinkingSignature"] = "Q" * (4 * 1024 * 1024 - size)
            assert len(wire([records[10]])) == 4 * 1024 * 1024
            assert 11 * 1024 * 1024 < len(wire(records)) < 16 * 1024 * 1024
        return records

    factory = FakeFactory(raw=raw, mutate=mutate)
    result = run_call(bounded, message, factory, clock=factory.clock)
    assert isinstance(result, RpcCandidate) and result.raw_response == raw.encode()
    assert len(wire([factory.sessions[0].commands[-1]])) == 256 * 1024


def test_candidate_over_limit_never_returns_half_candidate(
    description: CallDescription,
) -> None:
    factory = FakeFactory(raw="T" * (64 * 1024 + 1))
    assert invoke(description, factory) == RpcFailure(RpcReason.CANDIDATE_LIMIT)
    assert factory.sessions[0].terminated


def test_reason_catalog_has_an_explicit_exhaustive_category_mapping() -> None:
    expected = {
        RpcCategory.TIMEOUT: {"timeout", "close_timeout"},
        RpcCategory.CANCELLED: {"cancelled"},
        RpcCategory.ENVIRONMENT: {
            "session_cancelled",
            "model_rejected",
            "startup_error",
            "transport_error",
            "eof",
            "unexpected_exit",
        },
        RpcCategory.PROTOCOL: {
            "invalid_description",
            "invalid_utf8",
            "invalid_json",
            "non_object",
            "duplicate_key",
            "non_finite",
            "frame_limit",
            "stdout_limit",
            "stderr_limit",
            "request_limit",
            "candidate_limit",
            "partial_frame",
            "early_record",
            "response_mismatch",
            "command_rejected",
            "model_state",
            "thinking_unsupported",
            "thinking_state",
            "dirty_state",
            "commands_present",
            "prompt_disposition",
            "event_sequence",
            "event_not_allowed",
            "message_shape",
            "message_mismatch",
            "system_mismatch",
            "user_mismatch",
            "stop_reason",
            "channel",
            "usage_shape",
        },
    }
    assert {name for names in expected.values() for name in names} == {
        reason.value for reason in RpcReason
    }
    for category, names in expected.items():
        for name in names:
            assert RpcFailure(RpcReason(name)).category is category


@pytest.mark.parametrize(
    "kind,fields",
    [
        ("text_start", {"contentIndex": True}),
        ("text_start", {"contentIndex": -1}),
        ("text_start", {}),
        ("text_delta", {"contentIndex": 0, "delta": None}),
        ("thinking_delta", {"contentIndex": 0}),
        ("text_end", {"contentIndex": 0, "content": []}),
        ("thinking_end", {"contentIndex": 0}),
    ],
)
def test_allowed_stream_update_still_requires_its_typed_fields(
    description: CallDescription, kind: str, fields: dict[str, Any]
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            records.insert(
                8,
                {
                    "type": "message_update",
                    "usage": records[8]["message"]["usage"],
                    "assistantMessageEvent": {"type": kind, **fields},
                },
            )
        return records

    assert invoke(description, FakeFactory(mutate=mutate)) == RpcFailure(
        RpcReason.MESSAGE_SHAPE
    )


@pytest.mark.parametrize(
    "field", ["responseModel", "responseId", "providerThinkingLevel"]
)
@pytest.mark.parametrize("value", ["", True, [], {}])
def test_known_optional_message_strings_have_strict_shapes(
    description: CallDescription, field: str, value: object
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            records[8]["message"][field] = value
        return records

    assert invoke(description, FakeFactory(mutate=mutate)) == RpcFailure(
        RpcReason.MESSAGE_SHAPE
    )


@pytest.mark.parametrize("total", [0, 6, 8])
def test_usage_total_must_equal_four_nonnegative_components(
    description: CallDescription, total: int
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            records[8]["message"]["usage"]["totalTokens"] = total
        return records

    assert invoke(description, FakeFactory(mutate=mutate)) == RpcFailure(
        RpcReason.USAGE_SHAPE
    )


@pytest.mark.parametrize("zero", [True, False])
def test_usage_zero_is_unknown_and_cache_and_reasoning_are_not_double_counted(
    description: CallDescription, zero: bool
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            usage = records[8]["message"]["usage"]
            usage.update(
                input=0 if zero else 7,
                output=0 if zero else 5,
                cacheRead=0 if zero else 3,
                cacheWrite=0 if zero else 2,
                totalTokens=0 if zero else 17,
                reasoning=0 if zero else 4,
                cacheWrite1h=0 if zero else 1,
            )
        return records

    result = invoke(description, FakeFactory(mutate=mutate))
    assert isinstance(result, RpcCandidate)
    assert (result.input_tokens, result.output_tokens) == (
        (None, None) if zero else (12, 5)
    )


@pytest.mark.parametrize("level", ["off", "unknown", {}, [], None])
def test_final_canonical_thinking_level_must_match_when_present(
    description: CallDescription, level: object
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            records[8]["message"]["thinkingLevel"] = level
        return records

    assert invoke(description, FakeFactory(mutate=mutate)) == RpcFailure(
        RpcReason.THINKING_STATE
    )


@pytest.mark.parametrize("field", ["reasoning", "cacheWrite1h"])
@pytest.mark.parametrize("value", [True, -1, 1.0, "1", None, [], {}])
def test_optional_usage_counts_have_strict_numeric_shapes(
    description: CallDescription, field: str, value: object
) -> None:
    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            records[8]["message"]["usage"][field] = value
        return records

    assert invoke(description, FakeFactory(mutate=mutate)) == RpcFailure(
        RpcReason.USAGE_SHAPE
    )
