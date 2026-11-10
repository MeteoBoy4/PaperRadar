"""Live显式新封印模式;非特权派生/构建不改变旧v1部署协议。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from paper_radar.live_evidence.sealed_runtime import RUNTIME_ROOT, SiteConfiguration


class BundleInputError(ValueError):
    def __init__(self, reason: str, expected: dict[str, str]) -> None:
        self.expected = expected
        super().__init__(reason)


def expected_site_fields(site: SiteConfiguration) -> dict[str, str]:
    from paper_radar.pi_execution.isolation import ISOLATION_POLICY_VERSION
    from paper_radar.pi_execution.resources import LAUNCH_POLICY_VERSION
    from paper_radar.pi_supply import activation_history

    expected = {
        "binding.launch_policy_version": LAUNCH_POLICY_VERSION,
        "binding.isolation_policy_version": ISOLATION_POLICY_VERSION,
    }
    from paper_radar.pi_supply import SupplyError

    try:
        history = activation_history(site.database)
    except (SupplyError, OSError):
        raise BundleInputError("latest_activation_unavailable", expected) from None
    if not history:
        raise BundleInputError("latest_activation_missing", expected)
    latest = history[-1]
    return expected | {
        "snapshot_id": latest.snapshot_id,
        "binding.supply_id": latest.supply_id,
        "binding.install_id": latest.install_id,
    }


def assert_current_site(site: SiteConfiguration) -> dict[str, str]:
    expected = expected_site_fields(site)
    actual = {"snapshot_id": site.snapshot_id} | {
        "binding." + key: getattr(site.binding, key)
        for key in (
            "launch_policy_version",
            "isolation_policy_version",
            "supply_id",
            "install_id",
        )
    }
    if actual != expected:
        raise BundleInputError("site_binding_mismatch", expected)
    return expected


def derive_site(
    site: SiteConfiguration,
) -> tuple[SiteConfiguration, dict[str, dict[str, str]]]:
    """仅派生五个授权字段;install_path不一致继续由SiteConfiguration拒绝。"""
    expected = expected_site_fields(site)
    binding = replace(
        site.binding,
        launch_policy_version=expected["binding.launch_policy_version"],
        isolation_policy_version=expected["binding.isolation_policy_version"],
        supply_id=expected["binding.supply_id"],
        install_id=expected["binding.install_id"],
    )
    try:
        derived = SiteConfiguration.model_validate(
            site.model_dump()
            | {"binding": binding, "snapshot_id": expected["snapshot_id"]}
        )
    except ValueError:
        raise BundleInputError("derived_install_path_mismatch", expected) from None
    before = {"snapshot_id": site.snapshot_id} | {
        name: getattr(site.binding, name.split(".", 1)[1])
        for name in expected
        if name.startswith("binding.")
    }
    return derived, {
        name: {"before": before[name], "after": value}
        for name, value in expected.items()
        if before[name] != value
    }


def proposed_window(now: datetime) -> tuple[datetime, datetime]:
    from datetime import timezone

    if now.tzinfo is None:
        raise ValueError("plan_window_invalid")
    start = now.astimezone(timezone(timedelta(hours=8))).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return start.astimezone(UTC), (
        start + timedelta(days=14, hours=23, minutes=59, seconds=59)
    ).astimezone(UTC)


def assert_source_guard(source_root: Path) -> None:
    """向量必须对应当前完整源码,构建不接受旧向量配新root代码。"""
    import hashlib
    import json

    from paper_radar.pi_execution.current_binding import ADMISSION_POLICY_VERSION
    from paper_radar.pi_execution.isolation import ISOLATION_POLICY_VERSION
    from paper_radar.pi_execution.placement import PLACEMENT_POLICY_VERSION
    from paper_radar.pi_execution.resources import LAUNCH_POLICY_VERSION
    from paper_radar.pi_protocol import PROTOCOL_PROFILES

    version = ADMISSION_POLICY_VERSION.rsplit("-", 1)[1]
    path = (
        source_root
        / "tests/fixtures"
        / ("live-admission-source-guard-" + version + ".json")
    )
    vector = json.loads(path.read_bytes())
    if vector.get("format_version") != 1 or vector.get("policies") != {
        "admission": ADMISSION_POLICY_VERSION,
        "launch": LAUNCH_POLICY_VERSION,
        "placement": PLACEMENT_POLICY_VERSION,
        "isolation": ISOLATION_POLICY_VERSION,
        "protocol_1_4_0": PROTOCOL_PROFILES["1.4.0"],
    }:
        raise ValueError("source_guard_mismatch")
    from pathlib import PurePosixPath

    for name, expected in vector["files"].items():
        relative = PurePosixPath(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or hashlib.sha256((source_root / name).read_bytes()).hexdigest() != expected
        ):
            raise ValueError("source_guard_mismatch")


def build_live_bundle(
    target: Path,
    site: SiteConfiguration,
    *,
    starts_at: datetime,
    ends_at: datetime,
    source_root: Path,
    network_input: dict[str, Any],
    upgrade_from: tuple[str, str] | None = None,
) -> dict[str, str]:
    """独立Live模式;拒绝在任何输出前检查策略/activation/窗口与输入形状。"""
    import hashlib
    import os
    import tarfile
    import tempfile

    from paper_radar.live_evidence import deployment
    from paper_radar.live_evidence.collector import SITE_CASES
    from paper_radar.live_evidence.live_bundle_scripts import (
        render_runner,
        review_text,
        wrapper,
    )
    from paper_radar.live_evidence.live_host import cache_metadata
    from paper_radar.live_evidence.live_install import json_bytes
    from paper_radar.live_evidence.live_materials import freeze_materials
    from paper_radar.live_evidence.model_manifest import (
        NEGATIVES,
        USES,
        ModelManifest,
        NetworkConfiguration,
    )
    from paper_radar.live_evidence.receipt import (
        ApprovedPlan,
        canonical_bytes,
        content_sha256,
    )
    from paper_radar.live_evidence.receipt_v2 import ApprovedPlanV2

    expected = assert_current_site(site)
    if os.geteuid() == 0:
        raise ValueError("build_requires_unprivileged_user")
    if (
        starts_at.tzinfo is None
        or ends_at.tzinfo is None
        or ends_at - starts_at < timedelta(days=7)
    ):
        raise ValueError("plan_window_invalid")
    start, end = starts_at.astimezone(UTC), ends_at.astimezone(UTC)
    if (
        network_input.get("pool") != "28.0.0.0/8"
        or network_input.get("router") != "192.168.44.1"
    ):
        raise ValueError("owner_network_scope")
    allowed = {
        "pool",
        "router",
        "outside",
        "nonrouter",
        "udp443",
        "owner_network_applicable",
        "owner_window_confirmed",
        "owner_statement",
    }
    if (
        set(network_input) != allowed
        or not isinstance(network_input["owner_statement"], str)
        or not network_input["owner_statement"].strip()
        or any(
            type(network_input[field]) is not bool
            for field in ("owner_network_applicable", "owner_window_confirmed")
        )
    ):
        raise ValueError("owner_network_input")
    if upgrade_from is not None:
        deployment.render_upgrade(*upgrade_from)
    if set(site.claim_uses) != set(USES) or site.use_id != "boundary-low":
        raise ValueError("bundle_claim_uses")
    assert_source_guard(source_root)
    if target.exists():
        raise FileExistsError("bundle_output_exists")
    with tempfile.TemporaryDirectory(prefix="paperradar-live-seal-") as temporary:
        frozen = Path(temporary)
        deployment.freeze_runtime(frozen, source_root)
        for name, action in (
            ("collect", "collect"),
            ("tighten", "tighten"),
            ("owner", "owner"),
            ("refresh", "refresh"),
            ("model-collect", "collect-models"),
        ):
            path = frozen / "wrappers" / name
            path.write_bytes(wrapper(action))
            path.chmod(0o755)
        (frozen / "install-live.py").write_text(
            "import sys\nfrom pathlib import Path\nroot=Path(__file__).parent\n"
            "sys.path.insert(0,str(root/'site-packages'))\n"
            "from paper_radar.live_evidence.live_install import installation_main\n"
            "raise SystemExit(installation_main(root))\n"
        )
        import platform
        import subprocess

        if platform.system() != "Linux" or platform.machine() != "x86_64":
            raise ValueError("anchor_platform_unknown")
        (frozen / "anchor.S").write_text(
            ".global _start\n.section .text\n_start:\n"
            "mov $34,%rax\nsyscall\njmp _start\n"
            '.section .note.GNU-stack,"",@progbits\n'
        )
        subprocess.run(
            (
                "/usr/bin/cc",
                "-nostdlib",
                "-static",
                "-s",
                "-Wl,--build-id=none",
                "-o",
                str(frozen / "anchor"),
                str(frozen / "anchor.S"),
            ),
            env={"PATH": "/usr/bin:/bin"},
            capture_output=True,
            check=True,
            timeout=30,
        )
        vectors = frozen / "source-vectors"
        vectors.mkdir()
        for source in sorted(
            (source_root / "tests/fixtures").glob("live-admission-source-guard-v*.json")
        ):
            (vectors / source.name).write_bytes(source.read_bytes())
        resources = frozen / "resources"
        resources.mkdir()
        runtime = str(RUNTIME_ROOT)
        (resources / "paperradar.slice").write_text(
            "[Unit]\nDescription=PaperRadar product isolation slice\n"
            "[Slice]\nCPUAccounting=yes\nMemoryAccounting=yes\n"
        )
        (resources / "paperradar-anchor.service").write_text(
            "[Unit]\nDescription=PaperRadar product cgroup anchor\n"
            "[Service]\nType=simple\n"
            "Slice=paperradar.slice\nRestart=no\nLimitCORE=0\nStandardOutput=null\nStandardError=null\n"
            "UnsetEnvironment=LD_PRELOAD LD_LIBRARY_PATH "
            "PYTHONPATH PYTHONHOME PYTHONSTARTUP\n"
            f"ExecStart={runtime}/anchor\n"
        )
        (resources / "resolv.conf").write_text(
            "nameserver 192.168.44.1\noptions attempts:1 timeout:2\n"
        )
        (frozen / "sudoers").write_text(
            f"#{site.product_uid} ALL=(root) NOPASSWD: NOSETENV: "
            '/usr/libexec/paperradar/live-evidence-collect "", '
            '/usr/libexec/paperradar/live-evidence-refresh "", '
            '/usr/libexec/paperradar/live-evidence-model-collect "", '
            "/usr/libexec/paperradar/live-evidence-tighten *\n"
        )
        collector_sha = hashlib.sha256(
            json_bytes(deployment.file_digests(frozen))
        ).hexdigest()
        key = hashlib.sha256(
            canonical_bytes(site)
            + collector_sha.encode()
            + start.isoformat().encode()
            + end.isoformat().encode()
            + json_bytes(network_input)
        ).hexdigest()[:12]
        strict = ApprovedPlan(
            format_version="v1",
            plan_id="site-beta-" + key,
            kind="site_beta",
            collector_sha256=collector_sha,
            cases=SITE_CASES,
            starts_at=start,
            ends_at=end,
            max_auth_calls=0,
            max_model_calls=0,
            max_network_requests=0,
            max_rounds=1,
            stop_on_first_failure=True,
        )

        def plan(
            name: str, cases: tuple[str, ...], *, negative: bool = False
        ) -> ApprovedPlanV2:
            return ApprovedPlanV2(
                format_version="v2",
                domain_id="live-177",
                plan_id=name + "-" + key,
                kind="site_beta" if negative else "model_six_cell",
                collector_sha256=collector_sha,
                cases=cases,
                starts_at=start,
                ends_at=end,
                max_rounds=6,
                stop_on_first_failure=True,
                max_auth_calls=0 if negative else 6,
                max_model_calls=0 if negative else 6,
                max_network_requests=24 if negative else 0,
            )

        plans = tuple(plan("model-" + use, ("model-" + use,)) for use in USES)
        negative = plan("negative", NEGATIVES, negative=True)
        cells, members = freeze_materials(frozen, site, plans, source_root=source_root)
        ids = tuple(item.plan_id for item in (*plans, negative))
        confirmation = json_bytes(
            {
                "format_version": 1,
                "owner_input": network_input,
                "plan_ids": ids,
                "starts_at": start.isoformat(),
                "ends_at": end.isoformat(),
                "proof_boundary": (
                    "ADR-0050; upstream mapping unknown; "
                    "no TLS intermediary per owner input"
                ),
            }
        )
        network = NetworkConfiguration.model_validate(
            {
                name: network_input[name]
                for name in ("pool", "router", "outside", "nonrouter", "udp443")
            }
            | {
                "owner_confirmation_sha256": hashlib.sha256(confirmation).hexdigest(),
                "plan_ids": ids,
                "starts_at": start,
                "ends_at": end,
            }
        )
        manifest = ModelManifest(
            format_version=1,
            collector_sha256=collector_sha,
            site_plan_id=strict.plan_id,
            site_plan_sha256=content_sha256(strict),
            actual_snapshot_id=site.snapshot_id,
            cells=cells,
            negative_plan=negative,
            network=network,
            members=members,
        )
        (frozen / "model-manifest.json").write_bytes(canonical_bytes(manifest))
        (frozen / "network-owner-confirmation.json").write_bytes(confirmation)
        (frozen / "plan.json").write_bytes(canonical_bytes(strict))
        (frozen / "site.json").write_bytes(canonical_bytes(site))
        (frozen / "plans").mkdir()
        for item in (*plans, negative):
            (frozen / "plans" / (item.plan_id + ".json")).write_bytes(
                canonical_bytes(item)
            )
        cache_path = site.credentials_dir / "node-compile-cache"
        cache = cache_metadata(cache_path) if os.path.lexists(cache_path) else None
        (frozen / "deployment.json").write_bytes(
            json_bytes(
                {
                    "format_version": 2,
                    "upgrade_from": upgrade_from,
                    "cache_migration": cache,
                    "host_machine": platform.machine(),
                    "host_tools": {
                        name: {
                            "resolved": str(Path(name).resolve()),
                            "sha256": hashlib.sha256(
                                Path(name).read_bytes()
                            ).hexdigest(),
                        }
                        for name in (
                            "/usr/bin/systemctl",
                            "/usr/bin/loginctl",
                            "/usr/sbin/nft",
                            "/usr/sbin/visudo",
                        )
                    },
                    "strict_beta": strict.plan_id,
                    "natural_refresh": "unknown_stop_gate",
                }
            )
        )
        # source身份与payload分开,不把payload或manifest摘要反向写入自身。
        import subprocess
        import sys

        def git(*arguments: str) -> str:
            return subprocess.run(
                ("git", "-C", str(source_root), *arguments),
                capture_output=True,
                check=True,
                text=True,
            ).stdout.strip()

        identity = {
            "format_version": 2,
            "git_head": git("rev-parse", "HEAD"),
            "git_tree": git("rev-parse", "HEAD^{tree}"),
            "git_status": git("status", "--porcelain"),
            "source_python_sha256": {
                name: sha
                for name, sha in deployment.file_digests(
                    source_root / "src/paper_radar"
                ).items()
                if name.endswith(".py")
            },
            "uv_lock_sha256": hashlib.sha256(
                (source_root / "uv.lock").read_bytes()
            ).hexdigest(),
            "python_executable_sha256": hashlib.sha256(
                Path(sys.executable).resolve().read_bytes()
            ).hexdigest(),
        }
        (frozen / "source-identity.json").write_bytes(json_bytes(identity))
        digests = deployment.file_digests(frozen)
        manifest_raw = "".join(
            f"{sha}  {name}\n" for name, sha in digests.items()
        ).encode()
        (frozen / "manifest.sha256").write_bytes(manifest_raw)
        # 第二次完整断言在全部临时编译后、创建任何输出前完成。
        if assert_current_site(site) != expected:
            raise BundleInputError(
                "site_changed_during_build", expected_site_fields(site)
            )
        target.mkdir(mode=0o700, parents=True, exist_ok=False)
        with tarfile.open(target / "payload.tar", "w") as archive:
            for path in sorted(frozen.rglob("*")):
                info = archive.gettarinfo(
                    str(path), path.relative_to(frozen).as_posix()
                )
                if not (info.isfile() or info.isdir()):
                    raise ValueError("bundle_member_type")
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = "root"
                info.mode = 0o755 if path.is_dir() or info.mode & 0o111 else 0o644
                if path.is_file():
                    with path.open("rb") as stream:
                        archive.addfile(info, stream)
                else:
                    archive.addfile(info)
        payload = (target / "payload.tar").read_bytes()
        payload_sha = hashlib.sha256(payload).hexdigest()
        manifest_sha = hashlib.sha256(manifest_raw).hexdigest()
        runner = render_runner(
            payload,
            payload_sha,
            manifest_sha,
            files=len(digests),
            directories=sum(path.is_dir() for path in frozen.rglob("*")),
        )
        (target / "run-live.sh").write_text(runner)
        (target / "run-live.sh").chmod(0o700)
        (target / "REVIEW.md").write_text(
            review_text(
                target,
                payload_sha,
                manifest_sha,
                start.isoformat(),
                end.isoformat(),
                not (
                    network_input["owner_network_applicable"]
                    and network_input["owner_window_confirmed"]
                ),
            )
        )
    hashes = deployment.file_digests(target)
    (target / "SHA256SUMS").write_text(
        "".join(f"{sha}  {name}\n" for name, sha in hashes.items())
    )
    return hashes
