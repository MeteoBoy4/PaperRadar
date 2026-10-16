"""版本材料的共同验证与组装。不读取来源、不访问数据库。

当前仅接收已登记的 YAML 种类。来源交入 Material; 其他材料仍由各自
验证器处理后参与组装。新增 YAML 种类无需在当前装载与历史回放分别增加分支。
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from paper_radar.config.adapters import AdapterSemantics
from paper_radar.config.compile import (
    CompiledMaterial,
    Material,
    MaterialKind,
    SelectedMaterials,
)
from paper_radar.config.errors import ConfigError
from paper_radar.config.escalation import Escalation
from paper_radar.config.extraction import Extraction
from paper_radar.config.journals import Journals
from paper_radar.config.read import ReadConfig
from paper_radar.config.schema import Models, Profile, Settings
from paper_radar.config.topics import Topics
from paper_radar.config.yaml_loader import validate_yaml_bytes

# 仅约束当前解码器目录。MaterialAssembly 的入口不暴露这些具体种类。
type _YamlConfig = (
    Profile | Models | Topics | Journals | Escalation | Extraction | ReadConfig
)


@dataclass(frozen=True, slots=True)
class _YamlSpec:
    kind: MaterialKind
    model: type[_YamlConfig]
    folder: str

    def selected_version(self, settings: Settings) -> str | None:
        version: str | None = getattr(settings, self.kind.value)
        return version


# 顺序也是当前装载的首次报错顺序, 不能按材料名排序。
_YAML_SPECS = (
    _YamlSpec(MaterialKind.PROFILE, Profile, "profiles"),
    _YamlSpec(MaterialKind.MODELS, Models, "models"),
    _YamlSpec(MaterialKind.TOPICS, Topics, "topics"),
    _YamlSpec(MaterialKind.JOURNALS, Journals, "journals"),
    _YamlSpec(MaterialKind.ESCALATION, Escalation, "screening"),
    _YamlSpec(MaterialKind.EXTRACTION, Extraction, "extraction"),
    _YamlSpec(MaterialKind.READ, ReadConfig, "read"),
)
_BY_KEY = {(spec.kind, spec.kind.value): spec for spec in _YAML_SPECS}


def selected_yaml_paths(settings: Settings) -> Iterator[tuple[MaterialKind, str, str]]:
    """按既有顺序给出种类、声明版本和配置目录下的相对路径。"""
    for spec in _YAML_SPECS:
        version = spec.selected_version(settings)
        if version is not None:
            yield spec.kind, version, f"{spec.folder}/{version}.yaml"


def _compiled_config(config: BaseModel) -> dict[str, Any]:
    if isinstance(config, Extraction):
        return config.compiled_config()
    if isinstance(config, Profile):
        return config.model_dump()
    return config.model_dump(mode="json")


@dataclass(frozen=True, slots=True)
class _ValidatedMaterial:
    """配置对象和材料只由同一次解析配对, 不接受调用方分别提供。"""

    config: BaseModel
    compiled: CompiledMaterial


class MaterialAssembly:
    """拥有共同材料约束, 保留来源各自的错误语义与检查顺序。

    选中材料按来源到达顺序验证; 历史调用方可在其他引用检查前要求完整性。
    finish 生成纯值 SelectedMaterials, 供既有编译器使用。此对象仅在单次
    装载内使用; frozen 配对不宣称内部 Pydantic 对象具有深度不可变性。
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._validated: dict[MaterialKind, _ValidatedMaterial] = {}
        self._additional: list[CompiledMaterial] = []

    def add_selected(self, material: Material) -> None:
        """验证当前选择的原始材料, 版本不一致沿用字段级中文指引。"""
        spec = _BY_KEY[(material.kind, material.name)]
        config = validate_yaml_bytes(material.raw, spec.model, material.kind.value)
        if config.version != spec.selected_version(self._settings):
            label = material.kind.value
            raise ConfigError(
                f"{label}.version：与 settings.{label} 不一致；请选择匹配版本"
            )
        self._remember(config, CompiledMaterial(material, _compiled_config(config)))

    def accept_stored(self, material: Material, entry: Mapping[str, Any]) -> bool:
        """接收已核对字节哈希的历史材料; 非本模块种类交回原验证器。"""
        spec = _BY_KEY.get((material.kind, material.name))
        if spec is None:
            return False
        config = validate_yaml_bytes(material.raw, spec.model, material.kind.value)
        if (
            config.version != spec.selected_version(self._settings)
            or _compiled_config(config) != entry["config"]
        ):
            # 来源负责映射为原有的历史损坏消息; YAML ConfigError 原样传播。
            raise ValueError
        self._remember(config, CompiledMaterial(material, entry["config"]))
        return True

    def _remember(self, config: BaseModel, compiled: CompiledMaterial) -> None:
        kind = compiled.material.kind
        self._validated[kind] = _ValidatedMaterial(config, compiled)
        if kind is not MaterialKind.PROFILE:
            self._additional.append(compiled)

    def require_complete(self) -> None:
        """所选即存在, 未选即缺席; 空集合配置与未配置仍不同。"""
        if any(
            (spec.selected_version(self._settings) is None)
            != (spec.kind not in self._validated)
            for spec in _YAML_SPECS
        ):
            raise ValueError

    def _config[T: BaseModel](self, kind: MaterialKind, model: type[T]) -> T | None:
        item = self._validated.get(kind)
        if item is None:
            return None
        if not isinstance(item.config, model):
            raise TypeError
        return item.config

    @property
    def models(self) -> Models | None:
        """模型适配器仍需已验证的模型槽配置进行协议检查。"""
        return self._config(MaterialKind.MODELS, Models)

    def finish(
        self,
        additional: tuple[CompiledMaterial, ...],
        adapters: tuple[tuple[str, AdapterSemantics], ...],
    ) -> SelectedMaterials:
        """统一生成配置对象及材料集合, 其他材料保持各自的接收权威。"""
        self.require_complete()
        profile = self._validated.get(MaterialKind.PROFILE)
        return SelectedMaterials(
            settings=self._settings,
            profile=self._config(MaterialKind.PROFILE, Profile),
            profile_material=profile.compiled.material if profile is not None else None,
            models=self.models,
            topics=self._config(MaterialKind.TOPICS, Topics),
            journals=self._config(MaterialKind.JOURNALS, Journals),
            escalation=self._config(MaterialKind.ESCALATION, Escalation),
            extraction=self._config(MaterialKind.EXTRACTION, Extraction),
            read=self._config(MaterialKind.READ, ReadConfig),
            additional=(*self._additional, *additional),
            adapters=adapters,
        )
