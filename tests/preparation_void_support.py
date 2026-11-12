"""双失败准备的合成封印、root 文件与 kernel 模型。"""

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from paper_radar.live_evidence import preparation_void
from paper_radar.live_evidence.live_install import json_bytes
from paper_radar.live_evidence.placement_policy import read_placement_policy
from paper_radar.live_evidence.preparation_retirement import FailedPreparationRetirement
from paper_radar.live_evidence.preparation_void import (
    FailedPreparationVoid,
    describe_preparation_void,
)
from tests.preparation_recovery_support import RecoveryCase, recovery_case
from tests.preparation_retirement_support import reseal


@dataclass
class VoidCase:
    original: RecoveryCase
    gate: FailedPreparationVoid
    preserved: dict[Path, bytes]


def void_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> VoidCase:
    original = recovery_case(tmp_path, monkeypatch, distinct_candidate_plans=True)

    def refused() -> None:
        raise ValueError("placement_preflight_refused")

    with pytest.raises(ValueError, match=r"^placement_preflight_refused$"):
        original.gate.prepare(refused, lambda: None, recover=True)
    root = original.gate.staged
    payload = (root / "payload.sha256").read_text().strip()
    staged = original.source.staged.parent.parent / payload / "runtime"
    staged.parent.mkdir(mode=0o755)
    staged.parent.chmod(0o755)
    root.rename(staged)
    second = FailedPreparationRetirement(
        staged,
        original.gate.paths,
        owner_uid=os.getuid(),
        kernel_io=original.original.io,
    )
    target = tmp_path / "clean-candidate"
    shutil.copytree(staged, target)
    spec_path = target / "deployment.json"
    spec = json.loads(spec_path.read_bytes())
    spec.pop("failed_preparation")
    spec.pop("preparation_recovery")
    spec_path.write_bytes(json_bytes(spec))
    binary = target / "placement/apparmor.bin"
    binary.write_bytes(
        b"\x04\x08\x00version\x00\x02\x05\x00\x00\x00void-candidate-model"
    )
    build = target / "placement/build.json"
    data = json.loads(build.read_bytes())
    data["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
    build.write_bytes(json_bytes(data))
    reseal(target)
    descriptor = describe_preparation_void(
        original.source.staged,
        staged,
        target,
        (original.source.journal.read_bytes(), second.journal.read_bytes()),
    )
    spec["failed_preparation_void"] = descriptor.model_dump(mode="json")
    spec_path.write_bytes(json_bytes(spec))
    reseal(target)
    io = original.original.io
    new_policy = read_placement_policy(target)
    assert new_policy is not None
    io.policies[new_policy.policy.binary] = new_policy.policy
    monkeypatch.setattr(preparation_void, "_STAGING_ROOT", staged.parent.parent)
    monkeypatch.setattr(preparation_void, "verify_host_security", lambda sealed: None)
    gate = FailedPreparationVoid(
        target, original.gate.paths, owner_uid=os.getuid(), kernel_io=io
    )
    preserved = {
        path: path.read_bytes()
        for root in (
            original.gate.paths.runtime,
            original.gate.paths.ledger,
            original.source.staged,
            staged,
            original.original.old.root,
        )
        for path in root.rglob("*")
        if path.is_file()
    }
    io.writes.clear()
    return VoidCase(original, gate, preserved)


def assert_void_preserved(model: VoidCase) -> None:
    for path, raw in model.preserved.items():
        assert path.read_bytes() == raw, path
