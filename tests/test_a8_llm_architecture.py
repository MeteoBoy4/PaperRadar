"""协议值与内核不依赖配置/业务/持久化;描述只经公共面消费配置与输入。"""

from pathlib import Path

from tests.config_test_support import imported_modules


def test_protocol_modules_keep_business_dependencies_out() -> None:
    root = Path(__file__).parents[1] / "src/paper_radar/llm"
    prohibited = (
        "paper_radar.config",
        "paper_radar.stage_inputs",
        "paper_radar.screening_tasks",
        "paper_radar.papers",
        "paper_radar.storage",
        "sqlalchemy",
    )
    for path in root.glob("*.py"):
        if path.name in {"calls.py", "__init__.py"}:
            continue
        assert not any(
            name == prefix or name.startswith(prefix + ".")
            for name in imported_modules(path)
            for prefix in prohibited
        ), path.name
    imports = imported_modules(root / "calls.py")
    assert not any(
        name.startswith(("paper_radar.config.", "paper_radar.stage_inputs."))
        for name in imports
    )
    assert not any(
        name.startswith(
            (
                "paper_radar.screening_tasks",
                "paper_radar.papers",
                "paper_radar.storage",
                "sqlalchemy",
            )
        )
        for name in imports
    )
