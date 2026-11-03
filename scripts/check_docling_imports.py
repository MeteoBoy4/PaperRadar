"""Explicit SDK import smoke, without model loading or PDF parsing."""

import importlib
import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path


def main() -> None:
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
        actual = importlib.metadata.version(name)
        if actual != version:
            raise RuntimeError(f"{name}: expected {version}, found {actual}")
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
    for module, attributes in imports.items():
        imported = importlib.import_module(module)
        for attribute in attributes:
            getattr(imported, attribute)
    torch = importlib.import_module("torch")
    if torch.version.cuda is not None or torch.cuda.is_available():
        raise RuntimeError("CPU-only torch required")
    inventory = sorted(
        (
            {"name": dist.metadata["Name"], "version": dist.version}
            for dist in importlib.metadata.distributions()
        ),
        key=lambda entry: entry["name"].lower(),
    )
    if any(
        entry["name"].lower().startswith(("nvidia-", "easyocr", "rapidocr"))
        for entry in inventory
    ):
        raise RuntimeError("unexpected CUDA/OCR distribution")
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


if __name__ == "__main__":
    main()
