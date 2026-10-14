"""#23 的单快照重建与比较必须保持纯领域计算。"""

from pathlib import Path

from tests.config_test_support import imported_modules


def test_projection_and_comparison_do_not_depend_on_io_or_application_services() -> (
    None
):
    folder = Path(__file__).resolve().parents[1] / "src/paper_radar/config"
    forbidden = (
        "yaml",
        "sqlalchemy",
        "sqlite3",
        "alembic",
        "typer",
        "paper_radar.storage",
        "paper_radar.config.service",
        "paper_radar.config.cli",
        "paper_radar.config.yaml_loader",
    )
    for module in ("projections.py", "diff.py"):
        assert not any(
            name == prefix or name.startswith(prefix + ".")
            for name in imported_modules(folder / module)
            for prefix in forbidden
        )
