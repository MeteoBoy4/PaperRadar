"""实验 Feed 组合,保留 HTTP、条目及缺项真实状态的安全投影。"""

from typing import Any

from paper_radar.experiment.root import ExperimentRoot
from paper_radar.feed_pipeline import FeedPipeline
from paper_radar.fixture_audit.acquisition_policy import validate_contact
from paper_radar.runtime_logging import FileSink
from paper_radar.sources.feeds import endpoint


def fetch_feed(
    root: ExperimentRoot, *, request_id: str, contact_email: str
) -> dict[str, Any]:
    root.require()
    validate_contact(contact_email)
    pipeline = FeedPipeline(
        root.database,
        root.data_root,
        sink=FileSink(root.root),
        feed_parser_version=2,
        abstract_rules_version="audit-abstract-v2",
    )
    source = pipeline.papers.register_feed(endpoint("jgr"))
    preparation = pipeline.prepare(
        source.feed_id, request_id=request_id, contact_email=contact_email
    )
    check = pipeline.feed.replay(preparation.check_id)
    basis = check
    # 条件未修改只表示 HTTP 状态;候选成员仍来自可回查的原取得检查。
    seen = {basis.check_id}
    while basis.status_code == 304 and basis.prior_check_id is not None:
        basis = pipeline.feed.replay(basis.prior_check_id)
        if basis.check_id in seen:
            from paper_radar.papers.errors import PaperError, PaperReason

            raise PaperError(PaperReason.CORRUPT_REFERENCE, path="feed_check")
        seen.add(basis.check_id)
    if basis.check_id != check.check_id:
        preparation = pipeline.prepare(
            source.feed_id, request_id=basis.request_id, contact_email=contact_email
        )
    items = []
    for item in preparation.items:
        metadata = item.metadata
        language = (
            pipeline.tasks.record_language_status(item.paper_id)
            if item.paper_id is not None
            else None
        )
        items.append(
            dict(
                position=item.position,
                paper_id=item.paper_id,
                metadata_request_key=item.metadata_request_key,
                conflict_id=item.conflict_id,
                reason=item.reason,
                minimum_complete=metadata.minimum_complete if metadata else False,
                nontruncated_complete=metadata.nontruncated_complete
                if metadata
                else False,
                missing=list(metadata.missing) if metadata else [],
                language=language,
            )
        )
    return dict(
        check_id=check.check_id,
        feed_id=check.feed_id,
        source_check_id=basis.check_id,
        prior_check_id=check.prior_check_id,
        reason=check.reason,
        status_code=check.status_code,
        complete=check.complete,
        outcome="not_modified" if check.status_code == 304 else check.reason,
        parser_identity=check.parser_identity,
        abstract_rules_version="audit-abstract-v2",
        items=items,
        scope="实验 Feed 工程取得；不证明真实来源、选样或模型执行资格",
        next_action=(
            "请按 check_id 回查条目与缺项；未完成请求用同一 request-id 继续，"
            "来源失败不得解释为无新论文。"
        ),
    )
