"""固定 nft native 程序及双实际视图;不提供任意命令入口。

nftables 1.1.6 的 JSON socket 输入不支持 cgroupv2,输出遗漏 level。
level 只能来自同一 handle 的实际 native 输出,不能从目标或预期补造。
"""

from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Any

from paper_radar.live_evidence.model_manifest import NEGATIVES, NetworkConfiguration
from paper_radar.live_evidence.nft_generation import nft_generation
from paper_radar.pi_execution.placement import PlacementTarget


def nft_program(target: PlacementTarget, network: NetworkConfiguration) -> bytes:
    """单事务固定表、四 drop counter、三允许与剩余 drop。"""
    path = target.ancestors[0].path.lstrip("/")
    # native 插值只允许固定 systemd cgroup 名称;配置地址由 wire 类型验证。
    import re

    if not re.fullmatch(
        r"user\.slice/user-[0-9]+\.slice/user@[0-9]+\.service/paperradar\.slice",
        path,
    ):
        raise ValueError("nft_target_identity")
    level = len(PurePosixPath(target.ancestors[0].path).parts) - 1
    lines = [
        "add table inet paperradar",
        (
            "add chain inet paperradar output { type filter hook output "
            "priority -10; policy accept; }"
        ),
        "add chain inet paperradar project",
        f'add rule inet paperradar output socket cgroupv2 level {level} "{path}" '
        'jump project comment "paperradar-placement-v1"',
    ]
    for address, protocol, port, comment in zip(
        (network.outside, network.nonrouter, network.nonrouter, network.udp443),
        ("tcp", "udp", "tcp", "udp"),
        (443, 53, 53, 443),
        network.rule_comments,
        strict=True,
    ):
        lines.append(
            f"add rule inet paperradar project meta nfproto ipv4 ip daddr {address} "
            f"meta l4proto {protocol} {protocol} dport {port} "
            f'counter packets 0 bytes 0 drop comment "{comment}"'
        )
    for allow_address, protocol, port, label in (
        (network.pool, "tcp", 443, "pool-tls"),
        (network.router, "udp", 53, "router-udp53"),
        (network.router, "tcp", 53, "router-tcp53"),
    ):
        lines.append(
            "add rule inet paperradar project meta nfproto ipv4 "
            f"ip daddr {allow_address} "
            f"meta l4proto {protocol} {protocol} dport {port} "
            f'accept comment "paperradar-{label}"'
        )
    lines.append(
        'add rule inet paperradar project drop comment "paperradar-deny-remainder"'
    )
    return ("\n".join(lines) + "\n").encode("ascii")


def merge_nft_views(snapshot: dict[str, Any], native: str) -> dict[str, Any]:
    """只从实际 native 规则读 level;两视图逐规则 chain/comment/handle/right 关联。"""
    import re
    from copy import deepcopy

    def refuse() -> None:
        raise ValueError("nft_views_identity")

    rows = snapshot.get("nftables")
    if not isinstance(rows, list):
        refuse()
    result = deepcopy(snapshot)
    rules: list[dict[str, Any]] = []
    for row in result["nftables"]:
        if not isinstance(row, dict):
            refuse()
        if "rule" in row:
            rule = row["rule"]
            if not isinstance(rule, dict) or (
                rule.get("family") != "inet"
                or rule.get("table") != "paperradar"
                or type(rule.get("handle")) is not int
                or rule["handle"] <= 0
            ):
                refuse()
            rules.append(rule)
    inventory: list[tuple[str, str | None, int]] = []
    containers: list[tuple[str, str, int]] = []
    socket_rows: list[tuple[int, int, str, str]] = []
    chain: str | None = None
    table = False
    for raw in native.splitlines():
        line = raw.strip()
        if not line:
            continue
        if found := re.fullmatch(
            r"table inet paperradar \{ # handle ([1-9][0-9]*)", line
        ):
            if table or chain is not None:
                refuse()
            containers.append(("table", "paperradar", int(found[1])))
            table = True
        elif found := re.fullmatch(
            r'chain ([A-Za-z0-9_.@-]+|"(?:[^"\\]|\\.)*") \{ # handle ([1-9][0-9]*)',
            line,
        ):
            if not table or chain is not None:
                refuse()
            chain = json.loads(found[1]) if found[1].startswith('"') else found[1]
            containers.append(("chain", chain, int(found[2])))
        elif line == "}":
            if chain is not None:
                chain = None
            elif table:
                table = False
            else:
                refuse()
        elif line.startswith("type ") and line.endswith(";"):
            if chain is None:
                refuse()
        else:
            found = re.fullmatch(
                r'(.+?)(?: comment ("(?:[^"\\]|\\.)*"))? # handle ([1-9][0-9]*)',
                line,
            )
            if not found or not table or chain is None:
                refuse()
            assert found is not None and chain is not None
            body, handle = found[1], int(found[3])
            comment = json.loads(found[2]) if found[2] is not None else None
            inventory.append((chain, comment, handle))
            if "socket cgroupv2" in body:
                sockets = list(
                    re.finditer(
                        r"socket cgroupv2 level ([0-9]+) "
                        r'(?:(==|!=|<=|>=|<|>) )?("[^"\\\n]+"|[0-9]+)(?= |$)',
                        body,
                    )
                )
                if len(sockets) != body.count("socket cgroupv2"):
                    refuse()
                for socket in sockets:
                    socket_rows.append(
                        (
                            handle,
                            int(socket[1]),
                            str(json.loads(socket[3])),
                            socket[2] or "==",
                        )
                    )
    if (
        table
        or chain is not None
        or containers
        != [
            (kind, value.get("name"), value.get("handle"))
            for row in result["nftables"]
            for kind, value in row.items()
            if kind in {"table", "chain"}
        ]
        or inventory
        != [(rule.get("chain"), rule.get("comment"), rule["handle"]) for rule in rules]
        or len({item[2] for item in inventory}) != len(inventory)
    ):
        refuse()
    matches = []
    for rule in rules:
        for expression in rule.get("expr", []):
            if not isinstance(expression, dict):
                refuse()
            match = expression.get("match", {})
            if not isinstance(match, dict):
                refuse()
            left = match.get("left", {})
            if isinstance(left, dict) and "socket" in left:
                socket = left["socket"]
                if not isinstance(socket, dict):
                    refuse()
                if socket.get("key") == "cgroupv2":
                    if left != {"socket": {"key": "cgroupv2"}}:
                        refuse()
                    matches.append((rule["handle"], match, left))
    if len(matches) != len(socket_rows):
        refuse()
    for (handle, match, left), (native_handle, level, right, op) in zip(
        matches, socket_rows, strict=True
    ):
        if (
            handle != native_handle
            or match.get("op") != op
            or str(match.get("right")) != right
        ):
            refuse()
        left["socket"]["level"] = level
    # 两视图共同确认 selector 缺失/变更仍是 actual,供刷新持久收紧。
    # 安装器另外要求完整固定结构;缺 selector 不成为临时不可用的借口。
    return result


def stable_nft_snapshot(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: (
                {
                    field: stable_nft_snapshot(content)
                    for field, content in item.items()
                    if field not in {"packets", "bytes"}
                }
                if key == "counter" and isinstance(item, dict)
                else stable_nft_snapshot(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            stable_nft_snapshot(item)
            for item in value
            if not (isinstance(item, dict) and set(item) == {"metainfo"})
        ]
    return value


def read_nft_snapshot() -> dict[str, Any]:
    """零参数只读固定表;JSON/native/JSON 夹读,拒绝结构并发变化。"""
    import subprocess
    import tempfile

    def query(argv: tuple[str, ...]) -> tuple[int, bytes]:
        with tempfile.TemporaryFile() as output:
            try:
                result = subprocess.run(
                    argv,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.DEVNULL,
                    env={
                        "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                        "LANG": "C",
                        "LC_ALL": "C",
                    },
                    cwd="/",
                    timeout=5,
                    check=False,
                )
                if output.tell() > 1024 * 1024:
                    raise ValueError("nft_observation_unavailable")
                output.seek(0)
                raw = output.read()
            except (OSError, subprocess.SubprocessError):
                raise ValueError("nft_observation_unavailable") from None
        return result.returncode, raw

    def document(raw: bytes) -> dict[str, Any]:
        def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value = dict(pairs)
            if len(value) != len(pairs):
                raise ValueError("nft_observation_unavailable")
            return value

        try:
            value = json.loads(raw, object_pairs_hook=unique)
        except (ValueError, UnicodeError):
            raise ValueError("nft_observation_unavailable") from None
        if not isinstance(value, dict) or not isinstance(value.get("nftables"), list):
            raise ValueError("nft_observation_unavailable")
        return value

    generation = nft_generation()
    command = ("/usr/sbin/nft", "-j", "list", "table", "inet", "paperradar")
    status, raw = query(command)
    if status:
        status, raw = query(("/usr/sbin/nft", "-j", "list", "tables"))
        tables = document(raw)
        if status:
            raise ValueError("nft_observation_unavailable")
        for row in tables["nftables"]:
            if isinstance(row, dict) and set(row) == {"metainfo"}:
                continue
            if (
                not isinstance(row, dict)
                or set(row) != {"table"}
                or not isinstance(row["table"], dict)
                or not isinstance(row["table"].get("family"), str)
                or not isinstance(row["table"].get("name"), str)
                or (
                    row["table"]["family"] == "inet"
                    and row["table"]["name"] == "paperradar"
                )
            ):
                raise ValueError("nft_observation_unavailable")
        if nft_generation() != generation:
            raise ValueError("nft_views_identity")
        return {"nftables": []}
    first = document(raw)
    status, native = query(
        ("/usr/sbin/nft", "-a", "-n", "list", "table", "inet", "paperradar")
    )
    if status:
        raise ValueError("nft_observation_unavailable")
    status, raw = query(command)
    if status:
        raise ValueError("nft_observation_unavailable")
    last = document(raw)
    if nft_generation() != generation or (
        stable_nft_snapshot(first) != stable_nft_snapshot(last)
    ):
        raise ValueError("nft_views_identity")
    try:
        return merge_nft_views(last, native.decode("ascii"))
    except UnicodeError:
        raise ValueError("nft_views_identity") from None


def nft_document(
    target: PlacementTarget, network: NetworkConfiguration
) -> dict[str, Any]:
    """规范规则模型(不是 nft JSON 提交格式);四 counter、三允许、剩余 drop。"""
    base = {"family": "inet", "table": "paperradar"}
    rules: list[dict[str, Any]] = []

    def match(left: object, right: object) -> dict[str, Any]:
        return {"match": {"op": "==", "left": left, "right": right}}

    def destination(address: object, protocol: str, port: int) -> list[dict[str, Any]]:
        return [
            match({"meta": {"key": "nfproto"}}, "ipv4"),
            match({"payload": {"protocol": "ip", "field": "daddr"}}, address),
            match({"meta": {"key": "l4proto"}}, protocol),
            match({"payload": {"protocol": protocol, "field": "dport"}}, port),
        ]

    level = len(PurePosixPath(target.ancestors[0].path).parts) - 1
    rules.append(
        {
            "chain": "output",
            "expr": [
                match(
                    {"socket": {"key": "cgroupv2", "level": level}},
                    target.ancestors[0].path.lstrip("/"),
                ),
                {"jump": {"target": "project"}},
            ],
            "comment": "paperradar-placement-v1",
        }
    )
    for _case, address, protocol, port, comment in zip(
        NEGATIVES,
        (
            str(network.outside),
            str(network.nonrouter),
            str(network.nonrouter),
            str(network.udp443),
        ),
        ("tcp", "udp", "tcp", "udp"),
        (443, 53, 53, 443),
        network.rule_comments,
        strict=True,
    ):
        rules.append(
            {
                "chain": "project",
                "expr": [
                    *destination(address, protocol, port),
                    {"counter": {"packets": 0, "bytes": 0}},
                    {"drop": None},
                ],
                "comment": comment,
            }
        )
    from ipaddress import IPv4Network

    pool = IPv4Network(network.pool)
    for allow_address, protocol, port, label in (
        (
            {"prefix": {"addr": str(pool.network_address), "len": pool.prefixlen}},
            "tcp",
            443,
            "pool-tls",
        ),
        (str(network.router), "udp", 53, "router-udp53"),
        (str(network.router), "tcp", 53, "router-tcp53"),
    ):
        rules.append(
            {
                "chain": "project",
                "expr": [*destination(allow_address, protocol, port), {"accept": None}],
                "comment": "paperradar-" + label,
            }
        )
    rules.append(
        {
            "chain": "project",
            "expr": [{"drop": None}],
            "comment": "paperradar-deny-remainder",
        }
    )
    return {
        "nftables": [
            {"add": {"table": {"family": "inet", "name": "paperradar"}}},
            {
                "add": {
                    "chain": {
                        **base,
                        "name": "output",
                        "type": "filter",
                        "hook": "output",
                        "prio": -10,
                        "policy": "accept",
                    }
                }
            },
            {"add": {"chain": {**base, "name": "project"}}},
            *({"add": {"rule": {**base, **rule}}} for rule in rules),
        ]
    }


def _canonical_dependencies(expressions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """只消去完整固定地址/端口签名中被其 payload 协议蕴含的两条依赖。

    1.1.6 官方 inet/meta.t.json.output 与 inet/payloadmerge.t 证明该反编译。
    不删除任意 meta,不补造 actual 字段,也不接受缺少地址或端口的签名。
    """
    if len(expressions) < 4:
        return expressions
    for protocol in ("tcp", "udp"):
        if (
            expressions[0]
            == {
                "match": {
                    "op": "==",
                    "left": {"meta": {"key": "nfproto"}},
                    "right": "ipv4",
                }
            }
            and expressions[1].get("match", {}).get("left")
            == {"payload": {"protocol": "ip", "field": "daddr"}}
            and expressions[2]
            == {
                "match": {
                    "op": "==",
                    "left": {"meta": {"key": "l4proto"}},
                    "right": protocol,
                }
            }
            and expressions[3].get("match", {}).get("left")
            == {"payload": {"protocol": protocol, "field": "dport"}}
        ):
            return [expressions[1], expressions[3], *expressions[4:]]
    return expressions


def verify_nft(
    snapshot: dict[str, Any], target: PlacementTarget, network: NetworkConfiguration
) -> None:
    if set(snapshot) != {"nftables"} or not isinstance(snapshot["nftables"], list):
        raise ValueError("nft_inventory")
    expected = [item["add"] for item in nft_document(target, network)["nftables"]]
    actual = []
    handles: set[int] = set()
    for item in snapshot["nftables"]:
        if isinstance(item, dict) and set(item) == {"metainfo"}:
            continue
        if (
            not isinstance(item, dict)
            or len(item) != 1
            or next(iter(item)) not in {"table", "chain", "rule"}
            or not isinstance(next(iter(item.values())), dict)
        ):
            raise ValueError("nft_inventory")
        kind, value = next(iter(item.items()))
        row = {
            key: content
            for key, content in value.items()
            if key not in {"handle", "use", "index"}
        }
        if kind == "rule":
            handle = value.get("handle")
            if type(handle) is not int or handle <= 0 or handle in handles:
                raise ValueError("nft_rule_handle")
            handles.add(handle)
            from copy import deepcopy

            row = deepcopy(row)
            if not isinstance(row.get("expr"), list):
                raise ValueError("nft_structure")
            for expression in row["expr"]:
                if not isinstance(expression, dict):
                    raise ValueError("nft_structure")
                if "counter" in expression:
                    if (
                        not isinstance(expression["counter"], dict)
                        or set(expression["counter"]) != {"packets", "bytes"}
                        or any(
                            type(value) is not int or value < 0
                            for value in expression["counter"].values()
                        )
                    ):
                        raise ValueError("nft_counter")
                    expression["counter"] = {"packets": 0, "bytes": 0}
                match = expression.get("match", {})
                if not isinstance(match, dict) or not isinstance(
                    match.get("left", {}), dict
                ):
                    raise ValueError("nft_structure")
                socket = match.get("left", {}).get("socket", {})
                if not isinstance(socket, dict):
                    raise ValueError("nft_structure")
                if socket.get("key") == "cgroupv2":
                    right = match.get("right")
                    if right not in (
                        target.ancestors[0].path,
                        target.ancestors[0].path.lstrip("/"),
                        target.ancestors[0].inode,
                        str(target.ancestors[0].inode),
                    ):
                        raise ValueError("nft_target_identity")
                    match["right"] = target.ancestors[0].path.lstrip("/")
        actual.append({kind: row})
    for records in (actual, expected):
        for record in records:
            if "rule" in record:
                record["rule"]["expr"] = _canonical_dependencies(record["rule"]["expr"])
    if actual != expected:
        raise ValueError("nft_structure")


def check_nft_namespace(target: PlacementTarget, network: NetworkConfiguration) -> None:
    """root 安装预检:只在独立子 netns 内提交并回读固定规则;不发送流量。"""
    import os
    import subprocess

    if os.geteuid() != 0:
        raise ValueError("nft_namespace_privilege")
    parent_namespace = os.readlink("/proc/self/ns/net")
    program = nft_program(target, network)
    pid = os.fork()
    if pid == 0:
        stage = 10
        try:
            os.unshare(os.CLONE_NEWNET)
            if os.readlink("/proc/self/ns/net") == parent_namespace:
                os._exit(stage)
            stage = 11
            result = subprocess.run(
                ("/usr/sbin/nft", "-f", "-"),
                input=program,
                capture_output=True,
                env={
                    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                    "LANG": "C",
                    "LC_ALL": "C",
                },
                cwd="/",
                timeout=15,
                check=False,
            )
            if result.returncode != 0:
                os._exit(stage)
            stage = 12
            verify_nft(read_nft_snapshot(), target, network)
        except Exception:
            os._exit(stage)
        os._exit(0)
    _, status = os.waitpid(pid, 0)
    if status != 0:
        reason = {
            10: "nft_namespace_unavailable",
            11: "nft_namespace_apply_refused",
            12: "nft_namespace_readback_refused",
        }.get(os.waitstatus_to_exitcode(status), "nft_namespace_unavailable")
        raise ValueError(reason)
