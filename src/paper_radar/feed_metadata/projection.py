"""持久元数据路线与明确论文修订的纯投影;不把字段存在当路线完成。"""

from paper_radar.feed_metadata.models import (
    MetadataBasis,
    MetadataMissing,
    MetadataResult,
    MetadataRoute,
    RegistryApplicability,
)
from paper_radar.feed_metadata.repository import corrupt
from paper_radar.papers.models import AbstractValue, PaperView, RevisionView


def project_metadata(
    request_key: str,
    basis: MetadataBasis,
    revision: PaperView | RevisionView,
    current: PaperView | RevisionView,
    route_views: tuple[MetadataRoute, ...],
    revision_no: int | None,
) -> MetadataResult:
    routing = next((value for value in route_views if value.route == "doi_ra"), None)
    applicability: RegistryApplicability = (
        "not_applicable_no_doi"
        if basis.doi is None
        else "applicable"
        if routing
        and routing.reason == "acquired"
        and routing.agency in {"Crossref", "DataCite"}
        else "agency_unsupported"
        if routing and routing.reason == "agency_unsupported"
        else "agency_unknown"
    )
    expected = {"doi_ra", "publisher"} if basis.doi else set()
    if applicability == "applicable":
        assert routing is not None
        expected.add(
            "registry_crossref" if routing.agency == "Crossref" else "registry_datacite"
        )
    if revision_no is not None and (
        expected != {value.route for value in route_views}
        or not all(value.committed for value in route_views)
    ):
        raise corrupt()
    routes_settled = (
        revision_no is not None
        and expected == {value.route for value in route_views}
        and all(value.committed for value in route_views)
    )
    fields = revision.fields
    title = fields.get("title")
    abstract = fields.get("abstract")
    url = fields.get("source_url")
    abstract_value = (
        abstract.value
        if abstract and isinstance(abstract.value, AbstractValue)
        else None
    )
    current_version = (
        current.version_id == basis.version_id and current.doi == basis.doi
    )
    missing: list[MetadataMissing] = []
    if not current_version:
        missing.append("current_version_changed")
    if title is None:
        missing.append("no_title")
    if abstract_value is None:
        missing.append("no_abstract")
    elif abstract_value.is_truncated is None:
        missing.append("unknown_truncation")
    if url is None:
        missing.append("no_source_url")
    if not routes_settled:
        missing.append("routes_incomplete")
    if applicability == "agency_unknown":
        missing.append("agency_unknown")
    elif applicability == "agency_unsupported":
        missing.append("agency_unsupported")
    return MetadataResult(
        request_key=request_key,
        paper_id=basis.paper_id,
        version_id=basis.version_id,
        revision_no=revision.revision_no,
        title=title.value if title and isinstance(title.value, str) else None,
        abstract_present=abstract_value is not None,
        suspected_truncated=abstract_value.is_truncated if abstract_value else None,
        source_url=url.value if url and isinstance(url.value, str) else None,
        current_version=current_version,
        routes=route_views,
        routes_settled=routes_settled,
        registry_applicability=applicability,
        minimum_complete=not missing,
        nontruncated_complete=not missing
        and abstract_value is not None
        and abstract_value.is_truncated is False,
        missing=tuple(missing),
    )
