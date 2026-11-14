"""冻结跨库排除字节及本库完整历史依据;不授予任何执行或复用资格。"""

import json
import os
import tempfile
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Connection, insert, select

from paper_radar.body import BodyService
from paper_radar.eligibility import RootPurpose
from paper_radar.experiment.pdf import PdfSamples
from paper_radar.experiment.reports import Reports
from paper_radar.experiment.selections import Selections
from paper_radar.feed_metadata.repository import canonical, sha, transaction
from paper_radar.papers import PaperFacts, normalize_doi
from paper_radar.read_tasks import ReadTasks
from paper_radar.runtime_logging import RuntimeLog, Sink
from paper_radar.screening_tasks import ScreeningTasks
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.filesystem import (
    UnsafePathError,
    controlled_path,
    sync_directory,
)
from paper_radar.storage.history import HistoryBoundary, HistoryKeys, HistoryPage
from paper_radar.storage.schema import exposure_exports


class ExposureError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        next_action = (
            "请先通过论文身份权威补充强 DOI，再重新导出完整清单。"
            if reason == "strong_identity_missing"
            else "请核对根用途、冻结登记、历史引用及制品闭包，保留历史后显式重试。"
        )
        super().__init__(f"{reason}：暴露清单操作停止；{next_action}")


class ExposureAudit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    format_version: int = 1
    root_id: str
    # 元数据注册请求没有持久的精确版本;该字段明确限制审计声称的精度。
    read_request_precision: str = "paper"
    pages: tuple[HistoryPage, ...]


class HistoryOwner(Protocol):
    def exposure_history_in_connection(
        self, connection: Connection, through: dict[str, HistoryKeys] | None = None
    ) -> tuple[HistoryPage, ...]: ...

    def exposure_scope_in_connection(
        self, connection: Connection
    ) -> dict[str, HistoryBoundary]: ...

    def validate_all(self) -> None: ...


def portable_payload(audit: ExposureAudit) -> str:
    """纯投影:规范 DOI 种子、类别与相连权威边;临时审计键均留在库中。"""
    rows = {p.table: p.rows for p in audit.pages}
    versions = {r["version_id"]: r for r in rows["paper_versions"]}
    identifiers = {
        r["version_id"]: r["normalized_value"] for r in rows["external_identifiers"]
    }
    categories: dict[str, set[str]] = {}

    def add(version_id: str, category: str) -> None:
        version = versions[version_id]
        doi = identifiers.get(version_id)
        if doi is None:
            raise ExposureError("strong_identity_missing")
        if normalize_doi(doi) != doi:
            raise ExposureError("registration_invalid")
        categories.setdefault(doi, set()).add(category)
        if version["version_kind"] not in {"preprint", "journal"}:
            raise ExposureError("registration_invalid")

    for table, category in (
        ("experiment_selections", "selection_authorization"),
        ("screening_requests", "screening_request"),
        ("screening_attempts", "screening_attempt"),
        ("body_decisions", "decision"),
        ("experiment_pdf_confirmations", "pdf_confirmation"),
        ("body_pdfs", "pdf_attachment"),
        ("report_entries", "report_member"),
    ):
        for record in rows[table]:
            add(record["version_id"], category)
    for registration in rows["read_registrations"]:
        paper_id = registration["paper_id"]
        strong = [
            v
            for v in versions.values()
            if v["paper_id"] == paper_id and v["version_id"] in identifiers
        ]
        if not strong:
            raise ExposureError("strong_identity_missing")
        for version in strong:
            add(version["version_id"], "read_request")
    for attempt in rows["read_attempts"]:
        add(attempt["version_id"], "read_attempt")
    relations = PaperFacts.exposure_relations(audit.pages, frozenset(categories))
    kinds = {identifiers[v]: versions[v]["version_kind"] for v in identifiers}
    return canonical(
        {
            "domain": "paper-radar.exposure",
            "format_version": 1,
            "root_id": audit.root_id,
            "papers": [
                {
                    "doi": doi,
                    "version_kind": kinds[doi],
                    "categories": sorted(categories[doi]),
                }
                for doi in sorted(categories)
            ],
            "relations": relations,
        }
    )


class Exposures:
    """显式 database/data_root;恢复读取不依赖原布局、配置、模型或时钟。"""

    def __init__(
        self, database: Path, data_root: Path, *, sink: Sink | None = None
    ) -> None:
        self.database, self.data_root = database, data_root
        self.store = ArtifactStore(database, data_root)
        self.log = RuntimeLog(sink)
        self.body = BodyService(database, data_root)
        self.owners: tuple[HistoryOwner, ...] = (
            PaperFacts(database, data_root),
            Selections(database, data_root),
            ScreeningTasks(database, data_root),
            ReadTasks(database, data_root),
            self.body,
            PdfSamples(database, data_root),
            Reports(database, data_root, data_root),
        )

    def _root(self, connection: Connection) -> str:
        fact = self.body.root_in_connection(connection)
        if fact.purpose is not RootPurpose.EXPERIMENT or fact.root_id is None:
            raise ExposureError("root_not_experiment")
        return fact.root_id

    def _capture(
        self, connection: Connection, frozen: ExposureAudit | None = None
    ) -> ExposureAudit:
        through = (
            None
            if frozen is None
            else {page.table: page.identities for page in frozen.pages}
        )
        pages = tuple(
            sorted(
                (
                    page
                    for owner in self.owners
                    for page in owner.exposure_history_in_connection(
                        connection, through
                    )
                ),
                key=lambda p: p.table,
            )
        )
        if through is not None and set(through) != {p.table for p in pages}:
            raise ExposureError("registration_invalid")
        return ExposureAudit(root_id=self._root(connection), pages=pages)

    def _scope(self, connection: Connection) -> dict[str, HistoryBoundary]:
        return {
            name: value
            for owner in self.owners
            for name, value in owner.exposure_scope_in_connection(connection).items()
        }

    def _validate_sources(self) -> None:
        for owner in self.owners:
            owner.validate_all()

    def export(self) -> dict[str, object]:
        with self.log.operation("experiment", controlled=(ExposureError,), run=True):
            self._validate_sources()
            with transaction(self.database) as connection:
                audit = self._capture(connection)
            payload = portable_payload(audit)
            export_id = sha(payload)
            with transaction(self.database) as connection:
                exists = connection.execute(
                    select(exposure_exports.c.export_id).where(
                        exposure_exports.c.export_id == export_id
                    )
                ).scalar_one_or_none()
            if exists is not None:
                return self.receipt(export_id)
            audit_json = canonical(audit.model_dump(mode="json"))
            artifact = self.store.publish_artifact(
                "exposure_manifest",
                {"payload": [payload.encode()], "audit": [audit_json.encode()]},
            )
            expected = {
                p.table: HistoryBoundary(identities=p.identities) for p in audit.pages
            }
            with transaction(self.database, write=True) as connection:
                if (
                    self._root(connection) != audit.root_id
                    or self._scope(connection) != expected
                ):
                    raise ExposureError("facts_changed")
                exists = connection.execute(
                    select(exposure_exports.c.export_id).where(
                        exposure_exports.c.export_id == export_id
                    )
                ).scalar_one_or_none()
                if exists is None:
                    connection.execute(
                        insert(exposure_exports).values(
                            export_id=export_id,
                            root_id=audit.root_id,
                            format_version=1,
                            artifact_id=artifact.artifact_id,
                            audit_sha256=sha(audit_json),
                            scope_json=canonical(
                                {p.table: p.identities for p in audit.pages}
                            ),
                        )
                    )
            return self.receipt(export_id)

    def _load(self, export_id: str) -> tuple[ExposureAudit, bytes]:
        try:
            with transaction(self.database) as connection:
                row = (
                    connection.execute(
                        select(exposure_exports).where(
                            exposure_exports.c.export_id == export_id
                        )
                    )
                    .mappings()
                    .first()
                )
                if row is None:
                    raise ExposureError("export_not_found")
                artifact = self.store.get_artifact(row["artifact_id"])
                members = self.store.read_artifact_in_connection(
                    connection, row["artifact_id"]
                )
                audit = ExposureAudit.model_validate_json(members["audit"])
                if (
                    artifact.kind != "exposure_manifest"
                    or row["format_version"] != 1
                    or audit.format_version != 1
                    or audit.read_request_precision != "paper"
                    or sha(members["audit"]) != row["audit_sha256"]
                    or canonical({p.table: p.identities for p in audit.pages})
                    != row["scope_json"]
                    or canonical(audit.model_dump(mode="json")).encode()
                    != members["audit"]
                    or self._capture(connection, audit) != audit
                    or audit.root_id != row["root_id"]
                    or sha(members["payload"]) != export_id
                    or portable_payload(audit).encode() != members["payload"]
                ):
                    raise ExposureError("registration_invalid")
                return audit, members["payload"]
        except ExposureError:
            raise
        except (ValueError, TypeError, KeyError, IndexError):
            raise ExposureError("registration_invalid") from None

    def payload(self, export_id: str) -> bytes:
        """获准私有可移植字节;强标识与关系可供 C 消费。"""
        return self._load(export_id)[1]

    def receipt(self, export_id: str) -> dict[str, object]:
        audit, payload = self._load(export_id)
        return {
            "export_id": export_id,
            "root_id": audit.root_id,
            "format_version": 1,
            "paper_count": len(json.loads(payload)["papers"]),
            "relative_path": f"exposure/{export_id}.json",
        }

    def write(self, export_id: str, output_dir: Path) -> dict[str, object]:
        """从登记重建受控私有视图;不覆盖不同字节,不写数据库。"""
        payload = self.payload(export_id)
        temporary: Path | None = None
        try:
            for parent in (output_dir, *output_dir.parents):
                if parent.is_symlink():
                    raise UnsafePathError
            relative = f"exposure/{export_id}.json"
            path = controlled_path(
                output_dir,
                relative,
                create_directory=lambda p: p.mkdir(
                    parents=True, exist_ok=True, mode=0o700
                ),
            )
            if path.exists():
                if path.read_bytes() != payload:
                    raise ExposureError("content_corrupt")
            else:
                descriptor, name = tempfile.mkstemp(
                    prefix=".exposure-", dir=path.parent
                )
                temporary = Path(name)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                # link 是无覆盖发布;并发同一内容可安全复用。
                try:
                    os.link(temporary, path, follow_symlinks=False)
                except FileExistsError:
                    if path.read_bytes() != payload:
                        raise ExposureError("content_corrupt") from None
                sync_directory(path.parent)
            return self.receipt(export_id)
        except UnsafePathError:
            raise ExposureError("unsafe_path") from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def validate_all(self) -> None:
        with transaction(self.database) as connection:
            ids = tuple(
                connection.execute(
                    select(exposure_exports.c.export_id).order_by(
                        exposure_exports.c.export_id
                    )
                ).scalars()
            )
        for export_id in ids:
            self._load(export_id)
