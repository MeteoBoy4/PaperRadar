"""D1: source-derived systemctl model through the real public fork preflight.

systemd v259 systemctl-is-system-running.c checks sd_booted() before acquiring
even the user bus; sd-daemon.c checks /run/systemd/system. The fixed show command
reads the same user manager SystemState without that boot-marker predicate.
This is an offline OS model, not an actual mount or a successful live preflight.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.test_preflight_system_bus import PreflightModel

_LEGACY_QUERY = ("/usr/bin/systemctl", "--user", "is-system-running")
_PROPERTY_QUERY = (
    "/usr/bin/systemctl",
    "--user",
    "show",
    "--property=SystemState",
    "--value",
)


class ManagerStateModel(PreflightModel):
    """Independent literal command meanings; production _manager is untouched."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        super().__init__(tmp_path, monkeypatch)
        (self.host_run / "systemd/system").mkdir(parents=True)
        self.state = b"running\n"
        self.query_code = 0
        self.query_error = ""

    def manager_command(
        self, argv: tuple[str, ...], **kwargs: Any
    ) -> subprocess.CompletedProcess[bytes]:
        if argv not in (_LEGACY_QUERY, _PROPERTY_QUERY):
            return super().manager_command(argv, **kwargs)
        assert self.product
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
        bus = self.mapped(f"/run/user/{self.uid}/bus").exists()
        boot_marker = self.mapped("/run/systemd/system").is_dir()
        self.event(
            "manager-state-query",
            argv=argv,
            bus=bus,
            boot_marker=boot_marker,
            state=self.state.decode(),
        )
        if self.query_error == "oserror":
            raise OSError("SECRET /private/auth/cache manager error")
        if self.query_error == "timeout":
            raise subprocess.TimeoutExpired(argv, 3, stderr=b"SECRET manager stderr")
        if argv == _LEGACY_QUERY and not boot_marker:
            return subprocess.CompletedProcess(argv, 1, b"offline\n", b"")
        if not bus:
            return subprocess.CompletedProcess(argv, 1, b"", b"SECRET missing bus")
        return subprocess.CompletedProcess(
            argv, self.query_code, self.state, b"SECRET manager stderr"
        )


def test_private_run_reads_actual_manager_state_without_boot_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    model = ManagerStateModel(tmp_path, monkeypatch)
    model.run()
    assert capsys.readouterr().err == ""
    assert [
        event for event in model.events if event["event"] == "manager-state-query"
    ] == [
        {
            "event": "manager-state-query",
            "argv": list(_PROPERTY_QUERY),
            "bus": True,
            "boot_marker": False,
            "state": "running\n",
        }
    ]
    assert (model.host_run / "systemd/system").is_dir()
    assert not (model.private_run / "systemd").exists()
    assert {event["target"] for event in model.events if event["event"] == "bind"} == {
        f"/run/user/{model.uid}",
        "/run/dbus",
    }
    assert {"event": "scope-boundary"} in model.events
    assert model.events[-2:] == [{"event": "host-reverify"}, {"event": "raw-reverify"}]


@pytest.mark.parametrize(
    ("state", "code", "error", "bus"),
    [
        (b"degraded\n", 0, "", True),
        (b"unknown\n", 0, "", True),
        (b"starting\n", 0, "", True),
        (b"initializing\n", 0, "", True),
        (b"stopping\n", 0, "", True),
        (b"maintenance\n", 0, "", True),
        (b"offline\n", 0, "", True),
        (b"", 0, "", True),
        (b"running", 0, "", True),
        (b"running\n\n", 0, "", True),
        (b"running\nrunning\n", 0, "", True),
        (b"Running\n", 0, "", True),
        (b"running\n", 1, "", True),
        (b"running\n", -15, "", True),
        (b"running\n", 0, "oserror", True),
        (b"running\n", 0, "timeout", True),
        (b"running\n", 0, "", False),
    ],
)
def test_private_run_rejects_unhealthy_unavailable_or_inexact_manager_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    state: bytes,
    code: int,
    error: str,
    bus: bool,
) -> None:
    model = ManagerStateModel(tmp_path, monkeypatch)
    model.state, model.query_code, model.query_error = state, code, error
    if not bus:
        (model.host_run / f"user/{model.uid}/bus").unlink()
    with pytest.raises(ValueError, match=r"^placement_preflight_refused$"):
        model.run()
    assert (
        capsys.readouterr().err
        == "放置预检拒绝：阶段=产品 manager；原因=依赖不可用。\n"
    )
    queries = [
        event for event in model.events if event["event"] == "manager-state-query"
    ]
    assert len(queries) == 1
    assert queries[0]["argv"] == list(_PROPERTY_QUERY)
    assert queries[0]["state"] == state.decode()
    assert queries[0]["bus"] == bus
    assert queries[0]["boot_marker"] is False
    assert not any(
        event["event"] in {"manager", "anchor", "scope-boundary", "raw-reverify"}
        for event in model.events
    )
