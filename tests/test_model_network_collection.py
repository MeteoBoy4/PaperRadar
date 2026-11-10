"""IPv4 负对照的 root counter 归属,不以 errno/超时冒充通过。"""

from typing import Any

from paper_radar.live_evidence.network_collection import verify_counter_change


def table(packets: int = 3, handle: int = 11) -> dict[str, Any]:
    return {
        "nftables": [
            {
                "rule": {
                    "family": "inet",
                    "table": "paperradar",
                    "chain": "output",
                    "handle": handle,
                    "expr": [
                        {"counter": {"packets": packets, "bytes": packets * 80}},
                        {"drop": None},
                    ],
                }
            }
        ]
    }


def test_exact_drop_counter_increment_is_required() -> None:
    assert verify_counter_change(table(), table(4), handle=11, attributable=True)
    assert not verify_counter_change(table(), table(), handle=11, attributable=True)
    assert not verify_counter_change(table(), table(5), handle=11, attributable=True)
    assert not verify_counter_change(table(), table(4), handle=11, attributable=False)
    assert not verify_counter_change(
        table(), table(4, 12), handle=11, attributable=True
    )


def test_other_rule_counter_change_is_unattributable() -> None:
    before = table()
    before["nftables"].extend(table(0, 12)["nftables"])
    after = table(4)
    after["nftables"].extend(table(1, 12)["nftables"])
    assert not verify_counter_change(before, after, handle=11, attributable=True)
