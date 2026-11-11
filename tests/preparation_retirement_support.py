"""失败准备退役的完整合成封印/epoch与AppArmor OS模型;不使用现场输入。"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from paper_radar.live_evidence import preparation_retirement
from paper_radar.live_evidence.deployment import file_digests
from paper_radar.live_evidence.epoch_lineage import describe_epoch_upgrade
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
from paper_radar.live_evidence.live_install import LiveDeployment, json_bytes
from paper_radar.live_evidence.model_manifest import parse_manifest
from paper_radar.live_evidence.normal_auth_refresh import epoch_path
from paper_radar.live_evidence.placement_policy import (
    MEMBERS,
    PlacementPolicyLifecycle,
)
from paper_radar.live_evidence.preparation_retirement import (
    FailedPreparationRetirement,
    describe_failed_preparation,
    original_marker,
)
from tests.live_apparmor_support import PolicyOS
from tests.live_bundle_support import ModelHost, bundle_model


def reseal(root: Path) -> None:
    entries = file_digests(root)
    for name in ("manifest.sha256", "payload.sha256"):
        entries.pop(name, None)
    raw = "".join(f"{sha}  {name}\n" for name, sha in sorted(entries.items())).encode()
    (root / "manifest.sha256").write_bytes(raw)
    (root / "payload.sha256").write_text(hashlib.sha256(raw).hexdigest() + "\n")
    for path in root.rglob("*"):
        path.chmod(0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644)


class CutoverOS(PolicyOS):
    def __init__(
        self, old: PlacementPolicyLifecycle, new: PlacementPolicyLifecycle
    ) -> None:
        assert old.sealed is not None and new.sealed is not None
        super().__init__(parser=old.sealed.parser)
        self.policies = {
            old.sealed.policy.binary: old.sealed.policy,
            new.sealed.policy.binary: new.sealed.policy,
        }

    def load_binary(self, binary: bytes) -> None:
        self.expected = self.policies[binary]
        super().load_binary(binary)


@dataclass
class RetirementCase:
    gate: FailedPreparationRetirement
    old: PlacementPolicyLifecycle
    new: PlacementPolicyLifecycle
    io: CutoverOS
    before: dict[Path, bytes]
    host: ModelHost


def case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    main_policy: bool = False,
    static_binding: bool = False,
) -> RetirementCase:
    first, paths = bundle_model(tmp_path, monkeypatch)
    if static_binding:
        manifest_path = first / "model-manifest.json"
        manifest_value = json.loads(manifest_path.read_bytes())
        for cell_value in manifest_value["cells"]:
            cell_value["binding"] = {"supply": "d" * 64}
        manifest_path.write_bytes(json_bytes(manifest_value))
        reseal(first)
    future = tmp_path / "future"
    shutil.copytree(first, future)
    if not main_policy:
        for name in MEMBERS:
            (first / name).unlink()
        (first / "placement").rmdir()
        identity_path = first / "source-identity.json"
        identity = json.loads(identity_path.read_bytes())
        identity["source_auxiliary_sha256"].pop("pi_execution/placement_native.c")
        identity_path.write_bytes(json_bytes(identity))
        reseal(first)
    host = ModelHost(paths)
    assert (
        LiveDeployment(first, paths=paths, host=host, owner_uid=os.getuid()).install()
        == "installed"
    )
    ledger = EvidenceLedger(
        paths.ledger, trust=LedgerTrust(owner_uid=os.getuid(), anchor=paths.anchor)
    )
    manifest = parse_manifest((paths.runtime / "model-manifest.json").read_bytes())
    epoch = describe_epoch_upgrade(
        paths.runtime, epoch_path(ledger, manifest).read_bytes()
    )
    spec = json.loads((future / "deployment.json").read_bytes())
    spec["upgrade_from"] = [epoch.payload_sha256, epoch.runtime_manifest_sha256]
    spec["epoch_upgrade"] = epoch.model_dump(mode="json")
    (future / "deployment.json").write_bytes(json_bytes(spec))
    failed = tmp_path / "failed"
    shutil.copytree(future, failed)
    build_path = failed / "placement/build.json"
    build = json.loads(build_path.read_bytes())
    true = build.pop("fixed_true_exec")
    build["format_version"] = 1
    source_path = failed / "placement/apparmor.source"
    source_path.write_text(
        source_path.read_text().replace(
            f'  "{true["resolved"]}" ix,', "  /usr/bin/true ix,"
        )
    )
    binary_path = failed / "placement/apparmor.bin"
    # 明确OS模型的旧ABI5字节;不声称该literal由真实parser生成。
    binary_path.write_bytes(
        b"\x04\x08\x00version\x00\x02\x05\x00\x00\x00old-model-policy"
    )
    build["source_sha256"] = hashlib.sha256(source_path.read_bytes()).hexdigest()
    build["binary_sha256"] = hashlib.sha256(binary_path.read_bytes()).hexdigest()
    build_path.write_bytes(json_bytes(build))
    reseal(failed)
    staging = tmp_path / "live-bundles"
    payload = (failed / "payload.sha256").read_text().strip()
    old_root = staging / payload / "runtime"
    old_root.parent.mkdir(parents=True)
    failed.rename(old_root)
    for path in (staging, old_root.parent):
        path.chmod(0o755)
    monkeypatch.setattr(preparation_retirement, "_STAGING_ROOT", staging)
    descriptor = describe_failed_preparation(old_root, future)
    spec["failed_preparation"] = descriptor.model_dump(mode="json")
    (future / "deployment.json").write_bytes(json_bytes(spec))
    reseal(future)
    old = PlacementPolicyLifecycle(
        old_root, paths.ledger, owner_uid=os.getuid(), anchor=paths.anchor
    )
    new = PlacementPolicyLifecycle(
        future, paths.ledger, owner_uid=os.getuid(), anchor=paths.anchor
    )
    io = CutoverOS(old, new)
    gate = FailedPreparationRetirement(
        future, paths, owner_uid=os.getuid(), kernel_io=io
    )
    assert old.sealed is not None
    io.load_binary(old.sealed.policy.binary)
    io.writes.clear()
    old.journal.write_bytes(original_marker(descriptor))
    old.journal.chmod(0o644)
    # 只替换宿主身份/sysctl OS检查;封印/marker/epoch/kernel原bytes均走生产认证。
    monkeypatch.setattr(
        preparation_retirement, "verify_host_security", lambda sealed: None
    )
    before = {
        path: path.read_bytes()
        for root in (paths.runtime, paths.ledger, old_root)
        for path in root.rglob("*")
        if path.is_file()
    }
    return RetirementCase(gate, old, new, io, before, host)


def assert_business_unchanged(model: RetirementCase) -> None:
    for path, raw in model.before.items():
        if path != model.old.journal:
            assert path.read_bytes() == raw, path
    assert not tuple(model.gate.paths.ledger.glob("deployment-v2-history-*.json"))
    assert not tuple(model.gate.paths.runtime.parent.glob("*.archive-*"))
