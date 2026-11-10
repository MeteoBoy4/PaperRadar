"""公开站点元数据的只读观察;固定来源,不接触认证或模型。"""

import os
import platform
import stat
from pathlib import Path

from paper_radar.config.identity import canonical_json, sha256
from paper_radar.live_evidence.ledger import LedgerError
from paper_radar.live_evidence.types import BindingComponent as B
from paper_radar.pi_execution import resources
from paper_radar.pi_execution.isolation import (
    ISOLATION_POLICY_VERSION,
    isolation_capability,
)


def component_digest(value: object) -> str:
    return sha256(canonical_json(value))


def _public(path: Path, *, optional: bool = False) -> str:
    try:
        with path.open("rb") as source:
            data = source.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise LedgerError("binding_observation_unavailable")
        return sha256(data)
    except FileNotFoundError:
        if optional:
            return "absent"
        raise LedgerError("binding_observation_unavailable") from None


def _metadata(path: Path) -> tuple[int, ...]:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        raise LedgerError("binding_observation_unavailable")
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _apport_version() -> str:
    """从公开 dpkg 状态读取准确包版本;不运行外部程序。"""
    path = Path("/var/lib/dpkg/status")
    try:
        with path.open("rb") as source:
            data = source.read(16 * 1024 * 1024 + 1)
        if len(data) > 16 * 1024 * 1024:
            raise LedgerError("binding_observation_unavailable")
        for block in data.split(b"\n\n"):
            lines = block.splitlines()
            if b"Package: apport" in lines:
                return component_digest(
                    tuple(
                        line.decode("utf-8")
                        for line in lines
                        if line.startswith((b"Version:", b"Status:"))
                    )
                )
        return "absent"
    except FileNotFoundError:
        return "unavailable"


def _apport_config() -> str:
    from paper_radar.pi_supply.errors import SupplyError
    from paper_radar.pi_supply.filesystem import tree_hash

    root = Path("/etc/apport")
    try:
        return tree_hash(root) if root.exists() else "absent"
    except SupplyError:
        raise LedgerError("binding_observation_unavailable") from None


def site_binding_components() -> dict[B, str]:
    """不读取私有文件;Apport版本/配置字节身份与core_pattern每次比较。"""
    try:
        cwd = resources.check_cwd()
        ancestors = tuple((str(path), _metadata(path)) for path in (cwd, *cwd.parents))
        abi = isolation_capability()
        apport = tuple(
            (str(path), _public(path, optional=True))
            for path in (
                Path("/usr/share/apport/apport"),
                Path("/usr/share/apport/package-hooks/source_linux.py"),
                Path("/var/lib/dpkg/info/apport.list"),
                Path("/etc/default/apport"),
                Path("/etc/apport/crashdb.conf"),
            )
        )
        return {
            B.HOST: _public(Path("/etc/machine-id")),
            B.BOOT: _public(Path("/proc/sys/kernel/random/boot_id")),
            B.KERNEL: component_digest(tuple(os.uname())),
            B.LANDLOCK_ABI: component_digest(abi),
            B.CWD_ANCESTORS: component_digest(ancestors),
            B.FILE_ISOLATION: component_digest((ISOLATION_POLICY_VERSION, abi)),
            B.CORE_LIMITS: component_digest(("child-preexec", 0, 0)),
            B.APPORT: component_digest(
                (
                    _public(Path("/proc/sys/kernel/core_pattern")),
                    _public(Path("/proc/sys/fs/suid_dumpable")),
                    _apport_version(),
                    _apport_config(),
                    apport,
                )
            ),
        }
    except OSError:
        raise LedgerError("observation_unavailable") from None


def node_platform_component(node_version: str) -> str:
    return component_digest(
        (
            node_version,
            platform.system(),
            platform.machine(),
            os.confstr("CS_GNU_LIBC_VERSION"),
        )
    )
