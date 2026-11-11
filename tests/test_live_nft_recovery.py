"""D1: nft 失败后的已知 resources 谱系与替换前 dry-run。"""

import json
from pathlib import Path

import pytest

from paper_radar.live_evidence.deployment import file_digests
from paper_radar.live_evidence.live_install import LiveDeployment
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from tests.live_bundle_support import ModelHost, bundle_model
from tests.test_live_resources_replacement import pending


def chained_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[LiveDeployment, ModelHost, bytes]:
    second, host, _, _ = pending(tmp_path, monkeypatch)
    host.fail = "configure"
    with pytest.raises(ValueError, match=r"^model_interruption$"):
        second.install(recover=True)
    raw = second.paths.journal.read_bytes()
    state = json.loads(raw)
    third_root = tmp_path / "third-build"
    third_root.mkdir(mode=0o755)
    staged, _ = bundle_model(
        third_root,
        monkeypatch,
        upgrade_from=(state["payload"], state["manifest"]),
        site_override=SiteConfiguration.model_validate_json(
            (second.paths.runtime / "site.json").read_bytes()
        ),
    )
    host.fail = None
    host.calls.clear()
    return (
        LiveDeployment(
            staged, paths=second.paths, host=host, owner_uid=second.owner_uid
        ),
        host,
        raw,
    )


def test_recover_known_resources_chain_preserves_every_ancestor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deployment, host, journal = chained_pending(tmp_path, monkeypatch)
    paths = deployment.paths
    current = json.loads(journal)
    archives = {
        root: file_digests(root)
        for root in paths.runtime.parent.glob(paths.runtime.name + ".archive-*")
    }
    current_files = file_digests(paths.runtime)
    history = {
        source: source.read_bytes()
        for source in paths.ledger.glob("deployment-v2-history-*.json")
    }
    assert deployment.install(recover=True) == "installed"
    assert all(file_digests(root) == files for root, files in archives.items())
    assert all(source.read_bytes() == raw for source, raw in history.items())
    assert (
        file_digests(
            paths.runtime.with_name(
                paths.runtime.name + ".archive-" + current["payload"]
            )
        )
        == current_files
    )
    assert (
        paths.journal.with_name(
            "deployment-v2-history-" + current["payload"] + ".json"
        ).read_bytes()
        == journal
    )
    assert host.calls.count("stop_resources_anchor") == 1


def test_nft_precheck_failure_precedes_every_replacement_side_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deployment, host, journal, _ = pending(tmp_path, monkeypatch)
    paths = deployment.paths
    resources = {path: path.read_bytes() for path in deployment._resources()}
    inventory = sorted(str(path) for path in paths.ledger.rglob("*"))
    host.calls.clear()
    host.fail = "preflight_nft"
    with pytest.raises(ValueError, match=r"^model_interruption$"):
        deployment.install(recover=True)
    assert paths.journal.read_bytes() == journal
    assert {path: path.read_bytes() for path in resources} == resources
    assert sorted(str(path) for path in paths.ledger.rglob("*")) == inventory
    assert "disable_observation" not in host.calls
    assert "stop_resources_anchor" not in host.calls


@pytest.mark.parametrize(
    "change,reason",
    [
        ("history", "resources_history_identity"),
        ("missing_history", "resources_history_identity"),
        ("ancestor_phase", "resources_interruption_unknown"),
        ("ancestor_pair", "resources_interruption_unknown"),
        ("ancestor_archive", "runtime_member_identity"),
        ("ancestor_source", "resources_execution_history"),
        ("ancestor_epoch", "resources_execution_history"),
    ],
)
def test_unknown_or_executed_ancestor_chain_never_retires(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str, reason: str
) -> None:
    from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
    from paper_radar.live_evidence.live_install import json_bytes
    from paper_radar.live_evidence.model_manifest import parse_manifest
    from paper_radar.live_evidence.normal_auth_refresh import epoch_path

    deployment, host, journal = chained_pending(tmp_path, monkeypatch)
    paths = deployment.paths
    state = json.loads(journal)
    ancestor = state["previous"]
    archive = paths.runtime.with_name(
        paths.runtime.name + ".archive-" + ancestor["payload"]
    )
    history = paths.journal.with_name(
        "deployment-v2-history-" + ancestor["payload"] + ".json"
    )
    if change == "history":
        history.write_bytes(history.read_bytes() + b"\n")
    elif change == "missing_history":
        history.unlink()
    elif change == "ancestor_phase":
        ancestor["phase"] = "installed"
        history.write_bytes(json_bytes(ancestor))
        paths.journal.write_bytes(json_bytes(state))
    elif change == "ancestor_pair":
        ancestor["manifest"] = "0" * 64
        paths.journal.write_bytes(json_bytes(state))
    elif change == "ancestor_archive":
        (archive / "sudoers").write_bytes(b"unknown retained")
    else:
        manifest = parse_manifest((archive / "model-manifest.json").read_bytes())
        if change == "ancestor_source":
            (
                paths.ledger / "inbox" / (manifest.site_plan_id + "-plan.json")
            ).write_bytes(b"unknown execution retained")
        else:
            ledger = EvidenceLedger(
                paths.ledger,
                trust=LedgerTrust(owner_uid=deployment.owner_uid, anchor=tmp_path),
            )
            epoch_path(ledger, manifest).write_bytes(b"unknown epoch retained")
    before = paths.journal.read_bytes()
    host.calls.clear()
    with pytest.raises(ValueError, match="^" + reason + "$"):
        deployment.install(recover=True)
    assert paths.journal.read_bytes() == before
    assert not {"preflight_nft", "disable_observation", "stop_resources_anchor"} & set(
        host.calls
    )
    assert paths.runtime.is_dir() and archive.is_dir()


def test_recovery_keeps_legacy_observation_bytes_and_mode_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import stat

    from paper_radar.live_evidence.ledger import EvidenceLedger
    from paper_radar.live_evidence.observation import CurrentObservation
    from paper_radar.live_evidence.receipt import canonical_bytes
    from paper_radar.live_evidence.types import BindingComponent
    from tests.live_evidence_ledger_support import NOW

    deployment, _, _, _ = pending(tmp_path, monkeypatch, real_freeze=True)
    source = deployment.paths.ledger / "inbox/current-observation.json"
    raw = canonical_bytes(
        CurrentObservation(
            observed_at=NOW,
            binding={key: "b" * 64 for key in BindingComponent},
            checked_components=(),
        )
    )
    source.write_bytes(raw)
    source.chmod(0)
    original = EvidenceLedger._read_source

    # The production caller is root; the offline model explicitly supplies its
    # protected read capability without granting this pytest process privilege.
    def root_read(ledger: EvidenceLedger, path: Path) -> bytes:
        if path == source:
            ledger._protected(path, source=True)
            return raw
        return original(ledger, path)

    monkeypatch.setattr(EvidenceLedger, "_read_source", root_read)
    assert deployment.install(recover=True) == "installed"
    assert stat.S_IMODE(source.stat().st_mode) == 0
    source.chmod(0o644)
    assert source.read_bytes() == raw
