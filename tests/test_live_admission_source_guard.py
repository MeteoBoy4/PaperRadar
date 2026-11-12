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
MANIFEST = ROOT / "tests/fixtures/live-admission-source-guard-v24.json"
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


SOURCE_FILES = (
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
)


# 已审阅版本的清单摘要只追加;后继不得以同一策略键重绑该摘要。
REVIEWED_POLICY_MANIFESTS = {
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
    "version", (6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23)
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
