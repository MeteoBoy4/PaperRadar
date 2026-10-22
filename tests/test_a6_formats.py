"""验收消费的 Feed 格式权威与实际生产算法一致。"""


def test_feed_fingerprint_has_versioned_production_rule() -> None:
    from paper_radar.papers.feed import FEED_ITEM_FINGERPRINT_VERSION, item_fingerprint

    assert type(FEED_ITEM_FINGERPRINT_VERSION) is int
    assert FEED_ITEM_FINGERPRINT_VERSION == 1
    assert item_fingerprint(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_all_new_pure_rules_keep_storage_and_sqlalchemy_out() -> None:
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src/paper_radar/papers"
    for name in (
        "doi",
        "text",
        "text_rules",
        "rules",
        "relations",
        "feed",
        "models",
        "errors",
    ):
        tree = ast.parse((root / f"{name}.py").read_bytes())
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any(
            value.startswith(("sqlalchemy", "paper_radar.storage")) for value in imports
        ), name
