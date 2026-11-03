"""D1: 独立人工库存与受控 stdlib 边界,不从生产清单推导期望。"""

import importlib.metadata
import importlib.util
import os
import platform
import sysconfig

import pytest

V2_VERSIONS = {
    "docling-slim": "2.135.0",
    "docling-core": "2.105.0",
    "docling-ibm-models": "4.0.3",
    "torch": "2.14.1+cpu",
    "torchvision": "0.29.1+cpu",
    "transformers": "5.19.0",
    "pypdfium2": "5.14.0",
    "docling-parse": "7.22.2",
    "typer": "0.27.2",
    "opencv-python-headless": "4.13.0.92",
}
MODULES = {
    "docling",
    "docling_core",
    "docling_ibm_models",
    "torch",
    "torchvision",
    "transformers",
    "pypdfium2",
    "docling_parse",
    "typer",
    "cv2",
}


def environment(
    monkeypatch: pytest.MonkeyPatch,
    *,
    versions: dict[str, str] | None = None,
    modules: set[str] | None = None,
) -> None:
    installed = V2_VERSIONS if versions is None else versions
    available = MODULES if modules is None else modules
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(os, "confstr", lambda _name: "glibc 2.28")
    monkeypatch.setattr(sysconfig, "get_config_var", lambda _name: 0)

    def version(name: str) -> str:
        if name not in installed:
            raise importlib.metadata.PackageNotFoundError(name)
        return installed[name]

    def find_spec(name: str) -> object | None:
        assert "." not in name, "不能探测带点模块而隐式导入 SDK 父包"
        return object() if name in available else None

    monkeypatch.setattr(importlib.metadata, "version", version)
    monkeypatch.setattr(importlib.util, "find_spec", find_spec)
