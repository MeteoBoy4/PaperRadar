"""真实本地 helper 进程的临时资源生命周期;没有认证/模型网络。"""

import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from paper_radar.pi_execution import ExecutionError, prepare_launch
from tests.pi_execution_support import PEER, TOKEN, launch_inputs, observed


@pytest.mark.parametrize("mode", ["ok", "failure", "timeout"])
def test_helper_cache_is_outside_credentials_and_cleaned_before_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    peer = PEER.replace(
        "    config = json.loads((agent / 'auth.json').read_text())",
        "    config = json.loads((agent / 'auth.json').read_text())\n"
        "    (Path(os.environ['HOME']) / 'node-compile-cache').mkdir()\n"
        "    (Path(os.environ['TMPDIR']) / 'temporary').write_text('synthetic')",
    )
    database, description, roots, credentials, _ = launch_inputs(
        tmp_path, monkeypatch, peer=peer
    )
    (credentials / "auth.json").write_text(json.dumps({"token": TOKEN, "mode": mode}))
    if mode == "ok":
        with prepare_launch(
            database,
            description,
            roots=roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
        ) as prepared:
            session = prepared(description)
            private = observed(session)["private_access"]
            assert isinstance(private, dict)
            assert private["refresh_credentials"] == "denied"
            session.terminate(5)
    else:
        with (
            pytest.raises(
                ExecutionError,
                match="auth_timeout" if mode == "timeout" else "auth_failed",
            ),
            prepare_launch(
                database,
                description,
                roots=roots,
                credentials_dir=credentials,
                auth_mode="chatgpt_subscription",
                auth_timeout=0.1,
            ),
        ):
            pytest.fail("helper refusal must not prepare model launch")
    observation = json.loads((credentials / "auth-observed.json").read_text())
    home, temporary = (Path(observation["env"][name]) for name in ("HOME", "TMPDIR"))
    assert home != credentials
    assert temporary != credentials
    assert home.parent == temporary.parent
    assert not home.parent.exists()
    assert not (credentials / "node-compile-cache").exists()


def test_helper_cleanup_must_be_verified_before_model_preparation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    database, description, roots, credentials, _ = launch_inputs(tmp_path, monkeypatch)
    original = shutil.rmtree
    leaked: list[Path] = []

    def incomplete_cleanup(
        path: str | os.PathLike[str],
        *,
        onexc: Callable[[Callable[..., object], str, BaseException], object]
        | None = None,
    ) -> None:
        if Path(path).name.startswith("paper-radar-auth-"):
            leaked.append(Path(path))
            return
        original(path, onexc=onexc)

    monkeypatch.setattr(shutil, "rmtree", incomplete_cleanup)
    try:
        with (
            pytest.raises(ExecutionError, match="cleanup_failed"),
            prepare_launch(
                database,
                description,
                roots=roots,
                credentials_dir=credentials,
                auth_mode="chatgpt_subscription",
            ),
        ):
            pytest.fail("unclean helper resources must refuse model preparation")
        assert len(leaked) == 1
        assert leaked[0].is_dir()
    finally:
        for root in leaked:
            original(root)


def test_helper_resource_creation_failure_refuses_before_auth_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tempfile

    database, description, roots, credentials, _ = launch_inputs(tmp_path, monkeypatch)

    original = tempfile.mkdtemp

    def unavailable(
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | os.PathLike[str] | None = None,
    ) -> str:
        if prefix == "paper-radar-auth-":
            raise OSError("synthetic unavailable temporary storage")
        return original(suffix=suffix, prefix=prefix, dir=dir)

    monkeypatch.setattr(tempfile, "mkdtemp", unavailable)
    with (
        pytest.raises(ExecutionError, match="resources_invalid"),
        prepare_launch(
            database,
            description,
            roots=roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
        ),
    ):
        pytest.fail("resource failure must not yield model preparation")
    assert not (credentials / "auth-observed.json").exists()
