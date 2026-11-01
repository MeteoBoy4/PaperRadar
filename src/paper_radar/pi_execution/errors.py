"""启动资源错误只保留封闭原因,不携输入或外部异常。"""

from typing import Literal

ExecutionReason = Literal[
    "snapshot_invalid",
    "sampling_mapping_unavailable",
    "evidence_missing",
    "evidence_mismatch",
    "cwd_evidence_missing",
    "rpc_evidence_missing",
    "model_evidence_missing",
    "cwd_invalid",
    "cwd_not_empty",
    "system_prompt_path",
    "system_prompt_invalid",
    "argv_limit",
    "credentials_invalid",
    "auth_mode_unsupported",
    "auth_failed",
    "auth_timeout",
    "auth_shape",
    "isolation_unavailable",
    "proxy_invalid",
    "resources_invalid",
    "install_unavailable",
    "protocol_unsupported",
    "launch_reused",
    "timeout_invalid",
    "cleanup_failed",
]


class ExecutionError(ValueError):
    def __init__(self, reason: ExecutionReason) -> None:
        self.reason = reason
        super().__init__(reason)
