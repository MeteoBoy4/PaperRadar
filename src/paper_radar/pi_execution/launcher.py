"""固定安装的单次会话工厂;准入事实与任务领取由上层拥有。"""

from __future__ import annotations

import math
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from paper_radar.llm.models import PROTOCOL_PROFILES, CallDescription
from paper_radar.llm.rpc_pipes import PipeSession
from paper_radar.llm.rpc_types import ByteSession, RpcProblem, RpcReason, SessionEvent
from paper_radar.pi_execution.auth import credential_token
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.isolation import (
    ISOLATION_POLICY_VERSION,
    IsolationBoundary,
    isolation_capability,
)
from paper_radar.pi_execution.process import adopt_process
from paper_radar.pi_execution.resources import (
    LAUNCH_POLICY_VERSION,
    AttemptResources,
    ExecutionRoots,
    check_auth_mode,
    check_credentials_directory,
    check_cwd,
    check_system_prompt,
    proxy_port,
)
from paper_radar.pi_supply.errors import SupplyError
from paper_radar.pi_supply.models import SupplyManifest
from paper_radar.pi_supply.protection import InstallUse, inspect_instance, use_install


@dataclass(frozen=True, slots=True)
class LaunchIdentity:
    supply_id: str
    install_id: str
    pi_version: str
    node_version: str
    launch_policy_version: str
    isolation_policy_version: str
    auth_mode: Literal["chatgpt_subscription"]
    credential_provider: Literal["openai"]
    credential_source: Literal["owner_provisioned_dir"]
    proxy_used: bool
    proxy_port: int | None

    @classmethod
    def for_install(
        cls,
        supply_id: str,
        install_id: str,
        manifest: SupplyManifest,
        *,
        auth_mode: str,
        proxy: str | None = None,
    ) -> LaunchIdentity:
        """普通执行身份;供给预绑定与受保护安装分别使用各自已验证的清单。"""
        check_auth_mode("openai", auth_mode)
        return cls(
            supply_id,
            install_id,
            manifest.pi_version,
            manifest.node_version,
            LAUNCH_POLICY_VERSION,
            ISOLATION_POLICY_VERSION,
            "chatgpt_subscription",
            "openai",
            "owner_provisioned_dir",
            proxy is not None,
            proxy_port(proxy),
        )


class _OwnedSession:
    def __init__(self, pipes: PipeSession, resources: AttemptResources) -> None:
        self._pipes = pipes
        self._resources = resources
        self.closed = False

    def pump(self, pending: bytes, timeout: float, /) -> SessionEvent:
        return self._pipes.pump(pending, timeout)

    def close_stdin(self) -> None:
        self._pipes.close_stdin()

    def terminate(self, timeout: float, /) -> None:
        if not self.closed:
            self._pipes.terminate(timeout)
            self._resources.close()
            self.closed = True


class PreparedLaunch(Protocol):
    @property
    def identity(self) -> LaunchIdentity: ...

    def __call__(self, description: CallDescription, /) -> ByteSession: ...

    def close(self) -> None: ...


class _PreparedLaunch:
    """仅 prepare_launch 产生;秘密只存在私有内存中,不进入 repr。"""

    def __init__(
        self,
        database: Path,
        description: CallDescription,
        install: InstallUse,
        roots: ExecutionRoots,
        token: str,
        proxy: str | None,
        auth_mode: str,
    ) -> None:
        self._database = database
        self._description = description
        self._install = install
        self._roots = roots
        self._token: str | None = token
        self._proxy = proxy
        self._used = False
        self._session: _OwnedSession | None = None
        self._identity = LaunchIdentity.for_install(
            install.supply_id,
            install.install_id,
            install.record.manifest,
            auth_mode=auth_mode,
            proxy=proxy,
        )

    @property
    def identity(self) -> LaunchIdentity:
        return self._identity

    def __call__(self, description: CallDescription, /) -> ByteSession:
        if self._used or description != self._description or self._token is None:
            raise RpcProblem(RpcReason.STARTUP_ERROR)
        self._used = True
        resources: AttemptResources | None = None
        try:
            cwd = check_cwd()
            prompt = check_system_prompt(description.system_prompt)
            inspect_instance(
                self._database, self._install.record, self._install.instance
            )
            resources = AttemptResources(self._roots, self._proxy)
            env = {
                "PI_CODING_AGENT_DIR": str(resources.agent),
                "PI_SKIP_VERSION_CHECK": "1",
                "PI_TELEMETRY": "0",
                "PI_OFFLINE": "1",
                "HOME": str(resources.home),
                "TMPDIR": str(resources.tmp),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "PATH": str(self._install.node.parent),
                "OPENAI_API_KEY": self._token,
            }
            argv = (
                str(self._install.node),
                str(self._install.pi),
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
                prompt,
            )
            child = subprocess.Popen(
                argv,
                cwd=cwd,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                umask=0o077,
                pass_fds=self._install.pass_fds,
                preexec_fn=IsolationBoundary(
                    self._install.instance.path,
                    cwd,
                    resources.root,
                    self.identity.proxy_port,
                ),
            )
            self._session = _OwnedSession(adopt_process(child), resources)
            return self._session
        except (OSError, subprocess.SubprocessError, ExecutionError, SupplyError):
            if resources is not None:
                resources.close()
            raise RpcProblem(RpcReason.STARTUP_ERROR) from None
        except BaseException as error:
            # adopt_process 已确认组回收后才重抛原异常;所有权尚未交给会话。
            if resources is not None:
                try:
                    resources.close()
                except ExecutionError:
                    # 目录残留不代表清理成功,也不能把中断改结算为普通失败。
                    if not isinstance(error, (KeyboardInterrupt, SystemExit)):
                        raise
            raise
        finally:
            self._token = None

    def close(self) -> None:
        self._token = None
        if self._session is not None:
            self._session.terminate(10)


@contextmanager
def prepare_launch(
    database: Path,
    description: CallDescription,
    *,
    roots: ExecutionRoots,
    credentials_dir: Path,
    auth_mode: str,
    proxy: str | None = None,
    attempt_timeout: float = 300,
    auth_timeout: float = 30,
) -> Iterator[PreparedLaunch]:
    """领取前刷新是唯一允许的宿主写回;不创建 attempt 或模型会话。"""
    check_auth_mode(description.provider, auth_mode)
    if any(
        type(value) not in (int, float) or not math.isfinite(value) or value <= 0
        for value in (attempt_timeout, auth_timeout)
    ):
        raise ExecutionError("timeout_invalid")
    if PROTOCOL_PROFILES.get(description.pi_version) != description.protocol_profile:
        raise ExecutionError("protocol_unsupported")
    if re.fullmatch(r"[0-9a-f]{64}", description.audit_snapshot_id) is None:
        raise ExecutionError("snapshot_invalid")
    check_cwd()
    check_system_prompt(description.system_prompt)
    check_credentials_directory(credentials_dir, roots)
    proxy_port(proxy)
    isolation_capability()
    prepared: PreparedLaunch | None = None
    try:
        with use_install(database, description.audit_snapshot_id) as install:
            if install.record.manifest.pi_version != description.pi_version:
                raise ExecutionError("protocol_unsupported")
            token = credential_token(
                install,
                str(credentials_dir),
                attempt_timeout=attempt_timeout,
                timeout=auth_timeout,
            )
            prepared = _PreparedLaunch(
                database, description, install, roots, token, proxy, auth_mode
            )
            token = ""
            try:
                yield prepared
            finally:
                prepared.close()
    except SupplyError:
        raise ExecutionError("install_unavailable") from None
