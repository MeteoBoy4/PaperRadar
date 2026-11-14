"""B 显式单次正文执行:当前样本守卫、资源事实与持久回放。"""

import hashlib
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import Field
from sqlalchemy import Connection, insert, select

from paper_radar.body import BodyService
from paper_radar.body.models import BodyError, ExtractionView
from paper_radar.body.repository import transaction
from paper_radar.config import load_config_snapshot, resolve_config_snapshot_reference
from paper_radar.docling_executor import (
    DoclingParser,
    DoclingPreflightError,
    DoclingRun,
)
from paper_radar.doctor.service import Result
from paper_radar.experiment.candidates import SnapshotModel
from paper_radar.experiment.pdf import PdfError, PdfSamples
from paper_radar.experiment.preflight import model_snapshot_disk_check
from paper_radar.experiment.root import ExperimentRoot
from paper_radar.runtime_logging import FileSink, RuntimeLog
from paper_radar.storage.schema import (
    body_extraction_attempts,
    body_extraction_inputs,
    experiment_extraction_peaks,
    experiment_extractions,
)


class ExtractionError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(
            f"{reason}：提取停止；核对当前样本、cgroup ≤8 GiB/swap=0、"
            "模型部署与快照磁盘；回查 trace 后显式重跑，不绕过预算或质量。"
        )


@dataclass(frozen=True)
class ResourcePaths:
    membership: Path = Path("/proc/self/cgroup")
    mount: Path = Path("/sys/fs/cgroup")
    meminfo: Path = Path("/proc/meminfo")
    mountinfo: Path | None = Path("/proc/self/mountinfo")


RESOURCE_PATHS = ResourcePaths()


class ResourceFact(SnapshotModel):
    scope_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    memory_max_bytes: int = Field(gt=0, le=8 * 1024**3)
    swap_max_bytes: Literal[0] = 0
    host_mem_available_bytes: int | None = Field(default=None, ge=0)


class ExecutionRecord(SnapshotModel):
    attempt_id: str
    sample_id: str
    paper_id: str
    resources: ResourceFact


def _number(path: Path) -> int:
    if path.is_symlink():
        raise ValueError
    raw = path.read_text().strip()
    if not re.fullmatch(r"[0-9]+", raw):
        raise ValueError
    return int(raw)


def _mount_path(raw: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), raw)


def resource_fact(paths: ResourcePaths) -> tuple[ResourceFact, Path]:
    """只读当前进程所属 v2 scope;拒绝歧义、越界及不合格限制。"""
    try:
        entries = [
            line[3:]
            for line in paths.membership.read_text().splitlines()
            if line.startswith("0::")
        ]
        if (
            len(entries) != 1
            or not entries[0].startswith("/")
            or str(PurePosixPath(entries[0])) != entries[0]
            or any(part in {".", ".."} for part in entries[0].split("/"))
        ):
            raise ValueError
        membership = PurePosixPath(entries[0])
        mount_root = PurePosixPath("/")
        if paths.mountinfo is not None:
            mounts = []
            for line in paths.mountinfo.read_text().splitlines():
                fields, separator, filesystem = line.partition(" - ")
                parts = fields.split()
                if (
                    separator
                    and filesystem.split()[0] == "cgroup2"
                    and len(parts) >= 6
                    and Path(_mount_path(parts[4])) == paths.mount
                ):
                    mounts.append(PurePosixPath(_mount_path(parts[3])))
            if len(mounts) != 1:
                raise ValueError
            mount_root = mounts[0]
        relative = membership.relative_to(mount_root)
        group = paths.mount / relative
        current = paths.mount
        if not current.is_absolute() or any(
            p.is_symlink() for p in (current, *current.parents)
        ):
            raise ValueError
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ValueError
        if not (paths.mount / "cgroup.controllers").is_file():
            raise ValueError
        maximum = _number(group / "memory.max")
        swap = _number(group / "memory.swap.max")
        if maximum <= 0 or maximum > 8 * 1024**3 or swap != 0:
            raise ValueError
        available = None
        try:
            matches = re.findall(
                r"^MemAvailable:\s+([0-9]+) kB$",
                paths.meminfo.read_text(),
                re.MULTILINE,
            )
            if len(matches) == 1:
                available = int(matches[0]) * 1024
        except (OSError, ValueError):
            pass
        return ResourceFact(
            scope_sha256=hashlib.sha256(str(group).encode()).hexdigest(),
            memory_max_bytes=maximum,
            host_mem_available_bytes=available,
        ), group
    except (OSError, ValueError, IndexError):
        raise ExtractionError("cgroup_limit_invalid") from None


class _Execution:
    def __init__(self, paths: ResourcePaths, sample_id: str, paper_id: str) -> None:
        self.paths, self.sample_id, self.paper_id = paths, sample_id, paper_id
        self.fact, self.group = resource_fact(paths)
        self.peak: int | None = None
        self.attempt_id: str | None = None

    def before_claim(self) -> None:
        fact, group = resource_fact(self.paths)
        if fact.scope_sha256 != self.fact.scope_sha256:
            raise ExtractionError("cgroup_changed")
        self.fact, self.group = fact, group

    def claimed(self, connection: Connection, attempt_id: str) -> None:
        self.attempt_id = attempt_id
        record = ExecutionRecord(
            attempt_id=attempt_id,
            sample_id=self.sample_id,
            paper_id=self.paper_id,
            resources=self.fact,
        )
        connection.execute(
            insert(experiment_extractions).values(
                attempt_id=attempt_id,
                sample_id=self.sample_id,
                paper_id=self.paper_id,
                record_json=record.model_dump_json(),
            )
        )

    def completed(self) -> None:
        try:
            fact, group = resource_fact(self.paths)
            if fact.scope_sha256 != self.fact.scope_sha256:
                return
            self.peak = _number(group / "memory.peak")
        except (OSError, ValueError, ExtractionError):
            self.peak = None

    def settled(self, connection: Connection, attempt_id: str) -> None:
        connection.execute(
            insert(experiment_extraction_peaks).values(
                attempt_id=attempt_id, cgroup_peak_bytes=self.peak
            )
        )


def extraction_payload(view: ExtractionView) -> dict[str, object]:
    return dict(
        fingerprint=view.fingerprint,
        artifact_id=view.artifact_id,
        quality=view.quality.basis.value,
        quality_failure=view.quality.failure.value if view.quality.failure else None,
        automatic_quality=(
            "passed"
            if view.artifact_id and view.attempts[-1].failure is None
            else "failed"
            if view.artifact_id
            else "unknown"
        ),
        permanent_failure=view.permanent_failure,
        remaining_attempts=view.remaining_attempts,
        succeeded=bool(
            view.artifact_id
            and not view.permanent_failure
            and view.attempts[-1].failure is None
        ),
        attempts=[
            dict(
                attempt_id=a.attempt_id,
                ordinal=a.ordinal,
                claimed_at=a.claimed_at,
                failure=a.failure.value if a.failure else None,
                settled_at=a.settled_at,
                worker_ru_maxrss_bytes=a.peak_memory_bytes or "unknown",
                executor_audit=a.executor_audit.model_dump(mode="json")
                if a.executor_audit
                else None,
            )
            for a in view.attempts
        ],
    )


def extract_once(
    root: ExperimentRoot,
    *,
    paper_id: str,
    snapshot: str,
    model_root: Path,
    timeout_seconds: float,
    threads: int,
) -> dict[str, object]:
    root.require()
    log = RuntimeLog(FileSink(root.root))
    with log.execution(
        "experiment",
        controlled=(ExtractionError, PdfError, BodyError, DoclingPreflightError),
        paper_id=paper_id,
    ):
        samples = PdfSamples(root.database, root.data_root)
        sample = samples.require_current_sample(paper_id)
        observation = _Execution(RESOURCE_PATHS, sample.sample_id, paper_id)
        selected = load_config_snapshot(
            root.database, resolve_config_snapshot_reference(root.database, snapshot)
        )
        # 与真正快照使用同一 tempfile 根;按所选文件实际字节核对,不套开发/Pi阈值。
        disk = model_snapshot_disk_check(
            model_root, Path(tempfile.gettempdir()), selected.extraction
        )
        if disk.result is not Result.PASSED:
            raise ExtractionError(disk.reason)
        try:
            run = DoclingRun(
                model_root=model_root,
                timeout_seconds=timeout_seconds,
                memory_limit_bytes=32 * 1024**3,
                threads=threads,
            )
        except ValueError:
            raise ExtractionError("runtime_selection_invalid") from None
        view = BodyService(root.database, root.data_root).extract(
            paper_id,
            snapshot_id=selected.snapshot_id,
            parser=DoclingParser(run),
            claim_guard=lambda connection: samples.require_current_sample_in_connection(
                connection, sample
            ),
            observer=observation,
        )
        payload = extraction_payload(view)
        payload["executions"] = list(
            Extractions(root.database, root.data_root).history(paper_id)
        )
        payload["host_memory_disclosure"] = (
            observation.fact.host_mem_available_bytes
            if observation.fact.host_mem_available_bytes is not None
            else "unknown"
        )
        payload["cached"] = observation.attempt_id is None
        return payload


class Extractions:
    def __init__(self, database: Path, data_root: Path) -> None:
        self.database, self.data_root = database, data_root

    def history(self, paper_id: str | None = None) -> tuple[dict[str, object], ...]:
        # 先冻结只追加执行行,再读取其完整前置闭包;后来的样本只能增加,不能消失。
        with transaction(self.database) as connection:
            rows = (
                connection.execute(
                    select(experiment_extractions).order_by(
                        experiment_extractions.c.attempt_id
                    )
                )
                .mappings()
                .all()
            )
            peaks = {
                row["attempt_id"]: row["cgroup_peak_bytes"]
                for row in connection.execute(
                    select(experiment_extraction_peaks)
                ).mappings()
            }
            attempts = {
                row["attempt_id"]: row
                for row in connection.execute(
                    select(
                        body_extraction_attempts, body_extraction_inputs.c.pdf_sha256
                    ).join(body_extraction_inputs)
                ).mappings()
            }
            if not set(peaks) <= {row["attempt_id"] for row in rows}:
                raise ExtractionError("registration_invalid")
        samples = {
            sample.sample_id: sample
            for sample in PdfSamples(self.database, self.data_root).samples()
        }
        records = []
        for row in rows:
            try:
                record = ExecutionRecord.model_validate_json(row["record_json"])
                sample = samples[record.sample_id]
                attempt = attempts[record.attempt_id]
                from paper_radar.body.extraction import decode_attempt_audit

                audit = decode_attempt_audit(attempt["executor_audit_json"])
                peak = peaks.get(record.attempt_id)
                if (
                    record.attempt_id != row["attempt_id"]
                    or record.sample_id != row["sample_id"]
                    or record.paper_id != row["paper_id"]
                    or sample.paper_id != record.paper_id
                    or attempt["pdf_sha256"] != sample.pdf_sha256
                    or record.model_dump_json() != row["record_json"]
                    or audit is None
                    or audit.memory_limit_bytes != 32 * 1024**3
                    or (peak is not None and (type(peak) is not int or peak < 0))
                ):
                    raise ValueError
            except (ValueError, TypeError, KeyError):
                raise ExtractionError("registration_invalid") from None
            if paper_id is None or record.paper_id == paper_id:
                records.append(
                    dict(
                        **record.model_dump(mode="json"),
                        cgroup_memory_peak_bytes=peak
                        if peak is not None
                        else "unknown",
                        cgroup_peak_scope="historical_group_peak",
                    )
                )
        return tuple(records)

    def validate_all(self) -> None:
        self.history()
