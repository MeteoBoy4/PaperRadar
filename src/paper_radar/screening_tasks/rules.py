"""请求身份与文本约束;纯确定性规则。"""

import hashlib
import json
from datetime import date

from pydantic import ValidationError

from paper_radar.papers import PaperError
from paper_radar.papers.text_rules import normalize_text
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.models import (
    BoundaryRequest,
    RegistrationRequest,
    ValueRequest,
)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def parse_request(raw: object) -> BoundaryRequest | ValueRequest:
    try:
        if isinstance(raw, BoundaryRequest | ValueRequest):
            raw = raw.model_dump()
        if not isinstance(raw, dict):
            raise ValueError
        request: BoundaryRequest | ValueRequest
        if raw.get("stage") == "boundary":
            request = BoundaryRequest.model_validate(raw)
        elif raw.get("stage") == "value":
            request = ValueRequest.model_validate(raw)
        else:
            raise ValueError
        if request.source == "scheduled":
            if (
                request.scheduled_day is None
                or date.fromisoformat(request.scheduled_day).isoformat()
                != request.scheduled_day
                or any(
                    v is not None
                    for v in (request.request_id, request.reason, request.actor)
                )
            ):
                raise ValueError
        elif request.scheduled_day is not None:
            raise ValueError
        else:
            for value in (request.request_id, request.reason, request.actor):
                if (
                    not isinstance(value, str)
                    or not value.strip()
                    or len(value.encode("utf-8")) > 2048
                ):
                    raise ValueError
                normalize_text(value)
        canonical(request.model_dump())
        return request
    except (ValueError, TypeError, ValidationError, PaperError):
        raise TaskError(TaskReason.INVALID_REQUEST) from None


def request_digest(request: RegistrationRequest) -> str:
    return digest(request.model_dump())


def receipt_id(
    request: BoundaryRequest | ValueRequest,
    evidence: dict[str, object],
    fingerprint: str,
) -> str:
    if request.source == "manual":
        return digest({"source": "manual", "request_id": request.request_id})
    return digest(
        {
            "source": "scheduled",
            "paper_id": request.paper_id,
            "stage": request.stage,
            "fingerprint": fingerprint,
            "scheduled_day": request.scheduled_day,
            "version_id": evidence["version_id"],
            "revision_no": evidence["revision_no"],
            "snapshot_id": request.snapshot_id,
        }
    )
