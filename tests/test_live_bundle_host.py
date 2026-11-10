"""规则/实际unit投影公共边界;不运行nft/systemd或出站。"""

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.live_evidence.live_host import (
    nft_document,
    validate_unit_identity,
    verify_nft,
)
from paper_radar.live_evidence.live_install import InstallationPaths
from paper_radar.live_evidence.model_manifest import NetworkConfiguration
from paper_radar.pi_execution.placement import CgroupIdentity, PlacementTarget


def material() -> tuple[PlacementTarget, NetworkConfiguration]:
    target = PlacementTarget(
        format_version=1,
        slice="paperradar.slice",
        ancestors=(
            CgroupIdentity(
                "/user.slice/user-1000.slice/user@1000.service/paperradar.slice",
                28,
                105,
            ),
            CgroupIdentity("/user.slice/user-1000.slice/user@1000.service", 28, 104),
            CgroupIdentity("/user.slice/user-1000.slice", 28, 103),
            CgroupIdentity("/user.slice", 28, 102),
            CgroupIdentity("/", 28, 101),
        ),
        anchor_pid=12345,
        anchor_start=45678,
        anchor_cgroup="/user.slice/user-1000.slice/user@1000.service/paperradar.slice/paperradar-anchor.service",
        egress_digest="a" * 64,
        resolver_view="/run/paper-radar/resolv.conf",
        resolver_digest="b" * 64,
    )
    network = NetworkConfiguration.model_validate(
        dict(
            pool="28.0.0.0/8",
            router="192.168.44.1",
            outside="192.0.2.1",
            nonrouter="192.0.2.2",
            udp443="192.0.2.1",
            owner_confirmation_sha256="c" * 64,
            plan_ids=["negative"],
            starts_at=datetime(2026, 11, 11, tzinfo=UTC),
            ends_at=datetime(2026, 11, 25, tzinfo=UTC),
        )
    )
    return target, network


def test_project_rules_use_actual_depth_four_fixed_counters_and_exact_owner_scope() -> (
    None
):
    target, network = material()
    commands = nft_document(target, network)["nftables"]
    assert commands[3]["add"]["rule"]["expr"][0] == {
        "match": {
            "op": "==",
            "left": {"socket": {"key": "cgroupv2", "level": 4}},
            "right": "user.slice/user-1000.slice/user@1000.service/paperradar.slice",
        }
    }
    negative_rules = [item["add"]["rule"] for item in commands[4:8]]
    assert [rule["comment"] for rule in negative_rules] == [
        "paperradar-negative-outside-tcp443",
        "paperradar-negative-nonrouter-udp53",
        "paperradar-negative-nonrouter-tcp53",
        "paperradar-negative-udp443",
    ]
    assert [rule["expr"][3]["match"]["right"] for rule in negative_rules] == [
        443,
        53,
        53,
        443,
    ]
    assert all(
        rule["expr"][-2:] == [{"counter": {"packets": 0, "bytes": 0}}, {"drop": None}]
        for rule in negative_rules
    )
    assert commands[8]["add"]["rule"]["expr"][1]["match"]["right"] == {
        "prefix": {"addr": "28.0.0.0", "len": 8}
    }
    assert commands[-1]["add"]["rule"]["expr"] == [{"drop": None}]


@pytest.mark.parametrize(
    "tamper",
    [
        "extra_rule",
        "missing_counter",
        "target_inode",
        "allow_udp443",
        "extra_allow_pool",
        "duplicate_handle",
    ],
)
def test_actual_nft_structure_refuses_unreviewed_change(tamper: str) -> None:
    target, network = material()
    snapshot = {
        "nftables": [
            deepcopy(row["add"]) for row in nft_document(target, network)["nftables"]
        ]
    }
    for index, row in enumerate(snapshot["nftables"]):
        if "rule" in row:
            row["rule"]["handle"] = index + 10
    verify_nft(snapshot, target, network)
    if tamper == "extra_rule":
        snapshot["nftables"].append(deepcopy(snapshot["nftables"][-1]))
    elif tamper == "missing_counter":
        snapshot["nftables"][4]["rule"]["expr"].pop(-2)
    elif tamper == "target_inode":
        snapshot["nftables"][3]["rule"]["expr"][0]["match"]["right"] = 999
    elif tamper == "allow_udp443":
        snapshot["nftables"][7]["rule"]["expr"][-1] = {"accept": None}
    elif tamper == "extra_allow_pool":
        snapshot["nftables"][8]["rule"]["expr"][1]["match"]["right"]["prefix"][
            "len"
        ] = 0
    else:
        snapshot["nftables"][4]["rule"]["handle"] = snapshot["nftables"][3]["rule"][
            "handle"
        ]
    with pytest.raises(ValueError):
        verify_nft(snapshot, target, network)


@pytest.mark.parametrize(
    "change",
    [
        {
            "FragmentPath": (
                "/home/product/.config/systemd/user/paperradar-anchor.service"
            )
        },
        {
            "DropInPaths": (
                "/home/product/.config/systemd/user/"
                "paperradar-anchor.service.d/override.conf"
            )
        },
        {"LimitCORE": "infinity"},
        {"LimitCORESoft": "infinity"},
        {"Slice": "app.slice"},
        {"ExecStart": "/home/product/anchor"},
        {"ExecStartPost": "/home/product/after-start"},
    ],
)
def test_actual_unit_shadow_dropin_or_execution_drift_refuses(
    change: dict[str, str],
) -> None:
    paths = InstallationPaths()
    slice_values = {
        "FragmentPath": "/etc/systemd/user/paperradar.slice",
        "DropInPaths": "",
        "ActiveState": "active",
    }
    anchor_values = {
        "FragmentPath": "/etc/systemd/user/paperradar-anchor.service",
        "DropInPaths": "",
        "ActiveState": "active",
        "Slice": "paperradar.slice",
        "LimitCORE": "0",
        "LimitCORESoft": "0",
        "ExecStart": (
            "{ path=/usr/libexec/paperradar/live-evidence-runtime/anchor ; "
            "argv[]=/usr/libexec/paperradar/live-evidence-runtime/anchor ; "
            "ignore_errors=no ; }"
        ),
    }
    anchor_values.update(
        {
            name: ""
            for name in (
                "ExecStartPre",
                "ExecStartPost",
                "ExecStop",
                "ExecStopPost",
                "ExecReload",
                "ExecCondition",
            )
        }
    )
    validate_unit_identity(paths, slice_values, anchor_values)
    with pytest.raises(ValueError):
        validate_unit_identity(paths, slice_values, anchor_values | change)


def test_cache_migration_unknown_identity_or_destination_refuses_without_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path

    from paper_radar.live_evidence.live_host import cache_metadata, migrate_cache
    from tests.site_collector_support import site_configuration

    site = site_configuration(tmp_path)
    cache = site.credentials_dir / "node-compile-cache"
    cache.mkdir(parents=True)
    secret = cache / "never-read"
    secret.write_bytes(b"secret fixture never opened")
    expected = cache_metadata(cache)

    def forbidden(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("cache content must not be opened")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    with pytest.raises(ValueError, match="legacy_cache_identity"):
        migrate_cache(site, expected | {"ino": expected["ino"] + 1})
    destination = site.credentials_dir.parent / (
        "paperradar-legacy-cache-" + str(expected["dev"]) + "-" + str(expected["ino"])
    )
    destination.mkdir()
    with pytest.raises(ValueError, match="legacy_cache_identity"):
        migrate_cache(site, expected)
    assert cache.is_dir() and secret.exists() and destination.is_dir()
