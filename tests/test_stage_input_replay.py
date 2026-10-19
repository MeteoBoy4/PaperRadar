"""规范载荷回放、固定向量与安全拒绝。均从公共接口观察。"""

import hashlib
import json
from pathlib import Path

import pytest

from paper_radar.config import StageName, compile_config
from paper_radar.stage_inputs import (
    ReplayReason,
    ScreeningFacts,
    StageInputError,
    build_stage_input,
    compare_stage_inputs,
    replay_stage_input,
)
from tests.config_projection_support import full_inputs, new_yaml_version
from tests.config_test_support import boundary_inputs

FIXTURES = Path(__file__).parent / "fixtures/stage_inputs"


def test_boundary_matches_independent_nonempty_literal_vector(tmp_path: Path) -> None:
    settings, database = boundary_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    payload = (FIXTURES / "boundary-v1.json").read_bytes()
    expected = (FIXTURES / "boundary-v1.sha256").read_text().strip()
    assert (
        expected == "e27f19cc566e80158680aecfcf2b3bd41a3cb07201ef6c3a4cec66b4ba11abb2"
    )
    assert hashlib.sha256(payload).hexdigest() == expected
    result = build_stage_input(
        snapshot,
        StageName.BOUNDARY,
        ScreeningFacts(
            title="Synthetic title",
            abstract="Synthetic abstract\n",
            abstract_truncated=False,
        ),
    )
    assert result.payload_bytes == payload
    assert result.fingerprint == expected
    assert replay_stage_input(payload, expected) == result
    assert replay_stage_input(payload, expected, snapshot=snapshot) == result
    assert (
        compare_stage_inputs(result, replay_stage_input(payload, expected)).status
        == "same"
    )


@pytest.mark.parametrize(
    "fingerprint", ["A" * 64, "0x" + "0" * 64, 123, "0" * 63, "secret"]
)
def test_replay_rejects_noncanonical_hash_encoding(fingerprint: object) -> None:
    with pytest.raises(StageInputError) as caught:
        replay_stage_input((FIXTURES / "boundary-v1.json").read_bytes(), fingerprint)  # type: ignore[arg-type]
    assert caught.value.reason is ReplayReason.INVALID_FINGERPRINT
    assert "secret" not in str(caught.value) + repr(caught.value)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"kind": "secret-kind"}, ReplayReason.INVALID_PAYLOAD),
        ({"stage": "read"}, ReplayReason.UNSUPPORTED_STAGE),
        ({"stage": "suggestion"}, ReplayReason.UNSUPPORTED_STAGE),
        ({"stage": {"secret": "secret"}}, ReplayReason.UNSUPPORTED_STAGE),
        ({"format_version": True}, ReplayReason.UNSUPPORTED_FORMAT),
        ({"format_version": 2}, ReplayReason.UNSUPPORTED_FORMAT),
        ({"format_version": 1.0}, ReplayReason.UNSUPPORTED_FORMAT),
        ({"secret-name": "secret-value"}, ReplayReason.INVALID_PAYLOAD),
        ({"facts": {"title": "secret"}}, ReplayReason.INVALID_PAYLOAD),
        (
            {
                "facts": {
                    "title": "secret\ud800",
                    "abstract": "secret",
                    "abstract_truncated": False,
                }
            },
            ReplayReason.INVALID_PAYLOAD,
        ),
        (
            {"config_projection": {"format_version": True, "projection_id": "0" * 64}},
            ReplayReason.PROJECTION_FORMAT_UNVERIFIABLE,
        ),
        (
            {"config_projection": {"format_version": 2, "projection_id": "0" * 64}},
            ReplayReason.PROJECTION_FORMAT_UNVERIFIABLE,
        ),
        (
            {"config_projection": {"format_version": 1, "projection_id": "A" * 64}},
            ReplayReason.INVALID_PAYLOAD,
        ),
        (
            {"config_projection": {"format_version": 1, "projection_id": 123}},
            ReplayReason.INVALID_PAYLOAD,
        ),
    ],
)
def test_replay_rejections_do_not_retain_sensitive_values(
    change: dict[str, object], reason: ReplayReason
) -> None:
    value = json.loads((FIXTURES / "boundary-v1.json").read_bytes())
    value.update(change)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(StageInputError) as caught:
        replay_stage_input(payload, hashlib.sha256(payload).hexdigest())
    assert caught.value.reason is reason
    assert caught.value.__context__ is None
    assert "secret" not in str(caught.value) + repr(caught.value)


@pytest.mark.parametrize(
    "transform",
    [
        lambda b: b + b"\n",
        lambda b: b.replace(b'"kind":', b'"kind": '),
        lambda b: b.replace(
            b'"kind":"stage_input",', b'"kind":"stage_input","kind":"stage_input",'
        ),
    ],
)
def test_replay_rejects_equivalent_but_noncanonical_bytes(transform: object) -> None:
    payload = transform((FIXTURES / "boundary-v1.json").read_bytes())  # type: ignore[operator]
    with pytest.raises(StageInputError) as caught:
        replay_stage_input(payload, hashlib.sha256(payload).hexdigest())
    assert caught.value.reason is ReplayReason.NON_CANONICAL


@pytest.mark.parametrize(
    "payload", [b"secret invalid json", b"\xffsecret", b'{"secret":NaN}', b"[" * 1200]
)
def test_malformed_replay_is_safe(payload: bytes) -> None:
    with pytest.raises(StageInputError) as caught:
        replay_stage_input(payload, hashlib.sha256(payload).hexdigest())
    assert caught.value.reason is ReplayReason.INVALID_PAYLOAD
    assert caught.value.__context__ is None
    assert "secret" not in repr(caught.value) + str(caught.value)


def test_hash_and_explicit_historical_projection_are_verified_separately(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    result = build_stage_input(
        before,
        StageName.BOUNDARY,
        ScreeningFacts(title="T", abstract="A", abstract_truncated=False),
    )
    with pytest.raises(StageInputError) as caught:
        replay_stage_input(result.payload_bytes, "0" * 64)
    assert caught.value.reason is ReplayReason.FINGERPRINT_MISMATCH
    new_yaml_version(settings, "profile", lambda c: c.update(background="changed"))
    after = compile_config(settings, database)
    with pytest.raises(StageInputError) as caught:
        replay_stage_input(result.payload_bytes, result.fingerprint, snapshot=after)
    assert caught.value.reason is ReplayReason.PROJECTION_MISMATCH
    assert (
        replay_stage_input(result.payload_bytes, result.fingerprint, snapshot=before)
        == result
    )


def test_current_projection_format_cannot_impersonate_historical_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.config import projections

    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    result = build_stage_input(
        snapshot,
        StageName.BOUNDARY,
        ScreeningFacts(title="T", abstract="A", abstract_truncated=False),
    )
    monkeypatch.setattr(
        projections, "PROJECTION_FORMAT_VERSIONS", {stage: 2 for stage in StageName}
    )
    with pytest.raises(StageInputError) as caught:
        replay_stage_input(result.payload_bytes, result.fingerprint, snapshot=snapshot)
    assert caught.value.reason is ReplayReason.PROJECTION_FORMAT_UNVERIFIABLE
