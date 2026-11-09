"""带版本的六格能力登记;变更版本不继承旧证据激活。"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import get_args

from paper_radar.live_evidence.receipt import UseId
from paper_radar.live_evidence.types import (
    AdmissionUse,
    CallSite,
    CapabilityRequirement,
    Consumer,
    RegistryError,
    ThinkingLevel,
    UseRequirements,
)
from paper_radar.live_evidence.types import (
    BindingComponent as B,
)
from paper_radar.live_evidence.types import (
    Capability as C,
)
from paper_radar.live_evidence.types import (
    ExpiryClass as E,
)
from paper_radar.live_evidence.types import (
    Requirement as R,
)


@dataclass(frozen=True, slots=True)
class AdmissionRegistry:
    version: str
    uses: tuple[UseRequirements, ...]

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise RegistryError("registry_version_invalid")
        if not self.uses:
            raise RegistryError("admission_use_undefined")
        seen: set[AdmissionUse] = set()
        for entry in self.uses:
            if entry.use in seen:
                raise RegistryError("duplicate_use")
            seen.add(entry.use)
            capabilities = [rule.capability for rule in entry.requirements]
            if len(capabilities) != len(set(capabilities)):
                raise RegistryError("duplicate_capability")
            if set(capabilities) != set(C):
                raise RegistryError("registry_incomplete")
            if not any(rule.requirement is R.REQUIRED for rule in entry.requirements):
                raise RegistryError("required_set_empty")

    def requirements_for(self, use: AdmissionUse) -> tuple[CapabilityRequirement, ...]:
        for entry in self.uses:
            if entry.use == use:
                return entry.requirements
        raise RegistryError("admission_use_undefined")


# 每项独立登记类别与依赖,不能由 verified 或当前是否可观察推导分类。
_REQUIRED: tuple[tuple[C, E, frozenset[B]], ...] = (
    (C.AUTH_CACHE_CURRENT, E.SITE, frozenset({B.AUTH_CACHE_CURRENT})),
    (C.AUTH_CACHE_BASELINE, E.SITE, frozenset({B.AUTH_CACHE_BASELINE})),
    (C.CWD_ANCESTORS, E.SITE, frozenset({B.CWD_ANCESTORS})),
    (C.FILE_ISOLATION, E.SITE, frozenset({B.FILE_ISOLATION, B.ISOLATION_POLICY})),
    (C.IPV4_EGRESS, E.SITE, frozenset({B.IPV4_EGRESS})),
    (C.ZERO_CORE, E.SITE, frozenset({B.CORE_LIMITS})),
    (C.APPORT_IDENTITY, E.SITE, frozenset({B.APPORT})),
    (C.RPC_COMPLETION, E.UNCLASSIFIED, frozenset({B.PI_VERSION, B.LAUNCH_POLICY})),
    (C.RPC_EOF, E.UNCLASSIFIED, frozenset({B.PI_VERSION, B.LAUNCH_POLICY})),
    (C.RPC_TERMINATE, E.UNCLASSIFIED, frozenset({B.PI_VERSION, B.LAUNCH_POLICY})),
    (C.MODEL_IDENTITY, E.PROVIDER, frozenset({B.MODEL_TUPLE})),
    (C.SINGLE_DISPATCH, E.ENGINEERING, frozenset({B.LAUNCH_POLICY, B.OBSERVER})),
    (C.NO_EXTRA_TURNS, E.PROVIDER, frozenset({B.MODEL_TUPLE, B.OBSERVER})),
    (C.SUPPLY_TREE, E.SITE, frozenset({B.SUPPLY, B.SUPPLY_TREE})),
    (C.INSTANCE_TREE, E.SITE, frozenset({B.INSTANCE, B.INSTANCE_TREE})),
    (C.PI_VERSION, E.SITE, frozenset({B.PI_VERSION, B.NODE_PLATFORM})),
    (C.LAUNCH_POLICY, E.ENGINEERING, frozenset({B.LAUNCH_POLICY})),
    (C.ISOLATION_POLICY, E.ENGINEERING, frozenset({B.ISOLATION_POLICY})),
    (C.HOST_RUNTIME, E.SITE, frozenset({B.HOST, B.BOOT, B.KERNEL, B.LANDLOCK_ABI})),
)
_DISCLOSED = (
    C.PI_PUBLIC_300_SECONDS,
    C.PROVIDER_LATENCY,
    C.PROVIDER_ERRORS,
    C.THINKING_EFFECT,
    C.DATE_ALIAS,
    C.ACCOUNT_MODELS,
    C.ACCOUNT_LIMITS,
    C.EXACT_REQUEST_COUNT,
    C.AUTH_CACHE_HISTORY,
    C.AUTH_CACHE_WRITER,
)
_NOT_APPLICABLE = (
    C.SUPERVISOR_EXIT,
    C.EXTERNAL_INTERRUPT,
    C.IPV6,
    C.NEW_PLATFORM,
    C.UNATTENDED,
    C.NAS,
)
_RULES = (
    tuple(
        CapabilityRequirement(c, R.REQUIRED, expiry, deps)
        for c, expiry, deps in _REQUIRED
    )
    + tuple(
        CapabilityRequirement(
            c,
            R.DISCLOSURE,
            E.UNCLASSIFIED
            if c in {C.AUTH_CACHE_HISTORY, C.AUTH_CACHE_WRITER}
            else E.PROVIDER,
            frozenset({B.AUTH_CACHE_BASELINE, B.OBSERVER})
            if c in {C.AUTH_CACHE_HISTORY, C.AUTH_CACHE_WRITER}
            else frozenset({B.MODEL_TUPLE, B.OBSERVER})
            if c is C.EXACT_REQUEST_COUNT
            else frozenset({B.MODEL_TUPLE}),
        )
        for c in _DISCLOSED
    )
    + tuple(
        CapabilityRequirement(
            c,
            R.NOT_APPLICABLE,
            E.ENGINEERING if c is C.EXTERNAL_INTERRUPT else E.UNCLASSIFIED,
            frozenset({B.PI_VERSION, B.LAUNCH_POLICY})
            if c is C.EXTERNAL_INTERRUPT
            else frozenset(),
        )
        for c in _NOT_APPLICABLE
    )
)
INITIAL_REGISTRY = AdmissionRegistry(
    "live-admission-v1",
    tuple(
        UseRequirements(AdmissionUse(site, consumer, level), _RULES)
        for site, consumer in (
            (CallSite.SCREENING, Consumer.BOUNDARY),
            (CallSite.SCREENING, Consumer.VALUE),
            (CallSite.READ, Consumer.READ),
        )
        for level in (ThinkingLevel.LOW, ThinkingLevel.HIGH)
    ),
)


def _use_ids() -> Mapping[AdmissionUse, UseId]:
    # wire Literal 保持冻结;当前登记必须与它一一闭合,不借内部事件载荷铸造用途。
    wire_ids: tuple[UseId, ...] = get_args(UseId)
    indexed = {value: value for value in wire_ids}
    result: dict[AdmissionUse, UseId] = {}
    for entry in INITIAL_REGISTRY.uses:
        identifier = f"{entry.use.consumer.value}-{entry.use.thinking_level.value}"
        if identifier not in indexed:
            raise RegistryError("admission_use_undefined")
        result[entry.use] = indexed[identifier]
    if set(result.values()) != set(wire_ids) or len(result) != len(wire_ids):
        raise RegistryError("registry_incomplete")
    return MappingProxyType(result)


USE_IDS = _use_ids()


def use_id_for(use: AdmissionUse) -> UseId:
    try:
        return USE_IDS[use]
    except KeyError:
        raise RegistryError("admission_use_undefined") from None


def use_for_id(identifier: str) -> AdmissionUse:
    for use, use_id in USE_IDS.items():
        if identifier == use_id:
            return use
    raise RegistryError("admission_use_undefined")
