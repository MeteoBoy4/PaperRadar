"""父启动器仅做路径元数据/打开关闭正对照,业务读取只在受限 worker。"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from paper_radar.replay.container import check_layout, safe_path
from paper_radar.replay.contract import ReplayError, ReplaySummary
from paper_radar.replay.isolation import ReplayBoundary, runtime_paths


def replay(root: Path, originals: tuple[Path, ...]) -> dict[str, Any]:
    links: list[Path] = []
    try:
        root = check_layout(root)
        if len(originals) < 4:
            raise ReplayError("invalid_arguments")
        protected = tuple(safe_path(path) for path in originals)
        dependencies = runtime_paths()
        for path in protected:
            if path == root or path.is_relative_to(root):
                raise ReplayError("unsafe_layout")
            if any(
                path == dependency
                or path.is_relative_to(dependency)
                or dependency.is_relative_to(path)
                for dependency in dependencies
            ):
                raise ReplayError("unsafe_layout")
        probes = []
        for index, path in enumerate(protected):
            # 打开后立即关闭,不 read,不遍历材料,更不接触认证文件内容。
            exists = path.exists()
            if exists:
                descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
                os.close(descriptor)
            link = root / "views" / f".replay-escape-{index}"
            if link.exists() or link.is_symlink():
                raise ReplayError("unsafe_layout")
            link.symlink_to(path, target_is_directory=path.is_dir())
            links.append(link)
            probes.append({"path": str(path), "link": str(link), "exists": exists})
        process = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                str(Path(__file__).with_name("worker.py")),
                str(root),
                json.dumps(probes),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=root / "contents",
            env={},
            close_fds=True,
            pass_fds=(),
            preexec_fn=ReplayBoundary(root, dependencies),
            timeout=120,
            check=False,
        )
        try:
            result = json.loads(process.stdout)
        except (ValueError, UnicodeError):
            raise ReplayError("isolation_verification_failed") from None
        if not isinstance(result, dict):
            raise ReplayError("isolation_verification_failed")
        if process.returncode != 0:
            raise ReplayError(str(result.get("reason", "replay_failed")))
        try:
            return ReplaySummary.model_validate(result).model_dump()
        except ValidationError:
            raise ReplayError("isolation_verification_failed") from None
    except ReplayError:
        raise
    except subprocess.SubprocessError:
        raise ReplayError("isolation_unavailable") from None
    except (OSError, ValueError, RuntimeError):
        raise ReplayError("unsafe_layout") from None
    finally:
        for link in links:
            link.unlink(missing_ok=True)
