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
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from paper_radar.live_evidence.live_install import (
    InstallationPaths,
    json_bytes,
    protected,
    publish,
)
from paper_radar.live_evidence.model_manifest import (
    NEGATIVES,
    ModelManifest,
    NetworkConfiguration,
    parse_manifest,
)
from paper_radar.live_evidence.receipt import ApprovedPlan, canonical_bytes
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from paper_radar.pi_execution.placement import (
    CgroupIdentity,
    PlacementTarget,
    verify_placement,
)


def nft_document(
    target: PlacementTarget, network: NetworkConfiguration
) -> dict[str, Any]:
    """固定JSON规则,四个独立drop counter先于三个允许;IPv6落入末尾drop。"""
    base = {"family": "inet", "table": "paperradar"}
    rules: list[dict[str, Any]] = []

    def match(left: object, right: object) -> dict[str, Any]:
        return {"match": {"op": "==", "left": left, "right": right}}

    def destination(address: object, protocol: str, port: int) -> list[dict[str, Any]]:
        return [
            match({"meta": {"key": "nfproto"}}, "ipv4"),
            match({"payload": {"protocol": "ip", "field": "daddr"}}, address),
            match({"meta": {"key": "l4proto"}}, protocol),
            match({"payload": {"protocol": protocol, "field": "dport"}}, port),
        ]

    level = len(PurePosixPath(target.ancestors[0].path).parts) - 1
    rules.append(
        {
            "chain": "output",
            "expr": [
                match(
                    {"socket": {"key": "cgroupv2", "level": level}},
                    target.ancestors[0].path.lstrip("/"),
                ),
                {"jump": {"target": "project"}},
            ],
            "comment": "paperradar-placement-v1",
        }
    )
    for _case, address, protocol, port, comment in zip(
        NEGATIVES,
        (
            str(network.outside),
            str(network.nonrouter),
            str(network.nonrouter),
            str(network.udp443),
        ),
        ("tcp", "udp", "tcp", "udp"),
        (443, 53, 53, 443),
        network.rule_comments,
        strict=True,
    ):
        rules.append(
            {
                "chain": "project",
                "expr": [
                    *destination(address, protocol, port),
                    {"counter": {"packets": 0, "bytes": 0}},
                    {"drop": None},
                ],
                "comment": comment,
            }
        )
    from ipaddress import IPv4Network

    pool = IPv4Network(network.pool)
    for allow_address, protocol, port, label in (
        (
            {"prefix": {"addr": str(pool.network_address), "len": pool.prefixlen}},
            "tcp",
            443,
            "pool-tls",
        ),
        (str(network.router), "udp", 53, "router-udp53"),
        (str(network.router), "tcp", 53, "router-tcp53"),
    ):
        rules.append(
            {
                "chain": "project",
                "expr": [*destination(allow_address, protocol, port), {"accept": None}],
                "comment": "paperradar-" + label,
            }
        )
    rules.append(
        {
            "chain": "project",
            "expr": [{"drop": None}],
            "comment": "paperradar-deny-remainder",
        }
    )
    return {
        "nftables": [
            {"add": {"table": {"family": "inet", "name": "paperradar"}}},
            {
                "add": {
                    "chain": {
                        **base,
                        "name": "output",
                        "type": "filter",
                        "hook": "output",
                        "prio": -10,
                        "policy": "accept",
                    }
                }
            },
            {"add": {"chain": {**base, "name": "project"}}},
            *({"add": {"rule": {**base, **rule}}} for rule in rules),
        ]
    }


def verify_nft(
    snapshot: dict[str, Any], target: PlacementTarget, network: NetworkConfiguration
) -> None:
    expected = [item["add"] for item in nft_document(target, network)["nftables"]]
    actual = []
    handles: set[int] = set()
    for item in snapshot.get("nftables", []):
        if set(item) == {"metainfo"}:
            continue
        if len(item) != 1 or next(iter(item)) not in {"table", "chain", "rule"}:
            raise ValueError("nft_inventory")
        kind, value = next(iter(item.items()))
        row = {
            key: content
            for key, content in value.items()
            if key not in {"handle", "use", "index"}
        }
        if kind == "rule":
            handle = value.get("handle")
            if type(handle) is not int or handle <= 0 or handle in handles:
                raise ValueError("nft_rule_handle")
            handles.add(handle)
            from copy import deepcopy

            row = deepcopy(row)
            for expression in row.get("expr", []):
                if "counter" in expression:
                    if set(expression["counter"]) != {"packets", "bytes"} or any(
                        type(value) is not int or value < 0
                        for value in expression["counter"].values()
                    ):
                        raise ValueError("nft_counter")
                    expression["counter"] = {"packets": 0, "bytes": 0}
                match = expression.get("match", {})
                if match.get("left", {}).get("socket", {}).get("key") == "cgroupv2":
                    right = match.get("right")
                    if right not in (
                        target.ancestors[0].path,
                        target.ancestors[0].path.lstrip("/"),
                        target.ancestors[0].inode,
                    ):
                        raise ValueError("nft_target_identity")
                    match["right"] = target.ancestors[0].path.lstrip("/")
        actual.append({kind: row})
    if actual != expected:
        raise ValueError("nft_structure")


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
            raise ValueError("host_command_refused")
        return result.stdout

    def preflight(self, site: SiteConfiguration) -> None:
        self.site = site
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

    def _snapshot(self) -> dict[str, Any]:
        value = json.loads(
            self._run(("/usr/sbin/nft", "-j", "list", "table", "inet", "paperradar"))
        )
        if not isinstance(value, dict):
            raise ValueError("nft_snapshot_invalid")
        return value

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

    def _unit_properties(self, name: str) -> dict[str, str]:
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
        return dict(
            line.split("=", 1) for line in raw.decode().splitlines() if "=" in line
        )

    def _anchor_target(self) -> PlacementTarget:
        if self.site is None:
            raise ValueError("product_identity_missing")
        values = self._unit_properties("paperradar-anchor.service")
        validate_unit_identity(
            self.paths, self._unit_properties("paperradar.slice"), values
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
            self._run(
                ("/usr/sbin/nft", "-j", "-f", "-"),
                data=json_bytes(nft_document(target, manifest.network)),
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

    def stop_and_remove(self) -> None:
        from paper_radar.live_evidence.sealed_runtime import _read_configuration

        self.site = _read_configuration(self.paths.runtime)
        manifest = parse_manifest(
            (self.paths.runtime / "model-manifest.json").read_bytes()
        )
        target_path = self.paths.ledger / "inbox/placement-target-v1.json"
        target = self._read_target()
        raw = canonical_bytes(target)
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
            self._unit_properties("paperradar.slice"),
            self._unit_properties("paperradar-anchor.service"),
            require_active=False,
        )
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
        archive = target_path.with_name(
            "placement-target-retired-" + hashlib.sha256(raw).hexdigest() + ".json"
        )
        if archive.exists():
            raise ValueError("target_archive_conflict")
        target_path.rename(archive)

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
