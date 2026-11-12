"""所有者卸载工具的独立公开边界;不调用真实主机工具。"""

import io
import json
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from scripts.live_uninstall import (
    HOST_PROGRAM,
    RESOURCE_SOURCES,
    RUNTIME,
    canonical,
    main,
    prepare_review,
    sha,
    uninstall,
    validate_review,
)


def test_prepare_requires_installed_deployment_before_creating_review(
    tmp_path: Path,
) -> None:
    output = tmp_path / "review.json"
    report = prepare_review(tmp_path, output, owner_uid=1000)
    assert report["status"] == "refused"
    assert report["checks"]["deployment"]["reason"] == "deployment_missing"
    assert not output.exists()


def installed_tree(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    root = tmp_path / "host"
    root.mkdir()
    runtime = root / RUNTIME.relative_to("/")
    runtime.mkdir(parents=True)
    for source in RESOURCE_SOURCES.values():
        target = runtime / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(("known " + source).encode())
    (runtime / "site.json").write_bytes(
        canonical({"product_uid": 1000, "product_gid": 1000})
    )
    manifest = "".join(
        f"{sha(path.read_bytes())}  {path.relative_to(runtime)}\n"
        for path in sorted(runtime.rglob("*"))
        if path.is_file()
    ).encode()
    (runtime / "manifest.sha256").write_bytes(manifest)
    payload = "a" * 64
    (runtime / "payload.sha256").write_text(payload + "\n")
    for destination, source in RESOURCE_SOURCES.items():
        target = root / destination.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((runtime / source).read_bytes())
        target.chmod(
            0o440
            if source == "sudoers"
            else 0o755
            if source.startswith("wrappers/")
            else 0o644
        )
    ledger = root / "var/lib/paperradar/live-evidence"
    ledger.mkdir(parents=True)
    journal = canonical(
        {
            "format_version": 2,
            "phase": "installed",
            "payload": payload,
            "manifest": sha(manifest),
        }
    )
    (ledger / "deployment-v2.json").write_bytes(journal)
    for name in ("collector.lock", "collection.lock", "closure.lock"):
        (ledger / name).touch()
    (ledger / "ledger.sqlite3").write_bytes(b"preserved ledger bytes")
    (ledger / "inbox").mkdir()
    (ledger / "inbox/placement-target-v1.json").write_bytes(b"preserved target bytes")
    (root / "var/lib/paperradar/live-bundles").mkdir()
    (root / "var/backups").mkdir()
    review: dict[str, Any] = {
        "format_version": 1,
        "authorization": "owner-live-deployment-uninstall-v1",
        "deployment": [payload, sha(manifest)],
        "journal_sha256": sha(journal),
        "archives": [],
        "diagnostic_runtime": [payload, sha(manifest)],
    }
    for path in (root, *root.rglob("*")):
        if path.is_dir():
            path.chmod(0o755)
        elif str(path.relative_to(root)) == "etc/sudoers.d/paperradar-live-evidence":
            path.chmod(0o440)
        elif path.parent == root / "usr/libexec/paperradar":
            path.chmod(0o755)
        else:
            path.chmod(0o644)
    return root, review


class QuietHost:
    def __init__(self) -> None:
        self.events: list[str] = []

    def diagnose(self) -> dict[str, Any]:
        return {
            name: {"status": "pass", "reason": "known_idle"}
            for name in ("units", "nft", "apparmor", "processes")
        }

    def action(self, name: str) -> None:
        self.events.append(name)


def test_unknown_resource_aggregates_failures_before_any_write(tmp_path: Path) -> None:
    root, review = installed_tree(tmp_path)
    sudoers = root / "etc/sudoers.d/paperradar-live-evidence"
    sudoers.chmod(0o640)
    sudoers.write_bytes(b"unknown sudo permission")
    sudoers.chmod(0o440)
    (root / "run/paper-radar/resolv.conf").write_bytes(b"unknown resolver")
    host = QuietHost()
    report = uninstall(review, root=root, owner_uid=os.getuid(), host=host)
    assert report["status"] == "refused"
    assert (
        report["checks"]["resource:/etc/sudoers.d/paperradar-live-evidence"]["reason"]
        == "resource_identity"
    )
    assert (
        report["checks"]["resource:/run/paper-radar/resolv.conf"]["reason"]
        == "resource_identity"
    )
    assert host.events == []
    assert list((root / "var/backups").iterdir()) == []
    assert (
        root / "var/lib/paperradar/live-evidence/deployment-v2.json"
    ).read_bytes() == canonical(
        {
            "format_version": 2,
            "phase": "installed",
            "payload": "a" * 64,
            "manifest": review["deployment"][1],
        }
    )


def test_success_archives_original_bytes_and_preserves_all_history(
    tmp_path: Path,
) -> None:
    root, review = installed_tree(tmp_path)
    ledger = root / "var/lib/paperradar/live-evidence"
    original = {
        p.relative_to(ledger): p.read_bytes() for p in ledger.rglob("*") if p.is_file()
    }
    original_runtime = (
        root / RUNTIME.relative_to("/") / "manifest.sha256"
    ).read_bytes()
    host = QuietHost()
    report = uninstall(review, root=root, owner_uid=os.getuid(), host=host)
    assert report["status"] == "uninstalled"
    archive = Path(report["archive"])
    assert archive.stat().st_mode & 0o777 == 0o700
    assert (archive / "runtime/manifest.sha256").read_bytes() == original_runtime
    assert (archive / "history/deployment-v2.json").read_bytes() == original[
        Path("deployment-v2.json")
    ]
    assert not (root / RUNTIME.relative_to("/")).exists()
    assert all(not (root / path.lstrip("/")).exists() for path in RESOURCE_SOURCES)
    assert {
        p.relative_to(ledger): p.read_bytes() for p in ledger.rglob("*") if p.is_file()
    } == original
    assert host.events == ["stop", "policy-remove", "nft-remove", "reload", "absent"]


def test_unreadable_or_unowned_history_is_a_preflight_refusal(tmp_path: Path) -> None:
    root, review = installed_tree(tmp_path)
    (root / "var/lib/paperradar/live-evidence/unknown").symlink_to("/etc/passwd")
    host = QuietHost()
    report = uninstall(review, root=root, owner_uid=os.getuid(), host=host)
    assert report["status"] == "refused"
    assert report["checks"]["preserved"]["reason"] == "protected_identity"
    assert host.events == []
    assert list((root / "var/backups").iterdir()) == []


def run_host_program(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    action: str,
    failing: bool,
    policy_mode: str = "absent",
    kernel_events: list[str] | None = None,
) -> tuple[dict[str, Any], list[Path]]:
    reads: list[Path] = []
    policy_loaded = policy_mode != "absent"
    events: list[str] = [] if kernel_events is None else kernel_events

    def read(path: Path) -> bytes:
        reads.append(path)
        assert path.is_relative_to("/var/lib/paperradar/live-bundles")
        return b"{}"

    monkeypatch.setattr(Path, "read_bytes", read)
    monkeypatch.setattr(Path, "exists", lambda _: False)
    monkeypatch.setattr(Path, "iterdir", lambda _: iter(()))
    monkeypatch.setattr(sys, "path", list(sys.path))
    review = {
        "diagnostic_runtime": ["d" * 64, "e" * 64],
        "deployment": ["a" * 64, "b" * 64],
        "archives": [["d" * 64, "e" * 64]],
    }
    monkeypatch.setattr(
        sys, "stdin", io.StringIO(json.dumps({"review": review, "action": action}))
    )

    class ModelHost:
        def __init__(self, paths: Any) -> None:
            self.site: Any = None

        def unit_properties(self, name: str) -> dict[str, str]:
            raise ValueError("unit_shadow_or_dropin")

        def _read_target(self) -> Any:
            if failing:
                raise ValueError("placement_source_identity")
            return SimpleNamespace(
                ancestors=[SimpleNamespace(path="/user.slice/project")]
            )

        def _run(self, command: tuple[str, ...], **options: Any) -> bytes:
            if command == ("/usr/sbin/nft", "-j", "list", "tables"):
                return b'{"nftables": []}'
            assert command[:3] == ("/usr/bin/systemctl", "--user", "show")
            return b"LoadState=not-found\nActiveState=inactive\nMainPID=0\n"

    def nft() -> dict[str, Any]:
        if failing:
            raise ValueError("nft_views_identity")
        return {"nftables": []}

    class KernelIO:
        def profile_handles(self) -> tuple[str, ...]:
            if failing:
                raise ValueError("apparmor_snapshot_changed")
            return ("p1",) if policy_loaded else ()

        def read_field(self, handle: str, field: str) -> bytes:
            return {
                "name": b"paperradar-placement-pre-v1",
                "attach": b"<unknown>",
                "raw_sha256": b"c" * 64,
            }[field]

        def require_writer(self, parser: Any) -> None:
            events.append("writer_checked")

    class ModelKernel:
        def check(self, policy: Any, *, allow_partial: bool) -> None:
            assert allow_partial is True
            events.append("checked_owned_partial")

        def remove(self, policy: Any, *, allow_partial: bool) -> None:
            nonlocal policy_loaded
            assert allow_partial is True
            policy_loaded = False
            events.append("removed_owned_partial")

    candidate = SimpleNamespace(
        policy=SimpleNamespace(binary_sha256="c" * 64),
        parser=object(),
        kernel=ModelKernel,
    )

    def module(name: str, **members: Any) -> None:
        value = ModuleType(name)
        for key, member in members.items():
            setattr(value, key, member)
        monkeypatch.setitem(sys.modules, name, value)

    prefix = "paper_radar.live_evidence."
    module(prefix + "live_apparmor_kernel", LinuxKernelPolicyIO=KernelIO)
    module(
        prefix + "live_host",
        LinuxLiveHost=ModelHost,
        validate_unit_identity=lambda *a, **kw: None,
    )
    module(
        prefix + "live_install",
        InstallationPaths=lambda: SimpleNamespace(runtime=RUNTIME),
    )
    module(prefix + "model_manifest", parse_manifest=lambda _: None)
    module(prefix + "nft_rules", read_nft_snapshot=nft, verify_nft=lambda *a: None)
    module(
        prefix + "placement_policy",
        read_placement_policy=lambda _: (
            candidate if policy_mode == "known_partial" else None
        ),
    )
    site = SimpleNamespace(install_path=Path("/original/product/install"))
    module(
        prefix + "sealed_runtime",
        SiteConfiguration=SimpleNamespace(model_validate_json=lambda _: site),
    )
    exec(compile(HOST_PROGRAM, "<owner-host-program>", "exec"), {})
    return json.loads(capsys.readouterr().out), reads


def test_real_host_program_aggregates_all_four_failures_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result, _ = run_host_program(monkeypatch, capsys, action="diagnose", failing=True)
    assert result == {
        "units": {"status": "fail", "reason": "unit_shadow_or_dropin"},
        "processes": {"status": "fail", "reason": "placement_source_identity"},
        "nft": {"status": "fail", "reason": "nft_views_identity"},
        "apparmor": {"status": "fail", "reason": "apparmor_snapshot_changed"},
    }


def test_real_host_program_verifies_absence_using_only_preserved_archive(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result, reads = run_host_program(
        monkeypatch, capsys, action="absent", failing=False
    )
    assert result == {"status": "pass"}
    assert [path.name for path in reads] == ["site.json", "model-manifest.json"]
    assert all(
        path.is_relative_to("/var/lib/paperradar/live-bundles") for path in reads
    )


@pytest.mark.parametrize("field", ["deployment", "diagnostic_runtime", "archives"])
def test_review_rejects_paths_or_unregistered_runtime(field: str) -> None:
    review: dict[str, Any] = {
        "format_version": 1,
        "authorization": "owner-live-deployment-uninstall-v1",
        "journal_sha256": "f" * 64,
        "deployment": ["a" * 64, "b" * 64],
        "diagnostic_runtime": ["a" * 64, "b" * 64],
        "archives": [["a" * 64, "b" * 64]],
    }
    review[field] = (
        [["../../other", "b" * 64]]
        if field == "archives"
        else ["../../other", "b" * 64]
    )
    with pytest.raises(ValueError, match="review_identity"):
        validate_review(review)


def test_failure_after_stop_keeps_backups_and_never_reloads_policy(
    tmp_path: Path,
) -> None:
    root, review = installed_tree(tmp_path)

    class RefusingHost(QuietHost):
        def action(self, name: str) -> None:
            super().action(name)
            if name == "policy-remove":
                raise ValueError("apparmor_snapshot_changed")

    host = RefusingHost()
    report = uninstall(review, root=root, owner_uid=os.getuid(), host=host)
    assert report["status"] == "failed"
    assert report["phase"] == "host_removal"
    assert report["reason"] == "apparmor_snapshot_changed"
    assert report["automatic_rollback"] is False
    assert host.events == ["stop", "policy-remove"]
    assert (root / RUNTIME.relative_to("/")).exists()
    assert (Path(report["archive"]) / "history/deployment-v2.json").read_bytes() == (
        root / "var/lib/paperradar/live-evidence/deployment-v2.json"
    ).read_bytes()


def test_failed_lock_joins_host_diagnostics_and_prevents_backup(tmp_path: Path) -> None:
    root, review = installed_tree(tmp_path)
    host = QuietHost()
    report = uninstall(
        review,
        root=root,
        owner_uid=os.getuid(),
        host=host,
        lock_checks={
            "lock:collector.lock": {
                "status": "fail",
                "reason": "deployment_lock_unavailable",
            }
        },
    )
    assert report["status"] == "refused"
    assert report["checks"]["nft"]["status"] == "pass"
    assert (
        report["checks"]["lock:collector.lock"]["reason"]
        == "deployment_lock_unavailable"
    )
    assert host.events == []
    assert list((root / "var/backups").iterdir()) == []


def test_help_is_read_only_and_does_not_inspect_the_host(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0
    assert "apply" in capsys.readouterr().out


def test_real_host_program_removes_only_authenticated_owned_partial_policy(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    events: list[str] = []
    result, _ = run_host_program(
        monkeypatch,
        capsys,
        action="policy-remove",
        failing=False,
        policy_mode="known_partial",
        kernel_events=events,
    )
    assert result == {"status": "pass"}
    assert events == [
        "checked_owned_partial",
        "writer_checked",
        "removed_owned_partial",
    ]


def test_real_host_program_refuses_unknown_policy_without_remove(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    events: list[str] = []
    result, _ = run_host_program(
        monkeypatch,
        capsys,
        action="policy-remove",
        failing=False,
        policy_mode="unknown",
        kernel_events=events,
    )
    assert result == {"status": "fail", "reason": "apparmor_unknown_owned_bytes"}
    assert events == []


def test_diagnostics_are_emitted_before_creating_any_archive(tmp_path: Path) -> None:
    root, review = installed_tree(tmp_path)
    diagnostics: list[dict[str, Any]] = []

    def observe(checks: dict[str, Any]) -> None:
        assert list((root / "var/backups").iterdir()) == []
        assert all(item["status"] == "pass" for item in checks.values())
        diagnostics.append(checks)

    report = uninstall(
        review,
        root=root,
        owner_uid=os.getuid(),
        host=QuietHost(),
        report_diagnostics=observe,
    )
    assert report["status"] == "uninstalled"
    assert len(diagnostics) == 1
