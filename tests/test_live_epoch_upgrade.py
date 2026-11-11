"""D1: installed升级保留原部署UTC,不迁移资格或清除执行历史。"""

import json
import os
import shutil
import sys
import tarfile
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from paper_radar.live_evidence import deployment as runtime_deployment
from paper_radar.live_evidence.collection import CollectionStatus, ProtectedCollection
from paper_radar.live_evidence.epoch_lineage import EpochUpgrade, describe_epoch_upgrade
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError, LedgerTrust
from paper_radar.live_evidence.live_bundle import build_live_bundle
from paper_radar.live_evidence.live_install import (
    InstallationPaths,
    LiveDeployment,
    digest,
    json_bytes,
)
from paper_radar.live_evidence.model_manifest import (
    ModelManifest,
    ModelManifestV2,
    parse_manifest,
)
from paper_radar.live_evidence.normal_auth_refresh import (
    InheritedAuthEpoch,
    epoch_path,
    initialize_epoch,
    read_epoch,
    review_normal_refresh,
)
from paper_radar.live_evidence.receipt import WireModel, canonical_bytes, content_sha256
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from paper_radar.live_evidence.types import BindingComponent
from tests.live_bundle_support import ModelHost, alternate_python_input, bundle_model
from tests.live_evidence_ledger_support import NOW, plan, receipt

BINDING = {part: "b" * 64 for part in BindingComponent}


@pytest.fixture(scope="module")
def source_root() -> Path:
    # 最终完整源码走真实guard、cc与compile-only parser;无需历史Git对象。
    return Path(__file__).resolve().parents[1]


def test_installed_upgrade_without_epoch_source_refuses_before_first_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source_root: Path
) -> None:
    first, paths = bundle_model(tmp_path, monkeypatch, source_root=source_root)
    host = ModelHost(paths)
    assert (
        LiveDeployment(first, paths=paths, host=host, owner_uid=os.getuid()).install()
        == "installed"
    )
    before = paths.journal.read_bytes()
    state = json.loads(before)
    next_root = tmp_path / "next-build"
    next_root.mkdir(mode=0o755)
    staged, _ = bundle_model(
        next_root,
        monkeypatch,
        upgrade_from=(state["payload"], state["manifest"]),
        source_root=source_root,
    )
    with pytest.raises(ValueError, match=r"^epoch_upgrade_required$"):
        LiveDeployment(staged, paths=paths, host=host, owner_uid=os.getuid()).install()
    assert paths.journal.read_bytes() == before
    assert not tuple(paths.ledger.glob("deployment-v2-history-*.json"))
    assert not tuple(paths.runtime.parent.glob(paths.runtime.name + ".archive-*"))


@dataclass
class UpgradeCase:
    deployment: LiveDeployment
    host: ModelHost
    ledger: EvidenceLedger
    old: ModelManifest
    new: ModelManifest
    descriptor: EpochUpgrade
    old_epoch: bytes
    status: CollectionStatus
    source_root: Path

    @property
    def paths(self) -> InstallationPaths:
        return self.deployment.paths


@pytest.fixture
def upgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source_root: Path
) -> UpgradeCase:
    # 两代都冻结完整当前源码;只有合法解释器OS输入字节不同,业务输入不变。
    python_input = alternate_python_input(tmp_path)
    with monkeypatch.context() as freezer_input:
        freezer_input.setattr(sys, "executable", str(python_input))
        first, paths = bundle_model(
            tmp_path, monkeypatch, source_root=source_root, real_freeze=True
        )
    historical_ledger = EvidenceLedger(
        paths.ledger, trust=LedgerTrust(owner_uid=os.getuid(), anchor=tmp_path)
    )
    historical_ledger.initialize()
    for index in range(4):
        approved = plan().model_copy(update={"plan_id": f"historical-{index}"})
        historical_ledger.approve_plan(approved, now=NOW)
        record = receipt().model_copy(
            update={
                "plan_id": approved.plan_id,
                "plan_sha256": content_sha256(approved),
            }
        )
        source = paths.ledger / "inbox" / f"historical-{index}.json"
        source.write_bytes(canonical_bytes(record))
        source.chmod(0o644)
        historical_ledger.receive(source, now=NOW)
    host = ModelHost(paths)
    assert (
        LiveDeployment(first, paths=paths, host=host, owner_uid=os.getuid()).install()
        == "installed"
    )
    old = parse_manifest((first / "model-manifest.json").read_bytes())
    ledger = EvidenceLedger(
        paths.ledger, trust=LedgerTrust(owner_uid=os.getuid(), anchor=tmp_path)
    )
    collection = ProtectedCollection(ledger)
    now = datetime.now(UTC)
    collection.approve_plan(old.negative_plan, now=now)
    run = collection.start_round(old.negative_plan.plan_id, binding=BINDING, now=now)
    collection.cancel_round(run.round_id, now=now)
    status = collection.status(old.negative_plan.plan_id, now=now)
    old_epoch = epoch_path(ledger, old).read_bytes()
    descriptor = describe_epoch_upgrade(first, old_epoch)
    site = SiteConfiguration.model_validate_json((first / "site.json").read_bytes())
    output = tmp_path / "next-review"
    hashes = build_live_bundle(
        output,
        site,
        starts_at=old.network.starts_at,
        ends_at=old.network.ends_at,
        source_root=source_root,
        network_input=json.loads(
            (first / "network-owner-confirmation.json").read_bytes()
        )["owner_input"],
        upgrade_from=(descriptor.payload_sha256, descriptor.runtime_manifest_sha256),
        epoch_upgrade=descriptor,
    )
    staged = tmp_path / "next-staged"
    staged.mkdir(mode=0o755)
    with tarfile.open(output / "payload.tar") as archive:
        archive.extractall(staged, filter="data")
    (staged / "payload.sha256").write_text(hashes["payload.tar"] + "\n")
    for entry in staged.rglob("*"):
        entry.chmod(0o755 if entry.is_dir() or entry.stat().st_mode & 0o111 else 0o644)
    new = parse_manifest((staged / "model-manifest.json").read_bytes())
    assert old.collector_sha256 != new.collector_sha256
    return UpgradeCase(
        LiveDeployment(staged, paths=paths, host=host, owner_uid=os.getuid()),
        host,
        ledger,
        old,
        new,
        descriptor,
        old_epoch,
        status,
        source_root,
    )


def test_upgrade_inherits_exact_epoch_after_canceled_negative_round(
    upgrade: UpgradeCase,
) -> None:
    received = upgrade.ledger.list_received()
    assert len(received) == 4
    assert upgrade.deployment.install() == "installed"
    assert upgrade.ledger.list_received() == received
    epoch = read_epoch(upgrade.ledger, upgrade.new)
    assert isinstance(epoch, InheritedAuthEpoch)
    assert epoch.deployed_at == upgrade.descriptor.deployed_at
    assert epoch.inherited_from == upgrade.descriptor
    assert epoch_path(upgrade.ledger, upgrade.old).read_bytes() == upgrade.old_epoch
    assert (
        ProtectedCollection(upgrade.ledger).status(
            upgrade.old.negative_plan.plan_id, now=datetime.now(UTC)
        )
        == upgrade.status
    )
    assert (
        upgrade.status.network_remaining == 40 and upgrade.status.model_remaining == 40
    )
    original = epoch_path(upgrade.ledger, upgrade.new).read_bytes()
    initialize_epoch(
        upgrade.ledger,
        upgrade.new,
        now=epoch.deployed_at + timedelta(days=8),
        inherited_from=upgrade.descriptor,
    )
    assert epoch_path(upgrade.ledger, upgrade.new).read_bytes() == original
    assert upgrade.deployment.install() == "already_installed"
    review = review_normal_refresh(
        upgrade.ledger, upgrade.new, now=epoch.deployed_at + timedelta(hours=73)
    )
    assert review.target_at == epoch.deployed_at + timedelta(hours=72)
    assert review.status == "not_assessed" and review.sources == ()
    assert review.target_elapsed


def reseal(root: Path) -> None:
    """受测安装器的owner封印输入;不改变任何现有runtime或账本。"""
    members = runtime_deployment.file_digests(root)
    raw = "".join(
        f"{sha}  {name}\n"
        for name, sha in members.items()
        if name not in {"payload.sha256", "manifest.sha256"}
    ).encode()
    (root / "manifest.sha256").write_bytes(raw)
    (root / "payload.sha256").write_text(digest(raw) + "\n")


def snapshot(case: UpgradeCase) -> tuple[bytes, bytes, dict[str, str], tuple[str, ...]]:
    return (
        case.paths.journal.read_bytes(),
        case.ledger.database.read_bytes(),
        runtime_deployment.file_digests(case.paths.runtime),
        tuple(case.host.calls),
    )


@pytest.mark.parametrize(
    "field",
    [
        "epoch_sha256",
        "model_manifest_sha256",
        "first_plan_sha256",
        "runtime_manifest_sha256",
        "payload_sha256",
    ],
)
def test_foreign_epoch_source_refuses_before_writes(
    upgrade: UpgradeCase, field: str
) -> None:
    staged = upgrade.deployment.staged
    value = json.loads((staged / "deployment.json").read_bytes())
    value["epoch_upgrade"][field] = "f" * 64
    (staged / "deployment.json").write_bytes(json_bytes(value))
    reseal(staged)
    before = snapshot(upgrade)
    with pytest.raises(ValueError, match=r"^epoch_upgrade_source$"):
        upgrade.deployment.install()
    assert snapshot(upgrade) == before
    assert not tuple(upgrade.paths.ledger.glob("deployment-v2-history-*.json"))


@pytest.mark.parametrize("change", ["missing", "time", "collector"])
def test_old_epoch_missing_or_changed_refuses_before_writes(
    upgrade: UpgradeCase, change: str
) -> None:
    source = epoch_path(upgrade.ledger, upgrade.old)
    if change == "missing":
        source.unlink()
    else:
        value = json.loads(source.read_bytes())
        value["deployed_at" if change == "time" else "collector_sha256"] = (
            (upgrade.descriptor.deployed_at + timedelta(seconds=1)).isoformat()
            if change == "time"
            else "f" * 64
        )
        source.write_bytes(json_bytes(value))
    before = snapshot(upgrade)
    with pytest.raises(ValueError, match=r"source_untrusted|epoch_upgrade_source"):
        upgrade.deployment.install()
    assert snapshot(upgrade) == before


@pytest.mark.parametrize(
    "failure",
    [
        "disable_observation",
        "stop_and_remove",
        "validate_sudoers",
        "configure",
        "initialize_plans",
    ],
)
def test_upgrade_interruption_reauthenticates_and_resumes_same_epoch(
    upgrade: UpgradeCase, failure: str
) -> None:
    upgrade.host.fail = failure
    with pytest.raises(ValueError, match=r"^model_interruption$"):
        upgrade.deployment.install()
    upgrade.host.fail = None
    assert upgrade.deployment.install(recover=True) == "installed"
    assert (
        read_epoch(upgrade.ledger, upgrade.new).deployed_at
        == upgrade.descriptor.deployed_at
    )
    assert epoch_path(upgrade.ledger, upgrade.old).read_bytes() == upgrade.old_epoch
    assert upgrade.deployment.install() == "already_installed"


def test_retiring_recovery_rejects_fake_previous_before_writes(
    upgrade: UpgradeCase,
) -> None:
    upgrade.host.fail = "disable_observation"
    with pytest.raises(ValueError, match=r"^model_interruption$"):
        upgrade.deployment.install()
    value = json.loads(upgrade.paths.journal.read_bytes())
    value["previous"]["previous"] = dict(value["previous"])
    upgrade.paths.journal.write_bytes(json_bytes(value))
    upgrade.host.fail = None
    before = snapshot(upgrade)
    with pytest.raises(ValueError, match=r"^epoch_upgrade_history$"):
        upgrade.deployment.install(recover=True)
    assert snapshot(upgrade) == before


def test_new_epoch_conflict_is_rejected_before_retiring(upgrade: UpgradeCase) -> None:
    initialize_epoch(
        upgrade.ledger,
        upgrade.new,
        now=upgrade.descriptor.deployed_at + timedelta(hours=1),
    )
    before = snapshot(upgrade)
    with pytest.raises(LedgerError, match=r"^source_untrusted$"):
        upgrade.deployment.install()
    assert snapshot(upgrade) == before


def test_inherited_reader_rechecks_original_source(upgrade: UpgradeCase) -> None:
    upgrade.deployment.install()
    source = epoch_path(upgrade.ledger, upgrade.old)
    source.write_bytes(upgrade.old_epoch + b" ")
    with pytest.raises(LedgerError, match=r"^source_untrusted$"):
        read_epoch(upgrade.ledger, upgrade.new)


@pytest.mark.parametrize(
    "change", ["owner", "shorter", "longer", "product", "model", "supply"]
)
def test_builder_refuses_identity_or_owner_window_drift_before_output(
    upgrade: UpgradeCase, tmp_path: Path, change: str
) -> None:
    old_root = upgrade.paths.runtime
    site = SiteConfiguration.model_validate_json((old_root / "site.json").read_bytes())
    owner = json.loads((old_root / "network-owner-confirmation.json").read_bytes())[
        "owner_input"
    ]
    start, end = upgrade.old.network.starts_at, upgrade.old.network.ends_at
    if change == "owner":
        owner["owner_statement"] += " "
    elif change == "shorter":
        end -= timedelta(seconds=1)
    elif change == "longer":
        end += timedelta(seconds=1)
    elif change == "product":
        site = site.model_copy(update={"product_uid": site.product_uid + 1})
    elif change == "model":
        site = site.model_copy(
            update={"binding": replace(site.binding, model="changed-model")}
        )
    else:
        site = site.model_copy(
            update={"database": site.database.with_name("changed.db")}
        )
    output = tmp_path / "rejected-build"
    with pytest.raises(ValueError, match=r"^epoch_upgrade_continuity$"):
        build_live_bundle(
            output,
            site,
            starts_at=start,
            ends_at=end,
            source_root=upgrade.source_root,
            network_input=owner,
            upgrade_from=(
                upgrade.descriptor.payload_sha256,
                upgrade.descriptor.runtime_manifest_sha256,
            ),
            epoch_upgrade=upgrade.descriptor,
        )
    assert not output.exists()


def test_changed_source_copy_refuses_stale_guard(
    upgrade: UpgradeCase, tmp_path: Path
) -> None:
    site = SiteConfiguration.model_validate_json(
        (upgrade.paths.runtime / "site.json").read_bytes()
    )
    owner = json.loads(
        (upgrade.paths.runtime / "network-owner-confirmation.json").read_bytes()
    )["owner_input"]
    tampered_source = tmp_path / "guard-source"
    vector_path = Path("tests/fixtures/live-admission-source-guard-v22.json")
    vector = json.loads((upgrade.source_root / vector_path).read_bytes())
    for name in (*vector["files"], vector_path.as_posix()):
        target = tampered_source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(upgrade.source_root / name, target)
    member = tampered_source / "src/paper_radar/live_evidence/live_bundle.py"
    member.write_bytes(member.read_bytes() + b"\n# synthetic changed source\n")
    output = tmp_path / "guard-rejected"
    with pytest.raises(ValueError, match=r"^source_guard_mismatch$"):
        build_live_bundle(
            output,
            site,
            starts_at=upgrade.old.network.starts_at,
            ends_at=upgrade.old.network.ends_at,
            source_root=tampered_source,
            network_input=owner,
        )
    assert not output.exists()


@pytest.mark.parametrize(
    "name,model",
    [
        ("live-epoch-upgrade-v1", EpochUpgrade),
        ("normal-auth-epoch-v2", InheritedAuthEpoch),
    ],
)
def test_epoch_metadata_schema_matches_authoritative_models(
    name: str, model: type[WireModel]
) -> None:
    path = Path(__file__).resolve().parents[1] / "docs/schemas" / (name + ".json")
    assert json.loads(path.read_bytes()) == model.model_json_schema()


@pytest.mark.parametrize(
    "field,value",
    [
        ("epoch_sha256", "invalid-sha"),
        ("deployed_at", "2026-11-11T08:42:44"),
        ("deployed_at", "2026-11-11T08:42:44+08:00"),
        ("unexpected", "not-allowed"),
    ],
)
def test_epoch_descriptor_rejects_unknown_non_utc_or_invalid_digest(
    upgrade: UpgradeCase, field: str, value: str
) -> None:
    data = upgrade.descriptor.model_dump(mode="json")
    data[field] = value
    with pytest.raises(
        ValueError, match=r"epoch_sha256|epoch_upgrade_invalid|unexpected"
    ):
        EpochUpgrade.model_validate(data)


def test_missing_new_epoch_after_execution_cannot_be_reconstructed(
    upgrade: UpgradeCase,
) -> None:
    assert upgrade.deployment.install() == "installed"
    collection = ProtectedCollection(upgrade.ledger)
    now = datetime.now(UTC)
    collection.approve_plan(upgrade.new.negative_plan, now=now)
    run = collection.start_round(
        upgrade.new.negative_plan.plan_id, binding=BINDING, now=now
    )
    collection.cancel_round(run.round_id, now=now)
    epoch_path(upgrade.ledger, upgrade.new).unlink()
    with pytest.raises(LedgerError, match=r"^source_untrusted$"):
        initialize_epoch(
            upgrade.ledger, upgrade.new, now=now, inherited_from=upgrade.descriptor
        )
    assert not epoch_path(upgrade.ledger, upgrade.new).exists()


@pytest.mark.parametrize("missing_intent", [False, True])
def test_stopped_consumption_and_revocation_survive_upgrade(
    upgrade: UpgradeCase, monkeypatch: pytest.MonkeyPatch, missing_intent: bool
) -> None:
    from paper_radar.live_evidence.intents import (
        FS_APPEND_FL,
        INTENT_PATH,
        IntentHeader,
        ProtectedIntentLog,
    )
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
    from paper_radar.live_evidence.service import PendingRevocation
    from paper_radar.live_evidence.types import Capability

    collection = ProtectedCollection(upgrade.ledger)
    now = datetime.now(UTC)
    collection.approve_plan(upgrade.old.cells[0].plan, now=now)
    run = collection.start_round(
        upgrade.old.cells[0].plan.plan_id, binding=BINDING, now=now
    )
    collection.reserve(
        run.round_id, upgrade.old.cells[0].plan.cases[0], "auth", now=now
    )
    collection.recover_interrupted(now=now)
    lifecycle = EvidenceLifecycle(upgrade.ledger)
    lifecycle.tighten_use("boundary-low", now=now)
    event = lifecycle.cutover_intents(now=now)
    path = upgrade.paths.anchor / INTENT_PATH.relative_to("/")
    path.parent.mkdir(parents=True, mode=0o755)
    site = SiteConfiguration.model_validate_json(
        (upgrade.paths.runtime / "site.json").read_bytes()
    )
    # 仅模拟append-only ioctl这一OS边界,记录内容/权限/读取/重放均真实。
    monkeypatch.setattr(
        "paper_radar.live_evidence.intents._get_flags", lambda fd: FS_APPEND_FL
    )
    path.write_bytes(
        canonical_bytes(
            IntentHeader(sequence=event.sequence, recorded_at=event.recorded_at)
        )
    )
    os.chown(path, os.getuid(), site.product_gid)
    path.chmod(0o660)
    intents = ProtectedIntentLog(
        path, product_gid=site.product_gid, trust=upgrade.ledger.trust
    )
    intents.append(
        canonical_bytes(
            PendingRevocation(
                receipt_id=None,
                use_id="boundary-low",
                capabilities=(Capability.CWD_ANCESTORS,),
                recorded_at=now,
            )
        ).rstrip(b"\n")
    )
    before = collection.status(upgrade.old.negative_plan.plan_id, now=now)
    database = upgrade.ledger.database.read_bytes()
    intent_bytes = path.read_bytes()
    events = upgrade.ledger.audit()
    assert before.stopped and before.network_used == 1
    if missing_intent:
        path.unlink()
        unchanged = snapshot(upgrade)
        with pytest.raises(LedgerError, match=r"^pending_revocation_unavailable$"):
            upgrade.deployment.install()
        assert snapshot(upgrade) == unchanged
        return
    assert upgrade.deployment.install() == "installed"
    assert collection.status(upgrade.old.negative_plan.plan_id, now=now) == before
    assert upgrade.ledger.database.read_bytes() == database
    assert upgrade.ledger.audit() == events and path.read_bytes() == intent_bytes
    assert (
        read_epoch(upgrade.ledger, upgrade.new).deployed_at
        == upgrade.descriptor.deployed_at
    )


@pytest.mark.parametrize("stage", ["archive", "runtime", "epoch"])
def test_filesystem_interruption_after_atomic_publication_resumes_same_bytes(
    upgrade: UpgradeCase, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    import errno

    fired = False
    original_rename = Path.rename
    original_link = os.link

    def rename(path: Path, target: Path | str) -> Path:
        nonlocal fired
        result = original_rename(path, target)
        if not fired and (
            (stage == "archive" and path == upgrade.paths.runtime)
            or (stage == "runtime" and Path(target) == upgrade.paths.runtime)
        ):
            fired = True
            raise OSError(errno.EIO, "synthetic_atomic_interruption")
        return result

    def link(
        src: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        dst: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        **kwargs: Any,
    ) -> None:
        nonlocal fired
        original_link(src, dst, **kwargs)
        if (
            not fired
            and stage == "epoch"
            and dst == epoch_path(upgrade.ledger, upgrade.new)
        ):
            fired = True
            raise OSError(errno.EIO, "synthetic_atomic_interruption")

    monkeypatch.setattr(Path, "rename", rename)
    monkeypatch.setattr(os, "link", link)
    with pytest.raises(OSError) as caught:
        upgrade.deployment.install()
    assert caught.value.errno == errno.EIO and fired
    assert upgrade.deployment.install(recover=True) == "installed"
    assert (
        read_epoch(upgrade.ledger, upgrade.new).deployed_at
        == upgrade.descriptor.deployed_at
    )
    assert epoch_path(upgrade.ledger, upgrade.old).read_bytes() == upgrade.old_epoch


@pytest.mark.parametrize("source", ["manifest", "previous", "history"])
def test_ancestor_tampering_refuses_before_recovery_writes(
    upgrade: UpgradeCase, source: str
) -> None:
    if source == "manifest":
        (upgrade.paths.runtime / "model-manifest.json").write_bytes(
            b"untrusted old manifest"
        )
        reason = "runtime_member_identity"
    elif source == "previous":
        state = json.loads(upgrade.paths.journal.read_bytes())
        state["previous"] = dict(state)
        upgrade.paths.journal.write_bytes(json_bytes(state))
        reason = "epoch_upgrade_history"
    else:
        upgrade.host.fail = "disable_observation"
        with pytest.raises(ValueError, match=r"^model_interruption$"):
            upgrade.deployment.install()
        upgrade.host.fail = None
        history = upgrade.paths.journal.with_name(
            "deployment-v2-history-" + upgrade.descriptor.payload_sha256 + ".json"
        )
        history.write_bytes(history.read_bytes() + b" ")
        reason = "epoch_upgrade_history"
    before = snapshot(upgrade)
    with pytest.raises(ValueError, match="^" + reason + "$"):
        upgrade.deployment.install(recover=True)
    assert snapshot(upgrade) == before


def test_linear_inherited_epoch_reader_replays_every_original_source(
    upgrade: UpgradeCase,
) -> None:
    upgrade.deployment.install()
    source_epoch = epoch_path(upgrade.ledger, upgrade.new).read_bytes()
    second = describe_epoch_upgrade(upgrade.paths.runtime, source_epoch)
    data = upgrade.new.model_dump(mode="json")
    data["collector_sha256"] = "c" * 64
    identifiers = []
    for index, cell in enumerate(data["cells"]):
        cell["plan"]["plan_id"] = f"third-model-{index}"
        cell["plan"]["collector_sha256"] = "c" * 64
        identifiers.append(cell["plan"]["plan_id"])
    data["negative_plan"]["plan_id"] = "third-negative"
    data["negative_plan"]["collector_sha256"] = "c" * 64
    identifiers.append("third-negative")
    data["network"]["plan_ids"] = identifiers
    third = ModelManifestV2.model_validate(data)
    initialize_epoch(
        upgrade.ledger,
        third,
        now=second.deployed_at + timedelta(hours=20),
        inherited_from=second,
    )
    assert (
        read_epoch(upgrade.ledger, third).deployed_at == upgrade.descriptor.deployed_at
    )
    epoch_path(upgrade.ledger, upgrade.old).write_bytes(upgrade.old_epoch + b" ")
    with pytest.raises(LedgerError, match=r"^source_untrusted$"):
        read_epoch(upgrade.ledger, third)


def test_original_v1_epoch_model_ast_is_preserved() -> None:
    import ast

    relative = Path("src/paper_radar/live_evidence/normal_auth_refresh.py")
    # 独立固定的原v1声明;不依赖Git对象,也不从当前生产声明生成预期。
    baseline = ast.parse("""class NormalAuthEpoch(WireModel):
    format_version: Literal[1] = 1
    collector_sha256: Digest
    plan_ids: tuple[Identifier, ...]
    deployed_at: datetime
""")
    current = ast.parse((Path(__file__).resolve().parents[1] / relative).read_bytes())
    old = next(
        node
        for node in baseline.body
        if isinstance(node, ast.ClassDef) and node.name == "NormalAuthEpoch"
    )
    new = next(
        node
        for node in current.body
        if isinstance(node, ast.ClassDef) and node.name == "NormalAuthEpoch"
    )
    assert ast.dump(old, include_attributes=False) == ast.dump(
        new, include_attributes=False
    )
