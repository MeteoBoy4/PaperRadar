"""真实进程通过管道握手停在锁内或已提交 started 后。"""

import os
import selectors
import subprocess
import sys
from pathlib import Path

SCRIPT = """
import json
import socket
import sys
from pathlib import Path
import httpx
from paper_radar.fixture_audit import FixtureAudit
from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
from tests.audit_sampling_support import CODE, SamplingClock
from tests.audit_matrix_support import MatrixSources
mode, database, root, plan = sys.argv[1:]
if mode == "resume":
    sources = MatrixSources()
    clock = SamplingClock()
    def handler(request):
        if (request.url.host == "agupubs.onlinelibrary.wiley.com"
            and "/doi/" in request.url.path):
            print("http-started", flush=True)
            sys.stdin.readline()
        return sources(request)
    executor = SourceHTTPExecutor(transport=httpx.MockTransport(handler),
        monotonic=clock.monotonic, sleep=clock.sleep)
    service = FixtureAudit(Path(database), Path(root),
        source_executors={"http": executor})
    service.resume_audit(plan, contact_email="process@example.org", code_identity=CODE)
    print("complete", flush=True)
elif mode == "lock":
    service = FixtureAudit(Path(database), Path(root), source_executors={})
    with service.audit_execution(plan):
        print("locked", flush=True)
        sys.stdin.readline()
else:
    def forbidden(*args, **kwargs):
        raise RuntimeError("unexpected network")
    socket.socket.connect = forbidden
    service = FixtureAudit(Path(database), Path(root), source_executors={})
    result = service.replay_audit(plan)
    print(json.dumps({"status": result.status,
        "semantic_sha256": result.semantic_sha256}), flush=True)
"""


def spawn(
    script: Path, mode: str, database: Path, root: Path, plan: str
) -> subprocess.Popen[str]:
    script.write_text(SCRIPT)
    environment = {**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)}
    return subprocess.Popen(
        [sys.executable, str(script), mode, str(database), str(root), plan],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=script.parent,
        env=environment,
    )


def handshake(process: subprocess.Popen[str]) -> str:
    assert process.stdout is not None
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        assert selector.select(timeout=15), "child handshake timeout"
        value = process.stdout.readline().strip()
    return value


def finish(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.kill()
    process.wait(timeout=10)
    for stream in (process.stdin, process.stdout):
        if stream:
            stream.close()
