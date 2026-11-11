"""D1: public root-child preflight with offline mount/manager OS replay."""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import signal
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from paper_radar.live_evidence import placement_policy as owner
from paper_radar.pi_execution import placement_preflight as probe
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.placement import CgroupIdentity, PlacementTarget


class PreflightModel:
    """Real fork/control flow; no mount, socket, manager, scope or ptrace IO."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.base = tmp_path
        self.events_path = tmp_path / "events.jsonl"
        self.stage = tmp_path / "stage"
        self.stage.mkdir()
        self.resolver = tmp_path / "canonical-resolver"
        self.resolver.write_text("nameserver 192.0.2.1\n")
        self.host_run = tmp_path / "host-run"
        self.private_run = tmp_path / "private-run"
        for endpoint in (
            self.host_run / f"user/{os.getuid()}/bus",
            self.host_run / "dbus/system_bus_socket",
        ):
            endpoint.parent.mkdir(parents=True, exist_ok=True)
            endpoint.write_bytes(b"offline endpoint type model; no real socket")
        self.host_run.chmod(0o755)
        (self.host_run / "dbus").chmod(0o755)
        self.hidden = False
        self.product = False
        self.fail = ""
        self.fd_paths: dict[int, str] = {}
        self.uid, self.gid = os.getuid(), os.getgid()
        self.original_open = os.open
        self.original_close = os.close
        self.original_fstat = os.fstat
        self.lock = self.original_open(tmp_path / "parent-lock", os.O_RDWR | os.O_CREAT)
        self.target = PlacementTarget(
            format_version=1,
            slice="paperradar.slice",
            ancestors=(
                CgroupIdentity("/paperradar.slice", 1, 2),
                CgroupIdentity("/", 1, 1),
            ),
            anchor_pid=os.getpid(),
            anchor_start=1,
            anchor_cgroup="/paperradar.slice/paperradar-anchor.service",
            egress_digest="a" * 64,
            resolver_view="/run/paper-radar/resolv.conf",
            resolver_digest="b" * 64,
        )
        self.site: Any = SimpleNamespace(product_uid=self.uid, product_gid=self.gid)
        self.sealed: Any = SimpleNamespace(
            build={"resolver_target": str(self.resolver), "resolver_mount_flags": 0},
            security={},
            policy=None,
            kernel=lambda: SimpleNamespace(verify=self.raw_verify),
        )
        monkeypatch.setattr(owner, "verify_host_security", self.host_verify)
        monkeypatch.setattr(owner, "RUNTIME_ROOT", tmp_path / "runtime")
        monkeypatch.setattr(
            owner, "_RESOLVER_SOURCE_PATH", self.private_run / "paper-radar/resolv.conf"
        )
        monkeypatch.setattr(owner, "Path", self.mapped)
        monkeypatch.setattr(ctypes, "CDLL", lambda *args, **kwargs: self)
        monkeypatch.setattr(os, "geteuid", lambda: self.uid if self.product else 0)
        monkeypatch.setattr(os, "open", self.opened)
        monkeypatch.setattr(os, "close", self.closed)
        monkeypatch.setattr(os, "fstat", self.fstat)
        monkeypatch.setattr(os, "setgroups", self.groups)
        monkeypatch.setattr(os, "setresgid", self.gid_drop)
        monkeypatch.setattr(os, "setresuid", self.uid_drop)
        monkeypatch.setattr(os, "execve", self.execute)
        monkeypatch.setattr(subprocess, "run", self.manager_command)
        model = self

        class Platform(probe.LinuxPreflightPlatform):
            # Inherit manager_environment: production _manager loop runs intact.
            def verify(
                self, target: PlacementTarget, pid: int, start: int, unit: str
            ) -> None:
                assert model.product and unit == "paperradar-anchor.service"
                model.event("anchor")
                if model.fail == "anchor":
                    raise ExecutionError("placement_anchor_invalid")

            def spawn(self, argv: tuple[str, ...], env: dict[str, str]) -> Any:
                assert model.product
                assert argv[:6] == (
                    "/usr/bin/systemd-run",
                    "--user",
                    "--scope",
                    "--quiet",
                    "--collect",
                    "--expand-environment=no",
                )
                assert argv[-2:] == ("--preflight-traced", str(os.getpid()))
                model.event("scope-boundary")
                if model.fail == "native":
                    raise ExecutionError("placement_exec_failed")
                if model.fail == "trace":
                    raise ExecutionError("placement_handshake_invalid")
                if model.fail == "unknown":
                    raise RuntimeError("SECRET arbitrary /private/auth/cache exception")
                if model.fail == "unlisted-reason":
                    raise ExecutionError("credentials_invalid")
                if model.fail == "handshake-timeout":
                    raise ExecutionError("placement_handshake_timeout")
                if model.fail in ("timeout", "signal"):
                    os.kill(
                        os.getpid(),
                        signal.SIGALRM if model.fail == "timeout" else signal.SIGKILL,
                    )
                os._exit(0)  # Deliberately stop before any actual scope/native/ptrace.

        monkeypatch.setattr(probe, "PREFLIGHT_PLATFORM", Platform())

    def event(self, name: str, **details: object) -> None:
        # Open after FD closure, never inherit a root diagnostic write handle.
        with self.events_path.open("a") as stream:
            stream.write(json.dumps({"event": name, **details}) + "\n")

    @property
    def events(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.events_path.read_text().splitlines()]

    def mapped(self, value: Any) -> Path:
        path = Path(value)
        if path == Path("/run") or path.is_relative_to("/run"):
            return (
                self.private_run if self.hidden else self.host_run
            ) / path.relative_to("/run")
        return path

    def opened(
        self, path: Any, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        logical = os.fsdecode(path)
        if dir_fd in self.fd_paths:
            logical = str(Path(self.fd_paths[dir_fd]) / logical)
        if logical in ("/", "/run", "/run/dbus", "/run/dbus/system_bus_socket"):
            self.event("open-fixed", path=logical)
            assert not self.hidden and not self.product
            if logical != "/":
                assert flags & os.O_NOFOLLOW
            assert flags & os.O_PATH and flags & os.O_CLOEXEC
            if self.fail == "missing-bus" and logical == "/run/dbus":
                raise FileNotFoundError("SECRET missing /private/auth")
            physical: Any = self.mapped(logical)
            dir_fd = None
        else:
            physical = self.mapped(path)
        fd = self.original_open(physical, flags, mode, dir_fd=dir_fd)
        self.fd_paths[fd] = logical
        return fd

    def closed(self, fd: int) -> None:
        self.fd_paths.pop(fd, None)
        self.original_close(fd)

    def fstat(self, fd: int) -> os.stat_result:
        info = self.original_fstat(fd)
        path = self.fd_paths.get(fd)
        if path in ("/", "/run", "/run/dbus", "/run/dbus/system_bus_socket"):
            fields = list(info)
            fields[4] = 0  # root-owned OS fixture, even under unprivileged pytest.
            if path == "/run/dbus/system_bus_socket" and stat.S_ISREG(info.st_mode):
                fields[0] = stat.S_IFSOCK | 0o666
            if (
                self.fail == "wrong-socket-type"
                and path == "/run/dbus/system_bus_socket"
            ):
                fields[0] = stat.S_IFREG | 0o644
            if (
                self.fail == "wrong-socket-owner"
                and path == "/run/dbus/system_bus_socket"
            ):
                fields[4] = self.uid
            if self.fail == "wrong-owner" and path == "/run/dbus":
                fields[4] = self.uid
            if self.fail == "writable-directory" and path == "/run":
                fields[0] = stat.S_IFDIR | 0o777
            return os.stat_result(fields)
        return info

    def unshare(self, flags: int) -> int:
        assert flags == 0x00020000
        return -1 if self.fail == "mount" else 0

    def mount(
        self,
        source: bytes | None,
        target: bytes,
        kind: bytes | None,
        flags: object,
        data: bytes | None,
    ) -> int:
        source_s = os.fsdecode(source) if source is not None else None
        target_s = os.fsdecode(target)
        if target_s == "/run" and kind == b"tmpfs":
            self.private_run.mkdir()
            self.hidden = True
            self.event("hidden-run")
        elif source_s and source_s.startswith("/proc/self/fd/"):
            original = Path(os.readlink(source_s))
            destination = self.mapped(target_s)
            if original.is_dir():
                shutil.copytree(original, destination, dirs_exist_ok=True)
            else:
                shutil.copyfile(original, destination)
            logical_target = (
                "/run/" + destination.relative_to(self.private_run).as_posix()
                if destination.is_relative_to(self.private_run)
                else target_s
            )
            self.event(
                "bind", target=logical_target, flags=getattr(flags, "value", flags)
            )
        elif target_s not in ("/", "/usr/libexec"):
            assert self.mapped(target_s).is_relative_to(self.base)
        if target_s == str(self.private_run / "dbus") and source is None:
            self.event("bus-readonly", flags=getattr(flags, "value", flags))
            if self.fail == "bind":
                return -1
        return 0

    def prctl(self, *arguments: int) -> int:
        assert arguments == (4, 0, 0, 0, 0)
        return 0

    def closed_before_drop(self) -> None:
        assert not self.fd_paths
        assert not os.environ and os.getcwd() == "/"
        with pytest.raises(OSError, match="Bad file descriptor"):
            self.original_fstat(self.lock)
        self.event("closed-before-drop")

    def groups(self, values: list[int]) -> None:
        self.closed_before_drop()
        assert values == []
        if self.fail == "uid":
            raise PermissionError("SECRET permanent uid failure")

    def gid_drop(self, real: int, effective: int, saved: int) -> None:
        self.closed_before_drop()
        assert real == effective == saved == self.gid

    def uid_drop(self, real: int, effective: int, saved: int) -> None:
        self.closed_before_drop()
        assert real == effective == saved == self.uid
        self.product = True
        self.event("product")

    def execute(self, path: str, argv: tuple[str, ...], env: dict[str, str]) -> None:
        assert self.product and argv == (
            str(self.base / "runtime/placement-pre"),
            "--preflight",
        )
        assert env == {}
        self.event("cold-native")
        if self.fail == "cold-native":
            os._exit(125)
        if self.fail == "cold-unknown":
            os._exit(42)
        os._exit(0)

    def manager_command(
        self, argv: tuple[str, ...], **kwargs: Any
    ) -> subprocess.CompletedProcess[bytes]:
        assert self.product
        commands = {
            ("/usr/bin/systemctl", "--user", "is-system-running"): (
                f"/run/user/{self.uid}/bus",
                b"running\n",
            ),
            (
                "/usr/bin/loginctl",
                "show-user",
                str(self.uid),
                "--property=Linger",
                "--value",
            ): ("/run/dbus/system_bus_socket", b"yes\n"),
            (
                "/usr/bin/systemctl",
                "--user",
                "is-active",
                "paperradar-anchor.service",
            ): (f"/run/user/{self.uid}/bus", b"active\n"),
        }
        endpoint, output = commands[argv]
        assert kwargs == {
            "env": {
                "PATH": "/usr/bin:/bin",
                "LANG": "C",
                "LC_ALL": "C",
                "XDG_RUNTIME_DIR": f"/run/user/{self.uid}",
                "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{self.uid}/bus",
            },
            "capture_output": True,
            "timeout": 3,
            "check": False,
        }
        visible = self.mapped(endpoint).exists()
        if self.fail == "nonrunning" and argv[-1] == "is-system-running":
            output = b"degraded\n"
        if self.fail == "linger" and argv[0] == "/usr/bin/loginctl":
            output = b"no\n"
        if self.fail == "inactive" and argv[-1] == "paperradar-anchor.service":
            output = b"inactive\n"
        self.event("manager", command=argv[0], visible=visible)
        return subprocess.CompletedProcess(
            argv, 0 if visible else 1, output if visible else b"", b"SECRET stderr"
        )

    def host_verify(self, sealed: object) -> None:
        self.event("host-reverify")

    def raw_verify(self, policy: object) -> None:
        self.event("raw-reverify")

    def run(self, *, traced: bool = True) -> None:
        try:
            owner.native_preflight(
                self.stage,
                self.site,
                self.sealed,
                target=self.target if traced else None,
            )
        finally:
            assert (
                self.original_fstat(self.lock).st_ino
                == (self.base / "parent-lock").stat().st_ino
            )
            self.original_close(self.lock)


def test_traced_preflight_preserves_both_fixed_bus_views(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = PreflightModel(tmp_path, monkeypatch)
    model.run()
    assert [
        event["visible"] for event in model.events if event["event"] == "manager"
    ] == [True, True, True]
    assert {event["target"] for event in model.events if event["event"] == "bind"} == {
        f"/run/user/{os.getuid()}",
        "/run/dbus",
    }
    assert [event["event"] for event in model.events].count("closed-before-drop") == 3
    assert model.events[-2:] == [{"event": "host-reverify"}, {"event": "raw-reverify"}]
    assert {
        event["flags"] for event in model.events if event["event"] == "bus-readonly"
    } == {4143}


def test_preflight_reports_closed_setup_stage_without_exception_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    model = PreflightModel(tmp_path, monkeypatch)
    model.fail = "missing-bus"
    with pytest.raises(ValueError, match=r"^placement_preflight_refused$"):
        model.run()
    assert (
        capsys.readouterr().err == "放置预检拒绝：阶段=根挂载与设置；原因=设置失败。\n"
    )
    assert not any(event["event"] == "product" for event in model.events)


def test_unavailable_diagnostic_stream_keeps_original_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    class UnavailableStream:
        def write(self, value: str) -> int:
            raise BrokenPipeError("SECRET diagnostic IO error")

    model = PreflightModel(tmp_path, monkeypatch)
    model.fail = "missing-bus"
    with monkeypatch.context() as stream_patch:
        stream_patch.setattr(sys, "stderr", UnavailableStream())
        with pytest.raises(ValueError, match=r"^placement_preflight_refused$"):
            model.run()


@pytest.mark.parametrize(
    "failure",
    [
        "wrong-socket-type",
        "wrong-socket-owner",
        "wrong-owner",
        "writable-directory",
        "mount",
        "bind",
        "missing-socket",
        "alternate-socket",
        "directory-symlink",
        "socket-symlink",
    ],
)
def test_untrusted_or_failed_fixed_bus_setup_still_refuses_before_product(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    model = PreflightModel(tmp_path, monkeypatch)
    model.fail = failure
    socket = model.host_run / "dbus/system_bus_socket"
    if failure == "missing-socket":
        socket.unlink()
    elif failure == "alternate-socket":
        socket.rename(socket.with_name("other-system-bus"))
    elif failure == "directory-symlink":
        (model.host_run / "dbus").rename(model.host_run / "alternate-dbus")
        (model.host_run / "dbus").symlink_to("alternate-dbus", target_is_directory=True)
    elif failure == "socket-symlink":
        socket.rename(socket.with_name("alternate-socket"))
        socket.symlink_to("alternate-socket")
    with pytest.raises(ValueError, match=r"^placement_preflight_refused$"):
        model.run()
    assert (
        capsys.readouterr().err == "放置预检拒绝：阶段=根挂载与设置；原因=设置失败。\n"
    )
    assert not any(event["event"] == "product" for event in model.events)


@pytest.mark.parametrize(
    ("failure", "stage", "reason"),
    [
        ("uid", "永久降权", "身份切换失败"),
        ("nonrunning", "产品 manager", "依赖不可用"),
        ("linger", "产品 manager", "依赖不可用"),
        ("inactive", "产品 manager", "依赖不可用"),
        ("anchor", "放置身份", "身份不匹配"),
        ("native", "native/scope/trace", "执行链失败"),
        ("trace", "native/scope/trace", "执行链失败"),
        ("unknown", "native/scope/trace", "未知拒绝"),
        ("unlisted-reason", "native/scope/trace", "未知拒绝"),
        ("handshake-timeout", "native/scope/trace", "握手超时"),
        ("timeout", "预检子进程", "超时"),
        ("signal", "预检子进程", "信号终止"),
    ],
)
def test_preflight_failures_keep_fixed_stage_diagnostics_and_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
    stage: str,
    reason: str,
) -> None:
    model = PreflightModel(tmp_path, monkeypatch)
    model.fail = failure
    with pytest.raises(ValueError, match=r"^placement_preflight_refused$"):
        model.run()
    assert capsys.readouterr().err == f"放置预检拒绝：阶段={stage}；原因={reason}。\n"
    assert not any(event["event"] == "raw-reverify" for event in model.events)
    if failure in {"nonrunning", "linger", "inactive", "anchor", "uid"}:
        assert not any(event["event"] == "scope-boundary" for event in model.events)


def test_cold_preflight_does_not_require_or_restore_any_bus(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = PreflightModel(tmp_path, monkeypatch)
    shutil.rmtree(model.host_run)
    model.run(traced=False)
    assert not any(
        event["event"] in {"bind", "open-fixed", "manager", "scope-boundary"}
        for event in model.events
    )
    assert {"event": "cold-native"} in model.events
    assert model.events[-2:] == [{"event": "host-reverify"}, {"event": "raw-reverify"}]


@pytest.mark.parametrize(
    ("failure", "stage"),
    [("cold-native", "native/scope/trace"), ("cold-unknown", "预检子进程")],
)
def test_cold_native_refusal_stays_controlled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
    stage: str,
) -> None:
    model = PreflightModel(tmp_path, monkeypatch)
    model.fail = failure
    with pytest.raises(ValueError, match=r"^placement_preflight_refused$"):
        model.run(traced=False)
    assert capsys.readouterr().err == f"放置预检拒绝：阶段={stage}；原因=未知拒绝。\n"
