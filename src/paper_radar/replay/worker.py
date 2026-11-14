"""已经 exec 进入 OS 边界的 worker:先自证,再延迟导入业务链。"""

import ctypes
import errno
import hashlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from paper_radar.replay.contract import ReplayError


def denied(path: Path, exists: bool) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
    except OSError as error:
        if error.errno == errno.EACCES or (not exists and error.errno == errno.ENOENT):
            return
        raise ReplayError("isolation_verification_failed") from None
    os.close(descriptor)
    raise ReplayError("isolation_verification_failed")


def selftest(root: Path, probes: list[dict[str, Any]]) -> dict[str, object]:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(39, 0, 0, 0, 0) != 1 or libc.prctl(21, 0, 0, 0, 0) != 2:
        raise ReplayError("isolation_verification_failed")
    # 恢复正例必须真正可读;原件与逃逸链接都须由当前进程自己拒绝。
    try:
        with (root / "contents/manifest.json").open("rb") as stream:
            if not stream.read(1):
                raise ReplayError("invalid_manifest")
    except FileNotFoundError:
        raise ReplayError("file_missing") from None
    except OSError:
        raise ReplayError("isolation_verification_failed") from None
    for probe in probes:
        denied(Path(probe["path"]), probe["exists"])
        denied(Path(probe["link"]), probe["exists"])
    for family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX):
        try:
            with socket.socket(family, socket.SOCK_STREAM):
                pass
        except OSError as error:
            if error.errno == errno.EPERM:
                continue
        raise ReplayError("isolation_verification_failed")
    # 直接调用 connect,EPERM 必须先于无效 fd 的 EBADF;不靠 HTTP 失败。
    if libc.connect(-1, None, 0) != -1 or ctypes.get_errno() != errno.EPERM:
        raise ReplayError("isolation_verification_failed")
    try:
        descriptor = os.open(
            root / "contents/.replay-write-probe",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except OSError as error:
        if error.errno != errno.EACCES:
            raise ReplayError("isolation_verification_failed") from None
    else:
        os.close(descriptor)
        raise ReplayError("isolation_verification_failed")
    output_probe = root / "views" / f".replay-write-{os.getpid()}"
    try:
        with output_probe.open("xb") as stream:
            stream.write(b"synthetic-isolation-check")
        output_probe.unlink()
    except OSError:
        raise ReplayError("isolation_verification_failed") from None
    return {
        "isolation": "verified",
        "originals_denied": sum(bool(p["exists"]) for p in probes),
        "missing_originals": sum(not p["exists"] for p in probes),
        "sockets_denied": 3,
        "direct_connect_denied": True,
    }


def business(root: Path) -> dict[str, int]:
    def guard(event: str, args: tuple[object, ...]) -> None:
        if event in {"subprocess.Popen", "os.system", "os.posix_spawn"}:
            raise ReplayError("replay_failed")
        if (
            event == "import"
            and args
            and str(args[0]).split(".")[0]
            in {"docling", "torch", "openai", "anthropic", "pypdfium2"}
        ):
            raise ReplayError("replay_failed")

    # 业务阶段不启动执行器,不依赖 SDK 或模型缓存;实际禁网来自 OS 边界。
    sys.addaudithook(guard)
    from paper_radar.backup.service import verify_contents
    from paper_radar.body import BodyService
    from paper_radar.experiment.exposure import Exposures
    from paper_radar.experiment.reports import Reports
    from paper_radar.read_tasks import ReadTaskError, ReadTasks
    from paper_radar.replay.container import check_layout, verify_receipt
    from paper_radar.runtime_logging import FileSink

    check_layout(root)
    manifest = verify_receipt(root)
    contents, output = root / "contents", root / "views"
    database = contents / "database.sqlite3"
    verify_contents(contents, manifest)
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    sink = FileSink(output)
    reports = Reports(database, contents, output, sink=sink)
    report_count = 0
    expected: set[Path] = set()
    for inputs in reports.history():
        original = reports.receipt(inputs.report_id)
        if (output / inputs.relative_path).exists():
            reports.verify(inputs.report_id)
        if (
            reports.rebuild(inputs.report_id) != original
            or reports.verify(inputs.report_id) != original
        ):
            raise ReplayError("content_corrupt")
        expected.add(output / inputs.relative_path)
        report_count += 1
    reads = ReadTasks(database, contents, sink=sink)
    analyses = evidence_slices = 0
    experiment = BodyService(database, contents).root().purpose.value == "experiment"
    for paper in reads.analysis_papers():
        for key in reads.analysis_ids(paper):
            analysis = reads.analysis(key)
            loaded = reads.artifacts.load(
                analysis.artifact_id,
                expected_identity=analysis.identity,
                expected_language=analysis.output.output_language,
            )
            for item in loaded.context.replay():
                # orig 与位置来自持久 evidence-map; load 已验证全部定位。
                source = next(
                    s
                    for s in loaded.context.source_blocks
                    if s.source_id == item.provenance.source_id
                )
                if (
                    item.text.encode()
                    != source.orig[item.provenance.start : item.provenance.end].encode()
                ):
                    raise ReplayError("registration_invalid")
                evidence_slices += 1
            if experiment:
                try:
                    reads.analysis(key, ordinary=True)
                except ReadTaskError as error:
                    if error.reason not in {
                        "ordinary_consumption_denied",
                        "root_purpose_rejected",
                    }:
                        raise
                else:
                    raise ReplayError("registration_invalid")
            analyses += 1
    exposures = Exposures(database, contents, sink=sink)
    ids = exposures.history()
    for key in ids:
        receipt = exposures.write(key, output)
        path = output / str(receipt["relative_path"])
        if path.read_bytes() != exposures.payload(key):
            raise ReplayError("content_corrupt")
        expected.add(path)
    # 独立输出同样闭合:不接受任意自由文件、未知空目录、链接或旧内容。
    actual = {p for p in output.rglob("*")}
    allowed = expected | {
        parent
        for p in expected
        for parent in p.parents
        if parent != output and parent.is_relative_to(output)
    }
    if actual != allowed:
        raise ReplayError("unexpected_entry")
    verify_contents(contents, manifest)
    if hashlib.sha256(database.read_bytes()).hexdigest() != before:
        raise ReplayError("database_invalid")
    return {
        "reports": report_count,
        "analyses": analyses,
        "evidence_slices": evidence_slices,
        "exposures": len(ids),
    }


def main() -> int:
    try:
        root, probes = Path(sys.argv[1]), json.loads(sys.argv[2])
        result = selftest(root, probes)
        if len(sys.argv) > 3:
            print(json.dumps(result))
            return 0
        child = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                __file__,
                str(root),
                sys.argv[2],
                "--selftest",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={},
            close_fds=True,
            pass_fds=(),
            timeout=20,
            check=False,
        )
        if child.returncode != 0 or json.loads(child.stdout) != result:
            raise ReplayError("isolation_verification_failed")
        result["descendant"] = "verified"
        for probe in probes:
            Path(probe["link"]).unlink()
        result.update(business(root))
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        reason = getattr(error, "reason", "replay_failed")
        print(json.dumps({"reason": ReplayError(str(reason)).reason}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
