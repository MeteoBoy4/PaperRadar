"""D1:失败准备退役只读重放旧完整绑定报告,不继承资格或更改历史。"""

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
from paper_radar.live_evidence.live_install import json_bytes
from paper_radar.live_evidence.model_manifest import ModelManifest, parse_manifest
from paper_radar.live_evidence.normal_auth_refresh import (
    normal_review_path,
    publish_normal_review,
)
from paper_radar.live_evidence.receipt import content_sha256
from paper_radar.live_evidence.types import BindingComponent as B
from tests.preparation_retirement_support import (
    RetirementCase,
    assert_business_unchanged,
    case,
)


def historical_report(model: RetirementCase) -> tuple[Path, Path, ModelManifest]:
    paths = model.gate.paths
    ledger = EvidenceLedger(
        paths.ledger, trust=LedgerTrust(owner_uid=os.getuid(), anchor=paths.anchor)
    )
    manifest = parse_manifest((paths.runtime / "model-manifest.json").read_bytes())
    cells = tuple(
        cell.model_copy(
            update={"binding": {part: "a" * 64 for part in B} | cell.binding}
        )
        for cell in manifest.cells
    )
    bound = manifest.model_copy(update={"cells": cells})
    enrollment = (
        paths.ledger / "inbox" / f"collection-bindings-{content_sha256(manifest)}.json"
    )
    enrollment.write_bytes(
        json_bytes(
            {
                "format_version": 1,
                "manifest_sha256": content_sha256(manifest),
                "site_receipt_sha256": "b" * 64,
                "target_sha256": "c" * 64,
                "owner_confirmation_sha256": manifest.network.owner_confirmation_sha256,
                "bindings": {cell.use_id: cell.binding for cell in cells},
            }
        )
    )
    enrollment.chmod(0o644)
    report = publish_normal_review(ledger, bound, now=datetime.now(UTC))
    assert report.status == "not_assessed" and report.stopped is False
    report_path = normal_review_path(ledger, manifest)
    assert json.loads(report_path.read_bytes())["manifest_sha256"] == content_sha256(
        bound
    )
    return enrollment, report_path, bound


def test_original_bound_report_allows_read_only_check_and_retirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = case(tmp_path, monkeypatch)
    enrollment, report, _ = historical_report(model)
    model.before.update({path: path.read_bytes() for path in (enrollment, report)})
    assert model.gate.check() is True
    assert model.io.writes == []
    assert not model.gate.journal.exists() and not model.gate.snapshot.exists()
    assert_business_unchanged(model)
    assert model.gate.prepare(lambda: None, lambda: None) is True
    assert_business_unchanged(model)


@pytest.mark.parametrize(
    "change",
    [
        "missing-enrollment",
        "wrong-enrollment-manifest",
        "wrong-owner-confirmation",
        "missing-use",
        "extra-use",
        "partial-binding",
        "unknown-binding",
        "invalid-binding-digest",
        "wrong-binding",
        "static-drift",
        "wrong-report-digest",
        "enrollment-null",
        "enrollment-boolean-version",
        "enrollment-float-version",
        "enrollment-extra-field",
        "enrollment-noncanonical",
        "enrollment-mode",
        "enrollment-symlink",
        "enrollment-hardlink",
        "report-null",
        "report-invalid-stopped",
        "report-noncanonical",
        "report-mode",
        "report-symlink",
        "report-hardlink",
    ],
)
def test_untrusted_historical_refresh_refuses_both_public_entries_without_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    model = case(tmp_path, monkeypatch, static_binding=change == "static-drift")
    enrollment, report, bound = historical_report(model)
    value = json.loads(enrollment.read_bytes())
    if change == "missing-enrollment":
        enrollment.unlink()
    elif change == "wrong-enrollment-manifest":
        value["manifest_sha256"] = "f" * 64
    elif change == "wrong-owner-confirmation":
        value["owner_confirmation_sha256"] = "f" * 64
    elif change == "missing-use":
        value["bindings"].pop("read-high")
    elif change == "extra-use":
        value["bindings"]["other-use"] = value["bindings"]["read-high"]
    elif change == "partial-binding":
        value["bindings"]["read-high"].pop(B.OBSERVER)
    elif change == "unknown-binding":
        value["bindings"]["read-high"]["other-component"] = "f" * 64
    elif change == "invalid-binding-digest":
        value["bindings"]["read-high"][B.OBSERVER] = 7
    elif change == "wrong-binding":
        value["bindings"]["read-high"][B.OBSERVER] = "f" * 64
    elif change == "static-drift":
        for binding in value["bindings"].values():
            binding[B.SUPPLY] = "f" * 64
        # 全站一致漂移且report摘要也匹配,静态子集检查须独立拒绝。
        cells = tuple(
            cell.model_copy(update={"binding": cell.binding | {B.SUPPLY: "f" * 64}})
            for cell in bound.cells
        )
        changed = json.loads(report.read_bytes())
        changed["manifest_sha256"] = content_sha256(
            bound.model_copy(update={"cells": cells})
        )
        report.write_bytes(json_bytes(changed))
    elif change == "wrong-report-digest":
        changed = json.loads(report.read_bytes())
        changed["manifest_sha256"] = "f" * 64
        report.write_bytes(json_bytes(changed))
    elif change == "enrollment-boolean-version":
        value["format_version"] = True
    elif change == "enrollment-float-version":
        value["format_version"] = 1.0
    elif change == "enrollment-extra-field":
        value["observation"] = "not part of the historical source"
    if change in {
        "wrong-enrollment-manifest",
        "wrong-owner-confirmation",
        "missing-use",
        "extra-use",
        "partial-binding",
        "unknown-binding",
        "invalid-binding-digest",
        "wrong-binding",
        "static-drift",
        "enrollment-boolean-version",
        "enrollment-float-version",
        "enrollment-extra-field",
    }:
        enrollment.write_bytes(json_bytes(value))
    if change.endswith("-null"):
        (enrollment if change.startswith("enrollment") else report).write_bytes(
            b"null\n"
        )
    elif change == "report-invalid-stopped":
        changed = json.loads(report.read_bytes())
        changed["stopped"] = "false"
        report.write_bytes(json_bytes(changed))
    elif change.endswith("-noncanonical"):
        target = enrollment if change.startswith("enrollment") else report
        target.write_bytes(target.read_bytes().rstrip(b"\n"))
    elif change.endswith(("-mode", "-symlink", "-hardlink")):
        target = enrollment if change.startswith("enrollment") else report
        if change.endswith("-mode"):
            target.chmod(0o666)
        else:
            other = tmp_path / "original-source.json"
            if change.endswith("-symlink"):
                target.rename(other)
                target.symlink_to(other)
            else:
                other.hardlink_to(target)
    # 比较两次拒绝前后的完整文件集合和内容,包括未知/不受信来源。
    before = {
        path: (path.read_bytes(), path.lstat().st_mode, path.lstat().st_nlink)
        for root in (model.gate.paths.runtime, model.gate.paths.ledger, model.old.root)
        for path in root.rglob("*")
        if path.is_file()
    }
    operations: tuple[Callable[[], bool], ...] = (
        model.gate.check,
        lambda: model.gate.prepare(lambda: None, lambda: None),
    )
    for operation in operations:
        with pytest.raises(
            ValueError, match=r"^failed_preparation_refresh_source$"
        ) as error:
            operation()
        assert type(error.value) is ValueError
        assert model.io.writes == []
        assert not model.gate.journal.exists() and not model.gate.snapshot.exists()
        after = {
            path: (path.read_bytes(), path.lstat().st_mode, path.lstat().st_nlink)
            for root in (
                model.gate.paths.runtime,
                model.gate.paths.ledger,
                model.old.root,
            )
            for path in root.rglob("*")
            if path.is_file()
        }
        assert after == before


@pytest.mark.parametrize("stopped_fact", ["normal-review", "global-collection"])
def test_old_stopped_fact_is_preserved_with_original_bound_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stopped_fact: str
) -> None:
    from paper_radar.live_evidence.collection import ProtectedCollection
    from paper_radar.live_evidence.receipt import canonical_bytes

    model = case(tmp_path, monkeypatch)
    enrollment, report_path, bound = historical_report(model)
    paths = model.gate.paths
    ledger = EvidenceLedger(
        paths.ledger, trust=LedgerTrust(owner_uid=os.getuid(), anchor=paths.anchor)
    )
    now = datetime.now(UTC)
    if stopped_fact == "normal-review":
        report = publish_normal_review(ledger, bound, now=now)
        stopped = report.model_copy(
            update={
                "status": "unknown",
                "stopped": True,
                "next_batch": "none",
                "reason": "refresh_not_proven",
            }
        )
        report_path.write_bytes(canonical_bytes(stopped))
        assert publish_normal_review(ledger, bound, now=now).stopped is True
        assert ProtectedCollection(ledger).is_stopped() is False
    else:
        collection = ProtectedCollection(ledger)
        plan = bound.cells[0].plan
        collection.approve_plan(plan, now=now)
        run = collection.start_round(
            plan.plan_id, binding=bound.cells[0].binding, now=now
        )
        collection.reserve(run.round_id, plan.cases[0], "auth", now=now)
        collection.recover_interrupted(now=now)
        assert collection.is_stopped() is True
        assert json.loads(report_path.read_bytes())["stopped"] is False
    model.before.update(
        {path: path.read_bytes() for path in (enrollment, report_path, ledger.database)}
    )
    operations: tuple[Callable[[], bool], ...] = (
        model.gate.check,
        lambda: model.gate.prepare(lambda: None, lambda: None),
    )
    for operation in operations:
        with pytest.raises(ValueError, match=r"^failed_preparation_stopped$"):
            operation()
        assert model.io.writes == []
        assert not model.gate.journal.exists() and not model.gate.snapshot.exists()
        assert_business_unchanged(model)


def test_static_report_without_enrollment_retains_old_retirement_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = case(tmp_path, monkeypatch)
    paths = model.gate.paths
    ledger = EvidenceLedger(
        paths.ledger, trust=LedgerTrust(owner_uid=os.getuid(), anchor=paths.anchor)
    )
    manifest = parse_manifest((paths.runtime / "model-manifest.json").read_bytes())
    publish_normal_review(ledger, manifest, now=datetime.now(UTC))
    report = normal_review_path(ledger, manifest)
    model.before[report] = report.read_bytes()
    assert not tuple((paths.ledger / "inbox").glob("collection-bindings-*.json"))
    assert model.gate.check() is True
    assert model.gate.prepare(lambda: None, lambda: None) is True
    assert_business_unchanged(model)


def test_bound_report_replays_during_explicit_recovery_without_rewriting_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = case(tmp_path, monkeypatch)
    enrollment, report, _ = historical_report(model)
    model.before.update({path: path.read_bytes() for path in (enrollment, report)})

    def interrupted() -> None:
        raise ValueError("synthetic_new_preflight_interruption")

    with pytest.raises(ValueError, match=r"^synthetic_new_preflight_interruption$"):
        model.gate.prepare(interrupted, lambda: None)
    snapshot = model.gate.snapshot.read_bytes()
    with pytest.raises(ValueError, match=r"^failed_preparation_recovery_required$"):
        model.gate.prepare(lambda: None, lambda: None)
    assert model.gate.prepare(lambda: None, lambda: None, recover=True) is True
    assert (
        model.gate.snapshot.read_bytes() == snapshot == model.before[model.old.journal]
    )
    assert [kind for kind, _ in model.io.writes] == ["remove", "remove", "add"]
    assert_business_unchanged(model)
