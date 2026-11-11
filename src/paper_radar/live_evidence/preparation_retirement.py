"""仅退役已认证、从未安装的失败放置准备;不替换已安装策略或业务状态。"""

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
    json_bytes,
    protected,
    publish,
    verify_tree,
)
from paper_radar.live_evidence.placement_policy import (
    MEMBERS,
    PlacementPolicyLifecycle,
    read_placement_policy,
    verify_host_security,
)
from paper_radar.live_evidence.receipt import Digest, WireModel

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
    if (
        old_spec.get("failed_preparation") is not None
        or old_spec.get("epoch_upgrade") != new_spec.get("epoch_upgrade")
        or old_spec.get("upgrade_from") != list(pair)
        or new_spec.get("upgrade_from") != list(pair)
        or continuity_identity(old) != continuity_identity(new)
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
            phase = value.pop("phase")
            if (
                phase not in _PHASES
                or value != self._identity()
                or json_bytes({**value, "phase": phase}) != raw
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
                kernel=AppArmorKernel(self.io, new_policy.parser),
            ),
        )

    def _authenticate(
        self,
    ) -> tuple[PlacementPolicyLifecycle, PlacementPolicyLifecycle, str | None]:
        assert self.descriptor is not None
        old, new = self._lifecycles()
        for root, payload, manifest in (
            (
                old.root,
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
        if describe_failed_preparation(old.root, self.staged) != self.descriptor:
            raise ValueError("failed_preparation_source")
        for path in (self.journal, self.snapshot, old.journal, new.journal):
            if os.path.lexists(path.with_name(path.name + ".new")):
                raise ValueError("failed_preparation_pending_file")
        if any(
            path != self.journal
            for path in self.paths.ledger.glob("placement-retirement-v1-*.json")
        ):
            raise ValueError("failed_preparation_journal_conflict")
        phase = self._phase()
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
            state = json.loads(raw_state)
            if (
                json_bytes(state) != raw_state
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
            from paper_radar.live_evidence.normal_auth_refresh import (
                normal_review_path,
                review_normal_refresh,
            )

            ledger = EvidenceLedger(
                self.paths.ledger,
                trust=LedgerTrust(owner_uid=self.owner_uid, anchor=self.paths.anchor),
            )
            manifest = parse_manifest(
                (self.paths.runtime / "model-manifest.json").read_bytes()
            )
            now = datetime.now(UTC)
            if ProtectedCollection(ledger).status(
                manifest.cells[0].plan.plan_id, now=now
            ).stopped or (
                os.path.lexists(normal_review_path(ledger, manifest))
                and review_normal_refresh(ledger, manifest, now=now).stopped
            ):
                raise ValueError("failed_preparation_stopped")
        return old, new, phase

    def check(self, *, recover: bool = False) -> bool:
        """True表示本轮退役负责冲突核验;False沿用原正常生命周期。"""
        if self.descriptor is None:
            return False
        old, new, phase = self._authenticate()
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
            if old.phase() not in {"preparing", "removing", "removed"}:
                raise ValueError("failed_preparation_marker")
            old.check(recover=True)
        else:
            if old.phase() != "removed":
                raise ValueError("failed_preparation_marker")
            new.check(recover=True)
        return True

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
