"""D1: report all independent failures before any policy mutation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from paper_radar.live_evidence.live_host import LinuxLiveHost
from paper_radar.live_evidence.live_install import InstallationPaths


class HostModel(LinuxLiveHost):
    """Fixed host IO replay; report orchestration remains production code."""

    def __init__(self, tmp_path: Path) -> None:
        super().__init__(
            InstallationPaths.for_model(tmp_path), source=tmp_path / "stage"
        )
        self.fail: set[str] = set()
        self.queries: list[tuple[str, ...]] = []
        self.native_calls = 0
        self.policy_state = "exact"

    def _verify_prerequisite_source(self, root: Path, site: Any, manifest: Any) -> None:
        self.check("source")

    def _failed_preparation_void(self, root: Path) -> Any:
        return None

    def _verify_host_identity(self, site: Any) -> None:
        self.check("tools")

    def _verify_product_processes(self, site: Any) -> None:
        self.check("idle")

    def _preflight_target(self) -> Any:
        self.check("anchor")
        return SimpleNamespace(anchor_pid=42)

    def validate_sudoers(self, path: Path) -> None:
        self.check("sudoers")

    def _check_nft_program(self, target: Any, manifest: Any) -> None:
        self.check("nft")

    def _run(self, argv: tuple[str, ...], **kwargs: Any) -> bytes:
        self.queries.append(argv)
        label = (
            "linger"
            if "show-user" in argv
            else "anchor_active"
            if "is-active" in argv
            else "manager"
        )
        self.check(label)
        return (
            b"yes\n"
            if label == "linger"
            else b"active\n"
            if label == "anchor_active"
            else b"running\n"
        )

    def check(self, label: str) -> None:
        if label in self.fail:
            raise ValueError("SECRET hostile unchecked exception")


@pytest.fixture
def report_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> HostModel:
    model = HostModel(tmp_path)
    sealed = SimpleNamespace()

    def lifecycle(root: Path) -> Any:
        model.check("seal")
        return SimpleNamespace(sealed=sealed, check=lambda **kwargs: model.policy_state)

    monkeypatch.setattr(model, "_placement_lifecycle", lifecycle)
    from paper_radar.live_evidence import placement_policy

    monkeypatch.setattr(
        placement_policy, "verify_host_security", lambda value: model.check("security")
    )

    def native(*args: Any, **kwargs: Any) -> None:
        assert kwargs["preserve_boot_marker"] is True
        model.native_calls += 1
        model.check("native")

    monkeypatch.setattr(placement_policy, "native_preflight", native)
    return model


def run_report(model: HostModel) -> dict[str, Any]:
    site: Any = SimpleNamespace(product_uid=1000)
    manifest: Any = SimpleNamespace()
    values = model.prerequisite_report(model.source, site, manifest)
    return {value.name: value for value in values}


def test_independent_failures_are_aggregated_without_native_or_secret_text(
    report_model: HostModel,
) -> None:
    report_model.fail = {"security", "manager", "sudoers", "nft", "idle"}
    report = run_report(report_model)
    assert [name for name, value in report.items() if value.status == "fail"] == [
        "host_security",
        "manager_state",
        "product_idle",
        "sudoers",
        "nft",
    ]
    assert report["linger"].status == report["anchor_active"].status == "pass"
    assert len(report_model.queries) == 3
    assert report["native_scope_trace"].status == "blocked"
    assert report_model.native_calls == 0
    assert "SECRET" not in repr(report)


def test_untrusted_source_blocks_all_host_checks(report_model: HostModel) -> None:
    report_model.fail = {"source"}
    report = run_report(report_model)
    assert report["source_tree"].status == "fail"
    assert all(
        value.status == "blocked"
        for name, value in report.items()
        if name != "source_tree"
    )
    assert report_model.queries == []
    assert report_model.native_calls == 0


def test_missing_policy_is_pending_never_successful_native(
    report_model: HostModel,
) -> None:
    report_model.policy_state = "absent"
    report = run_report(report_model)
    assert report["placement_policy"].status == "pass"
    assert report["native_scope_trace"].status == "pending"
    assert report_model.native_calls == 0


def test_exact_policy_and_dependencies_run_full_native(report_model: HostModel) -> None:
    report = run_report(report_model)
    assert all(value.status == "pass" for value in report.values())
    assert report_model.native_calls == 1


def test_missing_anchor_explicitly_blocks_dependent_nft_and_native(
    report_model: HostModel,
) -> None:
    report_model.fail = {"anchor"}
    report = run_report(report_model)
    assert report["anchor_target"].status == "fail"
    assert report["nft"].status == report["native_scope_trace"].status == "blocked"
    assert report["sudoers"].status == "pass"


def test_native_failure_is_reported_as_failure(report_model: HostModel) -> None:
    report_model.fail = {"native"}
    report = run_report(report_model)
    assert report["native_scope_trace"].status == "fail"
    assert report_model.native_calls == 1


def test_selected_failed_policy_is_pending_and_independent_resource_failures_aggregate(
    report_model: HostModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    def resources() -> None:
        raise ValueError("SECRET resource drift")

    def quota() -> None:
        raise ValueError("SECRET quota drift")

    gate = SimpleNamespace(
        check=lambda **kwargs: True,
        verify_main_resources=resources,
        verify_zero_operation_baseline=quota,
    )
    monkeypatch.setattr(report_model, "_failed_preparation_void", lambda root: gate)
    report = run_report(report_model)
    assert (
        report["main_resources"].status
        == report["zero_operation_baseline"].status
        == "fail"
    )
    assert report["native_scope_trace"].status == "blocked"
    assert report_model.native_calls == 0


def test_authenticated_selected_failed_policy_waits_for_transaction(
    report_model: HostModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = SimpleNamespace(
        check=lambda **kwargs: True,
        verify_main_resources=lambda: None,
        verify_zero_operation_baseline=lambda: None,
    )
    monkeypatch.setattr(report_model, "_failed_preparation_void", lambda root: gate)
    report = run_report(report_model)
    assert report["placement_policy"].status == "pass"
    assert report["native_scope_trace"].status == "pending"
    assert report_model.native_calls == 0


def test_unknown_kernel_identity_is_failure_and_never_transaction_pending(
    report_model: HostModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unknown(**kwargs: Any) -> str:
        raise ValueError("placement_kernel_unknown")

    monkeypatch.setattr(
        report_model,
        "_placement_lifecycle",
        lambda root: SimpleNamespace(sealed=object(), check=unknown),
    )
    report = run_report(report_model)
    assert report["placement_policy"].status == "fail"
    assert report["native_scope_trace"].status == "blocked"
    assert report_model.native_calls == 0


def test_untrusted_seal_blocks_all_host_queries(report_model: HostModel) -> None:
    report_model.fail = {"seal"}
    report = run_report(report_model)
    assert report["placement_seal"].status == "fail"
    assert all(
        value.status == "blocked"
        for name, value in report.items()
        if name not in {"source_tree", "placement_seal"}
    )
    assert report_model.queries == []


def test_prepared_void_cannot_turn_missing_policy_into_expected_pending(
    report_model: HostModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    report_model.policy_state = "absent"
    gate = SimpleNamespace(
        check=lambda **kwargs: False,
        verify_main_resources=lambda: None,
        verify_zero_operation_baseline=lambda: None,
    )
    monkeypatch.setattr(report_model, "_failed_preparation_void", lambda root: gate)
    report = run_report(report_model)
    assert report["placement_policy"].status == "fail"
    assert report["native_scope_trace"].status == "blocked"


def test_report_retains_only_finite_native_checkpoint(
    report_model: HostModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence import placement_policy

    def fail(*args: Any, **kwargs: Any) -> None:
        raise placement_policy.PlacementPreflightRefusal("pre_post")

    monkeypatch.setattr(placement_policy, "native_preflight", fail)
    report = run_report(report_model)
    assert report["native_scope_trace"].status == "fail"
    assert report["native_scope_trace"].reason == "native_checkpoint:pre_post"
