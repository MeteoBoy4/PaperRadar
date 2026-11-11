"""封印放置语言:路径和程序来自受保护配置,通道只携带闭合操作实例。"""

from __future__ import annotations

import fcntl
import json
import math
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.resources import SETTINGS_JSON, check_system_prompt

RUNTIME_ROOT = Path("/usr/libexec/paperradar/live-evidence-runtime")
PROGRAM_PATH = Path("placement/program.json")
MAX_OPERATION_BYTES = 256 * 1024
MODEL_OPTIONS = (
    "--mode",
    "rpc",
    "--offline",
    "--no-session",
    "-ne",
    "-ns",
    "-np",
    "-nc",
    "-nt",
    "-na",
    "--no-mcp",
    "--no-themes",
    "--system-prompt",
)


def _invalid() -> NoReturn:
    raise ExecutionError("placement_handshake_invalid")


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _invalid()
        result[key] = value
    return result


def decode_operation(raw: bytes) -> dict[str, str]:
    """双端共用的严格 wire 校验;未知字段、重复键和类型混淆均拒绝。"""
    if not 0 < len(raw) <= MAX_OPERATION_BYTES:
        _invalid()
    try:
        value = json.loads(raw, object_pairs_hook=_object)
    except (ValueError, UnicodeError, RecursionError):
        _invalid()
    if not isinstance(value, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) or "\0" in v
        for k, v in value.items()
    ):
        _invalid()
    fields = {
        "negative": {"operation"},
        "auth": {"operation", "resource", "attempt_timeout"},
        "model": {"operation", "resource", "token", "prompt"},
    }.get(str(value.get("operation")))
    if fields is None or set(value) != fields:
        _invalid()
    if value["operation"] == "model":
        try:
            check_system_prompt(value["prompt"].encode())
        except (ExecutionError, UnicodeError):
            _invalid()
        token = value["token"]
        if (
            not token
            or len(token) > 16384
            or not token.isascii()
            or any(ord(c) < 33 or ord(c) == 127 for c in token)
        ):
            _invalid()
    if value["operation"] == "auth":
        try:
            timeout = float(value["attempt_timeout"])
            if not math.isfinite(timeout) or not 0 < timeout <= 86400:
                _invalid()
        except ValueError:
            _invalid()
    return {key: str(item) for key, item in value.items()}


@dataclass(frozen=True, repr=False)
class PlacementProgram:
    """只能由封印构建生成;产品现场没有选程序、cwd 或 resolver 的入口。"""

    product_uid: int
    product_gid: int
    install: Path
    credentials: Path
    lock: Path
    proxy: str | None
    runtime: Path = RUNTIME_ROOT
    cwd: Path = Path("/srv/pi-cwd")
    resolver_view: Path = Path("/run/paper-radar/resolv.conf")
    resolver_digest: str = ""
    protected_roots: tuple[Path, ...] = ()

    @property
    def node(self) -> Path:
        return self.install / "node/bin/node"

    @property
    def pi(self) -> Path:
        return (
            self.install
            / "app/node_modules/@earendil-works/pi-coding-agent/dist/cli.js"
        )

    @property
    def python(self) -> Path:
        return self.runtime / "python/bin/python3"

    @property
    def auth_helper(self) -> Path:
        return self.runtime / "site-packages/paper_radar/pi_execution/auth_helper.mjs"

    @property
    def probe(self) -> Path:
        return self.runtime / "site-packages/paper_radar/live_evidence/network_probe.py"

    def bytes(self) -> bytes:
        return (
            json.dumps(
                {
                    "version": 1,
                    "product_uid": self.product_uid,
                    "product_gid": self.product_gid,
                    "install": str(self.install),
                    "credentials": str(self.credentials),
                    "lock": str(self.lock),
                    "proxy": self.proxy,
                    "runtime": str(self.runtime),
                    "cwd": str(self.cwd),
                    "resolver_view": str(self.resolver_view),
                    "resolver_digest": self.resolver_digest,
                    "protected_roots": [str(path) for path in self.protected_roots],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()


def _protected(path: Path) -> None:
    for member in (path, *path.parents):
        info = member.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):
            _invalid()


def _parse_program(raw: bytes) -> PlacementProgram:
    if len(raw) > 65536:
        _invalid()
    value = json.loads(raw, object_pairs_hook=_object)
    if (
        set(value)
        != {
            "version",
            "product_uid",
            "product_gid",
            "install",
            "credentials",
            "lock",
            "proxy",
            "runtime",
            "cwd",
            "resolver_view",
            "resolver_digest",
            "protected_roots",
        }
        or value["version"] != 1
    ):
        _invalid()
    for field in ("product_uid", "product_gid"):
        if type(value[field]) is not int or value[field] <= 0:
            _invalid()
    for field in ("install", "credentials", "lock", "runtime", "cwd"):
        if not isinstance(value[field], str) or "\0" in value[field]:
            _invalid()
        candidate = Path(value[field])
        if not candidate.is_absolute() or ".." in candidate.parts:
            _invalid()
    roots = value["protected_roots"]
    if not isinstance(roots, list) or any(
        not isinstance(path, str)
        or "\0" in path
        or not Path(path).is_absolute()
        or ".." in Path(path).parts
        for path in roots
    ):
        _invalid()
    program = PlacementProgram(
        value["product_uid"],
        value["product_gid"],
        Path(value["install"]),
        Path(value["credentials"]),
        Path(value["lock"]),
        value["proxy"],
        resolver_view=Path(value["resolver_view"]),
        resolver_digest=value["resolver_digest"],
        protected_roots=tuple(Path(path) for path in roots),
    )
    if (
        not re.fullmatch(r"[a-f0-9]{64}", program.resolver_digest)
        or program.bytes() != raw
        or (os.getuid(), os.getgid())
        != (
            program.product_uid,
            program.product_gid,
        )
    ):
        _invalid()
    return program


def load_program() -> PlacementProgram:
    """Initial userns only: fixed path, root ownership and canonical bytes."""
    try:
        path = RUNTIME_ROOT / PROGRAM_PATH
        _protected(path)
        return _parse_program(path.read_bytes())
    except (OSError, ValueError, TypeError, KeyError):
        raise ExecutionError("placement_handshake_invalid") from None


def load_inherited_program() -> PlacementProgram:
    """Native pre verified root protection before UID0 became unmapped.

    Native post compares fd3 bytes to its compiled-in configuration and inode to
    the fixed pathname. Here we consume that sole fixed read-only descriptor;
    overflow uid is never treated as a root ownership assertion.
    """
    try:
        actual = os.fstat(3)
        expected = (RUNTIME_ROOT / PROGRAM_PATH).lstat()
        if (
            not stat.S_ISREG(actual.st_mode)
            or actual.st_nlink != 1
            or actual.st_mode & 0o022
            or (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino)
            or fcntl.fcntl(3, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY
        ):
            _invalid()
        return _parse_program(os.pread(3, 65537, 0))
    except (OSError, ValueError, TypeError, KeyError):
        raise ExecutionError("placement_handshake_invalid") from None
    finally:
        os.close(3)


def _directory(path: Path, uid: int) -> None:
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != uid
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        _invalid()


def _resources(program: PlacementProgram, operation: dict[str, str]) -> Path:
    resource = Path(operation["resource"])
    prefix = (
        "paper-radar-auth-" if operation["operation"] == "auth" else "paper-radar-pi-"
    )
    if resource.parent != Path("/tmp") or not re.fullmatch(
        prefix + r"[a-z0-9_]{8}", resource.name
    ):
        _invalid()
    candidate = resource.resolve()
    for protected in (*program.protected_roots, program.credentials, program.install):
        excluded = protected.resolve()
        if candidate.is_relative_to(excluded) or excluded.is_relative_to(candidate):
            _invalid()
    _directory(resource, program.product_uid)
    children = {"home", "tmp"} | (
        {"agent"} if operation["operation"] == "model" else set()
    )
    if {p.name for p in resource.iterdir()} != children:
        _invalid()
    for name in children:
        _directory(resource / name, program.product_uid)
        expected = {"settings.json"} if name == "agent" else set()
        if {p.name for p in (resource / name).iterdir()} != expected:
            _invalid()
    if operation["operation"] == "model":
        settings = resource / "agent/settings.json"
        info = settings.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_uid != program.product_uid
        ):
            _invalid()
        expected_settings = json.loads(SETTINGS_JSON)
        if program.proxy is not None:
            expected_settings["httpProxy"] = program.proxy
        if (
            json.loads(settings.read_bytes(), object_pairs_hook=_object)
            != expected_settings
        ):
            _invalid()
    return resource


@dataclass(frozen=True, repr=False)
class PlacementExecution:
    argv: tuple[str, ...]
    env: dict[str, str]
    cwd: Path
    attempt: Path | None
    metadata_fd: int | None


def reconstruct_execution(
    program: PlacementProgram, operation: dict[str, str], descriptors: tuple[int, ...]
) -> PlacementExecution:
    """完整校验 fd/临时资源后重建唯一 argv/env;不把私有 socket 当授权。"""
    try:
        # This revalidation also covers callers passing a hand-built dict.
        operation = decode_operation(json.dumps(operation, ensure_ascii=False).encode())
        kind = operation["operation"]
        count = {"negative": 0, "auth": 2, "model": 1}[kind]
        if (
            len(descriptors) != count
            or len(set(descriptors)) != count
            or any(fd < 3 for fd in descriptors)
        ):
            _invalid()
        metadata = None
        if count:
            descriptor = descriptors[0]
            expected = program.lock.lstat()
            actual = os.fstat(descriptor)
            flags = fcntl.fcntl(descriptor, fcntl.F_GETFL)
            if (
                not stat.S_ISREG(actual.st_mode)
                or actual.st_uid != program.product_uid
                or actual.st_nlink != 1
                or flags & os.O_ACCMODE != os.O_RDONLY
                or (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino)
                or not stat.S_ISREG(expected.st_mode)
            ):
                _invalid()
        if kind == "negative":
            return PlacementExecution(
                (str(program.python), "-I", str(program.probe)),
                {},
                program.cwd,
                None,
                None,
            )
        root = _resources(program, operation)
        env = {
            "PI_CODING_AGENT_DIR": str(
                program.credentials if kind == "auth" else root / "agent"
            ),
            "PI_SKIP_VERSION_CHECK": "1",
            "PI_TELEMETRY": "0",
            "HOME": str(root / "home"),
            "TMPDIR": str(root / "tmp"),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": str(program.node.parent),
        }
        if kind == "auth":
            metadata = descriptors[1]
            info = os.fstat(metadata)
            flags = fcntl.fcntl(metadata, fcntl.F_GETFL)
            if (
                not stat.S_ISFIFO(info.st_mode)
                or os.readlink(f"/proc/self/fd/{metadata}") != f"pipe:[{info.st_ino}]"
                or flags & os.O_ACCMODE != os.O_WRONLY
                or not flags & os.O_NONBLOCK
            ):
                _invalid()
            env.update(
                {
                    "PAPERRADAR_PI_PACKAGE": str(
                        program.install
                        / "app/node_modules/@earendil-works/pi-coding-agent"
                    ),
                    "PAPERRADAR_AUTH_ATTEMPT_TIMEOUT": operation["attempt_timeout"],
                    "PAPERRADAR_AUTH_METADATA_FD": str(metadata),
                }
            )
            return PlacementExecution(
                (str(program.node), str(program.auth_helper)),
                env,
                program.credentials,
                None,
                metadata,
            )
        env.update({"PI_OFFLINE": "1", "OPENAI_API_KEY": operation["token"]})
        return PlacementExecution(
            (str(program.node), str(program.pi), *MODEL_OPTIONS, operation["prompt"]),
            env,
            program.cwd,
            root,
            None,
        )
    except (OSError, ValueError, TypeError, KeyError):
        raise ExecutionError("placement_handshake_invalid") from None


def encode_execution(
    program: PlacementProgram,
    argv: tuple[str, ...],
    *,
    env: dict[str, str],
    cwd: Path,
    install: Path,
    attempt: Path | None,
    proxy_port: int | None,
    pass_fds: tuple[int, ...],
) -> bytes:
    """兼容现有正式调用接口,但拒绝无法还原成封印操作的调用。"""
    from paper_radar.pi_execution.resources import proxy_port as port

    if install != program.install:
        _invalid()
    if (
        argv == (str(program.node), str(program.auth_helper))
        and attempt is None
        and proxy_port is None
    ):
        root = Path(env.get("HOME", "/")).parent
        operation = {
            "operation": "auth",
            "resource": str(root),
            "attempt_timeout": env.get("PAPERRADAR_AUTH_ATTEMPT_TIMEOUT", ""),
        }
    elif (
        len(argv) == 2 + len(MODEL_OPTIONS) + 1
        and argv[:2] == (str(program.node), str(program.pi))
        and argv[2:-1] == MODEL_OPTIONS
        and attempt is not None
        and proxy_port == port(program.proxy)
    ):
        operation = {
            "operation": "model",
            "resource": str(attempt),
            "token": env.get("OPENAI_API_KEY", ""),
            "prompt": argv[-1],
        }
    elif (
        argv == (str(program.python), "-I", str(program.probe))
        and attempt is None
        and proxy_port is None
    ):
        operation = {"operation": "negative"}
    else:
        _invalid()
    expected = reconstruct_execution(program, operation, pass_fds)
    if (argv, env, cwd, attempt) != (
        expected.argv,
        expected.env,
        expected.cwd,
        expected.attempt,
    ):
        _invalid()
    raw = json.dumps(operation, separators=(",", ":"), ensure_ascii=False).encode()
    decode_operation(raw)
    return raw
