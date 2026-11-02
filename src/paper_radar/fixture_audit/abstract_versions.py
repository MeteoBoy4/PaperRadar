"""主摘要规则的封闭身份与生产 parser 版本映射。"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

AbstractRulesVersion = Literal["audit-abstract-v1", "audit-abstract-v2"]
AbstractParserVersion = Literal[1, 2]
ABSTRACT_RULES_VERSION: AbstractRulesVersion = "audit-abstract-v1"
WILEY_ABSTRACT_RULES_VERSION: AbstractRulesVersion = "audit-abstract-v2"
ABSTRACT_PARSER_VERSIONS: Mapping[AbstractRulesVersion, AbstractParserVersion] = (
    MappingProxyType({ABSTRACT_RULES_VERSION: 1, WILEY_ABSTRACT_RULES_VERSION: 2})
)


def parse_abstract_rules_version(value: object) -> AbstractRulesVersion:
    if type(value) is str:
        for version in ABSTRACT_PARSER_VERSIONS:
            if value == version:
                return version
    raise ValueError("unsupported_abstract_rules_version")


def abstract_parser_version(rules: AbstractRulesVersion) -> AbstractParserVersion:
    return ABSTRACT_PARSER_VERSIONS[rules]


def abstract_rules_for_parser(value: object) -> AbstractRulesVersion:
    if type(value) is int:
        for rules, parser in ABSTRACT_PARSER_VERSIONS.items():
            if value == parser:
                return rules
    raise ValueError("unsupported_feed_parser_version")
