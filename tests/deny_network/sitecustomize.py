"""A2 CLI 集成测试禁止网络。真实 SQLite 可用。"""

from __future__ import annotations

import socket
import ssl  # noqa: F401  # 先定义 SSLSocket 后拦截 socket 构造。
from typing import NoReturn


def _deny_network(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("A2 离线测试不应访问网络")


setattr(socket, "socket", _deny_network)  # noqa: B010
setattr(socket, "create_connection", _deny_network)  # noqa: B010
