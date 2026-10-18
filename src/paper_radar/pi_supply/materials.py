"""原字节配对、派生锁和 engines 的确定性规则。"""

from __future__ import annotations

import base64
import copy
import json
from typing import Any

from paper_radar.config.adapters import exact_program_version
from paper_radar.config.identity import canonical_json
from paper_radar.pi_supply.errors import SupplyError
from paper_radar.pi_supply.source_policy import checked_url

PI_PACKAGE = "@earendil-works/pi-coding-agent"


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate")
        result[key] = value
    return result


def object_bytes(raw: bytes) -> dict[str, Any]:
    try:
        result = json.loads(raw, object_pairs_hook=_pairs)
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (ValueError, UnicodeError, RecursionError):
        raise SupplyError("material_invalid") from None


def check_engine(engine: object, node_version: str) -> None:
    """V1 仅支持精确版本或单一 >= 三段版本,不实现完整 npm semver。"""
    if not isinstance(engine, str):
        raise SupplyError("engines_unsupported")
    lower = engine[2:] if engine.startswith(">=") else engine
    try:
        exact_program_version(lower)
    except ValueError:
        raise SupplyError("engines_unsupported") from None
    wanted = tuple(map(int, lower.split(".")))
    actual = tuple(map(int, node_version.split(".")))
    if actual < wanted if engine.startswith(">=") else actual != wanted:
        raise SupplyError("engines_mismatch")


def _integrity(value: object) -> str:
    try:
        if not isinstance(value, str) or not value.startswith("sha512-"):
            raise ValueError
        if len(base64.b64decode(value[7:], validate=True)) != 64:
            raise ValueError
    except ValueError:
        raise SupplyError("integrity_missing") from None
    return value


def derive_lock(
    package_raw: bytes,
    lock_raw: bytes,
    release_raw: bytes,
    pi_version: str,
    node_version: str,
) -> tuple[bytes, bytes]:
    package, lock, release = map(object_bytes, (package_raw, lock_raw, release_raw))
    try:
        if (
            package["version"] != pi_version
            or lock["version"] != pi_version
            or release["version"] != pi_version
            or type(release["schemaVersion"]) is not int
            or release["schemaVersion"] != 1
            or type(lock["lockfileVersion"]) is not int
            or lock["lockfileVersion"] != 3
            or package["dependencies"].get(PI_PACKAGE) != pi_version
            or package["dependencies"] != lock["packages"][""]["dependencies"]
            or package["name"] != lock["name"]
            or package["name"] != lock["packages"][""]["name"]
            or package["version"] != lock["packages"][""]["version"]
        ):
            raise SupplyError("material_conflict")
        check_engine(package["engines"]["node"], node_version)
        if package["engines"] != lock["packages"][""].get("engines"):
            raise SupplyError("material_conflict")
        evidence: dict[tuple[str, str, str], str] = {}
        for entry in release["packages"]:
            name, version, url = entry["name"], entry["version"], entry["tarball"]
            checked_url(url, "registry")
            key = (name, version, url)
            if key in evidence:
                raise SupplyError("material_conflict")
            evidence[key] = _integrity(entry["integrity"])
        derived = copy.deepcopy(lock)
        supplements = []
        for path, entry in derived["packages"].items():
            if path == "":
                continue
            if not path.startswith("node_modules/") or entry.get("link"):
                raise SupplyError("lock_unsupported")
            name = entry.get("name", path.rsplit("node_modules/", 1)[-1])
            version, resolved = entry["version"], entry["resolved"]
            override = package.get("overrides", {}).get(name)
            if override is not None and override != version:
                raise SupplyError("material_conflict")
            checked_url(resolved, "registry")
            supplement = evidence.get((name, version, resolved))
            existing = entry.get("integrity")
            if (
                existing is not None
                and supplement is not None
                and existing != supplement
            ):
                raise SupplyError("integrity_conflict")
            integrity = _integrity(existing if existing is not None else supplement)
            if existing is None:
                entry["integrity"] = integrity
                supplements.append(
                    {
                        "path": path,
                        "name": name,
                        "version": version,
                        "resolved": resolved,
                        "integrity": integrity,
                    }
                )
        # npm ci 消费原 package(含原 overrides)与只补 integrity 的派生锁。
        return canonical_json(derived), canonical_json(
            {
                "format_version": 1,
                "rule": "derived-lock-v1",
                "packages": supplements,
            }
        )
    except (KeyError, TypeError, AttributeError, ValueError):
        raise SupplyError("material_invalid") from None
