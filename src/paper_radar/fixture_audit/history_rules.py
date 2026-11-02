"""按保存版本选择历史实现;当前默认版本不代替历史版本。"""

from paper_radar.fixture_audit.abstract_versions import parse_abstract_rules_version
from paper_radar.fixture_audit.acquisition_models import AuditPlan
from paper_radar.fixture_audit.errors import FixtureError, FixtureReason

# 产品只发布这些完整历史实现。新默认值不能悄悄改变这个注册表。
# resume_rules.validate_execution_identity 比较当前执行版本,不要求与本历史表恒等。
HISTORICAL_V1 = {
    "acquisition_strategy_version": "audit-acquisition-v1",
    "channels_version": "audit-channels-v1",
    "http_rules_version": "audit-http-v1",
    "parser_version": "audit-parser-v1",
    "sampling_rules_version": "audit-sampling-v1",
    "category_rules_version": "audit-category-v1",
    "ua_template_version": "identified-public-v1",
    "abstract_rules_version": "audit-abstract-v1",
    "truncation_rules_version": "audit-truncation-v1",
    "matrix_rules_version": "audit-matrix-v1",
}


def require_historical_plan(plan: AuditPlan) -> None:
    try:
        parse_abstract_rules_version(plan.abstract_rules_version)
    except ValueError:
        raise FixtureError(
            FixtureReason.UNSUPPORTED_HISTORY, path="audit.plan_versions"
        ) from None
    # HISTORICAL_V1 remains a full historical snapshot. Abstract rules dispatch
    # independently; every other component must match that frozen combination.
    if any(
        getattr(plan, name) != version
        for name, version in HISTORICAL_V1.items()
        if name != "abstract_rules_version"
    ):
        raise FixtureError(
            FixtureReason.UNSUPPORTED_HISTORY, path="audit.plan_versions"
        )
