"""D1: nftables 1.1.6 native socket level 与双实际视图;不运行宿主 nft。"""

from pathlib import Path
from typing import Any

import pytest

from tests.test_live_bundle_host import material


def test_native_program_preserves_cgroup_level_and_fixed_network_scope() -> None:
    from paper_radar.live_evidence.nft_rules import nft_program

    target, network = material()
    program = nft_program(target, network)
    assert program.decode().splitlines() == [
        "add table inet paperradar",
        (
            "add chain inet paperradar output { type filter hook output "
            "priority -10; policy accept; }"
        ),
        "add chain inet paperradar project",
        (
            "add rule inet paperradar output socket cgroupv2 level 4 "
            '"user.slice/user-1000.slice/user@1000.service/paperradar.slice" '
            'jump project comment "paperradar-placement-v1"'
        ),
        (
            "add rule inet paperradar project meta nfproto ipv4 ip daddr "
            "192.0.2.1 meta l4proto tcp tcp dport 443 counter packets 0 bytes"
            ' 0 drop comment "paperradar-negative-outside-tcp443"'
        ),
        (
            "add rule inet paperradar project meta nfproto ipv4 ip daddr "
            "192.0.2.2 meta l4proto udp udp dport 53 counter packets 0 bytes "
            '0 drop comment "paperradar-negative-nonrouter-udp53"'
        ),
        (
            "add rule inet paperradar project meta nfproto ipv4 ip daddr "
            "192.0.2.2 meta l4proto tcp tcp dport 53 counter packets 0 bytes "
            '0 drop comment "paperradar-negative-nonrouter-tcp53"'
        ),
        (
            "add rule inet paperradar project meta nfproto ipv4 ip daddr "
            "192.0.2.1 meta l4proto udp udp dport 443 counter packets 0 bytes"
            ' 0 drop comment "paperradar-negative-udp443"'
        ),
        (
            "add rule inet paperradar project meta nfproto ipv4 ip daddr "
            "28.0.0.0/8 meta l4proto tcp tcp dport 443 accept comment "
            '"paperradar-pool-tls"'
        ),
        (
            "add rule inet paperradar project meta nfproto ipv4 ip daddr "
            "192.168.44.1 meta l4proto udp udp dport 53 accept comment "
            '"paperradar-router-udp53"'
        ),
        (
            "add rule inet paperradar project meta nfproto ipv4 ip daddr "
            "192.168.44.1 meta l4proto tcp tcp dport 53 accept comment "
            '"paperradar-router-tcp53"'
        ),
        'add rule inet paperradar project drop comment "paperradar-deny-remainder"',
    ]
    assert program.endswith(b"\n")


# Literal printer shapes follow nftables 1.1.6 socket.c/json.c/datatype.c.
# These are independent synthetic tool outputs, not a claimed kernel capture.
NATIVE = (
    "table inet paperradar { # handle 1\n"
    "    chain output { # handle 2\n"
    "        type filter hook output priority -10; policy accept;\n"
    "        socket cgroupv2 level 4 "
    '"user.slice/user-1000.slice/user@1000.service/paperradar.slice" '
    'jump project comment "paperradar-placement-v1" # handle 4\n'
    "    }\n"
    "    chain project { # handle 3\n"
    '        drop comment "paperradar-deny-remainder" # handle 5\n'
    "    }\n"
    "}\n"
)


def json_view() -> dict[str, Any]:
    return {
        "nftables": [
            {"table": {"family": "inet", "name": "paperradar", "handle": 1}},
            {
                "chain": {
                    "family": "inet",
                    "table": "paperradar",
                    "name": "output",
                    "handle": 2,
                }
            },
            {
                "chain": {
                    "family": "inet",
                    "table": "paperradar",
                    "name": "project",
                    "handle": 3,
                }
            },
            {
                "rule": {
                    "family": "inet",
                    "table": "paperradar",
                    "chain": "output",
                    "handle": 4,
                    "expr": [
                        {
                            "match": {
                                "op": "==",
                                "left": {"socket": {"key": "cgroupv2"}},
                                "right": (
                                    "user.slice/user-1000.slice/"
                                    "user@1000.service/paperradar.slice"
                                ),
                            }
                        },
                        {"jump": {"target": "project"}},
                    ],
                    "comment": "paperradar-placement-v1",
                }
            },
            {
                "rule": {
                    "family": "inet",
                    "table": "paperradar",
                    "chain": "project",
                    "handle": 5,
                    "expr": [{"drop": None}],
                    "comment": "paperradar-deny-remainder",
                }
            },
        ]
    }


def test_level_is_read_from_native_actual_and_changes_egress_identity() -> None:
    from paper_radar.live_evidence.nft_rules import merge_nft_views
    from paper_radar.live_evidence.protected_observer import egress_identity

    original = json_view()
    actual = merge_nft_views(original, NATIVE)
    changed = merge_nft_views(original, NATIVE.replace("level 4", "level 3"))
    assert actual["nftables"][3]["rule"]["expr"][0]["match"]["left"] == {
        "socket": {"key": "cgroupv2", "level": 4}
    }
    assert (
        "level"
        not in original["nftables"][3]["rule"]["expr"][0]["match"]["left"]["socket"]
    )
    target, _ = material()
    assert egress_identity(actual, target) != egress_identity(changed, target)


@pytest.mark.parametrize(
    "text",
    [
        NATIVE.replace("level 4 ", ""),
        NATIVE.replace("# handle 4", "# handle 9"),
        NATIVE.replace("paperradar-placement-v1", "paperradar-placement-v2"),
        NATIVE.replace("user-1000.slice", "user-1001.slice"),
        NATIVE.replace("jump project", "jump project socket cgroupv2 level 4 105"),
        NATIVE.replace("chain output", "chain other"),
    ],
)
def test_missing_or_uncorrelated_actual_socket_view_refuses(text: str) -> None:
    from paper_radar.live_evidence.nft_rules import merge_nft_views

    with pytest.raises(ValueError, match=r"^nft_views_identity$"):
        merge_nft_views(json_view(), text)


def test_reader_uses_bracketed_fixed_actual_views_and_never_expected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    import subprocess
    from typing import Any

    from paper_radar.live_evidence.nft_rules import read_nft_snapshot

    monkeypatch.setattr(
        "paper_radar.live_evidence.nft_rules.nft_generation", lambda: 42
    )
    calls: list[tuple[str, ...]] = []

    def run(argv: tuple[str, ...], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append(argv)
        kwargs["stdout"].write(
            NATIVE.encode() if "-a" in argv else json.dumps(json_view()).encode()
        )
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", run)
    actual = read_nft_snapshot()
    assert (
        actual["nftables"][3]["rule"]["expr"][0]["match"]["left"]["socket"]["level"]
        == 4
    )
    assert calls == [
        ("/usr/sbin/nft", "-j", "list", "table", "inet", "paperradar"),
        ("/usr/sbin/nft", "-a", "-n", "list", "table", "inet", "paperradar"),
        ("/usr/sbin/nft", "-j", "list", "table", "inet", "paperradar"),
    ]


def test_namespace_guard_refuses_shared_namespace_before_any_nft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os
    import subprocess

    from paper_radar.live_evidence.nft_rules import check_nft_namespace

    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(os, "unshare", lambda flags: None)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("shared namespace must never reach nft")

    monkeypatch.setattr(subprocess, "run", forbidden)
    target, network = material()
    with pytest.raises(ValueError, match=r"^nft_namespace_unavailable$"):
        check_nft_namespace(target, network)


def test_native_depth_mismatch_is_rejected_by_installer_and_counter_identity() -> None:
    import json
    from pathlib import Path

    from paper_radar.live_evidence.live_host import verify_nft
    from paper_radar.live_evidence.network_collection import verify_counter_change
    from paper_radar.live_evidence.nft_rules import merge_nft_views

    target, network = material()
    fixture = Path(__file__).parent / "fixtures/live-nft-1.1.6-source-derived.json"
    snapshot = json.loads(fixture.with_suffix(".json").read_bytes())
    native = fixture.with_suffix(".nft").read_text()
    actual = merge_nft_views(snapshot, native)
    verify_nft(actual, target, network)
    changed = merge_nft_views(snapshot, native.replace("level 4", "level 3"))
    with pytest.raises(ValueError, match=r"^nft_structure$"):
        verify_nft(changed, target, network)
    changed["nftables"][4]["rule"]["expr"][-2]["counter"] = {"packets": 1, "bytes": 60}
    assert not verify_counter_change(actual, changed, handle=5, attributable=True)


def test_generation_changes_refuse_but_other_tables_between_reads_do_not_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    import subprocess

    from paper_radar.live_evidence.nft_rules import read_nft_snapshot
    from paper_radar.live_evidence.protected_observer import egress_identity

    def run(argv: tuple[str, ...], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        kwargs["stdout"].write(
            NATIVE.encode() if "-a" in argv else json.dumps(json_view()).encode()
        )
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", run)
    generations = iter((41, 41, 42, 42, 42, 43))
    monkeypatch.setattr(
        "paper_radar.live_evidence.nft_rules.nft_generation", lambda: next(generations)
    )
    target, _ = material()
    assert egress_identity(read_nft_snapshot(), target) == egress_identity(
        read_nft_snapshot(), target
    )
    with pytest.raises(ValueError, match=r"^nft_views_identity$"):
        read_nft_snapshot()


def test_duplicate_native_empty_chain_is_not_a_correlated_inventory() -> None:
    from paper_radar.live_evidence.nft_rules import merge_nft_views

    duplicate = NATIVE.replace(
        "    chain project { # handle 3",
        "    chain output { # handle 2\n    }\n    chain project { # handle 3",
    )
    with pytest.raises(ValueError, match=r"^nft_views_identity$"):
        merge_nft_views(json_view(), duplicate)


@pytest.mark.parametrize(
    "change", ["missing_address", "missing_port", "protocol", "extra_meta", "ipv6"]
)
def test_protocol_dependency_equivalence_preserves_every_actual_restriction(
    change: str,
) -> None:
    import json
    from pathlib import Path

    from paper_radar.live_evidence.nft_rules import merge_nft_views, verify_nft

    fixture = Path(__file__).parent / "fixtures/live-nft-1.1.6-source-derived.json"
    actual = merge_nft_views(
        json.loads(fixture.read_bytes()), fixture.with_suffix(".nft").read_text()
    )
    expressions = actual["nftables"][4]["rule"]["expr"]
    if change == "missing_address":
        expressions.pop(0)
    elif change == "missing_port":
        expressions.pop(1)
    elif change == "protocol":
        expressions[1]["match"]["left"]["payload"]["protocol"] = "udp"
    elif change == "extra_meta":
        expressions.insert(
            0,
            {
                "match": {
                    "op": "==",
                    "left": {"meta": {"key": "nfproto"}},
                    "right": "ipv4",
                }
            },
        )
    else:
        expressions[0]["match"]["left"]["payload"]["protocol"] = "ip6"
    target, network = material()
    with pytest.raises(ValueError, match=r"^nft_structure$"):
        verify_nft(actual, target, network)


@pytest.mark.parametrize("failure", [None, "apply", "readback"])
def test_isolated_namespace_precheck_reads_back_the_same_fixed_program(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    import os
    import subprocess
    from pathlib import Path

    from paper_radar.live_evidence.nft_rules import check_nft_namespace

    fixture = Path(__file__).parent / "fixtures/live-nft-1.1.6-source-derived.json"
    trace = tmp_path / "fixed-child-calls"
    parent = os.getpid()
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        os,
        "readlink",
        lambda path: "net:parent" if os.getpid() == parent else "net:child",
    )

    def isolate(flags: int) -> None:
        assert flags == os.CLONE_NEWNET

    monkeypatch.setattr(os, "unshare", isolate)
    monkeypatch.setattr(
        "paper_radar.live_evidence.nft_rules.nft_generation", lambda: 42
    )

    def run(argv: tuple[str, ...], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        assert os.getpid() != parent
        if argv == ("/usr/sbin/nft", "-f", "-"):
            assert b'socket cgroupv2 level 4 "user.slice/' in kwargs["input"]
            trace.write_text("apply\n")
            return subprocess.CompletedProcess(
                argv, int(failure == "apply"), stdout=b"", stderr=b"private tool error"
            )
        assert argv in {
            ("/usr/sbin/nft", "-j", "list", "table", "inet", "paperradar"),
            ("/usr/sbin/nft", "-a", "-n", "list", "table", "inet", "paperradar"),
        }
        native = "-a" in argv
        with trace.open("a") as stream:
            stream.write("native\n" if native else "json\n")
        raw = (
            fixture.with_suffix(".nft").read_bytes() if native else fixture.read_bytes()
        )
        if native and failure == "readback":
            raw = raw.replace(b"level 4", b"level 3")
        kwargs["stdout"].write(raw)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", run)
    target, network = material()
    if failure:
        with pytest.raises(ValueError, match="^nft_namespace_" + failure + "_refused$"):
            check_nft_namespace(target, network)
    else:
        check_nft_namespace(target, network)
        assert trace.read_text() == "apply\njson\nnative\njson\n"
