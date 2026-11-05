"""从明确历史语义与输入构造调用描述;不读取当前配置或执行环境。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from paper_radar.config import RuntimeConfigSnapshot, StageName, project_config
from paper_radar.llm.models import (
    MAX_REQUEST_BYTES,
    PROTOCOL_PROFILES,
    REQUEST_HEADER,
    CallDescription,
    CallDescriptionError,
    DescriptionReason,
)
from paper_radar.llm.read_limits import CORRECTION_SLOT_BYTES, READ_RENDER_VERSION
from paper_radar.llm.rpc_frames import command_frame
from paper_radar.reading.acceptance_v2 import validate_read_context_v2
from paper_radar.reading.context import ReadContext
from paper_radar.stage_inputs import (
    ReadFacts,
    ScreeningFacts,
    StageInput,
    StageInputError,
    replay_stage_input,
)

_PROFILE_ORDER = (
    "background",
    "core_questions",
    "transferable_methods",
    "available_data_and_tools",
    "theory_and_cognitive_interests",
    "constraints_and_exclusions",
)


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def build_call(
    stage_input: StageInput,
    semantic_snapshot: RuntimeConfigSnapshot,
    audit_snapshot: RuntimeConfigSnapshot,
    *,
    read_context: ReadContext | None = None,
    reading: bytes | None = None,
) -> CallDescription:
    """调用者只传已验证历史快照;再次核对阶段输入和两份投影的同源性。"""
    try:
        result = _build(
            stage_input,
            semantic_snapshot,
            audit_snapshot,
            read_context=read_context,
            reading=reading,
        )
        render_request(result)
        return result
    except CallDescriptionError:
        raise
    except (StageInputError, KeyError, TypeError, ValueError, AttributeError):
        raise CallDescriptionError(DescriptionReason.CORRUPT_REFERENCE) from None


def _build(
    stage_input: StageInput,
    semantic_snapshot: RuntimeConfigSnapshot,
    audit_snapshot: RuntimeConfigSnapshot,
    *,
    read_context: ReadContext | None = None,
    reading: bytes | None = None,
) -> CallDescription:
    if (
        type(stage_input) is not StageInput
        or type(semantic_snapshot) is not RuntimeConfigSnapshot
        or type(audit_snapshot) is not RuntimeConfigSnapshot
    ):
        raise CallDescriptionError(DescriptionReason.CORRUPT_REFERENCE)
    if stage_input.stage not in (StageName.BOUNDARY, StageName.VALUE, StageName.READ):
        raise CallDescriptionError(DescriptionReason.INVALID_CONTEXT)
    slot = "reading" if stage_input.stage is StageName.READ else "screening"
    adapter = semantic_snapshot.adapters[slot]
    if (
        semantic_snapshot.stages[stage_input.stage].status != "ready"
        or adapter is None
        or semantic_snapshot.adapter_slots[slot] != "configured"
    ):
        raise CallDescriptionError(DescriptionReason.INVALID_CONTEXT)
    replayed = replay_stage_input(
        stage_input.payload_bytes, stage_input.fingerprint, snapshot=semantic_snapshot
    )
    if replayed != stage_input:
        raise CallDescriptionError(DescriptionReason.CORRUPT_REFERENCE)
    stage = stage_input.stage
    semantic = project_config(semantic_snapshot).projections[stage]
    audit = project_config(audit_snapshot).projections[stage]
    if (audit.format_version, audit.projection_id) != (
        semantic.format_version,
        semantic.projection_id,
    ):
        raise CallDescriptionError(DescriptionReason.PROJECTION_MISMATCH)
    version = audit_snapshot.adapter_selections.get(slot)
    material = next(
        (
            item
            for (kind, name, declared), item in audit_snapshot.materials.items()
            if kind == "adapter" and name == "pi-rpc" and declared == version
        ),
        None,
    )
    if material is None:
        raise CallDescriptionError(DescriptionReason.CORRUPT_REFERENCE)
    execution = json.loads(material.config_json)
    pi_version = execution["pi_version"]
    if pi_version not in PROTOCOL_PROFILES:
        raise CallDescriptionError(DescriptionReason.INVALID_CONTEXT)
    components = json.loads(semantic.payload_json)["components"]
    model = components["model"]
    if model["protocol"] != "prompt_only" or adapter.policy.version != "bounded-rpc-v1":
        raise CallDescriptionError(DescriptionReason.INVALID_CONTEXT)
    facts = stage_input.facts
    if stage is StageName.READ:
        if (
            not isinstance(facts, ReadFacts)
            or type(reading) is not bytes
            or type(read_context) is not ReadContext
        ):
            raise CallDescriptionError(DescriptionReason.INVALID_CONTEXT)
        context = validate_read_context_v2(read_context)
        if (
            (
                context.identity.extraction_fingerprint,
                context.identity.reading_sha256,
                context.identity.evidence_map_sha256,
            )
            != facts.identity
            or context.expected_language != facts.output_language
            or context.mode != "single"
            or hashlib.sha256(reading).hexdigest() != facts.reading_sha256
            or components["chunking_version"] != "v1"
        ):
            raise CallDescriptionError(DescriptionReason.CORRUPT_REFERENCE)
    elif (
        not isinstance(facts, ScreeningFacts)
        or reading is not None
        or read_context is not None
    ):
        raise CallDescriptionError(DescriptionReason.CORRUPT_REFERENCE)
    payload: dict[str, Any] = {
        "stage": stage.value,
        "prompt": components["prompt"],
        "profile": [
            {"name": name, "text": components["profile"][name]}
            for name in _PROFILE_ORDER
        ],
        "contract": components["contract"]["schema"],
        "correction": None,
    }
    if stage is StageName.READ:
        assert (
            isinstance(facts, ReadFacts)
            and reading is not None
            and read_context is not None
        )
        payload.update(
            output_language=facts.output_language,
            body={
                "render_version": READ_RENDER_VERSION,
                "reading": reading.decode("utf-8"),
                "evidence": [
                    {
                        "evidence_id": item.evidence_id,
                        "pages": sorted({p.page_no for p in item.provenance}),
                    }
                    for item in read_context.evidence
                ],
            },
        )
    else:
        assert isinstance(facts, ScreeningFacts)
        payload["paper"] = {
            "title": facts.title,
            "abstract": facts.abstract,
            "abstract_truncated": facts.abstract_truncated,
        }
    if stage is StageName.VALUE:
        payload["topics"] = components["topics"]
    return CallDescription(
        stage="read"
        if stage is StageName.READ
        else ("boundary" if stage is StageName.BOUNDARY else "value"),
        fingerprint=stage_input.fingerprint,
        projection_id=semantic.projection_id,
        semantic_snapshot_id=semantic_snapshot.snapshot_id,
        audit_snapshot_id=audit_snapshot.snapshot_id,
        pi_version=pi_version,
        adapter_version=execution["adapter_version"],
        protocol_profile=PROTOCOL_PROFILES[pi_version],
        provider=model["provider"],
        model=model["model"],
        protocol="prompt_only",
        thinking_level=adapter.thinking_level,
        temperature=model.get("temperature"),
        top_p=model.get("top_p"),
        sampling=model.get("sampling", "explicit"),
        policy_json=_canonical(adapter.policy.model_dump(mode="json")),
        system_prompt=adapter.system_prompt_text.encode("utf-8"),
        stage_input_payload=stage_input.payload_bytes,
        user_payload_json=_canonical(payload),
    )


def render_request(
    description: CallDescription, correction: str | None = None
) -> bytes:
    """精确保留绑定文本;修正由任务层按冻结安全规则构造。"""
    try:
        if type(description) is not CallDescription or (
            correction is not None and type(correction) is not str
        ):
            raise CallDescriptionError(DescriptionReason.INVALID_CONTEXT)
        payload = json.loads(description.user_payload_json)
        if description.stage == "read" and correction is not None:
            initial = command_frame(
                "rpc-9",
                "prompt",
                message=REQUEST_HEADER + _canonical({**payload, "correction": None}),
            )
            corrected = command_frame(
                "rpc-9",
                "prompt",
                message=REQUEST_HEADER
                + _canonical({**payload, "correction": correction}),
            )
            if len(corrected) - len(initial) > CORRECTION_SLOT_BYTES:
                raise CallDescriptionError(DescriptionReason.INVALID_CONTEXT)
        payload["correction"] = correction
        result = (REQUEST_HEADER + _canonical(payload)).encode("utf-8")
        if description.stage != "read" and len(result) > MAX_REQUEST_BYTES:
            raise CallDescriptionError(DescriptionReason.INVALID_CONTEXT)
        return result
    except CallDescriptionError:
        raise
    except (ValueError, TypeError, KeyError):
        raise CallDescriptionError(DescriptionReason.CORRUPT_REFERENCE) from None
