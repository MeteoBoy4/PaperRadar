"""宿主侧有界 OAuth 刷新;与沙箱 attempt 资源所有权严格分离。"""

import math
import subprocess
from collections.abc import Callable
from pathlib import Path
from time import monotonic

from paper_radar.llm.rpc_pipes import PipeSession
from paper_radar.llm.rpc_types import RpcProblem
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.placement import PlacedProcess
from paper_radar.pi_execution.process import adopt_process
from paper_radar.pi_execution.resources import (
    AuthHelperResources,
    CleanupAudit,
    ExecutionRoots,
)
from paper_radar.pi_supply.protection import InstallUse


def credential_token(
    install: InstallUse,
    credentials_dir: str,
    *,
    roots: ExecutionRoots,
    attempt_timeout: float,
    timeout: float,
    before_release: Callable[[int, int, str], None] | None = None,
    cleanup_audit: CleanupAudit | None = None,
) -> str:
    argv = (
        str(install.node),
        str(install.pi),
        "auth",
        "print-bearer-token",
        "--provider",
        "openai",
        "--min-expiry",
        f"{math.ceil(attempt_timeout) + 600}s",
    )
    resources = AuthHelperResources(
        roots,
        Path(credentials_dir),
        **({"audit": cleanup_audit} if cleanup_audit else {}),
    )
    env = {
        "PI_CODING_AGENT_DIR": credentials_dir,
        "PI_SKIP_VERSION_CHECK": "1",
        "PI_TELEMETRY": "0",
        "HOME": str(resources.home),
        "TMPDIR": str(resources.tmp),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": str(install.node.parent),
    }
    session: PipeSession | None = None
    output = bytearray()
    try:
        placement = PlacedProcess()
        child = placement.execute(
            argv,
            cwd=Path(credentials_dir),
            env=env,
            install=install.instance.path,
            attempt=None,
            proxy_port=None,
            pass_fds=install.pass_fds,
            before_release=(
                lambda: before_release(placement.pid, placement.start, placement.unit)
            )
            if before_release
            else None,
        )
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
            total += len(event.stdout) + event.stderr_bytes
            if total > 64 * 1024:
                raise ExecutionError("auth_failed")
            output.extend(event.stdout)
            if event.stdout_eof and event.stderr_eof and event.exit_code is not None:
                if event.exit_code != 0:
                    raise ExecutionError("auth_failed")
                break
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
