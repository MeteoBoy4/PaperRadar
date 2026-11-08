"""未绑定D1:合成loader实际接缝安装/调用,非Node/Pi运行验收。"""

from typing import cast

import pytest

from scripts.issue167_loader import (
    Category,
    ObservationBlocked,
    ObservationRow,
    Role,
    SyntheticLoader,
    SyntheticPeer,
    SyntheticSendFailure,
    independent_reference,
)


def installed(
    sink: list[ObservationRow] | None = None,
) -> tuple[SyntheticLoader, SyntheticPeer, SyntheticPeer]:
    def acknowledged(row: ObservationRow) -> int:
        assert sink is not None
        sink.append(row)
        return row["sequence"]

    loader = SyntheticLoader(None if sink is None else acknowledged)
    model = SyntheticPeer(Role.MODEL)
    auth = SyntheticPeer(Role.AUTH)
    loader.attach(model)
    loader.attach(auth)
    return loader, model, auth


def test_install_replaces_callable_and_covers_retry_warmup_refresh() -> None:
    emitted: list[ObservationRow] = []
    loader, model, auth = installed(emitted)
    model.dispatch(Category.PROMPT)
    auth.dispatch(Category.AUTH_CLI)
    model.dispatch(Category.TLS_CONNECTION)
    for _ in range(4):
        model.dispatch(Category.PACKET)
    model.dispatch(Category.MODEL_HTTP)
    model.dispatch(Category.MODEL_WARMUP)
    model.dispatch(Category.MODEL_RETRY)
    auth.dispatch(Category.AUTH_REFRESH_HTTP)
    rows = loader.finish(independent_reference(model, auth))
    loader.require_complete()
    counts = {row["category"]: row["count"] for row in rows}
    assert counts == {
        "prompt": 1,
        "auth_cli": 1,
        "model_tls_connection": 1,
        "model_packet": 4,
        "model_http": 1,
        "model_warmup": 1,
        "model_retry": 1,
        "auth_refresh_http": 1,
        "auth_tls_connection": 0,
        "auth_packet": 0,
        "model_ws_connect": 0,
        "model_ws_create": 0,
    }
    assert {row["completeness"] for row in rows} == {"complete"}
    assert [row["sequence"] for row in emitted] == list(range(1, 12))
    assert {row["completeness"] for row in emitted} == {"unknown"}
    assert all(
        set(row) == {"category", "sequence", "count", "completeness"}
        for row in emitted + list(rows)
    )


@pytest.mark.parametrize(
    "category",
    [Category.MODEL_WARMUP, Category.MODEL_RETRY, Category.AUTH_REFRESH_HTTP],
)
def test_independent_peer_detects_bypassed_transport(category: Category) -> None:
    loader, model, auth = installed()
    peer = auth if category is Category.AUTH_REFRESH_HTTP else model
    peer.bypass_observer(category)
    rows = loader.finish(independent_reference(model, auth))
    assert {row["completeness"] for row in rows} == {"unknown"}
    with pytest.raises(ObservationBlocked, match=r"^observation_unknown$"):
        loader.require_complete()
    with pytest.raises(ObservationBlocked, match=r"^observation_unknown$"):
        model.dispatch(Category.MODEL_HTTP)
    assert model.independent_counts().get(Category.MODEL_HTTP, 0) == 0


@pytest.mark.parametrize("bad_reference", ["none", "missing", "bool", "duplicate"])
def test_reference_missing_or_mismatch_blocks(bad_reference: str) -> None:
    loader, model, auth = installed()
    model.dispatch(Category.MODEL_HTTP)
    reference = independent_reference(model, auth)
    if bad_reference == "missing":
        del reference[Category.AUTH_REFRESH_HTTP]
    elif bad_reference == "bool":
        reference[Category.PROMPT] = True
    elif bad_reference == "duplicate":
        reference[Category.MODEL_HTTP] = 0
    rows = loader.finish(None if bad_reference == "none" else reference)
    assert {row["completeness"] for row in rows} == {"unknown"}
    with pytest.raises(ObservationBlocked, match=r"^observation_unknown$"):
        loader.require_complete()


def test_sink_failure_blocks_before_forward_without_external_error_text() -> None:
    def failed(_row: ObservationRow) -> int:
        raise RuntimeError("synthetic-external-text-not-for-output")

    loader = SyntheticLoader(failed)
    model = SyntheticPeer(Role.MODEL)
    auth = SyntheticPeer(Role.AUTH)
    loader.attach(model)
    loader.attach(auth)
    with pytest.raises(ObservationBlocked, match=r"^observation_unknown$") as error:
        model.dispatch(Category.MODEL_HTTP)
    assert str(error.value) == "observation_unknown"
    assert model.independent_counts() == {}
    assert {
        row["completeness"] for row in loader.finish(independent_reference(model, auth))
    } == {"unknown"}


def test_late_load_and_partial_load_cannot_claim_zero() -> None:
    model = SyntheticPeer(Role.MODEL)
    model.dispatch(Category.MODEL_WARMUP)
    loader = SyntheticLoader()
    with pytest.raises(ObservationBlocked, match=r"^observation_unknown$"):
        loader.attach(model)
    partial = SyntheticLoader()
    auth = SyntheticPeer(Role.AUTH)
    partial.attach(auth)
    rows = partial.finish(independent_reference(auth))
    assert {row["completeness"] for row in rows} == {"unknown"}


def test_replacing_dispatch_after_install_is_detected_by_independent_reference() -> (
    None
):
    loader, model, auth = installed()
    model.dispatch = model.bypass_observer
    model.dispatch(Category.MODEL_HTTP)
    assert {
        row["completeness"] for row in loader.finish(independent_reference(model, auth))
    } == {"unknown"}


def test_send_failure_still_counts_dispatch_attempt_not_zero_usage() -> None:
    loader, model, auth = installed()
    model.fail_after_send = True
    with pytest.raises(SyntheticSendFailure, match=r"^synthetic_send_failure$"):
        model.dispatch(Category.MODEL_HTTP)
    rows = loader.finish(independent_reference(model, auth))
    loader.require_complete()
    assert next(row for row in rows if row["category"] == "model_http")["count"] == 1
    # 合成接缝完整不代表模型成功,更不代表真实HTTP/计费事实。


@pytest.mark.parametrize(
    "category", [Category.AUTH_REFRESH_HTTP, cast(Category, "arbitrary-request-detail")]
)
def test_wrong_role_or_unknown_category_never_forwards(category: Category) -> None:
    loader, model, auth = installed()
    with pytest.raises(ObservationBlocked, match=r"^observation_unknown$"):
        model.dispatch(category)
    assert model.independent_counts() == {}
    assert {
        row["completeness"] for row in loader.finish(independent_reference(model, auth))
    } == {"unknown"}


def test_refinalization_and_postfinish_dispatch_invalidate_window() -> None:
    loader, model, auth = installed()
    reference = independent_reference(model, auth)
    loader.finish(reference)
    loader.require_complete()
    with pytest.raises(ObservationBlocked, match=r"^observation_unknown$"):
        model.dispatch(Category.MODEL_HTTP)
    with pytest.raises(ObservationBlocked, match=r"^observation_unknown$"):
        loader.require_complete()
    assert {row["completeness"] for row in loader.finish(reference)} == {"unknown"}


@pytest.mark.parametrize("acknowledgement", [None, 0, True])
def test_missing_or_invalid_sink_acknowledgement_blocks(
    acknowledgement: int | None,
) -> None:
    loader = SyntheticLoader(lambda _row: acknowledgement)
    model = SyntheticPeer(Role.MODEL)
    auth = SyntheticPeer(Role.AUTH)
    loader.attach(model)
    loader.attach(auth)
    with pytest.raises(ObservationBlocked, match=r"^observation_unknown$"):
        model.dispatch(Category.MODEL_HTTP)
    assert model.independent_counts() == {}
    rows = loader.finish(independent_reference(model, auth))
    assert {row["completeness"] for row in rows} == {"unknown"}


def test_duplicate_install_cannot_double_wrap_and_double_count() -> None:
    loader, model, auth = installed()
    with pytest.raises(ObservationBlocked, match=r"^observation_unknown$"):
        loader.attach(model)
    with pytest.raises(ObservationBlocked, match=r"^observation_unknown$"):
        model.dispatch(Category.MODEL_HTTP)
    assert model.independent_counts() == {}
    assert {
        row["completeness"] for row in loader.finish(independent_reference(model, auth))
    } == {"unknown"}


def test_dispatch_failure_before_peer_send_cannot_claim_complete() -> None:
    def failed_before_send(_category: Category) -> None:
        raise SyntheticSendFailure("synthetic_not_sent")

    model = SyntheticPeer(Role.MODEL)
    auth = SyntheticPeer(Role.AUTH)
    # 安装前已有transport函数实际抛错,peer发送口没有执行。
    model.dispatch = failed_before_send
    loader = SyntheticLoader()
    loader.attach(model)
    loader.attach(auth)
    with pytest.raises(SyntheticSendFailure, match=r"^synthetic_not_sent$"):
        model.dispatch(Category.MODEL_HTTP)
    assert model.independent_counts() == {}
    rows = loader.finish(independent_reference(model, auth))
    assert next(row for row in rows if row["category"] == "model_http")["count"] == 1
    assert {row["completeness"] for row in rows} == {"unknown"}
    with pytest.raises(ObservationBlocked, match=r"^observation_unknown$"):
        loader.require_complete()


@pytest.mark.parametrize("failure", ["items", "iteration", "lookup"])
def test_reference_read_failure_is_sticky_unknown_without_external_text(
    failure: str,
) -> None:
    from collections.abc import ItemsView, Iterator, Mapping

    class BrokenReference(Mapping[Category, int]):
        def __iter__(self) -> Iterator[Category]:
            if failure == "iteration":
                raise RuntimeError("synthetic-reference-text-must-not-escape")
            return iter(Category)

        def __len__(self) -> int:
            return len(Category)

        def __getitem__(self, key: Category) -> int:
            if failure == "lookup":
                raise RuntimeError("synthetic-reference-text-must-not-escape")
            return 0

        def items(self) -> ItemsView[Category, int]:
            if failure == "items":
                raise RuntimeError("synthetic-reference-text-must-not-escape")
            return super().items()

    loader, model, auth = installed()
    rows = loader.finish(BrokenReference())
    assert {row["completeness"] for row in rows} == {"unknown"}
    assert all(
        set(row) == {"category", "sequence", "count", "completeness"} for row in rows
    )
    assert "synthetic-reference-text" not in repr(rows)
    with pytest.raises(ObservationBlocked, match=r"^observation_unknown$"):
        loader.require_complete()
    repaired = loader.finish(independent_reference(model, auth))
    assert {row["completeness"] for row in repaired} == {"unknown"}


def test_reference_interrupt_is_preserved_and_cannot_recover_complete() -> None:
    from collections.abc import Iterator, Mapping

    class InterruptedReference(Mapping[Category, int]):
        def __iter__(self) -> Iterator[Category]:
            raise KeyboardInterrupt

        def __len__(self) -> int:
            return len(Category)

        def __getitem__(self, key: Category) -> int:
            return 0

    loader, model, auth = installed()
    with pytest.raises(KeyboardInterrupt):
        loader.finish(InterruptedReference())
    with pytest.raises(ObservationBlocked, match=r"^observation_unknown$"):
        loader.require_complete()
    rows = loader.finish(independent_reference(model, auth))
    assert {row["completeness"] for row in rows} == {"unknown"}
