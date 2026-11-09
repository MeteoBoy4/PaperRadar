#!/usr/bin/env python3
"""非特权封印构建入口;真实sudo与激活始终由所有者执行。"""

import argparse
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="构建可供所有者审阅的β采集器、冻结runtime与部署/卸载脚本；不执行部署。"
    )
    parser.add_argument(
        "--site", type=Path, required=True, help="所有者明确选择的本地站点配置JSON。"
    )
    parser.add_argument(
        "--starts-at", required=True, help="批准窗口起点，必须含UTC时区。"
    )
    parser.add_argument(
        "--ends-at", required=True, help="批准窗口终点，必须含UTC时区。"
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="尚不存在的私有审阅目录。"
    )
    parser.add_argument("--upgrade-from-payload", help="明确审阅的旧payload SHA256。")
    parser.add_argument(
        "--upgrade-from-manifest",
        help="明确审阅的旧manifest文件SHA256；必须与旧payload配对。",
    )
    args = parser.parse_args()
    if bool(args.upgrade_from_payload) != bool(args.upgrade_from_manifest):
        parser.error("升级必须同时提供旧payload与manifest SHA256。")
    from paper_radar.live_evidence.deployment import build_deployment
    from paper_radar.live_evidence.sealed_runtime import SiteConfiguration

    try:
        site = SiteConfiguration.model_validate_json(args.site.read_bytes())
        hashes = build_deployment(
            args.output.absolute(),
            site,
            starts_at=datetime.fromisoformat(args.starts_at),
            ends_at=datetime.fromisoformat(args.ends_at),
            source_root=Path(__file__).resolve().parents[1],
            upgrade_from=(args.upgrade_from_payload, args.upgrade_from_manifest)
            if args.upgrade_from_payload
            else None,
        )
    except (ValueError, OSError):
        parser.exit(
            2,
            "封印构建拒绝 [build_invalid]；"
            "请核对非特权身份、站点配置、UTC窗口与新输出目录。\n",
        )
    for name, digest in hashes.items():
        print(f"{digest}  {name}")
    print("封印包已生成；请审阅REVIEW.md与确切SHA256，尚未部署、接收或证据激活。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
