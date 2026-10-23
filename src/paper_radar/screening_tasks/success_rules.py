"""原始提交身份与审计/验证细节的确定性序列化。"""

import json
import re
from hashlib import sha256
from typing import Any
from uuid import UUID

from paper_radar.config import RuntimeConfigSnapshot
from paper_radar.config.compile import MaterialKind
from paper_radar.screening import (
    BoundaryOutput,
    OutputErrorCategory,
    OutputValidationIssue,
)
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.rules import canonical
from paper_radar.screening_tasks.success_models import SuccessCandidate


def candidate_audit(candidate: SuccessCandidate) -> str:
    if (
        type(candidate) is not SuccessCandidate
        or type(candidate.raw_response) is not bytes
        or candidate.executor_kind != "test"
        or type(candidate.executor_kind) is not str
    ):
        raise TaskError(TaskReason.INVALID_CANDIDATE)
    audit: dict[str, Any] = {"executor_kind": "test"}
    for name in ("reported_provider", "reported_model", "provider_request_id"):
        value = getattr(candidate, name)
        if value is not None and (
            type(value) is not str
            or not value.strip()
            or len(value.encode("utf-8", errors="replace")) > 2048
        ):
            raise TaskError(TaskReason.INVALID_CANDIDATE)
        if value is not None:
            try:
                value.encode("utf-8")
            except UnicodeError:
                raise TaskError(TaskReason.INVALID_CANDIDATE) from None
        audit[name] = value
    for name in ("input_tokens", "output_tokens"):
        value = getattr(candidate, name)
        if value is not None and (type(value) is not int or value < 0):
            raise TaskError(TaskReason.INVALID_CANDIDATE)
        audit[name] = value
    try:
        return canonical(audit).decode("utf-8")
    except ValueError:
        # Python 对极大整数的十进制转换有运行时限制;不回显审计内容。
        raise TaskError(TaskReason.INVALID_CANDIDATE) from None


def submission_digest(raw: bytes, audit_json: str) -> str:
    return sha256(
        canonical(
            {"raw_sha256": sha256(raw).hexdigest(), "audit": json.loads(audit_json)}
        )
    ).hexdigest()


def model_matches(candidate: SuccessCandidate, snapshot: RuntimeConfigSnapshot) -> bool:
    models = next(
        json.loads(material.config_json)
        for material in snapshot.materials.values()
        if material.kind == MaterialKind.MODELS and material.name == "models"
    )
    expected = models["screening"]
    return all(
        getattr(candidate, "reported_" + name) is None
        or getattr(candidate, "reported_" + name) == expected[name]
        for name in ("provider", "model")
    )


def encode_issues(issues: tuple[OutputValidationIssue, ...]) -> str | None:
    return (
        canonical(
            [
                {"location": issue.location, "category": issue.category.value}
                for issue in issues
            ]
        ).decode("utf-8")
        if issues
        else None
    )


def decode_issues(value: str | None) -> tuple[OutputValidationIssue, ...]:
    if value is None:
        return ()
    fields = set(BoundaryOutput.model_fields)
    parts = "|".join(re.escape(field) for field in fields | {"<额外字段>"})
    records = json.loads(value)
    if type(records) is not list or not records:
        raise TaskError(TaskReason.CORRUPT_REFERENCE)
    result = []
    for item in records:
        if (
            type(item) is not dict
            or set(item) != {"location", "category"}
            or type(item["location"]) is not str
            or re.fullmatch(r"\$(?:\.(?:" + parts + r")|\[\d+\])*", item["location"])
            is None
        ):
            raise TaskError(TaskReason.CORRUPT_REFERENCE)
        result.append(
            OutputValidationIssue(
                item["location"],
                OutputErrorCategory(item["category"]),
                "请按冻结契约修正该字段。",
            )
        )
    issues = tuple(result)
    if encode_issues(issues) != value:
        raise TaskError(TaskReason.CORRUPT_REFERENCE)
    return issues


def require_success_id(value: object) -> None:
    try:
        if type(value) is not str or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise TaskError(TaskReason.CORRUPT_REFERENCE) from None


def stored_candidate(raw: bytes, audit_json: str) -> SuccessCandidate:
    try:
        audit = json.loads(audit_json)
        if type(audit) is not dict:
            raise ValueError
        candidate = SuccessCandidate(raw, **audit)
        if candidate_audit(candidate) != audit_json:
            raise ValueError
        return candidate
    except (ValueError, TypeError, KeyError, TaskError):
        raise TaskError(TaskReason.CORRUPT_REFERENCE) from None
