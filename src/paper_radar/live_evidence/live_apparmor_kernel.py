"""固定 AppArmor policy 树的精确封印回读;不编译源码、不替换未知策略。"""

from __future__ import annotations

import hashlib
import os
import re
import selectors
import signal
import stat
import subprocess
import tempfile
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

FailureKind = Literal["unavailable", "drift", "conflict"]
PolicyReason = Literal[
    "apparmor_abi_mismatch",
    "apparmor_attachment_mismatch",
    "apparmor_blob_mismatch",
    "apparmor_field_unknown",
    "apparmor_inventory_limit",
    "apparmor_inventory_unknown",
    "apparmor_mode_mismatch",
    "apparmor_parser_identity",
    "apparmor_parser_output_limit",
    "apparmor_parser_refused",
    "apparmor_parser_timeout",
    "apparmor_parser_unavailable",
    "apparmor_partial_policy",
    "apparmor_profile_handle_invalid",
    "apparmor_profile_identity_unknown",
    "apparmor_profile_missing",
    "apparmor_profile_name_invalid",
    "apparmor_profile_set_mismatch",
    "apparmor_readback_incomplete",
    "apparmor_readback_limit",
    "apparmor_readback_unavailable",
    "apparmor_remove_incomplete",
    "apparmor_remove_refused",
    "apparmor_revision_unknown",
    "apparmor_sealed_policy_invalid",
    "apparmor_snapshot_changed",
    "apparmor_writer_not_root",
    "apparmor_writer_unchecked",
]


class AppArmorPolicyError(ValueError):
    def __init__(self, reason: PolicyReason, kind: FailureKind = "unavailable") -> None:
        super().__init__(reason)
        self.reason = reason
        self.kind = kind


@dataclass(frozen=True)
class ParserIdentity:
    resolved: str
    sha256: str


@dataclass(frozen=True)
class SealedPolicy:
    """来自已核封印的未压缩包;源码摘要仅记来源,不与 kernel hash 混用。"""

    binary: bytes
    binary_sha256: str
    source_sha256: str
    raw_abi: str
    profiles: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if (
            not self.binary
            or self.binary.startswith(b"\x28\xb5\x2f\xfd")
            or len(self.binary) > 16 * 1024 * 1024
            or hashlib.sha256(self.binary).hexdigest() != self.binary_sha256
            or re.fullmatch(r"[0-9a-f]{64}", self.source_sha256) is None
            or re.fullmatch(r"v[0-9]+", self.raw_abi) is None
            or not self.profiles
            or len(set(dict(self.profiles))) != len(self.profiles)
            or len({attach for _, attach in self.profiles}) != len(self.profiles)
            or any(
                re.fullmatch(r"[a-zA-Z0-9_.-]+", name) is None
                or not attach.startswith("/")
                or any(c in attach for c in "\x00\n\r")
                for name, attach in self.profiles
            )
        ):
            raise AppArmorPolicyError("apparmor_sealed_policy_invalid")


class KernelPolicyIO(Protocol):
    """仅 OS 接缝;生产实现固定 kernel 树和 parser 路径。"""

    def revision(self) -> bytes: ...
    def profile_handles(self) -> tuple[str, ...]: ...
    def profile_identity(self, handle: str) -> tuple[str, ...]: ...
    def read_field(self, handle: str, field: str) -> bytes: ...
    def require_writer(self, parser: ParserIdentity) -> None: ...
    def load_binary(self, binary: bytes) -> None: ...
    def remove_profile(self, name: str) -> None: ...


@dataclass(frozen=True)
class _LoadedProfile:
    name: str
    attach: str
    mode: str
    abi: str
    raw_sha: str
    raw: bytes | None


class AppArmorKernel:
    def __init__(self, io: KernelPolicyIO, parser: ParserIdentity) -> None:
        self._io = io
        self._parser = parser

    def _snapshot(self, policy: SealedPolicy) -> tuple[_LoadedProfile, ...]:
        try:
            revision = self._io.revision()
            if re.fullmatch(rb"[0-9]+\n?", revision) is None:
                raise AppArmorPolicyError("apparmor_revision_unknown")
            handles = self._io.profile_handles()
            if len(handles) > _MAX_PROFILES or len(set(handles)) != len(handles):
                raise AppArmorPolicyError("apparmor_inventory_limit")
            total = 0

            def read(handle: str, field: str) -> bytes:
                nonlocal total
                raw = self._io.read_field(handle, field)
                total += len(raw)
                if total > _MAX_SNAPSHOT_BYTES:
                    raise AppArmorPolicyError("apparmor_readback_limit")
                return raw

            identities = tuple(self._io.profile_identity(h) for h in handles)
            result = []
            for handle in handles:

                def text(field: str, handle: str = handle) -> str:
                    raw = read(handle, field)
                    value = raw.removesuffix(b"\n").decode("utf-8")
                    if not value or any(c in value for c in "\x00\r\n"):
                        raise AppArmorPolicyError("apparmor_readback_incomplete")
                    return value

                name, attach, mode = text("name"), text("attach"), text("mode")
                abi, raw_sha = text("raw_abi"), text("raw_sha256")
                if (
                    re.fullmatch(r"v[0-9]+", abi) is None
                    or re.fullmatch(r"[0-9a-f]{64}", raw_sha) is None
                ):
                    raise AppArmorPolicyError("apparmor_readback_incomplete")
                relevant = (
                    name in dict(policy.profiles)
                    or attach in dict(policy.profiles).values()
                    or raw_sha == policy.binary_sha256
                )
                raw = read(handle, "raw_data") if relevant else None
                result.append(_LoadedProfile(name, attach, mode, abi, raw_sha, raw))
            if (
                handles != self._io.profile_handles()
                or identities != tuple(self._io.profile_identity(h) for h in handles)
                or revision != self._io.revision()
            ):
                raise AppArmorPolicyError("apparmor_snapshot_changed")
            return tuple(result)
        except AppArmorPolicyError:
            raise
        except (OSError, ValueError, KeyError, UnicodeError) as from_error:
            raise AppArmorPolicyError("apparmor_readback_unavailable") from from_error

    def _known(self, policy: SealedPolicy, *, kind: FailureKind) -> frozenset[str]:
        found: set[str] = set()
        expected = dict(policy.profiles)
        for profile in self._snapshot(policy):
            relevant = (
                profile.name in expected
                or profile.attach in expected.values()
                or profile.raw_sha == policy.binary_sha256
            )
            if not relevant:
                continue
            if profile.name not in expected or profile.name in found:
                raise AppArmorPolicyError("apparmor_profile_set_mismatch", kind)
            # apparmorfs exports this exact sentinel when attachment has a DFA
            # but no xmatch_str. The reviewed sealed binary binds that DFA;
            # every mode/ABI/hash/full-byte check below remains mandatory.
            if profile.attach not in {expected[profile.name], "<unknown>"}:
                raise AppArmorPolicyError("apparmor_attachment_mismatch", kind)
            if profile.mode != "enforce":
                raise AppArmorPolicyError("apparmor_mode_mismatch", kind)
            if profile.abi != policy.raw_abi:
                raise AppArmorPolicyError("apparmor_abi_mismatch", kind)
            if profile.raw_sha != policy.binary_sha256 or profile.raw != policy.binary:
                raise AppArmorPolicyError("apparmor_blob_mismatch", kind)
            found.add(profile.name)
        return frozenset(found)

    def check(
        self, policy: SealedPolicy, *, allow_partial: bool = False
    ) -> Literal["absent", "exact", "partial"]:
        """只读检查初装/恢复状态;未知现存策略始终拒绝。"""
        found = self._known(policy, kind="conflict")
        if not found:
            return "absent"
        if found == frozenset(dict(policy.profiles)):
            return "exact"
        if allow_partial:
            return "partial"
        raise AppArmorPolicyError("apparmor_partial_policy", "conflict")

    def verify(self, policy: SealedPolicy) -> None:
        if self._known(policy, kind="drift") != frozenset(dict(policy.profiles)):
            raise AppArmorPolicyError("apparmor_profile_missing", "drift")

    def load(self, policy: SealedPolicy) -> bool:
        found = self._known(policy, kind="conflict")
        if found == frozenset(dict(policy.profiles)):
            return False
        if found:
            raise AppArmorPolicyError("apparmor_partial_policy", "conflict")
        self._io.require_writer(self._parser)
        if self._known(policy, kind="conflict"):
            raise AppArmorPolicyError("apparmor_snapshot_changed")
        self._io.load_binary(policy.binary)
        self.verify(policy)
        return True

    def remove(self, policy: SealedPolicy, *, allow_partial: bool = False) -> bool:
        found = self._known(policy, kind="conflict")
        if not found:
            return False
        if not allow_partial and found != frozenset(dict(policy.profiles)):
            raise AppArmorPolicyError("apparmor_partial_policy", "conflict")
        self._io.require_writer(self._parser)
        for name in sorted(found):
            if self._known(policy, kind="conflict") != found:
                raise AppArmorPolicyError("apparmor_snapshot_changed")
            self._io.remove_profile(name)
            found = found - {name}
        if self._known(policy, kind="conflict"):
            raise AppArmorPolicyError("apparmor_remove_incomplete", "conflict")
        return True


_POLICY_ROOT = Path("/sys/kernel/security/apparmor/policy")
_PARSER = Path("/usr/sbin/apparmor_parser")
_FIELDS = frozenset({"name", "mode", "attach", "raw_abi", "raw_sha256", "raw_data"})
_MAX_PROFILES = 4096
_MAX_DEPTH = 32
_MAX_BINARY = 16 * 1024 * 1024
_MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024
_MAX_OUTPUT = 64 * 1024
_PARSER_TIMEOUT = 15.0


class LinuxKernelPolicyIO:
    """固定 Linux 接口,没有调用方选择的 root 读取路径或 parser argv。"""

    def __init__(self) -> None:
        self._writer_identity: ParserIdentity | None = None

    def revision(self) -> bytes:
        # revision 为可等待更新的流,不能 read_bytes() 等待 EOF。
        fd = os.open(_POLICY_ROOT / "revision", os.O_RDONLY | os.O_NONBLOCK)
        try:
            return os.read(fd, 128)
        finally:
            os.close(fd)

    def profile_handles(self) -> tuple[str, ...]:
        result: list[str] = []

        def walk(directory: Path, depth: int) -> None:
            if depth > _MAX_DEPTH:
                raise AppArmorPolicyError("apparmor_inventory_limit")
            for entry in directory.iterdir():
                if entry.is_symlink() or not entry.is_dir():
                    raise AppArmorPolicyError("apparmor_inventory_unknown")
                result.append(str(entry.relative_to(_POLICY_ROOT / "profiles")))
                if len(result) > _MAX_PROFILES:
                    raise AppArmorPolicyError("apparmor_inventory_limit")
                children = entry / "profiles"
                try:
                    children.stat()
                except FileNotFoundError:
                    continue
                walk(children, depth + 1)

        walk(_POLICY_ROOT / "profiles", 0)
        return tuple(sorted(result))

    @staticmethod
    def _profile(handle: str) -> Path:
        parts = handle.split("/")
        if (
            len(parts) % 2 != 1
            or len(parts) > _MAX_DEPTH * 2 + 1
            or any(
                part in {".", ".."}
                or re.fullmatch(r"[a-zA-Z0-9_.-]+", part) is None
                or (index % 2 == 1 and part != "profiles")
                for index, part in enumerate(parts)
            )
        ):
            raise AppArmorPolicyError("apparmor_profile_handle_invalid")
        directory = _POLICY_ROOT / "profiles"
        # policy 根本身可为 apparmorfs magic link;其下组件只允许真目录。
        for part in parts:
            directory = directory / part
            if not stat.S_ISDIR(directory.lstat().st_mode):
                raise AppArmorPolicyError("apparmor_profile_identity_unknown")
        return directory

    def profile_identity(self, handle: str) -> tuple[str, ...]:
        directory = self._profile(handle)
        paths = (directory, *(directory / field for field in sorted(_FIELDS)))
        result: list[str] = []
        for path in paths:
            info, target = path.lstat(), path.stat()
            link = os.readlink(path) if path.is_symlink() else ""
            if link and not Path(os.path.normpath(path.parent / link)).is_relative_to(
                _POLICY_ROOT / "raw_data"
            ):
                raise AppArmorPolicyError("apparmor_profile_identity_unknown")
            result.extend(
                (
                    str(info.st_dev),
                    str(info.st_ino),
                    str(info.st_mode),
                    link,
                    str(target.st_dev),
                    str(target.st_ino),
                )
            )
        return tuple(result)

    def read_field(self, handle: str, field: str) -> bytes:
        if field not in _FIELDS:
            raise AppArmorPolicyError("apparmor_field_unknown")
        path = self._profile(handle) / field
        limit = _MAX_BINARY if field == "raw_data" else 8192
        with path.open("rb", buffering=0) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise AppArmorPolicyError("apparmor_readback_limit")
        return data

    def require_writer(self, parser: ParserIdentity) -> None:
        self._writer_identity = None
        if os.geteuid() != 0:
            raise AppArmorPolicyError("apparmor_writer_not_root")
        try:
            resolved = _PARSER.resolve(strict=True)
            if (
                str(resolved) != parser.resolved
                or re.fullmatch(r"[0-9a-f]{64}", parser.sha256) is None
            ):
                raise AppArmorPolicyError("apparmor_parser_identity")
            for path in (resolved, *resolved.parents):
                info = path.stat()
                if info.st_uid != 0 or info.st_mode & 0o022:
                    raise AppArmorPolicyError("apparmor_parser_identity")
            before = resolved.stat()
            if (
                not stat.S_ISREG(before.st_mode)
                or not before.st_mode & 0o111
                or hashlib.sha256(resolved.read_bytes()).hexdigest() != parser.sha256
                or before != resolved.stat()
            ):
                raise AppArmorPolicyError("apparmor_parser_identity")
        except OSError as error:
            raise AppArmorPolicyError("apparmor_parser_unavailable") from error
        self._writer_identity = parser

    def _require_writer(self) -> None:
        if self._writer_identity is None:
            raise AppArmorPolicyError("apparmor_writer_unchecked")
        self.require_writer(self._writer_identity)

    def load_binary(self, binary: bytes) -> None:
        self._require_writer()
        if not binary or len(binary) > _MAX_BINARY:
            raise AppArmorPolicyError("apparmor_sealed_policy_invalid")
        # 已封印的 binary 走 stdin,无 source/target/namespace 可变参数。
        argv = (
            str(_PARSER),
            "--config-file=/dev/null",
            "--add",
            "--binary",
            "--skip-cache",
            "--abort-on-error",
        )
        try:
            with tempfile.TemporaryFile() as source:
                source.write(binary)
                source.seek(0)
                with subprocess.Popen(
                    argv,
                    stdin=source,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd="/",
                    env={"LANG": "C", "LC_ALL": "C"},
                    start_new_session=True,
                ) as process:
                    try:
                        with selectors.DefaultSelector() as selector:
                            for stream in (process.stdout, process.stderr):
                                assert stream is not None
                                selector.register(stream, selectors.EVENT_READ)
                            deadline, total = time.monotonic() + _PARSER_TIMEOUT, 0
                            while selector.get_map():
                                remaining = deadline - time.monotonic()
                                if remaining <= 0:
                                    raise AppArmorPolicyError("apparmor_parser_timeout")
                                for key, _ in selector.select(min(remaining, 0.1)):
                                    chunk = os.read(key.fd, _MAX_OUTPUT + 1)
                                    if not chunk:
                                        selector.unregister(key.fd)
                                    total += len(chunk)
                                    if total > _MAX_OUTPUT:
                                        raise AppArmorPolicyError(
                                            "apparmor_parser_output_limit"
                                        )
                            try:
                                status = process.wait(
                                    timeout=max(0.001, deadline - time.monotonic())
                                )
                            except subprocess.TimeoutExpired as error:
                                raise AppArmorPolicyError(
                                    "apparmor_parser_timeout"
                                ) from error
                            if status != 0:
                                raise AppArmorPolicyError("apparmor_parser_refused")
                    except BaseException:
                        with suppress(ProcessLookupError):
                            os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                        raise
        except OSError as error:
            raise AppArmorPolicyError("apparmor_parser_unavailable") from error

    def remove_profile(self, name: str) -> None:
        self._require_writer()
        if re.fullmatch(r"[a-zA-Z0-9_.-]+", name) is None:
            raise AppArmorPolicyError("apparmor_profile_name_invalid")
        try:
            # .remove 接收一个精确 profile 名;不借整包 remove 吞掉缺失错误。
            fd = os.open(_POLICY_ROOT / ".remove", os.O_WRONLY)
            try:
                data = name.encode("ascii") + b"\x00"
                if os.write(fd, data) != len(data):
                    raise AppArmorPolicyError("apparmor_remove_incomplete")
            finally:
                os.close(fd)
        except OSError as error:
            raise AppArmorPolicyError("apparmor_remove_refused") from error
