"""Unbound D1: source-backed systemd259 capability configuration contract."""

import configparser

from scripts.issue167_h1_network_bundle import units
from scripts.issue167_h1_phase import Plan


def test_guardian_does_not_select_systemd259_explicit_uid_seccomp_drop_path() -> None:
    plan = Plan("7c93ab04d615", 1000, 1000)
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(units(plan)[plan.guardian_unit])
    service = parser["Service"]
    requested = set(service["CapabilityBoundingSet"].split())
    ambient = set(service.get("AmbientCapabilities", "").split())
    has_seccomp = any(
        key in service
        for key in ("SystemCallFilter", "RestrictNamespaces", "RestrictAddressFamilies")
    )
    # v259.5 exec-invoke: valid explicit UID + seccomp keeps privileges, then
    # explicitly drops SETUID unless ambient includes it. This is a source
    # prediction/configuration check, never a live service or capability proof.
    inconsistent = (
        "User" in service
        and has_seccomp
        and "CAP_SETUID" in requested
        and "CAP_SETUID" not in ambient
    )
    assert not inconsistent, "explicit_uid_seccomp_drops_required_setuid"
    assert "User" not in service  # system service's documented default is root.
    assert service["Group"] == "root"
    assert service.get("DynamicUser", "no") == "no"
    assert "PAMName" not in service
    assert service["ExecStart"][0] not in "|+!"
    assert service["NoNewPrivileges"] == "yes"
    assert service["LimitCORE"] == "0"
    assert ambient == set()
    assert requested == {
        "CAP_NET_ADMIN",
        "CAP_SETUID",
        "CAP_SETGID",
        "CAP_KILL",
        "CAP_CHOWN",
        "CAP_DAC_READ_SEARCH",
    }
