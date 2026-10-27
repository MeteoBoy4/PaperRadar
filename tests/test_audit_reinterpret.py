"""显式测试解析器只追加新解释和字段差异,不改冻结 v1 结论。"""

from collections.abc import Mapping
from pathlib import Path

from paper_radar.fixture_audit.acquisition_models import SourceRequest
from tests.audit_matrix_support import MatrixSources
from tests.audit_sampling_support import CODE, sampling_service


class SyntheticV2:
    version = "synthetic-abstract-v2"
    implementation_sha256 = "2" * 64

    def parse(
        self,
        request: SourceRequest,
        raw: bytes,
        *,
        decoding: str,
        entry_locator: str | None,
    ) -> Mapping[str, str | None]:
        return {
            "title": None,
            "abstract": "New v2 primary interpretation.",
            "identity_doi": request.doi,
            "category": "unknown",
        }


def test_new_parser_appends_safe_interpretation_and_preserves_v1_summary(
    tmp_path: Path,
) -> None:
    sources = MatrixSources()
    service = sampling_service(tmp_path, sources)
    original = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    before = service.replay_audit(original.plan.plan_id)
    calls = tuple(sources.calls)
    value = service.reinterpret_audit(
        original.plan.plan_id, parser=SyntheticV2(), request_key="v2-first"
    )
    assert value.parser_version == "synthetic-abstract-v2"
    assert len(value.rows) == 19
    assert any(
        row.removed == ("title",) and "abstract" in row.changed for row in value.rows
    )
    assert "New v2 primary interpretation." not in repr(value)
    assert service.replay_audit(original.plan.plan_id) == before
    assert tuple(sources.calls) == calls
    assert service.list_audit_interpretations(original.plan.plan_id) == (value,)
    assert (
        service.reinterpret_audit(
            original.plan.plan_id, parser=SyntheticV2(), request_key="v2-first"
        )
        == value
    )
    service.validate_all()


def test_v2_replay_requires_runtime_without_treating_new_fields_as_v1_damage(
    tmp_path: Path,
) -> None:
    import pytest

    from paper_radar.fixture_audit import FixtureError

    service = sampling_service(tmp_path, MatrixSources())
    original = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    value = service.reinterpret_audit(
        original.plan.plan_id, parser=SyntheticV2(), request_key="v2"
    )
    with pytest.raises(FixtureError) as missing:
        service.replay_audit_interpretation(
            original.plan.plan_id, value.interpretation_id
        )
    assert missing.value.reason == "unsupported_history"
    result = service.replay_audit_interpretation(
        original.plan.plan_id, value.interpretation_id, parser=SyntheticV2()
    )
    assert (
        result.interpretation == value
        and result.proof_level == "available_material_reparsed"
    )
    assert service.show_audit(original.plan.plan_id) == original


def test_interpretation_chain_differences_compare_previous_interpretation(
    tmp_path: Path,
) -> None:
    class SyntheticV3(SyntheticV2):
        version = "synthetic-abstract-v3"
        implementation_sha256 = "3" * 64

        def parse(
            self,
            request: SourceRequest,
            raw: bytes,
            *,
            decoding: str,
            entry_locator: str | None,
        ) -> Mapping[str, str | None]:
            return {"title": "New v3 title."}

    service = sampling_service(tmp_path, MatrixSources())
    original = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    first = service.reinterpret_audit(
        original.plan.plan_id, parser=SyntheticV2(), request_key="v2"
    )
    second = service.reinterpret_audit(
        original.plan.plan_id, parser=SyntheticV3(), request_key="v3"
    )
    assert second.previous_interpretation_id == first.interpretation_id
    assert any(
        row.added == ("title",) and "abstract" in row.removed for row in second.rows
    )
    assert (
        service.replay_audit_interpretation(
            original.plan.plan_id, second.interpretation_id, parser=SyntheticV3()
        ).interpretation
        == second
    )
    assert service.show_audit(original.plan.plan_id) == original


def test_parser_category_outside_closed_table_is_controlled_and_atomic(
    tmp_path: Path,
) -> None:
    import pytest

    from paper_radar.fixture_audit import FixtureError

    class InvalidCategory(SyntheticV2):
        def parse(
            self,
            request: SourceRequest,
            raw: bytes,
            *,
            decoding: str,
            entry_locator: str | None,
        ) -> Mapping[str, str | None]:
            return {"category": "conference_article"}

    sources = MatrixSources()
    service = sampling_service(tmp_path, sources)
    original = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    calls = tuple(sources.calls)
    with pytest.raises(FixtureError) as rejected:
        service.reinterpret_audit(
            original.plan.plan_id,
            parser=InvalidCategory(),
            request_key="invalid-category",
        )
    assert rejected.value.reason == "invalid_request"
    assert rejected.value.path == "audit.parser_output"
    assert service.list_audit_interpretations(original.plan.plan_id) == ()
    assert service.show_audit(original.plan.plan_id) == original
    assert tuple(sources.calls) == calls
    accepted = service.reinterpret_audit(
        original.plan.plan_id, parser=SyntheticV2(), request_key="invalid-category"
    )
    assert service.list_audit_interpretations(original.plan.plan_id) == (accepted,)
