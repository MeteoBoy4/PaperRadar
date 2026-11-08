"""独立未绑定 A5 原型测试;不取得 Live 产品准入。"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from scripts.issue167_lifecycle import (
    CHECKS,
    SLOTS,
    Binding,
    Receipt,
    Receiver,
    Rejected,
    Slot,
    synthetic_collect,
)

NOW = datetime(2026, 11, 7, tzinfo=UTC)
KEY = b"synthetic-collector-key-never-used-outside-tests"


def binding(slot: Slot = ("boundary", "low")) -> Binding:
    return Binding(
        supply="supply-sentinel",
        install_tree="tree-sentinel",
        node_toolchain="node-sentinel",
        pi_version="1.4.0",
        platform="linux-sentinel",
        host="host-sentinel",
        cwd_ancestors="cwd-sentinel",
        endpoint_policy="endpoint-sentinel",
        launch_policy="launch-sentinel",
        isolation_service="service-sentinel",
        observer="observer-sentinel",
        config_bundle="config-bundle-sentinel",
        slot_config=f"config-{slot[0]}-{slot[1]}",
        proxy_policy="proxy-disabled",
        core_policy="core-sentinel",
        provider="openai",
        model="gpt-6.1-sol",
        protocol="prompt_only",
        sampling="provider_default",
        auth_mode="chatgpt_subscription",
        temperature=None,
        top_p=None,
        stage=slot[0],
        level=slot[1],
    )


def receipt(slot: Slot = ("boundary", "low")) -> Receipt:
    return Receipt("collector-1", "approved-1", "run-1", binding(slot), NOW, CHECKS)


def receiver() -> Receiver:
    return Receiver({"collector-1": KEY}, "approved-1")


def activate_all(authority: Receiver) -> dict[Slot, str]:
    ids = {
        slot: authority.receive(synthetic_collect(receipt(slot), KEY), NOW)
        for slot in SLOTS
    }
    authority.activate(
        frozenset(ids.values()), owner_action="synthetic-owner-approve", now=NOW
    )
    return ids


def test_arbitrary_json_or_boolean_cannot_self_certify() -> None:
    authority = receiver()
    for untrusted in ({"passed": True}, True):
        with pytest.raises(Rejected, match=r"^envelope_untrusted$"):
            authority.receive(untrusted, NOW)  # type: ignore[arg-type]


@pytest.mark.parametrize("tamper", ["signature", "collector", "plan", "checks"])
def test_source_integrity_and_coverage(tamper: str) -> None:
    item = receipt()
    if tamper == "collector":
        item = replace(item, collector="unknown")
    elif tamper == "plan":
        item = replace(item, plan="unapproved")
    elif tamper == "checks":
        item = replace(item, passed_checks=CHECKS - {"session_write_history"})
    envelope = synthetic_collect(item, KEY)
    if tamper == "signature":
        envelope = replace(envelope, receipt=replace(item, run="tampered"))
    expected = {
        "signature": "integrity_invalid",
        "collector": "collector_untrusted",
        "plan": "plan_unapproved",
        "checks": "coverage_incomplete",
    }[tamper]
    with pytest.raises(Rejected, match=rf"^{expected}$"):
        receiver().receive(envelope, NOW)


def test_acceptance_does_not_activate_or_allow_partial_initial_coverage() -> None:
    authority = receiver()
    identity = authority.receive(synthetic_collect(receipt(), KEY), NOW)
    with pytest.raises(Rejected, match=r"^evidence_not_active$"):
        authority.admit(identity, current=binding(), current_checks=CHECKS, now=NOW)
    with pytest.raises(Rejected, match=r"^owner_activation_required$"):
        authority.activate(frozenset({identity}), owner_action=None, now=NOW)
    with pytest.raises(Rejected, match=r"^initial_coverage_incomplete$"):
        authority.activate(
            frozenset({identity}), owner_action="synthetic-owner-approve", now=NOW
        )


def test_six_slots_expire_at_completion_not_activation() -> None:
    authority = receiver()
    ids = activate_all(authority)
    almost = NOW + timedelta(days=30) - timedelta(microseconds=1)
    authority.activate(
        frozenset(ids.values()), owner_action="synthetic-owner-approve", now=almost
    )
    for slot, identity in ids.items():
        authority.admit(
            identity, current=binding(slot), current_checks=CHECKS, now=almost
        )
        with pytest.raises(Rejected, match=r"^evidence_expired$"):
            authority.admit(
                identity,
                current=binding(slot),
                current_checks=CHECKS,
                now=NOW + timedelta(days=30),
            )


@pytest.mark.parametrize(
    "field",
    [
        "supply",
        "install_tree",
        "node_toolchain",
        "platform",
        "host",
        "cwd_ancestors",
        "endpoint_policy",
        "launch_policy",
        "isolation_service",
        "observer",
        "slot_config",
        "level",
        "stage",
    ],
)
def test_each_binding_drift_blocks(field: str) -> None:
    authority = receiver()
    identity = activate_all(authority)[("boundary", "low")]
    drift = "high" if field == "level" else "read" if field == "stage" else "changed"
    with pytest.raises(Rejected, match=r"^binding_drift$"):
        authority.admit(
            identity,
            current=replace(binding(), **{field: drift}),  # type: ignore[arg-type]
            current_checks=CHECKS,
            now=NOW,
        )


def test_current_failure_blocks_even_with_valid_receipt() -> None:
    authority = receiver()
    identity = activate_all(authority)[("boundary", "low")]
    with pytest.raises(Rejected, match=r"^current_conditions_failed$"):
        authority.admit(
            identity,
            current=binding(),
            current_checks=CHECKS - {"core_privacy"},
            now=NOW,
        )


def test_failure_revokes_old_pass_targeted_retest_needs_new_activation() -> None:
    authority = receiver()
    ids = activate_all(authority)
    failed = NOW + timedelta(days=1)
    slot: Slot = ("boundary", "low")
    assert authority.invalidate(affected=frozenset({slot}), observed=failed) == {slot}
    with pytest.raises(Rejected, match=r"^evidence_revoked$"):
        authority.admit(ids[slot], current=binding(), current_checks=CHECKS, now=failed)
    authority.admit(
        ids[("read", "high")],
        current=binding(("read", "high")),
        current_checks=CHECKS,
        now=failed,
    )
    with pytest.raises(Rejected, match=r"^revalidation_required$"):
        authority.receive(synthetic_collect(receipt(), KEY), failed)
    completed = failed + timedelta(hours=1)
    fresh = replace(receipt(), run="run-2", completed=completed)
    identity = authority.receive(synthetic_collect(fresh, KEY), completed)
    with pytest.raises(Rejected, match=r"^evidence_not_active$"):
        authority.admit(
            identity, current=binding(), current_checks=CHECKS, now=completed
        )
    authority.activate(
        frozenset({identity}), owner_action="synthetic-owner-approve", now=completed
    )
    authority.admit(identity, current=binding(), current_checks=CHECKS, now=completed)


def test_unknown_impact_expands_to_all_slots() -> None:
    authority = receiver()
    ids = activate_all(authority)
    assert authority.invalidate(affected=None, observed=NOW) == SLOTS
    for slot, identity in ids.items():
        with pytest.raises(Rejected, match=r"^evidence_revoked$"):
            authority.admit(
                identity, current=binding(slot), current_checks=CHECKS, now=NOW
            )


@pytest.mark.parametrize(
    "completed,reason",
    [
        (NOW + timedelta(seconds=1), "completion_in_future"),
        (NOW - timedelta(days=30), "evidence_expired"),
        (NOW.replace(tzinfo=None), "clock_naive"),
    ],
)
def test_time_rejections(completed: datetime, reason: str) -> None:
    envelope = synthetic_collect(replace(receipt(), completed=completed), KEY)
    with pytest.raises(Rejected, match=rf"^{reason}$"):
        receiver().receive(envelope, NOW)


def test_new_site_requires_all_six_slots_again() -> None:
    authority = receiver()
    activate_all(authority)
    fresh = replace(receipt(), binding=replace(binding(), host="other-host"))
    identity = authority.receive(synthetic_collect(fresh, KEY), NOW)
    with pytest.raises(Rejected, match=r"^initial_coverage_incomplete$"):
        authority.activate(
            frozenset({identity}), owner_action="synthetic-owner-approve", now=NOW
        )


def test_failed_current_conditions_revoke_future_use_of_old_pass() -> None:
    authority = receiver()
    identity = activate_all(authority)[("boundary", "low")]
    with pytest.raises(Rejected, match=r"^current_conditions_failed$"):
        authority.admit(
            identity, current=binding(), current_checks=frozenset(), now=NOW
        )
    with pytest.raises(Rejected, match=r"^evidence_revoked$"):
        authority.admit(identity, current=binding(), current_checks=CHECKS, now=NOW)


def test_six_slots_have_distinct_configs_in_one_common_bundle() -> None:
    authority = receiver()
    ids = activate_all(authority)
    assert len({binding(slot).slot_config for slot in SLOTS}) == 6
    for slot, identity in ids.items():
        authority.admit(identity, current=binding(slot), current_checks=CHECKS, now=NOW)
