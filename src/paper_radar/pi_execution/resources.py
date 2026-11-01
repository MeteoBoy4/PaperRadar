"""领取前只读资源检查与领取后独占的 attempt 资源。"""

import json
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from paper_radar.pi_execution.errors import ExecutionError

EXECUTION_CWD = Path("/srv/pi-cwd")
LAUNCH_POLICY_VERSION = "pi-launch-1.4.0-v1"
# Default settings bytes are part of LAUNCH_POLICY_VERSION.
SETTINGS_JSON = (
    b'{"cacheWarming":"off","compaction":{"enabled":false},'
    b'"defaultProjectTrust":"never","enableInstallTelemetry":false,'
    b'"retry":{"enabled":false,"provider":{"maxRetries":0}}}\n'
)


@dataclass(frozen=True, slots=True)
class ExecutionRoots:
    data_root: Path
    config_root: Path
    material_root: Path
    install_root: Path

    def outside(self, path: Path) -> bool:
        candidate = path.resolve()
        return all(
            not candidate.is_relative_to(root.resolve())
            and not root.resolve().is_relative_to(candidate)
            for root in (
                self.data_root,
                self.config_root,
                self.material_root,
                self.install_root,
            )
        )


def _no_symlinks(path: Path) -> bool:
    return path.is_absolute() and not any(
        part.is_symlink() for part in (path, *path.parents)
    )


def check_cwd() -> Path:
    try:
        if not _no_symlinks(EXECUTION_CWD) or not stat.S_ISDIR(
            EXECUTION_CWD.lstat().st_mode
        ):
            raise ExecutionError("cwd_invalid")
        if any(EXECUTION_CWD.iterdir()):
            raise ExecutionError("cwd_not_empty")
    except OSError:
        raise ExecutionError("cwd_invalid") from None
    return EXECUTION_CWD


def expected_cwd_section() -> str:
    """由启动策略定义的唯一外发 cwd 段;非现场通过事实。"""
    return f"<cwd>\n{EXECUTION_CWD}\n</cwd>"


def check_system_prompt(prompt: bytes) -> str:
    try:
        text = prompt.decode("utf-8")
    except (UnicodeError, AttributeError):
        raise ExecutionError("system_prompt_invalid") from None
    if not text or "\x00" in text:
        raise ExecutionError("system_prompt_invalid")
    if len(prompt) + 1 > 131072:
        raise ExecutionError("argv_limit")
    if text.startswith("/") or text.split("/", 1)[0] in {".", ".."}:
        raise ExecutionError("system_prompt_path")
    return text


def check_auth_mode(provider: str, auth_mode: str) -> None:
    """声明式通道闭集判定;不读取凭据或连接认证执行。"""
    if auth_mode != "chatgpt_subscription" or provider != "openai":
        raise ExecutionError("auth_mode_unsupported")


def check_credentials_metadata(directory: Path) -> None:
    """只核对元数据,绝不读取 auth 内容或刷新;不证明与执行根隔离。"""
    try:
        info = directory.lstat()
        auth = directory / "auth.json"
        if (
            not _no_symlinks(directory)
            or not stat.S_ISDIR(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o700
            or info.st_uid != os.getuid()
            or not stat.S_ISREG(auth.lstat().st_mode)
            or auth.lstat().st_uid != os.getuid()
        ):
            raise ExecutionError("credentials_invalid")
    except OSError:
        raise ExecutionError("credentials_invalid") from None


def check_credentials_directory(directory: Path, roots: ExecutionRoots) -> None:
    """执行路径额外核对显式业务根;doctor 没有这些根的选择权。"""
    check_credentials_metadata(directory)
    if not roots.outside(directory):
        raise ExecutionError("credentials_invalid")


def proxy_port(proxy: str | None) -> int | None:
    if proxy is None:
        return None
    try:
        parts = urlsplit(proxy)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or parts.port == 0
            or any(c.isspace() for c in proxy)
            or parts.query
            or parts.fragment
            or parts.path not in {"", "/"}
        ):
            raise ExecutionError("proxy_invalid")
        return parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        raise ExecutionError("proxy_invalid") from None


class AttemptResources:
    """只删除自己 mkdtemp 登记的所有权单元。"""

    def __init__(self, roots: ExecutionRoots, proxy: str | None) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="paper-radar-pi-", dir="/tmp"))
        try:
            if not roots.outside(self.root):
                raise ExecutionError("resources_invalid")
            self.home = self.root / "home"
            self.tmp = self.root / "tmp"
            self.agent = self.root / "agent"
            for directory in (self.home, self.tmp, self.agent):
                directory.mkdir(mode=0o700)
            settings = json.loads(SETTINGS_JSON)
            if proxy is not None:
                settings["httpProxy"] = proxy
            (self.agent / "settings.json").write_text(
                json.dumps(settings, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        try:
            shutil.rmtree(self.root)
        except FileNotFoundError:
            return
        except OSError:
            raise ExecutionError("cleanup_failed") from None
