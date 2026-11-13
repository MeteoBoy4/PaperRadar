"""显式实验根与 B 工作流公共组合边界。"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from paper_radar.experiment.root import ExperimentError, ExperimentRoot

__all__ = ["ExperimentError", "ExperimentRoot"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from paper_radar.experiment import root

        return getattr(root, name)
    raise AttributeError(name)
