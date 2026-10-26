"""唯一已交付的来源 HTTP 执行器;整轮 deadline、解压上限及逐跳边界。"""

from __future__ import annotations

import asyncio
import codecs
import re
import time
import zlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol
from urllib.parse import urljoin, urlsplit

import httpx

from paper_radar.fixture_audit.acquisition_models import (
    HTTPFacts,
    HTTPRequestFact,
    SourceReason,
    SourceRequest,
    revalidate_model,
)
from paper_radar.fixture_audit.acquisition_policy import (
    checked_source_url,
    request_url,
    validate_contact,
)
from paper_radar.fixture_audit.errors import FixtureError, FixtureReason

SOURCE_BYTE_LIMIT = 8 * 1024 * 1024
ROUND_DEADLINE_SECONDS = 30.0


@dataclass(frozen=True)
class SourceResponse:
    facts: HTTPFacts
    body: bytes | None = field(default=None, repr=False)


class SourceExecutor(Protocol):
    def fetch(
        self, request: SourceRequest, *, contact_email: str
    ) -> SourceResponse: ...


def _media_type(value: str) -> str | None:
    candidate = value.partition(";")[0].strip().lower()
    return (
        candidate
        if re.fullmatch(r"[a-z0-9.+-]{1,64}/[a-z0-9.+-]{1,64}", candidate)
        else None
    )


def _charset(value: str) -> str | None:
    match = re.search(r"charset\s*=\s*[\"']?([A-Za-z0-9._-]{1,40})", value, re.I)
    if match:
        try:
            return codecs.lookup(match[1]).name
        except LookupError:
            pass
    return None


def _retry_after(value: str | None, now: datetime) -> float | None:
    if value is None:
        return None
    if re.fullmatch(r"[0-9]+", value.strip()):
        try:
            return float(value)
        except ValueError:
            return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.utcoffset() is None:
            return None
        return max(0.0, (parsed - now).total_seconds())
    except (ValueError, OverflowError, TypeError):
        return None


class _Rejected(Exception):
    def __init__(self, reason: SourceReason) -> None:
        self.reason = reason


def effective_decoding(charset: str | None, body: bytes | None) -> str | None:
    if body is None:
        return None
    if charset is not None:
        return charset
    declaration = re.match(
        rb"\s*<\?xml\b[^>]*encoding\s*=\s*[\"']([A-Za-z0-9._-]{1,40})", body
    )
    if declaration:
        try:
            return codecs.lookup(declaration[1].decode("ascii")).name
        except LookupError:
            pass
    return "utf-8"


def body_is_contact_free(body: bytes, decoding: str | None, contact: str) -> bool:
    """仅检查本次联系标识;不能安全解码的内容不进入保留路径。"""
    folded_contact = contact.casefold()
    if folded_contact.encode() in body.lower():
        return False
    try:
        text = body.decode(decoding or "utf-8")
    except (UnicodeError, LookupError, TypeError):
        return False
    return folded_contact not in text.casefold()


class SourceHTTPExecutor:
    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        proxy: str | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        wall_time: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.transport, self.proxy = transport, proxy
        self.monotonic, self.sleep, self.wall_time = monotonic, sleep, wall_time
        self._last_request: dict[str, float] = {}

    def __repr__(self) -> str:
        return "SourceHTTPExecutor(http, bounded=True)"

    def fetch(self, request: SourceRequest, *, contact_email: str) -> SourceResponse:
        contact = validate_contact(contact_email)
        try:
            request = revalidate_model(request, SourceRequest)
        except (ValueError, TypeError, RecursionError):
            raise FixtureError(
                FixtureReason.INVALID_REQUEST, path="source_request"
            ) from None
        return asyncio.run(self._fetch(request, contact))

    async def _fetch(self, request: SourceRequest, contact: str) -> SourceResponse:
        url = request_url(request)
        rejection = checked_source_url(url, request)
        if rejection:
            return SourceResponse(HTTPFacts(reason=rejection))
        facts: list[HTTPRequestFact] = []
        waits, redirects, rounds = 0.0, 0, 0
        content_type: str | None = None
        charset: str | None = None
        status: int | None = None
        reason: SourceReason = "invalid_response"
        body: bytes | None = None
        for round_no in (1, 2):
            rounds = round_no
            current = url
            deadline = self.monotonic() + ROUND_DEADLINE_SECONDS
            retryable, retry_delay = False, 1.0
            try:
                # asyncio timeout bounds real socket I/O as a whole, while the
                # injected monotonic checks make slow-drip tests deterministic.
                async with asyncio.timeout(ROUND_DEADLINE_SECONDS):
                    async with httpx.AsyncClient(
                        trust_env=False,
                        follow_redirects=False,
                        proxy=self.proxy,
                        transport=self.transport,
                        timeout=httpx.Timeout(30.0, connect=10.0),
                        headers={
                            "User-Agent": f"PaperRadar/0.1.0 (contact: {contact})",
                            "Accept-Encoding": "gzip, deflate",
                        },
                    ) as client:
                        for hop in range(6):
                            rejection = checked_source_url(current, request)
                            if rejection:
                                raise _Rejected(rejection)
                            host = urlsplit(current).hostname or ""
                            delay = max(
                                0.0,
                                1.0
                                - (
                                    self.monotonic()
                                    - self._last_request.get(host, float("-inf"))
                                ),
                            )
                            if delay:
                                if delay >= deadline - self.monotonic():
                                    raise _Rejected("deferred_retry_after")
                                await self.sleep(delay)
                                waits += delay
                            remaining = deadline - self.monotonic()
                            if remaining <= 0:
                                raise _Rejected("transient_error")
                            self._last_request[host] = self.monotonic()
                            status = None
                            headers: dict[str, str] = {}
                            conditions = request.conditional_headers
                            if conditions.if_none_match is not None:
                                headers["If-None-Match"] = conditions.if_none_match
                            if conditions.if_modified_since is not None:
                                headers["If-Modified-Since"] = (
                                    conditions.if_modified_since
                                )
                            client.cookies.clear()
                            fact_index = len(facts)
                            facts.append(
                                HTTPRequestFact(
                                    url=current,
                                    round_no=round_no,
                                    redirect_no=hop,
                                    reason="outcome_unknown",
                                    wait_seconds=delay,
                                )
                            )
                            async with client.stream(
                                "GET",
                                current,
                                headers=headers,
                                timeout=httpx.Timeout(
                                    remaining, connect=min(10.0, remaining)
                                ),
                            ) as response:
                                status = response.status_code
                                facts[fact_index] = facts[fact_index].model_copy(
                                    update={"status_code": status}
                                )
                                if self.monotonic() >= deadline:
                                    raise _Rejected("transient_error")
                                if status in (301, 302, 303, 307, 308):
                                    facts[fact_index] = facts[fact_index].model_copy(
                                        update={"reason": "acquired"}
                                    )
                                    target = response.headers.get("location")
                                    if not target or hop == 5:
                                        raise _Rejected("invalid_response")
                                    next_url = urljoin(current, target)
                                    rejection = checked_source_url(next_url, request)
                                    if rejection:
                                        raise _Rejected(rejection)
                                    current = next_url
                                    redirects += 1
                                    continue
                                if status != 200:
                                    reason = (
                                        "access_blocked_403"
                                        if status in (401, 403)
                                        else "not_found"
                                        if status == 404
                                        else "rate_limited"
                                        if status == 429
                                        else "transient_error"
                                        if 500 <= status <= 599
                                        else "acquired"
                                        if status == 304
                                        and conditions.prior_artifact_id is not None
                                        else "invalid_response"
                                    )
                                    retryable = status == 429 or 500 <= status <= 599
                                    delay_value = _retry_after(
                                        response.headers.get("Retry-After"),
                                        self.wall_time(),
                                    )
                                    if delay_value is not None:
                                        retry_delay = delay_value
                                    if retryable and retry_delay > 5:
                                        reason, retryable = (
                                            "deferred_retry_after",
                                            False,
                                        )
                                    facts[fact_index] = facts[fact_index].model_copy(
                                        update={"reason": reason}
                                    )
                                    break
                                content_type = _media_type(
                                    response.headers.get("content-type", "")
                                )
                                charset = _charset(
                                    response.headers.get("content-type", "")
                                )
                                body = await self._body(response, deadline)
                                if not body_is_contact_free(
                                    body, effective_decoding(charset, body), contact
                                ):
                                    body = None
                                    raise _Rejected("invalid_response")
                                reason = "acquired"
                                facts[fact_index] = facts[fact_index].model_copy(
                                    update={"reason": reason}
                                )
                                break
            except _Rejected as error:
                reason, body = error.reason, None
                if facts and facts[-1].round_no == round_no:
                    facts[-1] = facts[-1].model_copy(update={"reason": reason})
            except (httpx.ConnectError, httpx.ConnectTimeout):
                reason, retryable, body = "transient_error", True, None
                if facts:
                    facts[-1] = facts[-1].model_copy(update={"reason": reason})
            except (httpx.HTTPError, TimeoutError, OSError, ValueError, zlib.error):
                reason, body = "transient_error", None
                if facts:
                    facts[-1] = facts[-1].model_copy(update={"reason": reason})
            if not retryable or round_no == 2:
                break
            if retry_delay:
                await self.sleep(retry_delay)
                waits += retry_delay
        rounds = max((item.round_no for item in facts), default=0)
        return SourceResponse(
            HTTPFacts(
                reason=reason,
                requests=tuple(facts),
                round_count=rounds,
                retry_count=max(0, rounds - 1),
                redirect_count=redirects,
                wait_seconds=waits,
                content_type=content_type,
                charset=charset,
                decoding=effective_decoding(charset, body),
                status_code=status,
            ),
            body,
        )

    async def _body(self, response: httpx.Response, deadline: float) -> bytes:
        encoding = response.headers.get("content-encoding", "identity").strip().lower()
        decoder = None
        if not response.is_stream_consumed:
            if encoding == "gzip":
                decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
            elif encoding == "deflate":
                decoder = zlib.decompressobj()
            elif encoding not in ("identity", ""):
                raise _Rejected("invalid_response")
        output = bytearray()
        if response.is_stream_consumed:
            if len(response.content) > SOURCE_BYTE_LIMIT:
                raise _Rejected("invalid_response")
            output.extend(response.content)
        else:
            async for chunk in response.aiter_raw():
                if self.monotonic() >= deadline:
                    raise _Rejected("transient_error")
                pending = chunk
                while pending:
                    if self.monotonic() >= deadline:
                        raise _Rejected("transient_error")
                    if decoder is not None and decoder.eof:
                        if encoding != "gzip":
                            raise _Rejected("invalid_response")
                        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
                    try:
                        decoded = (
                            decoder.decompress(
                                pending, SOURCE_BYTE_LIMIT - len(output) + 1
                            )
                            if decoder is not None
                            else pending
                        )
                    except zlib.error:
                        raise _Rejected("invalid_response") from None
                    if len(output) + len(decoded) > SOURCE_BYTE_LIMIT:
                        raise _Rejected("invalid_response")
                    output.extend(decoded)
                    pending = (
                        (
                            decoder.unused_data
                            if decoder.eof
                            else decoder.unconsumed_tail
                        )
                        if decoder is not None
                        else b""
                    )
            if decoder is not None and not decoder.eof:
                raise _Rejected("invalid_response")
        if self.monotonic() >= deadline:
            raise _Rejected("transient_error")
        return bytes(output)
