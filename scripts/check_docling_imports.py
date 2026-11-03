"""Explicit SDK import smoke, without model loading or PDF parsing."""

import importlib
import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path


class _SmokeFailure(Exception):
    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        self.message = message


def _smoke() -> None:
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"):
        os.environ[name] = "1"
    os.environ["DO_NOT_TRACK"] = "1"
    expected = {
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
    for name, version in expected.items():
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            raise _SmokeFailure(
                "dependency_missing", f"缺少锁定依赖 {name}。"
            ) from None
        except Exception:
            raise _SmokeFailure(
                "dependency_inventory_invalid", f"无法读取 {name} 的安装元数据。"
            ) from None
        if actual != version:
            raise _SmokeFailure(
                "dependency_version_mismatch",
                f"{name} 版本不符,需要锁定版本 {version}。",
            )
    imports = {
        "docling.document_converter": ("DocumentConverter", "PdfFormatOption"),
        "docling.backend.pypdfium2_backend": ("PyPdfiumDocumentBackend",),
        "docling.backend.docling_parse_backend": (
            "ThreadedDoclingParseDocumentBackend",
        ),
        "docling_parse.pdf_parser": ("DoclingThreadedPdfParser",),
        "pypdfium2": ("PdfDocument",),
        "docling_ibm_models.tableformer.data_management.tf_predictor": ("TFPredictor",),
        "transformers": (
            "AutoModelForImageTextToText",
            "AutoModelForObjectDetection",
            "AutoProcessor",
        ),
        "cv2": ("__version__",),
        "torchvision": ("__version__",),
    }
    try:
        for module, attributes in imports.items():
            imported = importlib.import_module(module)
            for attribute in attributes:
                getattr(imported, attribute)
        torch = importlib.import_module("torch")
        cuda_version = torch.version.cuda
        cuda_available = torch.cuda.is_available()
    except Exception:
        raise _SmokeFailure(
            "sdk_import_failed", "SDK 或 native 组件导入失败,无法确认安装兼容性。"
        ) from None
    if cuda_version is not None or cuda_available:
        raise _SmokeFailure("cpu_required", "当前 torch 不是要求的 CPU 专用运行环境。")
    try:
        inventory = sorted(
            (
                {"name": dist.metadata["Name"], "version": dist.version}
                for dist in importlib.metadata.distributions()
            ),
            key=lambda entry: entry["name"].lower(),
        )
    except Exception:
        raise _SmokeFailure(
            "dependency_inventory_invalid", "无法读取完整安装元数据库存。"
        ) from None
    if any(
        entry["name"].lower().startswith(("nvidia-", "easyocr", "rapidocr"))
        for entry in inventory
    ):
        raise _SmokeFailure(
            "unexpected_accelerator_or_ocr", "发现不允许的 CUDA/OCR 依赖。"
        )
    print(
        json.dumps(
            {
                "python": sys.version,
                "executable": str(Path(sys.executable).absolute()),
                "implementation": platform.python_implementation(),
                "platform": platform.platform(),
                "machine": platform.machine(),
                "libc": platform.libc_ver(),
                "gil_enabled": sysconfig_gil_enabled(),
                "imports": imports,
                "torch_cuda": torch.version.cuda,
                "inventory": inventory,
                "model_loading": "not_assessed",
                "pdf_parsing": "not_assessed",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def sysconfig_gil_enabled() -> bool:
    import sysconfig

    return not bool(sysconfig.get_config_var("Py_GIL_DISABLED"))


def main() -> int:
    try:
        _smoke()
    except _SmokeFailure as exc:
        print(
            f"安装检查失败 [{exc.reason}]：{exc.message}"
            "下一步：在所选解释器与独立环境中执行 "
            "uv sync --offline --locked --extra docling；"
            "缓存不足时取得联网授权后按产品锁补齐。"
            "若仍失败,按 docs/contracts/extraction-config.md 的支持范围"
            "修复或重建环境后重试;不要替换版本或 CPU 索引。",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
