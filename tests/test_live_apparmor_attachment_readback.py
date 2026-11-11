"""D1: captured DFA-only export shape with offline sealed bytes, never host raw_data."""

import json
from pathlib import Path

import pytest

from paper_radar.live_evidence.live_apparmor_kernel import (
    AppArmorKernel,
    AppArmorPolicyError,
)
from paper_radar.live_evidence.live_install import json_bytes
from paper_radar.live_evidence.placement_policy import MEMBERS
from tests.test_live_apparmor_kernel import (
    PARSER,
    KernelFixture,
    loaded_profiles,
    sealed,
)
from tests.test_live_apparmor_lifecycle import lifecycle, policy_root


def dfa_profiles() -> dict[str, dict[str, bytes]]:
    # Captured metadata used these handles and exact attach value. The binary/hash
    # here are the existing offline fixture, not a claim to have read root raw_data.
    profiles = loaded_profiles()
    return {
        handle: {**profiles[key], "attach": b"<unknown>\n"}
        for handle, key in (
            ("paperradar-placement-post-v1.237", "entry.1"),
            ("paperradar-placement-pre-v1.238", "entry.0"),
        )
    }


def test_exact_sealed_binary_accepts_kernel_dfa_only_attachment_export() -> None:
    boundary = KernelFixture(dfa_profiles())
    AppArmorKernel(boundary, PARSER).verify(sealed())
    assert boundary.writes == []


def test_dfa_only_exact_check_and_load_reuse_without_kernel_writes() -> None:
    boundary = KernelFixture(dfa_profiles())
    kernel = AppArmorKernel(boundary, PARSER)
    assert kernel.check(sealed()) == "exact"
    assert kernel.load(sealed()) is False
    assert boundary.writes == []


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("raw_data", b"changed-raw-with-original-hash", "apparmor_blob_mismatch"),
        ("raw_sha256", b"d" * 64 + b"\n", "apparmor_blob_mismatch"),
        ("raw_abi", b"v9\n", "apparmor_abi_mismatch"),
        ("mode", b"complain\n", "apparmor_mode_mismatch"),
        ("mode", b"unconfined\n", "apparmor_mode_mismatch"),
        ("attach", b"unknown\n", "apparmor_attachment_mismatch"),
        ("attach", b"<UNKNOWN>\n", "apparmor_attachment_mismatch"),
        ("attach", b" <unknown>\n", "apparmor_attachment_mismatch"),
        ("attach", b"<unknown> \n", "apparmor_attachment_mismatch"),
        ("attach", b"<unknown>\n\n", "apparmor_readback_incomplete"),
        ("attach", b"/usr/bin/python3\n", "apparmor_attachment_mismatch"),
    ],
)
def test_dfa_only_export_still_requires_all_sealed_evidence(
    field: str, value: bytes, reason: str
) -> None:
    boundary = KernelFixture(dfa_profiles())
    boundary.profiles["paperradar-placement-pre-v1.238"][field] = value
    with pytest.raises(AppArmorPolicyError, match=f"^{reason}$") as error:
        AppArmorKernel(boundary, PARSER).verify(sealed())
    assert error.value.kind == (
        "unavailable" if reason == "apparmor_readback_incomplete" else "drift"
    )
    assert boundary.writes == []


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("missing", "apparmor_profile_missing"),
        ("duplicate", "apparmor_profile_set_mismatch"),
        ("extra", "apparmor_profile_set_mismatch"),
    ],
)
def test_dfa_only_export_requires_exact_whole_profile_set(
    change: str, reason: str
) -> None:
    profiles = dfa_profiles()
    if change == "missing":
        del profiles["paperradar-placement-pre-v1.238"]
    else:
        extra = profiles["paperradar-placement-pre-v1.238"].copy()
        if change == "extra":
            extra["name"] = b"unsealed-profile\n"
        profiles["foreign.239"] = extra
    boundary = KernelFixture(profiles)
    with pytest.raises(AppArmorPolicyError, match=f"^{reason}$") as error:
        AppArmorKernel(boundary, PARSER).verify(sealed())
    assert error.value.kind == "drift"
    assert boundary.writes == []


@pytest.mark.parametrize("operation", ["verify", "check", "load", "remove"])
@pytest.mark.parametrize("failure", ["revision", "unreadable"])
def test_dfa_only_metadata_never_replaces_complete_stable_raw_readback(
    operation: str, failure: str
) -> None:
    class UnstableRead(KernelFixture):
        def read_field(self, handle: str, field: str) -> bytes:
            if field == "raw_data":
                if failure == "unreadable":
                    raise PermissionError("synthetic root raw_data denied")
                self.revision_value = b"12\n"
            return super().read_field(handle, field)

    boundary = UnstableRead(dfa_profiles())
    reason = (
        "apparmor_snapshot_changed"
        if failure == "revision"
        else "apparmor_readback_unavailable"
    )
    with pytest.raises(AppArmorPolicyError, match=f"^{reason}$") as error:
        getattr(AppArmorKernel(boundary, PARSER), operation)(sealed())
    assert error.value.kind == "unavailable"
    assert boundary.writes == []


def test_dfa_only_exact_policy_can_be_explicitly_retired() -> None:
    boundary = KernelFixture(dfa_profiles())
    kernel = AppArmorKernel(boundary, PARSER)
    assert kernel.remove(sealed()) is True
    assert kernel.check(sealed()) == "absent"
    assert boundary.writes == [
        ("remove", b"paperradar-placement-post-v1"),
        ("remove", b"paperradar-placement-pre-v1"),
    ]


@pytest.mark.parametrize("marker", ["known", "unknown_identity", "missing"])
@pytest.mark.parametrize("recover", [False, True])
def test_preparing_recovery_keeps_full_seal_and_never_reloads_dfa_policy(
    tmp_path: Path, marker: str, recover: bool
) -> None:
    root = policy_root(tmp_path / "root")
    original_members = {name: (root / name).read_bytes() for name in MEMBERS}
    assert len(original_members) == 11
    gate, boundary = lifecycle(root, tmp_path / "ledger")

    def interrupted_preflight() -> None:
        raise ValueError("placement_preflight_refused")

    with pytest.raises(ValueError, match=r"^placement_preflight_refused$"):
        gate.prepare(interrupted_preflight)
    assert gate.sealed is not None
    original_identity = gate.sealed.identity
    for profile in boundary.profiles.values():
        profile["attach"] = b"<unknown>\n"
    boundary.writes.clear()
    if marker == "unknown_identity":
        record = json.loads(gate.journal.read_bytes())
        record["identity"] = "0" * 64
        gate.journal.write_bytes(json_bytes(record))
    elif marker == "missing":
        gate.journal.unlink()
    marker_before = gate.journal.read_bytes() if gate.journal.exists() else None
    observed: list[str] = []
    if marker == "known":
        gate.prepare(lambda: observed.append("no-secret-preflight"), recover=recover)
        gate.verify()
        assert json.loads(gate.journal.read_bytes()) == {
            "format_version": 1,
            "identity": original_identity,
            "phase": "prepared",
        }
        assert observed == ["no-secret-preflight"]
    else:
        reason = (
            "placement_policy_journal_identity"
            if marker == "unknown_identity"
            else "placement_policy_ownership_unknown"
        )
        with pytest.raises(ValueError, match=f"^{reason}$"):
            gate.prepare(
                lambda: observed.append("no-secret-preflight"), recover=recover
            )
        marker_after = gate.journal.read_bytes() if gate.journal.exists() else None
        assert marker_after == marker_before
        assert observed == []
    assert boundary.writes == []
    assert {name: (root / name).read_bytes() for name in MEMBERS} == original_members
    assert gate.sealed.identity == original_identity
