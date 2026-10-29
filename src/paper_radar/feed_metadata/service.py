"""显式 JGR 元数据补充;网络、材料发布、事实提交均可幂等重放。"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from paper_radar.feed_metadata.models import (
    MetadataContent,
    MetadataMissing,
    MetadataResult,
    MetadataRoute,
    RegistryApplicability,
)
from paper_radar.feed_metadata.repository import (
    canonical,
    corrupt,
    load_routes,
    load_run,
    put_route,
    sha,
    transaction,
)
from paper_radar.feed_metadata.tables import runs
from paper_radar.fixture_audit.abstract_models import (
    ABSTRACT_RULES_VERSION,
    TRUNCATION_RULES_VERSION,
    AbstractCandidate,
    ExcludedBlock,
)
from paper_radar.fixture_audit.abstract_parser import parse_material
from paper_radar.fixture_audit.acquisition_models import Route, SourceRequest
from paper_radar.fixture_audit.acquisition_policy import (
    normalize_request,
    request_url,
    validate_contact,
)
from paper_radar.fixture_audit.sampling_models import CategoryBasis, FeedCandidate
from paper_radar.fixture_audit.sampling_rules import category_bases
from paper_radar.fixture_audit.source_http import (
    SourceHTTPExecutor,
    body_is_contact_free,
)
from paper_radar.fixture_audit.source_validation import inspect_source
from paper_radar.papers import PaperFacts
from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.papers.models import AbstractValue, CandidateInput
from paper_radar.sources.errors import controlled
from paper_radar.storage.artifacts import ArtifactStore


class JGRMetadata:
    def __init__(
        self, database: Path, data_root: Path, *, http: SourceHTTPExecutor | None = None
    ) -> None:
        self.database, self.data_root = database, data_root
        self.http = http or SourceHTTPExecutor()

    @controlled("metadata")
    def enrich(
        self, paper_id: str, *, request_id: str, contact_email: str
    ) -> MetadataResult:
        validate_contact(contact_email)
        if (
            type(request_id) is not str
            or not request_id.strip()
            or len(request_id) > 128
        ):
            raise PaperError(PaperReason.INVALID_OBSERVATION, path="request_id")
        key = sha(canonical([paper_id, request_id]))
        with transaction(self.database, write=True) as connection:
            existing = connection.execute(
                select(runs.c.request_key).where(runs.c.request_key == key)
            ).first()
            if existing is None:
                # 冻结当前版本;后到发现不重绑已登记请求。
                trace = PaperFacts(self.database).trace(paper_id)
                current = trace.current
                from paper_radar.fixture_audit.acquisition_policy import FEED_ENDPOINTS

                endpoint = next(
                    value.url for value in FEED_ENDPOINTS if value.journal == "jgr"
                )
                if not any(
                    value.version_id == current.version_id
                    and value.feed_url == endpoint
                    for value in trace.discoveries
                ):
                    raise PaperError(
                        PaperReason.INVALID_OBSERVATION, path="jgr_discovery"
                    )
                if current.version_kind != "journal":
                    raise PaperError(
                        PaperReason.INVALID_OBSERVATION, path="version_kind"
                    )
                basis = dict(
                    paper_id=paper_id,
                    version_id=current.version_id,
                    doi=current.doi,
                    revision_no=current.revision_no,
                    request_id=request_id,
                    observed_at=datetime.now(UTC).isoformat(),
                )
                payload = canonical(basis)
                connection.execute(
                    runs.insert().values(
                        request_key=key,
                        paper_id=paper_id,
                        request_id=request_id,
                        basis_json=payload,
                        basis_sha256=sha(payload),
                    )
                )
        return self.resume(key, contact_email=contact_email)

    @controlled("metadata")
    def resume(self, request_key: str, *, contact_email: str) -> MetadataResult:
        validate_contact(contact_email)
        with transaction(self.database) as connection:
            basis, settled = load_run(connection, request_key)
        if settled is not None:
            return self.replay(request_key)
        doi = basis["doi"]
        if doi is not None:
            routing = self._route(request_key, basis, "doi_ra", contact_email)
            if (
                routing.agency in {"Crossref", "DataCite"}
                and routing.reason == "acquired"
            ):
                route: Route = (
                    "registry_crossref"
                    if routing.agency == "Crossref"
                    else "registry_datacite"
                )
                self._route(request_key, basis, route, contact_email)
            # Attempt publisher even with a complete Feed or registry abstract.
            self._route(request_key, basis, "publisher", contact_email)
        trace = PaperFacts(self.database).trace(basis["paper_id"])
        version = next(
            value for value in trace.versions if value.version_id == basis["version_id"]
        )
        with transaction(self.database, write=True) as connection:
            connection.execute(
                runs.update()
                .where(runs.c.request_key == request_key, runs.c.revision_no.is_(None))
                .values(revision_no=version.revision_no)
            )
        return self.replay(request_key)

    def _route(
        self, key: str, basis: dict[str, Any], route: Route, contact: str
    ) -> MetadataRoute:
        with transaction(self.database) as connection:
            old = next(
                (
                    value
                    for value in load_routes(connection, key)
                    if value.route == route
                ),
                None,
            )
        if old is None:
            request = normalize_request(
                SourceRequest(journal="jgr", route=route, doi=basis["doi"])
            )
            response = self.http.fetch(request, contact_email=contact)
            reason, agency, artifact_id, payload_hash = (
                response.facts.reason,
                None,
                None,
                None,
            )
            candidates: tuple[AbstractCandidate, ...] = ()
            excluded: tuple[ExcludedBlock, ...] = ()
            categories: tuple[CategoryBasis, ...] = ()
            if reason == "acquired" and response.body is None:
                reason = "invalid_response"
            if (
                reason == "acquired"
                and response.body is not None
                and not body_is_contact_free(
                    response.body, response.facts.decoding, contact
                )
            ):
                reason = "invalid_response"
            if reason == "acquired" and response.body is not None:
                inspection = inspect_source(
                    request, response.body, response.facts.decoding or "utf-8"
                )
                reason, agency = inspection.reason, inspection.agency
                if inspection.retain:
                    try:
                        candidates, excluded, _texts, _recognized = parse_material(
                            request,
                            response.body,
                            decoding=response.facts.decoding or "utf-8",
                            acquisition_id=key + route,
                        )
                        categories = category_bases(
                            "jgr",
                            route,
                            FeedCandidate(
                                position=1,
                                entry_locator="item[1]",
                                order_locator="item[1]",
                            ),
                            raw=response.body,
                            acquisition_id=key + route,
                            decoding=response.facts.decoding or "utf-8",
                        )
                    except (
                        ValueError,
                        TypeError,
                        KeyError,
                        AttributeError,
                        RecursionError,
                    ):
                        candidates, excluded, categories = (), (), ()
                        reason = "invalid_response"
                    # 仅保留主元数据候选的有效来源材料。
                    if candidates:
                        artifact_id = (
                            ArtifactStore(self.database, self.data_root)
                            .publish_single("source_snapshot", (response.body,))
                            .artifact_id
                        )
                        payload_hash = sha(response.body)
            view = MetadataRoute(
                route=route,
                request=request,
                observed_at=basis["observed_at"],
                http=response.facts,
                reason=reason,
                agency=agency,
                artifact_id=artifact_id,
                payload_sha256=payload_hash,
                candidates=candidates,
                excluded_blocks=excluded,
                categories=categories,
                committed=artifact_id is None,
            )
            with transaction(self.database, write=True) as connection:
                put_route(connection, key, view)
                old = next(
                    value
                    for value in load_routes(connection, key)
                    if value.route == route
                )
        if not old.committed:
            assert old.artifact_id and old.http
            raw = ArtifactStore(self.database, self.data_root).read_artifact(
                old.artifact_id
            )["payload"]
            candidates, _excluded, texts, _recognized = parse_material(
                old.request,
                raw,
                decoding=old.http.decoding or "utf-8",
                acquisition_id=key + route,
            )
            fields: dict[str, CandidateInput] = {
                candidate.field: CandidateInput(
                    value=AbstractValue(
                        text=texts[candidate.candidate_id],
                        is_truncated=candidate.suspected_truncated,
                        rule=f"{ABSTRACT_RULES_VERSION}/{TRUNCATION_RULES_VERSION}",
                    )
                    if candidate.field == "abstract"
                    else texts[candidate.candidate_id],
                    locator=candidate.locator,
                )
                for candidate in candidates
            }
            fields["source_url"] = CandidateInput(
                value=request_url(old.request), locator="http/validated_source_url"
            )
            result = PaperFacts(self.database, self.data_root).submit(
                dict(
                    target_paper_id=basis["paper_id"],
                    target_version_id=basis["version_id"],
                    doi=basis["doi"],
                    version_kind="journal",
                    source_kind="publisher" if route == "publisher" else "registry",
                    provider=request_url(old.request)
                    if route == "publisher"
                    else route,
                    query_key=request_url(old.request)
                    if route == "publisher"
                    else basis["doi"],
                    observed_at=datetime.fromisoformat(basis["observed_at"]),
                    parser_version=1,
                    interpretation="complete",
                    payload=raw,
                    fields=fields,
                )
            )
            if result.status == "rejected":
                raise PaperError(
                    result.reason or PaperReason.CORRUPT_REFERENCE,
                    path="metadata_source",
                )
            updated = old.model_copy(
                update={"committed": True, "acquisition_id": result.acquisition_id}
            )
            with transaction(self.database, write=True) as connection:
                # Another worker may already have committed this exact immutable source.
                put_route(connection, key, updated, replace=True)
            old = updated
        return old

    @controlled("metadata")
    def replay(self, request_key: str) -> MetadataResult:
        with transaction(self.database) as connection:
            basis, revision_no = load_run(connection, request_key)
            route_views = load_routes(connection, request_key)
        revision = PaperFacts(self.database).revision(
            basis["version_id"], revision_no or basis["revision_no"]
        )
        if revision.paper_id != basis["paper_id"] or (
            basis["doi"] is not None and revision.doi != basis["doi"]
        ):
            raise corrupt()
        for route in route_views:
            self._verify_route(request_key, basis, route)
            if revision_no is not None and route.acquisition_id is not None:
                trace = PaperFacts(self.database).trace(basis["paper_id"])
                acquisition = next(
                    value
                    for value in trace.acquisitions
                    if value.acquisition_id == route.acquisition_id
                )
                if (
                    acquisition.result_revision_no is not None
                    and acquisition.result_revision_no > revision_no
                ):
                    raise corrupt()
        routing = next(
            (value for value in route_views if value.route == "doi_ra"), None
        )
        applicability: RegistryApplicability = (
            "not_applicable_no_doi"
            if basis["doi"] is None
            else "applicable"
            if routing
            and routing.reason == "acquired"
            and routing.agency in {"Crossref", "DataCite"}
            else "agency_unsupported"
            if routing and routing.reason == "agency_unsupported"
            else "agency_unknown"
        )
        expected = {"doi_ra", "publisher"} if basis["doi"] else set()
        if applicability == "applicable":
            assert routing is not None
            expected.add(
                "registry_crossref"
                if routing.agency == "Crossref"
                else "registry_datacite"
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
        current = PaperFacts(self.database).show(basis["paper_id"])
        current_version = (
            current.version_id == basis["version_id"] and current.doi == basis["doi"]
        )
        missing: list[MetadataMissing] = []
        if not current_version:
            missing.append("current_version_changed")
        if title is None:
            missing.append("no_title")
        if abstract_value is None:
            missing.append("no_abstract")
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
            paper_id=basis["paper_id"],
            version_id=basis["version_id"],
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
            and not abstract_value.is_truncated,
            missing=tuple(missing),
        )

    def _verify_route(
        self, key: str, basis: dict[str, Any], route: MetadataRoute
    ) -> None:
        if route.route not in {
            "doi_ra",
            "publisher",
            "registry_crossref",
            "registry_datacite",
        }:
            raise corrupt()
        if route.request != normalize_request(
            SourceRequest(journal="jgr", route=route.request.route, doi=basis["doi"])
        ):
            raise corrupt()
        if (
            route.request.journal != "jgr"
            or route.request.doi != basis["doi"]
            or route.route != route.request.route
        ):
            raise corrupt()
        if bool(route.artifact_id) != bool(route.candidates) or (
            route.committed and route.artifact_id and route.acquisition_id is None
        ):
            raise corrupt()
        if route.artifact_id:
            raw = ArtifactStore(self.database, self.data_root).read_artifact(
                route.artifact_id
            )["payload"]
            if sha(raw) != route.payload_sha256 or not route.http:
                raise corrupt()
            inspection = inspect_source(
                route.request, raw, route.http.decoding or "utf-8"
            )
            parsed, excluded, _texts, _recognized = parse_material(
                route.request,
                raw,
                decoding=route.http.decoding or "utf-8",
                acquisition_id=key + route.route,
            )
            expected_categories = category_bases(
                "jgr",
                route.request.route,
                FeedCandidate(
                    position=1, entry_locator="item[1]", order_locator="item[1]"
                ),
                raw=raw,
                acquisition_id=key + route.route,
                decoding=route.http.decoding or "utf-8",
            )
            if (
                not inspection.retain
                or parsed != route.candidates
                or excluded != route.excluded_blocks
                or expected_categories != route.categories
            ):
                raise corrupt()
        if route.acquisition_id:
            trace = PaperFacts(self.database).trace(basis["paper_id"])
            found = next(
                (
                    value
                    for value in trace.acquisitions
                    if value.acquisition_id == route.acquisition_id
                ),
                None,
            )
            if (
                found is None
                or found.version_id != basis["version_id"]
                or found.payload_sha256 != route.payload_sha256
            ):
                raise corrupt()

    @controlled("metadata")
    def requests(self, paper_id: str) -> tuple[MetadataResult, ...]:
        with transaction(self.database) as connection:
            keys = (
                connection.execute(
                    select(runs.c.request_key)
                    .where(runs.c.paper_id == paper_id)
                    .order_by(runs.c.request_key)
                )
                .scalars()
                .all()
            )
        return tuple(self.replay(key) for key in keys)

    @controlled("metadata")
    def content(self, request_key: str) -> MetadataContent:
        result = self.replay(request_key)
        revision = PaperFacts(self.database).revision(
            result.version_id, result.revision_no
        )
        abstract = revision.fields.get("abstract")
        value = abstract.value if abstract else None
        return MetadataContent(
            result=result,
            abstract=value.text if isinstance(value, AbstractValue) else None,
            abstract_source_kind=abstract.source_kind if abstract else None,
            abstract_observed_at=abstract.source_observed_at if abstract else None,
            abstract_locator=abstract.locator if abstract else None,
        )

    @controlled("metadata")
    def source_bytes(self, request_key: str, route: str) -> bytes:
        result = self.replay(request_key)
        item = next((value for value in result.routes if value.route == route), None)
        if item is None or item.artifact_id is None:
            raise PaperError(PaperReason.INVALID_OBSERVATION, path="route")
        return ArtifactStore(self.database, self.data_root).read_artifact(
            item.artifact_id
        )["payload"]

    @controlled("metadata")
    def validate_all(self) -> None:
        with transaction(self.database) as connection:
            keys = connection.execute(select(runs.c.request_key)).scalars().all()
        for key in keys:
            self.replay(key)
