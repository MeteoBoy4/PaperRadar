"""封闭论文事实输入与安全输出。"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from paper_radar.papers import AbstractValue, PaperFacts, PaperReason
from paper_radar.papers.errors import GUIDANCE
from paper_radar.storage.database import upgrade_database
from tests.test_paper_service import observation


@pytest.fixture
def facts(tmp_path: Path) -> PaperFacts:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    return PaperFacts(database, tmp_path / "data")


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"scheme": "pmid"}, "unsupported_scheme"),
        ({"source_kind": "feed"}, "unsupported_source"),
        ({"source_kind": "manual"}, "unsupported_source"),
        ({"source_kind": "registry"}, "unsupported_source"),
        ({"relations": ({"type": "is-preprint-of"},)}, "unsupported_relation"),
        (
            {"fields": {"orcid": {"value": "SECRET", "locator": "id"}}},
            "unsupported_field",
        ),
        (
            {"fields": {"abstract_source": {"value": "SECRET", "locator": "source"}}},
            "unsupported_field",
        ),
        ({"http_status": 200}, "invalid_observation"),
        ({"artifact_id": "SECRET"}, "invalid_observation"),
        ({"payload": b""}, "invalid_observation"),
        ({"payload": b"x" * (8 * 1024 * 1024 + 1)}, "invalid_observation"),
        ({"payload": bytearray(b"SECRET")}, "invalid_observation"),
        ({"parser_version": True}, "invalid_observation"),
        ({"parser_version": 0}, "invalid_observation"),
        ({"observed_at": datetime(2026, 1, 1)}, "invalid_observation"),
        (
            {"observed_at": datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=8)))},
            "invalid_observation",
        ),
        ({"target_paper_id": "SECRET"}, "invalid_observation"),
        (
            {"fields": {"title": {"value": 7, "locator": "title"}}},
            "invalid_observation",
        ),
        (
            {"fields": {"title": {"value": "SECRET\ud800", "locator": "title"}}},
            "invalid_text",
        ),
        (
            {"fields": {"title": {"value": "<p>SECRET</p>", "locator": "title"}}},
            "invalid_text",
        ),
        (
            {"fields": {"title": {"value": "<!-- SECRET -->", "locator": "title"}}},
            "invalid_text",
        ),
        (
            {"fields": {"title": {"value": "SECRET", "locator": ""}}},
            "invalid_observation",
        ),
        (
            {
                "fields": {
                    "online_date": {
                        "value": {"value": "2026-02-30", "precision": "day"},
                        "locator": "date",
                    }
                }
            },
            "invalid_observation",
        ),
        (
            {"fields": {"volume": {"value": 42, "locator": "volume"}}},
            "invalid_observation",
        ),
    ],
)
def test_invalid_observation_has_controlled_reason_and_no_original_text(
    facts: PaperFacts, changes: dict[str, object], reason: str
) -> None:
    result = facts.submit(observation(**changes))
    assert (result.status, result.reason) == ("rejected", reason)
    assert "SECRET" not in repr(result)


def test_fields_preserve_structure_and_raw_source(facts: PaperFacts) -> None:
    result = facts.submit(
        observation(
            fields={
                "title": {
                    "value": "\u3000a < b\r\nx > 0\t\n\n\nZ\u3000",
                    "locator": "title",
                },
                "abstract": {
                    "value": {
                        "text": " No abstract available\r ",
                        "is_truncated": None,
                        "rule": "adapter-v1",
                    },
                    "locator": "abstract",
                },
                "authors": {"value": (" A\rB ", "作者"), "locator": "authors"},
                "volume": {"value": "007", "locator": "volume"},
                "issue": {"value": "S1", "locator": "issue"},
                "pages": {"value": "e00001", "locator": "pages"},
                "online_date": {
                    "value": {"value": "2026-01", "precision": "month"},
                    "locator": "online",
                },
                "print_date": {
                    "value": {"value": "2027", "precision": "year"},
                    "locator": "print",
                },
                "source_url": {
                    "value": "https://publisher.example/article",
                    "locator": "url",
                },
            }
        )
    )
    assert result.paper_id is not None
    fields = facts.show(result.paper_id).fields
    assert fields["title"].value == "a < b\nx > 0\t\n\n\nZ"
    assert fields["authors"].value == ("A\nB", "作者")
    abstract = fields["abstract"].value
    assert isinstance(abstract, AbstractValue)
    assert (abstract.text, abstract.is_truncated) == ("No abstract available", None)
    assert fields["volume"].value == "007"
    assert fields["title"].text_norm == 1


def test_reason_catalog_and_guidance_are_complete_and_private() -> None:
    contract = Path("docs/contracts/paper-facts.md").read_text()
    assert set(GUIDANCE) == set(PaperReason)
    assert all(
        f"`{reason.value}`" in contract and guidance in contract
        for reason, guidance in GUIDANCE.items()
    )


def test_fact_repr_does_not_expose_text(facts: PaperFacts) -> None:
    result = facts.submit(
        observation(
            fields={
                "abstract": {
                    "value": {
                        "text": "SECRET-ABSTRACT",
                        "is_truncated": False,
                        "rule": "fixture",
                    },
                    "locator": "abstract",
                }
            }
        )
    )
    assert result.paper_id
    trace = facts.trace(result.paper_id)
    assert "SECRET" not in repr(trace)
    assert "SECRET" not in str(trace.current.fields["abstract"])
    assert "SECRET" not in repr(
        AbstractValue(text="SECRET", is_truncated=False, rule="fixture")
    )


def test_public_typed_input_failure_has_no_pydantic_input_payload() -> None:
    from paper_radar.papers import PaperError

    with pytest.raises(PaperError, match="invalid_observation") as failure:
        AbstractValue.model_validate(
            {"text": {"SECRET": "PRIVATE"}, "is_truncated": False, "rule": "fixture"}
        )
    assert "SECRET" not in str(failure.value) + repr(failure.value)
    assert not hasattr(failure.value, "errors")


@pytest.mark.parametrize(
    "vector", json.loads(Path("tests/fixtures/paper_facts_v1.json").read_text())["text"]
)
def test_text_fixed_vector_at_service_boundary(
    facts: PaperFacts, vector: dict[str, str]
) -> None:
    result = facts.submit(
        observation(fields={"title": {"value": vector["raw"], "locator": "title"}})
    )
    if "reason" in vector:
        assert result.reason == vector["reason"]
    else:
        assert result.paper_id
        assert facts.show(result.paper_id).fields["title"].value == vector["expected"]


def test_service_revalidates_typed_input_after_caller_changes_nested_fields(
    facts: PaperFacts,
) -> None:
    from paper_radar.papers import CandidateInput, ObservationInput

    item = ObservationInput.model_validate(observation())
    item.fields["authors"] = CandidateInput.model_construct(
        value=(17,), locator="authors"
    )
    result = facts.submit(item)
    assert (result.status, result.reason) == ("rejected", "invalid_observation")


def test_blank_source_url_is_missing_and_does_not_overwrite_existing_fact(
    facts: PaperFacts,
) -> None:
    from datetime import UTC

    first = facts.submit(
        observation(
            fields={
                "source_url": {
                    "value": "https://publisher.example/paper",
                    "locator": "url",
                }
            }
        )
    )
    assert first.paper_id
    no_contribution = facts.submit(
        observation(
            payload=b"blank url",
            observed_at=datetime(2026, 2, 1, tzinfo=UTC),
            fields={"source_url": {"value": " \r\n\u3000", "locator": "url"}},
        )
    )
    assert (no_contribution.status, no_contribution.reason) == (
        "not_retained",
        "not_retained",
    )
    assert (
        facts.show(first.paper_id).fields["source_url"].value
        == "https://publisher.example/paper"
    )


@pytest.mark.parametrize("location", ["source_url", "query_key", "provider", "locator"])
@pytest.mark.parametrize(
    "url",
    [
        "https://user:SECRET@publisher.example/paper",
        "https://publisher.example/paper?token=SECRET",
        "https://publisher.example/paper#SECRET",
    ],
)
def test_authenticated_or_parameterized_urls_cannot_enter_query_output(
    facts: PaperFacts, location: str, url: str
) -> None:
    changes: dict[str, object]
    if location in {"provider", "query_key"}:
        changes = {location: url}
    elif location == "locator":
        changes = {"fields": {"title": {"value": "Title", "locator": url}}}
    else:
        changes = {"fields": {"source_url": {"value": url, "locator": "source"}}}
    result = facts.submit(observation(**changes))
    assert (result.status, result.reason) == ("rejected", "invalid_observation")
    assert "SECRET" not in repr(result)


@pytest.mark.parametrize("size", [1, 8 * 1024 * 1024])
def test_raw_source_accepts_both_inclusive_size_boundaries(
    facts: PaperFacts, size: int
) -> None:
    from paper_radar.storage.artifacts import ArtifactStore

    payload = b"x" * size
    result = facts.submit(observation(payload=payload))
    assert result.status == "retained" and result.paper_id
    trace = facts.trace(result.paper_id, verify_source_bytes=True)
    assert facts.data_root is not None
    assert (
        ArtifactStore(facts.database, facts.data_root).read_artifact(
            trace.observations[0].artifact_id
        )["payload"]
        == payload
    )
