"""期刊字段、ISSN 校验位和规范化冲突的脱敏验证。"""

import sqlite3
from pathlib import Path

import pytest

from paper_radar.config import ConfigError, check_config, compile_config
from tests.config_journals_support import journal_inputs


@pytest.mark.parametrize("field", ["issn_l", "issns"])
@pytest.mark.parametrize(
    ("identifier", "guidance"),
    [
        ("2169-8970", "校验位"),
        ("1234-567x", "校验位"),
        ("PRIVATE_MARKER", "格式"),
        (" 2169-897X", "格式"),
        ("２１６９-８９７X", "格式"),
        ("2169--897X", "格式"),
    ],
)
def test_invalid_issn_is_rejected_with_actionable_safe_reason(
    tmp_path: Path, field: str, identifier: str, guidance: str
) -> None:
    line = (
        f"issn_l: '{identifier}'"
        if field == "issn_l"
        else f"issn_l: 2169-897X, issns: ['{identifier}']"
    )
    settings, database = journal_inputs(
        tmp_path,
        f"version: journals-v1\njournals: [{{{line}, name: N, tier: normal}}]\n",
    )
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError) as error:
            operation(settings, database)
        assert f"journals.journals.0.{field}" in str(error.value)
        assert guidance in str(error.value)
        assert "请" in str(error.value)
        assert identifier not in str(error.value)
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)


@pytest.mark.parametrize(
    "entries",
    [
        "[{issn_l: 1477-870x, issns: [1477870X, 1477-870x], name: N, tier: low}]",
        "[{issn_l: 1477-870x, name: N, tier: normal},"
        "{issn_l: 1477870X, name: N, tier: preferred}]",
        "[{issn_l: 0035-9009, issns: [1477870x], name: N, tier: normal},"
        "{issn_l: 1477-870X, name: M, tier: low}]",
        "[{issn_l: 0035-9009, issns: [1477-870x], name: N, tier: normal},"
        "{issn_l: 2169-897X, issns: [1477870X], name: M, tier: normal}]",
    ],
)
def test_normalized_identifier_conflicts_are_rejected(
    tmp_path: Path, entries: str
) -> None:
    settings, database = journal_inputs(
        tmp_path, f"version: journals-v1\njournals: {entries}\n"
    )
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError, match="规范化后的期刊标识重复或冲突"):
            operation(settings, database)
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)


@pytest.mark.parametrize(
    ("entry", "field"),
    [
        ("{name: N, tier: normal}", "issn_l"),
        ("{issn_l: null, name: N, tier: normal}", "issn_l"),
        ("{issn_l: 27697525, name: N, tier: normal}", "issn_l"),
        ("{issn_l: 2769-7525, tier: normal}", "name"),
        ("{issn_l: 2769-7525, name: null, tier: normal}", "name"),
        ("{issn_l: 2769-7525, name: '  ', tier: normal}", "name"),
        ("{issn_l: 2769-7525, name: N}", "tier"),
        ("{issn_l: 2769-7525, name: N, tier: PRIVATE_MARKER}", "tier"),
        ("{issn_l: 2769-7525, name: N, tier: Preferred}", "tier"),
        ("{issn_l: 2769-7525, name: N, tier: 1}", "tier"),
        ("{issn_l: 2769-7525, name: N, tier: null}", "tier"),
        ("{issn_l: 2769-7525, name: N, tier: normal, issns: null}", "issns"),
        ("{issn_l: 2769-7525, name: N, tier: normal, issns: '2769-7525'}", "issns"),
        ("{issn_l: 2769-7525, name: N, tier: normal, issns: [27697525]}", "issns"),
        ("{issn_l: 2769-7525, name: N, tier: normal, weight: 1}", "weight"),
        (
            "{issn_l: 2769-7525, name: N, tier: normal, api_key: PRIVATE_MARKER}",
            "api_key",
        ),
    ],
)
def test_invalid_journal_fields_fail_without_partial_registration(
    tmp_path: Path, entry: str, field: str
) -> None:
    settings, database = journal_inputs(
        tmp_path, f"version: journals-v1\njournals: [{entry}]\n"
    )
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError) as error:
            operation(settings, database)
        assert f"journals.journals.0.{field}" in str(error.value)
        assert "PRIVATE_MARKER" not in str(error.value)
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)


@pytest.mark.parametrize(
    "content",
    [
        "journals: []\n",
        "version: journals-v2\njournals: []\n",
        "version: 1\njournals: []\n",
        "version: journals-v1\n",
        "version: journals-v1\njournals: null\n",
        "version: journals-v1\njournals: {}\n",
        "version: journals-v1\njournals: []\nsecret: PRIVATE_MARKER\n",
        "version: journals-v1\njournals: []\njournals: []\n",
        "version: journals-v1\njournals: &a []\n",
        "version: journals-v1\njournals: !custom []\n",
        "version: journals-v1\njournals: []\n---\njournals: []\n",
    ],
)
def test_invalid_journal_file_is_rejected(tmp_path: Path, content: str) -> None:
    settings, database = journal_inputs(tmp_path, content)
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError) as error:
            operation(settings, database)
        assert "PRIVATE_MARKER" not in str(error.value)


@pytest.mark.parametrize(
    "selection", ["../outside", "Journals-v1", " journals-v1", "1", "missing-version"]
)
def test_invalid_or_dangling_selector_is_rejected(
    tmp_path: Path, selection: str
) -> None:
    settings, database = journal_inputs(tmp_path)
    settings.write_text(f"journals: '{selection}'\n")
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError, match="journals"):
            operation(settings, database)
