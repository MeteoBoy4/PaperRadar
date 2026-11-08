"""离线合成 loader 接缝;不运行 Node/Pi,不注册产品策略或处理请求内容。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import Literal, TypedDict


class Category(StrEnum):
    PROMPT = "prompt"
    AUTH_CLI = "auth_cli"
    TLS_CONNECTION = "model_tls_connection"
    PACKET = "model_packet"
    MODEL_HTTP = "model_http"
    MODEL_WARMUP = "model_warmup"
    MODEL_RETRY = "model_retry"
    AUTH_REFRESH_HTTP = "auth_refresh_http"
    AUTH_TLS_CONNECTION = "auth_tls_connection"
    AUTH_PACKET = "auth_packet"
    MODEL_WS_CONNECT = "model_ws_connect"
    MODEL_WS_CREATE = "model_ws_create"


class Role(StrEnum):
    MODEL = "model"
    AUTH = "auth"


AUTH_CATEGORIES = frozenset(
    {
        Category.AUTH_CLI,
        Category.AUTH_REFRESH_HTTP,
        Category.AUTH_TLS_CONNECTION,
        Category.AUTH_PACKET,
    }
)
Dispatch = Callable[[Category], None]


class ObservationRow(TypedDict):
    category: str
    sequence: int
    count: int
    completeness: Literal["complete", "unknown"]


class ObservationBlocked(ValueError):
    """仅受控原因,不携带下游异常或请求数据。"""


class SyntheticSendFailure(ValueError):
    """仅用于无网络合成peer的发送后故障。"""


class SyntheticPeer:
    """实际调用对照,只接受类别;从无 URL/headers/body/token 字段。

    dispatch 是合成运行时待安装的真实可调用接缝。peer 的独立计数在
    _send 内增长,不读取 loader 的事件或计数,也不依赖 sink 是否成功。
    """

    def __init__(self, role: Role) -> None:
        self.role = role
        self._counts: Counter[Category] = Counter()
        self.dispatch: Dispatch = self._send
        self.fail_after_send = False

    @property
    def started(self) -> bool:
        return bool(self._counts)

    def _send(self, category: Category) -> None:
        self._counts[category] += 1
        if self.fail_after_send:
            raise SyntheticSendFailure("synthetic_send_failure")

    def bypass_observer(self, category: Category) -> None:
        """仅用于模拟未覆盖出口的负例,不伪造 loader 事件。"""
        self._send(category)

    def independent_counts(self) -> dict[Category, int]:
        return dict(self._counts)


def independent_reference(*peers: SyntheticPeer) -> dict[Category, int]:
    """合成独立参照。真实运行须另有可信出口参照,不得用loader自数。"""
    counts: Counter[Category] = Counter()
    for peer in peers:
        counts.update(peer.independent_counts())
    return {category: counts[category] for category in Category}


class SyntheticLoader:
    """替换合成peer调用口,拒绝安装不全/晚加载/坏观察或参照不完整。

    不读取原始请求对象。这里只检验可调用接缝安装和失败语义,不是对
    Node HTTP/Undici、固定 Pi 依赖或真实 cgroup 的覆盖证明。
    """

    def __init__(
        self, sink: Callable[[ObservationRow], int | None] | None = None
    ) -> None:
        self._sink = sink
        self._counts: Counter[Category] = Counter()
        self._last_sequence: dict[Category, int] = {}
        self._roles: set[Role] = set()
        self._sequence = 0
        self._invalid = False
        self._finished = False
        self._complete = False

    def attach(self, peer: SyntheticPeer) -> None:
        if (
            self._invalid
            or self._finished
            or peer.started
            or peer.role in self._roles
            or type(peer.role) is not Role
        ):
            self.observation_failed()
            raise ObservationBlocked("observation_unknown")
        previous = peer.dispatch
        self._roles.add(peer.role)

        def observed(category: Category) -> None:
            self._before_send(peer.role, category)
            previous(category)

        peer.dispatch = observed

    def observation_failed(self) -> None:
        self._invalid = True
        self._complete = False

    def _before_send(self, role: Role, category: Category) -> None:
        if self._invalid or self._finished:
            self.observation_failed()
            raise ObservationBlocked("observation_unknown")
        if type(category) is not Category or (
            category in AUTH_CATEGORIES and role is not Role.AUTH
        ):
            self.observation_failed()
            raise ObservationBlocked("observation_unknown")
        if role is Role.AUTH and category not in AUTH_CATEGORIES:
            self.observation_failed()
            raise ObservationBlocked("observation_unknown")
        self._sequence += 1
        self._counts[category] += 1
        self._last_sequence[category] = self._sequence
        if self._sink is not None:
            try:
                # 新字典交给sink,不保存sink对其进行的任意变更。
                acknowledged = self._sink(
                    {
                        "category": category.value,
                        "sequence": self._sequence,
                        "count": self._counts[category],
                        "completeness": "unknown",
                    }
                )
                if type(acknowledged) is not int or acknowledged != self._sequence:
                    raise ObservationBlocked("observation_unknown")
            except Exception:
                self.observation_failed()
                raise ObservationBlocked("observation_unknown") from None
            except BaseException:
                self.observation_failed()
                raise

    def finish(
        self, reference: Mapping[Category, int] | None
    ) -> tuple[ObservationRow, ...]:
        snapshot: dict[Category, int] = {}
        valid_reference = False
        try:
            if reference is not None:
                # 先完整读取为本地快照,后续不再反复访问外部Mapping。
                entries = list(reference.items())
                valid_reference = len(entries) == len(Category) and all(
                    type(category) is Category and type(count) is int and count >= 0
                    for category, count in entries
                )
                if valid_reference:
                    snapshot = dict(entries)
                    valid_reference = set(snapshot) == set(Category)
            if (
                self._finished
                or self._roles != set(Role)
                or not valid_reference
                or any(
                    self._counts[category] != snapshot[category]
                    for category in Category
                )
            ):
                self.observation_failed()
        except Exception:
            # 读取/校验错误与观察失败一样失效,不能泄漏外部异常或再恢复。
            self.observation_failed()
        except BaseException:
            self.observation_failed()
            self._finished = True
            raise
        self._finished = True
        self._complete = not self._invalid
        return tuple(
            {
                "category": category.value,
                "sequence": self._last_sequence.get(category, 0),
                "count": self._counts[category],
                "completeness": "complete" if self._complete else "unknown",
            }
            for category in Category
        )

    def require_complete(self) -> None:
        if not self._finished or not self._complete or self._invalid:
            raise ObservationBlocked("observation_unknown")
