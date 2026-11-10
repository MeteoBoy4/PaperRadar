"""固定合成六格材料;复用真实纯编译、StageInput与请求渲染。"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path

import yaml

from paper_radar.config import StageName
from paper_radar.config.service import compile_materials
from paper_radar.fulltext.canonical import (
    CanonicalBlock,
    CanonicalDocument,
    CanonicalPage,
    CanonicalProvenance,
)
from paper_radar.fulltext.normalization import (
    canonical_json,
    normalize_document,
    render_reading,
)
from paper_radar.fulltext.quality import reconstruct_context
from paper_radar.live_evidence.deployment import file_digests
from paper_radar.live_evidence.model_manifest import USES, ModelCell
from paper_radar.live_evidence.receipt_v2 import ApprovedPlanV2
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from paper_radar.llm import build_call, render_request
from paper_radar.pi_execution.admission import bind_description
from paper_radar.pi_execution.site_binding import component_digest
from paper_radar.reading import ExtractionIdentity
from paper_radar.stage_inputs import (
    ExtractionFacts,
    ReadFacts,
    ScreeningFacts,
    build_stage_input,
)


def freeze_materials(
    root: Path,
    site: SiteConfiguration,
    plans: tuple[ApprovedPlanV2, ...],
    *,
    source_root: Path,
) -> tuple[tuple[ModelCell, ...], dict[str, str]]:
    cells = []
    members = {}
    for use_id, plan in zip(USES, plans, strict=True):
        directory = root / "materials" / use_id
        # 仓库示例是版本控制的合成材料;不复制用户配置/研究资料/数据库。
        shutil.copytree(source_root / "examples", directory)
        settings = directory / "config/settings.yaml"
        selectors = {
            "profile": "profile-example-v1",
            "models": "models-live-v2",
            "topics": "topics-v1",
            "escalation": "reuse-escalation-v1",
            "extraction": "extraction-example-v2",
            "read": "read-v1",
            "prompts": {
                "boundary": "v1",
                "value": "v1",
                "reuse": "v1",
                "reading": "v1",
            },
            "contracts": {
                "boundary": "v1",
                "value_prediction": "v1",
                "reuse_assessment": "v1",
                "decision_reasons": "v1",
                "read": "v1",
            },
            "adapters": {
                slot: "pi-v1" for slot in ("screening", "reuse_assessment", "reading")
            },
        }
        settings.write_text(yaml.safe_dump(selectors), encoding="utf-8")
        model: dict[str, object] = {
            "provider": site.binding.provider,
            "model": site.binding.model,
            "protocol": "prompt_only",
            "sampling": site.binding.sampling,
        }
        if site.binding.sampling == "explicit":
            model.update(temperature=site.binding.temperature, top_p=site.binding.top_p)
        (directory / "config/models/models-live-v2.yaml").write_text(
            yaml.safe_dump(
                {
                    "version": "models-live-v2",
                    "format_version": 2,
                    **{
                        slot: dict(model)
                        for slot in ("screening", "reuse_assessment", "reading")
                    },
                }
            ),
            encoding="utf-8",
        )
        adapter = directory / "config/adapters/pi-v1.yaml"
        content = yaml.safe_load(adapter.read_text())
        content.update(pi_version="1.4.0", thinking_level=use_id.rsplit("-", 1)[1])
        adapter.write_text(yaml.safe_dump(content), encoding="utf-8")
        snapshot = compile_materials(settings)
        stage = StageName(use_id.rsplit("-", 1)[0])
        context = None
        reading = None
        facts: ReadFacts | ScreeningFacts
        if stage is StageName.READ:
            text = (
                "Synthetic experiment: a controlled weather estimator "
                "reduced error from 2 to 1 units."
            )
            document = CanonicalDocument(
                pages=(CanonicalPage(page_no=1, width=600.0, height=800.0),),
                blocks=(
                    CanonicalBlock(
                        ref="#/texts/0",
                        order=(0,),
                        label="text",
                        orig=text,
                        text=text,
                        provenance=(
                            CanonicalProvenance(
                                page_no=1,
                                bbox=(20.0, 20.0, 500.0, 80.0),
                                charspan=(0, len(text)),
                            ),
                        ),
                    ),
                ),
            )
            evidence = normalize_document(document)
            evidence_raw = canonical_json(evidence.model_dump(mode="json"))
            reading = render_reading(evidence)
            (directory / "evidence-map.json").write_bytes(evidence_raw)
            (directory / "reading.md").write_bytes(reading)
            (directory / "extraction.json").write_text(
                json.dumps({"pdf_sha256": "1" * 64})
            )
            extraction = build_stage_input(
                snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256="1" * 64)
            )
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
            values = {
                "title": "Synthetic weather study",
                "abstract": (
                    "A synthetic controlled experiment compares "
                    "weather estimation methods on generated data."
                ),
                "abstract_truncated": False,
            }
            (directory / "abstract.json").write_text(json.dumps(values))
            facts = ScreeningFacts(**values)
        stage_input = build_stage_input(snapshot, stage, facts)
        description = build_call(
            stage_input, snapshot, snapshot, read_context=context, reading=reading
        )
        model_binding = bind_description(
            description,
            supply_id=site.binding.supply_id,
            install_id=site.binding.install_id,
            launch_policy_version=site.binding.launch_policy_version,
            isolation_policy_version=site.binding.isolation_policy_version,
            cwd_section=site.binding.cwd_section,
            auth_mode=site.binding.auth_mode,
            proxy=site.binding.proxy,
        )
        if model_binding != replace(
            site.binding, thinking_level=use_id.rsplit("-", 1)[1]
        ):
            raise ValueError("collector_model_binding_invalid")
        own = {
            "materials/" + use_id + "/" + name: digest
            for name, digest in file_digests(directory).items()
        }
        members.update(own)
        cells.append(
            ModelCell(
                use_id=use_id,
                plan=plan,
                model=model_binding,
                binding={},
                material_sha256=component_digest(own),
                snapshot_id=snapshot.snapshot_id,
                request_sha256=hashlib.sha256(render_request(description)).hexdigest(),
            )
        )
    return tuple(cells), members
