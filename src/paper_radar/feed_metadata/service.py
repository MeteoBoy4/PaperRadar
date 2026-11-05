"""显式 JGR 元数据补充;网络、材料发布、事实提交均可幂等重放。"""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Connection, select

from paper_radar.eligibility import MetadataFacts
from paper_radar.feed_metadata.models import (
    MetadataBasis,
    MetadataContent,
    MetadataResult,
    MetadataRoute,
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
    TRUNCATION_RULES_VERSION,
    AbstractCandidate,
    ExcludedBlock,
)
from paper_radar.fixture_audit.abstract_parser import parse_material
from paper_radar.fixture_audit.abstract_versions import (
    ABSTRACT_RULES_VERSION,
    AbstractRulesVersion,
    abstract_parser_version,
    parse_abstract_rules_version,
)
from paper_radar.fixture_audit.acquisition_models import Route, SourceRequest
from paper_radar.fixture_audit.acquisition_policy import (
    normalize_request,
    request_url,
    validate_contact,
)
from paper_radar.fixture_audit.errors import FixtureError
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
from paper_radar.runtime_logging import RuntimeLog, Sink
from paper_radar.runtime_logging.events import Clock, MonotonicClock
from paper_radar.sources.errors import controlled
from paper_radar.sources.feeds import endpoint
from paper_radar.storage.artifacts import ArtifactStore


class JGRMetadata:
    def __init__(
        self,
        database: Path,
        data_root: Path,
        *,
        http: SourceHTTPExecutor | None = None,
        sink: Sink | None = None,
        clock: Clock | None = None,
        monotonic: MonotonicClock | None = None,
    ) -> None:
        self.database, self.data_root = database, data_root
        self.http = http or SourceHTTPExecutor()
        self.log = RuntimeLog(sink, clock=clock, monotonic=monotonic)

    @controlled("metadata")
    def enrich(
        self,
        paper_id: str,
        *,
        request_id: str,
        contact_email: str,
        abstract_rules_version: AbstractRulesVersion | None = None,
    ) -> MetadataResult:
        with self.log.execution(
            "metadata", controlled=(PaperError, FixtureError), paper_id=paper_id
        ):
            return self._enrich(
                paper_id,
                request_id=request_id,
                contact_email=contact_email,
                abstract_rules_version=abstract_rules_version,
            )

    @controlled("metadata")
    def _enrich(
        self,
        paper_id: str,
        *,
        request_id: str,
        contact_email: str,
        abstract_rules_version: AbstractRulesVersion | None = None,
    ) -> MetadataResult:
        validate_contact(contact_email)
        try:
            if abstract_rules_version is not None:
                abstract_rules_version = parse_abstract_rules_version(
                    abstract_rules_version
                )
        except ValueError:
            raise PaperError(
                PaperReason.INVALID_OBSERVATION, path="abstract_rules_version"
            ) from None
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
            if existing is not None:
                saved, _ = load_run(connection, key)
                if (
                    abstract_rules_version is not None
                    and abstract_rules_version != saved.abstract_rules_version
                ):
                    raise PaperError(
                        PaperReason.INVALID_OBSERVATION, path="abstract_rules_version"
                    )
            else:
                # 冻结当前版本;后到发现不重绑已登记请求。
                trace = PaperFacts(self.database).trace(paper_id)
                current = trace.current
                if not any(
                    value.version_id == current.version_id
                    and value.feed_url == endpoint("jgr")
                    for value in trace.discoveries
                ):
                    raise PaperError(
                        PaperReason.INVALID_OBSERVATION, path="jgr_discovery"
                    )
                if current.version_kind != "journal":
                    raise PaperError(
                        PaperReason.INVALID_OBSERVATION, path="version_kind"
                    )
                basis = MetadataBasis(
                    paper_id=paper_id,
                    version_id=current.version_id,
                    doi=current.doi,
                    revision_no=current.revision_no,
                    request_id=request_id,
                    observed_at=datetime.now(UTC).isoformat(),
                    abstract_rules_version=abstract_rules_version
                    or ABSTRACT_RULES_VERSION,
                )
                payload = canonical(basis.model_dump())
                connection.execute(
                    runs.insert().values(
                        request_key=key,
                        paper_id=paper_id,
                        request_id=request_id,
                        basis_json=payload,
                        basis_sha256=sha(payload),
                    )
                )
        return self._resume(key, contact_email=contact_email)

    @controlled("metadata")
    def resume(self, request_key: str, *, contact_email: str) -> MetadataResult:
        with self.log.execution(
            "metadata", controlled=(PaperError, FixtureError), execution_id=request_key
        ):
            return self._resume(request_key, contact_email=contact_email)

    @controlled("metadata")
    def _resume(self, request_key: str, *, contact_email: str) -> MetadataResult:
        validate_contact(contact_email)
        with transaction(self.database) as connection:
            basis, settled = load_run(connection, request_key)
        self.log.bind(execution_id=request_key, paper_id=basis.paper_id)
        if settled is not None:
            return self.replay(request_key)
        doi = basis.doi
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
        trace = PaperFacts(self.database).trace(basis.paper_id)
        version = next(
            value for value in trace.versions if value.version_id == basis.version_id
        )
        with transaction(self.database, write=True) as connection:
            connection.execute(
                runs.update()
                .where(runs.c.request_key == request_key, runs.c.revision_no.is_(None))
                .values(revision_no=version.revision_no)
            )
        return self.replay(request_key)

    def _route(
        self, key: str, basis: MetadataBasis, route: Route, contact: str
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
        settling = old is None or not old.committed
        if old is None:
            request = normalize_request(
                SourceRequest(journal="jgr", route=route, doi=basis.doi)
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
                            rules_version=basis.abstract_rules_version,
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
                abstract_rules_version=basis.abstract_rules_version,
                request=request,
                observed_at=basis.observed_at,
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
                rules_version=old.abstract_rules_version,
            )
            fields: dict[str, CandidateInput] = {
                candidate.field: CandidateInput(
                    value=AbstractValue(
                        text=texts[candidate.candidate_id],
                        is_truncated=candidate.suspected_truncated,
                        rule=f"{old.abstract_rules_version}/{TRUNCATION_RULES_VERSION}",
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
                    target_paper_id=basis.paper_id,
                    target_version_id=basis.version_id,
                    doi=basis.doi,
                    version_kind="journal",
                    source_kind="publisher" if route == "publisher" else "registry",
                    provider=request_url(old.request)
                    if route == "publisher"
                    else route,
                    query_key=request_url(old.request)
                    if route == "publisher"
                    else basis.doi,
                    observed_at=datetime.fromisoformat(basis.observed_at),
                    parser_version=abstract_parser_version(old.abstract_rules_version),
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
        if settling:
            self.log.emit("route_settled", route=route, category=old.reason)
        return old

    @controlled("metadata")
    def replay(self, request_key: str) -> MetadataResult:
        with transaction(self.database) as connection:
            basis, revision_no = load_run(connection, request_key)
            route_views = load_routes(connection, request_key)
        revision = PaperFacts(self.database).revision(
            basis.version_id, revision_no or basis.revision_no
        )
        if revision.paper_id != basis.paper_id or (
            basis.doi is not None and revision.doi != basis.doi
        ):
            raise corrupt()
        for route in route_views:
            self._verify_route(request_key, basis, route)
            if revision_no is not None and route.acquisition_id is not None:
                trace = PaperFacts(self.database).trace(basis.paper_id)
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
        from paper_radar.feed_metadata.projection import project_metadata

        return project_metadata(
            request_key,
            basis,
            revision,
            PaperFacts(self.database).show(basis.paper_id),
            route_views,
            revision_no,
        )

    def result_in_connection(
        self, connection: Connection, paper_id: str
    ) -> MetadataResult | None:
        """同Connection读取真实路线完成及当前字段,缺失返回None,不创建事实。"""
        from paper_radar.feed_metadata.projection import project_metadata
        from paper_radar.papers.queries import load_trace, resolve_revision

        trace = load_trace(connection, paper_id)
        candidates = []
        for key in connection.execute(
            select(runs.c.request_key).where(runs.c.paper_id == paper_id)
        ).scalars():
            basis, settled_revision = load_run(connection, key)
            routes = load_routes(connection, key)
            revision = (
                trace.current
                if basis.version_id == trace.current.version_id
                else resolve_revision(
                    connection,
                    version_id=basis.version_id,
                    revision_no=settled_revision or basis.revision_no,
                )
            )
            for route in routes:
                if (
                    route.request.doi != basis.doi
                    or route.abstract_rules_version != basis.abstract_rules_version
                ):
                    raise corrupt()
                if route.acquisition_id:
                    acquisition = next(
                        (
                            v
                            for v in trace.acquisitions
                            if v.acquisition_id == route.acquisition_id
                        ),
                        None,
                    )
                    if (
                        acquisition is None
                        or acquisition.version_id != basis.version_id
                        or acquisition.payload_sha256 != route.payload_sha256
                    ):
                        raise corrupt()
            result = project_metadata(
                key, basis, revision, trace.current, routes, settled_revision
            )
            candidates.append(
                (
                    basis.version_id == trace.current.version_id,
                    basis.observed_at,
                    key,
                    result,
                )
            )
        if not candidates:
            return None
        return max(candidates, key=lambda v: v[:3])[3]

    def facts_in_connection(
        self, connection: Connection, paper_id: str
    ) -> MetadataFacts | None:
        result = self.result_in_connection(connection, paper_id)
        return MetadataFacts.from_result(result) if result is not None else None

    def historical_result_in_connection(
        self,
        connection: Connection,
        paper_id: str,
        request_key: str,
        version_id: str,
        revision_no: int,
    ) -> MetadataResult:
        """重放明确历史修订的最低元数据依据,不以当前版本/新路线替换。"""
        from paper_radar.feed_metadata.projection import project_metadata
        from paper_radar.papers.queries import load_trace, resolve_revision

        basis, settled = load_run(connection, request_key)
        if basis.paper_id != paper_id or basis.version_id != version_id:
            raise corrupt()
        revision = resolve_revision(
            connection, version_id=version_id, revision_no=revision_no
        )
        if revision.paper_id != paper_id or revision.doi != basis.doi:
            raise corrupt()
        routes = load_routes(connection, request_key)
        trace = load_trace(connection, paper_id)
        for route in routes:
            if (
                route.request.doi != basis.doi
                or route.abstract_rules_version != basis.abstract_rules_version
            ):
                raise corrupt()
            if route.acquisition_id:
                acquisition = next(
                    (
                        a
                        for a in trace.acquisitions
                        if a.acquisition_id == route.acquisition_id
                    ),
                    None,
                )
                if (
                    acquisition is None
                    or acquisition.version_id != version_id
                    or acquisition.payload_sha256 != route.payload_sha256
                ):
                    raise corrupt()
        return project_metadata(request_key, basis, revision, revision, routes, settled)

    def _verify_route(
        self, key: str, basis: MetadataBasis, route: MetadataRoute
    ) -> None:
        if route.abstract_rules_version != basis.abstract_rules_version:
            raise corrupt()
        if route.route not in {
            "doi_ra",
            "publisher",
            "registry_crossref",
            "registry_datacite",
        }:
            raise corrupt()
        if route.request != normalize_request(
            SourceRequest(journal="jgr", route=route.request.route, doi=basis.doi)
        ):
            raise corrupt()
        if (
            route.request.journal != "jgr"
            or route.request.doi != basis.doi
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
                rules_version=route.abstract_rules_version,
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
            trace = PaperFacts(self.database).trace(basis.paper_id)
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
                or found.version_id != basis.version_id
                or found.payload_sha256 != route.payload_sha256
                or found.parser_version
                != abstract_parser_version(route.abstract_rules_version)
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
    def source_bytes(self, request_key: str, route: Route) -> bytes:
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
