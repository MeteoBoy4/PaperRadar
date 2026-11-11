"""受保护Live部署状态机;只核已知字节,不清理未知状态/历史/额度。"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
from paper_radar.live_evidence.model_manifest import ModelManifest, parse_manifest
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration


class LiveHost(Protocol):
    def preflight(self, site: SiteConfiguration) -> None: ...
    def ensure_no_table(self) -> None: ...
    def preflight_nft(
        self, site: SiteConfiguration, manifest: ModelManifest
    ) -> None: ...
    def validate_sudoers(self, path: Path) -> None: ...
    def configure(self, site: SiteConfiguration, manifest: ModelManifest) -> None: ...
    def verify_installed(
        self, site: SiteConfiguration, manifest: ModelManifest
    ) -> None: ...
    def initialize_plans(
        self, root: Path, site: SiteConfiguration, manifest: ModelManifest
    ) -> None: ...
    def disable_observation(self) -> None: ...
    def prepare_recovery(
        self, site: SiteConfiguration, manifest: ModelManifest
    ) -> None: ...
    def check_resources_interruption(
        self,
        site: SiteConfiguration,
        manifest: ModelManifest,
        *,
        allow_stopped: bool = False,
    ) -> None: ...
    def stop_resources_anchor(
        self, site: SiteConfiguration, manifest: ModelManifest
    ) -> None: ...
    def verify_resources_stopped(self, site: SiteConfiguration) -> None: ...
    def stop_and_remove(self) -> None: ...
    def verify_absent(self) -> None: ...


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def protected(path: Path, owner_uid: int, *, anchor: Path = Path("/")) -> None:
    if not path.is_absolute() or not path.is_relative_to(anchor):
        raise ValueError("protected_path")
    for current in (path, *path.parents):
        info = current.lstat()
        if (
            stat.S_ISLNK(info.st_mode)
            or info.st_uid != owner_uid
            or info.st_mode & 0o022
        ):
            raise ValueError("protected_identity")
        if current == anchor:
            return
    raise ValueError("protected_path")


def verify_tree(
    root: Path,
    *,
    owner_uid: int,
    anchor: Path = Path("/"),
    payload: str | None = None,
    manifest_digest: str | None = None,
) -> None:
    protected(root, owner_uid, anchor=anchor)
    manifest = root / "manifest.sha256"
    protected(manifest, owner_uid, anchor=anchor)
    info = manifest.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_size > 4 * 1024 * 1024
    ):
        raise ValueError("runtime_manifest_invalid")
    raw = manifest.read_bytes()
    if manifest_digest is not None and digest(raw) != manifest_digest:
        raise ValueError("runtime_manifest_identity")
    expected = {}
    for line in raw.decode("ascii").splitlines():
        sha, name = line.split("  ", 1)
        if (
            len(sha) != 64
            or any(c not in "0123456789abcdef" for c in sha)
            or name in expected
            or PurePosixPath(name).is_absolute()
            or ".." in PurePosixPath(name).parts
        ):
            raise ValueError("runtime_manifest_invalid")
        expected[name] = sha
    expected["manifest.sha256"] = digest(raw)
    if payload is not None:
        expected["payload.sha256"] = digest((payload + "\n").encode())
    directories = {
        str(parent)
        for name in expected
        for parent in PurePosixPath(name).parents
        if str(parent) != "."
    }
    actual = set()
    actual_directories = set()
    for path in root.rglob("*"):
        protected(path, owner_uid, anchor=anchor)
        info = path.lstat()
        name = path.relative_to(root).as_posix()
        if stat.S_ISDIR(info.st_mode):
            if stat.S_IMODE(info.st_mode) != 0o755:
                raise ValueError("runtime_member_mode")
            actual_directories.add(name)
        elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
            if stat.S_IMODE(info.st_mode) not in {0o644, 0o755}:
                raise ValueError("runtime_member_mode")
            actual.add(name)
            if name not in expected or digest(path.read_bytes()) != expected[name]:
                raise ValueError("runtime_member_identity")
        else:
            raise ValueError("runtime_member_type")
    if actual != set(expected) or actual_directories != directories:
        raise ValueError("runtime_inventory")


def publish(
    path: Path, data: bytes, *, replace: bool = False, mode: int = 0o644
) -> None:
    temporary = path.with_name(path.name + ".new")
    descriptor = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode
    )
    os.fchmod(descriptor, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if replace:
        os.replace(temporary, path)
    else:
        os.link(temporary, path, follow_symlinks=False)
        temporary.unlink()
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@dataclass(frozen=True)
class InstallationPaths:
    runtime: Path = Path("/usr/libexec/paperradar/live-evidence-runtime")
    ledger: Path = Path("/var/lib/paperradar/live-evidence")
    executables: Path = Path("/usr/libexec/paperradar")
    sudoers: Path = Path("/etc/sudoers.d/paperradar-live-evidence")
    units: Path = Path("/etc/systemd/user")
    resolver: Path = Path("/run/paper-radar/resolv.conf")
    anchor: Path = Path("/")

    @property
    def journal(self) -> Path:
        return self.ledger / "deployment-v2.json"

    @classmethod
    def for_model(cls, root: Path) -> InstallationPaths:
        defaults = cls()
        return cls(
            runtime=root / defaults.runtime.relative_to("/"),
            ledger=root / defaults.ledger.relative_to("/"),
            executables=root / defaults.executables.relative_to("/"),
            sudoers=root / defaults.sudoers.relative_to("/"),
            units=root / defaults.units.relative_to("/"),
            resolver=root / defaults.resolver.relative_to("/"),
            anchor=root,
        )


class LiveDeployment:
    def __init__(
        self,
        staged: Path,
        *,
        paths: InstallationPaths,
        host: LiveHost | None,
        owner_uid: int = 0,
    ) -> None:
        self.staged, self.paths, self.host, self.owner_uid = (
            staged,
            paths,
            host,
            owner_uid,
        )

    def preflight_existing(self, upgrade_from: tuple[str, str] | None) -> None:
        runtime = self.paths.runtime
        if not os.path.lexists(runtime):
            return
        if upgrade_from is None:
            raise ValueError("runtime_identity_unknown")
        verify_tree(
            runtime,
            owner_uid=self.owner_uid,
            anchor=self.paths.anchor,
            payload=upgrade_from[0],
            manifest_digest=upgrade_from[1],
        )

    def _read_journal(self) -> dict[str, Any] | None:
        if not os.path.lexists(self.paths.journal):
            return None
        protected(self.paths.journal, self.owner_uid, anchor=self.paths.anchor)
        info = self.paths.journal.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 65536:
            raise ValueError("deployment_journal_invalid")
        raw = self.paths.journal.read_bytes()
        value = json.loads(raw)
        if (
            json_bytes(value) != raw
            or set(value)
            != {
                "format_version",
                "payload",
                "manifest",
                "phase",
                "upgrade_from",
                "previous",
            }
            or value["format_version"] != 2
        ):
            raise ValueError("deployment_journal_invalid")
        if not isinstance(value, dict):
            raise ValueError("deployment_journal_invalid")
        return value

    def _checkpoint(self, state: dict[str, Any], phase: str) -> None:
        state["phase"] = phase
        publish(
            self.paths.journal, json_bytes(state), replace=self.paths.journal.exists()
        )

    def _resources(self) -> dict[Path, bytes]:
        result = {
            self.paths.executables / ("live-evidence-" + name): (
                self.staged / "wrappers" / name
            ).read_bytes()
            for name in ("collect", "tighten", "owner", "refresh", "model-collect")
        }
        result[self.paths.sudoers] = (self.staged / "sudoers").read_bytes()
        for name in ("paperradar.slice", "paperradar-anchor.service"):
            result[self.paths.units / name] = (
                self.staged / "resources" / name
            ).read_bytes()
        result[self.paths.resolver] = (
            self.staged / "resources/resolv.conf"
        ).read_bytes()
        return result

    def _check_resources(self, *, absent_ok: bool = False) -> None:
        for path, raw in self._resources().items():
            if not os.path.lexists(path) and absent_ok:
                continue
            protected(path, self.owner_uid, anchor=self.paths.anchor)
            info = path.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or path.read_bytes() != raw
                or stat.S_IMODE(info.st_mode)
                != (
                    0o440
                    if path == self.paths.sudoers
                    else 0o755
                    if path.parent == self.paths.executables
                    else 0o644
                )
            ):
                raise ValueError("deployment_resource_identity")

    def _unexecuted_resources(self, roots: tuple[Path, ...]) -> None:
        """只读旧新计划的缺史证明;不初始化/升级账本,不否定其他历史。"""
        from paper_radar.live_evidence.collection import ProtectedCollection
        from paper_radar.live_evidence.normal_auth_refresh import epoch_path
        from paper_radar.live_evidence.receipt import ApprovedPlan

        ledger = EvidenceLedger(
            self.paths.ledger,
            trust=LedgerTrust(owner_uid=self.owner_uid, anchor=self.paths.anchor),
        )
        ids: set[str] = set()
        collectors: set[str] = set()
        for root in roots:
            manifest = parse_manifest((root / "model-manifest.json").read_bytes())
            strict = ApprovedPlan.model_validate_json((root / "plan.json").read_bytes())
            collectors.update((manifest.collector_sha256, strict.collector_sha256))
            ids.update(
                (
                    strict.plan_id,
                    manifest.site_plan_id,
                    *(cell.plan.plan_id for cell in manifest.cells),
                    manifest.negative_plan.plan_id,
                )
            )
            if os.path.lexists(epoch_path(ledger, manifest)):
                raise ValueError("resources_execution_history")
        if os.path.lexists(self.paths.ledger / "inbox/placement-target-v1.json"):
            raise ValueError("resources_target_present")
        # 封印writer总在执行前发布计划来源;同计划任何残留均不猜测。
        for directory in (self.paths.ledger, self.paths.ledger / "inbox"):
            protected(directory, self.owner_uid, anchor=self.paths.anchor)
            if any(
                any(identifier in entry.name for identifier in ids)
                for entry in directory.iterdir()
            ):
                raise ValueError("resources_execution_history")
        if os.path.lexists(ledger.database):
            with ledger.connection() as connection:
                for identifier in ids:
                    if any(
                        connection.execute(query, (identifier,)).fetchone()
                        for query in (
                            "SELECT 1 FROM plans WHERE plan_id=?",
                            "SELECT 1 FROM receipts WHERE plan_id=?",
                            "SELECT 1 FROM events WHERE subject_id=?",
                        )
                    ):
                        raise ValueError("resources_execution_history")
                for (raw,) in connection.execute(
                    "SELECT payload FROM plans UNION ALL SELECT payload FROM receipts"
                ):
                    value = json.loads(raw)
                    if not isinstance(value, dict):
                        raise ValueError("resources_ledger_unknown")
                    if value.get("collector_sha256") in collectors:
                        raise ValueError("resources_execution_history")
                version = connection.execute("PRAGMA user_version").fetchone()
                if version == (1,) and (
                    {
                        row[0]
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        )
                    }
                    != {"plans", "receipts", "events"}
                    or connection.execute(
                        "SELECT 1 FROM events WHERE action LIKE 'collection_%' "
                        "OR action LIKE 'history_collection_%' LIMIT 1"
                    ).fetchone()
                ):
                    raise ValueError("resources_ledger_unknown")
            if version == (2,) and ProtectedCollection(ledger).has_plan_history(
                frozenset(ids)
            ):
                raise ValueError("resources_execution_history")
        for source in (self.paths.ledger / "inbox").glob("*.json"):
            value = json.loads(ledger._read_source(source))
            if not isinstance(value, dict):
                raise ValueError("resources_ledger_unknown")
            if value.get("collector_sha256") in collectors:
                raise ValueError("resources_execution_history")
        observation = self.paths.ledger / "inbox/current-observation.json"
        if os.path.lexists(observation):
            from datetime import UTC, datetime

            from paper_radar.live_evidence.observation import read_observation_snapshot
            from paper_radar.live_evidence.protected_observer import observer_identity
            from paper_radar.live_evidence.types import BindingComponent

            current = read_observation_snapshot(ledger, now=datetime.now(UTC))
            if current.binding[BindingComponent.OBSERVER] in {
                observer_identity(root, ledger) for root in roots
            }:
                raise ValueError("resources_execution_history")

    def _pending_resources(
        self, old: dict[str, Any], root: Path, *, absent_ok: bool = False
    ) -> LiveDeployment:
        # 每层是既有 root 发布的 resources journal;只接受有限、无重复的完整链。
        # previous 非空从不单独成为授权。
        # pair、封印声明、原 history 与 archive 必须一致。
        current: object = old
        selected = root
        roots: list[Path] = []
        seen: set[str] = set()
        for _depth in range(16):
            if (
                not isinstance(current, dict)
                or set(current)
                != {
                    "format_version",
                    "payload",
                    "manifest",
                    "phase",
                    "upgrade_from",
                    "previous",
                }
                or type(current["format_version"]) is not int
                or current["format_version"] != 2
                or current["phase"] != "resources"
            ):
                raise ValueError("resources_interruption_unknown")
            pair = [current["payload"], current["manifest"]]
            legacy = current["upgrade_from"]
            if any(
                not isinstance(value, str)
                or len(value) != 64
                or any(char not in "0123456789abcdef" for char in value)
                for value in pair
            ):
                raise ValueError("resources_interruption_unknown")
            if current["payload"] in seen:
                raise ValueError("resources_interruption_unknown")
            seen.add(current["payload"])
            if (
                not isinstance(legacy, list)
                or len(legacy) != 2
                or any(
                    not isinstance(value, str)
                    or len(value) != 64
                    or any(char not in "0123456789abcdef" for char in value)
                    for value in legacy
                )
                or legacy[0] in seen
            ):
                raise ValueError("resources_legacy_identity")
            verify_tree(
                selected,
                owner_uid=self.owner_uid,
                anchor=self.paths.anchor,
                payload=pair[0],
                manifest_digest=pair[1],
            )
            if (
                json.loads((selected / "deployment.json").read_bytes()).get(
                    "upgrade_from"
                )
                != legacy
            ):
                raise ValueError("resources_interruption_unknown")
            roots.append(selected)
            archive = self.paths.runtime.with_name(
                self.paths.runtime.name + ".archive-" + legacy[0]
            )
            verify_tree(
                archive,
                owner_uid=self.owner_uid,
                anchor=self.paths.anchor,
                payload=legacy[0],
                manifest_digest=legacy[1],
            )
            ancestor = current["previous"]
            if ancestor is None:
                break
            if not isinstance(ancestor, dict) or legacy != [
                ancestor.get("payload"),
                ancestor.get("manifest"),
            ]:
                raise ValueError("resources_interruption_unknown")
            history = self.paths.journal.with_name(
                "deployment-v2-history-" + legacy[0] + ".json"
            )
            if not os.path.lexists(history):
                raise ValueError("resources_history_identity")
            protected(history, self.owner_uid, anchor=self.paths.anchor)
            info = history.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_size > 65536
                or history.read_bytes() != json_bytes(ancestor)
            ):
                raise ValueError("resources_history_identity")
            current, selected = ancestor, archive
        else:
            raise ValueError("resources_interruption_unknown")
        previous = LiveDeployment(
            root, paths=self.paths, host=self.host, owner_uid=self.owner_uid
        )
        previous._check_resources(absent_ok=absent_ok)
        self._unexecuted_resources((*roots, self.staged))
        return previous

    def _replace_resources(self, state: dict[str, Any]) -> None:
        host = self.host
        if host is None:
            raise ValueError("host_unavailable")
        old = state["previous"]
        if not isinstance(old, dict) or state["upgrade_from"] != [
            old["payload"],
            old["manifest"],
        ]:
            raise ValueError("resources_interruption_unknown")
        history = self.paths.journal.with_name(
            "deployment-v2-history-" + old["payload"] + ".json"
        )
        protected(history, self.owner_uid, anchor=self.paths.anchor)
        if (
            not stat.S_ISREG(history.lstat().st_mode)
            or history.lstat().st_nlink != 1
            or history.read_bytes() != json_bytes(old)
        ):
            raise ValueError("resources_history_identity")
        archive = self.paths.runtime.with_name(
            self.paths.runtime.name + ".archive-" + old["payload"]
        )
        root = self.paths.runtime if os.path.lexists(self.paths.runtime) else archive
        previous = self._pending_resources(
            old, root, absent_ok=state["phase"] == "resources_stopped"
        )
        site = SiteConfiguration.model_validate_json((root / "site.json").read_bytes())
        manifest = parse_manifest((root / "model-manifest.json").read_bytes())
        if state["phase"] == "replacing_resources":
            if root != self.paths.runtime or os.path.lexists(archive):
                raise ValueError("archive_conflict")
            host.check_resources_interruption(site, manifest, allow_stopped=True)
            host.disable_observation()
            host.stop_resources_anchor(site, manifest)
            self._checkpoint(state, "resources_stopped")
        host.verify_resources_stopped(site)
        previous._check_resources(absent_ok=True)
        for path in previous._resources():
            path.unlink(missing_ok=True)
        if root == self.paths.runtime:
            if os.path.lexists(archive):
                raise ValueError("archive_conflict")
            root.rename(archive)
        verify_tree(
            archive,
            owner_uid=self.owner_uid,
            anchor=self.paths.anchor,
            payload=old["payload"],
            manifest_digest=old["manifest"],
        )
        self._checkpoint(state, "archived")

    def install(self, *, recover: bool = False) -> str:
        from paper_radar.live_evidence.sealed_runtime import SiteConfiguration

        host = self.host
        if host is None:
            raise ValueError("host_unavailable")
        payload = (self.staged / "payload.sha256").read_text().strip()
        verify_tree(
            self.staged,
            owner_uid=self.owner_uid,
            anchor=self.paths.anchor,
            payload=payload,
        )
        specification = json.loads((self.staged / "deployment.json").read_bytes())
        site = SiteConfiguration.model_validate_json(
            (self.staged / "site.json").read_bytes()
        )
        manifest = parse_manifest((self.staged / "model-manifest.json").read_bytes())
        confirmation = json.loads(
            (self.staged / "network-owner-confirmation.json").read_bytes()
        )
        if any(
            confirmation["owner_input"].get(field) is not True
            for field in ("owner_window_confirmed", "owner_network_applicable")
        ):
            raise ValueError("owner_confirmation_pending")
        from datetime import UTC, datetime

        if (
            not manifest.network.starts_at
            <= datetime.now(UTC)
            <= manifest.network.ends_at
        ):
            raise ValueError("plan_window_invalid")
        upgrade = (
            tuple(specification["upgrade_from"])
            if specification["upgrade_from"]
            else None
        )
        state = self._read_journal()
        identity = {
            "format_version": 2,
            "payload": payload,
            "manifest": digest((self.staged / "manifest.sha256").read_bytes()),
            "phase": "prepared",
            "upgrade_from": specification["upgrade_from"],
            "previous": None,
        }
        if state is not None:
            if any(
                state[key] != identity[key]
                for key in ("format_version", "payload", "manifest", "upgrade_from")
            ):
                if (
                    recover
                    and state["phase"] == "resources"
                    and upgrade == (state["payload"], state["manifest"])
                ):
                    self._pending_resources(state, self.paths.runtime)
                    old_site = SiteConfiguration.model_validate_json(
                        (self.paths.runtime / "site.json").read_bytes()
                    )
                    old_manifest = parse_manifest(
                        (self.paths.runtime / "model-manifest.json").read_bytes()
                    )
                    host.preflight(site)
                    host.check_resources_interruption(old_site, old_manifest)
                    host.preflight_nft(site, manifest)
                    archive = self.paths.runtime.with_name(
                        self.paths.runtime.name + ".archive-" + state["payload"]
                    )
                    if os.path.lexists(archive):
                        raise ValueError("archive_conflict")
                    history = self.paths.journal.with_name(
                        "deployment-v2-history-" + state["payload"] + ".json"
                    )
                    if os.path.lexists(history):
                        protected(history, self.owner_uid, anchor=self.paths.anchor)
                        if (
                            not stat.S_ISREG(history.lstat().st_mode)
                            or history.lstat().st_nlink != 1
                            or history.read_bytes() != json_bytes(state)
                        ):
                            raise ValueError("resources_history_identity")
                    else:
                        publish(history, json_bytes(state))
                    identity["previous"] = state
                    state = identity
                    self._checkpoint(state, "replacing_resources")
                elif state["phase"] != "installed" or upgrade != (
                    state["payload"],
                    state["manifest"],
                ):
                    raise ValueError("deployment_identity_conflict")
                if state["phase"] == "installed":
                    verify_tree(
                        self.paths.runtime,
                        owner_uid=self.owner_uid,
                        anchor=self.paths.anchor,
                        payload=state["payload"],
                        manifest_digest=state["manifest"],
                    )
                    previous = LiveDeployment(
                        self.paths.runtime,
                        paths=self.paths,
                        host=host,
                        owner_uid=self.owner_uid,
                    )
                    previous._check_resources()
                    old_site = SiteConfiguration.model_validate_json(
                        (self.paths.runtime / "site.json").read_bytes()
                    )
                    old_manifest = parse_manifest(
                        (self.paths.runtime / "model-manifest.json").read_bytes()
                    )
                    host.preflight(site)
                    host.verify_installed(old_site, old_manifest)
                    archive = self.paths.runtime.with_name(
                        self.paths.runtime.name + ".archive-" + state["payload"]
                    )
                    history = self.paths.journal.with_name(
                        "deployment-v2-history-" + state["payload"] + ".json"
                    )
                    if os.path.lexists(archive) or os.path.lexists(history):
                        raise ValueError("archive_conflict")
                    publish(history, json_bytes(state))
                    identity["previous"] = state
                    state = identity
                    self._checkpoint(state, "retiring")
            if state["phase"] in {"installed", "uninstalled"}:
                from paper_radar.live_evidence.model_manifest import ModelManifestV2
                from paper_radar.live_evidence.normal_auth_refresh import read_epoch

                if isinstance(manifest, ModelManifestV2):
                    read_epoch(
                        EvidenceLedger(
                            self.paths.ledger,
                            trust=LedgerTrust(
                                owner_uid=self.owner_uid, anchor=self.paths.anchor
                            ),
                        ),
                        manifest,
                    )
            if state["phase"] == "installed":
                verify_tree(
                    self.paths.runtime,
                    owner_uid=self.owner_uid,
                    anchor=self.paths.anchor,
                    payload=payload,
                )
                if recover:
                    self._check_resources(absent_ok=True)
                    host.preflight(site)
                    host.prepare_recovery(site, manifest)
                    self._checkpoint(state, "runtime")
                else:
                    self._check_resources()
                    host.preflight(site)
                    host.verify_installed(site, manifest)
                    return "already_installed"
            if state["phase"] == "uninstalled" and not recover:
                raise ValueError("explicit_recovery_required")
            if state["phase"] not in {
                "prepared",
                "archived",
                "runtime",
                "resources",
                "target",
                "installed",
                "uninstalled",
                "retiring",
                "replacing_resources",
                "resources_stopped",
            }:
                raise ValueError("deployment_interruption_unknown")
        else:
            self.preflight_existing(upgrade)
            legacy_archive = (
                self.paths.runtime.with_name(
                    self.paths.runtime.name + ".archive-" + upgrade[0]
                )
                if upgrade
                else None
            )
            if legacy_archive is not None and os.path.lexists(legacy_archive):
                raise ValueError("archive_conflict")
            host.preflight(site)
            # 旧入口也必须逐字对应旧runtime,不把普通用户文件提升为root信任。
            if upgrade:
                for name in ("collect", "tighten", "owner"):
                    path = self.paths.executables / ("live-evidence-" + name)
                    protected(path, self.owner_uid, anchor=self.paths.anchor)
                    info = path.lstat()
                    if (
                        not stat.S_ISREG(info.st_mode)
                        or info.st_nlink != 1
                        or stat.S_IMODE(info.st_mode) != 0o755
                        or path.read_bytes()
                        != (self.paths.runtime / "wrappers" / name).read_bytes()
                    ):
                        raise ValueError("legacy_entry_identity")
                protected(self.paths.sudoers, self.owner_uid, anchor=self.paths.anchor)
                info = self.paths.sudoers.lstat()
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1
                    or stat.S_IMODE(info.st_mode) != 0o440
                    or self.paths.sudoers.read_bytes()
                    != (self.paths.runtime / "sudoers").read_bytes()
                ):
                    raise ValueError("legacy_entry_identity")
            else:
                self._check_resources(absent_ok=True)
            host.ensure_no_table()
            for path in (self.paths.ledger, self.paths.ledger / "inbox"):
                if path.exists():
                    protected(path, self.owner_uid, anchor=self.paths.anchor)
                else:
                    path.mkdir(mode=0o755, parents=True)
                    protected(path, self.owner_uid, anchor=self.paths.anchor)
            state = identity
            self._checkpoint(state, "prepared")
        host.preflight(site)
        if state["phase"] in {"replacing_resources", "resources_stopped"}:
            self._replace_resources(state)
        if state["phase"] == "retiring":
            old_state = state["previous"]
            archive = self.paths.runtime.with_name(
                self.paths.runtime.name + ".archive-" + old_state["payload"]
            )
            if os.path.lexists(self.paths.runtime):
                verify_tree(
                    self.paths.runtime,
                    owner_uid=self.owner_uid,
                    anchor=self.paths.anchor,
                    payload=old_state["payload"],
                    manifest_digest=old_state["manifest"],
                )
                previous = LiveDeployment(
                    self.paths.runtime,
                    paths=self.paths,
                    host=host,
                    owner_uid=self.owner_uid,
                )
                previous._check_resources(absent_ok=True)
                host.disable_observation()
                host.stop_and_remove()
                for path in previous._resources():
                    path.unlink(missing_ok=True)
                if os.path.lexists(archive):
                    raise ValueError("archive_conflict")
                self.paths.runtime.rename(archive)
            verify_tree(
                archive,
                owner_uid=self.owner_uid,
                anchor=self.paths.anchor,
                payload=old_state["payload"],
                manifest_digest=old_state["manifest"],
            )
            self._checkpoint(state, "archived")
        if state["phase"] == "uninstalled":
            self._checkpoint(state, "archived")
        if state["phase"] == "prepared":
            if upgrade:
                archive = self.paths.runtime.with_name(
                    self.paths.runtime.name + ".archive-" + upgrade[0]
                )
                if os.path.lexists(self.paths.runtime):
                    self.preflight_existing(upgrade)
                    if os.path.lexists(archive):
                        raise ValueError("archive_conflict")
                    # 先关闭旧dispatch,逐个缺失只在已记录prepared恢复允许。
                    for name in ("collect", "tighten", "owner"):
                        path = self.paths.executables / ("live-evidence-" + name)
                        if path.exists():
                            if (
                                path.read_bytes()
                                != (self.paths.runtime / "wrappers" / name).read_bytes()
                            ):
                                raise ValueError("legacy_entry_identity")
                            path.unlink()
                    if self.paths.sudoers.exists():
                        if (
                            self.paths.sudoers.read_bytes()
                            != (self.paths.runtime / "sudoers").read_bytes()
                        ):
                            raise ValueError("legacy_entry_identity")
                        self.paths.sudoers.unlink()
                    self.paths.runtime.rename(archive)
                verify_tree(
                    archive,
                    owner_uid=self.owner_uid,
                    anchor=self.paths.anchor,
                    payload=upgrade[0],
                    manifest_digest=upgrade[1],
                )
            self._checkpoint(state, "archived")
        if state["phase"] == "archived":
            protected(
                self.paths.runtime.parent, self.owner_uid, anchor=self.paths.anchor
            )
            if not os.path.lexists(self.paths.runtime):
                pending = self.paths.runtime.with_name(self.paths.runtime.name + ".new")
                if os.path.lexists(pending):
                    # 只允许完整已核封印副本续行;部分复制不猜测/删除。
                    verify_tree(
                        pending,
                        owner_uid=self.owner_uid,
                        anchor=self.paths.anchor,
                        payload=payload,
                    )
                else:
                    shutil.copytree(self.staged, pending)
                    verify_tree(
                        pending,
                        owner_uid=self.owner_uid,
                        anchor=self.paths.anchor,
                        payload=payload,
                    )
                pending.rename(self.paths.runtime)
            verify_tree(
                self.paths.runtime,
                owner_uid=self.owner_uid,
                anchor=self.paths.anchor,
                payload=payload,
            )
            self._checkpoint(state, "runtime")
        if state["phase"] == "runtime":
            self._check_resources(absent_ok=True)
            for path, raw in self._resources().items():
                if not path.exists():
                    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                    protected(path.parent, self.owner_uid, anchor=self.paths.anchor)
                    mode = (
                        0o440
                        if path == self.paths.sudoers
                        else 0o755
                        if path.parent == self.paths.executables
                        else 0o644
                    )
                    publish(path, raw, mode=mode)
            host.validate_sudoers(self.paths.sudoers)
            self._checkpoint(state, "resources")
        if state["phase"] == "resources":
            self._check_resources()
            host.configure(site, manifest)
            self._checkpoint(state, "target")
        if state["phase"] == "target":
            host.verify_installed(site, manifest)
            host.initialize_plans(self.paths.runtime, site, manifest)
            from paper_radar.live_evidence.normal_auth_refresh import initialize_epoch

            initialize_epoch(
                EvidenceLedger(
                    self.paths.ledger,
                    trust=LedgerTrust(
                        owner_uid=self.owner_uid, anchor=self.paths.anchor
                    ),
                ),
                manifest,
                now=datetime.now(UTC),
            )
            self._checkpoint(state, "installed")
        return "installed"

    def uninstall(self) -> str:
        host = self.host
        state = self._read_journal()
        if state is None or host is None:
            raise ValueError("deployment_identity_unknown")
        if state["phase"] == "uninstalled":
            if os.path.lexists(self.paths.runtime) or any(
                os.path.lexists(path) for path in self._resources()
            ):
                raise ValueError("uninstalled_resource_conflict")
            host.verify_absent()
            return "already_uninstalled"
        if state["phase"] not in {
            "installed",
            "uninstalling",
            "disabled",
            "host_removed",
        }:
            raise ValueError("deployment_interruption_unknown")
        verify_tree(
            self.staged,
            owner_uid=self.owner_uid,
            anchor=self.paths.anchor,
            payload=state["payload"],
        )
        if state["phase"] == "installed":
            verify_tree(
                self.paths.runtime,
                owner_uid=self.owner_uid,
                anchor=self.paths.anchor,
                payload=state["payload"],
            )
            self._check_resources()
            self._checkpoint(state, "uninstalling")
        if state["phase"] == "uninstalling":
            host.disable_observation()
            for name in ("collect", "refresh", "model-collect"):
                path = self.paths.executables / ("live-evidence-" + name)
                if path.exists():
                    if path.read_bytes() != self._resources()[path]:
                        raise ValueError("deployment_resource_identity")
                    path.unlink()
            if self.paths.sudoers.exists():
                if (
                    self.paths.sudoers.read_bytes()
                    != self._resources()[self.paths.sudoers]
                ):
                    raise ValueError("deployment_resource_identity")
                self.paths.sudoers.unlink()
            self._checkpoint(state, "disabled")
        if state["phase"] == "disabled":
            host.stop_and_remove()
            self._checkpoint(state, "host_removed")
        if state["phase"] == "host_removed":
            self._check_resources(absent_ok=True)
            for path in self._resources():
                path.unlink(missing_ok=True)
            if os.path.lexists(self.paths.runtime):
                verify_tree(
                    self.paths.runtime,
                    owner_uid=self.owner_uid,
                    anchor=self.paths.anchor,
                    payload=state["payload"],
                )
                shutil.rmtree(self.paths.runtime)
            self._checkpoint(state, "uninstalled")
        return "uninstalled"


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def installation_main(root: Path, arguments: list[str] | None = None) -> int:
    """仅owner密码入口从root保护冻结树调用;无NOPASSWD安装/任意路径接口。"""
    import re
    import sys

    args = sys.argv[1:] if arguments is None else arguments
    if len(args) != 1 or args[0] not in {"install", "uninstall", "recover"}:
        return 2
    if os.geteuid() != 0:
        return 2
    try:
        if (
            root.parent.parent != Path("/var/lib/paperradar/live-bundles")
            or not re.fullmatch("[0-9a-f]{64}", root.parent.name)
            or root.name != "runtime"
        ):
            raise ValueError("execution_location")
        verify_tree(root, owner_uid=0, payload=root.parent.name)
        from paper_radar.live_evidence.ledger import EvidenceLedger
        from paper_radar.live_evidence.live_host import LinuxLiveHost
        from paper_radar.live_evidence.protected_observer import (
            protected_collection_lock,
        )

        paths = InstallationPaths()
        confirmation = json.loads(
            (root / "network-owner-confirmation.json").read_bytes()
        )
        if any(
            confirmation["owner_input"].get(field) is not True
            for field in ("owner_window_confirmed", "owner_network_applicable")
        ):
            raise ValueError("owner_confirmation_pending")
        for path in (
            paths.executables,
            paths.units,
            paths.sudoers.parent,
            Path("/srv/pi-cwd"),
        ):
            protected(path, 0)
        for path in (paths.ledger, paths.ledger / "inbox"):
            if not path.exists():
                protected(path.parent, 0)
                path.mkdir(mode=0o755)
            protected(path, 0)
        deployment = LiveDeployment(
            root, paths=paths, host=LinuxLiveHost(paths, source=root)
        )
        with protected_collection_lock(EvidenceLedger(paths.ledger)):
            result = (
                deployment.uninstall()
                if args[0] == "uninstall"
                else deployment.install(recover=args[0] == "recover")
            )
        print(
            f"Live部署状态={result}；历史/额度保留；站点与模型尚须采集和所有者显式激活。"
        )
        return 0
    except Exception as error:
        # 原始OSError/工具stderr可能含路径/宿主数据;只公开有限受控原因。
        reason = (
            str(error)
            if type(error) is ValueError
            and __import__("re").fullmatch("[a-z_]+", str(error))
            else "installation_unavailable"
        )
        print(
            f"Live部署拒绝 [{reason}]；保留现场，"
            "请所有者核对已审归档、状态journal及恢复步骤。",
            file=sys.stderr,
        )
        return 2
