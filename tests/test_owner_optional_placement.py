"""所有者豁免后的公共启动边界;无真实认证、DNS 或模型访问。"""

import json
import socket
from pathlib import Path

import pytest

from paper_radar.pi_execution import prepare_launch
from tests.pi_execution_support import PEER, launch_inputs, observed


def test_explicit_unplaced_launch_keeps_isolation_and_host_resolver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    peer = (
        PEER.replace(
            "import json, os, sys, time", "import json, os, resource, socket, sys, time"
        )
        .replace(
            "'node': sys.executable, 'entry': sys.argv[0],",
            """'node': sys.executable, 'entry': sys.argv[0],
        'resolver': Path('/etc/resolv.conf').read_text(),
        'cgroup': Path('/proc/self/cgroup').read_text(),
        'core': resource.getrlimit(resource.RLIMIT_CORE),""",
        )
        .replace(
            "'argv': args, 'env': dict(os.environ), 'cwd': os.getcwd(),",
            """'argv': args, 'env': dict(os.environ), 'cwd': os.getcwd(),
        'cgroup': Path('/proc/self/cgroup').read_text(),
        'no_new_privs': 'NoNewPrivs:\\t1' in Path('/proc/self/status').read_text(),
        'core': resource.getrlimit(resource.RLIMIT_CORE),""",
        )
    )
    database, description, roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch, peer=peer
    )

    monkeypatch.setattr(
        "paper_radar.pi_execution.auth.local_auth_entry", lambda install: install.pi
    )

    def forbidden_placement() -> None:
        pytest.fail("owner waiver must not consult protected placement state")

    monkeypatch.setattr(
        "paper_radar.pi_execution.placement.load_placement_target", forbidden_placement
    )
    expected_cgroup = Path("/proc/self/cgroup").read_text()
    with prepare_launch(
        database,
        description,
        roots=roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
        placement_required=False,
    ) as prepared:
        prepared.recheck_placement()
        auth = json.loads((credentials / "auth-observed.json").read_text())
        assert auth["cgroup"] == expected_cgroup
        assert auth["core"] == [0, 0]
        assert auth["no_new_privs"] is True
        result = observed(prepared(description))
        assert result["resolver"] == Path("/etc/resolv.conf").read_text()
        assert result["cgroup"] == expected_cgroup
        assert result["core"] == [0, 0]
        assert result["no_new_privs"] is True
        assert result["private_access"] == {
            "database": "denied",
            "blob": "denied",
            "publisher": "denied",
            "personal_pi": "denied",
            "refresh_credentials": "denied",
        }
        argv = result["argv"]
        assert isinstance(argv, list)
        assert "--no-session" in argv
        assert result["env_exact"] is True
        attempt = Path(str(result["root"]))
    assert not attempt.exists()


def test_unplaced_model_keeps_tcp_port_restriction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        peer = PEER.replace(
            "else:\n    agent = Path",
            f"""else:
    import socket
    with socket.socket() as connection:
        try:
            connection.connect(('127.0.0.1', {port}))
            tcp_denied = False
        except PermissionError:
            tcp_denied = True
    agent = Path""",
        ).replace(
            "'node': sys.executable, 'entry': sys.argv[0],",
            "'node': sys.executable, 'entry': sys.argv[0], 'tcp_denied': tcp_denied,",
        )
        database, description, roots, credentials, _cwd = launch_inputs(
            tmp_path, monkeypatch, peer=peer
        )
        monkeypatch.setattr(
            "paper_radar.pi_execution.auth.local_auth_entry", lambda install: install.pi
        )
        with prepare_launch(
            database,
            description,
            roots=roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
            placement_required=False,
        ) as prepared:
            assert observed(prepared(description))["tcp_denied"] is True


def test_default_launch_still_requires_placement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.pi_execution import ExecutionError

    database, description, roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch
    )

    def unavailable() -> None:
        raise ExecutionError("placement_unavailable")

    monkeypatch.setattr(
        "paper_radar.pi_execution.placement.load_placement_target", unavailable
    )
    with (
        pytest.raises(ExecutionError, match="placement_unavailable"),
        prepare_launch(
            database,
            description,
            roots=roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
        ),
    ):
        pytest.fail("the default must not silently fall back")
    assert not (credentials / "auth-observed.json").exists()


@pytest.mark.parametrize("boundary", ["auth", "model"])
def test_unplaced_core_limit_failure_refuses_before_secret_process_exec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    import resource

    from paper_radar.llm.rpc_types import RpcProblem
    from paper_radar.pi_execution import ExecutionError

    database, description, roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch
    )
    monkeypatch.setattr(
        "paper_radar.pi_execution.auth.local_auth_entry", lambda install: install.pi
    )

    def denied(_limit: int, _values: tuple[int, int]) -> None:
        raise OSError("controlled core limit rejection")

    if boundary == "auth":
        monkeypatch.setattr(resource, "setrlimit", denied)
        with (
            pytest.raises(ExecutionError, match="auth_failed"),
            prepare_launch(
                database,
                description,
                roots=roots,
                credentials_dir=credentials,
                auth_mode="chatgpt_subscription",
                placement_required=False,
            ),
        ):
            pytest.fail("core setup failure must not yield ownership")
        assert not (credentials / "auth-observed.json").exists()
    else:
        with prepare_launch(
            database,
            description,
            roots=roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
            placement_required=False,
        ) as prepared:
            monkeypatch.setattr(resource, "setrlimit", denied)
            with pytest.raises(RpcProblem, match="startup_error"):
                prepared(description)


def test_unplaced_auth_verifies_no_new_privs_before_helper_exec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ctypes
    from types import SimpleNamespace

    from paper_radar.pi_execution import ExecutionError

    database, description, roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch
    )
    monkeypatch.setattr(
        "paper_radar.pi_execution.auth.local_auth_entry", lambda install: install.pi
    )
    # The OS accepts SET but GET reports the invariant was not established.
    monkeypatch.setattr(
        ctypes, "CDLL", lambda *_args, **_kwargs: SimpleNamespace(prctl=lambda *_: 0)
    )
    with (
        pytest.raises(ExecutionError, match="auth_failed"),
        prepare_launch(
            database,
            description,
            roots=roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
            placement_required=False,
        ),
    ):
        pytest.fail("an unverified no_new_privs state must refuse")
    assert not (credentials / "auth-observed.json").exists()
