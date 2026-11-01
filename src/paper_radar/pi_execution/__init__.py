"""固定 Pi 的受控启动资源;不授予 Cwd/Live 执行准入。"""

from typing import TYPE_CHECKING, Any

from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.isolation import (
    ISOLATION_POLICY_VERSION,
    isolation_capability,
)

if TYPE_CHECKING:
    from paper_radar.pi_execution.launcher import (
        LaunchIdentity,
        PreparedLaunch,
        prepare_launch,
    )


from paper_radar.pi_execution.resources import (
    LAUNCH_POLICY_VERSION,
    ExecutionRoots,
    check_credentials_directory,
    check_cwd,
    check_system_prompt,
    expected_cwd_section,
)

__all__ = [
    "ISOLATION_POLICY_VERSION",
    "LAUNCH_POLICY_VERSION",
    "ExecutionError",
    "ExecutionRoots",
    "LaunchIdentity",
    "PreparedLaunch",
    "check_credentials_directory",
    "check_cwd",
    "check_system_prompt",
    "expected_cwd_section",
    "isolation_capability",
    "prepare_launch",
]


def __getattr__(name: str) -> Any:
    if name in {"LaunchIdentity", "PreparedLaunch", "prepare_launch"}:
        from paper_radar.pi_execution import launcher

        return getattr(launcher, name)
    raise AttributeError(name)
