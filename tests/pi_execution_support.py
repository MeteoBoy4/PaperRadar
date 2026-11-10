"""合成固定供给:Python 标准库对端替代 Node/Pi,不触及真实凭据。"""

import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from paper_radar.llm.models import CallDescription
from paper_radar.pi_execution import ExecutionRoots
from paper_radar.pi_supply import activate_supply
from tests import pi_supply_support

TOKEN = "oauth-test-only-sensitive-sentinel"


class PeerRun(pi_supply_support.Run):
    def __init__(self, peer: str) -> None:
        super().__init__()
        self.peer = peer

    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout: int,
        limit: int,
        pass_fds: tuple[int, ...] = (),
    ) -> bytes:
        output = super().run(
            argv, cwd=cwd, env=env, timeout=timeout, limit=limit, pass_fds=pass_fds
        )
        if "ci" in argv:
            node = cwd.parent / "node/bin/node"
            node.chmod(0o755)
            shutil.copyfile(Path(sys.executable).resolve(), node)
            (
                cwd / "node_modules/@earendil-works/pi-coding-agent/dist/cli.js"
            ).write_text(self.peer)
        return output


PEER = """
import json, os, sys, time
from pathlib import Path
args = sys.argv[1:]
if args[:2] == ['auth', 'print-bearer-token']:
    agent = Path(os.environ['PI_CODING_AGENT_DIR'])
    config = json.loads((agent / 'auth.json').read_text())
    (agent / 'auth-observed.json').write_text(json.dumps({
        'argv': args, 'env': dict(os.environ), 'cwd': os.getcwd(),
    }))
    if config.get('mode') == 'timeout':
        time.sleep(5)
    if config.get('mode') == 'failure':
        print(config['token'], file=sys.stderr)
        raise SystemExit(1)
    print(config['token'])
else:
    agent = Path(os.environ['PI_CODING_AGENT_DIR'])
    root = agent.parent
    expected = {
        'PI_CODING_AGENT_DIR': str(agent),
        'PI_SKIP_VERSION_CHECK': '1', 'PI_TELEMETRY': '0', 'PI_OFFLINE': '1',
        'HOME': str(root / 'home'), 'TMPDIR': str(root / 'tmp'),
        'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
        'PATH': str(Path(sys.executable).parent),
        'OPENAI_API_KEY': 'oauth-test-only-sensitive-sentinel',
    }
    protected = []
    for fd in range(3, 256):
        try:
            os.fstat(fd)
            protected.append(fd)
        except OSError:
            pass
    private = {}
    test_root = Path(__TEST_ROOT__)
    for label, path in [
        ('database', test_root / 'db.sqlite3'),
        ('blob', test_root / 'data/blob'),
        ('publisher', test_root / 'publisher-secret'),
        ('personal_pi', test_root / 'personal/.pi/auth.json'),
        ('refresh_credentials', test_root / 'credentials/auth.json'),
    ]:
        try:
            with path.open('rb'):
                private[label] = 'allowed'
        except PermissionError:
            private[label] = 'denied'
    print(json.dumps({
        'node': sys.executable, 'entry': sys.argv[0],
        'private_access': private,
        'cmdline_has_token': b'oauth-test-only-sensitive-sentinel' in (
            Path('/proc/self/cmdline').read_bytes()
        ),
        'argv': args, 'env_exact': dict(os.environ) == expected,
        'cwd': os.getcwd(), 'protected': protected,
        'settings': json.loads((agent / 'settings.json').read_text()),
        'agent_files': sorted(p.name for p in agent.iterdir()),
        'root': str(root), 'root_mode': root.stat().st_mode & 511,
        'no_new_privs': 'NoNewPrivs:\\t1' in Path('/proc/self/status').read_text(),
    }), flush=True)
    sys.stdin.buffer.read()
"""


def launch_inputs(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    peer: str = PEER,
) -> tuple[Path, CallDescription, ExecutionRoots, Path, Path]:
    monkeypatch.setattr(pi_supply_support, "PI", "1.4.0")
    source = pi_supply_support.inputs(root)
    (root / "data").mkdir(exist_ok=True)
    (root / "data/blob").write_text("business blob sentinel")
    (root / "publisher-secret").write_text("publisher sentinel")
    personal = root / "personal/.pi"
    personal.mkdir(parents=True)
    (personal / "auth.json").write_text("personal Pi sentinel")
    source = (*source[:4], PeerRun(peer.replace("__TEST_ROOT__", repr(str(root)))))
    prepared = pi_supply_support.prepare(root, source)
    activate_supply(source[0], prepared.supply_id, source[1])
    cwd = root / "cwd"
    cwd.mkdir()
    credentials = root / "credentials"
    credentials.mkdir(mode=0o700)
    (credentials / "auth.json").write_text(json.dumps({"token": TOKEN}))
    monkeypatch.setattr("paper_radar.pi_execution.resources.EXECUTION_CWD", cwd)
    from paper_radar.pi_execution import isolation
    from tests.pi_placement_support import local_placement

    local_placement(monkeypatch)

    monkeypatch.setattr(
        isolation,
        "_RUNTIME_PATHS",
        (*isolation._RUNTIME_PATHS, Path(sys.base_prefix) / "lib/python3.14"),
    )
    description = CallDescription(
        stage="boundary",
        fingerprint="1" * 64,
        projection_id="2" * 64,
        semantic_snapshot_id=source[1],
        audit_snapshot_id=source[1],
        pi_version="1.4.0",
        adapter_version="synthetic-v1",
        protocol_profile="pi-rpc-1.4.0-v1",
        provider="openai",
        model="gpt-test",
        protocol="prompt_only",
        thinking_level="off",
        temperature=0,
        top_p=1,
        policy_json="{}",
        system_prompt=b"Exact system instruction\n",
        stage_input_payload=b"{}",
        user_payload_json="{}",
    )
    return (
        source[0],
        replace(description),
        ExecutionRoots(
            root / "data", root / "config", root / "materials", root / "install"
        ),
        credentials,
        cwd,
    )


def observed(session: object) -> dict[str, object]:
    import time
    from typing import cast

    from paper_radar.llm.rpc_types import ByteSession

    stream = cast(ByteSession, session)
    output = b""
    deadline = time.monotonic() + 10
    while b"\n" not in output and time.monotonic() < deadline:
        output += stream.pump(b"", 0.05).stdout
    return cast(dict[str, object], json.loads(output))
