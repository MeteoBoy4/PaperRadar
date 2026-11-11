"""封印放置的离线 native/profile 构建;从不加载策略或创建命名空间。"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

from paper_radar.live_evidence.ledger import LEDGER_ROOT
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from paper_radar.pi_execution.placement_protocol import (
    PROGRAM_PATH,
    RUNTIME_ROOT,
    PlacementProgram,
)

PLACEMENT_PRE_PROFILE = "paperradar-placement-pre-v1"
PLACEMENT_POST_PROFILE = "paperradar-placement-post-v1"
PROFILE_NAMES = (PLACEMENT_PRE_PROFILE, PLACEMENT_POST_PROFILE)
PLACEMENT_RESOURCE_SOURCE = Path("placement/apparmor.source")
PLACEMENT_RESOURCE_BINARY = Path("placement/apparmor.bin")
PLACEMENT_RESOURCE_BUILD = Path("placement/build.json")
PROTECTED_SOURCES = {
    "target": LEDGER_ROOT / "inbox/placement-target-v1.json",
    "observation": LEDGER_ROOT / "inbox/current-observation.json",
    "refresh": LEDGER_ROOT / "inbox/observation-refresh.json",
}
ABI_PATH = Path("/etc/apparmor.d/abi/5.0")
CC = Path("/usr/bin/cc")
PARSER = Path("/usr/sbin/apparmor_parser")
CC_FLAGS = (
    "-std=c11",
    "-O2",
    "-static",
    "-fno-plt",
    "-fstack-protector-strong",
    "-D_FORTIFY_SOURCE=3",
    "-Wall",
    "-Wextra",
    "-Werror",
    "-Wno-unused-function",
    "-Wl,-z,noexecstack,-z,relro,-z,now,--build-id=none",
)
PARSER_FLAGS = ("-Q", "-K", "--zstd-compress-level=0", "--Werror")


@dataclass(frozen=True)
class FrozenPlacement:
    profile_source: Path
    profile_binary: Path
    build_manifest: Path
    profiles: tuple[tuple[str, str], ...]


def _safe_path(path: Path) -> str:
    text = str(path)
    if (
        not re.fullmatch(r"/[A-Za-z0-9_./-]+", text)
        or ".." in path.parts
        or path.as_posix() != text
    ):
        raise ValueError("placement_build_path_invalid")
    return text


def _run(argv: tuple[str, ...]) -> bytes:
    result = subprocess.run(
        argv,
        env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
        capture_output=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        raise ValueError("placement_build_failed")
    return result.stdout


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _array(name: str, data: bytes) -> str:
    return (
        f"static const unsigned char {name}[] = {{"
        + ",".join(str(b) for b in data)
        + "};\n"
    )


def verify_static_elf(path: Path) -> None:
    """直接解析 ELF64:拒绝 INTERP/DYNAMIC、非 x86_64 与可执行栈。"""
    data = path.read_bytes()
    try:
        if (
            data[:7] != b"\x7fELF\x02\x01\x01"
            or struct.unpack_from("<H", data, 18)[0] != 62
        ):
            raise ValueError
        offset = struct.unpack_from("<Q", data, 32)[0]
        size, count = struct.unpack_from("<HH", data, 54)
        if size != 56 or not 0 < count < 128:
            raise ValueError
        stack = False
        for index in range(count):
            kind, flags = struct.unpack_from("<II", data, offset + index * size)
            if kind in {2, 3}:
                raise ValueError
            if kind == 0x6474E551:
                stack = True
                if flags & 1:
                    raise ValueError
        if not stack:
            raise ValueError
    except (ValueError, struct.error):
        raise ValueError("placement_native_not_static") from None


def raw_abi_from_binary(data: bytes) -> str:
    """AppArmor serialized stream NAME(version), U32 little-endian header.

    Only the reviewed wire ABI5 is supported. The policy feature ABI filename
    and currently loaded kernel profiles are not evidence of this wire value.
    """
    prefix = b"\x04\x08\x00version\x00\x02"
    if len(data) < 16 or not data.startswith(prefix):
        raise ValueError("placement_policy_wire_abi")
    version = struct.unpack_from("<I", data, len(prefix))[0]
    if version != 5:
        raise ValueError("placement_policy_wire_abi")
    return f"v{version}"


_MOUNT_FLAGS = (
    ("nosuid", os.ST_NOSUID, 2),
    ("nodev", os.ST_NODEV, 4),
    ("noexec", os.ST_NOEXEC, 8),
    ("sync", os.ST_SYNCHRONOUS, 16),
    ("mand", os.ST_MANDLOCK, 64),
    ("noatime", os.ST_NOATIME, 1024),
    ("nodiratime", os.ST_NODIRATIME, 2048),
    ("relatime", os.ST_RELATIME, 1 << 21),
)


def _resolver_mount_flags(path: Path) -> tuple[int, tuple[str, ...]]:
    existing = path
    while not existing.exists():
        existing = existing.parent
    flags = os.statvfs(existing).f_flag
    selected = tuple((name, mount) for name, bit, mount in _MOUNT_FLAGS if flags & bit)
    return sum(value for _, value in selected), tuple(name for name, _ in selected)


def render_profiles(
    program: PlacementProgram,
    *,
    resolver_source: Path,
    resolver_target: Path,
    abi: Path = ABI_PATH,
    resolver_mount_options: tuple[str, ...] = (),
) -> str:
    """两个 enforce profile;pre 唯一 Px,post 只有固定解释器/Node 的 ix。"""
    remount_options = ",".join(("ro", "bind", "remount", *resolver_mount_options))
    root = _safe_path(program.runtime)
    resolver = _safe_path(resolver_source)
    target = _safe_path(resolver_target)
    install = _safe_path(program.install)
    credentials = _safe_path(program.credentials)
    lock = _safe_path(program.lock)
    cwd = _safe_path(program.cwd)
    directories = sorted(
        {
            str(parent)
            for path in (
                program.runtime / "placement-pre",
                program.runtime / "placement-post",
                program.runtime / PROGRAM_PATH,
                resolver_source,
                *PROTECTED_SOURCES.values(),
            )
            for parent in path.parents
        }
    )
    directory_rules = "\n".join(f'  "{path.rstrip("/")}/" r,' for path in directories)
    protected_source_rules = "\n".join(
        f'  "{path}" r,' for path in PROTECTED_SOURCES.values()
    )
    return f'''abi <{_safe_path(abi)}>,
profile {PLACEMENT_PRE_PROFILE} "{root}/placement-pre" {{
{directory_rules}
{protected_source_rules}
  "{root}/placement-pre" mr,
  "{root}/{PROGRAM_PATH}" r,
  "{resolver}" r,
  "{target}" r,
  /proc/self/** rw,
  /proc/[0-9]*/{{status,ns/user,ns/mnt,uid_map,gid_map,setgroups,fd/*,exe}} rw,
  /proc/[0-9]*/attr/{{current,apparmor/current}} r,
  /proc/1/ns/{{user,mnt}} r,
  / r,
  userns,
  capability sys_admin,
  capability setuid,
  capability setgid,
  capability setpcap,
  mount options=(rw,rprivate) -> /,
  mount options=(rw,bind) "{resolver}" -> "{target}",
  mount options=({remount_options}) -> "{target}",
  deny change_profile,
  deny ptrace (readby, tracedby),
  signal (receive) peer=unconfined,
  "{root}/placement-post" Px -> &{PLACEMENT_POST_PROFILE},
}}
profile {PLACEMENT_POST_PROFILE} "{root}/placement-post" {{
{directory_rules}
{protected_source_rules}
  deny userns,
  deny capability,
  deny mount,
  deny umount,
  deny pivot_root,
  deny change_profile,
  "{root}/placement-post" mr,
  "{root}/python/**" mr,
  "{root}/site-packages/**" mr,
  "{root}/{PROGRAM_PATH}" r,
  "{root}/model-manifest.json" r,
  "{resolver}" r,
  "{target}" r,
  "{program.python}" ix,
  "{program.node}" ix,
  /usr/bin/true ix,
  "{install}/**" mr,
  "{lock}" r,
  "{credentials}/" r,
  "{credentials}/**" rwk,
  "{cwd}/" r,
  /tmp/paperradar-placement-????????/handshake rw,
  /tmp/paper-radar-auth-????????/ rw,
  /tmp/paper-radar-auth-????????/** rwk,
  /tmp/paper-radar-pi-????????/ rw,
  /tmp/paper-radar-pi-????????/** rwk,
  /proc/self/** r,
  /proc/[0-9]*/** r,
  /sys/fs/cgroup/** r,
  /lib/** mr,
  /lib64/** mr,
  /usr/lib/** mr,
  /etc/{{ld.so.cache,hosts,nsswitch.conf,resolv.conf}} r,
  /etc/ssl/** r,
  /dev/{{null,urandom,random}} rw,
  network inet stream,
  network inet dgram,
  network unix stream,
  ptrace (readby, tracedby) peer=unconfined,
  signal (receive) peer=unconfined,
  signal (send, receive) peer={PLACEMENT_POST_PROFILE},
}}
'''


def freeze_placement(
    staged_root: Path,
    site: SiteConfiguration,
    source_root: Path,
    *,
    runtime_root: Path = RUNTIME_ROOT,
    resolver_source: Path = Path("/run/paper-radar/resolv.conf"),
    resolver_target: Path | None = None,
) -> FrozenPlacement:
    """显式编译目标便于离线模型;部署者必须绑定审核过的固定真实路径。

    staged_root 已由 freeze_runtime 准备;resources/resolv.conf 是唯一 resolver
    原文。返回 source/binary/name/attachment 供安装器精确加载和回读。
    """
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("placement_build_platform")
    target = resolver_target or Path("/etc/resolv.conf").resolve(strict=True)
    for path in (runtime_root, resolver_source, target):
        _safe_path(path)
    resolver_bytes = (staged_root / "resources/resolv.conf").read_bytes()
    program = PlacementProgram(
        site.product_uid,
        site.product_gid,
        site.install_path,
        site.credentials_dir,
        site.roots.install_root / ".locks" / (site.binding.install_id + ".lock"),
        site.binding.proxy,
        runtime_root,
        resolver_view=resolver_source,
        resolver_digest=hashlib.sha256(resolver_bytes).hexdigest(),
        protected_roots=(
            site.roots.data_root,
            site.roots.config_root,
            site.roots.material_root,
            site.roots.install_root,
        ),
    )
    directory = staged_root / "placement"
    directory.mkdir()
    if not 0 < len(resolver_bytes) <= 65536 or b"\0" in resolver_bytes:
        raise ValueError("placement_resolver_invalid")
    program_path = staged_root / PROGRAM_PATH
    program_path.write_bytes(program.bytes())
    native_source = source_root / "src/paper_radar/pi_execution/placement_native.c"
    shutil.copyfile(native_source, directory / "placement_native.c")
    source_mount_flags, source_mount_options = _resolver_mount_flags(resolver_source)
    initial_user = Path("/proc/self/ns/user").stat()
    initial_mount = Path("/proc/self/ns/mnt").stat()
    header = (
        f"#define PRODUCT_UID {site.product_uid}U\n"
        f"#define PRODUCT_GID {site.product_gid}U\n"
        + "".join(
            f'#define {name} "{_safe_path(path)}"\n'
            for name, path in (
                ("PRE_PATH", runtime_root / "placement-pre"),
                ("POST_PATH", runtime_root / "placement-post"),
                ("PROGRAM_PATH", runtime_root / PROGRAM_PATH),
                ("PYTHON_PATH", program.python),
                (
                    "WRAPPER_PATH",
                    runtime_root
                    / "site-packages/paper_radar/pi_execution/placement_wrapper.py",
                ),
                ("INBOX_PATH", LEDGER_ROOT / "inbox"),
                ("TARGET_PATH", PROTECTED_SOURCES["target"]),
                ("OBSERVATION_PATH", PROTECTED_SOURCES["observation"]),
                ("REFRESH_PATH", PROTECTED_SOURCES["refresh"]),
                ("RESOLVER_SOURCE", resolver_source),
                ("RESOLVER_TARGET", target),
            )
        )
        + f"#define RESOLVER_MOUNT_FLAGS {source_mount_flags}UL\n"
        + f"#define INITIAL_USER_DEVICE {initial_user.st_dev}UL\n"
        + f"#define INITIAL_USER_INODE {initial_user.st_ino}UL\n"
        + f"#define INITIAL_MOUNT_DEVICE {initial_mount.st_dev}UL\n"
        + f"#define INITIAL_MOUNT_INODE {initial_mount.st_ino}UL\n"
        + f'#define PRE_PROFILE "{PLACEMENT_PRE_PROFILE} (enforce)\\n"\n'
        + f'#define POST_PROFILE "{PLACEMENT_POST_PROFILE} (enforce)\\n"\n'
        + _array("program_bytes", program.bytes())
        + _array("resolver_bytes", resolver_bytes)
    )
    (directory / "placement_config.h").write_text(header)
    native_dependencies: dict[str, str] = {}
    for stage in ("pre", "post"):
        command = (
            str(CC),
            *CC_FLAGS,
            *(("-DPLACEMENT_PRE",) if stage == "pre" else ()),
            "-I",
            str(directory),
            "-MD",
            "-MF",
            str(directory / (stage + ".d")),
            "-o",
            str(staged_root / ("placement-" + stage)),
            str(directory / "placement_native.c"),
        )
        _run(command)
        dependency_file = directory / (stage + ".d")
        dependencies = (
            dependency_file.read_text().replace("\\\n", " ").split(":", 1)[1].split()
        )
        for dependency in dependencies:
            path = Path(dependency)
            if path.is_relative_to(directory):
                continue
            native_dependencies[str(path)] = _sha(path)
        dependency_file.unlink()
        verify_static_elf(staged_root / ("placement-" + stage))
    # Copy the sole include and force fixed compile/kernel features. No tunables,
    # abstractions, parser config or host kernel feature fallback are consumed.
    abi = directory / "abi-5.0"
    shutil.copyfile(ABI_PATH, abi)
    parser_config = directory / "parser.conf"
    parser_config.write_bytes(b"")
    source = staged_root / PLACEMENT_RESOURCE_SOURCE
    # The source references the bundled ABI by relative name; the fixed include
    # directory is supplied explicitly and is itself part of the frozen closure.
    profile = render_profiles(
        program,
        resolver_source=resolver_source,
        resolver_target=target,
        resolver_mount_options=source_mount_options,
    )
    profile = profile.replace(f"abi <{ABI_PATH}>,", "abi <abi-5.0>,")
    source.write_text(profile)
    binary = staged_root / PLACEMENT_RESOURCE_BINARY
    parser_command = (
        str(PARSER),
        *PARSER_FLAGS,
        "--config-file",
        str(parser_config),
        "--policy-features",
        str(abi),
        "--kernel-features",
        str(abi),
        "-I",
        str(directory),
        "--ofile",
        str(binary),
        str(source),
    )
    _run(parser_command)
    names = _run(
        (
            str(PARSER),
            "-Q",
            "-K",
            "--config-file",
            str(parser_config),
            "-N",
            "-I",
            str(directory),
            str(source),
        )
    )
    if set(names.decode().splitlines()) != set(PROFILE_NAMES):
        raise ValueError("placement_profile_set")
    manifest = staged_root / PLACEMENT_RESOURCE_BUILD
    identities = {}
    for name, tool in (("cc", CC), ("apparmor_parser", PARSER)):
        resolved = tool.resolve(strict=True)
        identities[name] = {
            "path": str(resolved),
            "sha256": _sha(resolved),
            "version": _run((str(tool), "--version")).decode().splitlines()[0],
        }
    # GCC is a driver: bind the assembler, linker, cc1, static runtime archives,
    # CRT objects and effective specs as well as the public compiler binary.
    for name in ("as", "ld", "cc1"):
        spelling = _run((str(CC), "-print-prog-name=" + name)).decode().strip()
        tool_path = (
            Path(spelling) if spelling.startswith("/") else Path("/usr/bin") / spelling
        )
        tool_path = tool_path.resolve(strict=True)
        identities[name] = {
            "path": str(tool_path),
            "sha256": _sha(tool_path),
            "version": (
                _run((str(tool_path), "--version")).decode().splitlines()
                or ["not-emitted"]
            )[0],
        }
    link_inputs = {}
    for name in (
        "libc.a",
        "libgcc.a",
        "libgcc_eh.a",
        "crt1.o",
        "crti.o",
        "crtbeginT.o",
        "crtend.o",
        "crtn.o",
    ):
        spelling = _run((str(CC), "-print-file-name=" + name)).decode().strip()
        path = Path(spelling)
        if not path.is_absolute():
            raise ValueError("placement_build_link_input")
        path = path.resolve(strict=True)
        link_inputs[name] = {"path": str(path), "sha256": _sha(path)}
    manifest.write_text(
        json.dumps(
            {
                "format_version": 1,
                "tools": identities,
                "initial_namespaces": {
                    "user": [initial_user.st_dev, initial_user.st_ino],
                    "mnt": [initial_mount.st_dev, initial_mount.st_ino],
                },
                "cc_flags": CC_FLAGS,
                "native_headers": native_dependencies,
                "link_inputs": link_inputs,
                "compiler_specs_sha256": hashlib.sha256(
                    _run((str(CC), "-dumpspecs"))
                ).hexdigest(),
                "parser_flags": PARSER_FLAGS,
                "protected_inbox": str(LEDGER_ROOT / "inbox"),
                "protected_sources": {
                    key: str(path) for key, path in PROTECTED_SOURCES.items()
                },
                "resolver_source": str(resolver_source),
                "resolver_target": str(target),
                "resolver_sha256": hashlib.sha256(resolver_bytes).hexdigest(),
                "resolver_mount_flags": source_mount_flags,
                "resolver_mount_options": source_mount_options,
                "abi": "v5",
                "raw_abi": raw_abi_from_binary(binary.read_bytes()),
                "abi_sha256": _sha(abi),
                "includes": {"abi-5.0": _sha(abi)},
                "parser_config_sha256": _sha(parser_config),
                "source_sha256": _sha(source),
                "binary_sha256": _sha(binary),
                "native_source_sha256": _sha(directory / "placement_native.c"),
                "native_header_sha256": _sha(directory / "placement_config.h"),
                "program_sha256": _sha(program_path),
                "profiles": [
                    {
                        "name": name,
                        "attachment": str(runtime_root / ("placement-" + stage)),
                    }
                    for name, stage in zip(PROFILE_NAMES, ("pre", "post"), strict=True)
                ],
                "native_sha256": {
                    stage: _sha(staged_root / ("placement-" + stage))
                    for stage in ("pre", "post")
                },
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    directory.chmod(0o755)
    for resource in directory.iterdir():
        resource.chmod(0o644)
    for stage in ("pre", "post"):
        (staged_root / ("placement-" + stage)).chmod(0o755)
    return FrozenPlacement(
        source,
        binary,
        manifest,
        tuple(
            (name, str(runtime_root / ("placement-" + stage)))
            for name, stage in zip(PROFILE_NAMES, ("pre", "post"), strict=True)
        ),
    )
