"""#153 独立冷进程哨兵;禁止 SDK、网络、子进程和业务写入。"""

import builtins
import importlib
import importlib.metadata
import importlib.util
import json
import os
import sys
from typing import Any

_SDK_ROOTS = {
    "docling",
    "docling_core",
    "docling_ibm_models",
    "docling_parse",
    "torch",
    "torchvision",
    "transformers",
    "pypdfium2",
    "cv2",
    "huggingface_hub",
}


_import = builtins.__import__
_import_module = importlib.import_module


def deny_import(name: str, *args: Any, **kwargs: Any) -> Any:
    if name.partition(".")[0] in _SDK_ROOTS:
        os._exit(97)
    return _import(name, *args, **kwargs)


def deny_import_module(name: str, package: str | None = None) -> Any:
    if name.partition(".")[0] in _SDK_ROOTS:
        os._exit(97)
    return _import_module(name, package)


builtins.__import__ = deny_import
importlib.import_module = deny_import_module


def guard(event: str, args: tuple[object, ...]) -> None:
    if (
        event.startswith(
            ("socket.", "subprocess.", "os.exec", "os.spawn", "os.posix_spawn")
        )
        or event
        in {
            "os.system",
            "os.fork",
            "os.forkpty",
            "pty.spawn",
            "os.mkdir",
            "os.remove",
            "os.rename",
        }
        or (event == "sqlite3.connect" and os.environ.get("DOCLING_HELP_ONLY") == "1")
    ):
        os._exit(97)
    if event == "open":
        path, _mode, flags = args
        if isinstance(path, str) and path.endswith(("-wal", "-shm", "-journal")):
            return  # 只读 SQLite 既有 sidecar 例外。
        if isinstance(flags, int) and flags & (
            os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC
        ):
            os._exit(97)


sys.addaudithook(guard)

facts = os.environ.get("DOCLING_FACTS")
if facts:
    import platform
    import sysconfig

    inventory = json.loads(facts)
    platform.system = lambda: inventory["system"]
    platform.machine = lambda: "x86_64"
    os.confstr = lambda _name: inventory["libc"]
    sysconfig.get_config_var = lambda _name: 0

    def version(distribution_name: str) -> str:
        if distribution_name not in inventory["versions"]:
            raise importlib.metadata.PackageNotFoundError(distribution_name)
        return str(inventory["versions"][distribution_name])

    def find_spec(name: str) -> object | None:
        if "." in name:
            os._exit(97)
        return object() if name in inventory["modules"] else None

    importlib.metadata.version = version
    importlib.util.find_spec = find_spec  # type: ignore[assignment]

if os.environ.get("DOCLING_FORBID_PROBE") == "1":

    def forbid_probe(*_args: object, **_kwargs: object) -> Any:
        os._exit(97)

    importlib.metadata.version = forbid_probe
    importlib.util.find_spec = forbid_probe
