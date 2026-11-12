"""同一完整放置策略的失败准备一跳恢复合成场景。"""

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from paper_radar.live_evidence.live_install import json_bytes
from paper_radar.live_evidence.preparation_retirement import FailedPreparationRetirement
from tests.preparation_retirement_support import RetirementCase, case, reseal


@dataclass
class RecoveryCase:
    original: RetirementCase
    source: FailedPreparationRetirement
    gate: FailedPreparationRetirement
    preserved: dict[Path, tuple[bytes, tuple[int, int, int, int, int]]]


def inventory(root: Path) -> dict[Path, tuple[bytes, tuple[int, int, int, int, int]]]:
    return {
        path: (
            path.read_bytes(),
            (s.st_mode, s.st_uid, s.st_gid, s.st_nlink, s.st_mtime_ns),
        )
        for path in root.rglob("*")
        if path.is_file() and (s := path.lstat())
    }


def recovery_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RecoveryCase:
    original = case(tmp_path, monkeypatch)

    def refused() -> None:
        raise ValueError("placement_preflight_refused")

    with pytest.raises(ValueError, match=r"^placement_preflight_refused$"):
        original.gate.prepare(refused, lambda: None)
    source_payload = (original.gate.staged / "payload.sha256").read_text().strip()
    source_root = original.old.root.parent.parent / source_payload / "runtime"
    source_root.parent.mkdir(mode=0o755)
    source_root.parent.chmod(0o755)
    original.gate.staged.rename(source_root)
    source = FailedPreparationRetirement(
        source_root, original.gate.paths, owner_uid=os.getuid(), kernel_io=original.io
    )
    target = tmp_path / "recovery"
    shutil.copytree(source_root, target)
    # 新源码包只修产品manager查询;放置闭包全部保持原字节。
    entry = target / "entry.py"
    entry.write_bytes(entry.read_bytes() + b"\n# synthetic manager query correction\n")
    spec_path = target / "deployment.json"
    spec = json.loads(spec_path.read_bytes())
    spec["preparation_recovery"] = {
        "payload_sha256": source_payload,
        "runtime_manifest_sha256": hashlib.sha256(
            (source_root / "manifest.sha256").read_bytes()
        ).hexdigest(),
        "journal_sha256": hashlib.sha256(source.journal.read_bytes()).hexdigest(),
    }
    spec_path.write_bytes(json_bytes(spec))
    reseal(target)
    gate = FailedPreparationRetirement(
        target, original.gate.paths, owner_uid=os.getuid(), kernel_io=original.io
    )
    preserved = (
        inventory(original.gate.paths.runtime)
        | inventory(source_root)
        | inventory(original.old.root)
        | {
            path: value
            for path, value in inventory(original.gate.paths.ledger).items()
            if path != original.new.journal
        }
    )
    for path in (source.journal, source.snapshot, original.old.journal):
        s = path.lstat()
        preserved[path] = (
            path.read_bytes(),
            (s.st_mode, s.st_uid, s.st_gid, s.st_nlink, s.st_mtime_ns),
        )
    original.io.writes.clear()
    return RecoveryCase(original, source, gate, preserved)


def assert_preserved(model: RecoveryCase) -> None:
    for path, (raw, metadata) in model.preserved.items():
        s = path.lstat()
        assert path.read_bytes() == raw, path
        assert (s.st_mode, s.st_uid, s.st_gid, s.st_nlink, s.st_mtime_ns) == metadata, (
            path
        )
