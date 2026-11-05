"""正文当前性与显式历史配置参照的只读组合。"""

from pathlib import Path
from typing import Literal

from paper_radar.body import BodyService
from paper_radar.body.models import CurrentBody
from paper_radar.calibration import visibility
from paper_radar.config import load_config_snapshot
from paper_radar.config.compile import StageName, StageStatus
from paper_radar.config.diff import compare_config_snapshots
from paper_radar.config.errors import ConfigError
from paper_radar.eligibility import RootPurpose
from paper_radar.read_queries.models import (
    AnalysisView,
    CurrentRead,
    DiscardCategory,
    DiscardCount,
    OldReadConfig,
    ReadConfigComponent,
)
from paper_radar.read_tasks import ReadAnalysis, ReadTaskError, ReadTasks
from paper_radar.reading.acceptance_v2 import ReadV2DiagnosticReason
from paper_radar.reading.context import SourceSlice


class ReadQueries:
    def __init__(self, database: Path, data_root: Path) -> None:
        self.database = database
        self.tasks = ReadTasks(database, data_root)
        self.body = BodyService(database, data_root)

    def _visible(self, ordinary: bool) -> None:
        assembled = visibility.evaluate_visibility(frozenset())
        if (
            assembled.permission(visibility.VisibilityCapability.AGENT_CONTENT)
            is not visibility.VisibilityPermission.ALLOWED
        ):
            raise ReadTaskError("visibility_denied")
        if ordinary and self.body.root().purpose is not RootPurpose.PRODUCTION:
            raise ReadTaskError("ordinary_consumption_denied")

    def _config(
        self, task_id: str, snapshot_id: str | None
    ) -> tuple[Literal["current", "old", "unknown"], tuple[ReadConfigComponent, ...]]:
        if snapshot_id is None:
            return "unknown", ()
        try:
            after = load_config_snapshot(self.database, snapshot_id)
            before = load_config_snapshot(
                self.database, self.tasks.task(task_id).snapshot_id
            )
        except ConfigError:
            return "unknown", ()
        if any(
            s.stages[StageName.READ].status is not StageStatus.READY
            for s in (before, after)
        ):
            return "unknown", ()
        diff = compare_config_snapshots(before, after)
        change = next(
            (c for c in diff.projection_changes if c.stage is StageName.READ), None
        )
        if change is None:
            return "current", ()
        names = {c.name for c in change.components}
        return "old", tuple(
            c
            for c in ReadConfigComponent
            if ("chunking_version" if c is ReadConfigComponent.CHUNKING else c.value)
            in names
        )

    def _view(
        self, analysis: ReadAnalysis, body: CurrentBody, snapshot_id: str | None
    ) -> AnalysisView:
        identity = body.identity
        config, changes = self._config(analysis.task_id, snapshot_id)
        categories: tuple[DiscardCategory, ...] = (
            "main_findings",
            "reusable_points",
            "key_limitations",
        )
        counts = tuple(
            DiscardCount(
                category, sum(d["item_category"] == category for d in analysis.discards)
            )
            for category in categories
        )
        return AnalysisView(
            analysis.analysis_id,
            analysis.paper_id,
            analysis.output.output_language,
            analysis.identity,
            "undeterminable"
            if identity is None
            else "current"
            if identity == analysis.identity
            else "historical",
            body.reason,
            config,
            changes,
            analysis.executor_kind,
            analysis.root_purpose,
            analysis.quality_basis,
            analysis.output,
            bool(analysis.discards),
            counts,
            any(
                d.get("reason") != ReadV2DiagnosticReason.EVIDENCE_ITEM_DISCARDED
                for d in analysis.diagnostics
            ),
        )

    def current(
        self, paper_id: str, *, snapshot_id: str | None = None, ordinary: bool = False
    ) -> CurrentRead:
        self._visible(ordinary)
        body = self.body.current_body(paper_id)
        identity = body.identity
        if identity is None:
            return CurrentRead(paper_id, "undeterminable", None, (), body.reason)
        latest: dict[str, ReadAnalysis] = {}
        for analysis in self.tasks.analyses(paper_id):
            if analysis.identity == identity:
                latest[analysis.output.output_language] = analysis
        views = tuple(
            self._view(
                self.tasks.analysis(latest[key].analysis_id, ordinary=True)
                if ordinary
                else latest[key],
                body,
                snapshot_id,
            )
            for key in sorted(latest)
        )
        return CurrentRead(
            paper_id, "available" if views else "no_analysis", identity, views
        )

    def analysis(
        self,
        analysis_id: str,
        *,
        snapshot_id: str | None = None,
        ordinary: bool = False,
    ) -> AnalysisView:
        self._visible(ordinary)
        analysis = self.tasks.analysis(analysis_id, ordinary=ordinary)
        return self._view(
            analysis, self.body.current_body(analysis.paper_id), snapshot_id
        )

    def history(
        self, paper_id: str, *, snapshot_id: str | None = None, ordinary: bool = False
    ) -> tuple[AnalysisView, ...]:
        self._visible(ordinary)
        body = self.body.current_body(paper_id)
        return tuple(
            self._view(a, body, snapshot_id)
            for a in self.tasks.analyses(paper_id, ordinary=ordinary)
        )

    def old_configurations(
        self,
        paper_ids: tuple[str, ...] | None = None,
        *,
        snapshot_id: str | None = None,
        ordinary: bool = False,
    ) -> tuple[OldReadConfig, ...]:
        self._visible(ordinary)
        selected = self.tasks.analysis_papers() if paper_ids is None else paper_ids
        return tuple(
            OldReadConfig(
                a.paper_id, a.analysis_id, a.output_language, a.changed_components
            )
            for paper in dict.fromkeys(selected)
            for a in self.current(
                paper, snapshot_id=snapshot_id, ordinary=ordinary
            ).analyses
            if a.config_status == "old"
        )

    def evidence(
        self, analysis_id: str, evidence_id: str, *, ordinary: bool = False
    ) -> tuple[SourceSlice, ...]:
        self._visible(ordinary)
        return self.tasks.evidence(analysis_id, evidence_id, ordinary=ordinary)
