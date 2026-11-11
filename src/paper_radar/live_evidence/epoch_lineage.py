"""部署时钟的封印来源;只迁移UTC事实,不迁移任何执行资格。"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self

from pydantic import Field, model_validator

from paper_radar.live_evidence.model_manifest import ModelManifestV2, parse_manifest
from paper_radar.live_evidence.receipt import (
    ApprovedPlan,
    Digest,
    Identifier,
    WireModel,
    canonical_bytes,
    content_sha256,
)
from paper_radar.live_evidence.receipt_v2 import ApprovedPlanV2
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration

if TYPE_CHECKING:
    from paper_radar.live_evidence.live_install import InstallationPaths


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


class EpochUpgrade(WireModel):
    """从原封印树与原epoch原字节派生;构建候选不赋予root信任。"""

    format_version: Literal[1] = 1
    payload_sha256: Digest
    runtime_manifest_sha256: Digest
    model_manifest_sha256: Digest
    first_plan_sha256: Digest
    epoch_sha256: Digest
    collector_sha256: Digest
    plan_ids: tuple[Identifier, ...] = Field(min_length=7, max_length=7)
    deployed_at: datetime
    starts_at: datetime
    ends_at: datetime
    owner_input_sha256: Digest
    continuity_sha256: Digest

    @model_validator(mode="before")
    @classmethod
    def strict_version(cls, value: Any) -> Any:
        if (
            isinstance(value, dict)
            and "format_version" in value
            and (
                type(value["format_version"]) is not int or value["format_version"] != 1
            )
        ):
            raise ValueError("epoch_upgrade_invalid")
        return value

    @model_validator(mode="after")
    def valid(self) -> Self:
        if (
            any(
                value.utcoffset() != timedelta(0)
                for value in (self.deployed_at, self.starts_at, self.ends_at)
            )
            or not self.starts_at <= self.deployed_at <= self.ends_at
            or self.starts_at >= self.ends_at
            or len(set(self.plan_ids)) != 7
        ):
            raise ValueError("epoch_upgrade_invalid")
        return self


def continuity_identity(root: Path) -> tuple[str, str]:
    """只白名单替换启动策略与派生collector/plan身份;其余字段全部参与。"""
    site = SiteConfiguration.model_validate_json((root / "site.json").read_bytes())
    manifest = parse_manifest((root / "model-manifest.json").read_bytes())
    strict = ApprovedPlan.model_validate_json((root / "plan.json").read_bytes())
    if not isinstance(manifest, ModelManifestV2):
        raise ValueError("epoch_upgrade_manifest")
    all_plans: tuple[ApprovedPlan | ApprovedPlanV2, ...]
    confirmation_raw = (root / "network-owner-confirmation.json").read_bytes()
    confirmation = json.loads(confirmation_raw)
    plans = (*(cell.plan for cell in manifest.cells), manifest.negative_plan)
    all_plans = (*plans, strict)
    if (
        _digest(confirmation_raw) != manifest.network.owner_confirmation_sha256
        or set(confirmation)
        != {
            "format_version",
            "owner_input",
            "plan_ids",
            "starts_at",
            "ends_at",
            "proof_boundary",
        }
        or confirmation["format_version"] != 1
        or confirmation["plan_ids"] != list(manifest.network.plan_ids)
        or datetime.fromisoformat(confirmation["starts_at"])
        != manifest.network.starts_at
        or datetime.fromisoformat(confirmation["ends_at"]) != manifest.network.ends_at
        or manifest.site_plan_id != strict.plan_id
        or manifest.site_plan_sha256 != content_sha256(strict)
        or strict.collector_sha256 != manifest.collector_sha256
        or any(
            (root / "plans" / (plan.plan_id + ".json")).read_bytes()
            != canonical_bytes(plan)
            for plan in plans
        )
        or any(
            plan.starts_at != manifest.network.starts_at
            or plan.ends_at != manifest.network.ends_at
            or plan.starts_at.utcoffset() != timedelta(0)
            or plan.ends_at.utcoffset() != timedelta(0)
            for plan in all_plans
        )
    ):
        raise ValueError("epoch_upgrade_continuity")
    data = {
        "site": site.model_dump(mode="json"),
        "manifest": manifest.model_dump(mode="json"),
        "strict": strict.model_dump(mode="json"),
        "confirmation": confirmation,
    }
    data["site"]["binding"]["launch_policy_version"] = "<launch>"
    model = data["manifest"]
    model["collector_sha256"] = "<collector>"
    model["site_plan_id"] = "<site-plan>"
    model["site_plan_sha256"] = "<site-plan-sha>"
    model["network"]["owner_confirmation_sha256"] = "<confirmation>"
    model["network"]["plan_ids"] = ["<plan>"] * 7
    for cell in model["cells"]:
        cell["model"]["launch_policy_version"] = "<launch>"
        # 此静态分项仅随启动策略变化;其他binding字段均须保留。
        if "launch_policy" in cell["binding"]:
            cell["binding"]["launch_policy"] = "<launch>"
        cell["plan"]["plan_id"] = "<plan>"
        cell["plan"]["collector_sha256"] = "<collector>"
    model["negative_plan"]["plan_id"] = "<plan>"
    model["negative_plan"]["collector_sha256"] = "<collector>"
    data["strict"]["plan_id"] = "<site-plan>"
    data["strict"]["collector_sha256"] = "<collector>"
    data["confirmation"]["plan_ids"] = ["<plan>"] * 7
    return _digest(_json(data)), _digest(_json(confirmation["owner_input"]))


def describe_epoch_upgrade(root: Path, epoch_raw: bytes) -> EpochUpgrade:
    """公开只读派生器;输入只能取旧原始epoch,安装时重新认证全部来源。"""
    from paper_radar.live_evidence.normal_auth_refresh import parse_epoch

    manifest_raw = (root / "model-manifest.json").read_bytes()
    manifest = parse_manifest(manifest_raw)
    epoch = parse_epoch(epoch_raw)
    ids = (
        *(cell.plan.plan_id for cell in manifest.cells),
        manifest.negative_plan.plan_id,
    )
    if epoch.collector_sha256 != manifest.collector_sha256 or epoch.plan_ids != ids:
        raise ValueError("epoch_upgrade_source")
    continuity, owner = continuity_identity(root)
    return EpochUpgrade(
        payload_sha256=(root / "payload.sha256").read_text().strip(),
        runtime_manifest_sha256=_digest((root / "manifest.sha256").read_bytes()),
        model_manifest_sha256=_digest(manifest_raw),
        first_plan_sha256=content_sha256(manifest.cells[0].plan),
        epoch_sha256=_digest(epoch_raw),
        collector_sha256=manifest.collector_sha256,
        plan_ids=ids,
        deployed_at=epoch.deployed_at,
        starts_at=manifest.network.starts_at,
        ends_at=manifest.network.ends_at,
        owner_input_sha256=owner,
        continuity_sha256=continuity,
    )


def verify_upgrade_candidate(root: Path, descriptor: EpochUpgrade) -> None:
    continuity, owner = continuity_identity(root)
    if (
        continuity != descriptor.continuity_sha256
        or owner != descriptor.owner_input_sha256
    ):
        raise ValueError("epoch_upgrade_continuity")


def verify_installed_upgrade(
    staged: Path,
    *,
    paths: InstallationPaths,
    state: dict[str, Any] | None,
    identity: dict[str, Any],
    owner_uid: int,
) -> EpochUpgrade | None:
    """安装器首次写入前的只读认证;恢复每次重放同一旧来源与完整祖先链。"""
    import os

    from paper_radar.live_evidence.collection import ProtectedCollection
    from paper_radar.live_evidence.intents import INTENT_PATH, ProtectedIntentLog
    from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
    from paper_radar.live_evidence.live_install import protected, verify_tree
    from paper_radar.live_evidence.normal_auth_refresh import (
        epoch_path,
        read_epoch,
        validate_epoch_inheritance,
    )

    specification = json.loads((staged / "deployment.json").read_bytes())
    raw_descriptor = specification.get("epoch_upgrade")
    same = state is not None and all(
        state[key] == identity[key]
        for key in ("format_version", "payload", "manifest", "upgrade_from")
    )
    if raw_descriptor is None:
        if state is not None and not same and state["phase"] == "installed":
            raise ValueError("epoch_upgrade_required")
        return None
    descriptor = EpochUpgrade.model_validate(raw_descriptor)
    pair = [descriptor.payload_sha256, descriptor.runtime_manifest_sha256]
    if state is None or specification["upgrade_from"] != pair:
        raise ValueError("epoch_upgrade_source")
    if same:
        old = state["previous"]
        if not isinstance(old, dict) or state["upgrade_from"] != pair:
            raise ValueError("epoch_upgrade_source")
        history = paths.journal.with_name("deployment-v2-history-" + pair[0] + ".json")
        protected(history, owner_uid, anchor=paths.anchor)
        if history.read_bytes() != _json(old) or history.stat().st_nlink != 1:
            raise ValueError("epoch_upgrade_history")
        archive = paths.runtime.with_name(paths.runtime.name + ".archive-" + pair[0])
        root = archive if os.path.lexists(archive) else paths.runtime
        if root == paths.runtime and state["phase"] != "retiring":
            raise ValueError("epoch_upgrade_source")
    else:
        old, root = state, paths.runtime
    if old["phase"] != "installed" or [old["payload"], old["manifest"]] != pair:
        raise ValueError("epoch_upgrade_source")
    source_root = root
    current: object = old
    seen: set[str] = set()
    for _depth in range(16):
        if (
            not isinstance(current, dict)
            or set(current)
            != {
                "format_version",
                "payload",
                "manifest",
                "phase",
                "upgrade_from",
                "previous",
            }
            or type(current["format_version"]) is not int
            or current["format_version"] != 2
            or current["phase"] not in {"installed", "resources"}
        ):
            raise ValueError("epoch_upgrade_history")
        current_pair = [current["payload"], current["manifest"]]
        # Pydantic SHA验证也用于journal pair,不接受路径或任意archive名。
        from pydantic import TypeAdapter

        for value in current_pair:
            TypeAdapter(Digest).validate_python(value)
        if current_pair[0] in seen:
            raise ValueError("epoch_upgrade_history")
        seen.add(current_pair[0])
        verify_tree(
            root,
            owner_uid=owner_uid,
            anchor=paths.anchor,
            payload=current_pair[0],
            manifest_digest=current_pair[1],
        )
        sealed = json.loads((root / "deployment.json").read_bytes())
        legacy = current["upgrade_from"]
        if sealed["upgrade_from"] != legacy:
            raise ValueError("epoch_upgrade_history")
        ancestor = current["previous"]
        if legacy is None:
            if ancestor is not None:
                raise ValueError("epoch_upgrade_history")
            break
        if not isinstance(legacy, list) or len(legacy) != 2:
            raise ValueError("epoch_upgrade_history")
        for value in legacy:
            TypeAdapter(Digest).validate_python(value)
        if legacy[0] in seen:
            raise ValueError("epoch_upgrade_history")
        archive = paths.runtime.with_name(paths.runtime.name + ".archive-" + legacy[0])
        verify_tree(
            archive,
            owner_uid=owner_uid,
            anchor=paths.anchor,
            payload=legacy[0],
            manifest_digest=legacy[1],
        )
        if ancestor is None:
            break  # 旧v1无journal;精确archive即边界,不补造epoch或history。
        if not isinstance(ancestor, dict) or legacy != [
            ancestor.get("payload"),
            ancestor.get("manifest"),
        ]:
            raise ValueError("epoch_upgrade_history")
        history = paths.journal.with_name(
            "deployment-v2-history-" + legacy[0] + ".json"
        )
        protected(history, owner_uid, anchor=paths.anchor)
        if history.read_bytes() != _json(ancestor) or history.stat().st_nlink != 1:
            raise ValueError("epoch_upgrade_history")
        current, root = ancestor, archive
    else:
        raise ValueError("epoch_upgrade_history")
    ledger = EvidenceLedger(
        paths.ledger, trust=LedgerTrust(owner_uid=owner_uid, anchor=paths.anchor)
    )
    manifest = parse_manifest((source_root / "model-manifest.json").read_bytes())
    read_epoch(ledger, manifest)
    actual = describe_epoch_upgrade(
        source_root, ledger._read_source(epoch_path(ledger, manifest))
    )
    if actual != descriptor:
        raise ValueError("epoch_upgrade_source")
    verify_upgrade_candidate(staged, descriptor)
    validate_epoch_inheritance(
        ledger,
        parse_manifest((staged / "model-manifest.json").read_bytes()),
        descriptor,
    )
    # 只读重放,不initialize/provision/恢复缺史;旧额度/失败/停止/撤销不改。
    ProtectedCollection(ledger).completed_receipts()
    EvidenceLifecycle(ledger).snapshot(now=datetime.now(UTC))
    events = ledger.audit()
    if any(event.action == "evidence_intent_cutover" for event in events):
        intent_path = paths.anchor / INTENT_PATH.relative_to("/")
        intents = ProtectedIntentLog(
            intent_path,
            product_gid=SiteConfiguration.model_validate_json(
                (source_root / "site.json").read_bytes()
            ).product_gid,
            trust=ledger.trust,
        )
        from paper_radar.live_evidence.service import PendingRevocation

        for line in intents.read(ledger):
            PendingRevocation.model_validate_json(line)
    return descriptor
