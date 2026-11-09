"""供执行消费者与 doctor 复用的完整只读当次身份;不准备启动或授予证据。"""

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from paper_radar.live_evidence.baseline import metadata_digest
from paper_radar.live_evidence.evidence import ExecutionBinding
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
from paper_radar.live_evidence.observation import load_current_observation
from paper_radar.live_evidence.service import AdmissionRequest
from paper_radar.live_evidence.types import AdmissionUse, BindingComponent
from paper_radar.pi_execution.admission import EvidenceBinding
from paper_radar.pi_execution.resources import check_credentials_metadata, proxy_port
from paper_radar.pi_execution.site_binding import (
    component_digest,
    node_platform_component,
    site_binding_components,
)
from paper_radar.pi_supply.protection import acquire_install

ADMISSION_POLICY_VERSION = "pi-admission-v1"
PROTECTED_COMPONENTS = frozenset(
    {BindingComponent.IPV4_EGRESS, BindingComponent.OBSERVER}
)


def local_binding_components(
    database: Path, binding: EvidenceBinding, *, credentials_dir: Path
) -> dict[BindingComponent, str]:
    """接收采集与当次比较共用的组件规范摘要;无认证/cache 内容读取。"""
    check_credentials_metadata(credentials_dir)
    proxy_port(binding.proxy)
    with acquire_install(database, binding.supply_id, binding.install_id) as install:
        return {
            **site_binding_components(),
            BindingComponent.NODE_PLATFORM: node_platform_component(
                install.record.manifest.node_version
            ),
            BindingComponent.SUPPLY: component_digest(binding.supply_id),
            BindingComponent.INSTANCE: component_digest(binding.install_id),
            BindingComponent.SUPPLY_TREE: install.record.manifest.expected_tree,
            BindingComponent.INSTANCE_TREE: install.record.manifest.expected_tree,
            BindingComponent.PI_VERSION: component_digest(
                install.record.manifest.pi_version
            ),
            BindingComponent.LAUNCH_POLICY: component_digest(
                (binding.launch_policy_version, ADMISSION_POLICY_VERSION, binding.proxy)
            ),
            BindingComponent.ISOLATION_POLICY: component_digest(
                binding.isolation_policy_version
            ),
            BindingComponent.MODEL_TUPLE: component_digest(
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
            ),
            BindingComponent.AUTH_CACHE_CURRENT: component_digest(
                "credentials-metadata-valid-v1"
            ),
            BindingComponent.AUTH_CACHE_BASELINE: metadata_digest((credentials_dir,)),
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
    observation = load_current_observation(EvidenceLedger(), now=now)
    components = local_binding_components(
        database, binding, credentials_dir=credentials_dir
    )
    protected_coverage = (
        frozenset(observation.checked_components)
        if all(
            observation.binding[component] == value
            for component, value in components.items()
        )
        else frozenset()
    )
    return AdmissionRequest(
        use,
        ExecutionBinding(tuple((observation.binding | components).items())),
        protected_coverage | frozenset(components),
    )


def recheck_admission_request(request: AdmissionRequest, *, now: datetime) -> None:
    """领取事务内只复核短时受保护观察;不重扫安装/认证/cache或宿主树。"""
    observation = load_current_observation(EvidenceLedger(), now=now)
    if (
        ExecutionBinding(tuple(observation.binding.items())) != request.binding
        or not request.checked_components & PROTECTED_COMPONENTS
        <= frozenset(observation.checked_components)
    ):
        raise LedgerError("observation_changed")
