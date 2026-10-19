"""阶段输入只通过下层公共面消费依赖。"""

from pathlib import Path

from tests.config_test_support import imported_modules


def test_stage_inputs_only_depend_on_public_domain_boundaries() -> None:
    source = Path(__file__).resolve().parents[1] / "src/paper_radar"
    allowed = {"paper_radar.config", "paper_radar.screening"}
    for module in (source / "stage_inputs").glob("*.py"):
        for imported in imported_modules(module):
            if imported.startswith("paper_radar."):
                assert imported in allowed or imported.startswith(
                    "paper_radar.stage_inputs."
                )
            else:
                assert imported.split(".")[0] in {
                    "__future__",
                    "hashlib",
                    "json",
                    "re",
                    "collections",
                    "types",
                    "dataclasses",
                    "enum",
                    "typing",
                    "pydantic",
                }
    for layer in ("config", "screening"):
        for module in (source / layer).glob("*.py"):
            assert not any(
                name.startswith("paper_radar.stage_inputs")
                for name in imported_modules(module)
            )
