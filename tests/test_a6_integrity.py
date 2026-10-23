"""A6 不能由缺执行、伪格式、旧前置或漂移取得通过。"""

from dataclasses import replace
from pathlib import Path

import pytest

from tests.a6_acceptance_support import conclude, rebind, same_a6_run


@pytest.mark.parametrize("predecessor", ["a1", "full", "a3", "a5"])
@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "returned",
        "run",
        "file",
        "scope",
        "issue",
        "bool_format",
        "status",
        "verified",
        "hash",
        "identity",
    ],
)
def test_each_predecessor_requires_independent_same_run_binding(
    tmp_path: Path, predecessor: str, fault: str
) -> None:
    import json

    inputs = same_a6_run(tmp_path)
    offset = {"a1": 1, "full": 3, "a3": 5, "a5": 7}[predecessor]
    path, value = inputs[offset], inputs[offset + 1]
    assert isinstance(path, Path) and isinstance(value, dict)
    expected = "binding_mismatch"
    if fault == "missing":
        path.unlink()
    else:
        key, replacement = {
            "returned": ("private_returned_mismatch", True),
            "run": ("run_id", "historical"),
            "file": ("evidence_file", "historical.json"),
            "scope": ("scope", "historical"),
            "issue": ("issue", 0),
            "bool_format": ("format_version", True),
            "status": ("status", "failed"),
            "verified": (
                {
                    "a1": "a1_verified",
                    "full": "a2_verified",
                    "a3": "a3_verified",
                    "a5": "a5_verified",
                }[predecessor],
                1,
            ),
            "hash": ("evidence_sha256", "0" * 64),
            "identity": ("worktree_sha256", "0" * 64),
        }[fault]
        value[key] = replacement
        if fault != "returned":
            path.write_text(json.dumps(value))
        if fault == "bool_format":
            expected = "format_mismatch"
        elif fault in {"status", "verified"}:
            expected = "prerequisite_not_passed"
        elif fault == "identity":
            expected = "identity_changed"
    _, result = conclude(tmp_path, inputs)
    assert result["status"] == "failed"
    assert result["a6_verified"] is False
    assert expected in {reason["code"] for reason in result["reasons"]}


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "old_run",
        "bool_format",
        "bool_exit",
        "float_exit",
        "incomplete",
        "missing_module",
        "bool_count",
        "negative_count",
        "text_count",
        "float_count",
        "missing_count",
        "skip",
        "deselect",
        "collect_only",
        "modules_not_object",
        "short_execution",
    ],
)
def test_fixed_execution_requires_every_real_integer_count(
    tmp_path: Path, case: str
) -> None:
    import json

    inputs = same_a6_run(tmp_path)
    receipt = inputs[0].with_suffix(".pytest.json")
    raw = json.loads(receipt.read_bytes())
    name = "tests/test_paper_recovery_combined.py"
    module = raw["modules"][name]
    if case == "old_run":
        raw["run_id"] = "historical"
    elif case == "bool_format":
        raw["format_version"] = True
    elif case in {"bool_exit", "float_exit"}:
        raw["exit_code"] = False if case == "bool_exit" else 0.0
    elif case == "incomplete":
        raw["completed"] = False
    elif case == "missing_module":
        raw["modules"].pop(name)
    elif case in {"bool_count", "negative_count", "text_count", "float_count"}:
        module["failed"] = {
            "bool_count": False,
            "negative_count": -1,
            "text_count": "0",
            "float_count": 0.0,
        }[case]
    elif case == "missing_count":
        module.pop("failed")
    elif case == "skip":
        module.update(passed=1, skipped=1)
    elif case == "deselect":
        module.update(collected=1, passed=1, deselected=1)
    elif case == "short_execution":
        module.update(collected=1, passed=1)
    elif case == "collect_only":
        module["passed"] = 0
    elif case == "modules_not_object":
        raw["modules"] = []
    receipt.write_text(json.dumps(raw))
    if case == "missing":
        receipt.unlink()
    rebind(inputs)
    _, result = conclude(tmp_path, inputs)
    assert result["status"] == ("incomplete" if case == "incomplete" else "failed")
    assert result["a6_verified"] is False
    assert (
        "format_mismatch" if case == "bool_format" else "test_execution_not_passed"
    ) in {reason["code"] for reason in result["reasons"]}
    if case == "bool_format":
        assert "format_mismatch" in {reason["code"] for reason in result["reasons"]}


@pytest.mark.parametrize(
    "domain",
    [
        "paper_facts",
        "doi_rules",
        "text_norm",
        "feed_item_fingerprint",
        "reason_catalog",
        "boundary",
        "value",
        "backup",
    ],
)
@pytest.mark.parametrize("version", [2, True, 1.0])
def test_actual_production_versions_cannot_drift_or_disguise_types(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, domain: str, version: object
) -> None:
    from paper_radar.backup import manifest
    from paper_radar.config import StageName
    from paper_radar.papers import doi, errors, feed, models
    from paper_radar.stage_inputs import service

    inputs = same_a6_run(tmp_path)
    if domain in {"boundary", "value"}:
        versions = dict(service.STAGE_INPUT_FORMAT_VERSIONS)
        versions[StageName(domain)] = version  # type: ignore[assignment]
        monkeypatch.setattr(service, "STAGE_INPUT_FORMAT_VERSIONS", versions)
        # 公共只读导出是同一生产权威的别名;版本替换模拟实际升级。
        import paper_radar.stage_inputs as public

        monkeypatch.setattr(public, "STAGE_INPUT_FORMAT_VERSIONS", versions)
    else:
        module, attribute = {
            "paper_facts": (models, "PAPER_FACTS_VERSION"),
            "doi_rules": (doi, "DOI_RULES_VERSION"),
            "text_norm": (models, "TEXT_NORM_VERSION"),
            "feed_item_fingerprint": (feed, "FEED_ITEM_FINGERPRINT_VERSION"),
            "reason_catalog": (errors, "REASON_CATALOG_VERSION"),
            "backup": (manifest, "BACKUP_FORMAT_VERSION"),
        }[domain]
        monkeypatch.setattr(module, attribute, version)
    _, result = conclude(tmp_path, inputs)
    assert result["status"] == "failed"
    assert "paper_fact_format_drift" in {reason["code"] for reason in result["reasons"]}


@pytest.mark.parametrize("case", ["source", "fixture", "support", "baseline"])
def test_fixed_material_and_identity_drift_rejects_previous_success(
    tmp_path: Path, case: str
) -> None:
    from tests.a2_full_support import repository_copy

    root = repository_copy(tmp_path / "repo")
    material = tmp_path / "material"
    material.mkdir()
    inputs = same_a6_run(material, root=root)
    if case == "baseline":
        inputs = (*inputs[:-1], replace(inputs[-1], lockfile_sha256="0" * 64))
    else:
        selected = (
            root
            / {
                "source": "src/paper_radar/papers/feed.py",
                "fixture": "tests/fixtures/paper_facts_v1.json",
                "support": "tests/paper_recovery_reader.py",
            }[case]
        )
        selected.write_bytes(selected.read_bytes() + b"\n")
    _, result = conclude(material, inputs, root=root)
    assert result["status"] == "failed"
    reasons = {reason["code"] for reason in result["reasons"]}
    assert "identity_changed" in reasons
    if case != "baseline":
        assert "scope_drift" in reasons


def test_unknown_real_migration_head_is_not_registered_automatically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    from paper_radar.storage import database

    inputs = same_a6_run(tmp_path)
    migrations = tmp_path / "migrations"
    shutil.copytree(Path(database.__file__).parent / "migrations", migrations)
    (migrations / "versions/unregistered.py").write_text(
        "revision='unregistered'\ndown_revision='a701_screening_registration'\n"
        "def upgrade():pass\ndef downgrade():pass\n"
    )
    monkeypatch.setattr(database, "_MIGRATIONS", migrations)
    _, result = conclude(tmp_path, inputs)
    assert result["migration_revision"] == "unregistered"
    assert result["status"] == "failed"
    assert "migration_unavailable" in {reason["code"] for reason in result["reasons"]}


def test_captured_interrupt_and_existing_conclusion_are_never_passed_or_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.metadata

    inputs = same_a6_run(tmp_path)

    def interrupt(name: str) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(importlib.metadata, "version", interrupt)
    path, result = conclude(tmp_path, inputs)
    assert result["status"] == "incomplete"
    assert result["a6_verified"] is False
    assert "run_incomplete" in {reason["code"] for reason in result["reasons"]}
    old = path.read_bytes()
    with pytest.raises(FileExistsError):
        conclude(tmp_path, inputs)
    assert path.read_bytes() == old


@pytest.mark.parametrize(
    "case",
    ["evidence", "a1", "full", "a3", "a5", "baseline", "scope_a1", "scope_stage"],
)
def test_rebound_boolean_impostors_still_fail(tmp_path: Path, case: str) -> None:
    import json

    inputs = same_a6_run(tmp_path)
    if case == "baseline":
        code = inputs[-1].code.copy()
        code["dirty"] = int(bool(code["dirty"]))  # type: ignore[typeddict-item]
        inputs = (*inputs[:-1], replace(inputs[-1], code=code))
    elif case in {"evidence", "scope_a1", "scope_stage"}:
        raw = json.loads(inputs[0].read_bytes())
        if case == "evidence":
            raw["code"]["dirty"] = int(raw["code"]["dirty"])
        else:
            raw["scope"][
                "full_a1_verified" if case == "scope_a1" else "stage_a_verified"
            ] = 0
        inputs[0].write_text(json.dumps(raw))
    else:
        offset = {"a1": 2, "full": 4, "a3": 6, "a5": 8}[case]
        value = inputs[offset]
        assert isinstance(value, dict)
        value["code"]["dirty"] = int(value["code"]["dirty"])
    rebind(inputs)
    _, result = conclude(tmp_path, inputs)
    assert result["status"] == "failed"
    assert (
        "binding_mismatch" if case.startswith("scope_") else "identity_changed"
    ) in {reason["code"] for reason in result["reasons"]}


def test_missing_dependency_is_controlled_without_raw_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.metadata

    inputs = same_a6_run(tmp_path)
    original = importlib.metadata.version

    def unavailable(name: str) -> str:
        if name == "alembic":
            raise importlib.metadata.PackageNotFoundError("PRIVATE_METADATA")
        return original(name)

    monkeypatch.setattr(importlib.metadata, "version", unavailable)
    path, result = conclude(tmp_path, inputs)
    assert result["status"] == "failed"
    assert "dependency_unavailable" in {reason["code"] for reason in result["reasons"]}
    assert "PRIVATE" not in path.read_text()


@pytest.mark.parametrize(
    "attribute",
    [
        "REQUIRED_TEST_MODULES",
        "REQUIRED_SOURCE_MODULES",
        "REQUIRED_FIXTURE_FILES",
        "REQUIRED_TEST_CASE_COUNTS",
    ],
)
def test_scope_cannot_omit_material_sets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attribute: str
) -> None:
    from scripts import a6_acceptance

    inputs = same_a6_run(tmp_path)
    monkeypatch.setattr(
        a6_acceptance, attribute, {} if attribute.endswith("COUNTS") else ()
    )
    _, result = conclude(tmp_path, inputs)
    assert result["status"] == "failed"
    assert "scope_drift" in {reason["code"] for reason in result["reasons"]}


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "format",
        "incomplete",
        "check_id",
        "skip",
        "bool_exit",
        "completed_impostor",
        "parent",
        "a5_incomplete",
    ],
)
def test_evidence_plan_and_a5_completion_are_required(
    tmp_path: Path, case: str
) -> None:
    import json

    inputs = same_a6_run(tmp_path)
    raw = json.loads(inputs[0].read_bytes())
    expected = "check_not_passed"
    if case == "missing":
        inputs[0].unlink()
        expected = "evidence_unavailable"
    elif case == "format":
        raw["format_version"] = True
        expected = "format_mismatch"
    elif case == "incomplete":
        raw.update(completed=False, overall="incomplete")
        expected = "run_incomplete"
    elif case == "check_id":
        raw["checks"][0]["id"] = "unregistered"
    elif case == "skip":
        raw["checks"][0].update(status="not_run", reason="skipped", exit_code=None)
    elif case == "bool_exit":
        raw["checks"][0]["exit_code"] = False
    elif case == "completed_impostor":
        raw["completed"] = 1
    elif case == "parent":
        inputs[8]["parent_issue"] = 75
        expected = "binding_mismatch"
    elif case == "a5_incomplete":
        inputs[8]["status"] = "incomplete"
        expected = "run_incomplete"
    if case != "missing":
        inputs[0].write_text(json.dumps(raw))
    rebind(inputs)
    _, result = conclude(tmp_path, inputs)
    assert result["status"] == (
        "incomplete" if case in {"incomplete", "a5_incomplete"} else "failed"
    )
    assert expected in {reason["code"] for reason in result["reasons"]}
    assert result["a6_verified"] is False


def test_drifted_capability_material_is_rejected_without_echoing_its_contents(
    tmp_path: Path,
) -> None:
    from tests.a2_full_support import repository_copy

    root = repository_copy(tmp_path / "repo")
    material = tmp_path / "material"
    material.mkdir()
    inputs = same_a6_run(material, root=root)
    (root / "tests/fixtures/a6_capabilities.json").write_text(
        '{"PRIVATE_MAPPING_SENTINEL": "private content"}'
    )
    path, result = conclude(material, inputs, root=root)
    assert result["status"] == "failed"
    assert "scope_drift" in {reason["code"] for reason in result["reasons"]}
    assert "PRIVATE_MAPPING_SENTINEL" not in path.read_text()
    assert result["capability_evidence"] is None
