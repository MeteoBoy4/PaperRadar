"""显式请求的 Docling CanonicalParser;import 不加载 SDK。"""

import json
import tempfile
from pathlib import Path
from typing import Protocol, get_args

from paper_radar.body.models import ParserFailure, ParserResult
from paper_radar.config.extraction import ExtractionSemantics
from paper_radar.docling_execution.deployment import snapshot_models
from paper_radar.docling_execution.models import (
    DoclingRun,
    WorkerRequest,
    WorkerResponse,
)
from paper_radar.docling_execution.process import DoclingProcess
from paper_radar.docling_runtime import probe_docling_runtime
from paper_radar.docling_toolchain import PDFBackend, ToolchainId, backend_identity
from paper_radar.fulltext.execution_audit import ExtractionExecutionAudit

__all__ = ["DoclingParser", "DoclingPreflightError", "DoclingRun"]


class DoclingPreflightError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(
            f"Docling 预检拒绝:{reason};"
            "请核对所选工具链、部署清单与模型文件,未领取尝试。"
        )


class DoclingExecution(Protocol):
    def execute(self, request: WorkerRequest) -> WorkerResponse: ...


class PreparedDocling:
    def __init__(
        self,
        run: DoclingRun,
        executor: DoclingExecution,
        semantics: ExtractionSemantics,
        snapshot: tempfile.TemporaryDirectory[str],
        audit: ExtractionExecutionAudit,
    ) -> None:
        self.run, self.executor, self.semantics = run, executor, semantics
        self.snapshot, self.audit = snapshot, audit
        self.closed = False

    def close(self) -> None:
        self.snapshot.cleanup()
        self.closed = True

    def convert(self, pdf: bytes, semantics: ExtractionSemantics) -> ParserResult:
        if self.closed or semantics != self.semantics:
            raise ParserFailure("executor_error")
        with tempfile.TemporaryDirectory(prefix="paperradar-docling-run-") as folder:
            path = Path(folder)
            pdf_path = path / "input.pdf"
            pdf_path.write_bytes(pdf)
            request = WorkerRequest(
                model_root=self.snapshot.name,
                pdf_path=str(pdf_path),
                response_path=str(path / "response.json"),
                timeout_seconds=self.run.timeout_seconds,
                memory_limit_bytes=self.run.memory_limit_bytes,
                threads=self.run.threads,
                backend_config_json=semantics.backend_config_json,
                model_commits={
                    m.stage.value: m.commit_sha for m in semantics.model_artifacts
                },
            )
            response = self.executor.execute(request)
        if response.failure is not None:
            raise ParserFailure(
                response.failure, peak_memory_bytes=response.peak_memory_bytes
            )
        if response.document is None or response.document_json is None:
            raise ParserFailure("executor_error")
        return ParserResult(
            response.document,
            response.document_json.encode("utf-8"),
            response.peak_memory_bytes,
            response.warnings,
        )


class DoclingParser:
    def __init__(
        self, run: DoclingRun, *, executor: DoclingExecution | None = None
    ) -> None:
        self.run = run
        self.executor = executor if executor is not None else DoclingProcess()

    def preflight(self, semantics: ExtractionSemantics) -> PreparedDocling:
        run, executor = self.run, self.executor
        try:
            config = json.loads(semantics.backend_config_json)
            backend = config["pdf_backend"]
            matches = [
                toolchain
                for toolchain in get_args(ToolchainId)
                if backend in get_args(PDFBackend)
                and backend_identity(toolchain, backend) == semantics.backend
            ]
            if len(matches) != 1:
                raise DoclingPreflightError("selection_invalid")
            probe = probe_docling_runtime(
                matches[0], backend, requested=True, enabled=True
            )
            if not probe.passed:
                raise DoclingPreflightError(probe.reason.value)
            audit = ExtractionExecutionAudit(
                toolchain=matches[0],
                pdf_backend=backend,
                component_versions=semantics.backend.component_versions,
                backend_config_hash=semantics.backend_config_hash,
                model_artifacts_hash=semantics.model_artifacts_hash or "",
                timeout_seconds=run.timeout_seconds,
                memory_limit_bytes=run.memory_limit_bytes,
                threads=run.threads,
            )
            snapshot = snapshot_models(run.model_root, semantics)
        except DoclingPreflightError:
            raise
        except (OSError, ValueError, KeyError, TypeError):
            raise DoclingPreflightError("model_deployment_invalid") from None
        return PreparedDocling(run, executor, semantics, snapshot, audit)

    def convert(self, pdf: bytes, semantics: ExtractionSemantics) -> ParserResult:
        # 服务只调用本次 preflight 返回的独立准备对象,避免并发覆盖。
        raise ParserFailure("executor_error")
