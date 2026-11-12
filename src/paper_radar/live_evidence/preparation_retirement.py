"""仅退役已认证、从未安装的失败放置准备;不替换已安装策略或业务状态。

生产调用由既有installer的collector独占锁序列化;本模块不另建锁协议。
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import model_validator

from paper_radar.live_evidence.epoch_lineage import (
    EpochUpgrade,
    continuity_identity,
    verify_installed_upgrade,
)
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
from paper_radar.live_evidence.live_apparmor_kernel import (
    AppArmorKernel,
    KernelPolicyIO,
    LinuxKernelPolicyIO,
    SealedPolicy,
)
from paper_radar.live_evidence.live_install import (
    InstallationPaths,
    json_bytes,
    protected,
    publish,
    verify_tree,
)
from paper_radar.live_evidence.model_manifest import USES, ModelManifest
from paper_radar.live_evidence.placement_policy import (
    MEMBERS,
    PlacementPolicyLifecycle,
    read_placement_policy,
    verify_host_security,
)
from paper_radar.live_evidence.receipt import (
    Digest,
    UseId,
    WireModel,
    canonical_bytes,
    content_sha256,
)
from paper_radar.live_evidence.types import BindingComponent as B

_STAGING_ROOT = Path("/var/lib/paperradar/live-bundles")
_PHASES = {"intent", "snapshotted", "removing", "removed", "preparing", "prepared"}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class FailedPreparation(WireModel):
    format_version: Literal[1] = 1
    payload_sha256: Digest
    runtime_manifest_sha256: Digest
    placement_identity: Digest
    binary_sha256: Digest
    source_sha256: Digest
    marker_sha256: Digest
    new_placement_identity: Digest
    upgrade_from: tuple[Digest, Digest]
    epoch_upgrade_sha256: Digest
    continuity_sha256: Digest

    @model_validator(mode="before")
    @classmethod
    def strict_version(cls, value: Any) -> Any:
        if isinstance(value, dict) and type(value.get("format_version", 1)) is not int:
            raise ValueError("failed_preparation_descriptor")
        return value


def original_marker(descriptor: FailedPreparation) -> bytes:
    return json_bytes(
        {
            "format_version": 1,
            "identity": descriptor.placement_identity,
            "phase": "preparing",
        }
    )


def describe_failed_preparation(old: Path, new: Path) -> FailedPreparation:
    """离线只读候选;安装时从固定root staged地址重读,不信任构建输入路径。"""
    payload = (old / "payload.sha256").read_text().strip()
    # 候选也核完整成员闭包;候选的本地owner不等于安装时root认证。
    verify_tree(old, owner_uid=old.stat().st_uid, anchor=old, payload=payload)
    previous, current = read_placement_policy(old), read_placement_policy(new)
    if previous is None or current is None:
        raise ValueError("failed_preparation_policy")
    old_spec = json.loads((old / "deployment.json").read_bytes())
    new_spec = json.loads((new / "deployment.json").read_bytes())
    epoch = EpochUpgrade.model_validate(new_spec.get("epoch_upgrade"))
    pair = (epoch.payload_sha256, epoch.runtime_manifest_sha256)
    derived = {"strict_beta", "failed_preparation", "preparation_recovery"}
    if (
        old_spec.get("failed_preparation") is not None
        or old_spec.get("epoch_upgrade") != new_spec.get("epoch_upgrade")
        or old_spec.get("upgrade_from") != list(pair)
        or new_spec.get("upgrade_from") != list(pair)
        or continuity_identity(old) != continuity_identity(new)
        or {key: value for key, value in old_spec.items() if key not in derived}
        != {key: value for key, value in new_spec.items() if key not in derived}
    ):
        raise ValueError("failed_preparation_continuity")
    changed = {
        "placement/apparmor.source",
        "placement/apparmor.bin",
        "placement/build.json",
    }
    if any(
        (old / name).read_bytes() != (new / name).read_bytes()
        for name in MEMBERS
        if name not in changed
    ):
        raise ValueError("failed_preparation_policy_change")
    old_source = (old / "placement/apparmor.source").read_bytes()
    true = previous.security["tools"]["/usr/bin/true"]
    old_rule = b"  /usr/bin/true ix,\n"
    new_rule = f'  "{true["resolved"]}" ix,\n'.encode("ascii")
    old_build, new_build = dict(previous.build), dict(current.build)
    if old_build["format_version"] != 1 or new_build["format_version"] != 2:
        raise ValueError("failed_preparation_policy_change")
    old_build["format_version"] = 2
    for name in ("source_sha256", "binary_sha256"):
        old_build.pop(name)
        new_build.pop(name)
    fixed_true = new_build.pop("fixed_true_exec", None)
    if (
        "fixed_true_exec" in old_build
        or fixed_true != true
        or old_build != new_build
        or old_source.count(old_rule) != 1
        or old_source.replace(old_rule, new_rule)
        != (new / "placement/apparmor.source").read_bytes()
        or previous.policy.binary_sha256 == current.policy.binary_sha256
        or previous.identity == current.identity
    ):
        raise ValueError("failed_preparation_policy_change")
    marker = json_bytes(
        {"format_version": 1, "identity": previous.identity, "phase": "preparing"}
    )
    return FailedPreparation(
        payload_sha256=payload,
        runtime_manifest_sha256=_sha((old / "manifest.sha256").read_bytes()),
        placement_identity=previous.identity,
        binary_sha256=previous.policy.binary_sha256,
        source_sha256=previous.policy.source_sha256,
        marker_sha256=_sha(marker),
        new_placement_identity=current.identity,
        upgrade_from=pair,
        epoch_upgrade_sha256=_sha(json_bytes(epoch.model_dump(mode="json"))),
        continuity_sha256=continuity_identity(new)[0],
    )


class PreparationRecovery(WireModel):
    """仅命名一个原preparing候选及其原日志字节;不接受路径或链。"""

    payload_sha256: Digest
    runtime_manifest_sha256: Digest
    journal_sha256: Digest


def describe_preparation_recovery(
    old: Path, new: Path, old_journal_raw: bytes
) -> PreparationRecovery:
    """离线派生一跳候选;root仍从固定staged/ledger地址重认证。"""
    payload = (old / "payload.sha256").read_text().strip()
    verify_tree(old, owner_uid=old.stat().st_uid, anchor=old, payload=payload)
    old_spec = json.loads((old / "deployment.json").read_bytes())
    new_spec = json.loads((new / "deployment.json").read_bytes())
    if (
        "preparation_recovery" in old_spec
        or old == new
        or (
            (new / "payload.sha256").exists()
            and (new / "payload.sha256").read_text().strip() == payload
        )
    ):
        raise ValueError("preparation_recovery_one_hop")
    descriptor = FailedPreparation.model_validate(old_spec.get("failed_preparation"))
    derived = {"strict_beta", "preparation_recovery"}
    if {key: value for key, value in old_spec.items() if key not in derived} != {
        key: value for key, value in new_spec.items() if key not in derived
    } or continuity_identity(old) != continuity_identity(new):
        raise ValueError("preparation_recovery_continuity")
    if any((old / name).read_bytes() != (new / name).read_bytes() for name in MEMBERS):
        raise ValueError("preparation_recovery_policy_change")
    previous, current = read_placement_policy(old), read_placement_policy(new)
    if (
        previous is None
        or current is None
        or previous.identity != current.identity
        or previous.identity != descriptor.new_placement_identity
    ):
        raise ValueError("preparation_recovery_policy_change")
    manifest = _sha((old / "manifest.sha256").read_bytes())
    if old_journal_raw != json_bytes(
        {
            "format_version": 1,
            "payload": payload,
            "manifest": manifest,
            "descriptor": descriptor.model_dump(mode="json"),
            "phase": "preparing",
        }
    ):
        raise ValueError("preparation_recovery_journal")
    return PreparationRecovery(
        payload_sha256=payload,
        runtime_manifest_sha256=manifest,
        journal_sha256=_sha(old_journal_raw),
    )


class _HistoricalEnrollment(WireModel):
    format_version: Literal[1]
    manifest_sha256: Digest
    site_receipt_sha256: Digest
    target_sha256: Digest
    owner_confirmation_sha256: Digest
    bindings: dict[UseId, dict[B, Digest]]

    @model_validator(mode="before")
    @classmethod
    def strict_version(cls, value: Any) -> Any:
        if isinstance(value, dict) and type(value.get("format_version")) is not int:
            raise ValueError("failed_preparation_refresh_source")
        return value


def _historical_refresh_stopped(
    ledger: EvidenceLedger, manifest: ModelManifest, *, now: datetime
) -> bool:
    """只在退役接缝重放原root登记;不读取/刷新当前站点,不改历史或授予资格。"""
    from paper_radar.live_evidence.normal_auth_refresh import (
        NormalRefreshReview,
        normal_review_path,
        review_normal_refresh,
    )

    path = normal_review_path(ledger, manifest)
    if not os.path.lexists(path):
        return False
    try:
        raw = ledger._read_source(path)
        report = NormalRefreshReview.model_validate_json(raw)
        if canonical_bytes(report) != raw:
            raise ValueError
        manifest_sha = content_sha256(manifest)
        if report.manifest_sha256 != manifest_sha:
            source = ledger.root / "inbox" / f"collection-bindings-{manifest_sha}.json"
            raw = ledger._read_source(source)
            enrollment = _HistoricalEnrollment.model_validate_json(raw)
            if (
                canonical_bytes(enrollment) != raw
                or enrollment.manifest_sha256 != manifest_sha
                or enrollment.owner_confirmation_sha256
                != manifest.network.owner_confirmation_sha256
                or set(enrollment.bindings) != set(USES)
            ):
                raise ValueError
            cells = []
            for cell in manifest.cells:
                binding = enrollment.bindings[cell.use_id]
                if set(binding) != set(B) or any(
                    binding[part] != value for part, value in cell.binding.items()
                ):
                    raise ValueError
                cells.append(cell.model_copy(update={"binding": binding}))
            # 原静态模型禁止部署后字段;仅替换已类型校验并认证的完整历史绑定。
            manifest = manifest.model_copy(update={"cells": tuple(cells)})
            if content_sha256(manifest) != report.manifest_sha256:
                raise ValueError
        return review_normal_refresh(ledger, manifest, now=now).stopped
    except (ValueError, LedgerError):
        # 在本接缝映射有限原因;不改变installer的历史异常处理。
        raise ValueError("failed_preparation_refresh_source") from None


class _ExistingPreparationKernel(AppArmorKernel):
    """一跳接续只核现存策略;耐久认领之后的漂移也不能触达kernel写入口。"""

    def load(self, policy: SealedPolicy) -> bool:
        self.verify(policy)
        return False

    def remove(self, policy: SealedPolicy, *, allow_partial: bool = False) -> bool:
        raise ValueError("preparation_recovery_kernel_write_refused")


class FailedPreparationRetirement:
    """check只读;prepare先保存原记录再严格remove,全阶段不得写旧业务对象。"""

    def __init__(
        self,
        staged: Path,
        paths: InstallationPaths,
        *,
        owner_uid: int = 0,
        kernel_io: KernelPolicyIO | None = None,
    ) -> None:
        self.staged, self.paths, self.owner_uid = staged, paths, owner_uid
        specification = json.loads((staged / "deployment.json").read_bytes())
        raw = specification.get("failed_preparation")
        self.descriptor = (
            FailedPreparation.model_validate(raw) if raw is not None else None
        )
        recovery = specification.get("preparation_recovery")
        self.recovery = (
            PreparationRecovery.model_validate(recovery)
            if "preparation_recovery" in specification
            else None
        )
        if self.recovery is not None and self.descriptor is None:
            raise ValueError("preparation_recovery_requires_retirement")
        self.io = kernel_io or LinuxKernelPolicyIO()

    def _read(self, path: Path) -> bytes:
        protected(path, self.owner_uid, anchor=self.paths.anchor)
        before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o644
            or before.st_nlink != 1
            or before.st_size > 16384
        ):
            raise ValueError("failed_preparation_record")
        raw = path.read_bytes()
        after = path.lstat()
        # 读取可以更新atime;身份/保护属性和内容时点必须稳定。
        fields = (
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
        if any(getattr(before, name) != getattr(after, name) for name in fields):
            raise ValueError("failed_preparation_record_changed")
        return raw

    @property
    def journal(self) -> Path:
        payload = (self.staged / "payload.sha256").read_text().strip()
        # 校验SHA后才拼任何受保护路径。
        from pydantic import TypeAdapter

        TypeAdapter(Digest).validate_python(payload)
        return self.paths.ledger / ("placement-retirement-v1-" + payload + ".json")

    @property
    def snapshot(self) -> Path:
        assert self.descriptor is not None
        return self.paths.ledger / (
            "placement-failed-preparation-v1-"
            + self.descriptor.placement_identity
            + ".json"
        )

    def _identity(self) -> dict[str, Any]:
        assert self.descriptor is not None
        value = {
            "format_version": 1,
            "payload": (self.staged / "payload.sha256").read_text().strip(),
            "manifest": _sha((self.staged / "manifest.sha256").read_bytes()),
            "descriptor": self.descriptor.model_dump(mode="json"),
        }
        if self.recovery is not None:
            value["preparation_recovery"] = self.recovery.model_dump(mode="json")
        return value

    def _phase(self) -> str | None:
        if not os.path.lexists(self.journal):
            return None
        raw = self._read(self.journal)
        try:
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError
            phase = value.get("phase")
            if (
                not isinstance(phase, str)
                or phase
                not in (
                    {"preparing", "prepared"} if self.recovery is not None else _PHASES
                )
                or json_bytes({**self._identity(), "phase": phase}) != raw
            ):
                raise ValueError
        except (ValueError, TypeError, KeyError):
            raise ValueError("failed_preparation_journal") from None
        return str(phase)

    def _record(self, phase: str) -> None:
        protected(self.paths.ledger, self.owner_uid, anchor=self.paths.anchor)
        publish(
            self.journal,
            json_bytes({**self._identity(), "phase": phase}),
            replace=self.journal.exists(),
        )

    def _lifecycles(self) -> tuple[PlacementPolicyLifecycle, PlacementPolicyLifecycle]:
        assert self.descriptor is not None
        old_root = _STAGING_ROOT / self.descriptor.payload_sha256 / "runtime"
        new_policy = read_placement_policy(self.staged)
        old_policy = read_placement_policy(old_root)
        if new_policy is None or old_policy is None:
            raise ValueError("failed_preparation_policy")
        return (
            PlacementPolicyLifecycle(
                old_root,
                self.paths.ledger,
                owner_uid=self.owner_uid,
                anchor=self.paths.anchor,
                kernel=AppArmorKernel(self.io, old_policy.parser),
            ),
            PlacementPolicyLifecycle(
                self.staged,
                self.paths.ledger,
                owner_uid=self.owner_uid,
                anchor=self.paths.anchor,
                kernel=(
                    _ExistingPreparationKernel
                    if self.recovery is not None
                    else AppArmorKernel
                )(self.io, new_policy.parser),
            ),
        )

    def _authenticate(
        self,
    ) -> tuple[PlacementPolicyLifecycle, PlacementPolicyLifecycle, str | None]:
        assert self.descriptor is not None
        old_root = _STAGING_ROOT / self.descriptor.payload_sha256 / "runtime"
        for root, payload, manifest in (
            (
                old_root,
                self.descriptor.payload_sha256,
                self.descriptor.runtime_manifest_sha256,
            ),
            (self.staged, self._identity()["payload"], self._identity()["manifest"]),
        ):
            verify_tree(
                root,
                owner_uid=self.owner_uid,
                anchor=self.paths.anchor,
                payload=payload,
                manifest_digest=manifest,
            )
        # 新增的旧staged来源先核完整保护树,再允许读取任何policy成员。
        source = self.staged
        allowed_journals = {self.journal}
        if self.recovery is not None:
            if any(self.paths.ledger.glob("placement-retirement-v1-*.json.new")):
                raise ValueError("failed_preparation_pending_file")
            source = _STAGING_ROOT / self.recovery.payload_sha256 / "runtime"
            verify_tree(
                source,
                owner_uid=self.owner_uid,
                anchor=self.paths.anchor,
                payload=self.recovery.payload_sha256,
                manifest_digest=self.recovery.runtime_manifest_sha256,
            )
            source_journal = self.paths.ledger / (
                "placement-retirement-v1-" + self.recovery.payload_sha256 + ".json"
            )
            if os.path.lexists(source_journal.with_name(source_journal.name + ".new")):
                raise ValueError("failed_preparation_pending_file")
            raw_source = self._read(source_journal)
            if (
                _sha(raw_source) != self.recovery.journal_sha256
                or describe_preparation_recovery(source, self.staged, raw_source)
                != self.recovery
            ):
                raise ValueError("preparation_recovery_source")
            allowed_journals.add(source_journal)
        old, new = self._lifecycles()
        # 原失败策略仍按原v1->v2接缝认证,不能直接用新源码跳过原候选。
        if describe_failed_preparation(old.root, source) != self.descriptor:
            raise ValueError("failed_preparation_source")
        for path in (self.journal, self.snapshot, old.journal, new.journal):
            if os.path.lexists(path.with_name(path.name + ".new")):
                raise ValueError("failed_preparation_pending_file")
        if any(
            path not in allowed_journals
            for path in self.paths.ledger.glob("placement-retirement-v1-*.json")
        ):
            raise ValueError("failed_preparation_journal_conflict")
        phase = self._phase()
        if self.recovery is not None and phase is None:
            # 只有完整认证原preparing来源后才产生内存阶段;首写仍在idle+重验之后。
            phase = "preparing"
        if os.path.lexists(self.snapshot):
            if self._read(self.snapshot) != original_marker(self.descriptor):
                raise ValueError("failed_preparation_snapshot")
            if phase is None:
                raise ValueError("failed_preparation_snapshot_unowned")
        elif phase not in {None, "intent"}:
            raise ValueError("failed_preparation_snapshot_missing")
        # prepared 后不再按“失败旧准备”判定MAIN;新安装继续既有生命周期。
        if phase != "prepared":
            raw_state = self._read(self.paths.journal)
            try:
                state = json.loads(raw_state)
            except ValueError:
                raise ValueError("failed_preparation_main") from None
            if (
                not isinstance(state, dict)
                or json_bytes(state) != raw_state
                or state.get("phase") != "installed"
                or [state.get("payload"), state.get("manifest")]
                != list(self.descriptor.upgrade_from)
            ):
                raise ValueError("failed_preparation_main")
            identity = {
                "format_version": 2,
                "payload": self._identity()["payload"],
                "manifest": self._identity()["manifest"],
                "upgrade_from": list(self.descriptor.upgrade_from),
            }
            verify_installed_upgrade(
                self.staged,
                paths=self.paths,
                state=state,
                identity=identity,
                owner_uid=self.owner_uid,
            )
            verify_tree(
                self.paths.runtime,
                owner_uid=self.owner_uid,
                anchor=self.paths.anchor,
                payload=state["payload"],
                manifest_digest=state["manifest"],
            )
            if read_placement_policy(self.paths.runtime) is not None:
                raise ValueError("failed_preparation_main_placement")
            from datetime import UTC, datetime

            from paper_radar.live_evidence.collection import ProtectedCollection
            from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
            from paper_radar.live_evidence.model_manifest import parse_manifest

            ledger = EvidenceLedger(
                self.paths.ledger,
                trust=LedgerTrust(owner_uid=self.owner_uid, anchor=self.paths.anchor),
            )
            manifest = parse_manifest(
                (self.paths.runtime / "model-manifest.json").read_bytes()
            )
            now = datetime.now(UTC)
            if ProtectedCollection(ledger).is_stopped() or _historical_refresh_stopped(
                ledger, manifest, now=now
            ):
                raise ValueError("failed_preparation_stopped")
        return old, new, phase

    def check(self, *, recover: bool = False) -> bool:
        """True表示本轮退役负责冲突核验;False沿用原正常生命周期。"""
        if self.descriptor is None:
            return False
        old, new, phase = self._authenticate()
        old_phases = (
            {"preparing"}
            if phase in {None, "intent", "snapshotted"}
            else {"preparing", "removing", "removed"}
            if phase == "removing"
            else {"removed"}
        )
        new_phases = (
            {"preparing", "prepared", "removing", "removed"}
            if phase == "prepared"
            else {"preparing", "prepared"}
            if phase == "preparing"
            else set()
        )
        # 旧生命周期保留历史解析语义;本接缝先按退休阶段认证完整规范字节。
        self._policy_marker(old, old_phases, "failed_preparation_marker")
        self._policy_marker(
            new,
            {"preparing"}
            if self.recovery is not None and not os.path.lexists(self.journal)
            else new_phases,
            "failed_preparation_new_marker",
            missing_allowed=self.recovery is None and phase != "prepared",
        )
        if phase == "prepared":
            return False
        if phase is not None and not recover:
            raise ValueError("failed_preparation_recovery_required")
        # 新宿主依赖必须先于旧策略退役核验;不加载、不更新记录。
        assert new.sealed is not None and old.sealed is not None
        verify_host_security(new.sealed)
        if phase in {None, "intent", "snapshotted"}:
            if self._read(old.journal) != original_marker(self.descriptor):
                raise ValueError("failed_preparation_marker")
            if old.check() != "exact":
                raise ValueError("failed_preparation_policy_missing")
            if os.path.lexists(new.journal):
                raise ValueError("failed_preparation_new_marker")
        elif phase == "removing":
            old.check(recover=True)
        elif self.recovery is not None:
            # 同完整身份桥接不需要kernel写;缺失/partial不能借恢复权重新加载。
            if new.check() != "exact":
                raise ValueError("preparation_recovery_policy_missing")
        else:
            new.check(recover=True)
        return True

    def _policy_marker(
        self,
        lifecycle: PlacementPolicyLifecycle,
        phases: set[str],
        reason: str,
        *,
        missing_allowed: bool = False,
    ) -> None:
        if missing_allowed and not os.path.lexists(lifecycle.journal):
            return
        raw = self._read(lifecycle.journal)
        assert lifecycle.sealed is not None
        try:
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError
            phase = value.get("phase")
            if (
                not isinstance(phase, str)
                or phase not in phases
                or raw
                != json_bytes(
                    {
                        "format_version": 1,
                        "identity": lifecycle.sealed.identity,
                        "phase": phase,
                    }
                )
            ):
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError(reason) from None

    def prepare(
        self,
        preflight: Callable[[], None],
        check_idle: Callable[[], None],
        *,
        recover: bool = False,
    ) -> bool:
        if not self.check(recover=recover):
            return False
        assert self.descriptor is not None
        old, new, phase = self._authenticate()
        check_idle()  # 仅实际进程/项目scope只读检查,不停止或trace。
        # idle观察后再次认证所有来源和kernel,再开始有限root写入。
        self.check(recover=recover)
        if self.recovery is not None:
            if not os.path.lexists(self.journal):
                self._record("preparing")
            new.prepare(preflight, recover=True)
            self._record("prepared")
            return True
        if phase is None:
            self._record("intent")
            phase = "intent"
        if phase == "intent":
            if not os.path.lexists(self.snapshot):
                publish(self.snapshot, original_marker(self.descriptor))
            if self._read(self.snapshot) != original_marker(self.descriptor):
                raise ValueError("failed_preparation_snapshot")
            self._record("snapshotted")
            phase = "snapshotted"
        if phase == "snapshotted":
            self._record("removing")
            phase = "removing"
        if phase == "removing":
            old.remove(recover=True)
            self._record("removed")
            phase = "removed"
        if phase == "removed":
            self._record("preparing")
        new.prepare(preflight, recover=recover)
        self._record("prepared")
        return True
