"""B-E16 独立 D1:冷帮助、受控错误与只读日志边界。"""

from pathlib import Path

from tests.config_test_support import run_cli


def test_replay_help_is_cold_and_complete(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "replay", "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    for fragment in (
        "参数",
        "副作用",
        "自动配额",
        "输出去向",
        "常见失败",
        "示例",
        "130",
        "禁网",
        "--original-database",
    ):
        assert fragment in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_readonly_replay_entry_explicitly_injects_selected_views_file_sink() -> None:
    """入口接线守卫;与实际子进程无日志/无写库断言合用。"""
    import ast

    from paper_radar.replay import worker

    tree = ast.parse(Path(worker.__file__).read_text())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    sinks = [
        node
        for node in calls
        if isinstance(node.func, ast.Name) and node.func.id == "FileSink"
    ]
    assert len(sinks) == 1 and ast.unparse(sinks[0]) == "FileSink(output)"
    for constructor in ("Reports", "ReadTasks", "Exposures"):
        selected = [
            node
            for node in calls
            if isinstance(node.func, ast.Name) and node.func.id == constructor
        ]
        assert len(selected) == 1
        assert any(
            keyword.arg == "sink" and ast.unparse(keyword.value) == "sink"
            for keyword in selected[0].keywords
        )
    assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Tuple)
    ]
    assert any(
        [ast.unparse(part) for part in node.value.elts]
        == ["root / 'contents'", "root / 'views'"]
        for node in assignments
        if isinstance(node.value, ast.Tuple)
    )
