"""人工维护的入口期望。禁止从生产登记或实际输出推导预期。"""

import json
from pathlib import Path
from typing import Any

EXPECTATIONS = Path(__file__).parent / "fixtures/verification_group_expectations.json"


def expected_groups() -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = json.loads(EXPECTATIONS.read_bytes())["groups"]
    return groups


def expected_suffixes(*, include_receipt: bool = True) -> set[str]:
    data = json.loads(EXPECTATIONS.read_bytes())
    return {
        data["evidence_suffix"],
        data["terminal_suffix"],
        *(group["suffix"] for group in data["groups"]),
        *([data["receipt_suffix"]] if include_receipt else []),
    }


def assert_output_files(
    output: Path, *, include_receipt: bool = True, extra: tuple[str, ...] = ()
) -> None:
    paths = list(output.glob("*.json"))
    expected = expected_suffixes(include_receipt=include_receipt) | set(extra)
    assert {path.name[32:] for path in paths} == expected
    assert len(paths) == len(expected)


def assert_help(stdout: str) -> None:
    groups = expected_groups()
    names = "、".join(group["name"] for group in groups)
    required = "、".join(group["name"] for group in groups if group["required"])
    assert f"同次离线证据与 {names} 独立结论" in stdout
    assert f"（{len(groups) + 1} 份主要文件" in stdout
    assert f"共 {len(expected_suffixes())} 份 JSON" in stdout
    assert f"只有本次 {required} 都通过才返回 0" in stdout


def fixture_receipt_modules() -> dict[str, int]:
    """只供旧entry单测的模拟执行器,不证明这些模块实际执行。"""
    modules: dict[str, int] = json.loads(EXPECTATIONS.read_bytes())[
        "fixture_receipt_modules"
    ]
    assert all(type(count) is int and count > 0 for count in modules.values())
    return modules


def historical_stdout_bytes(stdout: bytes) -> bytes:
    """仅排除独立清单明确声明的非历史组,未知组/漏输出仍拒绝。"""
    import re

    data = json.loads(EXPECTATIONS.read_bytes())
    names = [group["name"] for group in data["groups"]]
    historical = data["historical_stdout_groups"]
    assert set(historical) <= set(names)
    lines = stdout.splitlines(keepends=True)
    observed = []
    for line in lines:
        match = re.match(rb"^\[([^]]+) ", line)
        if match and " 验收]".encode() in line:
            name = line.split(" 验收]".encode(), 1)[0][1:].decode()
            assert name in names, name
            if name not in observed:
                observed.append(name)
    assert observed == names
    for name in names:
        prefix = f"[{name} 验收] ".encode()
        assert sum(line.startswith(prefix + "结论：".encode()) for line in lines) == 1
        assert sum(line.startswith(prefix + "结果：".encode()) for line in lines) == 1
    excluded = tuple(
        f"[{name} 验收]".encode() for name in names if name not in historical
    )
    return b"".join(line for line in lines if not line.startswith(excluded))
