"""Owner-run H1 helper; no privileged action at ordinary import."""

from __future__ import annotations

import argparse
import json
import os
import re
import resource
import shutil
import stat
import sys
from pathlib import Path
from typing import TYPE_CHECKING

_root: Path
if TYPE_CHECKING:
    from scripts.issue167_h1_guardian import (
        Commands,
        GuardianRejected,
        _json_pairs,
        bootstrap,
        protected_path,
        read_json,
        read_table_binding,
        verify_bound_nft_state,
    )
    from scripts.issue167_h1_phase import (
        Plan,
        load_plan,
        read_cgroup_state,
        verify_nft_state,
    )
elif __package__ in {None, ""}:
    _root = Path(__file__).absolute().parent
    for _item in (_root, *_root.parents):
        _info = _item.lstat()
        if (
            os.geteuid() != 0
            or stat.S_ISLNK(_info.st_mode)
            or _info.st_uid != 0
            or _info.st_mode & 0o022
        ):
            raise SystemExit("root_owned_installation_required")
    sys.path.insert(0, str(_root))
    from issue167_h1_guardian import (
        Commands,
        GuardianRejected,
        _json_pairs,
        bootstrap,
        protected_path,
        read_json,
        read_table_binding,
        verify_bound_nft_state,
    )
    from issue167_h1_phase import Plan, load_plan, read_cgroup_state, verify_nft_state
else:
    from scripts.issue167_h1_guardian import (
        Commands,
        GuardianRejected,
        _json_pairs,
        bootstrap,
        protected_path,
        read_json,
        read_table_binding,
        verify_bound_nft_state,
    )
    from scripts.issue167_h1_phase import (
        Plan,
        load_plan,
        read_cgroup_state,
        verify_nft_state,
    )

UNIT_ROOT = Path("/etc/systemd/system")
UNIT_SEARCH = (UNIT_ROOT, Path("/run/systemd/system"), Path("/usr/lib/systemd/system"))
LEDGER_ROOT = Path("/var/lib/paperradar/probe-runs")


class GuardianTarget(Plan):
    """Use the same bounded reader for only the second fixed unit."""

    @property
    def unit(self) -> str:
        return self.guardian_unit


def absent(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return True
    return False


def decoded_json(raw: bytes) -> object:
    try:
        return json.loads(raw, object_pairs_hook=_json_pairs)
    except (ValueError, UnicodeError):
        raise GuardianRejected("table_inventory_unknown") from None


def table_present(plan: Plan, raw: bytes) -> bool:
    value = decoded_json(raw)
    if (
        type(value) is not dict
        or set(value) != {"nftables"}
        or type(value["nftables"]) is not list
    ):
        raise GuardianRejected("table_inventory_unknown")
    found = False
    for item in value["nftables"]:
        if type(item) is not dict or len(item) != 1:
            raise GuardianRejected("table_inventory_unknown")
        if "metainfo" in item:
            if type(item["metainfo"]) is not dict:
                raise GuardianRejected("table_inventory_unknown")
            continue
        row = item.get("table")
        if (
            type(row) is not dict
            or not {"family", "name"} <= set(row)
            or not set(row) <= {"family", "name", "handle"}
            or type(row["family"]) is not str
            or type(row["name"]) is not str
        ):
            raise GuardianRejected("table_inventory_unknown")
        if row["family"] == "inet" and row["name"] == plan.table:
            if found:
                raise GuardianRejected("table_inventory_unknown")
            found = True
    return found


def manager_scope(commands: Commands, unit: str) -> dict[str, str]:
    raw = commands._run(
        (
            str(commands.tools["systemctl"]),
            "show",
            unit,
            "--property=LoadState,FragmentPath,DropInPaths",
            "--no-pager",
        )
    )
    rows = [line.split("=", 1) for line in raw.decode().splitlines()]
    values = dict(rows)
    if len(rows) != len(values) or set(values) != {
        "LoadState",
        "FragmentPath",
        "DropInPaths",
    }:
        raise GuardianRejected("unit_scope_unknown")
    return values


def check_units(plan: Plan, commands: Commands, *, must_be_absent: bool) -> set[str]:
    loaded = set()
    for unit in (plan.unit, plan.guardian_unit):
        for directory in UNIT_SEARCH:
            if not absent(directory / (unit + ".d")):
                raise GuardianRejected("unit_dropin_changed")
            if directory != UNIT_ROOT and not absent(directory / unit):
                raise GuardianRejected("unit_conflict")
        target = UNIT_ROOT / unit
        exists = not absent(target)
        if exists:
            if must_be_absent:
                raise GuardianRejected("unit_conflict")
            protected_path(target)
            if target.read_bytes() != (plan.install_root / unit).read_bytes():
                raise GuardianRejected("installed_unit_changed")
        state = manager_scope(commands, unit)
        if state == {"LoadState": "not-found", "FragmentPath": "", "DropInPaths": ""}:
            continue
        if (
            must_be_absent
            or not exists
            or state["LoadState"] != "loaded"
            or state["FragmentPath"] != str(target)
            or state["DropInPaths"]
        ):
            raise GuardianRejected("unit_scope_unknown")
        loaded.add(unit)
    return loaded


def require_no_conflict(plan: Plan, commands: Commands) -> None:
    check_units(plan, commands, must_be_absent=True)
    if not absent(plan.runtime_root) or not absent(
        LEDGER_ROOT / f"issue167-{plan.run_id}.json"
    ):
        raise GuardianRejected("run_already_present")
    if table_present(
        plan, commands._run((str(commands.tools["nft"]), "-j", "list", "tables"))
    ):
        raise GuardianRejected("table_exists")


def install(plan: Plan, commands: Commands) -> dict[str, object]:
    require_no_conflict(plan, commands)
    protected_path(UNIT_ROOT, directory=True)
    for directory in (LEDGER_ROOT.parent, LEDGER_ROOT):
        if absent(directory):
            directory.mkdir(mode=0o755)
        protected_path(directory, directory=True)
    for unit in (plan.unit, plan.guardian_unit):
        source = plan.install_root / unit
        protected_path(source)
        fd = os.open(
            UNIT_ROOT / unit,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o644,
        )
        with os.fdopen(fd, "wb") as output:
            output.write(source.read_bytes())
            output.flush()
            os.fsync(output.fileno())
    commands._run((str(commands.tools["systemctl"]), "daemon-reload"))
    return {
        "result": "installed_only",
        "started": False,
        "auth_calls": 0,
        "model_calls": 0,
    }


def require_empty(plan: Plan) -> None:
    guardian = GuardianTarget(
        plan.run_id,
        plan.uid,
        plan.gid,
        plan.port_a,
        plan.port_b,
        plan.blocked_port,
        plan.timeout_s,
    )
    if (
        read_cgroup_state(plan, allow_absent=True).pids
        or read_cgroup_state(guardian, allow_absent=True).pids
    ):
        raise GuardianRejected("cgroup_not_empty")


def restore(plan: Plan, commands: Commands) -> dict[str, object]:
    # Validate bytes/scope BEFORE stopping anything, then stop before rules.
    loaded = check_units(plan, commands, must_be_absent=False)
    for unit in (plan.unit, plan.guardian_unit):
        if unit in loaded:
            commands._run((str(commands.tools["systemctl"]), "stop", unit))
    require_empty(plan)
    if table_present(
        plan, commands._run((str(commands.tools["nft"]), "-j", "list", "tables"))
    ):
        raw = commands._run(
            (str(commands.tools["nft"]), "-j", "list", "table", "inet", plan.table)
        )
        value = decoded_json(raw)
        try:
            binding = read_table_binding(plan)
        except FileNotFoundError:
            binding = None  # Legacy/early failure: original path checks still apply.
        except (OSError, ValueError):
            raise GuardianRejected("table_ownership_unknown") from None
        recognized = False
        for phase in ("deny", "a", "b"):
            try:
                if binding is None:
                    verify_nft_state(plan, phase, value)
                else:
                    verify_bound_nft_state(plan, phase, value, binding)
                recognized = True
                break
            except ValueError:
                continue
        if not recognized:
            raise GuardianRejected("table_ownership_unknown")
        commands.delete()
    check_units(plan, commands, must_be_absent=False)
    for unit in (plan.unit, plan.guardian_unit):
        target = UNIT_ROOT / unit
        if not absent(target):
            target.unlink()
    commands._run((str(commands.tools["systemctl"]), "daemon-reload"))
    return {
        "result": "host_policy_restored",
        "ledger_retained": not absent(LEDGER_ROOT / f"issue167-{plan.run_id}.json"),
        "runtime_retained": not absent(plan.runtime_root),
        "code_retained": True,
        "auth_calls": 0,
        "model_calls": 0,
    }


def mountpoints(raw: str) -> tuple[Path, ...]:
    result = []
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) < 7 or "-" not in fields:
            raise GuardianRejected("mount_inventory_unknown")
        encoded = fields[4]

        def decode(match: re.Match[str]) -> str:
            return chr(int(match.group(1), 8))

        decoded = re.sub(r"\\(040|011|012|134)", decode, encoded)
        if not decoded.startswith("/"):
            raise GuardianRejected("mount_inventory_unknown")
        result.append(Path(decoded))
    return tuple(result)


def remove_successful_artifacts(plan: Plan, commands: Commands) -> dict[str, object]:
    require_empty(plan)
    check_units(plan, commands, must_be_absent=True)
    if table_present(
        plan, commands._run((str(commands.tools["nft"]), "-j", "list", "tables"))
    ):
        raise GuardianRejected("table_still_present")
    value = read_json(plan.runtime_root / "guardian-result.json", owner=0)
    if (
        not isinstance(value, dict)
        or value.get("scope") != "h1_synthetic_local_only"
        or value.get("run_id") != plan.run_id
        or value.get("result") != "observed_expected"
        or value.get("cleanup_complete") is not True
        or value.get("table_may_remain") is not False
    ):
        raise GuardianRejected("unsuccessful_metadata_retained")
    ledger = LEDGER_ROOT / f"issue167-{plan.run_id}.json"
    protected_path(ledger)
    if read_json(ledger, owner=0) != value:
        raise GuardianRejected("ledger_binding_unknown")
    if not shutil.rmtree.avoids_symlink_attacks:
        raise GuardianRejected("safe_removal_unavailable")
    points = mountpoints(Path("/proc/self/mountinfo").read_text())
    for root in (plan.runtime_root, plan.install_root):
        protected_path(root, directory=True)
        if any(point.is_relative_to(root) for point in points):
            raise GuardianRejected("artifact_mount_unknown")
    for root in (plan.runtime_root, plan.install_root):
        shutil.rmtree(root)
    return {
        "result": "successful_artifacts_removed",
        "ledger_retained": True,
        "auth_calls": 0,
        "model_calls": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="所有者审阅后手动执行的有限H1安装/恢复"
    )
    parser.add_argument("operation", choices=("install", "restore", "finish"))
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    tools = bootstrap(_root)
    plan = load_plan(_root / "plan.json")
    if plan.install_root != _root:
        raise GuardianRejected("plan_root_mismatch")
    commands = Commands(plan, tools)
    actions = {
        "install": install,
        "restore": restore,
        "finish": remove_successful_artifacts,
    }
    print(json.dumps(actions[args.operation](plan, commands), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit("owner_operation_unknown") from None
