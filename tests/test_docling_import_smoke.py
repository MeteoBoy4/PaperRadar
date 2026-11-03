"""D1: 显式安装 smoke 的公共输出,不依赖真实 SDK。"""

import importlib.metadata
import json
from types import SimpleNamespace

import pytest

from scripts.check_docling_imports import main


@pytest.fixture
def installed(monkeypatch: pytest.MonkeyPatch) -> None:
    versions = {
        "docling-slim": "2.135.0",
        "docling-core": "2.105.0",
        "docling-ibm-models": "4.0.3",
        "docling-parse": "7.22.2",
        "pypdfium2": "5.14.0",
        "torch": "2.14.1+cpu",
        "torchvision": "0.29.1+cpu",
        "transformers": "5.19.0",
        "typer": "0.27.2",
        "opencv-python-headless": "4.14.0.94",
    }
    monkeypatch.setattr(importlib.metadata, "version", versions.__getitem__)
    monkeypatch.setattr(
        importlib.metadata,
        "distributions",
        lambda: [
            SimpleNamespace(metadata={"Name": name}, version=version)
            for name, version in versions.items()
        ],
    )

    class FakeSDK:
        version = SimpleNamespace(cuda=None)
        cuda = SimpleNamespace(is_available=lambda: False)

        def __getattr__(self, _name: str) -> object:
            return object()

    original_import = importlib.import_module
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: (
            FakeSDK()
            if name.startswith(("docling", "transformers", "torch", "cv2", "pypdfium2"))
            else original_import(name)
        ),
    )


def test_missing_distribution_has_controlled_chinese_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def missing(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError("SECRET")

    monkeypatch.setattr(importlib.metadata, "version", missing)
    assert main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "dependency_missing" in captured.err
    assert "缺少" in captured.err and "docling-slim" in captured.err
    assert (
        "下一步" in captured.err
        and "uv sync --offline --locked --extra docling" in captured.err
    )
    assert "SECRET" not in captured.err and "Traceback" not in captured.err


@pytest.mark.parametrize(
    ("failure", "reason", "message"),
    [
        ("core_missing", "dependency_missing", "docling-core"),
        ("version", "dependency_version_mismatch", "版本不符"),
        ("metadata", "dependency_inventory_invalid", "安装元数据"),
        ("import", "sdk_import_failed", "导入失败"),
        ("attribute", "sdk_import_failed", "导入失败"),
        ("cpu", "cpu_required", "CPU"),
        ("ocr", "unexpected_accelerator_or_ocr", "CUDA/OCR"),
        ("inventory", "dependency_inventory_invalid", "安装元数据"),
    ],
)
def test_failed_smoke_explains_repair_without_raw_exception(
    installed: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
    reason: str,
    message: str,
) -> None:
    if failure == "core_missing":
        original = importlib.metadata.version

        def missing_core(name: str) -> str:
            if name == "docling-core":
                raise importlib.metadata.PackageNotFoundError("SECRET")
            return original(name)

        monkeypatch.setattr(importlib.metadata, "version", missing_core)
    elif failure == "version":
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "SECRET")
    elif failure == "metadata":

        def unreadable(_name: str) -> str:
            raise ValueError("SECRET")

        monkeypatch.setattr(importlib.metadata, "version", unreadable)
    elif failure == "import":

        def broken_import(_name: str) -> object:
            raise OSError("SECRET native ABI")

        monkeypatch.setattr(importlib, "import_module", broken_import)
    elif failure == "attribute":
        monkeypatch.setattr(importlib, "import_module", lambda _name: object())
    elif failure == "cpu":
        original_import = importlib.import_module
        monkeypatch.setattr(
            importlib,
            "import_module",
            lambda name: (
                SimpleNamespace(
                    version=SimpleNamespace(cuda="CUDA"),
                    cuda=SimpleNamespace(is_available=lambda: True),
                )
                if name == "torch"
                else original_import(name)
            ),
        )
    elif failure == "ocr":
        monkeypatch.setattr(
            importlib.metadata,
            "distributions",
            lambda: [SimpleNamespace(metadata={"Name": "easyocr"}, version="1")],
        )
    elif failure == "inventory":

        def broken_inventory() -> object:
            raise ValueError("SECRET")

        monkeypatch.setattr(importlib.metadata, "distributions", broken_inventory)

    assert main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert reason in captured.err and message in captured.err
    assert "下一步" in captured.err and "extraction-config.md" in captured.err
    assert "SECRET" not in captured.err and "Traceback" not in captured.err


def test_success_keeps_machine_json_and_not_assessed_boundaries(
    installed: None, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main() == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert captured.err == ""
    assert set(result) == {
        "python",
        "executable",
        "implementation",
        "platform",
        "machine",
        "libc",
        "gil_enabled",
        "imports",
        "torch_cuda",
        "inventory",
        "model_loading",
        "pdf_parsing",
    }
    assert result["torch_cuda"] is None
    assert result["model_loading"] == result["pdf_parsing"] == "not_assessed"
    assert result["imports"]["docling.backend.pypdfium2_backend"] == [
        "PyPdfiumDocumentBackend"
    ]
    assert result["imports"]["docling.backend.docling_parse_backend"] == [
        "ThreadedDoclingParseDocumentBackend"
    ]
    assert len(result["inventory"]) == 10
