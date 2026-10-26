"""来源 HTTP 外部边界:固定路由、原始字节与有界执行。"""

import gzip
from collections.abc import AsyncIterator

import httpx
import pytest

from paper_radar.fixture_audit.acquisition_models import SourceRequest
from paper_radar.fixture_audit.source_http import SourceHTTPExecutor


def test_gzip_feed_is_decoded_before_byte_identity_and_contact_is_ephemeral() -> None:
    seen: list[httpx.Request] = []
    raw = b"<rss><channel><title>fixed feed</title></channel></rss>"

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert (
            request.headers["user-agent"]
            == "PaperRadar/0.1.0 (contact: audit@example.org)"
        )
        assert "cookie" not in request.headers
        assert "authorization" not in request.headers
        return httpx.Response(
            200,
            headers={
                "Content-Encoding": "gzip",
                "Content-Type": "application/rss+xml; charset=utf-8",
                "Set-Cookie": "secret=value",
            },
            stream=httpx.ByteStream(gzip.compress(raw)),
        )

    result = SourceHTTPExecutor(transport=httpx.MockTransport(handler)).fetch(
        SourceRequest(journal="aies", route="feed"),
        contact_email="audit@example.org",
    )
    assert result.body == raw
    assert result.facts.reason == "acquired"
    assert result.facts.physical_requests == 1
    assert result.facts.charset == "utf-8"
    assert len(seen) == 1
    assert "audit@example.org" not in repr(result)
    assert "secret" not in repr(result)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.waits: list[float] = []

    def monotonic(self) -> float:
        return self.value

    async def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.value += seconds


def test_redirects_do_not_spend_the_single_retry_or_send_response_cookies() -> None:
    clock = FakeClock()
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert "cookie" not in request.headers
        if len(calls) == 1:
            return httpx.Response(
                302,
                headers={"Location": str(request.url), "Set-Cookie": "secret=value"},
            )
        if len(calls) == 2:
            return httpx.Response(503, headers={"Retry-After": "2"})
        return httpx.Response(404)

    result = SourceHTTPExecutor(
        transport=httpx.MockTransport(handler),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    ).fetch(
        SourceRequest(journal="jgr", route="feed"), contact_email="audit@example.org"
    )
    assert result.facts.reason == "not_found"
    assert result.facts.physical_requests == 3
    assert result.facts.round_count == 2
    assert result.facts.retry_count == 1
    assert result.facts.redirect_count == 1
    assert clock.waits == [1.0, 2.0]
    assert [fact.round_no for fact in result.facts.requests] == [1, 1, 2]


def test_connect_errors_stop_after_exactly_two_rounds_and_hide_exception_text() -> None:
    clock = FakeClock()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("secret audit@example.org", request=request)

    result = SourceHTTPExecutor(
        transport=httpx.MockTransport(handler),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    ).fetch(
        SourceRequest(journal="aies", route="feed"), contact_email="audit@example.org"
    )
    assert result.facts.reason == "transient_error"
    assert result.facts.physical_requests == 2
    assert result.facts.round_count == 2
    assert result.facts.retry_count == 1
    assert "secret" not in repr(result)


def test_gzip_bomb_aborts_on_decompressed_limit_and_exact_limit_is_valid() -> None:
    from paper_radar.fixture_audit.source_http import SOURCE_BYTE_LIMIT

    for size, reason in [
        (SOURCE_BYTE_LIMIT, "acquired"),
        (SOURCE_BYTE_LIMIT + 1, "invalid_response"),
    ]:
        compressed = gzip.compress(b"x" * size)
        result = SourceHTTPExecutor(
            transport=httpx.MockTransport(
                lambda request, compressed=compressed: httpx.Response(
                    200,
                    headers={"Content-Encoding": "gzip"},
                    stream=httpx.ByteStream(compressed),
                )
            )
        ).fetch(
            SourceRequest(journal="aies", route="feed"),
            contact_email="audit@example.org",
        )
        assert result.facts.reason == reason
        assert result.facts.physical_requests == 1
        assert (len(result.body) if result.body is not None else None) == (
            size if reason == "acquired" else None
        )


def test_total_deadline_stops_slow_drip_even_when_each_chunk_arrives() -> None:
    clock = FakeClock()

    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            for _ in range(100):
                clock.value += 10
                yield b"x"

    result = SourceHTTPExecutor(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, stream=SlowStream())
        ),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    ).fetch(
        SourceRequest(journal="aies", route="feed"), contact_email="audit@example.org"
    )
    assert result.facts.reason == "transient_error"
    assert result.facts.physical_requests == 1
    assert result.facts.retry_count == 0
    assert clock.value == 30
    assert result.body is None


@pytest.mark.parametrize(
    ("status", "retry_after", "reason", "requests"),
    [
        (403, None, "access_blocked_403", 1),
        (404, None, "not_found", 1),
        (429, "6", "deferred_retry_after", 1),
        (429, "0", "rate_limited", 2),
        (503, "bad-date", "transient_error", 2),
        (304, None, "invalid_response", 1),
    ],
)
def test_statuses_have_finite_retries_and_never_keep_failure_bodies(
    status: int,
    retry_after: str | None,
    reason: str,
    requests: int,
) -> None:
    clock = FakeClock()
    result = SourceHTTPExecutor(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                status,
                headers={"Retry-After": retry_after} if retry_after else {},
                content=b"secret failure body",
            )
        ),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    ).fetch(
        SourceRequest(journal="aies", route="feed"), contact_email="audit@example.org"
    )
    assert result.facts.reason == reason
    assert result.facts.physical_requests == requests
    assert result.body is None
    assert "secret" not in repr(result)


@pytest.mark.parametrize(
    "location,reason",
    [
        (
            "http://journals.ametsoc.org/journalissuetocrss/journals/aies/aies-overview.xml",
            "disallowed_scheme",
        ),
        (
            "https://login.example.org/secret?contact=audit@example.org",
            "disallowed_destination",
        ),
        (
            "https://secret@journals.ametsoc.org/journalissuetocrss/journals/aies/aies-overview.xml",
            "disallowed_destination",
        ),
        (
            "https://journals.ametsoc.org/journalissuetocrss/journals/aies/../secret",
            "disallowed_destination",
        ),
    ],
)
def test_every_redirect_rechecks_the_route_without_persisting_rejected_target(
    location: str, reason: str
) -> None:
    result = SourceHTTPExecutor(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(302, headers={"Location": location})
        )
    ).fetch(
        SourceRequest(journal="aies", route="feed"), contact_email="audit@example.org"
    )
    assert result.facts.reason == reason
    assert result.facts.physical_requests == 1
    assert result.facts.redirect_count == 0
    assert "secret" not in repr(result)
    assert "audit@example.org" not in repr(result)


def test_redirect_loop_stops_after_five_followed_hops() -> None:
    clock = FakeClock()
    result = SourceHTTPExecutor(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(302, headers={"Location": str(request.url)})
        ),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    ).fetch(
        SourceRequest(journal="aies", route="feed"), contact_email="audit@example.org"
    )
    assert result.facts.reason == "invalid_response"
    assert result.facts.redirect_count == 5
    assert result.facts.physical_requests == 6
    assert result.facts.retry_count == 0


def test_http_date_retry_after_is_resolved_without_saving_header_values() -> None:
    from datetime import UTC, datetime

    clock = FakeClock()
    result = SourceHTTPExecutor(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                429, headers={"Retry-After": "Mon, 26 Oct 2026 00:00:06 GMT"}
            )
        ),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        wall_time=lambda: datetime(2026, 10, 26, tzinfo=UTC),
    ).fetch(
        SourceRequest(journal="aies", route="feed"), contact_email="audit@example.org"
    )
    assert result.facts.reason == "deferred_retry_after"
    assert result.facts.physical_requests == 1
    assert clock.waits == []


def test_timeouts_are_not_reclassified_as_connect_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.extensions["timeout"]["connect"] <= 10
        assert request.extensions["timeout"]["read"] <= 30
        raise httpx.ReadTimeout("secret", request=request)

    result = SourceHTTPExecutor(transport=httpx.MockTransport(handler)).fetch(
        SourceRequest(journal="aies", route="feed"), contact_email="audit@example.org"
    )
    assert result.facts.reason == "transient_error"
    assert result.facts.physical_requests == 1
    assert result.facts.retry_count == 0


@pytest.mark.parametrize("chunked", [False, True])
def test_all_concatenated_gzip_members_contribute_to_retained_response_bytes(
    chunked: bool,
) -> None:
    first = b"<rss><channel><title>first"
    second = b" and second</title></channel></rss>"
    encoded = gzip.compress(first) + gzip.compress(second)

    class CompressedStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            if chunked:
                for index in range(0, len(encoded), 7):
                    yield encoded[index : index + 7]
            else:
                yield encoded

    response = SourceHTTPExecutor(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, headers={"Content-Encoding": "gzip"}, stream=CompressedStream()
            )
        )
    ).fetch(
        SourceRequest(journal="aies", route="feed"), contact_email="audit@example.org"
    )
    assert response.facts.reason == "acquired"
    assert response.body == first + second


@pytest.mark.parametrize("suffix", [b"not-a-member", b"\x1f\x8b\x08"])
def test_gzip_trailing_bytes_must_be_an_entire_valid_member(suffix: bytes) -> None:
    response = SourceHTTPExecutor(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"Content-Encoding": "gzip"},
                stream=httpx.ByteStream(gzip.compress(b"retained bytes") + suffix),
            )
        )
    ).fetch(
        SourceRequest(journal="aies", route="feed"), contact_email="audit@example.org"
    )
    assert response.facts.reason == "invalid_response"
    assert response.body is None


def test_concatenated_gzip_members_share_one_decompressed_byte_limit() -> None:
    from paper_radar.fixture_audit.source_http import SOURCE_BYTE_LIMIT

    encoded = gzip.compress(b"x" * SOURCE_BYTE_LIMIT) + gzip.compress(b"y")
    response = SourceHTTPExecutor(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"Content-Encoding": "gzip"},
                stream=httpx.ByteStream(encoded),
            )
        )
    ).fetch(
        SourceRequest(journal="aies", route="feed"), contact_email="audit@example.org"
    )
    assert response.facts.reason == "invalid_response"
    assert response.body is None


def test_contact_check_rejects_text_that_cannot_be_safely_decoded() -> None:
    response = SourceHTTPExecutor(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"Content-Type": "text/html; charset=utf-16"},
                stream=httpx.ByteStream(b"\x01"),
            )
        )
    ).fetch(
        SourceRequest(journal="jgr", route="publisher", doi="10.1029/example"),
        contact_email="audit@example.org",
    )
    assert response.facts.reason == "invalid_response"
    assert response.facts.physical_requests == 1
    assert response.body is None
