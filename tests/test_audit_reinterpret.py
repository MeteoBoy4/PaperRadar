"""显式测试解析器只追加新解释和字段差异，不改冻结 v1 结论。"""

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


def test_v2_replay_requires_matching_runtime_and_does_not_confuse_new_fields_with_v1_damage(
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
