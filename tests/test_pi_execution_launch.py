"""公共资源所有权/会话 seam,真实本地 auth/RPC 双形状对端。"""

import json
from pathlib import Path

import pytest

from paper_radar.pi_execution import prepare_launch
from paper_radar.pi_supply import probe_install
from tests.pi_execution_support import TOKEN, launch_inputs, observed


def test_controlled_launch_owns_fresh_resources_and_install_protection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, description, roots, credentials, cwd = launch_inputs(
        tmp_path, monkeypatch
    )
    monkeypatch.setenv("NODE_OPTIONS", "host-sensitive-sentinel")
    monkeypatch.setenv("XDG_CONFIG_HOME", "host-sensitive-sentinel")
    with prepare_launch(
        database,
        description,
        roots=roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
    ) as prepared:
        identity = prepared.identity
        assert probe_install(
            database, identity.supply_id, identity.install_id
        ).state == ("in_flight")
        assert TOKEN not in repr(prepared)
        auth = json.loads((credentials / "auth-observed.json").read_text())
        assert auth["argv"] == [
            "auth",
            "print-bearer-token",
            "--provider",
            "openai",
            "--min-expiry",
            "900s",
        ]
        assert "PI_OFFLINE" not in auth["env"]
        assert "OPENAI_API_KEY" not in auth["env"]
        assert "NODE_OPTIONS" not in auth["env"]
        session = prepared(description)
        result = observed(session)
        assert result["argv"] == [
            "--mode",
            "rpc",
            "--offline",
            "--no-session",
            "-ne",
            "-ns",
            "-np",
            "-nc",
            "-nt",
            "-na",
            "--no-mcp",
            "--no-themes",
            "--system-prompt",
            "Exact system instruction\n",
        ]
        assert result["env_exact"] is True
        assert result["cmdline_has_token"] is False
        assert result["private_access"] == {
            "database": "denied",
            "blob": "denied",
            "publisher": "denied",
            "personal_pi": "denied",
            "refresh_credentials": "denied",
        }
        assert result["no_new_privs"] is True
        assert result["cwd"] == str(cwd)
        assert result["protected"]
        assert result["agent_files"] == ["settings.json"]
        assert result["root_mode"] == 0o700
        assert result["settings"] == {
            "cacheWarming": "off",
            "retry": {"enabled": False, "provider": {"maxRetries": 0}},
            "compaction": {"enabled": False},
            "defaultProjectTrust": "never",
            "enableInstallTelemetry": False,
        }
        root = Path(str(result["root"]))
        assert TOKEN.encode() not in b"".join(
            p.read_bytes() for p in root.rglob("*") if p.is_file()
        )
        session.terminate(5)
        assert not root.exists()
        assert probe_install(
            database, identity.supply_id, identity.install_id
        ).state == ("in_flight")
    assert (
        probe_install(database, identity.supply_id, identity.install_id).state == "idle"
    )


@pytest.mark.parametrize(
    ("token", "mode", "reason"),
    [
        ("sk-forbidden-api-key", "ok", "auth_shape"),
        ("oauth token with spaces", "ok", "auth_shape"),
        ("", "ok", "auth_shape"),
        (TOKEN, "failure", "auth_failed"),
        (TOKEN, "timeout", "auth_timeout"),
    ],
)
def test_auth_refusal_happens_before_attempt_and_never_exposes_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    token: str,
    mode: str,
    reason: str,
) -> None:
    from paper_radar.pi_execution import ExecutionError

    database, description, roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch
    )
    (credentials / "auth.json").write_text(json.dumps({"token": token, "mode": mode}))
    with (
        pytest.raises(ExecutionError, match=reason) as caught,
        prepare_launch(
            database,
            description,
            roots=roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
            auth_timeout=0.1 if mode == "timeout" else 3,
        ),
    ):
        pytest.fail("invalid credential must not yield launch ownership")
    if token:
        assert token not in repr(caught.value)
    assert sorted(p.name for p in credentials.iterdir()) == [
        "auth-observed.json",
        "auth.json",
    ]


def test_proxy_and_distinct_attempt_ownership_with_context_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.llm.rpc_types import RpcProblem

    database, description, roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch
    )
    created: list[Path] = []
    for _ in range(2):
        with prepare_launch(
            database,
            description,
            roots=roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
            proxy="http://127.0.0.1:3128",
        ) as prepared:
            assert prepared.identity.proxy_used and prepared.identity.proxy_port == 3128
            assert "127.0.0.1" not in repr(prepared.identity)
            result = observed(prepared(description))
            assert result["env_exact"] is True
            settings = result["settings"]
            assert isinstance(settings, dict)
            assert settings["httpProxy"] == "http://127.0.0.1:3128"
            created.append(Path(str(result["root"])))
            with pytest.raises(RpcProblem, match="startup_error"):
                prepared(description)
        assert not created[-1].exists()
    assert created[0] != created[1]


def test_cwd_change_after_prepare_is_controlled_startup_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.llm.rpc_types import RpcProblem

    database, description, roots, credentials, cwd = launch_inputs(
        tmp_path, monkeypatch
    )
    with prepare_launch(
        database,
        description,
        roots=roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
    ) as prepared:
        (cwd / "CLAUDE.MD").write_text("private project context")
        with pytest.raises(RpcProblem, match="startup_error"):
            prepared(description)


def test_install_mutation_after_prepare_cannot_reach_model_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.llm.rpc_types import RpcProblem
    from paper_radar.pi_supply import show_supply

    database, description, roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch
    )
    with prepare_launch(
        database,
        description,
        roots=roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
    ) as prepared:
        record = show_supply(database, prepared.identity.supply_id)
        instance = next(
            i for i in record.installs if i.install_id == prepared.identity.install_id
        )
        entry = instance.path / record.manifest.pi_entry
        entry.chmod(0o644)
        entry.write_text("changed peer")
        with pytest.raises(RpcProblem, match="startup_error"):
            prepared(description)


def test_exec_and_isolation_establishment_failure_leave_no_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import paper_radar.pi_execution.isolation as isolation
    from paper_radar.llm.rpc_types import RpcProblem

    database, description, roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch
    )
    with prepare_launch(
        database,
        description,
        roots=roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
    ) as prepared:
        # 由真实 OS exec 边界拒绝:隔离白名单内运行库缺失,不 mock Popen。
        monkeypatch.setattr(isolation, "_RUNTIME_PATHS", ())
        with pytest.raises(RpcProblem, match="startup_error"):
            prepared(description)
    assert TOKEN.encode() not in database.read_bytes()


def test_cleanup_failure_refuses_success_and_can_only_clean_own_resource(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil

    from paper_radar.pi_execution import ExecutionError

    database, description, roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch
    )
    with prepare_launch(
        database,
        description,
        roots=roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
    ) as prepared:
        session = prepared(description)
        root = Path(str(observed(session)["root"]))
        original = shutil.rmtree
        with monkeypatch.context() as temporary:

            def denied(path: Path) -> None:
                assert path == root
                raise PermissionError("sensitive external detail")

            temporary.setattr(shutil, "rmtree", denied)
            with pytest.raises(ExecutionError, match="cleanup_failed") as caught:
                session.terminate(5)
            assert "sensitive external detail" not in repr(caught.value)
        session.terminate(5)
        assert not root.exists()
        assert (credentials / "auth.json").exists()
        assert original is shutil.rmtree


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("provider", "anthropic", "auth_mode_unsupported"),
        ("pi_version", "1.3.0", "protocol_unsupported"),
        ("system_prompt", b"x" * 131072, "argv_limit"),
        ("audit_snapshot_id", "01234567", "snapshot_invalid"),
    ],
    ids=["provider", "profile", "argv", "snapshot"],
)
def test_launch_prechecks_refuse_before_any_auth_or_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    reason: str,
) -> None:
    from dataclasses import replace

    from paper_radar.pi_execution import ExecutionError

    database, description, roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch
    )
    if field == "system_prompt":
        assert isinstance(value, bytes)
        description = replace(description, system_prompt=value)
    else:
        assert isinstance(value, str)
        if field == "provider":
            description = replace(description, provider=value)
        elif field == "pi_version":
            description = replace(description, pi_version=value)
        else:
            description = replace(description, audit_snapshot_id=value)
    with (
        pytest.raises(ExecutionError, match=reason),
        prepare_launch(
            database,
            description,
            roots=roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
        ),
    ):
        pytest.fail("precheck refusal must not yield")
    assert not (credentials / "auth-observed.json").exists()


@pytest.mark.parametrize("boundary", ["auth", "model"])
def test_pipe_handoff_failure_reaps_each_process_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    import os

    from paper_radar.llm.rpc_types import RpcProblem
    from paper_radar.pi_execution import ExecutionError

    database, description, roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch
    )
    real_getpgid = os.getpgid
    observed_pids: list[int] = []

    def failed_first_observation(pid: int) -> int:
        observed_pids.append(pid)
        if len(observed_pids) == 1:
            raise OSError(TOKEN)
        return real_getpgid(pid)

    if boundary == "auth":
        monkeypatch.setattr(os, "getpgid", failed_first_observation)
        with (
            pytest.raises(
                ExecutionError, match="placement_handshake_invalid"
            ) as caught,
            prepare_launch(
                database,
                description,
                roots=roots,
                credentials_dir=credentials,
                auth_mode="chatgpt_subscription",
            ),
        ):
            pytest.fail("auth pipe ownership failure must refuse before yield")
        assert TOKEN not in repr(caught.value)
    else:
        with prepare_launch(
            database,
            description,
            roots=roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
        ) as prepared:
            monkeypatch.setattr(os, "getpgid", failed_first_observation)
            with pytest.raises(RpcProblem, match="startup_error"):
                prepared(description)
    child_pid = observed_pids[0]
    with pytest.raises(ChildProcessError):
        os.waitpid(child_pid, os.WNOHANG)
    with pytest.raises(ProcessLookupError):
        os.killpg(child_pid, 0)


def test_activation_switch_preserves_already_protected_absolute_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.pi_supply import activate_supply, rebuild_supply
    from tests.pi_execution_support import PEER, PeerRun
    from tests.pi_supply_support import Download

    database, description, roots, credentials, _cwd = launch_inputs(
        tmp_path, monkeypatch
    )
    with prepare_launch(
        database,
        description,
        roots=roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
    ) as prepared:
        first = prepared.identity
        newer = rebuild_supply(
            database,
            first.supply_id,
            roots.install_root,
            data_root=roots.data_root,
            config_root=roots.config_root,
            material_root=roots.material_root,
            downloader=Download(),
            runner=PeerRun(PEER.replace("__TEST_ROOT__", repr(str(tmp_path)))),
        )
        activation = activate_supply(
            database, first.supply_id, description.audit_snapshot_id
        )
        assert activation.install_id == newer.install_id != first.install_id
        result = observed(prepared(description))
        assert first.install_id in str(result["node"])
        assert first.install_id in str(result["entry"])
        assert newer.install_id not in str(result["entry"])
        assert (
            probe_install(database, first.supply_id, first.install_id).state
            == "in_flight"
        )
