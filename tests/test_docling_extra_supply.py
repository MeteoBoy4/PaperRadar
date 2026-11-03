"""Independent #152 supply coverage, without importing optional SDKs."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CPU_MARKER = (
    "sys_platform == 'linux' and platform_machine == 'x86_64' "
    "and implementation_name == 'cpython'"
)


def test_cpu_extra_declares_exact_components_and_only_required_slim_features() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert project["project"]["requires-python"] == ">=3.12,<3.15"
    requirements = project["project"].get("optional-dependencies", {}).get("docling")
    assert requirements is not None, "产品必须提供 docling optional extra"
    assert {entry.split(" ; ")[0] for entry in requirements} == {
        "docling-slim[convert-core,format-pdf,models-local]==2.135.0",
        "docling-core==2.105.0",
        "docling-ibm-models[opencv-python-headless]==4.0.3",
        "docling-parse==7.22.2",
        "pypdfium2==5.14.0",
        "torch==2.14.1+cpu",
        "torchvision==0.29.1+cpu",
        "transformers==5.19.0",
        "typer==0.27.2",
    }
    assert all(entry.split(" ; ")[1] == CPU_MARKER for entry in requirements)


def test_cpu_index_is_explicit_and_three_minor_wheels_are_required() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    uv = project["tool"].get("uv", {})
    assert "environments" not in uv
    assert "conflicts" not in uv
    assert uv.get("required-environments") == [
        f"{CPU_MARKER} and python_version == '{version}'"
        for version in ("3.12", "3.13", "3.14")
    ]
    assert uv.get("index") == [
        {
            "name": "pytorch-cpu",
            "url": "https://download.pytorch.org/whl/cpu",
            "explicit": True,
        }
    ]
    for name in ("torch", "torchvision"):
        assert uv["sources"][name] == {"index": "pytorch-cpu", "marker": CPU_MARKER}


def test_single_lock_contains_cpu_supply_without_ocr_cuda_or_full_docling() -> None:
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    packages = {package["name"]: package for package in lock["package"]}
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
    assert {name: packages[name]["version"] for name in expected} == expected
    for name in ("torch", "torchvision"):
        assert packages[name]["source"] == {
            "registry": "https://download.pytorch.org/whl/cpu"
        }
        assert all(
            wheel["url"].startswith(
                (
                    "https://download.pytorch.org/whl/cpu/",
                    "https://download-r2.pytorch.org/whl/cpu/",
                )
            )
            and "manylinux_2_28_x86_64" in wheel["url"]
            for wheel in packages[name]["wheels"]
        )
        assert {
            minor
            for minor in ("cp312", "cp313", "cp314")
            if any(f"-{minor}-{minor}-" in w["url"] for w in packages[name]["wheels"])
        } == {"cp312", "cp313", "cp314"}
    assert "docling" not in packages
    assert "opencv-python" not in packages
    assert not any(
        name.startswith(("nvidia-", "cuda-", "easyocr", "rapidocr", "onnxruntime"))
        for name in packages
    )
    slim = packages["docling-slim"]["optional-dependencies"]
    assert set(slim) == {"convert-core", "format-pdf", "models-local"}
