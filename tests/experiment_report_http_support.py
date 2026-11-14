"""仅修改合成HTTP来源题名;验证报告不会创建非受控链接。"""

from collections.abc import Callable

import httpx
import pytest


def unsafe_title_transport(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    state = {"title": "[PRIVATE_SYNTHETIC_TITLE](file:///PRIVATE_PATH) `PRIVATE_TICKS`"}
    original = httpx.MockTransport.__init__

    def initialize(
        self: httpx.MockTransport, handler: Callable[[httpx.Request], httpx.Response]
    ) -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            response = handler(request)
            if (
                response.status_code == 200
                and "PRIVATE_SYNTHETIC_TITLE" in response.text
            ):
                return httpx.Response(
                    response.status_code,
                    content=response.content.replace(
                        b"PRIVATE_SYNTHETIC_TITLE", state["title"].encode()
                    ),
                    headers={
                        key: value
                        for key, value in response.headers.items()
                        if key != "content-length"
                    },
                )
            return response

        original(self, respond)

    monkeypatch.setattr(httpx.MockTransport, "__init__", initialize)
    return state
