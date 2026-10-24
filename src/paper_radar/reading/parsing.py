"""Read 结构解析,保留原始候选边界并隔离底层异常。"""

import json
import math
from typing import Any

from pydantic import ValidationError

from paper_radar.reading.errors import ReadErrorCategory, ReadIssue, ReadOutputError
from paper_radar.reading.schema import (
    EvidenceRef,
    ReadAnalysisOutput,
    ReusablePoint,
    SupportedStatement,
)

_FIELDS = frozenset(
    name
    for model in (ReadAnalysisOutput, EvidenceRef, SupportedStatement, ReusablePoint)
    for name in model.model_fields
)


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in values:
        if name in result:
            raise ValueError("duplicate key")
        result[name] = value
    return result


def _constant(value: str) -> object:
    raise ValueError("non-finite number")


def _check_json(value: object) -> None:
    pending = [value]
    while pending:
        item = pending.pop()
        if type(item) is str:
            item.encode("utf-8")
        elif type(item) is float and not math.isfinite(item):
            raise ValueError("non-finite number")
        elif type(item) is list:
            pending.extend(item)
        elif type(item) is dict:
            pending.extend(item)
            pending.extend(item.values())


def _schema_issue(detail: dict[str, Any]) -> ReadIssue:
    reason = detail["type"]
    category = {
        "missing": ReadErrorCategory.MISSING_FIELD,
        "extra_forbidden": ReadErrorCategory.EXTRA_FIELD,
        "literal_error": ReadErrorCategory.INVALID_ENUM,
        "enum": ReadErrorCategory.INVALID_ENUM,
        "value_error": ReadErrorCategory.INVALID_ENUM,
        "greater_than_equal": ReadErrorCategory.INVALID_SCORE,
        "less_than_equal": ReadErrorCategory.INVALID_SCORE,
        "string_too_short": ReadErrorCategory.INVALID_EVIDENCE_ID,
        "too_short": ReadErrorCategory.EVIDENCE_REQUIRED,
    }.get(reason, ReadErrorCategory.INVALID_TYPE)
    if reason == "literal_error" and type(detail.get("input")) is not str:
        category = ReadErrorCategory.INVALID_TYPE
    location = "$"
    for part in detail["loc"]:
        location += (
            f"[{part}]"
            if type(part) is int
            else ("." + part if part in _FIELDS else ".<额外字段>")
        )
    return ReadIssue(location, category)


def parse_candidate(raw: bytes) -> ReadAnalysisOutput:
    if type(raw) is not bytes:
        raise ReadOutputError((ReadIssue("$", ReadErrorCategory.INVALID_TYPE),))
    output: ReadAnalysisOutput | None = None
    issues: tuple[ReadIssue, ...] = ()
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant
        )
        _check_json(value)
        if type(value) is not dict:
            raise ValueError("expected object")
        output = ReadAnalysisOutput.model_validate(value)
    except ValidationError as error:
        issues = tuple(
            _schema_issue(dict(detail))
            for detail in error.errors(include_url=False, include_context=False)
        )
    except (ValueError, RecursionError):
        issues = (ReadIssue("$", ReadErrorCategory.INVALID_JSON),)
    if issues:
        raise ReadOutputError(issues)
    assert output is not None
    return output
