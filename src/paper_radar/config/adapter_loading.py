"""适配器文件装载与历史引用校验。沿用配置材料登记包络。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from paper_radar.config.adapters import (
    ADAPTER_NAME,
    SYSTEM_PROMPT_NAME,
    AdapterSemantics,
    PiAdapter,
)
from paper_radar.config.compile import CompiledMaterial, Material, MaterialKind
from paper_radar.config.errors import ConfigError
from paper_radar.config.schema import MODEL_SLOTS, ModelProtocol, Models, Settings
from paper_radar.config.yaml_loader import read_prompt, read_yaml


def selected_adapter_materials(
    config_root: Path, settings: Settings, models: Models | None
) -> tuple[tuple[CompiledMaterial, ...], tuple[tuple[str, AdapterSemantics], ...]]:
    """同一声明版本只装载一次。所有资源绑定精确内容而非外部路径。"""
    adapters: dict[str, PiAdapter] = {}
    prompts: dict[str, bytes] = {}
    materials: list[CompiledMaterial] = []
    for slot in MODEL_SLOTS:
        version = getattr(settings.adapters, slot)
        if version is None or version in adapters:
            continue
        raw, config = read_yaml(
            config_root / "adapters" / f"{version}.yaml", PiAdapter, "adapter"
        )
        if config.version != version:
            raise ConfigError(
                "adapter.version：与 selector 不一致；请选择匹配的声明版本"
            )
        adapters[version] = config
        materials.append(
            CompiledMaterial(
                Material(MaterialKind.ADAPTER, ADAPTER_NAME, version, raw),
                config.model_dump(mode="json"),
            )
        )
        resource = config.resources[0]
        if resource.version not in prompts:
            prompt = read_prompt(
                config_root / "prompts" / f"pi-system-{resource.version}.md",
                SYSTEM_PROMPT_NAME,
            )
            prompts[resource.version] = prompt
            materials.append(
                CompiledMaterial(
                    Material(
                        MaterialKind.PROMPT,
                        SYSTEM_PROMPT_NAME,
                        resource.version,
                        prompt,
                    ),
                    {"text": prompt.decode("utf-8")},
                )
            )
    semantics = adapter_semantics(settings, models, adapters, prompts)
    return tuple(materials), semantics


def adapter_semantics(
    settings: Settings,
    models: Models | None,
    adapters: Mapping[str, PiAdapter],
    prompts: Mapping[str, bytes],
) -> tuple[tuple[str, AdapterSemantics], ...]:
    """活跃装载和 SQLite 回放共用依赖检查。不探测模型或安装资源。"""
    selected_versions = {
        version
        for slot in MODEL_SLOTS
        if (version := getattr(settings.adapters, slot)) is not None
    }
    if set(adapters) != selected_versions:
        raise ConfigError("adapter：材料与阶段选择不一致；请检查版本引用")
    expected_prompts = {config.resources[0].version for config in adapters.values()}
    if set(prompts) != expected_prompts:
        raise ConfigError("adapter.resources：资源引用不完整；请检查系统提示词版本")
    result: list[tuple[str, AdapterSemantics]] = []
    for slot in MODEL_SLOTS:
        version = getattr(settings.adapters, slot)
        if version is None:
            continue
        config = adapters[version]
        model = getattr(models, slot) if models is not None else None
        if model is not None and model.protocol not in (
            None,
            ModelProtocol.PROMPT_ONLY,
        ):
            raise ConfigError(
                f"models.{slot}.protocol：Pi V1 只接受 prompt_only；"
                "请新建 models 版本并明确选择该协议"
            )
        resource = config.resources[0]
        raw = prompts[resource.version]
        material = Material(MaterialKind.PROMPT, resource.name, resource.version, raw)
        if material.raw_sha256 != resource.sha256:
            raise ConfigError(
                "adapter.resources.sha256：系统提示词哈希不匹配；请恢复材料或创建新版本"
            )
        result.append((slot, config.semantics(raw.decode("utf-8"))))
    return tuple(result)
