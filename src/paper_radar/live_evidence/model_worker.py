"""产品身份合成调用;原始 RPC 和候选只在产品内存,IPC 仅有限事实。"""

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from paper_radar.config import RuntimeConfigSnapshot
from paper_radar.live_evidence.model_manifest import ModelCell
from paper_radar.live_evidence.receipt import WireModel
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from paper_radar.llm.dispatch import CollectionReason
from paper_radar.llm.models import CallDescription
from paper_radar.llm.rpc_types import RpcReason
from paper_radar.reading.context import ReadContext
from paper_radar.stage_inputs import StageInput


class ModelObservation(WireModel):
    passed: bool = Field(strict=True)
    authority: Literal["boundary", "value", "read", "none"]
    failure: CollectionReason | None = None
    rpc_reason: RpcReason | None = None
    initialized: bool = Field(default=False, strict=True)
    settled: bool = Field(default=False, strict=True)
    eof: bool = Field(default=False, strict=True)
    terminated: bool = Field(default=False, strict=True)
    terminal_clean: bool = Field(default=False, strict=True)
    deleted: bool = Field(default=False, strict=True)
    input_tokens: int | None = Field(default=None, ge=0, strict=True)
    output_tokens: int | None = Field(default=None, ge=0, strict=True)

    @model_validator(mode="after")
    def consistent(self) -> "ModelObservation":
        if self.passed and (
            self.failure is not None
            or self.rpc_reason is not None
            or self.authority == "none"
            or not all(
                (
                    self.initialized,
                    self.settled,
                    self.eof,
                    self.terminated,
                    self.terminal_clean,
                    self.deleted,
                )
            )
        ):
            raise ValueError("collector_result_invalid")
        if not self.passed and self.failure is None:
            raise ValueError("collector_result_invalid")
        return self


def build_material_call(
    root: Path, cell: ModelCell
) -> tuple[
    CallDescription, bytes, RuntimeConfigSnapshot, StageInput, ReadContext | None
]:
    """固定文件名与权威编译器;不持久化合成 snapshot。"""
    import hashlib
    import json

    from paper_radar.config import StageName
    from paper_radar.config.service import compile_materials
    from paper_radar.fulltext.models import EvidenceMap
    from paper_radar.fulltext.normalization import render_reading
    from paper_radar.fulltext.quality import reconstruct_context
    from paper_radar.live_evidence.model_manifest import material_root
    from paper_radar.llm import build_call, render_request
    from paper_radar.llm.rpc import validate_request
    from paper_radar.reading.context import ExtractionIdentity
    from paper_radar.stage_inputs import (
        ExtractionFacts,
        ReadFacts,
        ScreeningFacts,
        build_stage_input,
    )

    directory = material_root(root, cell.use_id)
    snapshot = compile_materials(directory / "config/settings.yaml")
    if snapshot.snapshot_id != cell.snapshot_id:
        raise ValueError("collector_material_invalid")
    stage = StageName(cell.use_id.rsplit("-", 1)[0])
    context = None
    reading = None
    facts: ReadFacts | ScreeningFacts
    if stage == StageName.READ:
        extraction = build_stage_input(
            snapshot,
            StageName.EXTRACTION,
            ExtractionFacts(**json.loads((directory / "extraction.json").read_bytes())),
        )
        reading = (directory / "reading.md").read_bytes()
        evidence_raw = (directory / "evidence-map.json").read_bytes()
        evidence = EvidenceMap.model_validate_json(evidence_raw)
        if reading != render_reading(evidence):
            raise ValueError("collector_material_invalid")
        identity = ExtractionIdentity(
            extraction.fingerprint,
            hashlib.sha256(reading).hexdigest(),
            hashlib.sha256(evidence_raw).hexdigest(),
        )
        context = reconstruct_context(evidence, identity)
        facts = ReadFacts(
            extraction_input=extraction,
            reading_sha256=identity.reading_sha256,
            evidence_map_sha256=identity.evidence_map_sha256,
            output_language="zh",
        )
    else:
        facts = ScreeningFacts(**json.loads((directory / "abstract.json").read_bytes()))
    stage_input = build_stage_input(snapshot, stage, facts)
    description = build_call(
        stage_input, snapshot, snapshot, read_context=context, reading=reading
    )
    request = render_request(description)
    if (
        hashlib.sha256(request).hexdigest() != cell.request_sha256
        or validate_request(request) is not None
    ):
        raise ValueError("collector_material_invalid")
    return description, request, snapshot, stage_input, context


def execute_model(
    root: Path, site: SiteConfiguration, cell: ModelCell, exchange: Callable[..., None]
) -> ModelObservation:
    """只在不可逆降权worker内调用,exchange仅发送闭合阶段。"""
    import os

    from paper_radar.live_evidence.model_manifest import ModelCell
    from paper_radar.llm.dispatch import DispatchDenied
    from paper_radar.llm.rpc import run_call
    from paper_radar.llm.rpc_types import RpcAudit, RpcFailure
    from paper_radar.pi_execution.admission import bind_description
    from paper_radar.pi_execution.errors import ExecutionError
    from paper_radar.pi_execution.launcher import (
        CollectionExecutionContext,
        prepare_launch,
    )
    from paper_radar.pi_execution.resources import CleanupAudit
    from paper_radar.reading.acceptance_v2 import (
        ReadV2OutputError,
        validate_read_output_v2,
    )
    from paper_radar.screening.errors import OutputValidationError
    from paper_radar.screening.validation import validate_output

    if os.getuid() != site.product_uid or os.getgid() != site.product_gid:
        return ModelObservation(
            passed=False, authority="none", failure="permission_failed"
        )
    audit = RpcAudit()
    cleanup = CleanupAudit()
    reason: CollectionReason | None = None
    rpc_reason = None
    authority: Literal["boundary", "value", "read", "none"] = "none"
    tokens: tuple[int | None, int | None] = (None, None)
    try:
        description, request, snapshot, stage_input, context = build_material_call(
            root, cell
        )
        actual = bind_description(
            description,
            supply_id=site.binding.supply_id,
            install_id=site.binding.install_id,
            launch_policy_version=site.binding.launch_policy_version,
            isolation_policy_version=site.binding.isolation_policy_version,
            cwd_section=site.binding.cwd_section,
            auth_mode=site.binding.auth_mode,
            proxy=site.binding.proxy,
        )
        if actual != cell.model or not isinstance(cell, ModelCell):
            raise DispatchDenied("identity_mismatch")
        execution = CollectionExecutionContext(
            cell.use_id,
            cell.snapshot_id,
            cell.request_sha256,
            site.snapshot_id,
            site.binding.supply_id,
            site.binding.install_id,
        )
        with prepare_launch(
            site.database,
            description,
            roots=site.roots,
            credentials_dir=site.credentials_dir,
            auth_mode=site.binding.auth_mode,
            proxy=site.binding.proxy,
            collection=execution,
            before_auth=lambda pid, start, unit: exchange("auth", pid, start, unit),
            cleanup_audit=cleanup,
        ) as launch:
            execution.recheck(site.database, description)
            exchange("prepared", *launch.placement_metadata())
            result = run_call(
                description,
                request,
                launch,
                before_prompt=lambda: exchange("model", *launch.placement_metadata()),
                audit=audit,
                expected_cwd_section=site.binding.cwd_section,
            )
        if isinstance(result, RpcFailure):
            rpc_reason = result.reason
            reason = (
                "identity_mismatch"
                if audit.identity_mismatch or result.reason == RpcReason.MODEL_STATE
                else "protocol_failed"
            )
        elif (
            result.provider != description.provider or result.model != description.model
        ):
            reason = "identity_mismatch"
        else:
            tokens = (result.input_tokens, result.output_tokens)
            if description.stage == "read":
                assert context is not None
                validate_read_output_v2(result.raw_response, context, attempt_ordinal=1)
            elif description.stage == "value":
                validate_output(
                    "value_prediction",
                    result.raw_response,
                    stage_input.value_prediction_context(
                        snapshot, original_title_is_zh=False
                    ),
                )
            else:
                validate_output("boundary", result.raw_response)
            authority = description.stage
    except DispatchDenied as error:
        reason = error.reason
    except (OutputValidationError, ReadV2OutputError):
        reason = "protocol_failed"
    except ExecutionError as error:
        reason = (
            "isolation_failed"
            if error.reason
            in {"cleanup_failed", "placement_mismatch", "placement_anchor_invalid"}
            else "resource_unavailable"
        )
    except PermissionError:
        reason = "permission_failed"
    except BaseException as error:
        reason = (
            "interrupted"
            if isinstance(error, (KeyboardInterrupt, SystemExit))
            else "collector_failed"
        )
    if audit.cleanup_failed:
        reason = "isolation_failed"
    if reason is None and not all(
        (
            cleanup.auth_terminal,
            cleanup.auth_deleted,
            cleanup.model_terminal,
            cleanup.model_deleted,
        )
    ):
        reason = "isolation_failed"
    return ModelObservation(
        passed=reason is None,
        failure=reason,
        authority=authority,
        rpc_reason=rpc_reason,
        initialized=audit.initialized,
        settled=audit.settled,
        eof=audit.eof,
        terminated=audit.terminated,
        terminal_clean=cleanup.auth_terminal and cleanup.model_terminal,
        deleted=cleanup.auth_deleted and cleanup.model_deleted,
        input_tokens=tokens[0],
        output_tokens=tokens[1],
    )
