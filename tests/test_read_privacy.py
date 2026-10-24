"""Read 纯层的敏感内容和导入边界。"""

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from paper_radar.reading import ReadContextError, ReadOutputError, validate_read_output
from tests.read_support import candidate, context_for


def test_reading_is_pure_and_does_not_import_upper_layers_or_io() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "paper_radar" / "reading"
    from tests.test_screening_architecture import FORBIDDEN_IMPORT_PREFIXES, _imports_in

    forbidden = (
        *FORBIDDEN_IMPORT_PREFIXES,
        "paper_radar.config",
        "paper_radar.llm",
        "paper_radar.screening_tasks",
        "paper_radar.artifacts",
        "paper_radar.backup",
        "subprocess",
        "pathlib",
        "os",
        "pi",
    )
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        imported = _imports_in(path, root.parents[1])
        assert not any(
            name == prefix or name.startswith(prefix + ".")
            for name in imported
            for prefix in forbidden
        ), path.name
        for node in ast.walk(tree):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            assert not any(
                name == prefix or name.startswith(prefix + ".")
                for name in names
                for prefix in forbidden
            ), path.name
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("open", "eval", "exec", "__import__"), (
                    path.name
                )


def test_representations_and_error_chains_do_not_expose_content(
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "SYNTHETIC_PRIVATE_FULLTEXT_29837"
    context = context_for(secret)
    raw = candidate(
        one_sentence_conclusion=secret,
        main_findings=[{"statement": "30%", "evidence": [{"evidence_id": "e1"}]}],
        degraded_content_warnings=[secret],
    )
    result = validate_read_output(raw, context)
    for value in (
        context,
        *context.source_blocks,
        *context.evidence,
        *context.replay(),
        result,
        result.analysis,
        result.warnings,
        result.diagnostics,
    ):
        assert secret not in repr(value)
        assert secret not in str(value)
    with pytest.raises(ReadOutputError) as error:
        validate_read_output(candidate(**{secret: secret}), context)
    assert secret not in str(error.value)
    assert error.value.__cause__ is error.value.__context__ is None
    with pytest.raises(ReadContextError) as context_error:
        context_for(source_blocks=[secret])
    assert secret not in str(context_error.value)
    assert context_error.value.__cause__ is context_error.value.__context__ is None
    assert capsys.readouterr() == ("", "")


def test_result_is_frozen_and_merged_view_cannot_be_changed() -> None:
    result = validate_read_output(candidate(), context_for())
    with pytest.raises(FrozenInstanceError):
        result.mode = "reduce"  # type: ignore[misc]
    assert all(
        type(value) is tuple
        for value in (result.support, result.warnings, result.diagnostics)
    )
