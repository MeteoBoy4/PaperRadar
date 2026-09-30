"""公共 check/compile/load 服务。加载材料并组织持久化事务。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from paper_radar.config.compile import (
    FORMAT_VERSION,
    CompiledMaterial,
    Material,
    MaterialKind,
    RuntimeConfigSnapshot,
    compile_snapshot,
)
from paper_radar.config.errors import ConfigError
from paper_radar.config.identity import canonical_json, sha256
from paper_radar.config.schema import Models, Profile, Settings
from paper_radar.config.topics import Topics
from paper_radar.config.yaml_loader import read_yaml, validate_yaml_bytes
from paper_radar.contracts import (
    ContractCheckError,
    ContractCheckErrorCategory,
    ContractName,
    ContractVersion,
    build_frozen_contract,
    check_frozen_contract,
)
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)
from paper_radar.storage.errors import StorageError
from paper_radar.storage.records import VersionRecord
from paper_radar.storage.repository import check_version, read_snapshot, save_snapshot

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PROFILE_KEY = (MaterialKind.PROFILE, "profile")
_MODELS_KEY = (MaterialKind.MODELS, "models")
_TOPICS_KEY = (MaterialKind.TOPICS, "topics")
_PROMPT_NAMES = ("boundary", "value")
_CONTRACT_NAMES = {
    "boundary": ContractName.BOUNDARY,
    "value_prediction": ContractName.VALUE_PREDICTION,
}
_CONTRACT_CHECK_GUIDANCE = {
    ContractCheckErrorCategory.INVALID_SELECTION: "请确认所选契约和版本已实现",
    ContractCheckErrorCategory.MISSING_SNAPSHOT: "请从版本控制恢复完整冻结快照",
    ContractCheckErrorCategory.UNREADABLE_SNAPSHOT: "请检查冻结快照的读取权限",
    ContractCheckErrorCategory.DAMAGED_SNAPSHOT: "请从版本控制恢复未损坏的冻结快照",
    ContractCheckErrorCategory.VERSION_MISMATCH: "请核对所选契约版本与冻结快照",
    ContractCheckErrorCategory.CONTENT_DRIFT: "请恢复权威快照；契约变化须创建新版本",
    ContractCheckErrorCategory.INVALID_TARGET: "请检查冻结契约目录布局",
    ContractCheckErrorCategory.PATH_ESCAPE: "请将冻结契约放在配置根目录内",
}


def _unsupported(settings: Settings) -> None:
    selected = [
        name
        for name in ("journals", "escalation", "extraction")
        if getattr(settings, name) is not None
    ]
    selected.extend(
        f"prompts.{name}"
        for name, value in settings.prompts.model_dump().items()
        if name not in _PROMPT_NAMES and value is not None
    )
    selected.extend(
        f"contracts.{name}"
        for name, value in settings.contracts.model_dump().items()
        if name not in _CONTRACT_NAMES and value is not None
    )
    if selected:
        raise ConfigError(
            f"settings.{selected[0]}：本票尚不支持非空选择；请移除或设为 null"
        )


def _read_prompt(path: Path, name: str) -> bytes:
    try:
        raw = path.read_bytes()
        raw.decode("utf-8")
        return raw
    except (OSError, UnicodeDecodeError):
        raise ConfigError(
            f"prompts.{name}：无法读取 UTF-8 提示词；请检查路径和编码"
        ) from None


def _contract_materials(
    root: Path, selector: str, name: ContractName, version: str
) -> tuple[CompiledMaterial, ...]:
    try:
        controlled_version = ContractVersion(version)
    except ValueError:
        raise ConfigError(
            f"contracts.{selector}：所选版本尚无权威契约；请选择已实现的 v1"
        ) from None
    try:
        contract = build_frozen_contract(name, controlled_version)
    except (ValueError, KeyError):
        raise ConfigError(
            f"contracts.{selector}：权威契约构造失败；请检查所选版本"
        ) from None
    try:
        check_frozen_contract(name, controlled_version, root / "contracts")
    except ContractCheckError as error:
        raise ConfigError(
            f"contracts.{selector}：{error.category.value}；"
            f"{_CONTRACT_CHECK_GUIDANCE[error.category]}"
        ) from None
    try:
        folder = root / "contracts" / Path(*contract.snapshot_parts)
        schema_raw = (folder / contract.schema_filename).read_bytes()
        manifest_raw = (folder / contract.manifest_filename).read_bytes()
    except OSError:
        raise ConfigError(
            f"contracts.{selector}：检查后无法读取冻结契约；请检查路径和权限并重试"
        ) from None
    if schema_raw != contract.schema_bytes or manifest_raw != contract.manifest_bytes:
        raise ConfigError(f"contracts.{selector}：冻结契约检查后内容变化；请重试")
    return (
        CompiledMaterial(
            Material(MaterialKind.CONTRACT_SCHEMA, name, version, schema_raw),
            json.loads(schema_raw),
        ),
        CompiledMaterial(
            Material(MaterialKind.CONTRACT_MANIFEST, name, version, manifest_raw),
            json.loads(manifest_raw),
        ),
    )


def _selected_materials(
    settings_path: Path,
) -> tuple[
    Settings,
    Profile | None,
    Material | None,
    Models | None,
    tuple[CompiledMaterial, ...],
    Topics | None,
]:
    _, settings = read_yaml(settings_path, Settings, "settings")
    _unsupported(settings)
    root = settings_path.parent.parent
    profile: Profile | None = None
    profile_material: Material | None = None
    if settings.profile is not None:
        raw, profile = read_yaml(
            settings_path.parent / "profiles" / f"{settings.profile}.yaml",
            Profile,
            "profile",
        )
        if profile.version != settings.profile:
            raise ConfigError(
                "profile.version：与 settings.profile 不一致；请选择匹配版本"
            )
        profile_material = Material(*_PROFILE_KEY, profile.version, raw)

    models: Models | None = None
    additional: list[CompiledMaterial] = []
    if settings.models is not None:
        raw, models = read_yaml(
            settings_path.parent / "models" / f"{settings.models}.yaml",
            Models,
            "models",
        )
        if models.version != settings.models:
            raise ConfigError(
                "models.version：与 settings.models 不一致；请选择匹配版本"
            )
        additional.append(
            CompiledMaterial(
                Material(*_MODELS_KEY, models.version, raw),
                models.model_dump(mode="json"),
            )
        )
    topics: Topics | None = None
    if settings.topics is not None:
        raw, topics = read_yaml(
            settings_path.parent / "topics" / f"{settings.topics}.yaml",
            Topics,
            "topics",
        )
        if topics.version != settings.topics:
            raise ConfigError(
                "topics.version：与 settings.topics 不一致；请选择匹配版本"
            )
        additional.append(
            CompiledMaterial(
                Material(*_TOPICS_KEY, topics.version, raw),
                topics.model_dump(mode="json"),
            )
        )
    for name in _PROMPT_NAMES:
        version = getattr(settings.prompts, name)
        if version is not None:
            raw = _read_prompt(
                root / "prompts/screening" / f"{name}-{version}.md", name
            )
            additional.append(
                CompiledMaterial(
                    Material(MaterialKind.PROMPT, name, version, raw),
                    {"text": raw.decode("utf-8")},
                )
            )
    for selector, contract_name in _CONTRACT_NAMES.items():
        version = getattr(settings.contracts, selector)
        if version is not None:
            additional.extend(
                _contract_materials(root, selector, contract_name, version)
            )
    return settings, profile, profile_material, models, tuple(additional), topics


def _records(
    profile_material: Material | None, additional: tuple[CompiledMaterial, ...]
) -> tuple[VersionRecord, ...]:
    items = ([profile_material] if profile_material is not None else []) + [
        item.material for item in additional
    ]
    return tuple(
        VersionRecord(item.kind, item.name, item.version, item.raw) for item in items
    )


def check_config(settings_path: Path, database: Path) -> RuntimeConfigSnapshot:
    try:
        engine = open_database(database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            settings, profile, material, models, additional, topics = (
                _selected_materials(settings_path)
            )
            check_version(engine, _records(material, additional))
            return compile_snapshot(
                settings, profile, material, models, additional, topics
            )
        finally:
            engine.dispose()
    except StorageError as error:
        raise ConfigError(str(error)) from None
    except SQLAlchemyError:
        raise ConfigError("数据库读取失败；请检查数据库状态") from None


def compile_config(settings_path: Path, database: Path) -> RuntimeConfigSnapshot:
    try:
        engine = open_database(database, mode=DatabaseMode.READ_WRITE)
        try:
            require_current_revision(engine)
            settings, profile, material, models, additional, topics = (
                _selected_materials(settings_path)
            )
            snapshot = compile_snapshot(
                settings, profile, material, models, additional, topics
            )
            save_snapshot(
                engine,
                snapshot.snapshot_id,
                snapshot.payload_json,
                _records(material, additional),
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
        engine = open_database(database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            saved_json, stored = read_snapshot(engine, snapshot_id)
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
            canonical_json(saved) != saved_json.encode()
            or sha256(saved_json.encode()) != snapshot_id
        ):
            raise ValueError
        settings = Settings.model_validate(saved["selectors"])
        listed = saved["materials"]
        if not isinstance(listed, list) or len(listed) != len(stored):
            raise ValueError
        by_key = {
            (kind, name, version): (raw_hash, raw)
            for kind, name, version, raw_hash, raw in stored
        }
        if len(by_key) != len(stored):
            raise ValueError
        profile: Profile | None = None
        profile_material: Material | None = None
        models: Models | None = None
        topics: Topics | None = None
        additional: list[CompiledMaterial] = []
        for entry in listed:
            key = (entry["kind"], entry["name"], entry["version"])
            raw_hash, raw = by_key.pop(key)
            material = Material(MaterialKind(key[0]), key[1], key[2], raw)
            if material.raw_sha256 != raw_hash or raw_hash != entry["raw_sha256"]:
                raise ValueError
            if key[:2] == _PROFILE_KEY:
                profile = validate_yaml_bytes(raw, Profile, "profile")
                if (
                    profile.version != settings.profile
                    or profile.model_dump() != entry["config"]
                ):
                    raise ValueError
                profile_material = material
            elif key[:2] == _MODELS_KEY:
                models = validate_yaml_bytes(raw, Models, "models")
                if (
                    models.version != settings.models
                    or models.model_dump(mode="json") != entry["config"]
                ):
                    raise ValueError
                additional.append(CompiledMaterial(material, entry["config"]))
            elif key[:2] == _TOPICS_KEY:
                topics = validate_yaml_bytes(raw, Topics, "topics")
                if (
                    topics.version != settings.topics
                    or topics.model_dump(mode="json") != entry["config"]
                ):
                    raise ValueError
                additional.append(CompiledMaterial(material, entry["config"]))
            elif (
                material.kind is MaterialKind.PROMPT and material.name in _PROMPT_NAMES
            ):
                if (
                    key[2] != getattr(settings.prompts, material.name)
                    or {"text": raw.decode("utf-8")} != entry["config"]
                ):
                    raise ValueError
                additional.append(CompiledMaterial(material, entry["config"]))
            elif (
                material.kind
                in (MaterialKind.CONTRACT_SCHEMA, MaterialKind.CONTRACT_MANIFEST)
                and material.name in _CONTRACT_NAMES.values()
            ):
                selector = next(
                    field
                    for field, name in _CONTRACT_NAMES.items()
                    if name == material.name
                )
                if (
                    key[2] != getattr(settings.contracts, selector)
                    or json.loads(raw) != entry["config"]
                ):
                    raise ValueError
                additional.append(CompiledMaterial(material, entry["config"]))
            else:
                raise ValueError
        if (
            by_key
            or (settings.profile is None) != (profile is None)
            or (settings.models is None) != (models is None)
            or (settings.topics is None) != (topics is None)
        ):
            raise ValueError
        expected_keys = {
            (MaterialKind.PROMPT, name, version)
            for name in _PROMPT_NAMES
            if (version := getattr(settings.prompts, name)) is not None
        } | {
            (kind, name, version)
            for selector, name in _CONTRACT_NAMES.items()
            if (version := getattr(settings.contracts, selector)) is not None
            for kind in (MaterialKind.CONTRACT_SCHEMA, MaterialKind.CONTRACT_MANIFEST)
        }
        actual_keys = {
            (item.material.kind, item.material.name, item.material.version)
            for item in additional
            if item.material.kind
            in (
                MaterialKind.PROMPT,
                MaterialKind.CONTRACT_SCHEMA,
                MaterialKind.CONTRACT_MANIFEST,
            )
        }
        if expected_keys != actual_keys:
            raise ValueError
        rebuilt = compile_snapshot(
            settings, profile, profile_material, models, tuple(additional), topics
        )
        if rebuilt.snapshot_id != snapshot_id or rebuilt.payload_json != saved_json:
            raise ValueError
        return rebuilt
    except ConfigError:
        raise
    except (KeyError, TypeError, ValueError, UnicodeDecodeError):
        raise ConfigError("快照内容或版本引用损坏；请检查数据库") from None
