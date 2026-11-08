"""准入用途、能力及绑定组件的闭合领域词表。"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class EvidenceStatus(StrEnum):
    VERIFIED = "verified"
    NOT_ASSESSED = "not_assessed"
    UNKNOWN = "unknown"


class Requirement(StrEnum):
    REQUIRED = "required"
    DISCLOSURE = "disclosure"
    NOT_APPLICABLE = "not_applicable"


class ExpiryClass(StrEnum):
    PROVIDER = "provider"
    SITE = "site"
    ENGINEERING = "engineering"
    UNCLASSIFIED = "unclassified"


class CallSite(StrEnum):
    SCREENING = "PiExecution.run_attempt"
    READ = "read_execution"


class Consumer(StrEnum):
    BOUNDARY = "boundary"
    VALUE = "value"
    READ = "read"


class ThinkingLevel(StrEnum):
    LOW = "low"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class AdmissionUse:
    call_site: CallSite
    consumer: Consumer
    thinking_level: ThinkingLevel


class Capability(StrEnum):
    AUTH_CACHE_CURRENT = "auth_cache_current"
    AUTH_CACHE_BASELINE = "auth_cache_baseline"
    CWD_ANCESTORS = "cwd_ancestors"
    FILE_ISOLATION = "file_isolation"
    IPV4_EGRESS = "ipv4_egress"
    ZERO_CORE = "zero_core"
    APPORT_IDENTITY = "apport_identity"
    RPC_COMPLETION = "rpc_completion"
    RPC_EOF = "rpc_eof"
    RPC_TERMINATE = "rpc_terminate"
    MODEL_IDENTITY = "model_identity"
    SINGLE_DISPATCH = "single_dispatch"
    NO_EXTRA_TURNS = "no_extra_turns"
    SUPPLY_TREE = "supply_tree"
    INSTANCE_TREE = "instance_tree"
    PI_VERSION = "pi_version"
    LAUNCH_POLICY = "launch_policy"
    ISOLATION_POLICY = "isolation_policy"
    HOST_RUNTIME = "host_runtime"
    PI_PUBLIC_300_SECONDS = "pi_public_300_seconds"
    PROVIDER_LATENCY = "provider_latency"
    PROVIDER_ERRORS = "provider_errors"
    THINKING_EFFECT = "thinking_effect"
    DATE_ALIAS = "date_alias"
    ACCOUNT_MODELS = "account_models"
    ACCOUNT_LIMITS = "account_limits"
    EXACT_REQUEST_COUNT = "exact_request_count"
    AUTH_CACHE_HISTORY = "auth_cache_history"
    AUTH_CACHE_WRITER = "auth_cache_writer"
    SUPERVISOR_EXIT = "supervisor_exit"
    EXTERNAL_INTERRUPT = "external_interrupt"
    IPV6 = "ipv6"
    NEW_PLATFORM = "new_platform"
    UNATTENDED = "unattended"
    NAS = "nas"


class BindingComponent(StrEnum):
    SUPPLY = "supply"
    INSTANCE = "instance"
    SUPPLY_TREE = "supply_tree"
    INSTANCE_TREE = "instance_tree"
    PI_VERSION = "pi_version"
    NODE_PLATFORM = "node_platform"
    LAUNCH_POLICY = "launch_policy"
    ISOLATION_POLICY = "isolation_policy"
    HOST = "host"
    BOOT = "boot"
    KERNEL = "kernel"
    LANDLOCK_ABI = "landlock_abi"
    CWD_ANCESTORS = "cwd_ancestors"
    FILE_ISOLATION = "file_isolation"
    IPV4_EGRESS = "ipv4_egress"
    CORE_LIMITS = "core_limits"
    APPORT = "apport"
    OBSERVER = "observer"
    MODEL_TUPLE = "model_tuple"
    AUTH_CACHE_CURRENT = "auth_cache_current"
    AUTH_CACHE_BASELINE = "auth_cache_baseline"


RegistryReason = Literal[
    "admission_use_undefined",
    "required_set_empty",
    "required_dependencies_empty",
    "duplicate_use",
    "duplicate_capability",
    "expiry_limit_invalid",
    "registry_version_invalid",
    "registry_incomplete",
    "binding_incomplete",
    "binding_duplicate",
]


class RegistryError(ValueError):
    def __init__(self, reason: RegistryReason) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class CapabilityRequirement:
    capability: Capability
    requirement: Requirement
    expiry_class: ExpiryClass
    dependencies: frozenset[BindingComponent]
    maximum_age_days: int | None = None
    material_dependent: bool = False

    def __post_init__(self) -> None:
        if self.maximum_age_days is not None and (
            type(self.maximum_age_days) is not int or self.maximum_age_days <= 0
        ):
            raise RegistryError("expiry_limit_invalid")
        if self.requirement is Requirement.REQUIRED and not self.dependencies:
            raise RegistryError("required_dependencies_empty")


@dataclass(frozen=True, slots=True)
class UseRequirements:
    use: AdmissionUse
    requirements: tuple[CapabilityRequirement, ...]
