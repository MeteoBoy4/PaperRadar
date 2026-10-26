"""核对已冻结的 A10 需求处置与具体文件指针, 不生成或补全覆盖映射。"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any


def validate_coverage(
    root: Path,
    value: dict[str, Any],
    *,
    fixed: set[str],
    test_modules: set[str],
    capabilities: set[str],
) -> bool:
    """693 项原库存、来源原文及每种处置都须闭合; 未决项阻断通过。"""
    if (
        type(value.get("format_version")) is not int
        or value.get("format_version") != 1
        or value.get("artifact_kind") != "a10_requirements_coverage"
        or value.get("review_state") != "reviewed"
        or value.get("open_items") != []
        or value.get("owner_conflicts") != []
        or type(value.get("original_inventory_count")) is not int
        or value.get("original_inventory_count") != 693
    ):
        return False
    sources = value.get("source_documents")
    requirements = value.get("requirements")
    original_ids = value.get("original_inventory_ids")
    if (
        not isinstance(sources, list)
        or len(sources) != 37
        or type(value.get("source_document_count")) is not int
        or value["source_document_count"] != len(sources)
        or not isinstance(requirements, list)
        or len(requirements) != 693
        or not isinstance(original_ids, list)
        or len(original_ids) != 693
        or any(not isinstance(item, str) for item in original_ids)
        or len(set(original_ids)) != 693
    ):
        return False
    documents: dict[str, dict[str, Any]] = {}
    for source in sources:
        if (
            not isinstance(source, dict)
            or not isinstance(source.get("source_id"), str)
            or source["source_id"] in documents
            or type(source.get("issue")) is not int
            or source["issue"] not in range(100, 109)
            or not isinstance(source.get("url"), str)
            or not source["url"].startswith(
                f"https://github.com/MeteoBoy4/PaperRadar/issues/{source['issue']}"
            )
            or not isinstance(source.get("original_text"), str)
            or hashlib.sha256(source["original_text"].encode()).hexdigest()
            != source.get("sha256")
        ):
            return False
        documents[source["source_id"]] = source

    symbols: dict[str, set[str]] = {}
    test_symbols: dict[str, set[str]] = {}

    def pointer_valid(pointer: object, *, test: bool = False) -> bool:
        if not isinstance(pointer, str):
            return False
        parts = pointer.split("::")
        path = parts[0]
        if path not in fixed or (
            test and (path not in test_modules or len(parts) != 2)
        ):
            return False
        if len(parts) == 1:
            return not test
        if len(parts) != 2 or not path.endswith(".py"):
            return False
        if path not in symbols:
            try:
                tree = ast.parse((root / path).read_bytes())
            except (OSError, SyntaxError, ValueError):
                return False
            found: set[str] = set()
            tests_found: set[str] = set()

            def visit(nodes: list[ast.stmt], prefix: str = "") -> None:
                for node in nodes:
                    if isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    ):
                        found.add(prefix + node.name)
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            fixture = any(
                                (
                                    isinstance(decorator, ast.Attribute)
                                    and decorator.attr == "fixture"
                                )
                                or (
                                    isinstance(decorator, ast.Name)
                                    and decorator.id == "fixture"
                                )
                                or (
                                    isinstance(decorator, ast.Call)
                                    and isinstance(decorator.func, ast.Attribute)
                                    and decorator.func.attr == "fixture"
                                )
                                for decorator in node.decorator_list
                            )
                            if (
                                node.name.startswith("test_")
                                and (
                                    not prefix
                                    or all(
                                        part.startswith("Test")
                                        for part in prefix.rstrip(".").split(".")
                                    )
                                )
                                and not fixture
                            ):
                                tests_found.add(prefix + node.name)
                        if isinstance(node, ast.ClassDef):
                            visit(node.body, prefix + node.name + ".")
                    elif isinstance(node, ast.Assign):
                        found.update(
                            prefix + target.id
                            for target in node.targets
                            if isinstance(target, ast.Name)
                        )
                    elif isinstance(node, ast.AnnAssign) and isinstance(
                        node.target, ast.Name
                    ):
                        found.add(prefix + node.target.id)

            visit(tree.body)
            symbols[path] = found
            test_symbols[path] = tests_found
        return parts[1] in (test_symbols[path] if test else symbols[path])

    def pointers_valid(raw: object, *, test: bool = False) -> bool:
        return (
            isinstance(raw, list)
            and bool(raw)
            and all(pointer_valid(pointer, test=test) for pointer in raw)
        )

    def behavior_valid(row: dict[str, Any]) -> bool:
        return pointers_valid(
            row.get("specific_test_pointers"), test=True
        ) and pointers_valid(row.get("scope_materials"))

    seen: set[str] = set()
    not_assessed = value.get("not_assessed")
    if not isinstance(not_assessed, dict) or not not_assessed:
        return False
    for row in requirements:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("requirement_id"), str)
            or row["requirement_id"] in seen
            or row["requirement_id"] not in original_ids
            or not isinstance(row.get("source_id"), str)
            or row.get("coverage_state") != "reviewed"
            or not isinstance(row.get("status"), str)
            or row.get("status")
            not in {"covered", "superseded", "not_assessed", "operational"}
        ):
            return False
        seen.add(row["requirement_id"])
        source = documents.get(row.get("source_id", ""))
        if (
            source is None
            or row.get("source_url") != source["url"]
            or row.get("issue") != source["issue"]
            or not isinstance(row.get("original_text"), str)
            or not row["original_text"]
            or row["original_text"] not in source["original_text"]
        ):
            return False
        if row["status"] == "covered":
            if not behavior_valid(row) or not pointers_valid(
                row.get("public_behavior_pointers")
            ):
                return False
        elif row["status"] == "superseded":
            decisions = row.get("supersession")
            if not isinstance(decisions, list) or not decisions:
                return False
            for decision in decisions:
                if (
                    not isinstance(decision, dict)
                    or not isinstance(decision.get("decision_url"), str)
                    or decision.get("decision_url")
                    not in {doc["url"] for doc in sources}
                    or not decision.get("reason")
                    or not isinstance(decision.get("decision_requirement_ids"), list)
                    or not decision["decision_requirement_ids"]
                    or any(
                        item not in original_ids
                        for item in decision["decision_requirement_ids"]
                    )
                ):
                    return False
        elif row["status"] == "not_assessed":
            responsibility = row.get("not_assessed_responsibility")
            refs = row.get("not_assessed_refs")
            if (
                not isinstance(responsibility, (str, dict))
                or not responsibility
                or not isinstance(refs, list)
                or not refs
                or any(
                    not isinstance(ref, str) or ref not in not_assessed for ref in refs
                )
            ):
                return False
        elif not row.get("mapping_note"):
            return False
    coverage = value.get("capabilities")
    if not isinstance(coverage, dict) or set(coverage) != capabilities:
        return False
    for material in coverage.values():
        if (
            not isinstance(material, dict)
            or not pointers_valid(material.get("cases"), test=True)
            or not pointers_valid(material.get("materials"))
        ):
            return False
    for key in ("behavior_catalog", "extra_safety_assertions"):
        rows = value.get(key)
        if not isinstance(rows, list) or not rows:
            return False
        if any(not isinstance(row, dict) or not behavior_valid(row) for row in rows):
            return False
    return seen == set(original_ids)
