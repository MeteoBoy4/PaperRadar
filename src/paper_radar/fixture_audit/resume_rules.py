"""显式继续允许的暂时性终态及完整执行身份。"""

from paper_radar.fixture_audit import abstract_models, acquisition_models
from paper_radar.fixture_audit.acquisition_identity import capture_code_identity
from paper_radar.fixture_audit.acquisition_models import (
    AuditPlan,
    CodeIdentity,
    RouteExecution,
    revalidate_model,
)
from paper_radar.fixture_audit.errors import FixtureError, FixtureReason

TEMPORARY_REASONS = frozenset(
    {
        "transient_error",
        "rate_limited",
        "deferred_retry_after",
        "outcome_unknown",
        "agency_unknown",
        "provider_incomplete",
        "access_blocked_403",
        "not_attempted",
    }
)


def can_continue(execution: RouteExecution) -> bool:
    return execution.settlement is None or execution.reason in TEMPORARY_REASONS


def validate_execution_identity(
    plan: AuditPlan, code_identity: CodeIdentity | None
) -> None:
    try:
        code = (
            revalidate_model(code_identity, CodeIdentity)
            if code_identity is not None
            else capture_code_identity()
        )
    except (ValueError, TypeError, RecursionError):
        raise FixtureError(
            FixtureReason.PLAN_IDENTITY_MISMATCH, path="code_identity"
        ) from None
    # 当前执行准入随默认实现升级;历史回放独立使用 history_rules.HISTORICAL_V1。
    versions = {
        "acquisition_strategy_version": acquisition_models.ACQUISITION_STRATEGY_VERSION,
        "channels_version": acquisition_models.CHANNELS_VERSION,
        "http_rules_version": acquisition_models.HTTP_RULES_VERSION,
        "parser_version": acquisition_models.PARSER_VERSION,
        "sampling_rules_version": acquisition_models.SAMPLING_RULES_VERSION,
        "category_rules_version": acquisition_models.CATEGORY_RULES_VERSION,
        "ua_template_version": acquisition_models.UA_TEMPLATE_VERSION,
        "abstract_rules_version": abstract_models.ABSTRACT_RULES_VERSION,
        "truncation_rules_version": abstract_models.TRUNCATION_RULES_VERSION,
        "matrix_rules_version": abstract_models.MATRIX_RULES_VERSION,
    }
    if code != plan.code_identity or any(
        getattr(plan, field) != version for field, version in versions.items()
    ):
        raise FixtureError(FixtureReason.PLAN_IDENTITY_MISMATCH, path="code_identity")
