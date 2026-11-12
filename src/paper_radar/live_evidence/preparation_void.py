"""显式双失败准备作废;保全原字节,候选失败耐久回滚至无策略基线。"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import model_validator

from paper_radar.live_evidence.epoch_lineage import (
    EpochUpgrade,
    continuity_identity,
    verify_installed_upgrade,
)
from paper_radar.live_evidence.live_apparmor_kernel import (
    AppArmorKernel,
    KernelPolicyIO,
    LinuxKernelPolicyIO,
)
from paper_radar.live_evidence.live_install import (
    InstallationPaths,
    LiveDeployment,
    json_bytes,
    protected,
    publish,
    verify_tree,
)
from paper_radar.live_evidence.placement_policy import (
    PlacementPolicyLifecycle,
    read_placement_policy,
    verify_host_security,
)
from paper_radar.live_evidence.preparation_retirement import (
    FailedPreparation,
    FailedPreparationRetirement,
    describe_preparation_recovery,
)
from paper_radar.live_evidence.receipt import Digest, WireModel

_STAGING_ROOT = Path("/var/lib/paperradar/live-bundles")
_PHASES = frozenset(
    {
        "void_intent",
        "failed_policy_removing",
        "clean",
        "candidate_preparing",
        "candidate_rollback",
        "rollback_failed",
        "prepared",
    }
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class FailedPreparationSource(WireModel):
    failure_stage: Literal["no_secret_preflight"] = "no_secret_preflight"
    payload_sha256: Digest
    runtime_manifest_sha256: Digest
    journal_sha256: Digest


class FailedPreparationVoidDescriptor(WireModel):
    format_version: Literal[1] = 1
    authorization: Literal["owner-authorized-zero-operation-preparations-v1"]
    sources: tuple[FailedPreparationSource, FailedPreparationSource]
    failed_placement_identity: Digest
    failed_marker_sha256: Digest
    new_placement_identity: Digest
    upgrade_from: tuple[Digest, Digest]
    epoch_upgrade_sha256: Digest
    continuity_sha256: Digest
    baseline: Literal["auth=0;network=0;model=0;remaining=40/40;idle;unstopped"]

    @model_validator(mode="before")
    @classmethod
    def strict_version(cls, value: Any) -> Any:
        if isinstance(value, dict) and type(value.get("format_version", 1)) is not int:
            raise ValueError("format_version")
        return value


def describe_preparation_void(
    first: Path, second: Path, new: Path, journals: tuple[bytes, bytes]
) -> FailedPreparationVoidDescriptor:
    """只读派生明确 v1 退役→单跳恢复的两来源;不接受任意链或路径授权。"""
    specs = []
    sources = []
    for root, raw in zip((first, second), journals, strict=True):
        payload = (root / "payload.sha256").read_text().strip()
        verify_tree(root, owner_uid=root.stat().st_uid, anchor=root, payload=payload)
        specs.append(json.loads((root / "deployment.json").read_bytes()))
        sources.append(
            FailedPreparationSource(
                payload_sha256=payload,
                runtime_manifest_sha256=_sha((root / "manifest.sha256").read_bytes()),
                journal_sha256=_sha(raw),
            )
        )
    spec = json.loads((new / "deployment.json").read_bytes())
    descriptor = FailedPreparation.model_validate(specs[0].get("failed_preparation"))
    recovery = describe_preparation_recovery(first, second, journals[0])
    if (
        sources[0].payload_sha256 == sources[1].payload_sha256
        or specs[1].get("preparation_recovery") != recovery.model_dump(mode="json")
        or any(key in spec for key in ("failed_preparation", "preparation_recovery"))
        or any("failed_preparation_void" in old for old in specs)
    ):
        raise ValueError("preparation_void_sources")
    for source, old, raw in zip(sources, specs, journals, strict=True):
        identity = {
            "format_version": 1,
            "payload": source.payload_sha256,
            "manifest": source.runtime_manifest_sha256,
            "descriptor": descriptor.model_dump(mode="json"),
        }
        if "preparation_recovery" in old:
            identity["preparation_recovery"] = old["preparation_recovery"]
        if raw != json_bytes({**identity, "phase": "preparing"}):
            raise ValueError("preparation_void_source_journal")
    ignored = {
        "strict_beta",
        "failed_preparation",
        "preparation_recovery",
        "failed_preparation_void",
        "placement_preflight_version",
    }
    if {key: value for key, value in specs[1].items() if key not in ignored} != {
        key: value for key, value in spec.items() if key not in ignored
    } or continuity_identity(second) != continuity_identity(new):
        raise ValueError("preparation_void_continuity")
    if (
        type(spec.get("placement_preflight_version")) is not int
        or spec.get("placement_preflight_version") != 2
    ):
        raise ValueError("preparation_void_preflight_protocol")
    previous, current = read_placement_policy(second), read_placement_policy(new)
    if previous is None or current is None or previous.identity == current.identity:
        raise ValueError("preparation_void_policy")
    epoch = EpochUpgrade.model_validate(spec.get("epoch_upgrade"))
    return FailedPreparationVoidDescriptor(
        authorization="owner-authorized-zero-operation-preparations-v1",
        sources=(sources[0], sources[1]),
        failed_placement_identity=previous.identity,
        failed_marker_sha256=_sha(
            json_bytes(
                {
                    "format_version": 1,
                    "identity": previous.identity,
                    "phase": "preparing",
                }
            )
        ),
        new_placement_identity=current.identity,
        upgrade_from=(epoch.payload_sha256, epoch.runtime_manifest_sha256),
        epoch_upgrade_sha256=_sha(json_bytes(epoch.model_dump(mode="json"))),
        continuity_sha256=continuity_identity(new)[0],
        baseline="auth=0;network=0;model=0;remaining=40/40;idle;unstopped",
    )


class FailedPreparationVoid:
    """collector 独占锁下运行;check 只读,prepare 有界写入并可显式恢复。"""

    def __init__(
        self,
        staged: Path,
        paths: InstallationPaths,
        *,
        owner_uid: int = 0,
        kernel_io: KernelPolicyIO | None = None,
    ) -> None:
        self.staged, self.paths, self.owner_uid = staged, paths, owner_uid
        spec = json.loads((staged / "deployment.json").read_bytes())
        raw = spec.get("failed_preparation_void")
        self.descriptor = (
            FailedPreparationVoidDescriptor.model_validate(raw)
            if raw is not None
            else None
        )
        self.io = kernel_io or LinuxKernelPolicyIO()

    @property
    def journal(self) -> Path:
        from pydantic import TypeAdapter

        payload = (self.staged / "payload.sha256").read_text().strip()
        TypeAdapter(Digest).validate_python(payload)
        return self.paths.ledger / f"placement-void-v1-{payload}.json"

    def _read(self, path: Path) -> bytes:
        protected(path, self.owner_uid, anchor=self.paths.anchor)
        before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) != 0o644
            or before.st_size > 65536
        ):
            raise ValueError("preparation_void_record")
        raw = path.read_bytes()
        after = path.lstat()
        if any(
            getattr(before, field) != getattr(after, field)
            for field in (
                "st_dev",
                "st_ino",
                "st_mode",
                "st_nlink",
                "st_uid",
                "st_gid",
                "st_size",
                "st_mtime_ns",
                "st_ctime_ns",
            )
        ):
            raise ValueError("preparation_void_record_changed")
        return raw

    def _identity(self) -> dict[str, Any]:
        assert self.descriptor is not None
        return {
            "format_version": 1,
            "payload": (self.staged / "payload.sha256").read_text().strip(),
            "manifest": _sha((self.staged / "manifest.sha256").read_bytes()),
            "descriptor": self.descriptor.model_dump(mode="json"),
        }

    def _phase(self) -> str | None:
        if not os.path.lexists(self.journal):
            return None
        raw = self._read(self.journal)
        try:
            value = json.loads(raw)
        except ValueError:
            raise ValueError("preparation_void_journal") from None
        phase = value.get("phase") if isinstance(value, dict) else None
        if (
            not isinstance(phase, str)
            or phase not in _PHASES
            or raw != json_bytes({**self._identity(), "phase": phase})
        ):
            raise ValueError("preparation_void_journal")
        return str(phase)

    def _record(self, phase: str) -> None:
        publish(
            self.journal,
            json_bytes({**self._identity(), "phase": phase}),
            replace=self.journal.exists(),
        )

    def _lifecycles(self) -> tuple[PlacementPolicyLifecycle, PlacementPolicyLifecycle]:
        assert self.descriptor is not None
        old = _STAGING_ROOT / self.descriptor.sources[1].payload_sha256 / "runtime"
        result = []
        for root in (old, self.staged):
            sealed = read_placement_policy(root)
            if sealed is None:
                raise ValueError("preparation_void_policy")
            result.append(
                PlacementPolicyLifecycle(
                    root,
                    self.paths.ledger,
                    owner_uid=self.owner_uid,
                    anchor=self.paths.anchor,
                    kernel=AppArmorKernel(self.io, sealed.parser),
                )
            )
        return result[0], result[1]

    def _originals(self) -> dict[Path, bytes]:
        assert self.descriptor is not None
        result = {}
        for source in self.descriptor.sources:
            path = (
                self.paths.ledger
                / f"placement-retirement-v1-{source.payload_sha256}.json"
            )
            raw = self._read(path)
            if _sha(raw) != source.journal_sha256:
                raise ValueError("preparation_void_source_journal")
            result[path] = raw
        old, _ = self._lifecycles()
        raw = self._read(old.journal)
        if _sha(raw) != self.descriptor.failed_marker_sha256:
            raise ValueError("preparation_void_failed_marker")
        result[old.journal] = raw
        return result

    def archives(self) -> dict[Path, bytes]:
        """明确的三份不可覆盖内容寻址归档;不扫描或清理未知材料。"""
        return {
            self.paths.ledger / f"placement-void-archive-v1-{_sha(raw)}.json": raw
            for raw in self._originals().values()
        }

    def _authenticate(
        self,
    ) -> tuple[PlacementPolicyLifecycle, PlacementPolicyLifecycle, str | None]:
        assert self.descriptor is not None
        roots = tuple(
            _STAGING_ROOT / source.payload_sha256 / "runtime"
            for source in self.descriptor.sources
        )
        for root, source in zip(roots, self.descriptor.sources, strict=True):
            verify_tree(
                root,
                owner_uid=self.owner_uid,
                anchor=self.paths.anchor,
                payload=source.payload_sha256,
                manifest_digest=source.runtime_manifest_sha256,
            )
        verify_tree(
            self.staged,
            owner_uid=self.owner_uid,
            anchor=self.paths.anchor,
            payload=self._identity()["payload"],
            manifest_digest=self._identity()["manifest"],
        )
        originals = self._originals()
        raw_sources = list(originals.values())
        if (
            describe_preparation_void(
                roots[0], roots[1], self.staged, (raw_sources[0], raw_sources[1])
            )
            != self.descriptor
        ):
            raise ValueError("preparation_void_descriptor")
        phase = self._phase()
        old, new = self._lifecycles()
        known = {*originals, self.journal, old.journal, new.journal, *self.archives()}
        if (
            any(os.path.lexists(path.with_name(path.name + ".new")) for path in known)
            or any(self.paths.ledger.glob("placement-void-v1-*.json.new"))
            or any(self.paths.ledger.glob("placement-retirement-v1-*.json.new"))
        ):
            raise ValueError("preparation_void_pending_file")
        if any(
            path != self.journal
            for path in self.paths.ledger.glob("placement-void-v1-*.json")
        ):
            raise ValueError("preparation_void_journal_conflict")
        for archive, raw in self.archives().items():
            if os.path.lexists(archive):
                if self._read(archive) != raw:
                    raise ValueError("preparation_void_archive")
            elif phase is not None:
                raise ValueError("preparation_void_archive_missing")
        self._candidate_marker(new, phase)
        if phase == "prepared":
            return old, new, phase
        # 复用原协议的完整 old19→first→second 认证,但不授予原协议 kernel 写权限。
        historical = FailedPreparationRetirement(
            roots[1], self.paths, owner_uid=self.owner_uid, kernel_io=self.io
        )
        historical.authenticate_preparing_source()
        state = LiveDeployment(
            self.staged, paths=self.paths, host=None, owner_uid=self.owner_uid
        )._read_journal()
        verify_installed_upgrade(
            self.staged,
            paths=self.paths,
            state=state,
            identity={
                "format_version": 2,
                "payload": self._identity()["payload"],
                "manifest": self._identity()["manifest"],
                "upgrade_from": list(self.descriptor.upgrade_from),
            },
            owner_uid=self.owner_uid,
        )
        if read_placement_policy(self.paths.runtime) is not None:
            raise ValueError("preparation_void_main_placement")
        self.verify_main_resources()
        self.verify_zero_operation_baseline()
        assert new.sealed is not None
        verify_host_security(new.sealed)
        return old, new, phase

    def _candidate_marker(
        self, new: PlacementPolicyLifecycle, phase: str | None
    ) -> None:
        if not os.path.lexists(new.journal):
            if phase == "prepared":
                raise ValueError("preparation_void_candidate_marker")
            return
        raw = self._read(new.journal)
        try:
            value = json.loads(raw)
            allowed = (
                {"removed"}
                if phase == "clean"
                else {"preparing", "prepared", "removing", "removed"}
                if phase
                in {
                    "candidate_preparing",
                    "candidate_rollback",
                    "rollback_failed",
                    "prepared",
                }
                else set()
            )
            assert new.sealed is not None
            if (
                not isinstance(value, dict)
                or type(value.get("format_version")) is not int
                or value.get("phase") not in allowed
                or raw
                != json_bytes(
                    {
                        "format_version": 1,
                        "identity": new.sealed.identity,
                        "phase": value.get("phase"),
                    }
                )
            ):
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError("preparation_void_candidate_marker") from None

    def verify_main_resources(self) -> None:
        """供已核来源的安装报告独立检查旧主部署资源。"""
        if self.descriptor is not None and self._phase() != "prepared":
            LiveDeployment(
                self.paths.runtime,
                paths=self.paths,
                host=None,
                owner_uid=self.owner_uid,
            )._check_resources()

    def verify_zero_operation_baseline(self) -> None:
        """供已核来源的安装报告独立检查零调用、空闲与候选无证据。"""
        if self.descriptor is not None and self._phase() != "prepared":
            self._baseline(
                tuple(
                    _STAGING_ROOT / source.payload_sha256 / "runtime"
                    for source in self.descriptor.sources
                )
            )

    def _baseline(self, roots: tuple[Path, ...]) -> None:
        from paper_radar.live_evidence.collection import ProtectedCollection
        from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust

        ledger = EvidenceLedger(
            self.paths.ledger,
            trust=LedgerTrust(owner_uid=self.owner_uid, anchor=self.paths.anchor),
        )
        collection = ProtectedCollection(ledger)
        if not collection.zero_operation_baseline():
            raise ValueError("preparation_void_zero_operation_baseline")
        try:
            LiveDeployment(
                self.staged, paths=self.paths, host=None, owner_uid=self.owner_uid
            )._unexecuted_resources((*roots, self.staged), allow_installed_target=True)
        except ValueError:
            raise ValueError("preparation_void_candidate_evidence") from None

    def check(self, *, recover: bool = False) -> bool:
        if self.descriptor is None:
            return False
        old, new, phase = self._authenticate()
        assert old.kernel is not None and old.sealed is not None
        assert new.kernel is not None and new.sealed is not None
        if phase == "prepared":
            return False
        if phase is not None and not recover:
            raise ValueError("preparation_void_recovery_required")
        if phase in {None, "void_intent"}:
            if old.kernel.check(old.sealed.policy) != "exact":
                raise ValueError("preparation_void_failed_policy_missing")
            if os.path.lexists(new.journal):
                raise ValueError("preparation_void_candidate_marker")
        elif phase == "failed_policy_removing":
            old.kernel.check(old.sealed.policy, allow_partial=True)
        else:
            actual = new.check(recover=True)
            if phase == "clean" and actual != "absent":
                raise ValueError("preparation_void_clean_policy_present")
        return True

    def _rollback(self, new: PlacementPolicyLifecycle) -> None:
        self._record("candidate_rollback")
        try:
            new.remove(recover=True)
            new.verify_absent()
        except Exception:
            self._record("rollback_failed")
            raise ValueError("preparation_void_rollback_failed") from None
        self._record("clean")

    def prepare(
        self,
        preflight: Callable[[], None],
        check_idle: Callable[[], None],
        *,
        recover: bool = False,
    ) -> bool:
        if not self.check(recover=recover):
            return False
        old, new, phase = self._authenticate()
        check_idle()
        self.check(recover=recover)
        if phase is None:
            for archive, raw in self.archives().items():
                if not os.path.lexists(archive):
                    publish(archive, raw)
                if self._read(archive) != raw:
                    raise ValueError("preparation_void_archive")
            self._record("void_intent")
            phase = "void_intent"
        if phase == "void_intent":
            self._record("failed_policy_removing")
            phase = "failed_policy_removing"
        if phase == "failed_policy_removing":
            assert old.kernel is not None and old.sealed is not None
            old.kernel.remove(old.sealed.policy, allow_partial=True)
            if old.kernel.check(old.sealed.policy) != "absent":
                raise ValueError("preparation_void_failed_policy_present")
            self._record("clean")
        elif phase in {"candidate_preparing", "candidate_rollback", "rollback_failed"}:
            self._rollback(new)
        self._record("candidate_preparing")
        try:
            new.prepare(preflight, recover=True)
            new.verify()
            self._record("prepared")
        except Exception:
            self._rollback(new)
            raise
        return True
