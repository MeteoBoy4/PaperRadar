"""小型官方形状材料,真实 SQLite/目录;fake 只替代下载和程序。"""

import base64
import hashlib
import io
import json
import tarfile
from pathlib import Path
from typing import Any

from paper_radar.config import compile_config
from paper_radar.pi_supply import prepare_supply
from paper_radar.pi_supply.models import PrepareResult
from tests.config_adapter_support import adapter_inputs

PI = "1.3.0"
NODE = "22.19.0"
NPM = "10.9.3"
PACKAGE_NAME = "@earendil-works/pi-coding-agent"


def encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def node_archive(extra: tuple[str, bytes] | None = None) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:xz") as archive:
        files = {
            "bin/node": b"synthetic executable",
            "lib/node_modules/npm/bin/npm-cli.js": b"synthetic npm",
        }
        if extra:
            files[extra[0]] = extra[1]
        for name, content in files.items():
            item = tarfile.TarInfo(f"node-v{NODE}-linux-x64/{name}")
            item.size = len(content)
            item.mode = 0o755 if name == "bin/node" else 0o644
            archive.addfile(item, io.BytesIO(content))
    return stream.getvalue()


class Download:
    def __init__(self) -> None:
        archive = node_archive()
        self.node_sha256 = hashlib.sha256(archive).hexdigest()
        integrity = "sha512-" + base64.b64encode(bytes(range(64))).decode()
        package: dict[str, Any] = {
            "name": "pi-install",
            "version": PI,
            "dependencies": {PACKAGE_NAME: PI},
            "overrides": {"protobufjs": "7.6.6"},
            "engines": {"node": ">=22.19.0"},
        }
        resolved = f"https://registry.npmjs.org/{PACKAGE_NAME}/-/pi-{PI}.tgz"
        lock = {
            "name": "pi-install",
            "version": PI,
            "lockfileVersion": 3,
            "packages": {
                "": package,
                "node_modules/" + PACKAGE_NAME: {
                    "version": PI,
                    "resolved": resolved,
                },
            },
        }
        release = {
            "schemaVersion": 1,
            "version": PI,
            "packages": [
                {
                    "name": PACKAGE_NAME,
                    "version": PI,
                    "tarball": resolved,
                    "integrity": integrity,
                }
            ],
        }
        base = f"https://pi.dev/api/installer/releases/{PI}"
        node_base = f"https://nodejs.org/dist/v{NODE}"
        self.content = {
            base: encoded(release),
            base + "/package.json": encoded(package),
            base + "/package-lock.json": encoded(lock),
            node_base + f"/node-v{NODE}-linux-x64.tar.xz": archive,
            node_base + "/SHASUMS256.txt": (
                f"{self.node_sha256}  node-v{NODE}-linux-x64.tar.xz\n"
            ).encode(),
        }
        self.calls: list[str] = []

    def fetch(self, url: str, *, limit: int, proxy: str | None) -> bytes:
        self.calls.append(url)
        raw = self.content[url]
        assert len(raw) <= limit
        return raw


class Run:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], Path, dict[str, str]]] = []

    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout: int,
        limit: int,
    ) -> bytes:
        self.calls.append((argv, cwd, env))
        if "ci" in argv:
            package = cwd / "node_modules" / PACKAGE_NAME
            package.mkdir(parents=True)
            (package / "package.json").write_bytes(
                encoded(
                    {
                        "name": PACKAGE_NAME,
                        "version": PI,
                        "bin": {"pi": "dist/cli.js"},
                        "engines": {"node": ">=22.19.0"},
                    }
                )
            )
            (package / "dist").mkdir()
            (package / "dist/cli.js").write_bytes(b"synthetic Pi entry")
            return b"installed"
        if argv[-1] == "--help":
            return b"Pi help"
        if "npm-cli.js" in argv[1]:
            return (NPM + "\n").encode()
        if len(argv) == 2:
            return ("v" + NODE + "\n").encode()
        return (PI + "\n").encode()


def inputs(root: Path) -> tuple[Path, str, Path, Download, Run]:
    settings, adapter, database = adapter_inputs(root)
    adapter.write_text(adapter.read_text().replace("1.1.0", PI))
    snapshot = compile_config(settings, database)
    download = Download()
    request = root / "request.json"
    (root / "evidence.txt").write_bytes(b"First supply; upstream reviewed.\n")
    request.write_bytes(
        encoded(
            {
                "format_version": 1,
                "node_version": NODE,
                "npm_version": NPM,
                "node_source": "nodejs.org",
                "node_sha256": download.node_sha256,
                "platform": {"os": "linux", "arch": "x86_64", "libc": "glibc"},
                "d5": {
                    "decision": "unknown",
                    "basis": "First supply, no baseline",
                    "baseline_supply_id": None,
                    "evidence": [{"kind": "evidence_file", "path": "evidence.txt"}],
                },
            }
        )
    )
    return database, snapshot.snapshot_id, request, download, Run()


def prepare(
    root: Path,
    source: tuple[Path, str, Path, Download, Run],
) -> PrepareResult:
    database, snapshot, request, download, run = source
    return prepare_supply(
        database,
        snapshot,
        "screening",
        request,
        root / "install",
        data_root=root / "data",
        config_root=root / "config",
        material_root=root / "materials",
        downloader=download,
        runner=run,
    )
