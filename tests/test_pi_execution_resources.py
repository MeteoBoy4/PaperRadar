"""启动前纯检查公共边界;没有 Pi、认证或网络调用。"""

from pathlib import Path

import pytest

from paper_radar.pi_execution import ExecutionError, check_cwd, check_system_prompt


def test_empty_constant_cwd_and_literal_system_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("paper_radar.pi_execution.resources.EXECUTION_CWD", tmp_path)
    assert check_cwd() == tmp_path
    assert check_system_prompt(b"PaperRadar system instruction\n") == (
        "PaperRadar system instruction\n"
    )
    (tmp_path / "AGENTS.override.md").write_text("private")
    with pytest.raises(ExecutionError, match="cwd_not_empty"):
        check_cwd()


@pytest.mark.parametrize(
    "prompt", [b"/private/file", b"./file", b"../file", b".", b".."]
)
def test_prompt_that_pi_could_read_as_path_is_rejected(prompt: bytes) -> None:
    with pytest.raises(ExecutionError, match="system_prompt_path"):
        check_system_prompt(prompt)


def test_single_argument_limit_includes_nul_and_counts_utf8_bytes() -> None:
    assert len(check_system_prompt(b"x" * 131071)) == 131071
    with pytest.raises(ExecutionError, match="argv_limit"):
        check_system_prompt(("中" * 43691).encode())
    with pytest.raises(ExecutionError, match="system_prompt_invalid"):
        check_system_prompt(b"secret\x00text")


def test_cwd_symlink_component_and_missing_directory_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    monkeypatch.setattr("paper_radar.pi_execution.resources.EXECUTION_CWD", link)
    with pytest.raises(ExecutionError, match="cwd_invalid"):
        check_cwd()
    monkeypatch.setattr(
        "paper_radar.pi_execution.resources.EXECUTION_CWD", target / "gone"
    )
    with pytest.raises(ExecutionError, match="cwd_invalid"):
        check_cwd()


def test_owner_credentials_are_metadata_only_and_outside_business_roots(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_execution import ExecutionRoots, check_credentials_directory

    roots = ExecutionRoots(
        *(tmp_path / name for name in ("data", "config", "materials", "install"))
    )
    directory = tmp_path / "credentials"
    directory.mkdir(mode=0o700)
    (directory / "auth.json").write_bytes(
        b"not JSON; metadata inspection must not parse"
    )
    check_credentials_directory(directory, roots)
    directory.chmod(0o755)
    with pytest.raises(ExecutionError, match="credentials_invalid"):
        check_credentials_directory(directory, roots)
    directory.chmod(0o700)
    link = tmp_path / "credentials-link"
    link.symlink_to(directory, target_is_directory=True)
    with pytest.raises(ExecutionError, match="credentials_invalid"):
        check_credentials_directory(link, roots)
    (directory / "auth.json").unlink()
    (directory / "auth.json").symlink_to(tmp_path / "publisher-secret")
    with pytest.raises(ExecutionError, match="credentials_invalid"):
        check_credentials_directory(directory, roots)


@pytest.mark.parametrize(
    "proxy",
    [
        "http://user:password@127.0.0.1:3128",
        "http://127.0.0.1:0",
        "http://host:65536",
        "file:///private/file",
        "http://host/?token=secret",
    ],
)
def test_proxy_rejects_credentials_and_invalid_shape(proxy: str) -> None:
    from paper_radar.pi_execution.resources import proxy_port

    with pytest.raises(ExecutionError, match="proxy_invalid"):
        proxy_port(proxy)


def test_credentials_cannot_be_inside_any_business_root(tmp_path: Path) -> None:
    from paper_radar.pi_execution import ExecutionRoots, check_credentials_directory

    roots = ExecutionRoots(
        *(tmp_path / name for name in ("data", "config", "materials", "install"))
    )
    for parent in (
        roots.data_root,
        roots.config_root,
        roots.material_root,
        roots.install_root,
    ):
        directory = parent / "credentials"
        directory.mkdir(mode=0o700, parents=True)
        (directory / "auth.json").write_text("{}")
        with pytest.raises(ExecutionError, match="credentials_invalid"):
            check_credentials_directory(directory, roots)
