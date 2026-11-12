"""固定Linux宿主边界:管理员user unit、独立kernfs身份、项目nft和resolver。"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import resource
import signal
import stat
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Literal

from paper_radar.live_evidence.live_install import (
    InstallationPaths,
    protected,
    publish,
)
from paper_radar.live_evidence.model_manifest import (
    ModelManifest,
    parse_manifest,
)
from paper_radar.live_evidence.nft_rules import (
    check_nft_namespace,
    nft_program,
    read_nft_snapshot,
)
from paper_radar.live_evidence.nft_rules import (
    nft_document as nft_document,
)
from paper_radar.live_evidence.nft_rules import (
    verify_nft as verify_nft,
)
from paper_radar.live_evidence.receipt import ApprovedPlan, canonical_bytes
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from paper_radar.pi_execution.placement import (
    CgroupIdentity,
    PlacementTarget,
    verify_placement,
)

if TYPE_CHECKING:
    from paper_radar.live_evidence.placement_policy import PlacementPolicyLifecycle


@dataclass(frozen=True)
class PrerequisiteCheck:
    name: str
    status: Literal["pass", "fail", "blocked", "pending"]
    reason: str


def process_identity(pid: int) -> tuple[int, str]:
    fields = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
    lines = (Path("/proc") / str(pid) / "cgroup").read_text().splitlines()
    if len(lines) != 1 or not lines[0].startswith("0::/"):
        raise ValueError("anchor_identity")
    return int(fields[19]), lines[0][3:]


def cgroup_ancestors(path: str) -> tuple[CgroupIdentity, ...]:
    """不从nft右值倒推ID;每层fd/O_NOFOLLOW/fstatfs独立读取。"""
    pure = PurePosixPath(path)
    if not pure.is_absolute() or ".." in pure.parts or pure.name != "paperradar.slice":
        raise ValueError("cgroup_path")
    result = []
    for item in (pure, *pure.parents):
        fd = os.open("/sys/fs/cgroup", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            buffer = ctypes.create_string_buffer(256)
            if (
                ctypes.CDLL(None, use_errno=True).fstatfs(fd, buffer) != 0
                or ctypes.c_long.from_buffer(buffer).value != 0x63677270
            ):
                raise ValueError("cgroup_filesystem")
            for part in item.parts[1:]:
                child = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                )
                os.close(fd)
                fd = child
            info = os.fstat(fd)
            result.append(CgroupIdentity(str(item), info.st_dev, info.st_ino))
        finally:
            os.close(fd)
    return tuple(result)


class LinuxLiveHost:
    def __init__(self, paths: InstallationPaths, *, source: Path | None = None) -> None:
        self.paths = paths
        self.source = source or paths.runtime
        self.site: SiteConfiguration | None = None
        self.manifest: ModelManifest | None = None

    def _run(
        self, argv: tuple[str, ...], *, product: bool = False, data: bytes | None = None
    ) -> bytes:
        options: dict[str, Any] = {}
        env = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"}
        if product:
            if self.site is None:
                raise ValueError("product_identity_missing")
            uid = self.site.product_uid
            options.update(user=uid, group=self.site.product_gid, extra_groups=())
            env.update(
                XDG_RUNTIME_DIR=f"/run/user/{uid}",
                DBUS_SESSION_BUS_ADDRESS=f"unix:path=/run/user/{uid}/bus",
            )
        result: subprocess.CompletedProcess[bytes] = subprocess.run(
            argv,
            input=data,
            capture_output=True,
            env=env,
            cwd="/",
            timeout=15,
            check=False,
            **options,
        )
        if result.returncode != 0 or len(result.stdout) > 1024 * 1024:
            reason = {
                ("/usr/sbin/nft", "--check", "-f", "-"): "host_nft_check_refused",
                ("/usr/sbin/nft", "-f", "-"): "host_nft_apply_refused",
                ("/usr/sbin/nft", "-j", "list", "tables"): "host_nft_inventory_refused",
            }.get(argv, "host_command_refused")
            raise ValueError(reason)
        return result.stdout

    def _verify_host_identity(self, site: SiteConfiguration) -> None:
        import platform

        specification = json.loads((self.source / "deployment.json").read_bytes())
        if (
            platform.system() != "Linux"
            or platform.machine() != specification["host_machine"]
            or platform.machine() != "x86_64"
        ):
            raise ValueError("host_platform_unknown")
        for name, identity in specification["host_tools"].items():
            resolved = Path(name).resolve()
            protected(resolved, 0)
            if (
                str(resolved) != identity["resolved"]
                or hashlib.sha256(resolved.read_bytes()).hexdigest()
                != identity["sha256"]
            ):
                raise ValueError("host_tool_identity")

    def _verify_product_processes(self, site: SiteConfiguration) -> None:
        # 只观察exe/uid元数据;不读环境、命令行、内存或秘密文件。
        for directory in Path("/proc").iterdir():
            if not directory.name.isdecimal():
                continue
            try:
                if directory.stat().st_uid == site.product_uid and (
                    directory / "exe"
                ).resolve().is_relative_to(site.install_path):
                    raise ValueError("product_process_active")
            except (FileNotFoundError, PermissionError):
                continue

    def preflight(self, site: SiteConfiguration) -> None:
        self.site = site
        self._verify_host_identity(site)
        if (
            self._run(
                ("/usr/bin/systemctl", "--user", "is-system-running"), product=True
            )
            != b"running\n"
            or self._run(
                (
                    "/usr/bin/loginctl",
                    "show-user",
                    str(site.product_uid),
                    "--property=Linger",
                    "--value",
                ),
                product=True,
            )
            != b"yes\n"
        ):
            raise ValueError("manager_unavailable")
        self._verify_product_processes(site)

    def _verify_prerequisite_source(
        self, root: Path, site: SiteConfiguration, manifest: ModelManifest
    ) -> None:
        from paper_radar.live_evidence.live_install import verify_tree

        if root != self.source or root.resolve() != root:
            raise ValueError("prerequisite_source_identity")
        protected(root / "payload.sha256", 0, anchor=self.paths.anchor)
        verify_tree(
            root,
            owner_uid=0,
            anchor=self.paths.anchor,
            payload=(root / "payload.sha256").read_text().strip(),
        )
        if (
            SiteConfiguration.model_validate_json((root / "site.json").read_bytes())
            != site
            or parse_manifest((root / "model-manifest.json").read_bytes()) != manifest
        ):
            raise ValueError("prerequisite_source_identity")
        self._preflight_v2(root)

    def prerequisite_report(
        self,
        root: Path,
        site: SiteConfiguration,
        manifest: ModelManifest,
        *,
        recover: bool = False,
    ) -> tuple[PrerequisiteCheck, ...]:
        """只读汇总独立前提;未知身份阻断,新策略的 true 明确等待事务应用。"""
        from paper_radar.live_evidence.placement_policy import (
            PlacementPreflightRefusal,
            native_preflight,
            verify_host_security,
        )

        results: list[PrerequisiteCheck] = []

        def check(name: str, action: Callable[[], Any]) -> Any:
            try:
                value = action()
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                # Never reflect exception text, subprocess output or secret paths.
                reason = (
                    "native_checkpoint:" + error.checkpoint
                    if isinstance(error, PlacementPreflightRefusal)
                    and error.checkpoint is not None
                    else name + "_refused"
                )
                if (
                    isinstance(error, PlacementPreflightRefusal)
                    and error.manager_checks
                ):
                    reason = "manager_checks:" + ",".join(error.manager_checks)
                if (
                    isinstance(error, PlacementPreflightRefusal)
                    and error.supervisor_checkpoint is not None
                ):
                    reason = "supervisor_checkpoint:" + error.supervisor_checkpoint
                results.append(PrerequisiteCheck(name, "fail", reason))
                return None
            results.append(PrerequisiteCheck(name, "pass", "verified"))
            return value

        names = (
            "placement_seal",
            "host_identity",
            "host_security",
            "manager_state",
            "linger",
            "anchor_active",
            "product_idle",
            "anchor_target",
            "sudoers",
            "nft",
            "failed_preparation_descriptor",
            "main_resources",
            "zero_operation_baseline",
            "placement_policy",
            "native_scope_trace",
        )
        check(
            "source_tree",
            lambda: self._verify_prerequisite_source(root, site, manifest),
        )
        if results[-1].status != "pass":
            return tuple(
                results
                + [PrerequisiteCheck(name, "blocked", "source_tree") for name in names]
            )
        lifecycle = check("placement_seal", lambda: self._placement_lifecycle(root))
        if lifecycle is None or lifecycle.sealed is None:
            if lifecycle is not None:
                results[-1] = PrerequisiteCheck(
                    "placement_seal", "fail", "placement_seal_missing"
                )
            return tuple(
                results
                + [
                    PrerequisiteCheck(name, "blocked", "placement_seal")
                    for name in names[1:]
                ]
            )
        self.site, self.manifest = site, manifest
        sealed = lifecycle.sealed
        check("host_identity", lambda: self._verify_host_identity(site))
        check("host_security", lambda: verify_host_security(sealed))
        for name, argv, expected in (
            (
                "manager_state",
                (
                    "/usr/bin/systemctl",
                    "--user",
                    "show",
                    "--property=SystemState",
                    "--value",
                ),
                b"running\n",
            ),
            (
                "linger",
                (
                    "/usr/bin/loginctl",
                    "show-user",
                    str(site.product_uid),
                    "--property=Linger",
                    "--value",
                ),
                b"yes\n",
            ),
            (
                "anchor_active",
                (
                    "/usr/bin/systemctl",
                    "--user",
                    "is-active",
                    "paperradar-anchor.service",
                ),
                b"active\n",
            ),
        ):

            def query(argv: tuple[str, ...] = argv, expected: bytes = expected) -> None:
                if self._run(argv, product=True) != expected:
                    raise ValueError("manager_unavailable")

            check(name, query)
        check("product_idle", lambda: self._verify_product_processes(site))
        target = check("anchor_target", self._preflight_target)
        check("sudoers", lambda: self.validate_sudoers(root / "sudoers"))
        if target is None:
            results.append(PrerequisiteCheck("nft", "blocked", "anchor_target"))
        else:
            check("nft", lambda: self._check_nft_program(target, manifest))
        gate = check(
            "failed_preparation_descriptor", lambda: self._failed_preparation_void(root)
        )
        gate_valid = results[-1].status == "pass"
        if gate is not None:
            check("main_resources", gate.verify_main_resources)
            check("zero_operation_baseline", gate.verify_zero_operation_baseline)

        def policy() -> str:
            if gate is not None and gate.check(recover=recover):
                return "transaction_required"
            actual = lifecycle.check(recover=recover)
            if not isinstance(actual, str) or actual not in {
                "exact",
                "absent",
                "partial",
                "legacy",
            }:
                raise ValueError("placement_policy_unknown")
            if gate is not None and actual != "exact":
                raise ValueError("placement_policy_missing")
            return actual

        if gate_valid:
            policy_state = check("placement_policy", policy)
        else:
            policy_state = None
            results.extend(
                PrerequisiteCheck(name, "blocked", "failed_preparation_descriptor")
                for name in (
                    "main_resources",
                    "zero_operation_baseline",
                    "placement_policy",
                )
            )
        if any(value.status != "pass" for value in results):
            results.append(
                PrerequisiteCheck("native_scope_trace", "blocked", "prerequisites")
            )
        elif policy_state != "exact":
            results.append(
                PrerequisiteCheck(
                    "native_scope_trace", "pending", "placement_transaction_required"
                )
            )
        else:
            check(
                "native_scope_trace",
                lambda: native_preflight(
                    root, site, sealed, target=target, preserve_boot_marker=True
                ),
            )
        return tuple(results)

    def _preflight_v2(self, root: Path) -> bool:
        specification = json.loads((root / "deployment.json").read_bytes())
        if not isinstance(specification, dict):
            raise ValueError("placement_preflight_protocol")
        if "placement_preflight_version" not in specification:
            return False
        version = specification["placement_preflight_version"]
        if type(version) is not int or version != 2:
            raise ValueError("placement_preflight_protocol")
        return True

    def _failed_preparation_void(self, root: Path) -> Any:
        specification = json.loads((root / "deployment.json").read_bytes())
        if specification.get("failed_preparation_void") is None:
            return None
        from paper_radar.live_evidence.preparation_void import FailedPreparationVoid

        return FailedPreparationVoid(root, self.paths)

    def _placement_lifecycle(self, root: Path) -> PlacementPolicyLifecycle:
        from paper_radar.live_evidence.placement_policy import PlacementPolicyLifecycle

        return PlacementPolicyLifecycle(
            root, self.paths.ledger, owner_uid=0, anchor=self.paths.anchor
        )

    def preflight_placement(self, root: Path, *, recover: bool = False) -> None:
        from paper_radar.live_evidence.placement_policy import verify_host_security
        from paper_radar.live_evidence.preparation_retirement import (
            FailedPreparationRetirement,
        )

        self._preflight_v2(root)
        lifecycle = self._placement_lifecycle(root)
        if lifecycle.sealed is not None:
            verify_host_security(lifecycle.sealed)
        gate = self._failed_preparation_void(root)
        if gate is not None and gate.check(recover=recover):
            return
        if not FailedPreparationRetirement(root, self.paths).check(recover=recover):
            lifecycle.check(recover=recover)

    def prepare_placement(
        self, root: Path, site: SiteConfiguration, *, recover: bool = False
    ) -> None:
        from paper_radar.live_evidence.placement_policy import native_preflight
        from paper_radar.live_evidence.preparation_retirement import (
            FailedPreparationRetirement,
        )

        v2 = self._preflight_v2(root)
        lifecycle = self._placement_lifecycle(root)
        sealed = lifecycle.sealed
        if sealed is not None:
            gate = self._failed_preparation_void(root)
            target = (
                self._preflight_target()
                if gate is not None
                or os.path.lexists(self.paths.ledger / "inbox/placement-target-v1.json")
                else None
            )

            def preflight() -> None:
                if v2:
                    native_preflight(
                        root, site, sealed, target=target, preserve_boot_marker=True
                    )
                else:
                    native_preflight(root, site, sealed, target=target)

            if gate is not None and gate.prepare(
                preflight, lambda: self.verify_preparation_idle(site), recover=recover
            ):
                return

            retirement = FailedPreparationRetirement(root, self.paths)
            if not retirement.prepare(
                preflight, lambda: self.verify_preparation_idle(site), recover=recover
            ):
                lifecycle.prepare(preflight, recover=recover)

    def verify_preparation_idle(self, site: SiteConfiguration) -> None:
        self.preflight(site)
        target = self._preflight_target()  # MAIN的实际anchor与project scope必须空闲。
        for directory in Path("/proc").iterdir():
            if not directory.name.isdecimal():
                continue
            try:
                if directory.stat().st_uid != site.product_uid:
                    continue
                exe = (directory / "exe").resolve(strict=True)
                if (
                    int(directory.name) == target.anchor_pid
                    and exe == self.paths.runtime / "anchor"
                    and process_identity(target.anchor_pid)[0] == target.anchor_start
                ):
                    continue
                if (
                    exe.name in {"placement-pre", "placement-post"}
                    or exe.is_relative_to(self.paths.runtime)
                    or exe.is_relative_to(self.source)
                ):
                    raise ValueError("failed_preparation_process_active")
            except FileNotFoundError:
                continue
            except PermissionError:
                raise ValueError("failed_preparation_process_unavailable") from None

    def _preflight_target(self) -> PlacementTarget:
        target = self._read_target()
        if (
            target.model_copy(update={"egress_digest": "0" * 64})
            != self._anchor_target()
        ):
            raise ValueError("placement_identity_drift")
        verify_placement(
            target, target.anchor_pid, target.anchor_start, "paperradar-anchor.service"
        )
        return target

    def verify_target_preflight(self, root: Path, site: SiteConfiguration) -> None:
        from paper_radar.live_evidence.placement_policy import native_preflight

        v2 = self._preflight_v2(root)
        self.site = site
        lifecycle = self._placement_lifecycle(root)
        sealed = lifecycle.sealed
        if sealed is not None:
            lifecycle.verify()
            if v2:
                native_preflight(
                    root,
                    site,
                    sealed,
                    target=self._preflight_target(),
                    preserve_boot_marker=True,
                )
            else:
                native_preflight(root, site, sealed, target=self._preflight_target())

    def retire_placement(self, root: Path, *, recover: bool = False) -> None:
        self._placement_lifecycle(root).remove(recover=recover)

    def verify_placement_absent(self, root: Path) -> None:
        self._placement_lifecycle(root).verify_absent()

    def _snapshot(self) -> dict[str, Any]:
        return read_nft_snapshot()

    def preflight_nft(self, site: SiteConfiguration, manifest: ModelManifest) -> None:
        """旧 anchor 仍完好时先核新固定规则;此方法没有宿主资源写入。"""
        self.site, self.manifest = site, manifest
        self.ensure_no_table()
        self._check_nft_program(self._anchor_target(), manifest)

    def _check_nft_program(
        self, target: PlacementTarget, manifest: ModelManifest
    ) -> None:
        check_nft_namespace(target, manifest.network)
        self._run(
            ("/usr/sbin/nft", "--check", "-f", "-"),
            data=nft_program(target, manifest.network),
        )

    def ensure_no_table(self) -> None:
        tables = json.loads(self._run(("/usr/sbin/nft", "-j", "list", "tables")))
        if any(
            item.get("table", {}).get("family") == "inet"
            and item.get("table", {}).get("name") == "paperradar"
            for item in tables["nftables"]
        ):
            raise ValueError("nft_table_conflict")

    def validate_sudoers(self, path: Path) -> None:
        self._run(("/usr/sbin/visudo", "-cf", str(path)))

    def unit_properties(self, name: str) -> dict[str, str]:
        """固定两unit的实际manager投影;空执行数组须由D-Bus明确证明。"""
        if name not in {"paperradar.slice", "paperradar-anchor.service"}:
            raise ValueError("unit_unknown")
        raw = self._run(
            (
                "/usr/bin/systemctl",
                "--user",
                "show",
                name,
                "--property=FragmentPath,DropInPaths,ExecStart,Slice,MainPID,ControlGroup,ActiveState,LimitCORE,LimitCORESoft,ExecStartPre,ExecStartPost,ExecStop,ExecStopPost,ExecReload,ExecCondition",
            ),
            product=True,
        )
        values = dict(
            line.split("=", 1) for line in raw.decode().splitlines() if "=" in line
        )
        if name == "paperradar-anchor.service":
            properties = (
                "ExecCondition",
                "ExecStartPre",
                "ExecStartPost",
                "ExecStop",
                "ExecStopPost",
                "ExecReload",
            )
            raw = self._run(
                (
                    "/usr/bin/busctl",
                    "--user",
                    "--json=short",
                    "get-property",
                    "org.freedesktop.systemd1",
                    "/org/freedesktop/systemd1/unit/paperradar_2danchor_2eservice",
                    "org.freedesktop.systemd1.Service",
                    *properties,
                ),
                product=True,
            )

            def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                value = dict(pairs)
                if len(value) != len(pairs):
                    raise ValueError("anchor_exec_properties_invalid")
                return value

            try:
                arrays = [
                    json.loads(line, object_pairs_hook=unique_object)
                    for line in raw.splitlines()
                ]
            except (ValueError, UnicodeError) as error:
                raise ValueError("anchor_exec_properties_invalid") from error
            if len(arrays) != len(properties) or any(
                not isinstance(value, dict)
                or set(value) != {"type", "data"}
                or value["type"] != "a(sasbttttuii)"
                or not isinstance(value["data"], list)
                for value in arrays
            ):
                raise ValueError("anchor_exec_properties_invalid")
            if any(value["data"] for value in arrays) or any(
                values.get(key, "") != "" for key in properties
            ):
                raise ValueError("anchor_extra_commands")
            values.update(dict.fromkeys(properties, ""))
        return values

    def _anchor_target(self) -> PlacementTarget:
        if self.site is None:
            raise ValueError("product_identity_missing")
        values = self.unit_properties("paperradar-anchor.service")
        validate_unit_identity(
            self.paths, self.unit_properties("paperradar.slice"), values
        )
        pid = int(values["MainPID"])
        if (
            self.site is None
            or Path(f"/proc/{pid}").stat().st_uid != self.site.product_uid
            or not os.path.samefile(f"/proc/{pid}/exe", self.paths.runtime / "anchor")
        ):
            raise ValueError("anchor_executable_identity")
        limits = Path(f"/proc/{pid}/limits").read_text().splitlines()
        if not any(
            line.split()[:6] == ["Max", "core", "file", "size", "0", "0"]
            for line in limits
        ):
            raise ValueError("anchor_core_limit")
        start, path = process_identity(pid)
        if path != values["ControlGroup"] or not path.endswith(
            "/paperradar.slice/paperradar-anchor.service"
        ):
            raise ValueError("anchor_identity")
        target = PlacementTarget(
            format_version=1,
            slice="paperradar.slice",
            ancestors=cgroup_ancestors(str(PurePosixPath(path).parent)),
            anchor_pid=pid,
            anchor_start=start,
            anchor_cgroup=path,
            egress_digest="0" * 64,
            resolver_view=str(self.paths.resolver),
            resolver_digest=hashlib.sha256(
                self.paths.resolver.read_bytes()
            ).hexdigest(),
        )
        verify_placement(target, pid, start, "paperradar-anchor.service")
        from paper_radar.live_evidence.network_collection import idle_probe_scope

        if not idle_probe_scope(target):
            raise ValueError("project_scope_not_idle")
        return target

    def _read_target(self) -> PlacementTarget:
        from paper_radar.live_evidence.ledger import EvidenceLedger

        source = self.paths.ledger / "inbox/placement-target-v1.json"
        raw = EvidenceLedger(self.paths.ledger)._read_source(source)
        target = PlacementTarget.model_validate_json(raw)
        if canonical_bytes(target) != raw:
            raise ValueError("placement_source_identity")
        return target

    def configure(self, site: SiteConfiguration, manifest: ModelManifest) -> None:
        self.site, self.manifest = site, manifest
        specification = json.loads(
            (self.paths.runtime / "deployment.json").read_bytes()
        )
        confirmation = json.loads(
            (self.paths.runtime / "network-owner-confirmation.json").read_bytes()
        )
        if (
            confirmation["owner_input"].get("owner_network_applicable") is not True
            or confirmation["owner_input"].get("owner_window_confirmed") is not True
        ):
            raise ValueError("owner_confirmation_pending")
        self._run(("/usr/bin/systemctl", "--user", "daemon-reload"), product=True)
        self._run(
            ("/usr/bin/systemctl", "--user", "start", "paperradar-anchor.service"),
            product=True,
        )
        target = self._anchor_target()
        target_path = self.paths.ledger / "inbox/placement-target-v1.json"
        if os.path.lexists(target_path):
            old = self._read_target()
            snapshot = self._snapshot()
            verify_nft(snapshot, old, manifest.network)
            if old.model_copy(update={"egress_digest": "0" * 64}) != target:
                raise ValueError("placement_identity_drift")
        else:
            self.ensure_no_table()
            self._check_nft_program(target, manifest)
            self._run(
                ("/usr/sbin/nft", "-f", "-"),
                data=nft_program(target, manifest.network),
            )
            snapshot = self._snapshot()
        verify_nft(snapshot, target, manifest.network)
        from paper_radar.live_evidence.protected_observer import egress_identity

        target = target.model_copy(
            update={"egress_digest": egress_identity(snapshot, target)}
        )
        verify_placement(
            target, target.anchor_pid, target.anchor_start, "paperradar-anchor.service"
        )
        if os.path.lexists(target_path):
            if target_path.read_bytes() != canonical_bytes(target):
                raise ValueError("placement_identity_drift")
        else:
            publish(target_path, canonical_bytes(target))
        if specification.get("cache_migration"):
            migrate_cache(site, specification["cache_migration"])

    def verify_installed(
        self, site: SiteConfiguration, manifest: ModelManifest
    ) -> None:
        self.site, self.manifest = site, manifest
        from paper_radar.live_evidence.placement_policy import verify_host_security

        lifecycle = self._placement_lifecycle(self.paths.runtime)
        if lifecycle.sealed is not None:
            verify_host_security(lifecycle.sealed)
        lifecycle.verify()
        target = self._read_target()
        if (
            target.model_copy(update={"egress_digest": "0" * 64})
            != self._anchor_target()
        ):
            raise ValueError("placement_identity_drift")
        snapshot = self._snapshot()
        verify_nft(snapshot, target, manifest.network)
        from paper_radar.live_evidence.protected_observer import egress_identity

        if target.egress_digest != egress_identity(snapshot, target):
            raise ValueError("egress_identity_drift")

    def initialize_plans(
        self, root: Path, site: SiteConfiguration, manifest: ModelManifest
    ) -> None:
        from paper_radar.live_evidence.collection import ProtectedCollection
        from paper_radar.live_evidence.intents import ProtectedIntentLog
        from paper_radar.live_evidence.ledger import EvidenceLedger

        ledger = EvidenceLedger(self.paths.ledger)
        ledger.initialize()
        collection = ProtectedCollection(ledger)
        collection.initialize(now=datetime.now(UTC))
        ProtectedIntentLog(product_gid=site.product_gid).provision(
            ledger, now=datetime.now(UTC)
        )
        site_plan = ApprovedPlan.model_validate_json((root / "plan.json").read_bytes())
        ledger.approve_plan(site_plan, now=datetime.now(UTC))
        for plan in (*(cell.plan for cell in manifest.cells), manifest.negative_plan):
            collection.approve_plan(plan, now=datetime.now(UTC))

    def disable_observation(self) -> None:
        # 不续时点、不清撤销;mode000使当前投影立即不可执行。
        source = self.paths.ledger / "inbox/current-observation.json"
        if source.exists():
            protected(source, 0)
            source.chmod(0)

    def prepare_recovery(
        self, site: SiteConfiguration, manifest: ModelManifest
    ) -> None:
        self.site, self.manifest = site, manifest
        self.disable_observation()
        self.stop_and_remove()

    def check_resources_interruption(
        self,
        site: SiteConfiguration,
        manifest: ModelManifest,
        *,
        allow_stopped: bool = False,
    ) -> None:
        """专用的target发布前检查,不清理nft或停止项目slice。"""
        self.site, self.manifest = site, manifest
        if os.path.lexists(self.paths.ledger / "inbox/placement-target-v1.json"):
            raise ValueError("resources_target_present")
        self.ensure_no_table()
        anchor = self.unit_properties("paperradar-anchor.service")
        if anchor.get("ActiveState") == "active":
            self._anchor_target()  # 独立核exe/uid/start/core/CG且项目仅此anchor。
        elif allow_stopped:
            validate_unit_identity(
                self.paths,
                self.unit_properties("paperradar.slice"),
                anchor,
                require_active=False,
            )
            self.verify_resources_stopped(site)
        else:
            raise ValueError("resources_anchor_identity")

    def verify_resources_stopped(self, site: SiteConfiguration) -> None:
        self.site = site
        self.ensure_no_table()
        values = self.unit_properties("paperradar-anchor.service")
        if values.get("ActiveState") != "inactive" or values.get("MainPID") != "0":
            raise ValueError("resources_anchor_not_stopped")
        directory = Path("/sys/fs/cgroup") / (
            f"user.slice/user-{site.product_uid}.slice/"
            f"user@{site.product_uid}.service/paperradar.slice"
        )
        if directory.exists() and (
            not directory.is_dir()
            or any(
                source.read_text().strip() for source in directory.rglob("cgroup.procs")
            )
        ):
            raise ValueError("scope_not_empty")

    def stop_resources_anchor(
        self, site: SiteConfiguration, manifest: ModelManifest
    ) -> None:
        self.check_resources_interruption(site, manifest, allow_stopped=True)
        self._run(
            ("/usr/bin/systemctl", "--user", "stop", "paperradar-anchor.service"),
            product=True,
        )
        self.verify_resources_stopped(site)

    def stop_and_remove(self) -> None:
        from paper_radar.live_evidence.sealed_runtime import _read_configuration

        self.site = _read_configuration(self.paths.runtime)
        manifest = parse_manifest(
            (self.paths.runtime / "model-manifest.json").read_bytes()
        )
        target_path = self.paths.ledger / "inbox/placement-target-v1.json"
        payload = (self.paths.runtime / "payload.sha256").read_text().strip()
        import re

        if re.fullmatch(r"[0-9a-f]{64}", payload) is None:
            raise ValueError("runtime_payload_identity")
        retirement = self.paths.ledger / (
            "placement-target-retirement-v1-" + payload + ".json"
        )
        retained = None
        if os.path.lexists(retirement):
            protected(retirement, 0)
            info = retirement.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o644
                or info.st_size > 65536
            ):
                raise ValueError("target_retirement_identity")
            retained = retirement.read_bytes()
            if (
                canonical_bytes(PlacementTarget.model_validate_json(retained))
                != retained
            ):
                raise ValueError("target_retirement_identity")
        if os.path.lexists(target_path):
            target = self._read_target()
        elif retained is not None:
            target = PlacementTarget.model_validate_json(retained)
        else:
            raise ValueError("target_retirement_missing")
        raw = canonical_bytes(target)
        archive = target_path.with_name(
            "placement-target-retired-" + hashlib.sha256(raw).hexdigest() + ".json"
        )
        # An existing archive is resumable only when the exact retirement
        # pointer already authenticated it; never bless a pre-existing object.
        if os.path.lexists(archive) and retained != raw:
            raise ValueError("target_archive_conflict")
        if not os.path.lexists(target_path):
            protected(archive, 0)
            if (
                not stat.S_ISREG(archive.lstat().st_mode)
                or archive.lstat().st_nlink != 1
                or stat.S_IMODE(archive.lstat().st_mode) != 0o644
                or archive.read_bytes() != raw
            ):
                raise ValueError("target_retirement_identity")
        if retained is not None and retained != raw:
            prior = target_path.with_name(
                "placement-target-retired-"
                + hashlib.sha256(retained).hexdigest()
                + ".json"
            )
            protected(prior, 0)
            if (
                not stat.S_ISREG(prior.lstat().st_mode)
                or prior.lstat().st_nlink != 1
                or stat.S_IMODE(prior.lstat().st_mode) != 0o644
                or prior.read_bytes() != retained
            ):
                raise ValueError("target_retirement_identity")
        tables = json.loads(self._run(("/usr/sbin/nft", "-j", "list", "tables")))
        present = any(
            item.get("table", {}).get("family") == "inet"
            and item.get("table", {}).get("name") == "paperradar"
            for item in tables["nftables"]
        )
        if present:
            verify_nft(self._snapshot(), target, manifest.network)
        validate_unit_identity(
            self.paths,
            self.unit_properties("paperradar.slice"),
            self.unit_properties("paperradar-anchor.service"),
            require_active=False,
        )
        if retained != raw:
            publish(retirement, raw, replace=retained is not None)
        self._run(
            ("/usr/bin/systemctl", "--user", "stop", "paperradar.slice"), product=True
        )
        directory = Path("/sys/fs/cgroup") / target.ancestors[0].path.lstrip("/")
        if directory.exists():
            info = directory.lstat()
            if not stat.S_ISDIR(info.st_mode) or any(
                source.read_text().strip() for source in directory.rglob("cgroup.procs")
            ):
                raise ValueError("scope_not_empty")
        if present:
            verify_nft(self._snapshot(), target, manifest.network)
            self._run(("/usr/sbin/nft", "delete", "table", "inet", "paperradar"))
        if os.path.lexists(archive):
            protected(archive, 0)
            info = archive.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o644
                or archive.read_bytes() != raw
                or retirement.read_bytes() != raw
            ):
                raise ValueError("target_archive_conflict")
            target_path.unlink(missing_ok=True)
        else:
            target_path.rename(archive)
        descriptor = os.open(target_path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def verify_absent(self) -> None:
        self.ensure_no_table()


def cache_metadata(path: Path) -> dict[str, int]:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise ValueError("legacy_cache_type")
    return {
        name: getattr(info, "st_" + name)
        for name in (
            "dev",
            "ino",
            "mode",
            "uid",
            "gid",
            "nlink",
            "size",
            "mtime_ns",
            "ctime_ns",
        )
    }


def migrate_cache(site: SiteConfiguration, expected: dict[str, int]) -> None:
    """只在降权child中rename;用户可写路径不能成为root提升操作。"""
    source = site.credentials_dir / "node-compile-cache"
    destination = site.credentials_dir.parent / (
        "paperradar-legacy-cache-" + str(expected["dev"]) + "-" + str(expected["ino"])
    )
    if not os.path.lexists(source):
        actual = cache_metadata(destination)
        if any(
            actual[key] != value for key, value in expected.items() if key != "ctime_ns"
        ):
            raise ValueError("legacy_cache_identity")
        return
    if os.path.lexists(destination) or cache_metadata(source) != expected:
        raise ValueError("legacy_cache_identity")
    pid = os.fork()
    if pid == 0:
        try:
            os.environ.clear()
            os.setgroups([])
            os.setresgid(site.product_gid, site.product_gid, site.product_gid)
            os.setresuid(site.product_uid, site.product_uid, site.product_uid)
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            if ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0) != 0:
                os._exit(2)
            os.closerange(3, 1048576)
            null = os.open("/dev/null", os.O_RDWR)
            for descriptor in (0, 1, 2):
                os.dup2(null, descriptor)
            if null > 2:
                os.close(null)
            signal.alarm(10)
            if cache_metadata(source) != expected or os.path.lexists(destination):
                os._exit(2)
            # 不打开cache正文,不复制、不合并、不覆盖;同一FS原子迁出。
            parent_fd = os.open(
                source.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            )
            destination_fd = os.open(
                destination.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            )
            try:
                if os.stat(
                    destination.name, dir_fd=destination_fd, follow_symlinks=False
                ):
                    os._exit(2)
            except FileNotFoundError:
                pass
            # Linux renameat2 RENAME_NOREPLACE;目的地竞态不覆盖。
            libc = ctypes.CDLL(None, use_errno=True)
            if (
                libc.renameat2(
                    parent_fd,
                    source.name.encode(),
                    destination_fd,
                    destination.name.encode(),
                    1,
                )
                != 0
            ):
                os._exit(2)
            os.fsync(parent_fd)
            os.fsync(destination_fd)
            os._exit(0)
        except BaseException:
            os._exit(2)
    _, status = os.waitpid(pid, 0)
    if status != 0 or os.path.lexists(source):
        raise ValueError("legacy_cache_migration_refused")
    actual = cache_metadata(destination)
    if any(
        actual[key] != value for key, value in expected.items() if key != "ctime_ns"
    ):
        raise ValueError("legacy_cache_identity")


def validate_unit_identity(
    paths: InstallationPaths,
    slice_values: dict[str, str],
    anchor_values: dict[str, str],
    *,
    require_active: bool = True,
) -> None:
    """实际manager返回的管理员来源、dropin、argv与LimitCORE完整前提。"""
    for name, values in (
        ("paperradar.slice", slice_values),
        ("paperradar-anchor.service", anchor_values),
    ):
        if (
            values.get("FragmentPath") != str(paths.units / name)
            or values.get("DropInPaths") != ""
            or values.get("ActiveState")
            not in ({"active"} if require_active else {"active", "inactive"})
        ):
            raise ValueError("unit_shadow_or_dropin")
    if any(
        anchor_values.get(name) != ""
        for name in (
            "ExecStartPre",
            "ExecStartPost",
            "ExecStop",
            "ExecStopPost",
            "ExecReload",
            "ExecCondition",
        )
    ):
        raise ValueError("anchor_extra_commands")
    executable = str(paths.runtime / "anchor")
    if (
        anchor_values.get("Slice") != "paperradar.slice"
        or anchor_values.get("LimitCORE") != "0"
        or anchor_values.get("LimitCORESoft") != "0"
        or f"path={executable} ; argv[]={executable} ;"
        not in anchor_values.get("ExecStart", "")
    ):
        raise ValueError("anchor_unit_identity")
