"""供执行消费者与 doctor 复用的完整只读当次身份;不准备启动或授予证据。"""

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from paper_radar.live_evidence.auth_cache_stat import credentials_metadata_digest
from paper_radar.live_evidence.evidence import ExecutionBinding
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
from paper_radar.live_evidence.observation import (
    ObservationChanged,
    load_current_observation,
    load_refresh_status,
    read_observation_snapshot,
)
from paper_radar.live_evidence.service import AdmissionProjection, AdmissionRequest
from paper_radar.live_evidence.types import AdmissionUse, BindingComponent
from paper_radar.pi_execution.admission import EvidenceBinding
from paper_radar.pi_execution.resources import proxy_port
from paper_radar.pi_execution.site_binding import (
    component_digest,
    node_platform_component,
    site_binding_components,
)
from paper_radar.pi_supply import SupplyError
from paper_radar.pi_supply.protection import acquire_install

ADMISSION_POLICY_VERSION = "pi-admission-v24"
# site 观察不承诺某一 thinking 档的模型身份;每格请求/模型证据仍完整比较。
SITE_CONTEXT_EXCLUDED = frozenset({BindingComponent.MODEL_TUPLE})
PROTECTED_COMPONENTS = frozenset(
    {BindingComponent.IPV4_EGRESS, BindingComponent.OBSERVER}
)


def model_tuple_component(binding: EvidenceBinding) -> str:
    """固定模型元组的纯摘要;正式消费者与封印采集共用。"""
    return component_digest(
        {
            key: value
            for key, value in asdict(binding).items()
            if key
            in {
                "provider",
                "model",
                "thinking_level",
                "sampling",
                "temperature",
                "top_p",
                "protocol_profile",
                "auth_mode",
            }
        }
    )


def _declared_components(binding: EvidenceBinding) -> dict[BindingComponent, str]:
    """当前调用的纯身份;本地 I/O 不可用也不能借用站点的 low 模型元组。"""
    return {
        BindingComponent.SUPPLY: component_digest(binding.supply_id),
        BindingComponent.INSTANCE: component_digest(binding.install_id),
        BindingComponent.LAUNCH_POLICY: component_digest(
            (binding.launch_policy_version, ADMISSION_POLICY_VERSION, binding.proxy)
        ),
        BindingComponent.ISOLATION_POLICY: component_digest(
            binding.isolation_policy_version
        ),
        BindingComponent.MODEL_TUPLE: model_tuple_component(binding),
    }


def local_binding_components(
    database: Path, binding: EvidenceBinding, *, credentials_dir: Path
) -> dict[BindingComponent, str]:
    """接收采集与当次比较共用的组件规范摘要;无认证/cache 内容读取。"""
    baseline = credentials_metadata_digest(credentials_dir)
    proxy_port(binding.proxy)
    with acquire_install(database, binding.supply_id, binding.install_id) as install:
        return {
            **site_binding_components(),
            **_declared_components(binding),
            BindingComponent.NODE_PLATFORM: node_platform_component(
                install.record.manifest.node_version
            ),
            BindingComponent.SUPPLY_TREE: install.record.manifest.expected_tree,
            BindingComponent.INSTANCE_TREE: install.record.manifest.expected_tree,
            BindingComponent.PI_VERSION: component_digest(
                install.record.manifest.pi_version
            ),
            BindingComponent.AUTH_CACHE_CURRENT: component_digest(
                "credentials-metadata-valid-v1"
            ),
            BindingComponent.AUTH_CACHE_BASELINE: baseline,
        }


def build_admission_request(
    database: Path,
    binding: EvidenceBinding,
    *,
    use: AdmissionUse,
    credentials_dir: Path,
    now: datetime,
) -> AdmissionRequest:
    """固定受保护观察与当次本地复核合并;不写账本、不刷新或启动子进程。"""
    ledger = EvidenceLedger()
    observation = load_current_observation(ledger, now=now)
    status = load_refresh_status(ledger)
    observation.validate_current(status, now=now)
    components = local_binding_components(
        database, binding, credentials_dir=credentials_dir
    )
    protected_coverage = (
        frozenset(observation.checked_components)
        if all(
            observation.binding[component] == value
            for component, value in components.items()
            if component not in SITE_CONTEXT_EXCLUDED
        )
        else frozenset()
    )
    return AdmissionRequest(
        use,
        ExecutionBinding(tuple((observation.binding | components).items())),
        protected_coverage | frozenset(components),
        observation,
        status,
    )


def recheck_admission_request(request: AdmissionRequest, *, now: datetime) -> None:
    """领取事务内只复核短时受保护观察;不重扫安装/认证/cache或宿主树。"""
    ledger = EvidenceLedger()
    observation = read_observation_snapshot(ledger, now=now)
    status = load_refresh_status(ledger)
    changed = frozenset(
        component
        for component, value in request.binding.components
        if component not in SITE_CONTEXT_EXCLUDED
        and observation.binding[component] != value
    ) | (
        request.checked_components
        & PROTECTED_COMPONENTS - frozenset(observation.checked_components)
    )
    if changed:
        raise ObservationChanged(changed)
    observation.validate_current(status, now=now)


def diagnose_observation_failure(
    database: Path,
    binding: EvidenceBinding,
    *,
    use: AdmissionUse,
    credentials_dir: Path,
    now: datetime,
    error: LedgerError,
) -> AdmissionProjection:
    """只读诊断:保留原主张与时点,输出始终由失败原因封闭。"""
    from paper_radar.live_evidence.observation import (
        load_refresh_status,
        read_observation_snapshot,
    )
    from paper_radar.live_evidence.service import (
        load_admission_evidence,
        unavailable_projection,
    )

    try:
        ledger = EvidenceLedger()
        observation = read_observation_snapshot(ledger, now=now)
        status = load_refresh_status(ledger)
        try:
            components = local_binding_components(
                database, binding, credentials_dir=credentials_dir
            )
        except LedgerError as local_error:
            if local_error.category != "observation_unavailable":
                raise
            # 原快照只供披露旧主张;没有本次 checked 集合,不能恢复执行资格。
            components = _declared_components(binding)
        request = AdmissionRequest(
            use,
            ExecutionBinding(tuple((observation.binding | components).items())),
            frozenset(components),
        )
        projection = load_admission_evidence(request, now=now)
    except LedgerError as source_error:
        return unavailable_projection(use, source_error)
    except SupplyError:
        return unavailable_projection(use, LedgerError("source_untrusted"))
    return unavailable_projection(
        use, error, previous=projection, observation=observation, refresh=status
    )
