"""严格恢复封装:内容闭包与派生视图使用独立命名空间。"""

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from paper_radar.backup.files import read_manifest
from paper_radar.backup.manifest import BackupManifest, parse_manifest
from paper_radar.replay.contract import ReplayError

RECEIPT = "restore-receipt.json"


class RestoreReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    format_version: Literal[1] = 1
    operation: Literal["restore verify"] = "restore verify"
    contents: Literal["contents"] = "contents"
    manifest_sha256: str
    batch_id: str

    def canonical(self) -> bytes:
        return (
            json.dumps(
                self.model_dump(),
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()


def write_receipt(root: Path, manifest: BackupManifest) -> None:
    receipt = RestoreReceipt(
        manifest_sha256=manifest.sha256, batch_id=manifest.batch_id
    )
    path = root / RECEIPT
    with path.open("xb") as stream:
        stream.write(receipt.canonical())
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o600)


def safe_path(path: Path) -> Path:
    if not path.is_absolute():
        path = Path.cwd() / path
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ReplayError("unsafe_layout")
    return path.resolve()


def check_layout(root: Path) -> Path:
    root = safe_path(root)
    if not root.is_dir() or {p.name for p in root.iterdir()} != {
        "contents",
        "views",
        RECEIPT,
    }:
        raise ReplayError("restore_provenance_invalid")
    for path in (root, *root.rglob("*")):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ReplayError("unsafe_layout")
        if stat.S_ISDIR(mode) and stat.S_IMODE(mode) & 0o077:
            raise ReplayError("unsafe_layout")
        if stat.S_ISREG(mode) and path.stat().st_nlink != 1:
            raise ReplayError("unsafe_layout")
    if (
        not (root / "contents").is_dir()
        or not (root / "views").is_dir()
        or not (root / RECEIPT).is_file()
    ):
        raise ReplayError("restore_provenance_invalid")
    return root


def verify_receipt(root: Path) -> BackupManifest:
    try:
        raw = (root / RECEIPT).read_bytes()
        receipt = RestoreReceipt.model_validate_json(raw)
        if raw != receipt.canonical():
            raise ReplayError("restore_provenance_invalid")
        manifest_raw = read_manifest(root / "contents")
        manifest = parse_manifest(manifest_raw)
        if (
            receipt.manifest_sha256 != hashlib.sha256(manifest_raw).hexdigest()
            or receipt.batch_id != manifest.batch_id
        ):
            raise ReplayError("restore_provenance_invalid")
        return manifest
    except (ValidationError, OSError, ValueError) as error:
        if isinstance(error, ReplayError):
            raise
        raise ReplayError("restore_provenance_invalid") from None
