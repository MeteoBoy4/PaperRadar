"""请求、D5、根、平台与归档边界的公共服务拒绝。"""

import hashlib
import io
import json
import os
import tarfile
from pathlib import Path

import pytest

from paper_radar.pi_supply import SupplyError, list_supplies, prepare_supply
from tests.pi_supply_support import NODE, encoded, inputs, prepare


@pytest.mark.parametrize(
    "change",
    [
        "no_baseline",
        "blank_basis",
        "no_evidence",
        "url_only",
        "duplicate",
        "missing_adapter",
    ],
)
def test_invalid_request_or_d5_never_publishes(tmp_path: Path, change: str) -> None:
    source = inputs(tmp_path)
    payload = json.loads(source[2].read_bytes())
    slot = "screening"
    if change == "no_baseline":
        payload["d5"]["decision"] = "no_change"
    elif change == "blank_basis":
        payload["d5"]["basis"] = " "
    elif change == "no_evidence":
        payload["d5"]["evidence"] = []
    elif change == "url_only":
        payload["d5"]["evidence"] = [{"kind": "url", "url": "https://SECRET.example"}]
    elif change == "missing_adapter":
        slot = "SECRET-unknown"
    source[2].write_bytes(encoded(payload))
    if change == "duplicate":
        source[2].write_bytes(b'{"node_version":"22.19.0","node_version":"SECRET"}')
    with pytest.raises(SupplyError) as caught:
        prepare_supply(
            source[0],
            source[1],
            slot,
            source[2],
            tmp_path / "install",
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
            downloader=source[3],
            runner=source[4],
        )
    assert "SECRET" not in str(caught.value)
    assert list_supplies(source[0]) == ()


def test_foreign_database_cannot_claim_or_modify_install_root(tmp_path: Path) -> None:
    first = inputs(tmp_path / "first")
    prepare(tmp_path / "first", first)
    root = tmp_path / "first/install"
    marker = (root / ".paper-radar-install-root").read_bytes()
    second = inputs(tmp_path / "second")
    with pytest.raises(SupplyError, match="root_foreign"):
        prepare_supply(
            second[0],
            second[1],
            "screening",
            second[2],
            root,
            data_root=tmp_path / "second/data",
            config_root=tmp_path / "second/config",
            material_root=tmp_path / "second/materials",
            downloader=second[3],
            runner=second[4],
        )
    assert not second[3].calls
    assert (root / ".paper-radar-install-root").read_bytes() == marker
    assert list_supplies(second[0]) == ()


@pytest.mark.parametrize(
    "root_kind", ["database", "config", "data", "materials", "symlink"]
)
def test_unsafe_install_roots_rejected_before_download(
    tmp_path: Path, root_kind: str
) -> None:
    source = inputs(tmp_path)
    roots = {
        "database": tmp_path,
        "config": tmp_path / "config/pi",
        "data": tmp_path / "data",
        "materials": tmp_path / "materials",
    }
    if root_kind == "symlink":
        (tmp_path / "linked").symlink_to(tmp_path / "outside")
        root = tmp_path / "linked"
    else:
        root = roots[root_kind]
    with pytest.raises(SupplyError):
        prepare_supply(
            source[0],
            source[1],
            "screening",
            source[2],
            root,
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
            downloader=source[3],
            runner=source[4],
        )
    assert not source[3].calls


@pytest.mark.parametrize("kind", ["traversal", "symlink", "device"])
def test_node_archive_safety_after_checksum_verification(
    tmp_path: Path, kind: str
) -> None:
    source = inputs(tmp_path)
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:xz") as archive:
        item = tarfile.TarInfo(
            f"node-v{NODE}-linux-x64/"
            + ("../../SECRET" if kind == "traversal" else "bad")
        )
        if kind == "symlink":
            item.type = tarfile.SYMTYPE
            item.linkname = "../../SECRET"
        elif kind == "device":
            item.type = tarfile.CHRTYPE
        archive.addfile(item)
    raw = stream.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    base = f"https://nodejs.org/dist/v{NODE}"
    source[3].content[base + f"/node-v{NODE}-linux-x64.tar.xz"] = raw
    source[3].content[base + "/SHASUMS256.txt"] = (
        f"{digest}  node-v{NODE}-linux-x64.tar.xz\n".encode()
    )
    payload = json.loads(source[2].read_bytes())
    payload["node_sha256"] = digest
    source[2].write_bytes(encoded(payload))
    with pytest.raises(SupplyError, match="archive_unsafe"):
        prepare(tmp_path, source)
    assert list_supplies(source[0]) == ()
    assert not (tmp_path / "SECRET").exists()


@pytest.mark.parametrize("value", [None, "musl 1.2.0", "glibc"])
def test_runtime_libc_must_be_probed_and_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    source = inputs(tmp_path)
    monkeypatch.setattr(os, "confstr", lambda _: value)
    with pytest.raises(SupplyError, match="platform_mismatch"):
        prepare(tmp_path, source)
    assert not source[3].calls


def test_prepare_allows_missing_profile_models_and_mixed_adapter_versions(
    tmp_path: Path,
) -> None:
    from paper_radar.config import compile_config

    source = inputs(tmp_path)
    settings = tmp_path / "config/settings.yaml"
    settings.write_text(
        settings.read_text()
        .replace("profile: profile-v1", "profile: null")
        .replace("models: models-v1", "models: null")
        .replace("reading: pi-v1", "reading: pi-other")
    )
    original = tmp_path / "config/adapters/pi-v1.yaml"
    (original.parent / "pi-other.yaml").write_text(
        original.read_text()
        .replace("version: pi-v1", "version: pi-other")
        .replace("pi_version: 1.3.0", "pi_version: 1.2.0")
    )
    snapshot = compile_config(settings, source[0])
    modified = (source[0], snapshot.snapshot_id, *source[2:])
    prepared = prepare(tmp_path, modified)
    assert list_supplies(source[0])[0].supply_id == prepared.supply_id
    assert all("--model" not in argv for argv, _, _ in source[4].calls)


def test_space_precheck_is_only_an_early_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = inputs(tmp_path)
    values = list(os.statvfs(tmp_path))
    values[4] = 0
    monkeypatch.setattr(os, "statvfs", lambda _: os.statvfs_result(values))
    with pytest.raises(SupplyError, match="space_insufficient"):
        prepare(tmp_path, source)
    assert not source[3].calls
    assert not (tmp_path / "install").exists()


def test_environment_secrets_and_proxy_are_not_inherited_or_frozen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = inputs(tmp_path)
    for name in ("NODE_OPTIONS", "HTTPS_PROXY", "NPM_TOKEN", "OPENAI_API_KEY"):
        monkeypatch.setenv(name, "SECRET-value")
    prepare(tmp_path, source)
    record = list_supplies(source[0])[0]
    assert b"SECRET" not in record.manifest.canonical_bytes
    assert all(
        "SECRET" not in value for _, _, env in source[4].calls for value in env.values()
    )
