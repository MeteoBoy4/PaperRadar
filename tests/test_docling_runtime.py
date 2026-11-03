"""D1: Body 共用的按需 Docling 探测公共边界。"""

import pytest

from paper_radar.docling_runtime import probe_docling_runtime
from tests.docling_runtime_support import MODULES, V2_VERSIONS, environment


def test_installed_packages_cannot_enable_unselected_extraction() -> None:
    result = probe_docling_runtime(None, None, requested=True, enabled=False)
    assert not result.passed
    assert result.reason == "extraction_unselected"
    assert result.missing == ()
    assert result.platform is None
    assert result.dependencies == ()


def test_missing_extra_names_components_without_importing_sdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib.metadata
    import importlib.util
    import os
    import platform
    import sysconfig

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(os, "confstr", lambda _name: "glibc 2.28")
    monkeypatch.setattr(sysconfig, "get_config_var", lambda _name: 0)
    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: None)

    def absent(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", absent)
    result = probe_docling_runtime(
        "docling-2.135.0-cpu-v2", "pypdfium2", requested=True, enabled=True
    )
    assert not result.passed
    assert result.reason == "dependency_missing"
    assert result.platform is not None
    assert result.platform.reason == "platform_supported"
    assert set(result.missing) == {
        "docling-slim",
        "docling-core",
        "docling-ibm-models",
        "torch",
        "torchvision",
        "transformers",
        "pypdfium2",
        "typer",
        "opencv-python-headless",
    }
    assert result.mismatched == ()
    assert "docling-parse" not in {item.distribution for item in result.dependencies}


@pytest.mark.parametrize("backend", ["pypdfium2", "threaded_docling_parse"])
def test_only_explicit_selected_backend_is_required(
    monkeypatch: pytest.MonkeyPatch,
    backend: str,
) -> None:
    from typing import cast

    from paper_radar.docling_toolchain import PDFBackend

    environment(monkeypatch)
    result = probe_docling_runtime(
        "docling-2.135.0-cpu-v2",
        cast(PDFBackend, backend),
        requested=True,
        enabled=True,
    )
    assert result.passed
    assert result.pdf_backend == backend
    assert result.missing == result.mismatched == ()
    assert ("docling-parse" in {item.distribution for item in result.dependencies}) == (
        backend == "threaded_docling_parse"
    )
    assert result.next_step == "consumer_runtime_checks"


@pytest.mark.parametrize(
    ("distribution", "module", "change", "reason"),
    [
        ("docling-slim", "docling", "absent", "dependency_missing"),
        ("docling-core", "docling_core", "absent", "dependency_missing"),
        ("opencv-python-headless", "cv2", "absent", "dependency_missing"),
        ("docling-parse", "docling_parse", "absent", "dependency_missing"),
        ("docling-core", "docling_core", "module_only", "dependency_inconsistent"),
        ("docling-core", "docling_core", "metadata_only", "dependency_inconsistent"),
        ("docling-core", "docling_core", "version", "dependency_version_mismatch"),
        ("typer", "typer", "version", "dependency_version_mismatch"),
        ("torch", "torch", "version", "dependency_version_mismatch"),
    ],
)
def test_current_inventory_failures_are_structured_and_never_fallback(
    monkeypatch: pytest.MonkeyPatch,
    distribution: str,
    module: str,
    change: str,
    reason: str,
) -> None:
    versions, modules = dict(V2_VERSIONS), set(MODULES)
    if change in {"absent", "module_only"}:
        del versions[distribution]
    if change in {"absent", "metadata_only"}:
        modules.remove(module)
    if change == "version":
        versions[distribution] = "99.0.0"
    environment(monkeypatch, versions=versions, modules=modules)
    result = probe_docling_runtime(
        "docling-2.135.0-cpu-v2", "threaded_docling_parse", requested=True, enabled=True
    )
    assert not result.passed
    assert result.reason == reason
    assert result.pdf_backend == "threaded_docling_parse"
    assert result.toolchain == "docling-2.135.0-cpu-v2"
    fact = next(
        item for item in result.dependencies if item.distribution == distribution
    )
    assert fact.reason == reason
    assert (distribution in result.missing) == (change == "absent")
    assert (distribution in result.mismatched) == (change != "absent")


def test_old_toolchain_is_not_reinterpreted_by_new_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment(monkeypatch)
    result = probe_docling_runtime(
        "docling-2.135.0-cpu-v1", "pypdfium2", requested=True, enabled=True
    )
    assert result.reason == "dependency_version_mismatch"
    assert result.mismatched == ("docling-core",)
    core = next(
        item for item in result.dependencies if item.distribution == "docling-core"
    )
    assert core.expected_version == "2.101.1"
    assert core.installed_version == "2.105.0"
    assert "typer" not in {item.distribution for item in result.dependencies}


def test_unconsumed_parse_inventory_cannot_change_pypdfium2_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    versions, modules = dict(V2_VERSIONS), set(MODULES)
    del versions["docling-parse"]
    modules.remove("docling_parse")
    environment(monkeypatch, versions=versions, modules=modules)
    result = probe_docling_runtime(
        "docling-2.135.0-cpu-v2", "pypdfium2", requested=True, enabled=True
    )
    assert result.passed
    versions["docling-parse"] = "unrelated-version"
    modules.add("docling_parse")
    assert (
        probe_docling_runtime(
            "docling-2.135.0-cpu-v2", "pypdfium2", requested=True, enabled=True
        )
        == result
    )


@pytest.mark.parametrize(
    ("fact", "value", "reason"),
    [
        ("os", "Darwin", "platform_unsupported"),
        ("os", "", "platform_unknown"),
        ("arch", "aarch64", "platform_unsupported"),
        ("arch", "", "platform_unknown"),
        ("libc", "musl 1.2", "platform_unsupported"),
        ("libc", "glibc 2.27", "platform_unsupported"),
        ("libc", None, "platform_unknown"),
        ("libc", "glibc unknown", "platform_unknown"),
        ("abi", 1, "platform_unsupported"),
        ("abi", None, "platform_unknown"),
        ("python", (3, 11, 9), "platform_unsupported"),
        ("python", (3, 15, 0), "platform_unsupported"),
        ("implementation", "pypy", "platform_unsupported"),
    ],
)
def test_unsupported_or_unknown_platform_never_passes_even_with_all_packages(
    monkeypatch: pytest.MonkeyPatch,
    fact: str,
    value: object,
    reason: str,
) -> None:
    import os
    import platform
    import sys
    import sysconfig
    from types import SimpleNamespace

    environment(monkeypatch)
    if fact == "os":
        monkeypatch.setattr(platform, "system", lambda: value)
    elif fact == "arch":
        monkeypatch.setattr(platform, "machine", lambda: value)
    elif fact == "libc":
        monkeypatch.setattr(os, "confstr", lambda _name: value)
    elif fact == "abi":
        monkeypatch.setattr(sysconfig, "get_config_var", lambda _name: value)
    elif fact == "python":
        monkeypatch.setattr(sys, "version_info", value)
    elif fact == "implementation":
        monkeypatch.setattr(sys, "implementation", SimpleNamespace(name=value))
    result = probe_docling_runtime(
        "docling-2.135.0-cpu-v2", "pypdfium2", requested=True, enabled=True
    )
    assert not result.passed
    assert result.reason == reason
    assert result.platform is not None and result.platform.reason == reason
    assert result.missing == result.mismatched == ()


@pytest.mark.parametrize("minor", [12, 13, 14])
def test_supported_cpython_minors_and_glibc_boundary(
    monkeypatch: pytest.MonkeyPatch,
    minor: int,
) -> None:
    import sys

    environment(monkeypatch)
    monkeypatch.setattr(sys, "version_info", (3, minor, 0))
    result = probe_docling_runtime(
        "docling-2.135.0-cpu-v2", "pypdfium2", requested=True, enabled=True
    )
    assert result.passed
    assert result.platform is not None
    assert result.platform.libc_version == (2, 28)


def test_unrequested_probe_never_reads_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib.metadata
    import importlib.util
    import platform

    def forbidden(*_args: object) -> None:
        pytest.fail("没有明确请求，不得探测现场")

    monkeypatch.setattr(importlib.metadata, "version", forbidden)
    monkeypatch.setattr(importlib.util, "find_spec", forbidden)
    monkeypatch.setattr(platform, "system", forbidden)
    result = probe_docling_runtime(
        "docling-2.135.0-cpu-v2", "pypdfium2", requested=False, enabled=True
    )
    assert result.reason == "runtime_not_requested"
    assert result.platform is None and result.dependencies == ()


def test_nonposix_interpreter_without_abiflags_is_controlled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import platform
    import sys

    environment(monkeypatch)
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.delattr(sys, "abiflags")
    result = probe_docling_runtime(
        "docling-2.135.0-cpu-v2", "pypdfium2", requested=True, enabled=True
    )
    assert result.reason == "platform_unsupported"


def test_unreadable_abi_fact_is_unknown_and_blocks_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sysconfig

    environment(monkeypatch)

    def unreadable(_name: str) -> object:
        raise OSError("SECRET")

    monkeypatch.setattr(sysconfig, "get_config_var", unreadable)
    result = probe_docling_runtime(
        "docling-2.135.0-cpu-v2", "pypdfium2", requested=True, enabled=True
    )
    assert result.reason == "platform_unknown"
    assert not result.passed
