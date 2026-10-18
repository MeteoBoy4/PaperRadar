"""prepare 的唯一纵向路径;查询不访问平台、网络或安装现场。"""

from __future__ import annotations

import os
import platform
import re
import shutil
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from pathlib import Path, PurePosixPath

from sqlalchemy import insert, select

from paper_radar.config import (
    ConfigError,
    load_config_snapshot,
    resolve_config_snapshot_reference,
)
from paper_radar.config.adapters import PiAdapter
from paper_radar.config.compile import MaterialKind
from paper_radar.config.identity import canonical_json, sha256
from paper_radar.config.yaml_loader import validate_yaml_bytes
from paper_radar.pi_supply import tables
from paper_radar.pi_supply.errors import SupplyError, SupplyReason
from paper_radar.pi_supply.filesystem import (
    check_space,
    durable_directories,
    durable_tree,
    extract_node,
    freeze_tree,
    fsync_directory,
    local_filesystem,
    no_symlink_components,
    publish_directory,
    safe_roots,
    tree_hash,
)
from paper_radar.pi_supply.materials import (
    PI_PACKAGE,
    check_engine,
    derive_lock,
    object_bytes,
)
from paper_radar.pi_supply.models import (
    D5,
    Evidence,
    InstallInstance,
    PrepareResult,
    SupplyManifest,
    SupplyRecord,
    SupplyRequest,
    VerificationResult,
)
from paper_radar.pi_supply.repository import (
    append_check,
    append_rebuild_failure,
    commit_install,
    commit_supply,
    database_engine,
    read_records,
)
from paper_radar.pi_supply.source_policy import checked_proxy
from paper_radar.pi_supply.transport import (
    Downloader,
    HttpDownloader,
    ProcessRunner,
    Runner,
)

SMALL_LIMIT = 4 * 1024 * 1024
ARCHIVE_LIMIT = 128 * 1024 * 1024
OUTPUT_LIMIT = 1024 * 1024
NPM_FLAGS = (
    "ci",
    "--ignore-scripts",
    "--omit=dev",
    "--include=optional",
    "--no-fund",
    "--no-audit",
    "--update-notifier=false",
)
PI_FLAGS = (
    "--offline",
    "--no-session",
    "--no-extensions",
    "--no-mcp",
    "--no-skills",
    "--no-prompt-templates",
    "--no-themes",
    "--no-context-files",
    "--no-tools",
)


def list_supplies(database: Path) -> tuple[SupplyRecord, ...]:
    return read_records(database)


def show_supply(database: Path, supply_id: str) -> SupplyRecord:
    if not re.fullmatch(r"[0-9a-f]{64}", supply_id):
        raise SupplyError("supply_reference_invalid")
    for record in read_records(database):
        if record.supply_id == supply_id:
            return record
    raise SupplyError("supply_not_found")


def _platform(manifest: SupplyManifest) -> None:
    try:
        libc_info = os.confstr("CS_GNU_LIBC_VERSION") or ""
    except (AttributeError, OSError, ValueError):
        raise SupplyError("platform_mismatch") from None
    if (
        platform.system() != "Linux"
        or platform.machine() != manifest.platform.arch
        or libc_info != f"{manifest.platform.libc} {manifest.libc_version}"
    ):
        raise SupplyError("platform_mismatch")


def _inspect(tree: Path, work: Path, manifest: SupplyManifest, process: Runner) -> None:
    if tree_hash(tree) != manifest.expected_tree:
        raise SupplyError("tree_mismatch")
    node, npm, pi = (
        tree / entry
        for entry in (manifest.node_entry, manifest.npm_entry, manifest.pi_entry)
    )
    env = _environment(work, node, None)
    probes: tuple[tuple[tuple[str, ...], str, SupplyReason], ...] = (
        (
            (str(node), "--version"),
            "v" + manifest.node_version,
            "node_version_mismatch",
        ),
        (
            (str(node), str(npm), "--version"),
            manifest.npm_version,
            "npm_version_mismatch",
        ),
        (
            (str(node), str(pi), *PI_FLAGS, "--version"),
            manifest.pi_version,
            "pi_version_mismatch",
        ),
    )
    for argv, expected, reason in probes:
        if (
            process.run(
                argv, cwd=work / "cwd", env=env, timeout=240, limit=OUTPUT_LIMIT
            ).strip()
            != expected.encode()
        ):
            raise SupplyError(reason)
    process.run(
        (str(node), str(pi), *PI_FLAGS, "--help"),
        cwd=work / "cwd",
        env=env,
        timeout=240,
        limit=OUTPUT_LIMIT,
    )
    if any((work / "sessions").iterdir()) or tree_hash(tree) != manifest.expected_tree:
        raise SupplyError("startup_side_effect")


def verify_supply(
    database: Path, supply_id: str, *, runner: Runner | None = None
) -> tuple[VerificationResult, ...]:
    """逐实例完整检查并追加事实;失败不隐藏其他实例的结果。"""
    record = show_supply(database, supply_id)
    _platform(record.manifest)
    results = []
    for instance in record.installs:
        reason: SupplyReason | None = None
        try:
            root = instance.path.parent.parent
            _check_root_marker(database, root, instance.root_id)
            no_symlink_components(instance.path)
            with tempfile.TemporaryDirectory(prefix="paperradar-pi-verify-") as work:
                _inspect(
                    instance.path,
                    Path(work),
                    record.manifest,
                    runner or ProcessRunner(),
                )
        except SupplyError as error:
            reason = error.reason
        except (OSError, ValueError):
            reason = "verify_failed"
        except KeyboardInterrupt:
            append_check(database, instance.install_id, "operation_interrupted")
            raise
        append_check(database, instance.install_id, reason)
        results.append(
            VerificationResult(instance.install_id, reason is None, reason or "passed")
        )
    return tuple(results)


def available_installs(database: Path, supply_id: str) -> tuple[InstallInstance, ...]:
    """最近通过且现场完整的实例;同时间由全库单调 check_id 唯一破同。"""
    record = show_supply(database, supply_id)
    available = []
    for instance in record.installs:
        try:
            _check_root_marker(database, instance.path.parent.parent, instance.root_id)
            no_symlink_components(instance.path)
            if tree_hash(instance.path) == record.manifest.expected_tree:
                available.append(instance)
        except (SupplyError, OSError):
            continue
    return tuple(
        sorted(
            available,
            key=lambda instance: max(
                (datetime.fromisoformat(check.created_at), check.check_id)
                for check in instance.checks
                if check.passed
            ),
            reverse=True,
        )
    )


def _read_small(path: Path) -> bytes:
    try:
        with path.open("rb") as source:
            raw = source.read(SMALL_LIMIT + 1)
        if len(raw) > SMALL_LIMIT:
            raise SupplyError("material_limit")
        return raw
    except OSError:
        raise SupplyError("material_unreadable") from None


@contextmanager
def _lock(path: Path) -> Iterator[None]:
    import fcntl

    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _owned_root(database: Path, root: Path) -> str:
    durable_directories(root)
    with _lock(root / ".root.lock"):
        no_symlink_components(root)
        marker = root / ".paper-radar-install-root"
        with (
            database_engine(database, write=True) as engine,
            engine.connect() as connection,
        ):
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            database_id = connection.execute(
                select(tables.database_identity.c.database_id)
            ).scalar_one()
            if marker.exists() or marker.is_symlink():
                if marker.is_symlink():
                    raise SupplyError("root_foreign")
                payload = object_bytes(_read_small(marker))
                root_id = payload.get("root_id")
                if (
                    set(payload) != {"database_id", "root_id"}
                    or payload.get("database_id") != database_id
                    or not isinstance(root_id, str)
                    or not re.fullmatch(r"[0-9a-f]{32}", root_id)
                ):
                    raise SupplyError("root_foreign")
            else:
                if any(item.name != ".root.lock" for item in root.iterdir()):
                    raise SupplyError("root_unowned_nonempty")
                root_id = uuid.uuid4().hex
                temporary_marker = root / f".root-marker-{uuid.uuid4().hex}"
                with temporary_marker.open("xb") as output:
                    output.write(
                        canonical_json({"database_id": database_id, "root_id": root_id})
                    )
                    output.flush()
                    os.fsync(output.fileno())
                os.link(temporary_marker, marker)
                temporary_marker.unlink()
                fsync_directory(root)
            row = (
                connection.execute(
                    select(tables.roots).where(tables.roots.c.root_id == root_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                conflict = connection.execute(
                    select(tables.roots).where(tables.roots.c.path == str(root))
                ).first()
                if conflict:
                    raise SupplyError("root_foreign")
                connection.execute(
                    insert(tables.roots).values(root_id=root_id, path=str(root))
                )
            elif row["path"] != str(root):
                raise SupplyError("root_foreign")
            connection.commit()
            return root_id


def _environment(work: Path, node: Path, proxy: str | None) -> dict[str, str]:
    for name in (
        "home",
        "tmp",
        "cache",
        "agent",
        "sessions",
        "config",
        "data",
        "state",
        "cwd",
    ):
        (work / name).mkdir(parents=True, exist_ok=True)
    (work / "agent/settings.json").write_bytes(
        canonical_json(
            {
                "enableInstallTelemetry": False,
                "enableAnalytics": False,
            }
        )
    )
    (work / "npmrc").write_text(
        "registry=https://registry.npmjs.org/\naudit=false\nfund=false\n"
        "update-notifier=false\nignore-scripts=true\nfetch-retries=0\n"
        "fetch-timeout=30000\n"
        + f"proxy={proxy or 'null'}\nhttps-proxy={proxy or 'null'}\n"
    )
    (work / "global-npmrc").write_bytes(b"")
    return {
        "PATH": str(node.parent),
        "HOME": str(work / "home"),
        "TMPDIR": str(work / "tmp"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "CI": "1",
        "NO_COLOR": "1",
        "NPM_CONFIG_USERCONFIG": str(work / "npmrc"),
        "NPM_CONFIG_GLOBALCONFIG": str(work / "global-npmrc"),
        "NPM_CONFIG_CACHE": str(work / "cache"),
        "PI_OFFLINE": "1",
        "PI_SKIP_VERSION_CHECK": "1",
        "PI_TELEMETRY": "0",
        "PI_CODING_AGENT_DIR": str(work / "agent"),
        "PI_CODING_AGENT_SESSION_DIR": str(work / "sessions"),
        "XDG_CONFIG_HOME": str(work / "config"),
        "XDG_DATA_HOME": str(work / "data"),
        "XDG_STATE_HOME": str(work / "state"),
    }


def _freeze_d5(
    request: SupplyRequest,
    request_path: Path,
    materials: dict[str, bytes],
    old: tuple[SupplyRecord, ...],
) -> D5:
    records = {record.supply_id: record for record in old}
    if request.d5.baseline_supply_id and request.d5.baseline_supply_id not in records:
        raise SupplyError("evidence_unresolved")
    evidence = []
    for item in request.d5.evidence:
        digest = None
        if item.kind == "evidence_file":
            assert item.path is not None
            raw = _read_small(request_path.parent / item.path)
            digest = sha256(raw)
            materials[f"d5-evidence/{digest}.bin"] = raw
        elif item.kind == "supply_material":
            assert item.material is not None
            source = (
                materials if item.supply_id is None else records.get(item.supply_id)
            )
            mapping = source.materials if isinstance(source, SupplyRecord) else source
            if mapping is None or item.material not in mapping:
                raise SupplyError("evidence_unresolved")
            digest = sha256(mapping[item.material])
        else:
            record = records.get(item.supply_id or "")
            if record is None or (
                item.check_id is not None
                and not any(
                    check.check_id == item.check_id
                    for install in record.installs
                    for check in install.checks
                )
            ):
                raise SupplyError("evidence_unresolved")
        evidence.append(
            Evidence(
                kind=item.kind,
                sha256=digest,
                material=item.material,
                supply_id=item.supply_id,
                check_id=item.check_id,
                note=item.note,
            )
        )
    return D5(
        decision=request.d5.decision,
        basis=request.d5.basis,
        baseline_supply_id=request.d5.baseline_supply_id,
        evidence=tuple(evidence),
    )


def _cleanup_staging(path: Path) -> None:
    if path.exists():
        for item in path.rglob("*"):
            if item.is_dir() and not item.is_symlink():
                item.chmod(0o700)
        path.chmod(0o700)
        shutil.rmtree(path)


def _check_root_marker(database: Path, root: Path, root_id: str) -> None:
    no_symlink_components(root)
    marker = root / ".paper-radar-install-root"
    if marker.is_symlink():
        raise SupplyError("root_foreign")
    with database_engine(database) as engine, engine.connect() as connection:
        owner = connection.execute(
            select(tables.database_identity.c.database_id)
        ).scalar_one()
    if object_bytes(_read_small(marker)) != {"database_id": owner, "root_id": root_id}:
        raise SupplyError("root_foreign")


def _publish_tree(
    root: Path, manifest: SupplyManifest, tree: Path, install_id: str
) -> Path:
    parent = root / manifest.supply_id
    no_symlink_components(parent)
    parent.mkdir(exist_ok=True, mode=0o700)
    target = parent / install_id
    no_symlink_components(target)
    if target.exists():
        if tree_hash(target) != manifest.expected_tree:
            raise SupplyError("publication_conflict")
        freeze_tree(target)
        durable_tree(target)
    else:
        freeze_tree(tree)
        durable_tree(tree)
        tree.chmod(0o755)
        publish_directory(tree, target)
        target.chmod(0o555)
        fsync_directory(target)
        fsync_directory(parent)
        fsync_directory(root)
    return target


def _publish(
    database: Path,
    root: Path,
    root_id: str,
    manifest: SupplyManifest,
    materials: dict[str, bytes],
    tree: Path,
    old_ids: frozenset[str],
) -> PrepareResult:
    with (
        _lock(database.with_name(database.name + ".pi-supply.lock")),
        _lock(root / ".root.lock"),
        _lock(root / f".prepare-{manifest.material_key}.lock"),
    ):
        _check_root_marker(database, root, root_id)
        for record in read_records(database):
            if record.manifest.material_key != manifest.material_key:
                continue
            if record.supply_id in old_ids:
                raise SupplyError("already_prepared_use_rebuild")
            if record.manifest.canonical_bytes != manifest.canonical_bytes:
                raise SupplyError("concurrent_supply_conflict")
            existing = record.installs[0]
            if tree_hash(existing.path) != manifest.expected_tree:
                raise SupplyError("concurrent_tree_conflict")
            return PrepareResult(record.supply_id, existing.install_id, True)
        pending = root / f".pending-{manifest.material_key}.json"
        install_id = uuid.uuid4().hex
        if pending.exists() or pending.is_symlink():
            if pending.is_symlink():
                raise SupplyError("publication_conflict")
            intent = object_bytes(_read_small(pending))
            install_id = intent.get("install_id", "")
            if (
                set(intent) != {"install_id", "supply_id"}
                or not isinstance(install_id, str)
                or not re.fullmatch(r"[0-9a-f]{32}", install_id)
                or intent["supply_id"] != manifest.supply_id
            ):
                raise SupplyError("publication_conflict")
        else:
            with pending.open("xb") as output:
                output.write(
                    canonical_json(
                        {"install_id": install_id, "supply_id": manifest.supply_id}
                    )
                )
                output.flush()
                os.fsync(output.fileno())
            fsync_directory(root)
        _publish_tree(root, manifest, tree, install_id)
        commit_supply(database, manifest, materials, root_id, install_id)
        pending.unlink()
        fsync_directory(root)
        return PrepareResult(manifest.supply_id, install_id)


def _publish_rebuild(
    database: Path,
    root: Path,
    root_id: str,
    manifest: SupplyManifest,
    tree: Path,
    process: Runner,
) -> PrepareResult:
    with (
        _lock(database.with_name(database.name + ".pi-supply.lock")),
        _lock(root / ".root.lock"),
    ):
        _check_root_marker(database, root, root_id)
        pending = root / f".pending-rebuild-{manifest.supply_id}.json"
        install_id = uuid.uuid4().hex
        if pending.exists() or pending.is_symlink():
            if pending.is_symlink():
                raise SupplyError("publication_conflict")
            intent = object_bytes(_read_small(pending))
            install_id = intent.get("install_id", "")
            if (
                set(intent) != {"install_id", "supply_id"}
                or not isinstance(install_id, str)
                or not re.fullmatch(r"[0-9a-f]{32}", install_id)
                or intent["supply_id"] != manifest.supply_id
            ):
                raise SupplyError("publication_conflict")
        else:
            with pending.open("xb") as output:
                output.write(
                    canonical_json(
                        {"install_id": install_id, "supply_id": manifest.supply_id}
                    )
                )
                output.flush()
                os.fsync(output.fileno())
            fsync_directory(root)
        target = _publish_tree(root, manifest, tree, install_id)
        with tempfile.TemporaryDirectory(prefix="paperradar-pi-rebuild-") as work:
            _inspect(target, Path(work), manifest, process)
        commit_install(database, manifest, root_id, install_id)
        residuals = False
        try:
            pending.unlink()
            fsync_directory(root)
        except OSError:
            residuals = True
        return PrepareResult(manifest.supply_id, install_id, residuals=residuals)


def rebuild_supply(
    database: Path,
    supply_id: str,
    install_root: Path,
    *,
    data_root: Path,
    config_root: Path,
    material_root: Path,
    downloader: Downloader | None = None,
    runner: Runner | None = None,
    proxy: str | None = None,
) -> PrepareResult:
    """联网重新下载固定大包,由历史材料重建新实例,不重新冻结或激活。"""
    record = show_supply(database, supply_id)
    manifest = record.manifest
    staging = None
    result = None
    cleanup_incomplete = False
    try:
        _platform(manifest)
        proxy = checked_proxy(proxy)
        root = safe_roots(database, install_root, data_root, config_root, material_root)
        database = database.resolve()
        local_filesystem(root)
        check_space(root)
        root_id = _owned_root(database, root)
        staging = root / f".staging-{uuid.uuid4().hex}"
        staging.mkdir(mode=0o700)
        process = runner or ProcessRunner()
        tree, _, _ = _build_tree(
            staging,
            record.materials,
            manifest.node_version,
            manifest.npm_version,
            manifest.pi_version,
            manifest.node_sha256,
            downloader or HttpDownloader(),
            process,
            proxy,
            frozen_tree=manifest.expected_tree,
            frozen_entry=manifest.pi_entry,
        )
        result = _publish_rebuild(database, root, root_id, manifest, tree, process)
    except SupplyError as error:
        _record_rebuild_failure(database, supply_id, error.reason)
        raise
    except KeyboardInterrupt:
        _record_rebuild_failure(database, supply_id, "operation_interrupted")
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError):
        _record_rebuild_failure(database, supply_id, "rebuild_failed")
        raise SupplyError("rebuild_failed") from None
    finally:
        if staging is not None:
            try:
                _cleanup_staging(staging)
            except OSError:
                cleanup_incomplete = True
    assert result is not None
    return replace(result, residuals=result.residuals or cleanup_incomplete)


def _record_rebuild_failure(
    database: Path, supply_id: str, reason: SupplyReason
) -> None:
    try:
        append_rebuild_failure(database, supply_id, reason)
    except SupplyError:
        raise SupplyError("failure_record_failed", execution_reason=reason) from None


def _build_tree(
    staging: Path,
    materials: dict[str, bytes],
    node_version: str,
    npm_version: str,
    pi_version: str,
    node_sha256: str,
    download: Downloader,
    process: Runner,
    proxy: str | None,
    *,
    frozen_tree: str | None = None,
    frozen_entry: str | None = None,
) -> tuple[Path, str, str]:
    node_base = f"https://nodejs.org/dist/v{node_version}"
    node_name = f"node-v{node_version}-linux-x64.tar.xz"
    derived = materials["derived-lock.json"]
    archive = download.fetch(
        node_base + "/" + node_name, limit=ARCHIVE_LIMIT, proxy=proxy
    )
    if sha256(archive) != node_sha256:
        raise SupplyError("node_checksum_mismatch")
    tree, work = staging / "tree", staging / "work"
    tree.mkdir()
    extract_node(archive, tree / "node", node_version)
    app = tree / "app"
    app.mkdir()
    (app / "package.json").write_bytes(materials["package.json"])
    (app / "package-lock.json").write_bytes(derived)
    node, npm = (
        tree / "node/bin/node",
        tree / "node/lib/node_modules/npm/bin/npm-cli.js",
    )
    if not node.is_file() or not npm.is_file() or not node.stat().st_mode & 0o111:
        raise SupplyError("entry_invalid")
    env = _environment(work, node, proxy)

    def run(argv: tuple[str, ...], cwd: Path) -> bytes:
        return process.run(argv, cwd=cwd, env=env, timeout=240, limit=OUTPUT_LIMIT)

    if (
        run((str(node), "--version"), work / "cwd").strip()
        != ("v" + node_version).encode()
    ):
        raise SupplyError("node_version_mismatch")
    if (
        run((str(node), str(npm), "--version"), work / "cwd").strip()
        != npm_version.encode()
    ):
        raise SupplyError("npm_version_mismatch")
    run((str(node), str(npm), *NPM_FLAGS), app)
    if (app / "package.json").read_bytes() != materials["package.json"] or (
        app / "package-lock.json"
    ).read_bytes() != derived:
        raise SupplyError("installed_material_changed")
    package_root = app / "node_modules" / PI_PACKAGE
    installed = object_bytes(_read_small(package_root / "package.json"))
    if installed.get("name") != PI_PACKAGE or installed.get("version") != pi_version:
        raise SupplyError("pi_version_mismatch")
    check_engine(installed.get("engines", {}).get("node"), node_version)
    bin_value = installed.get("bin")
    entry = bin_value.get("pi") if isinstance(bin_value, dict) else bin_value
    if (
        not isinstance(entry, str)
        or PurePosixPath(entry).is_absolute()
        or ".." in PurePosixPath(entry).parts
    ):
        raise SupplyError("entry_invalid")
    pi = package_root / entry
    if not pi.is_file() or not pi.resolve().is_relative_to(package_root.resolve()):
        raise SupplyError("entry_invalid")
    expected_tree = tree_hash(tree)
    if frozen_tree is not None and expected_tree != frozen_tree:
        raise SupplyError("tree_mismatch")
    if frozen_entry is not None and pi.relative_to(tree).as_posix() != frozen_entry:
        raise SupplyError("entry_invalid")
    if (
        run((str(node), str(pi), *PI_FLAGS, "--version"), work / "cwd").strip()
        != pi_version.encode()
    ):
        raise SupplyError("pi_version_mismatch")
    run((str(node), str(pi), *PI_FLAGS, "--help"), work / "cwd")
    if any((work / "sessions").iterdir()) or tree_hash(tree) != expected_tree:
        raise SupplyError("startup_side_effect")
    return tree, expected_tree, pi.relative_to(tree).as_posix()


def prepare_supply(
    database: Path,
    snapshot_reference: str,
    adapter_slot: str,
    request_path: Path,
    install_root: Path,
    *,
    data_root: Path,
    config_root: Path,
    material_root: Path,
    downloader: Downloader | None = None,
    runner: Runner | None = None,
    proxy: str | None = None,
) -> PrepareResult:
    """准备并冻结,不激活;显式根仅用于安全范围,不进入供给身份。"""
    staging: Path | None = None
    try:
        try:
            request = validate_yaml_bytes(
                _read_small(request_path), SupplyRequest, "supply"
            )
        except (ConfigError, SupplyError):
            raise SupplyError("request_invalid") from None
        proxy = checked_proxy(proxy)
        root = safe_roots(database, install_root, data_root, config_root, material_root)
        database = database.resolve()
        local_filesystem(root)
        libc_info = os.confstr("CS_GNU_LIBC_VERSION") or ""
        libc, _, libc_version = libc_info.partition(" ")
        if (
            platform.system() != "Linux"
            or platform.machine() != request.platform.arch
            or libc != request.platform.libc
            or not libc_version
        ):
            raise SupplyError("platform_mismatch")
        snapshot_id = resolve_config_snapshot_reference(database, snapshot_reference)
        snapshot = load_config_snapshot(database, snapshot_id)
        selected = snapshot.adapter_selections.get(adapter_slot)
        if (
            adapter_slot not in {"screening", "reuse_assessment", "reading"}
            or selected is None
        ):
            raise SupplyError("adapter_missing")
        material = snapshot.materials[(MaterialKind.ADAPTER, "pi-rpc", selected)]
        adapter = PiAdapter.model_validate(object_bytes(material.config_json.encode()))
        old = read_records(database)
        old_ids = frozenset(record.supply_id for record in old)
        check_space(root)
        root_id = _owned_root(database, root)
        download = downloader or HttpDownloader()
        process = runner or ProcessRunner()
        base = f"https://pi.dev/api/installer/releases/{adapter.pi_version}"
        materials = {
            role: download.fetch(base + suffix, limit=SMALL_LIMIT, proxy=proxy)
            for role, suffix in (
                ("package.json", "/package.json"),
                ("package-lock.json", "/package-lock.json"),
                ("release.json", ""),
            )
        }
        derived, supplements = derive_lock(
            materials["package.json"],
            materials["package-lock.json"],
            materials["release.json"],
            adapter.pi_version,
            request.node_version,
        )
        materials["derived-lock.json"] = derived
        materials["integrity-supplements.json"] = supplements
        node_base = f"https://nodejs.org/dist/v{request.node_version}"
        materials["SHASUMS256.txt"] = download.fetch(
            node_base + "/SHASUMS256.txt", limit=SMALL_LIMIT, proxy=proxy
        )
        node_name = f"node-v{request.node_version}-linux-x64.tar.xz"
        expected = f"{request.node_sha256}  {node_name}"
        if materials["SHASUMS256.txt"].decode().splitlines().count(expected) != 1:
            raise SupplyError("node_checksum_mismatch")
        d5 = _freeze_d5(request, request_path, materials, old)
        material_hashes = {key: sha256(raw) for key, raw in materials.items()}
        for record in old:
            frozen = record.manifest
            if (
                frozen.pi_version == adapter.pi_version
                and frozen.node_version == request.node_version
                and frozen.npm_version == request.npm_version
                and frozen.platform == request.platform
                and frozen.libc_version == libc_version
                and frozen.node_sha256 == request.node_sha256
                and {
                    k: v
                    for k, v in frozen.materials.items()
                    if not k.startswith("d5-evidence/")
                }
                == {
                    k: v
                    for k, v in material_hashes.items()
                    if not k.startswith("d5-evidence/")
                }
            ):
                raise SupplyError("already_prepared_use_rebuild")
        staging = root / f".staging-{uuid.uuid4().hex}"
        staging.mkdir(mode=0o700)
        tree, expected_tree, pi_entry = _build_tree(
            staging,
            materials,
            request.node_version,
            request.npm_version,
            adapter.pi_version,
            request.node_sha256,
            download,
            process,
            proxy,
        )
        manifest = SupplyManifest(
            pi_version=adapter.pi_version,
            node_version=request.node_version,
            npm_version=request.npm_version,
            node_sha256=request.node_sha256,
            platform=request.platform,
            libc_version=libc_version,
            materials=material_hashes,
            expected_tree=expected_tree,
            node_entry="node/bin/node",
            npm_entry="node/lib/node_modules/npm/bin/npm-cli.js",
            pi_entry=pi_entry,
            d5=d5,
        )
        return _publish(database, root, root_id, manifest, materials, tree, old_ids)
    except ConfigError:
        raise SupplyError("snapshot_invalid") from None
    except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError):
        raise SupplyError("prepare_failed") from None
    finally:
        if staging is not None:
            try:
                _cleanup_staging(staging)
            except OSError:
                raise SupplyError("prepare_failed") from None
