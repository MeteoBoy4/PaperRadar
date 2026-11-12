"""#183 新Live构建公共接缝;旧v1部署与现场资格不作替代。"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.site_collector_support import site_configuration


def test_build_rejects_stale_policy_before_creating_any_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.live_bundle import (
        BundleInputError,
        build_live_bundle,
    )
    from paper_radar.pi_execution.isolation import ISOLATION_POLICY_VERSION
    from paper_radar.pi_execution.resources import LAUNCH_POLICY_VERSION

    site = site_configuration(tmp_path)
    monkeypatch.setattr(
        "paper_radar.pi_supply.activation_history",
        lambda database: [
            SimpleNamespace(
                snapshot_id=site.snapshot_id,
                supply_id=site.binding.supply_id,
                install_id=site.binding.install_id,
            )
        ],
    )
    site = site.model_copy(
        update={
            "binding": replace(
                site.binding,
                launch_policy_version="old",
                isolation_policy_version=ISOLATION_POLICY_VERSION,
            )
        }
    )
    target = tmp_path / "output"
    with pytest.raises(BundleInputError) as caught:
        build_live_bundle(
            target,
            site,
            starts_at=datetime.now(UTC),
            ends_at=datetime.now(UTC) + timedelta(days=14),
            source_root=Path(__file__).resolve().parents[1],
            network_input={},
        )
    assert (
        caught.value.expected["binding.launch_policy_version"] == LAUNCH_POLICY_VERSION
    )
    assert not target.exists()


def test_fixed_synthetic_materials_compile_all_six_requests_without_database(
    tmp_path: Path,
) -> None:
    from paper_radar.live_evidence.live_materials import freeze_materials
    from paper_radar.live_evidence.model_manifest import USES
    from paper_radar.live_evidence.model_worker import build_material_call
    from paper_radar.live_evidence.receipt_v2 import ApprovedPlanV2
    from paper_radar.pi_execution.isolation import ISOLATION_POLICY_VERSION
    from paper_radar.pi_execution.resources import LAUNCH_POLICY_VERSION

    site = site_configuration(tmp_path)
    site = site.model_copy(
        update={
            "binding": replace(
                site.binding,
                launch_policy_version=LAUNCH_POLICY_VERSION,
                isolation_policy_version=ISOLATION_POLICY_VERSION,
            )
        }
    )
    start = datetime(2026, 11, 11, tzinfo=UTC)
    plans = tuple(
        ApprovedPlanV2(
            format_version="v2",
            domain_id="live-177",
            plan_id="model-" + use,
            kind="model_six_cell",
            collector_sha256="a" * 64,
            cases=("model-" + use,),
            starts_at=start,
            ends_at=start + timedelta(days=14),
            max_rounds=6,
            stop_on_first_failure=True,
            max_auth_calls=6,
            max_model_calls=6,
            max_network_requests=0,
        )
        for use in USES
    )
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    cells, members = freeze_materials(
        runtime, site, plans, source_root=Path(__file__).resolve().parents[1]
    )
    assert tuple(cell.use_id for cell in cells) == USES
    assert len(members) > 60
    for cell in cells:
        description, request, snapshot, stage_input, context = build_material_call(
            runtime, cell
        )
        assert description.provider == site.binding.provider
        assert description.model == site.binding.model
        assert description.sampling == site.binding.sampling
        assert description.temperature is None and description.top_p is None
        assert description.thinking_level == cell.use_id.rsplit("-", 1)[1]
        assert request and snapshot.snapshot_id == cell.snapshot_id
        assert stage_input.stage.value == cell.use_id.rsplit("-", 1)[0]
        assert (context is not None) == cell.use_id.startswith("read-")
    assert not list(runtime.rglob("*.sqlite3"))


def test_bundle_freezes_seven_plans_inventory_and_explicit_pending_owner_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib
    import json
    import tarfile

    from paper_radar.live_evidence.live_bundle import build_live_bundle, derive_site
    from paper_radar.live_evidence.model_manifest import parse_manifest
    from paper_radar.live_evidence.receipt import ApprovedPlan
    from paper_radar.live_evidence.receipt_v2 import ApprovedPlanV2

    site = site_configuration(tmp_path)
    monkeypatch.setattr(
        "paper_radar.pi_supply.activation_history",
        lambda database: [
            SimpleNamespace(
                snapshot_id=site.snapshot_id,
                supply_id=site.binding.supply_id,
                install_id=site.binding.install_id,
            )
        ],
    )
    site, _changes = derive_site(site)
    from paper_radar.live_evidence.model_manifest import USES

    site = site.model_copy(update={"claim_uses": USES})

    def freeze(root: Path, source: Path) -> None:
        (root / "python/bin").mkdir(parents=True)
        (root / "python/bin/python3").write_bytes(b"synthetic interpreter")
        (root / "entry.py").write_text("raise SystemExit(2)\n")
        (root / "wrappers").mkdir()

    monkeypatch.setattr("paper_radar.live_evidence.deployment.freeze_runtime", freeze)
    output = tmp_path / "review"
    start = datetime(2026, 11, 11, tzinfo=UTC)
    hashes = build_live_bundle(
        output,
        site,
        starts_at=start,
        ends_at=start + timedelta(days=14),
        source_root=Path(__file__).resolve().parents[1],
        network_input={
            "pool": "28.0.0.0/8",
            "router": "192.168.44.1",
            "outside": "192.0.2.1",
            "nonrouter": "192.0.2.2",
            "udp443": "192.0.2.1",
            "owner_network_applicable": False,
            "owner_window_confirmed": False,
            "owner_statement": "Pending owner review; synthetic test only.",
        },
    )
    assert (
        hashlib.sha256((output / "payload.tar").read_bytes()).hexdigest()
        == hashes["payload.tar"]
    )
    runtime = tmp_path / "extracted"
    with tarfile.open(output / "payload.tar") as archive:
        archive.extractall(runtime, filter="data")
    manifest = parse_manifest((runtime / "model-manifest.json").read_bytes())
    assert len(manifest.cells) == 6
    assert len(list((runtime / "plans").glob("*.json"))) == 7
    assert (
        ApprovedPlan.model_validate_json(
            (runtime / "plan.json").read_bytes()
        ).max_rounds
        == 1
    )
    for source in (runtime / "plans").glob("*.json"):
        assert (
            ApprovedPlanV2.model_validate_json(source.read_bytes()).domain_id
            == "live-177"
        )
    assert (
        json.loads((runtime / "network-owner-confirmation.json").read_bytes())[
            "owner_input"
        ]["owner_window_confirmed"]
        is False
    )
    assert not (runtime / "placement-target-v1.json").exists()
    assert "receive" not in (runtime / "install-live.py").read_text()
    assert "未确认" in (output / "REVIEW.md").read_text()
    assert "NOPASSWD" in (runtime / "sudoers").read_text()
    assert 'model-collect ""' in (runtime / "sudoers").read_text()


@pytest.mark.parametrize(
    "field", ["snapshot_id", "supply_id", "install_id", "isolation_policy_version"]
)
def test_current_binding_mismatches_show_expected_and_leave_no_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    from paper_radar.live_evidence.live_bundle import (
        BundleInputError,
        build_live_bundle,
        derive_site,
    )

    original = site_configuration(tmp_path)
    latest = SimpleNamespace(
        snapshot_id=original.snapshot_id,
        supply_id=original.binding.supply_id,
        install_id=original.binding.install_id,
    )
    monkeypatch.setattr(
        "paper_radar.pi_supply.activation_history", lambda database: [latest]
    )
    current, _ = derive_site(original)
    changed = (
        current.model_copy(update={"snapshot_id": "a" * 64})
        if field == "snapshot_id"
        else current.model_copy(
            update={
                "binding": replace(current.binding, supply_id="stale")
                if field == "supply_id"
                else replace(current.binding, install_id="stale")
                if field == "install_id"
                else replace(current.binding, isolation_policy_version="stale")
            }
        )
    )
    output = tmp_path / "must-not-exist"
    with pytest.raises(BundleInputError) as caught:
        build_live_bundle(
            output,
            changed,
            starts_at=datetime.now(UTC),
            ends_at=datetime.now(UTC) + timedelta(days=14),
            source_root=Path(__file__).resolve().parents[1],
            network_input={},
        )
    key = field if field == "snapshot_id" else "binding." + field
    assert key in caught.value.expected and caught.value.expected[key] != (
        "a" * 64 if field == "snapshot_id" else "stale"
    )
    assert not output.exists()


def test_empty_activation_history_refuses_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.live_bundle import (
        BundleInputError,
        build_live_bundle,
    )

    monkeypatch.setattr("paper_radar.pi_supply.activation_history", lambda database: [])
    with pytest.raises(BundleInputError, match="latest_activation_missing") as caught:
        build_live_bundle(
            tmp_path / "output",
            site_configuration(tmp_path),
            starts_at=datetime.now(UTC),
            ends_at=datetime.now(UTC) + timedelta(days=14),
            source_root=Path(__file__).resolve().parents[1],
            network_input={},
        )
    assert caught.value.expected["binding.launch_policy_version"]
    assert not (tmp_path / "output").exists()


def test_frozen_runtime_cold_entries_reject_arguments_and_ignore_user_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    from tests.live_bundle_support import bundle_model

    staged, _ = bundle_model(tmp_path, monkeypatch, real_freeze=True)
    import hashlib
    import json

    helper_name = "pi_execution/auth_helper.mjs"
    helper = staged / "site-packages/paper_radar" / helper_name
    identity = json.loads((staged / "source-identity.json").read_bytes())
    assert identity["format_version"] == 3
    assert (
        identity["source_auxiliary_sha256"][helper_name]
        == hashlib.sha256(helper.read_bytes()).hexdigest()
    )
    hostile = tmp_path / "hostile"
    hostile.mkdir()
    marker = tmp_path / "imported-user-code"
    for name in ("sitecustomize.py", "usercustomize.py", "paper_radar.py"):
        (hostile / name).write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).touch()\n"
            'raise RuntimeError("HOSTILE")\n'
        )
    (hostile / "evil.pth").write_text(
        f"import pathlib; pathlib.Path({str(marker)!r}).touch()\n"
    )
    environment = {
        "PYTHONPATH": str(hostile),
        "PYTHONHOME": str(hostile),
        "HOME": str(hostile),
        "PATH": str(hostile),
    }
    for action in ("collect", "refresh", "collect-models"):
        result = subprocess.run(
            [
                str(staged / "python/bin/python3"),
                "-I",
                "-S",
                "-B",
                str(staged / "entry.py"),
                action,
                "--arbitrary",
            ],
            cwd=hostile,
            env=environment,
            capture_output=True,
            check=False,
            timeout=15,
        )
        assert result.returncode == 2, result.stderr.decode()
    result = subprocess.run(
        [
            str(staged / "python/bin/python3"),
            "-I",
            "-S",
            "-B",
            str(staged / "install-live.py"),
            "install",
            "--path",
        ],
        cwd=hostile,
        env=environment,
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 2, result.stderr.decode()
    assert not marker.exists()


def test_derive_latest_activation_cannot_silently_change_the_frozen_install_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.live_bundle import BundleInputError, derive_site

    site = site_configuration(tmp_path)
    monkeypatch.setattr(
        "paper_radar.pi_supply.activation_history",
        lambda database: [
            SimpleNamespace(
                snapshot_id="e" * 64, supply_id="new-supply", install_id="new-install"
            )
        ],
    )
    with pytest.raises(
        BundleInputError, match="derived_install_path_mismatch"
    ) as caught:
        derive_site(site)
    assert caught.value.expected["snapshot_id"] == "e" * 64
    assert caught.value.expected["binding.supply_id"] == "new-supply"
    assert site.install_path == tmp_path / "installs/supply/install"


def test_build_refuses_unreviewed_source_guard_before_freezing_or_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from paper_radar.live_evidence.live_bundle import build_live_bundle, derive_site
    from paper_radar.live_evidence.model_manifest import USES

    site = site_configuration(tmp_path).model_copy(update={"claim_uses": USES})
    monkeypatch.setattr(
        "paper_radar.pi_supply.activation_history",
        lambda database: [
            SimpleNamespace(
                snapshot_id=site.snapshot_id,
                supply_id=site.binding.supply_id,
                install_id=site.binding.install_id,
            )
        ],
    )
    site, _ = derive_site(site)
    source = tmp_path / "source"
    fixture = source / "tests/fixtures/live-admission-source-guard-v23.json"
    fixture.parent.mkdir(parents=True)
    reviewed = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "tests/fixtures/live-admission-source-guard-v23.json"
        ).read_bytes()
    )
    reviewed["files"] = {"root.py": "0" * 64}
    fixture.write_text(json.dumps(reviewed))
    (source / "root.py").write_bytes(b"unreviewed frozen root code\n")
    with pytest.raises(ValueError, match="source_guard_mismatch"):
        build_live_bundle(
            tmp_path / "output",
            site,
            starts_at=datetime.now(UTC),
            ends_at=datetime.now(UTC) + timedelta(days=14),
            source_root=source,
            network_input=dict(
                pool="28.0.0.0/8",
                router="192.168.44.1",
                outside="192.0.2.1",
                nonrouter="192.0.2.2",
                udp443="192.0.2.1",
                owner_network_applicable=False,
                owner_window_confirmed=False,
                owner_statement="Pending source guard test.",
            ),
        )
    assert not (tmp_path / "output").exists()
