"""宿主侧有界 OAuth 刷新;与沙箱 attempt 资源所有权严格分离。"""

import math
import subprocess
from time import monotonic

from paper_radar.llm.rpc_pipes import PipeSession
from paper_radar.llm.rpc_types import RpcProblem
from paper_radar.pi_execution import isolation
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.process import adopt_process
from paper_radar.pi_supply.protection import InstallUse


def credential_token(
    install: InstallUse,
    credentials_dir: str,
    *,
    attempt_timeout: float,
    timeout: float,
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
    env = {
        "PI_CODING_AGENT_DIR": credentials_dir,
        "PI_SKIP_VERSION_CHECK": "1",
        "PI_TELEMETRY": "0",
        "HOME": credentials_dir,
        "TMPDIR": credentials_dir,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": str(install.node.parent),
    }
    session: PipeSession | None = None
    output = bytearray()
    try:
        child = subprocess.Popen(
            argv,
            cwd=credentials_dir,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            pass_fds=install.pass_fds,
            umask=0o077,
            preexec_fn=isolation.disable_core_dumps,
        )
        session = adopt_process(child)
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
        if session is not None:
            try:
                session.terminate(10)
            except (OSError, RpcProblem):
                raise ExecutionError("auth_failed") from None
