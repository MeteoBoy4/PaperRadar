"""D1: 正式准入和只读站点观察的 metadata 故障与材料身份边界。"""

import errno
import os
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from paper_radar.live_evidence import auth_cache_stat, sealed_runtime
from paper_radar.live_evidence.collector import SiteObservation
from paper_radar.live_evidence.ledger import LedgerError
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from paper_radar.live_evidence.types import BindingComponent as B
from paper_radar.pi_execution import current_binding
from paper_radar.pi_execution.admission import EvidenceBinding, bind_description
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.isolation import ISOLATION_POLICY_VERSION
from paper_radar.pi_execution.resources import (
    LAUNCH_POLICY_VERSION,
    expected_cwd_section,
)
from paper_radar.pi_execution.service import PiExecution, prepare_call
from paper_radar.pi_execution.site_binding import site_binding_components
from paper_radar.pi_supply import activate_supply, activation_history
from paper_radar.read_execution import ReadExecution
from tests.live_evidence_ledger_support import NOW
from tests.screening_live_admission_support import product_inputs, protected_admission


def material_site(
    root: Path, monkeypatch: pytest.MonkeyPatch, *, consumer: str = "screening"
) -> tuple[PiExecution | ReadExecution, str, Path, SiteConfiguration]:
    product: PiExecution | ReadExecution
    if consumer == "screening":
        product, task, credentials = product_inputs(root, monkeypatch)
        identifier = task.receipt_id
        description = prepare_call(product.tasks, identifier)
    else:
        from tests.read_execution_support import setup

        product, read_task, credentials = setup(root, monkeypatch)
        identifier = read_task.task_id
        description = product.tasks.prepare_execution(identifier).description
    selected = activation_history(product.database)[-1]
    binding = bind_description(
        description,
        supply_id=selected.supply_id,
        install_id=selected.install_id,
        launch_policy_version=LAUNCH_POLICY_VERSION,
        isolation_policy_version=ISOLATION_POLICY_VERSION,
        cwd_section=expected_cwd_section(),
        auth_mode="chatgpt_subscription",
    )
    site = SiteConfiguration(
        product_uid=os.getuid(),
        product_gid=os.getgid(),
        database=product.database,
        snapshot_id=selected.snapshot_id,
        install_path=product.roots.install_root
        / selected.supply_id
        / selected.install_id,
        credentials_dir=credentials,
        roots=product.roots,
        binding=binding,
        use_id="boundary-low",
    )
    # 合成 cwd 的祖先包含 SQLite 目录;冻结该 OS fixture,使其 journal 不冒充执行漂移。
    host = site_binding_components()
    monkeypatch.setattr(current_binding, "site_binding_components", lambda: host.copy())
    return product, identifier, credentials, site


@pytest.mark.parametrize("consumer", ["screening", "read"])
@pytest.mark.parametrize("operation", ["open", "lstat"])
def test_formal_temporary_metadata_io_preserves_snapshot_claims_and_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consumer: str, operation: str
) -> None:
    from paper_radar.live_evidence import service as evidence

    product, identifier, credentials, site = material_site(
        tmp_path / "product", monkeypatch, consumer=consumer
    )
    local = current_binding.local_binding_components
    components = local(product.database, site.binding, credentials_dir=credentials)
    components.update({B.OBSERVER: "a" * 64, B.IPV4_EGRESS: "b" * 64})
    ledger, original, _ = protected_admission(
        tmp_path / "evidence",
        monkeypatch,
        components=components,
        uses=("boundary-low", "read-low"),
    )
    monkeypatch.setattr(current_binding, "local_binding_components", local)
    product._now = lambda: NOW
    source = ledger.root / "inbox/current-observation.json"
    snapshot = source.read_bytes()
    before = (
        product.tasks.status(identifier)
        if isinstance(product, PiExecution)
        else product.tasks.task(identifier)
    )
    events = ledger.audit()
    actual_open = os.open
    actual_lstat = os.lstat

    def temporary_open(
        path: str | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if path == credentials and operation == "open":
            raise OSError(errno.EIO, "synthetic_metadata_io")
        return actual_open(path, flags, mode, dir_fd=dir_fd)

    def temporary_lstat(
        path: str | os.PathLike[str], *, dir_fd: int | None = None
    ) -> os.stat_result:
        if path == credentials and operation == "lstat":
            raise OSError(errno.EIO, "synthetic_metadata_io")
        return actual_lstat(path, dir_fd=dir_fd)

    def unavailable() -> None:
        raise LedgerError("observation_unavailable")

    monkeypatch.setattr(os, "open", temporary_open)
    monkeypatch.setattr(os, "lstat", temporary_lstat)
    monkeypatch.setattr(
        "paper_radar.pi_execution.admission_checkpoints.request_observation_refresh",
        unavailable,
    )
    with pytest.raises(ExecutionError, match=r"^evidence_missing$"):
        product.run_attempt(identifier)
    assert source.read_bytes() == snapshot
    assert ledger.audit() == events and evidence._read_pending() == ()
    after = (
        product.tasks.status(identifier)
        if isinstance(product, PiExecution)
        else product.tasks.task(identifier)
    )
    assert after == before
    assert ledger.show(original.receipt_id).receipt == original
    assert not (credentials / "auth-observed.json").exists()
    from paper_radar.doctor.admission import render_admission_fragment
    from paper_radar.live_evidence.lifecycle import use_for_id

    diagnostic = current_binding.diagnose_observation_failure(
        product.database,
        site.binding,
        use=use_for_id("read-low" if consumer == "read" else "boundary-low"),
        credentials_dir=credentials,
        now=NOW,
        error=LedgerError("observation_unavailable"),
    )
    text = render_admission_fragment(diagnostic)
    assert "original_state=verified" in text
    assert f"verified_at={NOW.isoformat()}" in text
    assert f"observed_at={NOW.isoformat()}" in text
    assert "reason=observation_unavailable" in text


def test_metadata_only_accepts_new_material_snapshot_with_same_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.config import compile_config

    product, _, credentials, site = material_site(tmp_path, monkeypatch)
    before = sealed_runtime.observe_site(site, metadata_only=True)
    assert before.checks == (("metadata", True),)
    newer = compile_config(tmp_path / "config/settings.yaml", product.database)
    assert newer.snapshot_id != site.snapshot_id
    selected = activate_supply(
        product.database, site.binding.supply_id, newer.snapshot_id
    )
    assert selected.install_id == site.binding.install_id
    assert (
        current_binding.local_binding_components(
            product.database, site.binding, credentials_dir=credentials
        )
        == before.components
    )
    observed = sealed_runtime.observe_site(site, metadata_only=True)
    assert observed.checks == (("metadata", True),)
    assert observed.components == before.components
    # 初次 beta 仍严格钉住封印选择三元组。
    assert sealed_runtime.observe_site(site).checks == (("metadata", False),)
    assert sealed_runtime.observe_site(
        site, metadata_only=True, require_snapshot=True
    ).checks == (("metadata", False),)


def test_unstable_metadata_sample_is_temporary_and_has_no_new_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "credentials"
    root.mkdir()
    member = root / "auth.json"
    member.write_bytes(b"synthetic")
    baseline = auth_cache_stat.metadata_digest((root,))
    actual_stat = os.stat
    calls = 0

    def changing(
        path: str | os.PathLike[str],
        *,
        dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        nonlocal calls
        if path == "auth.json":
            calls += 1
            if calls == 2:
                member.write_bytes(b"synthetic approved evolution races this sample")
        return actual_stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(os, "stat", changing)
    with pytest.raises(LedgerError, match=r"^observation_unavailable$"):
        auth_cache_stat.metadata_digest((root,))
    monkeypatch.setattr(os, "stat", actual_stat)
    assert auth_cache_stat.metadata_digest((root,)) == baseline


@pytest.mark.parametrize(
    "damage",
    [
        "compile-cache",
        "symlink",
        "hardlink",
        "permissions",
        "member",
        "nested-permissions",
    ],
)
def test_formal_confirmed_cache_drift_cannot_revive_by_removing_the_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    from paper_radar.live_evidence import service as evidence
    from tests.screening_live_admission_support import projected_admission

    product, identifier, credentials, site = material_site(
        tmp_path / "product", monkeypatch
    )
    registered = credentials / "registered-directory"
    if damage == "nested-permissions":
        registered.mkdir(mode=0o700)
    local = current_binding.local_binding_components
    components = local(product.database, site.binding, credentials_dir=credentials)
    components.update({B.OBSERVER: "a" * 64, B.IPV4_EGRESS: "b" * 64})
    ledger, original, _ = protected_admission(
        tmp_path / "evidence", monkeypatch, components=components
    )
    monkeypatch.setattr(current_binding, "local_binding_components", local)
    product._now = lambda: NOW
    assert projected_admission(components, "boundary-low").decision.executable
    extra = credentials / "unapproved"
    if damage == "compile-cache":
        extra = credentials / "node-compile-cache"
        extra.mkdir()
    elif damage == "symlink":
        extra.symlink_to(tmp_path)
    elif damage == "hardlink":
        os.link(credentials / "auth.json", extra)
    elif damage == "permissions":
        credentials.chmod(0o755)
    elif damage == "nested-permissions":
        registered.chmod(0)
    else:
        extra.write_bytes(b"unapproved synthetic member")

    def unavailable() -> None:
        raise LedgerError("observation_unavailable")

    monkeypatch.setattr(
        "paper_radar.pi_execution.admission_checkpoints.request_observation_refresh",
        unavailable,
    )
    with pytest.raises(ExecutionError, match=r"^evidence_missing$"):
        product.run_attempt(identifier)
    assert evidence._read_pending()
    if damage == "compile-cache":
        extra.rmdir()
    elif damage == "permissions":
        credentials.chmod(0o700)
    elif damage == "nested-permissions":
        registered.chmod(0o700)
    else:
        extra.unlink()
    assert not projected_admission(components, "boundary-low").decision.executable
    assert ledger.show(original.receipt_id).receipt == original
    assert not (credentials / "auth-observed.json").exists()


@pytest.mark.parametrize("unsafe", [False, True])
def test_root_metadata_refresh_preserves_temporary_but_persistently_tightens_unsafe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unsafe: bool
) -> None:
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
    from paper_radar.live_evidence.observation import load_current_observation
    from paper_radar.live_evidence.protected_observer import refresh_once
    from paper_radar.live_evidence.receipt import canonical_bytes
    from tests.test_observation_refresh import refresh_site

    _, _, credentials, site = material_site(tmp_path / "product", monkeypatch)
    (tmp_path / "evidence").mkdir()
    ledger, runtime, _, previous = refresh_site(tmp_path / "evidence", monkeypatch)
    observed = sealed_runtime.observe_site(site, metadata_only=True)
    assert observed.checks == (("metadata", True),)
    previous = previous.model_copy(
        update={"binding": previous.binding | observed.components}
    )
    source = ledger.root / "inbox/current-observation.json"
    source.write_bytes(canonical_bytes(previous))

    def product_metadata(
        _site: SiteConfiguration, *, metadata_only: bool = False
    ) -> SiteObservation:
        return sealed_runtime.observe_site(site, metadata_only=metadata_only)

    monkeypatch.setattr(sealed_runtime, "product_observation", product_metadata)
    assert refresh_once(runtime, ledger, now=NOW) == "available"
    snapshot = source.read_bytes()
    events = ledger.audit()
    actual_open = os.open
    cache = credentials / "node-compile-cache"
    if unsafe:
        cache.mkdir()
    else:

        def temporary_open(
            path: str | os.PathLike[str],
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            if path == credentials:
                raise OSError(errno.EIO, "synthetic_metadata_io")
            return actual_open(path, flags, mode, dir_fd=dir_fd)

        monkeypatch.setattr(os, "open", temporary_open)
    at = NOW + timedelta(seconds=61)
    assert refresh_once(runtime, ledger, now=at) == (
        "source_untrusted" if unsafe else "observation_unavailable"
    )
    assert source.read_bytes() == snapshot
    revoked = EvidenceLifecycle(ledger).snapshot(now=at).evidence
    assert revoked and all(item.revoked == unsafe for item in revoked)
    if unsafe:
        cache.rmdir()
    else:
        assert ledger.audit() == events
        monkeypatch.setattr(os, "open", actual_open)
    assert refresh_once(runtime, ledger, now=at) == "available"
    assert load_current_observation(ledger, now=at).observed_at == at
    assert all(
        item.revoked == unsafe
        for item in EvidenceLifecycle(ledger).snapshot(now=at).evidence
    )


@pytest.mark.parametrize("part", [B.LAUNCH_POLICY, B.MODEL_TUPLE])
def test_material_refresh_does_not_hide_real_execution_identity_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, part: B
) -> None:
    from paper_radar.live_evidence.lifecycle import use_for_id
    from paper_radar.pi_execution.admission_guard import AdmissionGuard
    from tests.screening_live_admission_support import projected_admission

    product, _, credentials, site = material_site(tmp_path / "product", monkeypatch)
    local = current_binding.local_binding_components
    components = local(product.database, site.binding, credentials_dir=credentials)
    components.update({B.OBSERVER: "a" * 64, B.IPV4_EGRESS: "b" * 64})
    protected_admission(tmp_path / "evidence", monkeypatch, components=components)
    monkeypatch.setattr(current_binding, "local_binding_components", local)
    changed = (
        replace(site.binding, launch_policy_version="changed")
        if part == B.LAUNCH_POLICY
        else replace(site.binding, model="changed")
    )
    request = current_binding.build_admission_request(
        product.database,
        changed,
        use=use_for_id("boundary-low"),
        credentials_dir=credentials,
        now=NOW,
    )
    guard = AdmissionGuard(request.use)
    with pytest.raises(ExecutionError, match=r"^evidence_missing$"):
        guard.check(request, now=NOW)
    guard.tighten_after_denial(now=NOW)
    assert not projected_admission(components, "boundary-low").decision.executable


@pytest.mark.parametrize("field", ["supply_id", "install_id"])
def test_routine_metadata_still_refuses_actual_execution_selection_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    _, _, _, site = material_site(tmp_path, monkeypatch)
    assert sealed_runtime.observe_site(site, metadata_only=True).checks == (
        ("metadata", True),
    )
    binding = (
        replace(site.binding, supply_id="f" * 64)
        if field == "supply_id"
        else replace(site.binding, install_id="f" * 64)
    )
    observed = sealed_runtime.observe_site(
        site.model_copy(update={"binding": binding}), metadata_only=True
    )
    assert observed.checks == (("metadata", False),)
    assert observed.failure == "binding_observation_unavailable"


@pytest.mark.parametrize("policy_drift", [False, True])
def test_temporary_failure_with_low_site_context_keeps_high_model_qualification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, policy_drift: bool
) -> None:
    from paper_radar.live_evidence import service as evidence
    from paper_radar.live_evidence.lifecycle import use_for_id
    from paper_radar.live_evidence.observation import CurrentObservation
    from paper_radar.live_evidence.receipt import canonical_bytes
    from paper_radar.pi_execution.admission_guard import AdmissionGuard

    product, _, credentials, site = material_site(tmp_path / "product", monkeypatch)
    local = current_binding.local_binding_components
    high = replace(site.binding, thinking_level="high")
    components = local(product.database, high, credentials_dir=credentials)
    components.update({B.OBSERVER: "a" * 64, B.IPV4_EGRESS: "b" * 64})
    ledger, original, _ = protected_admission(
        tmp_path / "evidence",
        monkeypatch,
        components=components,
        uses=("boundary-high",),
    )
    source = ledger.root / "inbox/current-observation.json"
    source.write_bytes(
        canonical_bytes(
            CurrentObservation(
                observed_at=NOW,
                binding=components
                | {B.MODEL_TUPLE: current_binding.model_tuple_component(site.binding)},
                checked_components=tuple(B),
            )
        )
    )

    def unavailable(
        database: Path,
        binding: EvidenceBinding,
        *,
        credentials_dir: Path,
    ) -> dict[B, str]:
        raise LedgerError("observation_unavailable")

    monkeypatch.setattr(current_binding, "local_binding_components", unavailable)
    use = use_for_id("boundary-high")
    requested = replace(high, launch_policy_version="changed") if policy_drift else high
    projection = current_binding.diagnose_observation_failure(
        product.database,
        requested,
        use=use,
        credentials_dir=credentials,
        now=NOW,
        error=LedgerError("observation_unavailable"),
    )
    guard = AdmissionGuard(use)
    guard.note_observation_failure(LedgerError("observation_unavailable"), projection)
    guard.tighten_after_denial(now=NOW)
    assert bool(evidence._read_pending()) == policy_drift
    assert ledger.show(original.receipt_id).receipt == original
