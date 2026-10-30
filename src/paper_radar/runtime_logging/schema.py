"""日志字段只接受封闭 vocabulary 和有界标识符,未知字段不序列化。"""

import re
from collections.abc import Mapping
from datetime import datetime

FORMAT_VERSION = 1
FINGERPRINT_LENGTH = 16
EVENTS = frozenset(
    {
        "claimed",
        "succeeded",
        "failed",
        "submit_rejected",
        "reclaimed",
        "interrupted",
        "unexpected_error",
        "run_started",
        "run_finished",
        "route_settled",
    }
)
COMPONENTS = frozenset({"screening", "audit", "feed", "metadata"})
ROUTES = frozenset(
    {"feed", "doi_ra", "registry_crossref", "registry_datacite", "publisher"}
)
CATEGORIES = frozenset(
    {
        "completed",
        "controlled_failure",
        "acquired",
        "not_found",
        "rate_limited",
        "transient_error",
        "invalid_response",
        "provider_incomplete",
        "access_blocked_403",
        "not_applicable_no_doi",
        "agency_unknown",
        "agency_unsupported",
        "identity_mismatch",
        "unrecognized_page_shape",
        "record_without_abstract",
        "outcome_unknown",
        "deferred_retry_after",
        "not_attempted",
        "disallowed_destination",
        "disallowed_scheme",
        "channel_not_installed",
        "invalid_feed",
    }
)
KINDS = frozenset(
    {
        "output_invalid",
        "model_mismatch",
        "timeout",
        "cancelled",
        "protocol_error",
        "executor_error",
        "outcome_unknown",
    }
)
REASONS = frozenset(
    {
        "language_missing",
        "language_ambiguous",
        "task_not_found",
        "already_retried",
        "not_latest",
        "not_failed",
        "invalid_request",
        "invalid_context",
        "context_conflict",
        "request_conflict",
        "request_not_found",
        "facts_changed",
        "corrupt_reference",
        "database_busy",
        "invalid_clock",
        "task_running",
        "budget_exhausted",
        "invalid_credential",
        "settlement_conflict",
        "invalid_failure",
        "invalid_candidate",
        "already_succeeded",
        "success_not_found",
        "data_root_required",
    }
)
IDS = frozenset({"task_id", "paper_id", "run_id", "plan_id", "execution_id"})
VOCABULARY = {
    "event": EVENTS,
    "component": COMPONENTS,
    "route": ROUTES,
    "category": CATEGORIES,
    "kind": KINDS,
    "reason": REASONS,
    "stage": frozenset({"boundary", "value", "reuse", "read"}),
}


def safe_event(event: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {"format_version": FORMAT_VERSION}
    for name, allowed in VOCABULARY.items():
        if name in event:
            value = event[name]
            if type(value) is not str or value not in allowed:
                raise ValueError("invalid_log_vocabulary")
            result[name] = value
    if "event" not in result or "component" not in result:
        raise ValueError("invalid_log_event")
    for name in IDS:
        if name in event:
            value = event[name]
            if (
                type(value) is not str
                or re.fullmatch(
                    r"(?:[0-9a-f]{32}|[0-9a-f]{64}|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})",
                    value,
                )
                is None
            ):
                raise ValueError("invalid_log_identifier")
            result[name] = value
    if "fingerprint" in event:
        value = event["fingerprint"]
        if type(value) is not str or re.fullmatch(r"[0-9a-f]{16,64}", value) is None:
            raise ValueError("invalid_log_fingerprint")
        result["fingerprint"] = value[:FINGERPRINT_LENGTH]
    for name in ("attempt", "elapsed_ms"):
        if name in event:
            value = event[name]
            if (
                type(value) is not int
                or value < 0
                or (name == "attempt" and value not in {1, 2})
            ):
                raise ValueError("invalid_log_number")
            result[name] = value
    if "timestamp" in event:
        value = event["timestamp"]
        if type(value) is not str:
            raise ValueError("invalid_log_timestamp")
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError("invalid_log_timestamp")
        result["timestamp"] = parsed.isoformat()
    return result
