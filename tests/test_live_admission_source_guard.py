"""D7 开发期冻结源码守卫;不参与运行时准入或既有验收分母。"""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from paper_radar.pi_execution.current_binding import ADMISSION_POLICY_VERSION
from paper_radar.pi_execution.isolation import ISOLATION_POLICY_VERSION
from paper_radar.pi_execution.placement import PLACEMENT_POLICY_VERSION
from paper_radar.pi_execution.resources import LAUNCH_POLICY_VERSION
from paper_radar.pi_protocol import PROTOCOL_PROFILES

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests/fixtures/live-admission-source-guard-v29.json"
ARCHIVED_MANIFEST = ROOT / "tests/fixtures/live-admission-source-guard-v1.json"
# 显式清单;不能由目录扫描或生产依赖图动态扩大/缩小。
ARCHIVED_SOURCE_FILES = (
    "src/paper_radar/pi_execution/admission.py",
    "src/paper_radar/pi_execution/admission_guard.py",
    "src/paper_radar/pi_execution/current_binding.py",
    "src/paper_radar/pi_execution/site_binding.py",
    "src/paper_radar/pi_execution/service.py",
    "src/paper_radar/pi_execution/resources.py",
    "src/paper_radar/pi_execution/launcher.py",
    "src/paper_radar/pi_execution/isolation.py",
    "src/paper_radar/pi_execution/auth.py",
    "src/paper_radar/pi_execution/process.py",
    "src/paper_radar/live_evidence/service.py",
    "src/paper_radar/live_evidence/evaluator.py",
    "src/paper_radar/live_evidence/registry.py",
    "src/paper_radar/live_evidence/observation.py",
    "src/paper_radar/live_evidence/baseline.py",
    "src/paper_radar/live_evidence/time_policy.py",
    "src/paper_radar/live_evidence/ledger.py",
    "src/paper_radar/live_evidence/lifecycle.py",
    "src/paper_radar/live_evidence/evidence.py",
    "src/paper_radar/live_evidence/types.py",
    "src/paper_radar/live_evidence/reasons.py",
    "src/paper_radar/live_evidence/receipt.py",
    "src/paper_radar/live_evidence/tightening.py",
    "src/paper_radar/read_execution/service.py",
    "src/paper_radar/llm/rpc.py",
    "src/paper_radar/llm/rpc_types.py",
    "src/paper_radar/llm/rpc_frames.py",
    "src/paper_radar/llm/rpc_messages.py",
    "src/paper_radar/llm/rpc_pipes.py",
    "src/paper_radar/llm/models.py",
    "src/paper_radar/llm/calls.py",
    "src/paper_radar/llm/__init__.py",
    "src/paper_radar/pi_protocol.py",
)


V25_SOURCE_FILES = (
    *ARCHIVED_SOURCE_FILES,
    "src/paper_radar/live_evidence/intents.py",
    "src/paper_radar/live_evidence/sealed_runtime.py",
    "src/paper_radar/live_evidence/deployment.py",
    "scripts/issue176_closure_workflow.py",
    "scripts/issue176_closure.py",
    "scripts/seal_site_evidence.py",
    "scripts/issue176_resume_after_backup.py",
    "scripts/issue176_resume_after_backup_workflow.py",
    "src/paper_radar/pi_execution/admission_checkpoints.py",
    "src/paper_radar/live_evidence/collector.py",
    "src/paper_radar/live_evidence/site_tree.py",
    "src/paper_radar/live_evidence/cli.py",
    "src/paper_radar/pi_supply/filesystem.py",
    "src/paper_radar/live_evidence/auth_cache_stat.py",
    "src/paper_radar/live_evidence/ledger_errors.py",
    "src/paper_radar/live_evidence/receipt_v2.py",
    "src/paper_radar/live_evidence/collection.py",
    "src/paper_radar/pi_execution/placement.py",
    "src/paper_radar/pi_execution/placement_wrapper.py",
    "src/paper_radar/pi_execution/resolver.py",
    "src/paper_radar/doctor/pi_exec.py",
    "src/paper_radar/doctor/admission.py",
    "src/paper_radar/live_evidence/refresh.py",
    "src/paper_radar/live_evidence/protected_observer.py",
    "src/paper_radar/live_evidence/model_collector.py",
    "src/paper_radar/live_evidence/model_ipc.py",
    "src/paper_radar/live_evidence/model_manifest.py",
    "src/paper_radar/live_evidence/model_worker.py",
    "src/paper_radar/live_evidence/network_collection.py",
    "src/paper_radar/live_evidence/network_probe.py",
    "src/paper_radar/llm/dispatch.py",
    "src/paper_radar/config/service.py",
    "src/paper_radar/live_evidence/live_bundle.py",
    "src/paper_radar/live_evidence/live_bundle_scripts.py",
    "src/paper_radar/live_evidence/live_host.py",
    "src/paper_radar/live_evidence/live_install.py",
    "src/paper_radar/live_evidence/live_materials.py",
    "scripts/seal_live_bundle.py",
    "src/paper_radar/pi_execution/auth_helper.mjs",
    "src/paper_radar/pi_execution/auth_metadata.py",
    "src/paper_radar/live_evidence/normal_auth_refresh.py",
    "src/paper_radar/live_evidence/nft_rules.py",
    "src/paper_radar/live_evidence/nft_generation.py",
    "src/paper_radar/live_evidence/epoch_lineage.py",
    "src/paper_radar/live_evidence/live_apparmor_kernel.py",
    "src/paper_radar/live_evidence/placement_build.py",
    "src/paper_radar/live_evidence/placement_policy.py",
    "src/paper_radar/pi_execution/placement_protocol.py",
    "src/paper_radar/pi_execution/placement_native.c",
    "src/paper_radar/pi_execution/placement_preflight.py",
    "src/paper_radar/live_evidence/preparation_retirement.py",
    "src/paper_radar/live_evidence/preparation_void.py",
    "src/paper_radar/config/owner_waiver.py",
)


# B 的准入、模型选择、外发授权及事务内领取权威;不在运行时扫描依赖。
STAGE_B_SOURCE_FILES = (
    "src/paper_radar/body/__init__.py",
    "src/paper_radar/body/extraction.py",
    "src/paper_radar/body/facts.py",
    "src/paper_radar/body/models.py",
    "src/paper_radar/body/pdf.py",
    "src/paper_radar/body/queries.py",
    "src/paper_radar/body/query_records.py",
    "src/paper_radar/body/read_basis.py",
    "src/paper_radar/body/repository.py",
    "src/paper_radar/body/selection.py",
    "src/paper_radar/body/service.py",
    "src/paper_radar/body/tables.py",
    "src/paper_radar/body/validation.py",
    "src/paper_radar/calibration/__init__.py",
    "src/paper_radar/calibration/visibility.py",
    "src/paper_radar/config/__init__.py",
    "src/paper_radar/config/adapter_loading.py",
    "src/paper_radar/config/adapters.py",
    "src/paper_radar/config/compile.py",
    "src/paper_radar/config/diff.py",
    "src/paper_radar/config/errors.py",
    "src/paper_radar/config/escalation.py",
    "src/paper_radar/config/extraction.py",
    "src/paper_radar/config/extraction_models.py",
    "src/paper_radar/config/extraction_policy.py",
    "src/paper_radar/config/extraction_toolchain.py",
    "src/paper_radar/config/identity.py",
    "src/paper_radar/config/journals.py",
    "src/paper_radar/config/material_assembly.py",
    "src/paper_radar/config/material_names.py",
    "src/paper_radar/config/projections.py",
    "src/paper_radar/config/read.py",
    "src/paper_radar/config/readiness.py",
    "src/paper_radar/config/schema.py",
    "src/paper_radar/config/snapshot_queries.py",
    "src/paper_radar/config/snapshot_summary.py",
    "src/paper_radar/config/topics.py",
    "src/paper_radar/config/yaml_loader.py",
    "src/paper_radar/content_reliability.py",
    "src/paper_radar/contracts/__init__.py",
    "src/paper_radar/contracts/check.py",
    "src/paper_radar/contracts/errors.py",
    "src/paper_radar/contracts/export.py",
    "src/paper_radar/contracts/schema.py",
    "src/paper_radar/contracts/snapshot.py",
    "src/paper_radar/eligibility/__init__.py",
    "src/paper_radar/eligibility/models.py",
    "src/paper_radar/eligibility/rules.py",
    "src/paper_radar/experiment/__init__.py",
    "src/paper_radar/experiment/acceptance.py",
    "src/paper_radar/experiment/body_selection.py",
    "src/paper_radar/experiment/candidates.py",
    "src/paper_radar/experiment/cli.py",
    "src/paper_radar/experiment/egress.py",
    "src/paper_radar/experiment/layout.py",
    "src/paper_radar/experiment/layout_errors.py",
    "src/paper_radar/experiment/layout_models.py",
    "src/paper_radar/experiment/model_mapping.py",
    "src/paper_radar/experiment/pdf.py",
    "src/paper_radar/experiment/preflight.py",
    "src/paper_radar/experiment/reading.py",
    "src/paper_radar/experiment/root.py",
    "src/paper_radar/experiment/screening.py",
    "src/paper_radar/experiment/selections.py",
    "src/paper_radar/feed_metadata/__init__.py",
    "src/paper_radar/feed_metadata/models.py",
    "src/paper_radar/feed_metadata/projection.py",
    "src/paper_radar/feed_metadata/repository.py",
    "src/paper_radar/feed_metadata/service.py",
    "src/paper_radar/feed_metadata/tables.py",
    "src/paper_radar/feed_pipeline/__init__.py",
    "src/paper_radar/feed_pipeline/models.py",
    "src/paper_radar/feed_pipeline/service.py",
    "src/paper_radar/fulltext/__init__.py",
    "src/paper_radar/fulltext/artifacts.py",
    "src/paper_radar/fulltext/execution_audit.py",
    "src/paper_radar/fulltext/models.py",
    "src/paper_radar/fulltext/quality.py",
    "src/paper_radar/llm/read_limits.py",
    "src/paper_radar/papers/__init__.py",
    "src/paper_radar/papers/conflict_tables.py",
    "src/paper_radar/papers/conflicts.py",
    "src/paper_radar/papers/doi.py",
    "src/paper_radar/papers/errors.py",
    "src/paper_radar/papers/fact_reads.py",
    "src/paper_radar/papers/feed.py",
    "src/paper_radar/papers/feed_queries.py",
    "src/paper_radar/papers/mapping.py",
    "src/paper_radar/papers/mapping_models.py",
    "src/paper_radar/papers/models.py",
    "src/paper_radar/papers/queries.py",
    "src/paper_radar/papers/read_checks.py",
    "src/paper_radar/papers/repository.py",
    "src/paper_radar/papers/rules.py",
    "src/paper_radar/papers/selection_repository.py",
    "src/paper_radar/papers/service.py",
    "src/paper_radar/papers/tables.py",
    "src/paper_radar/pi_execution/__init__.py",
    "src/paper_radar/pi_execution/errors.py",
    "src/paper_radar/pi_supply/__init__.py",
    "src/paper_radar/pi_supply/errors.py",
    "src/paper_radar/pi_supply/execution.py",
    "src/paper_radar/pi_supply/materials.py",
    "src/paper_radar/pi_supply/models.py",
    "src/paper_radar/pi_supply/protection.py",
    "src/paper_radar/pi_supply/repository.py",
    "src/paper_radar/pi_supply/selection.py",
    "src/paper_radar/pi_supply/service.py",
    "src/paper_radar/pi_supply/source_policy.py",
    "src/paper_radar/pi_supply/tables.py",
    "src/paper_radar/pi_supply/transport.py",
    "src/paper_radar/read_execution/__init__.py",
    "src/paper_radar/read_inputs/__init__.py",
    "src/paper_radar/read_inputs/budget.py",
    "src/paper_radar/read_inputs/corrections.py",
    "src/paper_radar/read_tasks/__init__.py",
    "src/paper_radar/read_tasks/acceptance.py",
    "src/paper_radar/read_tasks/execution.py",
    "src/paper_radar/read_tasks/models.py",
    "src/paper_radar/read_tasks/pi_rpc.py",
    "src/paper_radar/read_tasks/preconditions.py",
    "src/paper_radar/read_tasks/queries.py",
    "src/paper_radar/read_tasks/repository.py",
    "src/paper_radar/read_tasks/service.py",
    "src/paper_radar/read_tasks/tables.py",
    "src/paper_radar/read_tasks/validation.py",
    "src/paper_radar/reading/__init__.py",
    "src/paper_radar/reading/acceptance_v2/__init__.py",
    "src/paper_radar/reading/context.py",
    "src/paper_radar/reading/diagnostics.py",
    "src/paper_radar/reading/errors.py",
    "src/paper_radar/reading/numbers.py",
    "src/paper_radar/reading/parsing.py",
    "src/paper_radar/reading/result.py",
    "src/paper_radar/reading/schema.py",
    "src/paper_radar/reading/validation.py",
    "src/paper_radar/reading/value_types.py",
    "src/paper_radar/screening/__init__.py",
    "src/paper_radar/screening/context.py",
    "src/paper_radar/screening/errors.py",
    "src/paper_radar/screening/excerpt_kinds.py",
    "src/paper_radar/screening/kinds.py",
    "src/paper_radar/screening/reasons.py",
    "src/paper_radar/screening/schema.py",
    "src/paper_radar/screening/text.py",
    "src/paper_radar/screening/validation.py",
    "src/paper_radar/screening/value_types.py",
    "src/paper_radar/screening_tasks/__init__.py",
    "src/paper_radar/screening_tasks/attempt_integrity.py",
    "src/paper_radar/screening_tasks/attempt_models.py",
    "src/paper_radar/screening_tasks/attempt_repository.py",
    "src/paper_radar/screening_tasks/attempt_rules.py",
    "src/paper_radar/screening_tasks/database_errors.py",
    "src/paper_radar/screening_tasks/errors.py",
    "src/paper_radar/screening_tasks/execution.py",
    "src/paper_radar/screening_tasks/feed_gate.py",
    "src/paper_radar/screening_tasks/frozen.py",
    "src/paper_radar/screening_tasks/integrity.py",
    "src/paper_radar/screening_tasks/language.py",
    "src/paper_radar/screening_tasks/models.py",
    "src/paper_radar/screening_tasks/pi_rpc_audit.py",
    "src/paper_radar/screening_tasks/query.py",
    "src/paper_radar/screening_tasks/query_models.py",
    "src/paper_radar/screening_tasks/repository.py",
    "src/paper_radar/screening_tasks/retry.py",
    "src/paper_radar/screening_tasks/rules.py",
    "src/paper_radar/screening_tasks/service.py",
    "src/paper_radar/screening_tasks/success.py",
    "src/paper_radar/screening_tasks/success_integrity.py",
    "src/paper_radar/screening_tasks/success_models.py",
    "src/paper_radar/screening_tasks/success_references.py",
    "src/paper_radar/screening_tasks/success_rules.py",
    "src/paper_radar/screening_tasks/tables.py",
    "src/paper_radar/stage_inputs/__init__.py",
    "src/paper_radar/stage_inputs/service.py",
    "src/paper_radar/storage/__init__.py",
    "src/paper_radar/storage/artifact_contract.py",
    "src/paper_radar/storage/artifact_repository.py",
    "src/paper_radar/storage/artifacts.py",
    "src/paper_radar/storage/blob_store.py",
    "src/paper_radar/storage/database.py",
    "src/paper_radar/storage/errors.py",
    "src/paper_radar/storage/filesystem.py",
    "src/paper_radar/storage/history.py",
    "src/paper_radar/storage/records.py",
    "src/paper_radar/storage/repository.py",
    "src/paper_radar/storage/schema.py",
    "src/paper_radar/storage/snapshot_queries.py",
)


V28_SOURCE_FILES = (*V25_SOURCE_FILES, *STAGE_B_SOURCE_FILES)
SOURCE_FILES = (*V28_SOURCE_FILES, "src/paper_radar/experiment/reasons.py")


# 已审阅版本的清单摘要只追加;后继不得以同一策略键重绑该摘要。
REVIEWED_POLICY_MANIFESTS = {
    "pi-admission-v29": (
        "5c21855b8ed457148ea1a5005d6c779164e22bc3dc1b3f9ee3aee7e5ad3a4839"
    ),
    "pi-admission-v28": (
        "cd6ad7bb74b954002e40db4d5c6e7bb861f0be7108811b1b3a80607bb89d044e"
    ),
    "pi-admission-v27": (
        "7527179b22cc6020985bedd9f66bbd2893a8d727aaf53ee9e7f5ba249c9396b5"
    ),
    "pi-admission-v26": (
        "d3000d203a1b680c760abc852bfcb915dac40229d1d840242c93f5b0ab8b6ec5"
    ),
    "pi-admission-v25": (
        "93fcd47a3976747601ce8855cf1d53a1df61d6ceb56441d138e62df9e5f0a31b"
    ),
    "pi-admission-v24": (
        "c67dd3ffee26b5b6b71d2d93b03da1835223f31927551302fe5203ce49508015"
    ),
    "pi-admission-v23": (
        "803959899ae38d4d83d70d6f4a56654ee2439180fa50a757b5e167d0d86c0073"
    ),
    "pi-admission-v22": (
        "4987dcdb82bb087f9da2b1358bdefb8a566fe04d4ba0475240e7634bcefb57f1"
    ),
    "pi-admission-v21": (
        "9077b96b324e3f3a90b68741f6ce59184cfadd784c02e23fa3684acb8fccbef5"
    ),
    "pi-admission-v20": (
        "d0638d3fdf1b9c36d7f87fb2ebbfe28c8bb5e18aaec2fc482f1605f354e6cc2e"
    ),
    "pi-admission-v19": (
        "dd418bdaff59b9845be32642daa7afea412569511f5d1b0f6298a1ab9cc449a6"
    ),
    "pi-admission-v18": (
        "c67d0b9b78b450d98a7410d94e25fe9b6f64474896766eeee928e44d25bcdcac"
    ),
    "pi-admission-v17": (
        "08416e02199798eef8406e827c20c894b1c61556e8b131b101c762a3a8b93453"
    ),
    "pi-admission-v16": (
        "f25d67d915172228c310721df0ee22d6bda80497cb41b47f333c1a5a696c315b"
    ),
    "pi-admission-v15": (
        "dce441bec96f6a40bf6f3cd15f108f863d0c9836d219a27ac8478aa6e4224139"
    ),
    "pi-admission-v14": (
        "c98ddf0850df467e0073002c3c29c32d8f9ead8c5aa28996308e9c427b71208b"
    ),
    "pi-admission-v13": (
        "718bf68e838eb75622ceea9f16420ed66aa91cbcd46787266a3b102fa9455424"
    ),
    "pi-admission-v12": (
        "cd2bb0f609180552ad722c5e5f3e9f8f0c76ada71cfd59a218a3e5fa9290cef6"
    ),
    "pi-admission-v11": (
        "b3209a6f797248e9db7d2a4469e62bb31b5aa6d1cfeb82ff320ee6a866987da7"
    ),
    "pi-admission-v10": (
        "0636c8c80653df4c62b40c02d27411a4b48c0371318279b35234141113e61e2d"
    ),
    "pi-admission-v9": (
        "f135a73fa3489a39f05792de3915a4f8f0f4513f8f6902f98c887bc13ae7cc2e"
    ),
    "pi-admission-v8": (
        "ab3beeacbda934f3389639ce220cfd84bfcc6826bb9999eae2e1241a8877316c"
    ),
    "pi-admission-v1": (
        "695c4e9bc933b06bb211663796bb1dd89db52d000881c8590e82ac4e57e1a2f0"
    ),
    "pi-admission-v2": (
        "aa3cb3836b4072a8e6d66b6c99f3181f901f90aa8015e59dc24a3c82d8244ac4"
    ),
    "pi-admission-v3": (
        "78c7e3f27768e138a9137395cefb71cb0058005020cf3a4d1ac4ad9fc5726fc6"
    ),
    "pi-admission-v4": (
        "ff8a37321ea097d9d444d4840212f249431d36d2b364f275f7ca1253db7cefc1"
    ),
    "pi-admission-v5": (
        "5b298801df891e8284def2327e26b9a12c7db9a41554481c387c4ca915d1f03f"
    ),
    "pi-admission-v6": (
        "df039edfb53f85b526c7828984dda44d51c3300a65a07e833b4a4dffc3916223"
    ),
    "pi-admission-v7": (
        "7d5f59efbc2addb76848bbd6cccdbfa6bb6a9a1172a659ba8667bf08d189075e"
    ),
}


def _reviewed_manifest(data: bytes) -> dict[str, Any]:
    assert ADMISSION_POLICY_VERSION in REVIEWED_POLICY_MANIFESTS, (
        "policy_version_unreviewed"
    )
    assert (
        hashlib.sha256(data).hexdigest()
        == REVIEWED_POLICY_MANIFESTS[ADMISSION_POLICY_VERSION]
    ), "policy_version_must_change"
    manifest: dict[str, Any] = json.loads(data)
    return manifest


def _check_sources(root: Path, files: dict[str, str]) -> None:
    for relative in SOURCE_FILES:
        assert (
            hashlib.sha256((root / relative).read_bytes()).hexdigest()
            == files[relative]
        ), relative


def test_admission_sources_match_reviewed_policy_manifest() -> None:
    manifest = _reviewed_manifest(MANIFEST.read_bytes())
    assert manifest["format_version"] == 1
    assert manifest["policies"] == {
        "admission": ADMISSION_POLICY_VERSION,
        "launch": LAUNCH_POLICY_VERSION,
        "placement": PLACEMENT_POLICY_VERSION,
        "isolation": ISOLATION_POLICY_VERSION,
        "protocol_1_4_0": PROTOCOL_PROFILES["1.4.0"],
    }
    assert set(manifest["files"]) == set(SOURCE_FILES)
    _check_sources(ROOT, manifest["files"])


def test_source_edit_with_same_policy_fails_guard(tmp_path: Path) -> None:
    manifest = _reviewed_manifest(MANIFEST.read_bytes())
    for relative in SOURCE_FILES:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    changed = tmp_path / "src/paper_radar/pi_execution/service.py"
    changed.write_bytes(changed.read_bytes() + b"\n# unreviewed edit\n")
    with pytest.raises(AssertionError, match=r"pi_execution/service\.py"):
        _check_sources(tmp_path, manifest["files"])


def test_manifest_rebinding_without_policy_change_fails() -> None:
    manifest = _reviewed_manifest(MANIFEST.read_bytes())
    manifest["files"]["src/paper_radar/pi_execution/service.py"] = "0" * 64
    rebound = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    with pytest.raises(AssertionError, match="policy_version_must_change"):
        _reviewed_manifest(rebound)


def test_previous_policy_manifest_retains_original_bytes() -> None:
    data = ARCHIVED_MANIFEST.read_bytes()
    assert (
        hashlib.sha256(data).hexdigest() == REVIEWED_POLICY_MANIFESTS["pi-admission-v1"]
    )
    manifest = json.loads(data)
    assert manifest["policies"]["admission"] == "pi-admission-v1"
    assert manifest["format_version"] == 1
    assert set(manifest["files"]) == set(ARCHIVED_SOURCE_FILES)


def test_second_policy_manifest_retains_original_bytes() -> None:
    data = (ROOT / "tests/fixtures/live-admission-source-guard-v2.json").read_bytes()
    assert (
        hashlib.sha256(data).hexdigest() == REVIEWED_POLICY_MANIFESTS["pi-admission-v2"]
    )
    assert json.loads(data)["policies"]["admission"] == "pi-admission-v2"


def test_third_policy_manifest_retains_original_bytes() -> None:
    data = (ROOT / "tests/fixtures/live-admission-source-guard-v3.json").read_bytes()
    assert (
        hashlib.sha256(data).hexdigest() == REVIEWED_POLICY_MANIFESTS["pi-admission-v3"]
    )
    manifest = json.loads(data)
    assert manifest["policies"]["admission"] == "pi-admission-v3"
    assert set(manifest["files"]) == set(ARCHIVED_SOURCE_FILES)


def test_fourth_policy_manifest_retains_deployed_bytes() -> None:
    data = (ROOT / "tests/fixtures/live-admission-source-guard-v4.json").read_bytes()
    assert (
        hashlib.sha256(data).hexdigest() == REVIEWED_POLICY_MANIFESTS["pi-admission-v4"]
    )
    assert json.loads(data)["policies"]["admission"] == "pi-admission-v4"


def test_fifth_policy_manifest_retains_original_bytes() -> None:
    data = (ROOT / "tests/fixtures/live-admission-source-guard-v5.json").read_bytes()
    assert (
        hashlib.sha256(data).hexdigest() == REVIEWED_POLICY_MANIFESTS["pi-admission-v5"]
    )
    assert json.loads(data)["policies"]["admission"] == "pi-admission-v5"


@pytest.mark.parametrize(
    "version",
    (
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
        16,
        17,
        18,
        19,
        20,
        21,
        22,
        23,
        24,
        25,
        26,
        27,
    ),
)
def test_later_archived_policy_vectors_keep_original_bytes(version: int) -> None:
    data = (
        ROOT / f"tests/fixtures/live-admission-source-guard-v{version}.json"
    ).read_bytes()
    assert (
        hashlib.sha256(data).hexdigest()
        == REVIEWED_POLICY_MANIFESTS[f"pi-admission-v{version}"]
    )
    assert json.loads(data)["policies"]["admission"] == f"pi-admission-v{version}"
