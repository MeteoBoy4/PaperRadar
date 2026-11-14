"""B 持久事实的唯一备份验证聚合;不检查当前执行适用性。"""

from pathlib import Path

from paper_radar.config.owner_waiver import OwnerWaiverError, owner_waiver
from paper_radar.experiment.acceptance import AcceptanceError, Acceptances
from paper_radar.experiment.candidates import validate_candidate_snapshots
from paper_radar.experiment.egress import EgressError, egress_authorization
from paper_radar.experiment.extraction import ExtractionError, Extractions
from paper_radar.experiment.layout import LayoutError, LayoutReviews
from paper_radar.experiment.pdf import PdfError, PdfSamples
from paper_radar.experiment.selections import SelectionError, Selections
from paper_radar.storage.artifact_contract import ArtifactError


class ExperimentValidationError(ValueError):
    """聚合仅向备份暴露统一的登记损坏,下游扩展不改备份异常清单。"""

    reason = "registration_invalid"


def validate_all(database: Path, data_root: Path) -> None:
    """允许恢复副本的新路径;所有 B 事实扩展均在这里接入。"""
    try:
        validate_candidate_snapshots(database, data_root)
        Selections(database, data_root).validate_all()
        Acceptances(database, data_root).validate_all()
        PdfSamples(database, data_root).validate_all()
        Extractions(database, data_root).validate_all()
        LayoutReviews(database, data_root).validate_all()
        owner_waiver(database)
        egress_authorization(database)
    except (
        ArtifactError,
        SelectionError,
        AcceptanceError,
        PdfError,
        ExtractionError,
        LayoutError,
        OwnerWaiverError,
        EgressError,
    ):
        raise ExperimentValidationError("registration_invalid") from None
