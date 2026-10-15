"""配置材料的封闭逻辑名称。列表摘要与历史加载共用。"""

from types import MappingProxyType

from paper_radar.config.adapters import ADAPTER_NAME, SYSTEM_PROMPT_NAME
from paper_radar.config.compile import MaterialKind
from paper_radar.config.schema import PromptName
from paper_radar.contracts import ContractName

MATERIAL_NAMES = MappingProxyType(
    {
        MaterialKind.PROFILE: frozenset({"profile"}),
        MaterialKind.MODELS: frozenset({"models"}),
        MaterialKind.TOPICS: frozenset({"topics"}),
        MaterialKind.JOURNALS: frozenset({"journals"}),
        MaterialKind.ESCALATION: frozenset({"escalation"}),
        MaterialKind.EXTRACTION: frozenset({"extraction"}),
        MaterialKind.READ: frozenset({"read"}),
        MaterialKind.ADAPTER: frozenset({ADAPTER_NAME}),
        MaterialKind.PROMPT: frozenset({*PromptName, SYSTEM_PROMPT_NAME}),
        MaterialKind.CONTRACT_SCHEMA: frozenset(ContractName),
        MaterialKind.CONTRACT_MANIFEST: frozenset(ContractName),
    }
)
