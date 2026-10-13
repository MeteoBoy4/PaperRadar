"""期刊配置使用已确认的公共服务与真实 SQLite 边界。"""

from pathlib import Path

from tests.config_test_support import value_inputs

JOURNALS = """version: journals-v1
journals:
  - issn_l: 2169897x
    issns: [2169-8996, 2169-897x]
    name: 同名期刊
    tier: preferred
  - issn_l: 0035-9009
    issns: [1477870x]
    name: 同名期刊
    tier: low
  - issn_l: 2769-7525
    name: 电子期刊
    tier: normal
  - issn_l: 1006-9895
    issns: []
    name: 中文期刊
    tier: normal
"""


def journal_inputs(root: Path, content: str = JOURNALS) -> tuple[Path, Path]:
    settings, database = value_inputs(root)
    folder = settings.parent / "journals"
    folder.mkdir()
    (folder / "journals-v1.yaml").write_text(content, encoding="utf-8")
    settings.write_text(
        settings.read_text(encoding="utf-8") + "journals: journals-v1\n",
        encoding="utf-8",
    )
    return settings, database
