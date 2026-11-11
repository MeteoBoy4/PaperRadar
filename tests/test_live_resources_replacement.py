"""D1: 明确recover只替换可证明未执行的resources中断,保留旧史。"""

import hashlib
import json
import os
from pathlib import Path

import pytest

from paper_radar.live_evidence.deployment import file_digests
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
from paper_radar.live_evidence.live_install import InstallationPaths, LiveDeployment
from tests.live_bundle_support import ModelHost, bundle_model
from tests.live_evidence_ledger_support import NOW, plan


class ResourceHost(ModelHost):
    def check_resources_interruption(
        self, site: object, manifest: object, *, allow_stopped: bool = False
    ) -> None:
        self._call("check_resources_interruption")

    def stop_resources_anchor(self, site: object, manifest: object) -> None:
        self._call("stop_resources_anchor")

    def verify_resources_stopped(self, site: object) -> None:
        self._call("verify_resources_stopped")


def pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, real_freeze: bool = False
) -> tuple[LiveDeployment, ResourceHost, bytes, dict[str, str]]:
    paths = InstallationPaths.for_model(tmp_path)
    (paths.runtime / "wrappers").mkdir(parents=True)
    paths.sudoers.parent.mkdir(parents=True)
    for name in ("collect", "tighten", "owner"):
        raw = ("legacy " + name).encode()
        (paths.runtime / "wrappers" / name).write_bytes(raw)
        entry = paths.executables / ("live-evidence-" + name)
        entry.write_bytes(raw)
        entry.chmod(0o755)
    (paths.runtime / "sudoers").write_bytes(b"legacy sudoers")
    paths.sudoers.write_bytes(b"legacy sudoers")
    paths.sudoers.chmod(0o440)
    raw_manifest = "".join(
        f"{sha}  {name}\n" for name, sha in file_digests(paths.runtime).items()
    ).encode()
    (paths.runtime / "manifest.sha256").write_bytes(raw_manifest)
    (paths.runtime / "payload.sha256").write_text("a" * 64 + "\n")
    first, paths = bundle_model(
        tmp_path,
        monkeypatch,
        real_freeze=real_freeze,
        upgrade_from=("a" * 64, hashlib.sha256(raw_manifest).hexdigest()),
    )
    for member in paths.runtime.rglob("*"):
        member.chmod(0o755 if member.is_dir() else 0o644)
    host = ResourceHost(paths, fail="configure")
    old = LiveDeployment(first, paths=paths, host=host, owner_uid=os.getuid())
    with pytest.raises(ValueError, match=r"^model_interruption$"):
        old.install()
    journal = paths.journal.read_bytes()
    before = file_digests(paths.runtime)
    state = json.loads(journal)
    next_root = tmp_path / "next-build"
    next_root.mkdir(mode=0o755)
    staged, _ = bundle_model(
        next_root,
        monkeypatch,
        real_freeze=real_freeze,
        upgrade_from=(state["payload"], state["manifest"]),
    )
    host.fail = None
    return (
        LiveDeployment(staged, paths=paths, host=host, owner_uid=os.getuid()),
        host,
        journal,
        before,
    )


def test_explicit_resources_replacement_archives_pending_and_preserves_schema1_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deployment, host, journal, before = pending(tmp_path, monkeypatch)
    tools = json.loads((deployment.staged / "deployment.json").read_bytes())[
        "host_tools"
    ]
    assert set(tools) == {
        "/usr/bin/systemctl",
        "/usr/bin/busctl",
        "/usr/bin/loginctl",
        "/usr/sbin/nft",
        "/usr/sbin/visudo",
    }
    assert tools["/usr/bin/busctl"] == {
        "resolved": str(Path("/usr/bin/busctl").resolve()),
        "sha256": hashlib.sha256(Path("/usr/bin/busctl").read_bytes()).hexdigest(),
    }
    ledger = EvidenceLedger(
        deployment.paths.ledger,
        trust=LedgerTrust(owner_uid=os.getuid(), anchor=tmp_path),
    )
    ledger.initialize()
    ledger.approve_plan(plan(), now=NOW)
    database_before = ledger.database.read_bytes()
    retained = deployment.paths.ledger / "collector-history.jsonl"
    retained.write_bytes(
        b'{"at":"2026-11-09T12:00:00+00:00","cases":[],"binding_sha256":"legacy"}\n'
    )
    assert deployment.install(recover=True) == "installed"
    state = json.loads(journal)
    archive = deployment.paths.runtime.with_name(
        deployment.paths.runtime.name + ".archive-" + state["payload"]
    )
    assert file_digests(archive) == before
    assert (
        deployment.paths.journal.with_name(
            "deployment-v2-history-" + state["payload"] + ".json"
        ).read_bytes()
        == journal
    )
    assert retained.read_bytes().endswith(b'"legacy"}\n')
    assert host.calls.count("stop_resources_anchor") == 1
    assert "stop_and_remove" not in host.calls
    assert ledger.show_plan("beta-1") == plan()
    # ModelHost performs the production schema1->2 initialization after configure.
    with ledger.connection() as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (2,)
    assert ledger.database.read_bytes() != database_before


@pytest.mark.parametrize(
    "change,reason",
    [
        ("install", "deployment_identity_conflict"),
        ("runtime_phase", "deployment_identity_conflict"),
        ("target_phase", "deployment_identity_conflict"),
        ("prior_journal", "resources_interruption_unknown"),
        ("journal_upgrade", "resources_interruption_unknown"),
        ("unknown_resource", "deployment_resource_identity"),
        ("unknown_runtime", "runtime_member_identity"),
        ("unknown_archive", "runtime_member_identity"),
        ("target", "resources_target_present"),
        ("old_epoch", "resources_execution_history"),
        ("new_epoch", "resources_execution_history"),
        ("strict_source", "resources_execution_history"),
        ("model_source", "resources_execution_history"),
        ("stopped", "resources_execution_history"),
        ("collector_alias", "resources_execution_history"),
        ("registered_strict", "resources_execution_history"),
        ("registered_model", "resources_execution_history"),
        ("host_unknown", "model_interruption"),
    ],
)
def test_unknown_or_executed_resources_refuse_without_retirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str, reason: str
) -> None:
    from paper_radar.live_evidence.live_install import json_bytes
    from paper_radar.live_evidence.model_manifest import parse_manifest
    from paper_radar.live_evidence.normal_auth_refresh import epoch_path
    from paper_radar.live_evidence.receipt import ApprovedPlan

    deployment, host, _journal, _before = pending(tmp_path, monkeypatch)
    paths = deployment.paths
    state = json.loads(paths.journal.read_bytes())
    manifest = parse_manifest((paths.runtime / "model-manifest.json").read_bytes())
    ledger = EvidenceLedger(
        paths.ledger, trust=LedgerTrust(owner_uid=os.getuid(), anchor=tmp_path)
    )
    if change in {"runtime_phase", "target_phase", "prior_journal"}:
        if change == "prior_journal":
            state["previous"] = {}
        else:
            state["phase"] = change.removesuffix("_phase")
        paths.journal.write_bytes(json_bytes(state))
    elif change == "journal_upgrade":
        import shutil

        original = paths.runtime.with_name(paths.runtime.name + ".archive-" + "a" * 64)
        other = paths.runtime.with_name(paths.runtime.name + ".archive-" + "c" * 64)
        shutil.copytree(original, other)
        (other / "payload.sha256").write_text("c" * 64 + "\n")
        state["upgrade_from"][0] = "c" * 64
        paths.journal.write_bytes(json_bytes(state))
    elif change == "unknown_resource":
        paths.resolver.write_bytes(b"unknown keep")
    elif change in {"unknown_runtime", "unknown_archive"}:
        root = (
            paths.runtime
            if change == "unknown_runtime"
            else paths.runtime.with_name(paths.runtime.name + ".archive-" + "a" * 64)
        )
        extra = root / "unknown"
        extra.write_bytes(b"unknown keep")
        extra.chmod(0o644)
    elif change == "target":
        (paths.ledger / "inbox/placement-target-v1.json").write_bytes(b"unknown keep")
    elif change.endswith("epoch"):
        root = paths.runtime if change == "old_epoch" else deployment.staged
        selected = parse_manifest((root / "model-manifest.json").read_bytes())
        epoch_path(ledger, selected).write_bytes(b"unknown keep")
    elif change in {"strict_source", "model_source", "stopped"}:
        identifier = (
            manifest.site_plan_id
            if change == "strict_source"
            else manifest.cells[0].plan.plan_id
        )
        directory = paths.ledger if change == "stopped" else paths.ledger / "inbox"
        (
            directory
            / (identifier + (".stopped" if change == "stopped" else "-plan.json"))
        ).write_bytes(b"keep history")
    elif change == "collector_alias":
        ledger.initialize()
        ledger.approve_plan(
            plan().model_copy(
                update={
                    "collector_sha256": manifest.collector_sha256,
                }
            ),
            now=NOW,
        )
    elif change.startswith("registered"):
        ledger.initialize()
        approved = (
            ApprovedPlan.model_validate_json((paths.runtime / "plan.json").read_bytes())
            if change == "registered_strict"
            else manifest.cells[0].plan
        )
        if change == "registered_model":
            from paper_radar.live_evidence.collection import ProtectedCollection

            ProtectedCollection(ledger).initialize(now=approved.starts_at)
        ledger.approve_plan(approved, now=approved.starts_at)
    elif change == "host_unknown":
        host.fail = "check_resources_interruption"
    journal_before = paths.journal.read_bytes()
    resources_before = {str(p): p.read_bytes() for p in [paths.resolver, paths.sudoers]}
    host.calls.clear()
    with pytest.raises(ValueError, match=r"^" + reason + "$"):
        deployment.install(recover=change != "install")
    assert paths.journal.read_bytes() == journal_before
    assert {
        str(p): p.read_bytes() for p in [paths.resolver, paths.sudoers]
    } == resources_before
    assert (
        "disable_observation" not in host.calls
        and "stop_resources_anchor" not in host.calls
    )
    assert paths.runtime.is_dir()


@pytest.mark.parametrize(
    "failure",
    ["disable_observation", "stop_resources_anchor", "verify_resources_stopped"],
)
def test_replacement_host_interruptions_resume_with_original_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    deployment, host, journal, before = pending(tmp_path, monkeypatch)
    host.fail = failure
    with pytest.raises(ValueError, match=r"^model_interruption$"):
        deployment.install(recover=True)
    host.fail = None
    assert deployment.install(recover=True) == "installed"
    state = json.loads(journal)
    archive = deployment.paths.runtime.with_name(
        deployment.paths.runtime.name + ".archive-" + state["payload"]
    )
    assert file_digests(archive) == before
    assert (
        deployment.paths.journal.with_name(
            "deployment-v2-history-" + state["payload"] + ".json"
        ).read_bytes()
        == journal
    )


@pytest.mark.parametrize(
    "boundary", ["resource_unlinked", "runtime_archived", "history_published"]
)
def test_filesystem_interruptions_resume_without_rewriting_known_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    deployment, _host, journal, before = pending(tmp_path, monkeypatch)
    paths = deployment.paths
    old = json.loads(journal)
    history = paths.journal.with_name(
        "deployment-v2-history-" + old["payload"] + ".json"
    )
    archive = paths.runtime.with_name(paths.runtime.name + ".archive-" + old["payload"])
    unlink = Path.unlink
    rename = Path.rename
    fired = False

    def unlink_once(path: Path, *args: object, **kwargs: object) -> None:
        nonlocal fired
        unlink(path, *args, **kwargs)
        if boundary == "resource_unlinked" and path == paths.sudoers and not fired:
            fired = True
            raise OSError("simulated crash after unlink")

    def rename_once(path: Path, target: Path) -> Path:
        nonlocal fired
        result = rename(path, target)
        if (
            boundary == "runtime_archived"
            and path == paths.runtime
            and target == archive
            and not fired
        ):
            fired = True
            raise OSError("simulated crash after rename")
        return result

    # A published history, before new journal checkpoint, is recognized by exact bytes.
    if boundary == "history_published":
        from paper_radar.live_evidence.live_install import publish

        publish(history, journal)
        fired = True
    else:
        monkeypatch.setattr(Path, "unlink", unlink_once)
        monkeypatch.setattr(Path, "rename", rename_once)
        with pytest.raises(OSError, match=r"^simulated crash after"):
            deployment.install(recover=True)
    assert fired
    assert deployment.install(recover=True) == "installed"
    assert history.read_bytes() == journal and file_digests(archive) == before


@pytest.mark.parametrize("observer", ["legacy", "pending"])
def test_current_observation_identifies_pending_execution_and_preserves_legacy_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, observer: str
) -> None:
    from paper_radar.live_evidence.observation import CurrentObservation
    from paper_radar.live_evidence.protected_observer import observer_identity
    from paper_radar.live_evidence.receipt import canonical_bytes
    from paper_radar.live_evidence.types import BindingComponent as B

    deployment, host, journal, _before = pending(
        tmp_path, monkeypatch, real_freeze=True
    )
    paths = deployment.paths
    ledger = EvidenceLedger(
        paths.ledger, trust=LedgerTrust(owner_uid=os.getuid(), anchor=tmp_path)
    )
    identity = (
        "b" * 64 if observer == "legacy" else observer_identity(paths.runtime, ledger)
    )
    source = paths.ledger / "inbox/current-observation.json"
    raw = canonical_bytes(
        CurrentObservation(
            observed_at=NOW,
            binding={component: identity for component in B},
            checked_components=(),
        )
    )
    source.write_bytes(raw)
    source.chmod(0o644)
    if observer == "pending":
        host.calls.clear()
        with pytest.raises(ValueError, match=r"^resources_execution_history$"):
            deployment.install(recover=True)
        assert paths.journal.read_bytes() == journal
        assert "disable_observation" not in host.calls
    else:
        assert deployment.install(recover=True) == "installed"
        assert "disable_observation" in host.calls
    assert source.read_bytes() == raw


def test_resources_replacement_preserves_existing_schema2_budget_stop_and_intents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.live_evidence.collection import ProtectedCollection
    from tests.protected_intents_support import intent_log
    from tests.test_live_collection_v2 import BINDING, approved

    deployment, _host, _journal, _before = pending(tmp_path, monkeypatch)
    ledger = EvidenceLedger(
        deployment.paths.ledger,
        trust=LedgerTrust(owner_uid=os.getuid(), anchor=tmp_path),
    )
    ledger.initialize()
    collection = ProtectedCollection(ledger)
    collection.initialize(now=NOW)
    collection.approve_plan(approved(), now=NOW)
    intent_path = tmp_path / "intent-source/pending.jsonl"
    intent_path.parent.mkdir(mode=0o755)
    log, _kernel = intent_log(ledger, monkeypatch, path=intent_path)
    log.append(b'{"refusal":"existing_legacy_failure"}')
    run = collection.start_round("live-plan", binding=BINDING, now=NOW)
    collection.reserve(run.round_id, "auth-model", "auth", now=NOW)
    collection.reserve(run.round_id, "auth-model", "model", now=NOW)
    collection.recover_interrupted(now=NOW)
    status = collection.status("live-plan", now=NOW)
    assert status.network_used == 1 and status.model_used == 1
    assert status.stopped and status.failed_rounds == 1
    database = ledger.database.read_bytes()
    audit = ledger.audit()
    intents = log.path.read_bytes()
    records = log.read(ledger)
    assert deployment.install(recover=True) == "installed"
    assert ProtectedCollection(ledger).status("live-plan", now=NOW) == status
    assert ledger.database.read_bytes() == database and ledger.audit() == audit
    assert log.path.read_bytes() == intents and log.read(ledger) == records
