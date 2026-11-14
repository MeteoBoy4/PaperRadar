"""所有者授权 Agent 代录正文选择;不调用提取器或模型。"""

from collections.abc import Callable
from datetime import UTC, datetime

from paper_radar.body import BodyService
from paper_radar.body.models import BodyError
from paper_radar.body.selection import BodySelection, BodySelections, require_visibility
from paper_radar.experiment.pdf import PdfError, PdfSamples
from paper_radar.experiment.root import ExperimentRoot
from paper_radar.fulltext.models import FulltextError
from paper_radar.reading.context import ExtractionIdentity
from paper_radar.runtime_logging import FileSink, RuntimeLog


class BodySelectionError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(
            f"{reason}：正文选择停止；请核对当前冻结样本、PDF "
            "和已成功注册的准确正文三元组，"
            "使用所有者授权及 agent 代录；选择后仍须完成六项核查。"
        )


class SelectBody:
    def __init__(
        self, root: ExperimentRoot, *, clock: Callable[[], datetime] | None = None
    ) -> None:
        self.root = root
        self.clock = clock or (lambda: datetime.now(UTC))

    def record(
        self,
        paper: str,
        identity: ExtractionIdentity,
        *,
        selector: str,
        recorder: str,
        request_id: str,
    ) -> dict[str, object]:
        if (
            selector != "owner"
            or recorder != "agent"
            or not request_id.strip()
            or len(request_id) > 128
        ):
            raise BodySelectionError("owner_authorization_required")
        self.root.require()
        require_visibility()
        history = BodySelections(self.root.database, self.root.data_root)
        log = RuntimeLog(FileSink(self.root.root))
        with log.execution(
            "experiment",
            controlled=(BodySelectionError, BodyError, PdfError, FulltextError),
            paper_id=paper,
        ):
            previous = next(
                (r for r in history.history() if r.request_id == request_id), None
            )
            if previous is not None:
                if (
                    previous.paper_id,
                    previous.identity,
                    previous.selector,
                    previous.recorder,
                ) != (paper, identity, selector, recorder):
                    raise BodySelectionError("request_conflict")
                return dict(**previous.model_dump(mode="json"), replayed=True)
            samples = PdfSamples(self.root.database, self.root.data_root)
            sample = samples.require_current_sample(paper)
            root_fact = BodyService(self.root.database, self.root.data_root).root()
            selected_at = self.clock()
            if selected_at.utcoffset() is None:
                raise BodySelectionError("invalid_clock")
            try:
                proposed = BodySelection(
                    body_selection_id="pending",
                    request_id=request_id,
                    request_hash="0" * 64,
                    root_id=root_fact.root_id or "",
                    paper_id=paper,
                    version_id=sample.version_id,
                    revision_no=sample.revision_no,
                    sequence=1,
                    sample_id=sample.sample_id,
                    attachment_id=sample.attachment_id,
                    authorization_id=sample.selection_id,
                    pdf_sha256=sample.pdf_sha256,
                    fingerprint=identity.extraction_fingerprint,
                    reading_sha256=identity.reading_sha256,
                    evidence_map_sha256=identity.evidence_map_sha256,
                    selector="owner",
                    recorder="agent",
                    selected_at=selected_at.astimezone(UTC).isoformat(),
                )
            except ValueError:
                raise BodySelectionError("invalid_identity") from None
            saved, replayed = history.select(
                proposed,
                guard=lambda connection: samples.require_current_sample_in_connection(
                    connection, sample
                ),
            )
            return dict(**saved.model_dump(mode="json"), replayed=replayed)

    def history(self, paper: str) -> dict[str, object]:
        self.root.require()
        require_visibility()
        return {
            "selections": [
                r.model_dump(mode="json")
                for r in BodySelections(
                    self.root.database, self.root.data_root
                ).history(paper)
            ]
        }
