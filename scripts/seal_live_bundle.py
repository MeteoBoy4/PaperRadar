#!/usr/bin/env python3
"""显式Live v2私有审阅包;不执行sudo/认证/网络/接收/激活。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from paper_radar.live_evidence.epoch_lineage import EpochUpgrade


class SealArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.exit(
            2, "Live构建拒绝 [arguments_invalid]；参数无效，请使用--help核对输入。\n"
        )


def read_epoch_candidate(
    runtime: Path | None,
    epoch_source: Path | None,
    explicit_pair: tuple[str, str] | None,
) -> tuple[tuple[str, str] | None, EpochUpgrade | None]:
    """只从原runtime和epoch原字节派生;不接受自由部署时点,不赋予root信任。"""
    if bool(runtime) != bool(epoch_source):
        raise ValueError("epoch_upgrade_inputs_missing")
    if runtime is None or epoch_source is None:
        if explicit_pair is not None:
            raise ValueError("epoch_upgrade_required")
        return None, None
    from paper_radar.live_evidence.epoch_lineage import describe_epoch_upgrade

    descriptor = describe_epoch_upgrade(runtime, epoch_source.read_bytes())
    pair = (descriptor.payload_sha256, descriptor.runtime_manifest_sha256)
    if explicit_pair is not None and explicit_pair != pair:
        raise ValueError("epoch_upgrade_source")
    return pair, descriptor


def main() -> int:
    parser = SealArgumentParser(
        description="派生或构建新的Live私有封印包；旧β封印入口保持独立。"
    )
    parser.add_argument("action", choices=("derive", "build"))
    parser.add_argument(
        "--baseline", type=Path, required=True, help="所有者选定的私有基线。"
    )
    parser.add_argument(
        "--baseline-sha256", required=True, help="基线完整SHA256，必须逐字匹配。"
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="尚不存在的私有配置文件或审阅目录。"
    )
    parser.add_argument("--site", type=Path, help="build时经所有者审阅的派生site。")
    parser.add_argument(
        "--network",
        type=Path,
        help="build时所有者网络适用性/窗口声明JSON；pending仍保留现场gate。",
    )
    parser.add_argument("--starts-at", help="显式时区起点。")
    parser.add_argument("--ends-at", help="显式时区终点；共同窗口至少7天。")
    parser.add_argument(
        "--upgrade-from-payload",
        help="本地旧封印payload候选SHA；实际root状态由部署入口核。",
    )
    parser.add_argument(
        "--upgrade-from-manifest", help="配对的旧成员清单文件SHA；须有原epoch来源。"
    )
    parser.add_argument(
        "--epoch-from-runtime",
        type=Path,
        help="build升版时只读原runtime，派生旧payload/manifest和连续性候选。",
    )
    parser.add_argument(
        "--epoch-source",
        type=Path,
        help="配对的原部署epoch原字节文件；沿用原UTC，不接受手抄deployed_at。",
    )
    parser.add_argument(
        "--failed-preparation-runtime",
        type=Path,
        help="build时明确只读原失败preparing的封印runtime；仅派生有限退休描述，部署时重新认证。",
    )
    args = parser.parse_args()
    from paper_radar.live_evidence.live_bundle import (
        BundleInputError,
        assert_current_site,
        build_live_bundle,
        derive_site,
    )
    from paper_radar.live_evidence.receipt import canonical_bytes
    from paper_radar.live_evidence.sealed_runtime import SiteConfiguration

    try:
        if os.geteuid() == 0:
            raise ValueError("build_requires_unprivileged_user")
        if bool(args.upgrade_from_payload) != bool(args.upgrade_from_manifest):
            raise ValueError("build_inputs_missing")
        explicit_pair = (
            (args.upgrade_from_payload, args.upgrade_from_manifest)
            if args.upgrade_from_payload
            else None
        )
        if args.action == "derive" and (
            args.epoch_from_runtime
            or args.epoch_source
            or explicit_pair
            or args.failed_preparation_runtime
        ):
            raise ValueError("epoch_upgrade_build_only")
        upgrade_from, epoch_upgrade = read_epoch_candidate(
            args.epoch_from_runtime, args.epoch_source, explicit_pair
        )
        raw = args.baseline.read_bytes()
        if hashlib.sha256(raw).hexdigest() != args.baseline_sha256:
            raise ValueError("baseline_identity")
        baseline = SiteConfiguration.model_validate_json(raw)
        derived, changes = derive_site(baseline)
        print(json.dumps({"baseline_diff": changes}, ensure_ascii=False, indent=2))
        print(derived.model_dump_json(indent=2))
        if args.action == "derive":
            if bool(args.starts_at) != bool(args.ends_at):
                raise ValueError("plan_window_invalid")
            window = None
            if args.starts_at:
                start = datetime.fromisoformat(args.starts_at)
                end = datetime.fromisoformat(args.ends_at)
                if start.tzinfo is None or end.tzinfo is None or start >= end:
                    raise ValueError("plan_window_invalid")
                window = {"starts_at": start.isoformat(), "ends_at": end.isoformat()}
            print(json.dumps({"explicit_window_not_reconfirmed": window}))
            descriptor = os.open(
                args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(canonical_bytes(derived))
            print(
                "派生配置仅供私有审阅；窗口须显式给定并沿用所有者确认原值，不能按当前日滚动；尚未封印或部署。"
            )
            return 0
        if not all((args.site, args.network, args.starts_at, args.ends_at)) or bool(
            args.upgrade_from_payload
        ) != bool(args.upgrade_from_manifest):
            raise ValueError("build_inputs_missing")
        site = SiteConfiguration.model_validate_json(args.site.read_bytes())
        assert_current_site(site)
        if canonical_bytes(site) != canonical_bytes(derived):
            # 只允许五字段派生,不让build入口顺手换根/模型/uid。
            raise ValueError("derived_site_changed")
        hashes = build_live_bundle(
            args.output.absolute(),
            site,
            starts_at=datetime.fromisoformat(args.starts_at),
            ends_at=datetime.fromisoformat(args.ends_at),
            source_root=Path(__file__).resolve().parents[1],
            network_input=json.loads(args.network.read_bytes()),
            upgrade_from=upgrade_from,
            epoch_upgrade=epoch_upgrade,
            failed_preparation_runtime=args.failed_preparation_runtime,
        )
        for name, sha in hashes.items():
            print(f"{sha}  {name}")
        print("私有封印包已生成；请审阅确切归档/成员SHA；未部署、接收或激活。")
        return 0
    except BundleInputError as error:
        parser.exit(
            2,
            "Live构建拒绝 ["
            + str(error)
            + "]；expected="
            + json.dumps(error.expected, sort_keys=True)
            + "；重新派生并审阅输入。\n",
        )
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        reason = (
            str(error)
            if type(error) is ValueError
            and str(error)
            in {
                "build_inputs_missing",
                "epoch_upgrade_required",
                "epoch_upgrade_inputs_missing",
                "epoch_upgrade_source",
                "epoch_upgrade_build_only",
            }
            else "build_invalid"
        )
        parser.exit(
            2,
            f"Live构建拒绝 [{reason}]；请核对基线SHA、最新派生字段、"
            "显式时区窗口、原runtime/epoch来源及尚不存在的输出。\n",
        )


if __name__ == "__main__":
    raise SystemExit(main())
