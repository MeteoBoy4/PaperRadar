"""封闭来源类别表与非依据字段的公共行为向量。"""

from pathlib import Path

import httpx
import pytest

from tests.audit_sampling_support import CODE, SamplingSources, sampling_service


class CategorySources(SamplingSources):
    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode
        if mode == "platform_unknown":
            self.feeds = {
                url: body.replace(b">article</dc:type>", b">unregistered</dc:type>")
                for url, body in self.feeds.items()
            }
        if mode == "no_stable_identifier":
            self.feeds = {
                url: body.replace(
                    b"<link>https://journals.ametsoc.org/view/journals/aies/5/1/synthetic.xml</link>",
                    b"",
                ).replace(
                    b"synthetic identity only",
                    b"10.1175/not-an-identity journal-article",
                )
                for url, body in self.feeds.items()
            }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        response = super().__call__(request)
        path = request.url.path
        if path == "/works/10.1029/jgr.synthetic":
            if self.mode == "non_article":
                return httpx.Response(
                    200,
                    json={
                        "message": {
                            "DOI": "10.1029/jgr.synthetic",
                            "type": "peer-review",
                        }
                    },
                )
            if self.mode == "missing_type":
                return httpx.Response(
                    200, json={"message": {"DOI": "10.1029/jgr.synthetic"}}
                )
        if (
            path == "/doiRA/10.1175/aies.synthetic"
            and self.mode == "og_and_citation_not_type"
        ):
            return httpx.Response(
                200, json=[{"DOI": "10.1175/aies.synthetic", "RA": "ISTIC"}]
            )
        if path == "/doiRA/10.3878/dqkx.synthetic" and self.mode == "category_conflict":
            return httpx.Response(
                200, json=[{"DOI": "10.3878/dqkx.synthetic", "RA": "Crossref"}]
            )
        if path == "/works/10.3878/dqkx.synthetic" and self.mode == "category_conflict":
            return httpx.Response(
                200,
                json={
                    "message": {"DOI": "10.3878/dqkx.synthetic", "type": "component"}
                },
            )
        if path == "/dois/10.1002/qj.synthetic" and self.mode == "datacite_non_article":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": "10.1002/qj.synthetic",
                        "attributes": {
                            "doi": "10.1002/qj.synthetic",
                            "types": {"resourceTypeGeneral": "Text"},
                        },
                    }
                },
            )
        if (
            request.url.host == "www.iapjournals.ac.cn"
            and path.startswith("/dqkx/article/")
            and self.mode == "platform_unknown"
        ):
            return httpx.Response(200, text=response.text.replace("论文", "未登记值"))
        if (
            request.url.host == "www.iapjournals.ac.cn"
            and path.startswith("/dqkx/article/")
            and self.mode == "publisher_type_missing"
        ):
            return httpx.Response(
                200,
                text=response.text.replace('<meta name="dc.type" content="论文">', ""),
            )
        if request.url.host == "journals.ametsoc.org" and path.startswith("/view/"):
            if self.mode == "identity_blocked":
                return httpx.Response(403)
            if self.mode == "identity_absent":
                return httpx.Response(404)
        return response


@pytest.mark.parametrize(
    "mode,journal,result,reason",
    [
        ("non_article", "jgr", "excluded_deterministic", "not_journal_article"),
        ("missing_type", "jgr", "excluded_deterministic", "category_unknown"),
        (
            "og_and_citation_not_type",
            "aies",
            "excluded_deterministic",
            "category_unknown",
        ),
        ("category_conflict", "dqkx", "excluded_deterministic", "category_conflict"),
        (
            "datacite_non_article",
            "qjrms",
            "excluded_deterministic",
            "not_journal_article",
        ),
        ("platform_unknown", "dqkx", "excluded_deterministic", "category_unknown"),
        ("publisher_type_missing", "dqkx", "selected", "selected"),
        (
            "no_stable_identifier",
            "aies",
            "excluded_deterministic",
            "no_stable_identifier",
        ),
        ("identity_blocked", "aies", "blocked_pending", "source_blocked"),
        ("identity_absent", "aies", "excluded_deterministic", "identity_unavailable"),
    ],
)
def test_only_closed_explicit_fields_supply_category_evidence(
    tmp_path: Path, mode: str, journal: str, result: str, reason: str
) -> None:
    sources = CategorySources(mode)
    service = sampling_service(tmp_path, sources)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    view = service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    outcome = next(item for item in view.sampling if item.journal == journal).entries[0]
    assert outcome.result == result
    assert outcome.reason == reason
    if mode == "identity_blocked":
        assert [item.status for item in view.sampling[1:]] == ["complete"] * 3
        assert outcome.routes[0].reason == "access_blocked_403"
    if mode == "publisher_type_missing":
        assert [basis.locator for basis in outcome.category_bases] == ["item/dc:type"]
    service.validate_all()


class NonMappingTypeSources(SamplingSources):
    def __init__(self, types: object) -> None:
        import json

        super().__init__()
        self.registry_raw = json.dumps(
            {
                "data": {
                    "id": "10.1002/qj.synthetic",
                    "attributes": {"doi": "10.1002/qj.synthetic", "types": types},
                }
            },
            separators=(",", ":"),
        ).encode()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.datacite.org":
            self.calls.append(str(request.url))
            return httpx.Response(
                200,
                headers={"Content-Type": "application/json"},
                stream=httpx.ByteStream(self.registry_raw),
            )
        return super().__call__(request)


@pytest.mark.parametrize(
    "types", [None, [], ["JournalArticle"], "JournalArticle", False, 5]
)
def test_non_mapping_type_containers_preserve_source_and_continue_other_journals(
    tmp_path: Path, types: object
) -> None:
    from paper_radar.fixture_audit.acquisition_policy import FEED_ENDPOINTS
    from paper_radar.storage.artifacts import ArtifactStore

    sources = NonMappingTypeSources(types)
    service = sampling_service(tmp_path, sources)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    view = service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    assert [journal.status for journal in view.sampling] == ["complete"] * 4
    qjrms = view.sampling[2]
    assert qjrms.members == ()
    assert qjrms.shortfall == 5
    assert qjrms.entries[0].result == "excluded_deterministic"
    assert qjrms.entries[0].reason == "category_unknown"
    assert qjrms.entries[0].category_bases == ()
    registry = next(
        route for route in view.executions if route.request.route == "registry_datacite"
    )
    assert registry.reason == "acquired"
    assert (
        registry.settlement is not None and registry.settlement.artifact_id is not None
    )
    assert service.data_root is not None
    assert ArtifactStore(service.database, service.data_root).read_artifact(
        registry.settlement.artifact_id
    ) == {"payload": sources.registry_raw}
    assert FEED_ENDPOINTS[3].url in sources.calls
    assert [len(journal.members) for journal in view.sampling] == [1, 1, 0, 1]
    assert service.show_audit(plan.plan_id) == view
    before_calls = tuple(sources.calls)
    assert (
        service.continue_audit_sampling(
            plan.plan_id, contact_email="audit@example.org", code_identity=CODE
        )
        == view
    )
    assert tuple(sources.calls) == before_calls
    service.validate_all()


def test_unknown_type_source_and_selection_restore_without_original_directory(
    tmp_path: Path,
) -> None:
    from paper_radar.backup import create_backup
    from paper_radar.backup.restore import restore_backup
    from paper_radar.fixture_audit import FixtureAudit

    source_root = tmp_path / "source"
    source_root.mkdir()
    service = sampling_service(source_root, NonMappingTypeSources(None))
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    before = service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    assert before.sampling[2].entries[0].reason == "category_unknown"
    assert service.data_root is not None
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    source_root.rename(tmp_path / "source-unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    recovered = FixtureAudit(
        restored.target_dir / "database.sqlite3", restored.target_dir
    )
    assert recovered.show_audit(plan.plan_id) == before
    recovered.validate_all()
