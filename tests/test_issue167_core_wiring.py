"""独立D1:auth/model生产pre-exec设零core,只运行合成Python且不崩溃。"""

import json
import resource
from pathlib import Path

import pytest

from paper_radar.llm.rpc_types import RpcProblem
from paper_radar.pi_execution import ExecutionError, isolation, prepare_launch
from tests.pi_execution_support import TOKEN, launch_inputs, observed
from tests.pi_placement_support import instrument_wrapper

PEER = f"""
import json, os, resource, sys
from pathlib import Path
limits = list(resource.getrlimit(resource.RLIMIT_CORE))
if not sys.argv[1:]:
    path = Path(os.environ['PI_CODING_AGENT_DIR']) / 'core-observed.json'
    path.write_text(json.dumps(limits))
    from datetime import UTC, datetime
    now = datetime.now(UTC).isoformat()
    os.write(int(os.environ['PAPERRADAR_AUTH_METADATA_FD']), json.dumps({{
        'format_version': 1, 'source_id': 'pi-auth-refresh-1.4.0-v1',
        'pid': os.getpid(), 'started_at': now, 'completed_at': now,
        'refresh_called': False,
    }}).encode())
    print({TOKEN!r})
else:
    print(json.dumps({{'core': limits}}), flush=True)
    sys.stdin.buffer.read()
"""


def test_auth_and_model_exec_observe_zero_soft_and_hard_without_parent_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent_limits = resource.getrlimit(resource.RLIMIT_CORE)
    database, description, roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch, peer=PEER
    )
    with prepare_launch(
        database,
        description,
        roots=roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
    ) as prepared:
        assert json.loads((credentials / "core-observed.json").read_text()) == [0, 0]
        session = prepared(description)
        assert observed(session)["core"] == [0, 0]
        session.terminate(5)
    assert resource.getrlimit(resource.RLIMIT_CORE) == parent_limits


@pytest.mark.parametrize("stage", ["auth", "model"])
def test_failed_core_setting_refuses_auth_or_model_before_peer_exec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stage: str,
) -> None:
    database, description, roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch, peer=PEER
    )

    fail_core = tmp_path / "fail-core"
    fault = tmp_path / "core-fault"
    exec_log = tmp_path / "peer-exec"
    instrument_wrapper(
        monkeypatch,
        f"""
import resource
from pathlib import Path
setrlimit = resource.setrlimit
execve = os.execve
core_calls = 0
exec_fd = os.open({str(exec_log)!r}, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
def checked_limit(key, value):
    global core_calls
    core_calls += 1
    if core_calls > 1 and Path({str(fail_core)!r}).exists():
        Path({str(fault)!r}).write_text(str((key, value)))
        raise PermissionError('sensitive-core-error-text')
    return setrlimit(key, value)
def checked_exec(path, argv, env):
    stage = b'auth\\n' if 'PAPERRADAR_AUTH_METADATA_FD' in env else b'model\\n'
    os.write(exec_fd, stage)
    return execve(path, argv, env)
resource.setrlimit = checked_limit
os.execve = checked_exec
""",
    )
    if stage == "auth":
        fail_core.touch()
        with (
            pytest.raises(ExecutionError, match=r"^placement_exec_failed$"),
            prepare_launch(
                database,
                description,
                roots=roots,
                credentials_dir=credentials,
                auth_mode="chatgpt_subscription",
            ),
        ):
            pytest.fail("auth limit failure must not yield")
        assert not (credentials / "core-observed.json").exists()
        assert exec_log.read_bytes() == b""
    else:
        with prepare_launch(
            database,
            description,
            roots=roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
        ) as prepared:
            fail_core.touch()
            with pytest.raises(RpcProblem) as error:
                prepared(description)
            assert error.value.reason.value == "startup_error"
            assert exec_log.read_text() == "auth\n"
    assert fault.read_text() == str((resource.RLIMIT_CORE, (0, 0)))
    captured = capsys.readouterr()
    assert "sensitive-core-error-text" not in captured.out + captured.err
    assert TOKEN not in captured.out + captured.err


def test_core_helper_sets_both_limits_and_checks_effective_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, tuple[int, int]]] = []
    monkeypatch.setattr(
        resource, "setrlimit", lambda key, value: calls.append((key, value))
    )
    monkeypatch.setattr(resource, "getrlimit", lambda _key: (0, 0))
    isolation.disable_core_dumps()
    assert calls == [(resource.RLIMIT_CORE, (0, 0))]


@pytest.mark.parametrize("effective", [(0, -1), (1, 0), (1, 1)])
def test_core_helper_rejects_ineffective_setting(
    monkeypatch: pytest.MonkeyPatch,
    effective: tuple[int, int],
) -> None:
    monkeypatch.setattr(resource, "setrlimit", lambda _key, _value: None)
    monkeypatch.setattr(resource, "getrlimit", lambda _key: effective)
    with pytest.raises(ExecutionError, match=r"^isolation_unavailable$"):
        isolation.disable_core_dumps()
