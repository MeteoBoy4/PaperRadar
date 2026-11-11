"""D1: 固定宿主工具接缝明确观察空数组;完全离线。"""

import subprocess
from pathlib import Path
from typing import Any

import pytest

from paper_radar.live_evidence.live_host import LinuxLiveHost, validate_unit_identity
from paper_radar.live_evidence.live_install import InstallationPaths

EMPTY_EXEC = b'{"type":"a(sasbttttuii)","data":[]}\n'
BUS_COMMAND = (
    "/usr/bin/busctl",
    "--user",
    "--json=short",
    "get-property",
    "org.freedesktop.systemd1",
    "/org/freedesktop/systemd1/unit/paperradar_2danchor_2eservice",
    "org.freedesktop.systemd1.Service",
    "ExecCondition",
    "ExecStartPre",
    "ExecStartPost",
    "ExecStop",
    "ExecStopPost",
    "ExecReload",
)


def observe(
    monkeypatch: pytest.MonkeyPatch, output: bytes = EMPTY_EXEC * 6, *, status: int = 0
) -> tuple[LinuxLiveHost, list[tuple[str, ...]]]:
    from tests.site_collector_support import site_configuration

    host = LinuxLiveHost(InstallationPaths())
    host.site = site_configuration(Path("/tmp/unused-synthetic-site"))
    calls: list[tuple[str, ...]] = []

    def run(argv: tuple[str, ...], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append(argv)
        if argv[0] == "/usr/bin/busctl":
            assert argv == BUS_COMMAND
            assert (
                kwargs["env"]["DBUS_SESSION_BUS_ADDRESS"]
                == "unix:path=/run/user/1000/bus"
            )
            return subprocess.CompletedProcess(argv, status, stdout=output, stderr=b"")
        assert argv[:3] == ("/usr/bin/systemctl", "--user", "show")
        if argv[3] == "paperradar.slice":
            raw = (
                b"FragmentPath=/etc/systemd/user/paperradar.slice\n"
                b"DropInPaths=\nActiveState=active\n"
            )
        else:
            # Actual systemd 259 omits all six empty arrays, also with --all.
            raw = (
                b"FragmentPath=/etc/systemd/user/paperradar-anchor.service\nDropInPaths=\n"
                b"ActiveState=active\nSlice=paperradar.slice\nLimitCORE=0\nLimitCORESoft=0\n"
                b"ExecStart={ path=/usr/libexec/paperradar/"
                b"live-evidence-runtime/anchor ; "
                b"argv[]=/usr/libexec/paperradar/live-evidence-runtime/anchor ; "
                b"ignore_errors=no ; }\n"
            )
        return subprocess.CompletedProcess(argv, 0, stdout=raw, stderr=b"")

    monkeypatch.setattr(subprocess, "run", run)
    return host, calls


def test_explicit_empty_arrays_accept_systemctl_omission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host, calls = observe(monkeypatch)
    validate_unit_identity(
        host.paths,
        host.unit_properties("paperradar.slice"),
        host.unit_properties("paperradar-anchor.service"),
    )
    assert calls.count(BUS_COMMAND) == 1


@pytest.mark.parametrize(
    "output,reason",
    [
        (b"", "anchor_exec_properties_invalid"),
        (EMPTY_EXEC * 5, "anchor_exec_properties_invalid"),
        (EMPTY_EXEC * 7, "anchor_exec_properties_invalid"),
        (
            EMPTY_EXEC * 5 + b'{"type":"s","data":[]}\n',
            "anchor_exec_properties_invalid",
        ),
        (
            EMPTY_EXEC * 5 + b'{"type":"a(sasbttttuii)","data":""}\n',
            "anchor_exec_properties_invalid",
        ),
        (
            EMPTY_EXEC * 5 + b'{"type":"a(sasbttttuii)"}\n',
            "anchor_exec_properties_invalid",
        ),
        (
            EMPTY_EXEC * 5 + b'{"type":"a(sasbttttuii)","data":[],"extra":true}\n',
            "anchor_exec_properties_invalid",
        ),
        (EMPTY_EXEC * 5 + b"[]\n", "anchor_exec_properties_invalid"),
        (
            EMPTY_EXEC * 5 + b'{"type":"a(sasbttttuii)","data":[["/bin/false"]]}\n',
            "anchor_extra_commands",
        ),
        (
            EMPTY_EXEC * 5 + b'{"type":"a(sasbttttuii)","data":[1],"data":[]}\n',
            "anchor_exec_properties_invalid",
        ),
        (EMPTY_EXEC * 5 + b"{broken\n", "anchor_exec_properties_invalid"),
        (EMPTY_EXEC * 5 + b"\xff\n", "anchor_exec_properties_invalid"),
    ],
)
def test_missing_malformed_or_nonempty_exec_arrays_refuse(
    monkeypatch: pytest.MonkeyPatch, output: bytes, reason: str
) -> None:
    host, _calls = observe(monkeypatch, output)
    with pytest.raises(ValueError, match=r"^" + reason + "$"):
        host.unit_properties("paperradar-anchor.service")


def test_busctl_failure_refuses_even_if_stdout_is_empty_arrays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host, _calls = observe(monkeypatch, status=1)
    with pytest.raises(ValueError, match=r"^host_command_refused$"):
        host.unit_properties("paperradar-anchor.service")


def test_unit_adapter_has_no_arbitrary_unit_or_property_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host, calls = observe(monkeypatch)
    with pytest.raises(ValueError, match=r"^unit_unknown$"):
        host.unit_properties("unreviewed.service")
    assert calls == []


@pytest.mark.parametrize(
    "state,pids,reason",
    [
        ("inactive", "", None),
        ("inactive", "42\n", "scope_not_empty"),
        ("activating", "", "resources_anchor_not_stopped"),
    ],
)
def test_recovery_stop_checks_fixed_anchor_and_refuses_other_processes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
    pids: str,
    reason: str | None,
) -> None:
    from tests.site_collector_support import site_configuration

    host = LinuxLiveHost(InstallationPaths.for_model(tmp_path))
    site = site_configuration(tmp_path)
    directory = Path(
        "/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/paperradar.slice"
    )
    source = tmp_path / "cgroup.procs"
    source.write_text(pids)
    rglob = Path.rglob
    exists = Path.exists
    is_dir = Path.is_dir
    monkeypatch.setattr(
        Path, "exists", lambda path: True if path == directory else exists(path)
    )
    monkeypatch.setattr(
        Path, "is_dir", lambda path: True if path == directory else is_dir(path)
    )
    monkeypatch.setattr(
        Path,
        "rglob",
        lambda path, pattern: (
            iter([source]) if path == directory else rglob(path, pattern)
        ),
    )
    calls: list[tuple[str, ...]] = []

    def run(argv: tuple[str, ...], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append(argv)
        if argv == ("/usr/sbin/nft", "-j", "list", "tables"):
            raw = b'{"nftables":[]}'
        elif argv[0] == "/usr/bin/busctl":
            assert argv == BUS_COMMAND
            raw = EMPTY_EXEC * 6
        else:
            assert argv[:3] == ("/usr/bin/systemctl", "--user", "show")
            raw = ("ActiveState=" + state + "\nMainPID=0\n").encode()
        return subprocess.CompletedProcess(argv, 0, stdout=raw, stderr=b"")

    monkeypatch.setattr(subprocess, "run", run)
    if reason:
        with pytest.raises(ValueError, match="^" + reason + "$"):
            host.verify_resources_stopped(site)
    else:
        host.verify_resources_stopped(site)
    assert all("stop" not in argv for argv in calls)


def test_recovery_never_deletes_existing_project_nft_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.site_collector_support import site_configuration

    calls: list[tuple[str, ...]] = []

    def run(argv: tuple[str, ...], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append(argv)
        assert argv == ("/usr/sbin/nft", "-j", "list", "tables")
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=b'{"nftables":[{"table":{"family":"inet","name":"paperradar"}}]}',
            stderr=b"",
        )

    monkeypatch.setattr(subprocess, "run", run)
    host = LinuxLiveHost(InstallationPaths.for_model(tmp_path))
    # Stopped verification requires no manifest and never invokes deletion/stop.
    with pytest.raises(ValueError, match=r"^nft_table_conflict$"):
        host.verify_resources_stopped(site_configuration(tmp_path))
    assert len(calls) == 1
