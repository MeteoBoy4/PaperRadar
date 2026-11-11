"""宿主侧有界 OAuth 刷新;与沙箱 attempt 资源所有权严格分离。"""

import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from time import monotonic

from paper_radar.llm.rpc_pipes import PipeSession
from paper_radar.llm.rpc_types import RpcProblem
from paper_radar.pi_execution.auth_metadata import (
    AuthRefreshMetadata,
    parse_auth_metadata,
)
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.placement import PlacedProcess
from paper_radar.pi_execution.process import adopt_process
from paper_radar.pi_execution.resources import (
    AuthHelperResources,
    CleanupAudit,
    ExecutionRoots,
)
from paper_radar.pi_supply.protection import InstallUse


def auth_entry(install: InstallUse) -> Path:
    return Path(__file__).with_name("auth_helper.mjs")


def credential_token(
    install: InstallUse,
    credentials_dir: str,
    *,
    roots: ExecutionRoots,
    attempt_timeout: float,
    timeout: float,
    before_release: Callable[[int, int, str], None] | None = None,
    cleanup_audit: CleanupAudit | None = None,
    observe_auth: Callable[[AuthRefreshMetadata], None] | None = None,
) -> str:
    argv = (str(install.node), str(auth_entry(install)))
    resources = AuthHelperResources(
        roots,
        Path(credentials_dir),
        **({"audit": cleanup_audit} if cleanup_audit else {}),
    )
    try:
        metadata_read, metadata_write = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
    except OSError:
        resources.close()
        raise ExecutionError("auth_failed") from None
    env = {
        "PI_CODING_AGENT_DIR": credentials_dir,
        "PI_SKIP_VERSION_CHECK": "1",
        "PI_TELEMETRY": "0",
        "HOME": str(resources.home),
        "TMPDIR": str(resources.tmp),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": str(install.node.parent),
        "PAPERRADAR_PI_PACKAGE": str(
            install.instance.path / "app/node_modules/@earendil-works/pi-coding-agent"
        ),
        "PAPERRADAR_AUTH_ATTEMPT_TIMEOUT": str(attempt_timeout),
        "PAPERRADAR_AUTH_METADATA_FD": str(metadata_write),
    }
    session: PipeSession | None = None
    output = bytearray()
    metadata = bytearray()
    try:
        placement = PlacedProcess()
        child = placement.execute(
            argv,
            cwd=Path(credentials_dir),
            env=env,
            install=install.instance.path,
            attempt=None,
            proxy_port=None,
            pass_fds=(*install.pass_fds, metadata_write),
            before_release=(
                lambda: before_release(placement.pid, placement.start, placement.unit)
            )
            if before_release
            else None,
        )
        os.close(metadata_write)
        metadata_write = -1
        session = adopt_process(child)
        placement.handoff()
        session.close_stdin()
        deadline = monotonic() + timeout
        total = 0
        while True:
            left = deadline - monotonic()
            if left <= 0:
                raise ExecutionError("auth_timeout")
            event = session.pump(b"", min(left, 0.05))
            try:
                chunk = os.read(metadata_read, 2049)
            except BlockingIOError:
                chunk = b""
            metadata.extend(chunk)
            if len(metadata) > 2048:
                raise ExecutionError("auth_shape")
            total += len(event.stdout) + event.stderr_bytes + len(chunk)
            if total > 64 * 1024:
                raise ExecutionError("auth_failed")
            output.extend(event.stdout)
            if event.stdout_eof and event.stderr_eof and event.exit_code is not None:
                break
        try:
            observation = parse_auth_metadata(bytes(metadata), pid=placement.pid)
        except ValueError:
            raise ExecutionError(
                "auth_failed" if event.exit_code != 0 else "auth_shape"
            ) from None
        if observe_auth is not None:
            observe_auth(observation)
        if event.exit_code != 0:
            raise ExecutionError("auth_failed")
        try:
            token = output.decode("utf-8").removesuffix("\n")
        except UnicodeError:
            raise ExecutionError("auth_shape") from None
        if (
            not token
            or token.startswith("sk-")
            or any(c.isspace() for c in token)
            or (not token.isascii() or any(ord(c) < 33 or ord(c) == 127 for c in token))
        ):
            raise ExecutionError("auth_shape")
        return token
    except (OSError, subprocess.SubprocessError, RpcProblem):
        raise ExecutionError("auth_failed") from None
    finally:
        output.clear()
        metadata.clear()
        os.close(metadata_read)
        if metadata_write >= 0:
            os.close(metadata_write)
        try:
            try:
                if session is not None:
                    try:
                        session.terminate(10)
                    except (OSError, RpcProblem):
                        raise ExecutionError("auth_failed") from None
            finally:
                if "placement" in locals():
                    placement.close()
        finally:
            resources.close()
