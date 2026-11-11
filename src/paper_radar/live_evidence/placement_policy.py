"""封印 native/AppArmor 与安装状态机的有限桥接;不接受任意命令或策略路径。"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from paper_radar.live_evidence.live_apparmor_kernel import (
    AppArmorKernel,
    LinuxKernelPolicyIO,
    ParserIdentity,
    SealedPolicy,
)
from paper_radar.live_evidence.sealed_runtime import RUNTIME_ROOT, SiteConfiguration
from paper_radar.pi_execution.placement import PlacementTarget

_PROC_ROOT = Path("/proc")
_PARSER_PATH = Path("/usr/sbin/apparmor_parser")
_RESOLVER_PATH = Path("/etc/resolv.conf")
_RESOLVER_SOURCE_PATH = Path("/run/paper-radar/resolv.conf")

PROFILES = (
    ("paperradar-placement-pre-v1", str(RUNTIME_ROOT / "placement-pre")),
    ("paperradar-placement-post-v1", str(RUNTIME_ROOT / "placement-post")),
)
SYSCTLS = (
    "apparmor_restrict_unprivileged_unconfined",
    "apparmor_restrict_unprivileged_userns",
)
RUNTIME_TOOLS = (
    "/usr/sbin/apparmor_parser",
    "/usr/bin/true",
    "/usr/bin/systemd-run",
    "/usr/bin/systemctl",
    "/usr/bin/loginctl",
)

MEMBERS = (
    "placement-pre",
    "placement-post",
    "placement/apparmor.source",
    "placement/apparmor.bin",
    "placement/abi-5.0",
    "placement/parser.conf",
    "placement/program.json",
    "placement/build.json",
    "placement/security.json",
    "placement/placement_native.c",
    "placement/placement_config.h",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class PlacementPolicy:
    policy: SealedPolicy
    parser: ParserIdentity
    build: dict[str, Any]
    security: dict[str, Any]
    identity: str

    def kernel(self) -> AppArmorKernel:
        return AppArmorKernel(LinuxKernelPolicyIO(), self.parser)


def read_placement_policy(
    root: Path, *, reader: Callable[[Path], bytes] | None = None
) -> PlacementPolicy | None:
    """已核树/非特权构建用默认IO;root observer注入先核保护链的fd reader。"""
    read = reader or Path.read_bytes
    if not os.path.lexists(root / "placement") and not any(
        os.path.lexists(root / name) for name in MEMBERS
    ):
        identity_path = root / "source-identity.json"
        if identity_path.exists():
            identity = json.loads(read(identity_path))
            auxiliary = (
                identity.get("source_auxiliary_sha256", {})
                if isinstance(identity, dict)
                else None
            )
            if not isinstance(auxiliary, dict):
                raise ValueError("placement_seal_identity")
            if "pi_execution/placement_native.c" in auxiliary:
                raise ValueError("placement_seal_incomplete")
        return None
    try:
        members = {name: read(root / name) for name in MEMBERS}
    except OSError:
        raise ValueError("placement_seal_incomplete") from None
    try:
        build = json.loads(members["placement/build.json"])
        security = json.loads(members["placement/security.json"])
        if (
            type(build["format_version"]) is not int
            or build["format_version"] not in {1, 2}
            or build["profiles"]
            != [{"name": name, "attachment": attach} for name, attach in PROFILES]
            or build["raw_abi"] != "v5"
            or build["abi"] != "v5"
            or build["parser_flags"]
            != ["-Q", "-K", "--zstd-compress-level=0", "--Werror"]
            or build["includes"] != {"abi-5.0": build["abi_sha256"]}
            or set(security) != {"format_version", "sysctls", "tools"}
            or security["format_version"] != 1
            or security["sysctls"] != dict.fromkeys(SYSCTLS, 1)
            or not isinstance(security["tools"], dict)
            or set(security["tools"]) != set(RUNTIME_TOOLS)
            or build["resolver_source"] != "/run/paper-radar/resolv.conf"
            or type(build["resolver_mount_flags"]) is not int
            or build["resolver_mount_flags"] < 0
            or build["resolver_mount_flags"]
            & ~(2 | 4 | 8 | 16 | 64 | 1024 | 2048 | (1 << 21))
            or not Path(build["resolver_target"]).is_absolute()
        ):
            raise ValueError
        for identity in security["tools"].values():
            if (
                not isinstance(identity, dict)
                or set(identity) != {"resolved", "sha256"}
                or not isinstance(identity["resolved"], str)
                or not Path(identity["resolved"]).is_absolute()
                or not isinstance(identity["sha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", identity["sha256"]) is None
            ):
                raise ValueError
        if build["format_version"] == 2:
            true = security["tools"]["/usr/bin/true"]
            program = json.loads(members["placement/program.json"])
            expected_exec = {
                f'  "{program["runtime"]}/python/bin/python3" ix,',
                f'  "{program["install"]}/node/bin/node" ix,',
                f'  "{true["resolved"]}" ix,',
            }
            source = members["placement/apparmor.source"].decode("ascii")
            if (
                build["fixed_true_exec"] != true
                or re.fullmatch(r"/[A-Za-z0-9_./-]+", true["resolved"]) is None
                or ".." in Path(true["resolved"]).parts
                or [line for line in source.splitlines() if line.endswith(" ix,")]
                != [
                    f'  "{program["runtime"]}/python/bin/python3" ix,',
                    f'  "{program["install"]}/node/bin/node" ix,',
                    f'  "{true["resolved"]}" ix,',
                ]
                or len(expected_exec) != 3
            ):
                raise ValueError
        for field, member in (
            ("source_sha256", "placement/apparmor.source"),
            ("binary_sha256", "placement/apparmor.bin"),
            ("abi_sha256", "placement/abi-5.0"),
            ("parser_config_sha256", "placement/parser.conf"),
            ("native_source_sha256", "placement/placement_native.c"),
            ("native_header_sha256", "placement/placement_config.h"),
            ("program_sha256", "placement/program.json"),
        ):
            if build[field] != _sha(members[member]):
                raise ValueError
        for stage in ("pre", "post"):
            if build["native_sha256"][stage] != _sha(members["placement-" + stage]):
                raise ValueError
        # Wire header is independent of the source ABI declaration and metadata.
        if not members["placement/apparmor.bin"].startswith(
            b"\x04\x08\x00version\x00\x02\x05\x00\x00\x00"
        ):
            raise ValueError
        tool = build["tools"]["apparmor_parser"]
        if (
            not isinstance(tool, dict)
            or not isinstance(tool.get("path"), str)
            or not isinstance(tool.get("sha256"), str)
        ):
            raise ValueError
        parser = ParserIdentity(tool["path"], tool["sha256"])
        if not parser.resolved.startswith("/") or len(parser.sha256) != 64:
            raise ValueError
        if security["tools"]["/usr/sbin/apparmor_parser"] != {
            "resolved": parser.resolved,
            "sha256": parser.sha256,
        }:
            raise ValueError
        for namespace in ("user", "mnt"):
            identity = build["initial_namespaces"][namespace]
            if len(identity) != 2 or any(
                type(value) is not int or value <= 0 for value in identity
            ):
                raise ValueError
        policy = SealedPolicy(
            members["placement/apparmor.bin"],
            build["binary_sha256"],
            build["source_sha256"],
            build["raw_abi"],
            PROFILES,
        )
    except (KeyError, TypeError, ValueError):
        raise ValueError("placement_seal_identity") from None
    return PlacementPolicy(
        policy,
        parser,
        build,
        security,
        _sha(
            json.dumps(
                {name: _sha(raw) for name, raw in members.items()}, sort_keys=True
            ).encode()
        ),
    )


def read_sysctls() -> dict[str, int]:
    try:
        values = {
            name: ((_PROC_ROOT / "sys/kernel") / name).read_text().strip()
            for name in SYSCTLS
        }
        if any(value != "1" for value in values.values()):
            raise ValueError("placement_sysctl_identity")
    except OSError:
        raise ValueError("placement_sysctl_unavailable") from None
    return dict.fromkeys(SYSCTLS, 1)


def freeze_security(root: Path) -> None:
    tools = {
        name: {
            "resolved": str(Path(name).resolve(strict=True)),
            "sha256": _sha(Path(name).resolve(strict=True).read_bytes()),
        }
        for name in RUNTIME_TOOLS
    }
    path = root / "placement/security.json"
    path.write_text(
        json.dumps(
            {"format_version": 1, "sysctls": read_sysctls(), "tools": tools},
            sort_keys=True,
        )
        + "\n"
    )
    path.chmod(0o644)


def verify_host_security(sealed: PlacementPolicy) -> None:
    if read_sysctls() != sealed.security["sysctls"]:
        raise ValueError("placement_sysctl_identity")
    from paper_radar.live_evidence.live_install import protected

    try:
        for name, identity in sealed.security["tools"].items():
            tool = Path(name).resolve(strict=True)
            try:
                protected(tool, 0)
            except ValueError:
                raise ValueError("placement_tool_identity") from None
            if (
                str(tool) != identity["resolved"]
                or _sha(tool.read_bytes()) != identity["sha256"]
            ):
                raise ValueError("placement_tool_identity")
        for namespace in ("user", "mnt"):
            current = ((_PROC_ROOT / "self/ns") / namespace).stat()
            initial = ((_PROC_ROOT / "1/ns") / namespace).stat()
            expected = sealed.build["initial_namespaces"][namespace]
            if [current.st_dev, current.st_ino] != expected or [
                initial.st_dev,
                initial.st_ino,
            ] != expected:
                raise ValueError("placement_namespace_identity")
        if str(_RESOLVER_PATH.resolve(strict=True)) != sealed.build["resolver_target"]:
            raise ValueError("placement_resolver_target")
        parser = _PARSER_PATH.resolve(strict=True)
        if (
            str(parser) != sealed.parser.resolved
            or _sha(parser.read_bytes()) != sealed.parser.sha256
        ):
            raise ValueError("placement_parser_identity")
    except OSError:
        raise ValueError("placement_host_unavailable") from None


class PlacementPolicyLifecycle:
    """策略准备先于旧业务首写;精确side journal证明中断归属,不恢复资格。"""

    def __init__(
        self,
        root: Path,
        ledger: Path,
        *,
        owner_uid: int,
        anchor: Path,
        kernel: AppArmorKernel | None = None,
    ) -> None:
        self.root, self.ledger = root, ledger
        self.owner_uid, self.anchor = owner_uid, anchor
        self.sealed = read_placement_policy(root)
        self.kernel = kernel or (self.sealed.kernel() if self.sealed else None)

    @property
    def journal(self) -> Path:
        if self.sealed is None:
            raise ValueError("placement_policy_missing")
        return self.ledger / (
            "placement-policy-v1-" + self.sealed.policy.binary_sha256 + ".json"
        )

    def _state(self) -> str | None:
        from paper_radar.live_evidence.live_install import json_bytes, protected

        if self.sealed is None or not os.path.lexists(self.journal):
            return None
        protected(self.journal, self.owner_uid, anchor=self.anchor)
        info = self.journal.lstat()
        import stat

        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o644
            or info.st_size > 4096
        ):
            raise ValueError("placement_policy_journal_identity")
        raw = self.journal.read_bytes()
        try:
            value = json.loads(raw)
            if (
                set(value) != {"format_version", "identity", "phase"}
                or value["format_version"] != 1
                or value["identity"] != self.sealed.identity
                or value["phase"]
                not in {"preparing", "prepared", "removing", "removed"}
                or json_bytes(value) != raw
            ):
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError("placement_policy_journal_identity") from None
        return str(value["phase"])

    def _record(self, phase: str) -> None:
        from paper_radar.live_evidence.live_install import (
            json_bytes,
            protected,
            publish,
        )

        assert self.sealed is not None
        if not self.ledger.exists():
            self.ledger.mkdir(parents=True, mode=0o755)
        protected(self.ledger, self.owner_uid, anchor=self.anchor)
        publish(
            self.journal,
            json_bytes(
                {"format_version": 1, "identity": self.sealed.identity, "phase": phase}
            ),
            replace=self.journal.exists(),
        )

    def phase(self) -> str | None:
        """只读认证已拥有的精确side journal;不处理另一个完整身份。"""
        return self._state()

    def check(self, *, recover: bool = False) -> str:
        if self.sealed is None or self.kernel is None:
            return "legacy"
        state = self._state()
        actual = self.kernel.check(
            self.sealed.policy,
            allow_partial=recover and state in {"preparing", "removing"},
        )
        if actual != "absent" and state is None:
            raise ValueError("placement_policy_ownership_unknown")
        if actual != "absent" and state == "removed":
            raise ValueError("placement_policy_reappeared")
        return actual

    def prepare(self, preflight: Callable[[], None], *, recover: bool = False) -> None:
        if self.sealed is None or self.kernel is None:
            return
        actual = self.check(recover=recover)
        state = self._state()
        if state == "prepared" and actual == "exact":
            # Revalidate the same owned deployment without regressing its phase.
            if os.path.lexists(self.journal.with_name(self.journal.name + ".new")):
                raise ValueError("placement_policy_journal_identity")
            preflight()
            self.kernel.verify(self.sealed.policy)
            return
        if actual == "partial":
            # Explicit recover + exact preparing/removing record only.
            self.kernel.remove(self.sealed.policy, allow_partial=True)
        elif state == "prepared" and actual == "absent" and not recover:
            raise ValueError("placement_policy_missing")
        self._record("preparing")
        self.kernel.load(self.sealed.policy)
        preflight()
        self.kernel.verify(self.sealed.policy)
        self._record("prepared")

    def verify(self) -> None:
        if self.sealed is None or self.kernel is None:
            return
        if self._state() != "prepared":
            raise ValueError("placement_policy_not_prepared")
        self.kernel.verify(self.sealed.policy)

    def remove(self, *, recover: bool = False) -> None:
        if self.sealed is None or self.kernel is None:
            return
        actual = self.check(recover=recover)
        if actual == "absent":
            if self._state() is not None:
                self._record("removed")
            return
        self._record("removing")
        self.kernel.remove(self.sealed.policy, allow_partial=recover)
        self._record("removed")

    def verify_absent(self) -> None:
        if self.check() != "absent" and self.sealed is not None:
            raise ValueError("placement_policy_still_present")


def _close_root_descriptors() -> None:
    # Enumerate the actual forked process, including descriptors above a usual
    # RLIMIT_NOFILE. No unrelated parent root handle may reach product Python.
    import errno

    for name in os.listdir("/proc/self/fd"):
        if name.isdecimal() and int(name) >= 3:
            try:
                os.close(int(name))
            except OSError as error:
                if error.errno != errno.EBADF:
                    raise


def native_preflight(
    root: Path,
    site: SiteConfiguration,
    sealed: PlacementPolicy,
    *,
    target: PlacementTarget | None = None,
) -> None:
    """Owner root child only: private MNT, exact staged binds, product UID true.

    Without a target this tests only the namespace/cap/seccomp/profile chain.
    A root-verified target additionally requires the actual product scope and
    post R/SEIZE/true exec-stop checks. Neither mode grants execution evidence.
    All mountpoints created below are inside private tmpfs mounts.
    """
    import ctypes
    import resource
    import signal

    if os.geteuid() != 0 or root.resolve() != root:
        raise ValueError("placement_preflight_not_root")
    verify_host_security(sealed)
    pid = os.fork()
    if pid == 0:
        try:
            signal.alarm(15)
            os.setsid()
            # Parent keeps the collector lock; this root child must not retain
            # writable ledger/lock or any unrelated inherited authority.
            _close_root_descriptors()
            os.environ.clear()
            os.chdir("/")
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            libc = ctypes.CDLL(None, use_errno=True)

            def mount(
                source: str | None,
                target: str,
                kind: str | None,
                flags: int,
                data: bytes | None = None,
            ) -> None:
                if (
                    libc.mount(
                        source.encode() if source else None,
                        target.encode(),
                        kind.encode() if kind else None,
                        ctypes.c_ulong(flags),
                        data,
                    )
                    != 0
                ):
                    raise OSError("placement_private_mount")

            if libc.unshare(0x00020000) != 0:  # CLONE_NEWNS, never NEWUSER as root.
                os._exit(125)
            mount(None, "/", None, 0x4000 | 0x40000)  # MS_REC|MS_PRIVATE
            # Preserve the real canonical resolver as an fd before hiding /run.
            resolver_target = Path(sealed.build["resolver_target"])
            resolver_fd = os.open(resolver_target, os.O_RDONLY | os.O_NOFOLLOW)
            user_runtime_fd = (
                os.open(
                    f"/run/user/{site.product_uid}",
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                )
                if target is not None
                else None
            )
            # /usr/libexec and /run are fixed existing root directories. Covering
            # them in this child permits initial installs without host mkdirs.
            mount("tmpfs", "/usr/libexec", "tmpfs", 2 | 4, b"mode=755")
            mount("tmpfs", "/run", "tmpfs", 2 | 4, b"mode=755")
            RUNTIME_ROOT.mkdir(parents=True, mode=0o755)
            mount(str(root), str(RUNTIME_ROOT), None, 4096)
            mount(None, str(RUNTIME_ROOT), None, 4096 | 32 | 1)
            source = _RESOLVER_SOURCE_PATH
            source.parent.mkdir(parents=True, mode=0o755)
            source.touch(mode=0o644)
            mount(str(root / "resources/resolv.conf"), str(source), None, 4096)
            mount(
                None,
                str(source),
                None,
                4096 | 32 | 1 | sealed.build["resolver_mount_flags"],
            )
            if resolver_target.is_relative_to("/run"):
                resolver_target.parent.mkdir(parents=True, mode=0o755, exist_ok=True)
                resolver_target.touch(mode=0o644)
                mount(
                    "/proc/self/fd/" + str(resolver_fd),
                    str(resolver_target),
                    None,
                    4096,
                )
            os.close(resolver_fd)
            if user_runtime_fd is not None:
                user_runtime = Path(f"/run/user/{site.product_uid}")
                user_runtime.mkdir(parents=True, mode=0o755)
                mount(
                    "/proc/self/fd/" + str(user_runtime_fd),
                    str(user_runtime),
                    None,
                    4096 | 0x4000,
                )
                os.close(user_runtime_fd)
            # Redirect and close every setup fd while still root. The product
            # Python supervisor never receives an inherited root write handle.
            null = os.open("/dev/null", os.O_RDWR | os.O_CLOEXEC)
            for descriptor in (0, 1, 2):
                os.dup2(null, descriptor)
            if null > 2:
                os.close(null)
            _close_root_descriptors()
            os.chdir("/")
            os.setgroups([])
            os.setresgid(site.product_gid, site.product_gid, site.product_gid)
            os.setresuid(site.product_uid, site.product_uid, site.product_uid)
            # Pre must enter with NNP0; it and post enforce their own core,
            # label, fd, immutable bytes, maps, capability and syscall checks.
            if libc.prctl(4, 0, 0, 0, 0) != 0:
                os._exit(125)
            if target is not None:
                from paper_radar.pi_execution.placement_preflight import (
                    run_traced_preflight,
                )

                run_traced_preflight(
                    target, product_uid=site.product_uid, product_gid=site.product_gid
                )
                os._exit(0)
            executable = str(RUNTIME_ROOT / "placement-pre")
            os.execve(executable, (executable, "--preflight"), {})
        except BaseException:
            os._exit(125)
    _, status = os.waitpid(pid, 0)
    if status != 0:
        raise ValueError("placement_preflight_refused")
    # Changes during the probe cannot be treated as a successful preparation.
    verify_host_security(sealed)
    sealed.kernel().verify(sealed.policy)
