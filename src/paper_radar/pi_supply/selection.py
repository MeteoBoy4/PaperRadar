"""激活、诊断和后续执行器共用的全部已选槽版本判定。"""

from pathlib import Path

from paper_radar.config import (
    ConfigError,
    load_config_snapshot,
    resolve_config_snapshot_reference,
)
from paper_radar.config.adapters import PiAdapter
from paper_radar.config.compile import MaterialKind, RuntimeConfigSnapshot
from paper_radar.pi_supply.errors import SupplyError


def load_snapshot(database: Path, reference: str) -> RuntimeConfigSnapshot:
    try:
        return load_config_snapshot(
            database, resolve_config_snapshot_reference(database, reference)
        )
    except ConfigError:
        raise SupplyError("snapshot_invalid") from None


def selected_pi_version(snapshot: RuntimeConfigSnapshot) -> str:
    versions = {
        PiAdapter.model_validate_json(
            snapshot.materials[(MaterialKind.ADAPTER, "pi-rpc", selected)].config_json
        ).pi_version
        for selected in snapshot.adapter_selections.values()
    }
    if not versions:
        raise SupplyError("adapter_missing")
    if len(versions) != 1:
        raise SupplyError("adapter_versions_mixed")
    return versions.pop()


def match_snapshot(snapshot: RuntimeConfigSnapshot, pi_version: str) -> None:
    if selected_pi_version(snapshot) != pi_version:
        raise SupplyError("selection_version_mismatch")
