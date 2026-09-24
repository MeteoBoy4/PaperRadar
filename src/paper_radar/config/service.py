"""公共 check/compile/load 服务。加载材料并组织持久化事务。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from paper_radar.config.compile import (
    FORMAT_VERSION,
    Material,
    RuntimeConfigSnapshot,
    compile_snapshot,
)
from paper_radar.config.errors import ConfigError
from paper_radar.config.identity import canonical_json, sha256
from paper_radar.config.schema import Profile, Settings
from paper_radar.config.yaml_loader import read_yaml, validate_yaml_bytes
from paper_radar.storage.database import open_database, require_current_revision
from paper_radar.storage.errors import StorageError
from paper_radar.storage.records import VersionRecord
from paper_radar.storage.repository import check_version, read_snapshot, save_snapshot

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _selected_materials(
    settings_path: Path,
) -> tuple[Settings, Profile | None, Material | None]:
    _, settings = read_yaml(settings_path, Settings, "settings")
    unsupported = [
        name
        for name in ("topics", "journals", "escalation", "extraction")
        if getattr(settings, name) is not None
    ]
    for group in ("models", "prompts", "contracts"):
        selected = getattr(settings, group)
        unsupported.extend(
            f"{group}.{name}"
            for name, value in selected.model_dump().items()
            if value is not None
        )
    if unsupported:
        raise ConfigError(
            f"settings.{unsupported[0]}：本票尚不支持非空选择；请移除或设为 null"
        )
    if settings.profile is None:
        return settings, None, None
    # settings.yaml 的父目录是 config/。不依赖当前工作目录。
    path = settings_path.parent / "profiles" / f"{settings.profile}.yaml"
    raw, profile = read_yaml(path, Profile, "profile")
    if profile.version != settings.profile:
        raise ConfigError("profile.version：与 settings.profile 不一致；请选择匹配版本")
    return settings, profile, Material("profile", "profile", profile.version, raw)


def _version_record(material: Material | None) -> VersionRecord | None:
    if material is None:
        return None
    return VersionRecord(material.kind, material.name, material.version, material.raw)


def check_config(settings_path: Path, database: Path) -> RuntimeConfigSnapshot:
    try:
        engine = open_database(database, mode="ro")
        try:
            require_current_revision(engine)
            settings, profile, material = _selected_materials(settings_path)
            check_version(engine, _version_record(material))
            return compile_snapshot(settings, profile, material)
        finally:
            engine.dispose()
    except StorageError as error:
        raise ConfigError(str(error)) from None
    except SQLAlchemyError:
        raise ConfigError("数据库读取失败；请检查数据库状态") from None


def compile_config(settings_path: Path, database: Path) -> RuntimeConfigSnapshot:
    try:
        engine = open_database(database, mode="rw")
        try:
            require_current_revision(engine)
            settings, profile, material = _selected_materials(settings_path)
            snapshot = compile_snapshot(settings, profile, material)
            save_snapshot(
                engine,
                snapshot.snapshot_id,
                snapshot.payload_json,
                _version_record(material),
            )
            return snapshot
        finally:
            engine.dispose()
    except StorageError as error:
        raise ConfigError(str(error)) from None
    except SQLAlchemyError:
        raise ConfigError("数据库访问失败；请检查数据库状态") from None


def load_config_snapshot(database: Path, snapshot_id: str) -> RuntimeConfigSnapshot:
    if not _SHA256.fullmatch(snapshot_id):
        raise ConfigError("快照身份必须是完整 64 位小写 SHA-256")
    try:
        engine = open_database(database, mode="ro")
        try:
            require_current_revision(engine)
            saved_json, materials = read_snapshot(engine, snapshot_id)
        finally:
            engine.dispose()
    except StorageError as error:
        raise ConfigError(str(error)) from None
    try:
        saved: Any = json.loads(saved_json)
        if not isinstance(saved, dict):
            raise ValueError
        if saved.get("format_version") != FORMAT_VERSION:
            raise ConfigError("快照编译格式不受当前程序支持；请使用匹配版本加载")
        if (
            canonical_json(saved) != saved_json.encode("utf-8")
            or sha256(saved_json.encode("utf-8")) != snapshot_id
        ):
            raise ValueError
        selector = saved["selectors"]["profile"]
        settings = Settings.model_validate({"profile": selector})
        if selector is None:
            if materials:
                raise ValueError
            profile = None
            material = None
        else:
            if len(materials) != 1:
                raise ValueError
            kind, name, version, raw_hash, raw = materials[0]
            if (kind, name, version) != ("profile", "profile", selector):
                raise ValueError
            material = Material(kind, name, version, raw)
            if material.raw_sha256 != raw_hash:
                raise ValueError
            profile = validate_yaml_bytes(raw, Profile, "profile")
            if not isinstance(profile, Profile) or profile.version != selector:
                raise ValueError
        rebuilt = compile_snapshot(settings, profile, material)
        if rebuilt.snapshot_id != snapshot_id or rebuilt.payload_json != saved_json:
            raise ValueError
        return rebuilt
    except ConfigError:
        raise
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise ConfigError("快照内容或版本引用损坏；请检查数据库") from None
