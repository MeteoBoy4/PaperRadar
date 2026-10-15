"""#27 发现服务不能侵入纯比较/投影。摘要与 help 保持无存储依赖。"""

from pathlib import Path

from tests.config_test_support import imported_modules

ROOT = Path(__file__).resolve().parents[1]


def test_reference_rules_do_not_enter_projection_or_diff_core() -> None:
    for module in (
        "compile",
        "projections",
        "diff",
        "snapshot_summary",
        "material_names",
    ):
        imports = imported_modules(ROOT / f"src/paper_radar/config/{module}.py")
        assert not any(
            name.startswith(
                ("paper_radar.storage", "paper_radar.config.snapshot_queries")
            )
            or name in ("sqlite3", "sqlalchemy", "typer", "alembic", "yaml")
            for name in imports
        )
