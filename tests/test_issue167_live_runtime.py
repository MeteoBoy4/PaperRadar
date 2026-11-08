"""Independent D1: bound ordinary-controller imports, no actual application I/O."""

import hashlib
import importlib.abc
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import issue167_live_runtime as runtime


def fixture_binding(tmp_path: Path) -> dict[str, Any]:
    root = tmp_path / "package"
    root.mkdir()
    source = root / "example.py"
    source.write_text("answer = 42\n")
    python = Path(sys.executable).resolve()
    return {
        "kind": "ordinary_worker_bound_application_runtime",
        "uid": os.getuid(),
        "python_version": list(sys.version_info[:3]),
        "python": str(python),
        "source_parent": str(tmp_path),
        "site_packages": str(tmp_path),
        "roots": [str(root)],
        "files": {
            str(source): hashlib.sha256(source.read_bytes()).hexdigest(),
            str(python): hashlib.sha256(python.read_bytes()).hexdigest(),
        },
        "links": {},
        "bytecode_policy": "compile_bound_source_no_pyc",
        "logical_database_io": "none",
    }


@pytest.mark.parametrize(
    "change", ["none", "missing", "extra", "wrong_key", "duplicate"]
)
def test_embedded_runtime_binding_keeps_exact_context_and_all_members(
    tmp_path: Path, change: str
) -> None:
    b = fixture_binding(tmp_path)
    context = {
        "kind": "live_six_public_bindings",
        "supply": {},
        "synthetic_manifest_sha256": "a" * 64,
        "nsswitch_sha256": "b" * 64,
        "hostname_contains_dot": False,
        "application_runtime": b,
        "auth_input_declaration": {},
        "observation_choice": "S",
    }
    key = "application_runtime"
    if change == "missing":
        context.pop(key)
    elif change == "extra":
        context["raw"] = "forbidden"
    elif change == "wrong_key":
        key = "supply"
    raw = json.dumps(context)
    if change == "duplicate":
        raw = raw.replace(
            '"application_runtime":',
            '"application_runtime": {}, "application_runtime":',
            1,
        )
    path = tmp_path / "context.json"
    path.write_text(raw)
    if change == "none":
        assert runtime.load_binding(path, key=key) == b
    else:
        with pytest.raises(runtime.RuntimeRejected, match="runtime_binding_unknown"):
            runtime.load_binding(path, key=key)


@pytest.mark.parametrize("change", ["extra", "bool_uid", "relative", "hash"])
def test_runtime_binding_rejects_uncontrolled_shape(
    tmp_path: Path, change: str
) -> None:
    b = fixture_binding(tmp_path)
    if change == "extra":
        b["raw"] = "uncontrolled"
    elif change == "bool_uid":
        b["uid"] = True
    elif change == "relative":
        b["source_parent"] = "relative"
    else:
        b["files"][b["python"]] = "not-a-digest"
    p = tmp_path / "binding.json"
    p.write_text(json.dumps(b))
    with pytest.raises(runtime.RuntimeRejected, match="runtime_binding_unknown"):
        runtime.load_binding(p)


@pytest.mark.parametrize("change", ["source", "extra_member"])
def test_changed_or_added_application_member_blocks(
    tmp_path: Path, change: str
) -> None:
    b = fixture_binding(tmp_path)
    if change == "source":
        (tmp_path / "package/example.py").write_text("answer = 43\n")
    else:
        (tmp_path / "package/unapproved.py").write_text("answer = 43\n")
    with pytest.raises(
        runtime.RuntimeRejected, match=r"runtime_member_changed|runtime_members_changed"
    ):
        runtime.verify_binding(b)


def test_root_is_not_allowed_to_import_bound_application(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    b = fixture_binding(tmp_path)
    monkeypatch.setattr("scripts.issue167_live_runtime.os.getuid", lambda: 0)
    with pytest.raises(runtime.RuntimeRejected, match="ordinary_worker_required"):
        runtime.verify_binding(b)


def test_source_loader_compiles_bound_source_and_never_uses_pyc(tmp_path: Path) -> None:
    p = tmp_path / "example.py"
    p.write_text("answer = 42\n")
    loader = runtime.BoundSourceLoader(
        "example", str(p), hashlib.sha256(p.read_bytes()).hexdigest()
    )
    namespace: dict[str, Any] = {}
    exec(loader.get_code("example"), namespace)
    assert namespace["answer"] == 42
    p.write_text("answer = 43\n")
    with pytest.raises(runtime.RuntimeRejected, match="runtime_import_changed"):
        loader.get_code("example")


def test_unbound_source_cannot_be_imported_via_site_directory(tmp_path: Path) -> None:
    p = tmp_path / "unapproved.py"
    p.write_text("answer = 43\n")
    with pytest.raises(runtime.RuntimeRejected, match="runtime_import_unbound"):
        runtime.BoundFinder({}).find_spec("unapproved", [str(tmp_path)])


def test_missing_module_cannot_fall_through_to_later_unbound_finder() -> None:
    class LaterFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, *args: Any, **kwargs: Any) -> Any:
            pytest.fail("unbound_later_finder_must_not_run")

    finder = runtime.BoundFinder({})
    later = LaterFinder()
    sys.meta_path[:0] = [finder, later]
    try:
        with pytest.raises(ModuleNotFoundError, match="runtime_import_unbound"):
            __import__("issue167_unbound_synthetic_loader")
    finally:
        sys.meta_path.remove(later)
        sys.meta_path.remove(finder)


def test_single_file_root_link_is_rejected_before_external_read(tmp_path: Path) -> None:
    external = tmp_path / "outside"
    external.write_text("synthetic-unread-body")
    alias = tmp_path / "typing_extensions.py"
    alias.symlink_to(external)
    with pytest.raises(runtime.RuntimeRejected, match="runtime_path_unknown"):
        runtime._members(alias)
