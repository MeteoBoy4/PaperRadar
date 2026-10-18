"""供给请求、冻结清单及只读查询的权威类型。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from paper_radar.config.adapters import exact_program_version
from paper_radar.config.identity import canonical_json, sha256
from paper_radar.pi_supply.errors import SupplyReason

Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Decision = Literal["no_change", "may_change", "unknown"]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    @field_validator("*", mode="before")
    @classmethod
    def no_boolean_format(cls, value: object, info: object) -> object:
        if (
            getattr(info, "field_name", None) == "format_version"
            and type(value) is not int
        ):
            raise ValueError("format version requires integer")
        return value


class Platform(Frozen):
    os: Literal["linux"]
    arch: Literal["x86_64"]
    libc: Literal["glibc"]


class RequestEvidence(Frozen):
    kind: Literal["evidence_file", "supply_material", "supply_record"]
    path: str | None = None
    material: str | None = None
    supply_id: Hash | None = None
    check_id: int | None = None
    note: str | None = None

    @model_validator(mode="after")
    def shape(self) -> RequestEvidence:
        if self.kind == "evidence_file":
            valid = bool(self.path) and self.material is None and self.supply_id is None
        elif self.kind == "supply_material":
            valid = bool(self.material) and self.path is None and self.check_id is None
        else:
            valid = self.supply_id is not None and self.path is self.material is None
        if not valid or (self.kind == "evidence_file" and self.check_id is not None):
            raise ValueError("evidence shape")
        return self


class RequestD5(Frozen):
    decision: Decision
    basis: Annotated[str, Field(min_length=1, max_length=16384)]
    baseline_supply_id: Hash | None
    evidence: tuple[RequestEvidence, ...]

    @field_validator("evidence", mode="before")
    @classmethod
    def sequence(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def complete(self) -> RequestD5:
        if not self.basis.strip() or not self.evidence:
            raise ValueError("D5 incomplete")
        if self.baseline_supply_id is None and self.decision == "no_change":
            raise ValueError("D5 baseline required")
        return self


class SupplyRequest(Frozen):
    format_version: Literal[1]
    node_version: str
    npm_version: str
    node_source: Literal["nodejs.org"]
    node_sha256: Hash
    platform: Platform
    d5: RequestD5

    @field_validator("node_version", "npm_version")
    @classmethod
    def exact_version(cls, value: str) -> str:
        return exact_program_version(value)


class Evidence(Frozen):
    kind: Literal["evidence_file", "supply_material", "supply_record"]
    sha256: Hash | None = None
    material: str | None = None
    supply_id: Hash | None = None
    check_id: int | None = None
    note: str | None = None

    @model_validator(mode="after")
    def shape(self) -> Evidence:
        if self.kind == "evidence_file":
            valid = self.sha256 is not None and self.material is self.supply_id is None
        elif self.kind == "supply_material":
            valid = (
                self.sha256 is not None
                and bool(self.material)
                and self.check_id is None
            )
        else:
            valid = self.supply_id is not None and self.sha256 is self.material is None
        if not valid or (self.kind == "evidence_file" and self.check_id is not None):
            raise ValueError("evidence shape")
        return self


class D5(Frozen):
    decision: Decision
    basis: str
    baseline_supply_id: Hash | None
    evidence: tuple[Evidence, ...]

    @field_validator("evidence", mode="before")
    @classmethod
    def sequence(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def complete(self) -> D5:
        if not self.basis.strip() or not self.evidence or len(self.basis) > 16384:
            raise ValueError("D5 incomplete")
        if self.baseline_supply_id is None and self.decision == "no_change":
            raise ValueError("D5 baseline required")
        return self


class SupplyManifest(Frozen):
    format_version: Literal[1] = 1
    pi_version: str
    node_version: str
    npm_version: str
    node_sha256: Hash
    platform: Platform
    libc_version: str
    install_policy: Literal["install-policy-v1"] = "install-policy-v1"
    derived_lock_rule: Literal["derived-lock-v1"] = "derived-lock-v1"
    tree_rule: Literal["tree-v1"] = "tree-v1"
    materials: dict[str, Hash]
    expected_tree: Hash
    node_entry: str
    npm_entry: str
    pi_entry: str
    d5: D5

    @field_validator("pi_version", "node_version", "npm_version")
    @classmethod
    def exact_version(cls, value: str) -> str:
        return exact_program_version(value)

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json(self.model_dump(mode="json"))

    @property
    def supply_id(self) -> str:
        return sha256(self.canonical_bytes)

    @property
    def material_key(self) -> str:
        payload = self.model_dump(
            mode="json", exclude={"d5", "expected_tree", "pi_entry"}
        )
        payload["materials"] = {
            key: value
            for key, value in self.materials.items()
            if not key.startswith("d5-evidence/")
        }
        return sha256(canonical_json(payload))


@dataclass(frozen=True)
class InstallCheck:
    check_id: int
    scope: str
    passed: bool
    reason: str
    created_at: str


@dataclass(frozen=True)
class InstallInstance:
    install_id: str
    root_id: str
    path: Path
    created_at: str
    checks: tuple[InstallCheck, ...]


@dataclass(frozen=True)
class RebuildFailure:
    failure_id: int
    reason: str
    created_at: str


@dataclass(frozen=True)
class SupplyRecord:
    supply_id: str
    manifest: SupplyManifest
    materials: dict[str, bytes]
    installs: tuple[InstallInstance, ...]
    created_at: str
    rebuild_failures: tuple[RebuildFailure, ...] = ()


@dataclass(frozen=True)
class PrepareResult:
    supply_id: str
    install_id: str
    reused_concurrent: bool = False
    residuals: bool = False


@dataclass(frozen=True)
class VerificationResult:
    install_id: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class Activation:
    activation_id: int
    supply_id: str
    install_id: str
    snapshot_id: str
    root_id: str
    root_path: Path
    created_at: str


@dataclass(frozen=True)
class InstanceDiagnosis:
    supply_id: str
    install_id: str
    reason: SupplyReason | Literal["passed"]
    present: bool | None
    protection: tuple[str, ...]


@dataclass(frozen=True)
class DoctorReport:
    passed: bool
    current: Activation | None
    blockers: tuple[SupplyReason, ...]
    configuration_missing: tuple[str, ...]
    adapter_unconfigured: tuple[str, ...]
    instances: tuple[InstanceDiagnosis, ...]
    retained_install_ids: tuple[str, ...]
    acceptance_install_ids: tuple[str, ...]
    present_count: int
    d5: D5 | None
    not_assessed: tuple[str, ...] = (
        "rpc_compatibility",
        "provider_model",
        "credentials",
        "parameter_mapping",
        "production_isolation",
        "calibration",
        "automatic_read",
        "in_flight_protection",
    )


@dataclass(frozen=True)
class RetentionProtection:
    retained_install_ids: tuple[str, ...]
    acceptance_install_ids: tuple[str, ...]
