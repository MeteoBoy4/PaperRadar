#!/usr/bin/env python3
"""显式Live v2私有审阅包;不执行sudo/认证/网络/接收/激活。"""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
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
    parser.add_argument("--upgrade-from-manifest", help="配对的旧成员清单文件SHA。")
    args = parser.parse_args()
    from paper_radar.live_evidence.live_bundle import (
        BundleInputError,
        assert_current_site,
        build_live_bundle,
        derive_site,
        proposed_window,
    )
    from paper_radar.live_evidence.receipt import canonical_bytes
    from paper_radar.live_evidence.sealed_runtime import SiteConfiguration

    try:
        if os.geteuid() == 0:
            raise ValueError("build_requires_unprivileged_user")
        raw = args.baseline.read_bytes()
        if hashlib.sha256(raw).hexdigest() != args.baseline_sha256:
            raise ValueError("baseline_identity")
        baseline = SiteConfiguration.model_validate_json(raw)
        derived, changes = derive_site(baseline)
        print(json.dumps({"baseline_diff": changes}, ensure_ascii=False, indent=2))
        print(derived.model_dump_json(indent=2))
        if args.action == "derive":
            start, end = proposed_window(datetime.now(UTC))
            print(
                json.dumps(
                    {
                        "window_candidate_not_confirmed": {
                            "starts_at": start.isoformat(),
                            "ends_at": end.isoformat(),
                        }
                    }
                )
            )
            descriptor = os.open(
                args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(canonical_bytes(derived))
            print("派生配置仅供私有审阅；日期/网络仍待本人确认，尚未封印或部署。")
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
            upgrade_from=(args.upgrade_from_payload, args.upgrade_from_manifest)
            if args.upgrade_from_payload
            else None,
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
    except (ValueError, OSError, subprocess.SubprocessError):
        parser.exit(
            2,
            "Live构建拒绝 [build_invalid]；请核对基线SHA、最新派生字段、"
            "显式时区窗口及尚不存在的输出。\n",
        )


if __name__ == "__main__":
    raise SystemExit(main())
