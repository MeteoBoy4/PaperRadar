"""#173 完整只读绑定,与 doctor/collector 共用的公共 seam。"""

from pathlib import Path

import pytest

from paper_radar.live_evidence.lifecycle import use_for_id
from paper_radar.live_evidence.types import BindingComponent as B
from paper_radar.pi_execution.current_binding import build_admission_request
from paper_radar.pi_execution.launcher import LaunchIdentity
from paper_radar.pi_execution.service import prepare_call
from paper_radar.pi_supply import activation_history, show_supply
from tests.live_evidence_ledger_support import NOW
from tests.screening_live_admission_support import product_inputs, protected_admission


def test_current_binding_rechecks_local_host_and_stat_baseline_without_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, receipt, credentials = product_inputs(tmp_path / "product", monkeypatch)
    # 此例保留真实本地观察;只替换受保护临时来源。
    from paper_radar.pi_execution.current_binding import local_binding_components

    ledger, _, components = protected_admission(tmp_path / "evidence", monkeypatch)
    monkeypatch.setattr(
        "paper_radar.pi_execution.current_binding.local_binding_components",
        local_binding_components,
    )
    selected = activation_history(service.database)[-1]
    manifest = show_supply(service.database, selected.supply_id).manifest
    identity = LaunchIdentity.for_install(
        selected.supply_id,
        selected.install_id,
        manifest,
        auth_mode="chatgpt_subscription",
    )
    binding = service._binding(
        prepare_call(service.tasks, receipt.receipt_id), identity
    )
    from paper_radar.live_evidence.observation import CurrentObservation
    from paper_radar.live_evidence.receipt import canonical_bytes

    components.update(
        local_binding_components(service.database, binding, credentials_dir=credentials)
    )
    (ledger.root / "inbox/current-observation.json").write_bytes(
        canonical_bytes(
            CurrentObservation(
                observed_at=NOW, binding=components, checked_components=tuple(B)
            )
        )
    )
    before_bytes = service.database.read_bytes()
    before = build_admission_request(
        service.database,
        binding,
        use=use_for_id("boundary-low"),
        credentials_dir=credentials,
        now=NOW,
    )
    assert before.binding.value(B.HOST) != "b" * 64
    assert before.binding.value(B.INSTANCE_TREE) == manifest.expected_tree
    assert before.checked_components == frozenset(B)
    assert not (credentials / "auth-observed.json").exists()
    assert service.database.read_bytes() == before_bytes
    (credentials / "new-cache").write_bytes(b"private-never-read")
    after = build_admission_request(
        service.database,
        binding,
        use=use_for_id("boundary-low"),
        credentials_dir=credentials,
        now=NOW,
    )
    assert after.binding.value(B.AUTH_CACHE_BASELINE) != before.binding.value(
        B.AUTH_CACHE_BASELINE
    )
    assert after.binding.value(B.MODEL_TUPLE) == before.binding.value(B.MODEL_TUPLE)
    # 站点上下文已变时不能把旧观察里的特权组件证明拼到新现场。
    assert B.IPV4_EGRESS not in after.checked_components
    assert B.OBSERVER not in after.checked_components

    from dataclasses import replace

    proxy_changed = build_admission_request(
        service.database,
        replace(binding, proxy="http://127.0.0.1:8080"),
        use=use_for_id("boundary-low"),
        credentials_dir=credentials,
        now=NOW,
    )
    assert proxy_changed.binding.value(B.LAUNCH_POLICY) != before.binding.value(
        B.LAUNCH_POLICY
    )
