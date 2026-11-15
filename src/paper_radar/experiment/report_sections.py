"""从分析绑定的持久正文层级派生报告章节;不查询当前样本。"""

from collections.abc import Collection

from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.fulltext.models import EvidenceMap
from paper_radar.read_tasks.models import ReadAnalysis
from paper_radar.storage.artifacts import ArtifactStore


def evidence_sections(
    store: ArtifactStore, analysis: ReadAnalysis, evidence_ids: Collection[str]
) -> dict[str, list[dict[str, object]]]:
    # 先核验准确三元组及完整成员,再消费同一个内容寻址的 evidence-map。
    FulltextArtifacts(store).load(
        analysis.artifact_id, expected_identity=analysis.identity
    )
    mapping = EvidenceMap.model_validate_json(
        store.read_artifact(analysis.artifact_id)["evidence_map"]
    )
    sources = {source.source_id: source for source in mapping.source_blocks}
    stack: list[tuple[int, str | None]] = []
    paths: dict[str, tuple[tuple[str, ...], str | None]] = {}
    by_source: dict[str, list[tuple[tuple[str, ...], str | None]]] = {}
    for block in mapping.reading_blocks:
        if block.excluded is not None or block.content_layer != "body":
            continue
        source = sources.get(block.source_id or "")
        if block.label == "section_header":
            level = block.heading_level or 1
            while stack and stack[-1][0] >= level:
                stack.pop()
            reliable = (
                block.role == "source"
                and source is not None
                and not source.unreliable
                and source.kind == "text"
                and bool(source.orig.strip())
                and block.heading_level is not None
            )
            stack.append((level, source.orig if reliable and source else None))
        sequential = (
            ((), "unreliable_section_heading")
            if any(text is None for _, text in stack)
            else (
                tuple(text for _, text in stack if text is not None),
                None if stack else "no_persisted_section",
            )
        )
        if block.label == "section_header":
            path = sequential
        else:
            # 明确父层级优先;无父 heading 的线性正文沿持久阅读顺序继承标题栈。
            path = paths.get(block.parent_id or "", sequential)
        paths[block.block_id] = path
        if source is not None and block.role == "source":
            by_source.setdefault(source.source_id, []).append(path)
    result: dict[str, list[dict[str, object]]] = {}
    for evidence in mapping.evidence:
        if evidence.evidence_id not in evidence_ids:
            continue
        alternatives = tuple(dict.fromkeys(by_source.get(evidence.source_id, ())))
        result[evidence.evidence_id] = [
            dict(
                source_id=evidence.source_id,
                headings=path,
                state="located" if path else "unavailable",
                reason=reason,
            )
            for path, reason in (alternatives or (((), "no_persisted_section"),))
        ]
    return result
