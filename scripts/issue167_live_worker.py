"""Ordinary controller for one explicitly approved synthetic six-cell batch.

Import is inert. Product/dependency imports happen only inside application_runtime.
No credentials, token, raw model output or external exception is published.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import pwd
import signal
import stat
import threading
import time
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

from scripts import issue167_live_case as contract
from scripts import issue167_live_runtime as runtime
from scripts import issue167_resolver_worker as local

_CORE_PATTERN = (
    b"|/usr/share/apport/apport -p%p -s%s -c%c -d%d -P%P -u%u -g%g -F%F -- %E\n"
)
_CORE_SOURCE_HASHES = {
    Path(
        "/usr/share/apport/apport"
    ): "e8b57da9924d461fee6d3b392dc184697bc14d2eb8d717c05e1cbf0bd376041e",
    Path(
        "/usr/lib/python3/dist-packages/apport/fileutils.py"
    ): "f4237093be3bcfd9e95be2622e721edf1bd21093d080dc8db4cdb7ca18104817",
    Path(
        "/usr/lib/python3/dist-packages/apport/report.py"
    ): "47bf22887ca462381db48bd0609d6e78db29fa5c193953857d7b5c1db0387615",
}


def check_core_policy(
    *, reader: Callable[[Path, int], bytes] = runtime.read_file
) -> None:
    """Current config/source applicability only; never invokes the handler."""
    try:
        if reader(Path("/proc/sys/kernel/core_pattern"), 4096) != _CORE_PATTERN:
            raise ValueError
        for path, expected in _CORE_SOURCE_HASHES.items():
            if hashlib.sha256(reader(path, 2 * 1024 * 1024)).hexdigest() != expected:
                raise ValueError
    except (OSError, ValueError):
        raise contract.CaseRejected("live_core_applicability_unknown") from None


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def verification_timing(
    started_at_utc: str,
    started_monotonic: float,
    *,
    clock: Callable[[], float] = time.monotonic,
    utc_clock: Callable[[], str] = utc_now,
) -> dict[str, object]:
    end = clock()
    value: dict[str, object] = {
        "started_at_utc": started_at_utc,
        "verified_at_utc": utc_clock(),
        "started_monotonic": started_monotonic,
        "verified_monotonic": end,
        "elapsed_seconds": end - started_monotonic,
    }
    contract.validate_timing(value)
    return value


def extract_materials(
    root: Path, destination: Path, expected_manifest: str
) -> dict[str, Any]:
    destination.mkdir(mode=0o700, exist_ok=False)
    with zipfile.ZipFile(root / "materials.zip") as archive:
        members = archive.infolist()
        if len(members) != 66 or len({m.filename for m in members}) != 66:
            raise contract.CaseRejected("live_materials_unknown")
        total = 0
        for item in members:
            p = Path(item.filename)
            if (
                p.is_absolute()
                or ".." in p.parts
                or item.is_dir()
                or item.file_size > 4 * 1024 * 1024
                or (item.external_attr >> 16) & 0o170000 == stat.S_IFLNK
            ):
                raise contract.CaseRejected("live_materials_unknown")
            total += item.file_size
            if total > 16 * 1024 * 1024:
                raise contract.CaseRejected("live_materials_unknown")
            raw = archive.read(item)
            target = destination / p
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as out:
                out.write(raw)
    raw = (destination / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_manifest:
        raise contract.CaseRejected("live_materials_unknown")
    manifest = json.loads(raw)
    expected = {"manifest.json"}
    for name, h in manifest["configuration_sha256"].items():
        expected.add(name)
        if hashlib.sha256((destination / name).read_bytes()).hexdigest() != h:
            raise contract.CaseRejected("live_materials_unknown")
    for name, h in manifest["source_sha256"].items():
        expected.add("source/" + name)
        if (
            hashlib.sha256((destination / "source" / name).read_bytes()).hexdigest()
            != h
        ):
            raise contract.CaseRejected("live_materials_unknown")
    for cell in manifest["cases"]:
        for name, h in cell["sha256"].items():
            expected.add(cell["case"] + "/" + name)
            if (
                hashlib.sha256(
                    (destination / cell["case"] / name).read_bytes()
                ).hexdigest()
                != h
            ):
                raise contract.CaseRejected("live_materials_unknown")
    actual = {
        str(p.relative_to(destination)) for p in destination.rglob("*") if p.is_file()
    }
    if actual != expected or len(expected) != 66:
        raise contract.CaseRejected("live_materials_unknown")
    return cast(dict[str, Any], manifest)


def check_core_site(root: Path, uid: int) -> None:
    contract.check_site(root)
    check_core_policy()
    check_user_core_config(uid)
    for ancestor in (Path("/"), Path("/srv"), Path("/srv/pi-cwd")):
        if any(
            not known_absent(ancestor / name, "live_cwd_resources_unknown")
            for name in (".pi", "AGENTS.md", "CLAUDE.md")
        ):
            raise contract.CaseRejected("live_cwd_resources_unknown")
    if any(Path("/srv/pi-cwd").iterdir()):
        raise contract.CaseRejected("live_cwd_resources_unknown")


def known_absent(path: Path, reason: str) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return True
    except OSError:
        raise contract.CaseRejected(reason) from None
    return False


def check_user_core_config(uid: int) -> None:
    try:
        home = Path(pwd.getpwuid(uid).pw_dir)
        if not known_absent(
            home / ".config/apport/settings", "live_core_applicability_unknown"
        ):
            raise contract.CaseRejected("live_core_applicability_unknown")
    except (KeyError, OSError):
        raise contract.CaseRejected("live_core_applicability_unknown") from None


def auth_directory_metadata(directory: Path, uid: int) -> dict[str, object]:
    """Only fixed-path lstat checkpoints; never read or hash credential bytes."""
    try:
        if not directory.is_absolute() or any(
            p.is_symlink() for p in (directory, *directory.parents)
        ):
            raise ValueError
        info = directory.lstat()
        auth = (directory / "auth.json").lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != uid
            or stat.S_IMODE(info.st_mode) != 0o700
            or not stat.S_ISREG(auth.st_mode)
            or auth.st_uid != uid
            or stat.S_IMODE(auth.st_mode) != 0o600
            or auth.st_nlink != 1
            or not known_absent(directory / "models.json", "live_auth_metadata_unknown")
        ):
            raise ValueError
        states = {}
        for name, label, is_directory in (
            ("models-store.json", "models_store", False),
            ("node-compile-cache", "compile_cache", True),
        ):
            try:
                entry = (directory / name).lstat()
            except FileNotFoundError:
                states[label] = "absent"
                continue
            if entry.st_uid != uid or entry.st_mode & 0o022:
                raise ValueError
            if is_directory:
                if not stat.S_ISDIR(entry.st_mode):
                    raise ValueError
                states[label] = "directory_owned"
            else:
                if (
                    not stat.S_ISREG(entry.st_mode)
                    or entry.st_nlink != 1
                    or stat.S_IMODE(entry.st_mode) != 0o600
                ):
                    raise ValueError
                states[label] = "regular_private_owned"
        result = {
            "scope": "fixed_auth_metadata_paths_only",
            "directory_private_owned": True,
            "auth_regular_private_owned": True,
            "models_configuration_absent": True,
            "contents_read": False,
            "content_shape_verified_by_agent": False,
            **states,
        }
        return contract.validate_auth_metadata(result)
    except (OSError, ValueError):
        raise contract.CaseRejected("live_auth_metadata_unknown") from None


_ACTIVATION_LEASE = threading.Lock()


def guarded_activate(
    database: Path, supply_id: str, snapshot_id: str, expected: dict[str, object]
) -> Any:
    """Add an expected-old check inside public commit_activation's write transaction."""
    from paper_radar.pi_supply import activate_supply, repository
    from paper_radar.pi_supply.errors import SupplyError

    if (
        set(expected)
        != {
            "activation_id",
            "supply_id",
            "install_id",
            "snapshot_id",
            "root_id",
            "root_path",
        }
        or type(expected["activation_id"]) is not int
        or expected["activation_id"] < 1
        or any(type(expected[k]) is not str for k in expected if k != "activation_id")
    ):
        raise contract.CaseRejected("live_selection_unknown")
    if not _ACTIVATION_LEASE.acquire(blocking=False):
        raise contract.CaseRejected("live_activation_guard_busy")
    original = repository._select_activation

    def guarded(connection: Any, activation_id: int) -> None:
        rows = (
            connection.exec_driver_sql(
                "SELECT c.activation_id,a.supply_id,a.install_id,a.snapshot_id,"
                "a.root_id,a.root_path "
                "FROM pi_current_selection c JOIN pi_activation_events a "
                "ON a.activation_id=c.activation_id WHERE c.singleton=1"
            )
            .mappings()
            .all()
        )
        if len(rows) != 1 or dict(rows[0]) != expected:
            raise SupplyError("selection_changed")
        new_rows = (
            connection.exec_driver_sql(
                "SELECT activation_id,supply_id,install_id,snapshot_id,"
                "root_id,root_path "
                "FROM pi_activation_events WHERE activation_id=?",
                (activation_id,),
            )
            .mappings()
            .all()
        )
        target = {
            **expected,
            "activation_id": activation_id,
            "snapshot_id": snapshot_id,
        }
        if (
            type(activation_id) is not int
            or supply_id != expected["supply_id"]
            or len(new_rows) != 1
            or dict(new_rows[0]) != target
        ):
            raise SupplyError("selection_changed")
        original(connection, activation_id)

    repository._select_activation = guarded
    try:
        return activate_supply(database, supply_id, snapshot_id)
    finally:
        repository._select_activation = original
        _ACTIVATION_LEASE.release()


class SessionMeter:
    """A byte-preserving wrapper retaining only approved protocol metadata."""

    def __init__(self, session: Any, prompt: bytes, level: str) -> None:
        from paper_radar.llm.rpc_frames import FrameDecoder

        self.session = session
        self.prompt = prompt
        self.level = level
        self.decoder = FrameDecoder()
        self.pending = b""
        self.active_prompt = False
        self.prompt_started = False
        self.prompt_completed = 0
        self.counts = {
            k: 0
            for k in (
                "response",
                "agent_start",
                "turn_start",
                "message_start",
                "message_update",
                "message_end",
                "turn_end",
                "agent_end",
                "agent_settled",
                "thinking_level_changed",
            )
        }
        self.records = 0
        self.prompt_ack_count = 0
        self.prompt_ack_sequence: int | None = None
        self.agent_start_sequence: int | None = None
        self.clean = False
        self.commands = False
        self.settled = False
        self.eof = False
        self.stderr_eof = False
        self.exit_code: int | None = None
        self.terminated = False
        self.usage: dict[str, int] | None = None

    def pump(self, pending: bytes, timeout: float, /) -> Any:
        from paper_radar.llm.rpc_types import RpcProblem, RpcReason, SessionEvent

        if pending:
            if self.pending:
                if pending != self.pending:
                    raise RpcProblem(RpcReason.TRANSPORT_ERROR)
            else:
                command = json.loads(pending)
                self.active_prompt = command.get("type") == "prompt"
                if self.active_prompt:
                    if self.prompt_started or pending != self.prompt:
                        raise RpcProblem(RpcReason.REQUEST_LIMIT)
                    self.prompt_started = True
            self.pending = pending
        event = self.session.pump(pending, timeout)
        if (
            type(event) is not SessionEvent
            or type(event.written) is not int
            or not 0 <= event.written <= len(pending)
        ):
            raise RpcProblem(RpcReason.TRANSPORT_ERROR)
        if pending:
            self.pending = pending[event.written :]
            if not self.pending and self.active_prompt:
                self.prompt_completed += 1
                self.active_prompt = False
        for record in self.decoder.feed(event.stdout):
            kind = record.get("type")
            if kind not in {
                "response",
                "agent_start",
                "turn_start",
                "message_start",
                "message_update",
                "message_end",
                "turn_end",
                "agent_end",
                "agent_settled",
                "thinking_level_changed",
            }:
                raise RpcProblem(RpcReason.EVENT_NOT_ALLOWED)
            self.records += 1
            self.counts[kind] += 1
            if self.records > 50000:
                raise RpcProblem(RpcReason.STDOUT_LIMIT)
            if kind == "agent_start" and self.agent_start_sequence is None:
                self.agent_start_sequence = self.records
            if (
                kind == "response"
                and record.get("id") == "rpc-9"
                and record.get("command") == "prompt"
                and record.get("success") is True
                and type(record.get("data")) is dict
                and record["data"].get("disposition") == "started"
            ):
                self.prompt_ack_count += 1
                if self.prompt_ack_sequence is None:
                    self.prompt_ack_sequence = self.records
            if kind == "response" and record.get("success") is True:
                data = record.get("data", {})
                if record.get("command") == "get_state" and type(data) is dict:
                    self.clean = (
                        all(
                            data.get(k) == v
                            for k, v in {
                                "autoCompactionEnabled": False,
                                "isStreaming": False,
                                "isCompacting": False,
                                "messageCount": 0,
                                "pendingMessageCount": 0,
                            }.items()
                        )
                        and data.get("sessionFile") is None
                    )
                if record.get("command") == "get_commands" and type(data) is dict:
                    self.commands = data.get("commands") == []
            if kind == "agent_settled":
                self.settled = True
            if kind == "message_end":
                m = record.get("message", {})
                if type(m) is dict and m.get("role") == "assistant":
                    u = m.get("usage")
                    names = (
                        "input",
                        "output",
                        "cacheRead",
                        "cacheWrite",
                        "totalTokens",
                    )
                    if type(u) is dict and all(
                        type(u.get(k)) is int and u[k] >= 0 for k in names
                    ):
                        self.usage = {k: u[k] for k in names}
        self.eof |= event.stdout_eof
        self.stderr_eof |= event.stderr_eof
        if event.stdout_eof:
            self.decoder.finish()
        if event.exit_code is not None:
            self.exit_code = event.exit_code
        return event

    def close_stdin(self) -> None:
        self.session.close_stdin()

    def terminate(self, timeout: float, /) -> None:
        self.session.terminate(timeout)
        self.terminated = True


class CellOperations(Protocol):
    def preflight(self) -> dict[str, object]: ...
    def run_cell(self, sequence: int) -> dict[str, object]: ...
    def restore_selection(self) -> dict[str, object]: ...


def run_batch(operations: CellOperations, *, run_id: str) -> dict[str, object]:
    result: dict[str, object] = {
        "scope": "live_six_normal_batch",
        "result": "unknown",
        "cases": [],
        "limits": dict(contract.LIMITS),
        "preflight": None,
        "selection_restoration": None,
    }
    try:
        result["preflight"] = operations.preflight()
        rows: list[dict[str, object]] = []
        result["cases"] = rows
        for sequence in range(1, 7):
            row = contract.validate_cell(
                sequence, operations.run_cell(sequence), run_id=run_id
            )
            rows.append(row)
        result["cases"] = rows
        result["result"] = "observed_expected"
    except (Exception, KeyboardInterrupt, SystemExit):
        result["failure_reason"] = "live_batch_unknown"
    finally:
        try:
            from scripts.issue167_resolver_owner import cleanup_signals

            with cleanup_signals():
                restored = operations.restore_selection()
            if json.dumps(restored, sort_keys=True) != json.dumps(
                {
                    "result": "original_selection_restored",
                    "append_only_history_retained": True,
                },
                sort_keys=True,
            ):
                raise contract.CaseRejected("live_selection_restore_unknown")
            result["selection_restoration"] = restored
        except BaseException:
            result["result"] = "unknown"
            result["selection_restoration"] = {
                "result": "unknown",
                "append_only_history_retained": True,
            }
        result["auth_metadata_journal"] = list(
            getattr(operations, "auth_metadata_journal", [])
        )
    return result


class ApplicationOperations:
    def __init__(
        self, case: contract.Case, root: Path, ready: dict[str, object]
    ) -> None:
        self.case = case
        self.root = root
        self.ready = ready
        self.deadline = time.monotonic() + case.worker_timeout_s
        self.context = cast(
            dict[str, Any],
            contract.read_metadata(
                root / "live-context.json", owner=0, limit=contract.CONTEXT_LIMIT
            ),
        )
        self.binding = runtime.load_binding(
            root / "live-context.json", key="application_runtime"
        )
        self.project = Path(self.binding["source_parent"]).parent
        self.database = self.project / ".scratch/exp-2/data/exp2.sqlite3"
        self.credentials = self.project / ".scratch/exp-2/credentials"
        self.supply = cast(dict[str, Any], self.context["supply"])
        self.materials = case.worker_root / "materials"
        self.manifest = extract_materials(
            root, self.materials, self.context["synthetic_manifest_sha256"]
        )
        self.last_activation: int | None = None
        self.last_snapshot: str | None = None
        self.journal: list[dict[str, object]] = []
        self.auth_metadata_journal: list[dict[str, object]] = []
        self.original_snapshot = self.supply["registration"]["snapshot_id"]

    def wait(self, name: str, sequence: int) -> None:
        local.wait_gate(
            self.case.runtime_root / name, self.case.run_id, sequence, self.deadline
        )

    def _current(self) -> Any:
        from paper_radar.pi_supply.repository import read_state

        current = read_state(self.database)[2]
        if current is None:
            raise contract.CaseRejected("live_selection_unknown")
        if (
            current.supply_id,
            current.install_id,
            current.root_id,
            str(current.root_path),
        ) != (
            self.supply["supply_id"],
            self.supply["install_id"],
            self.supply["registration"]["root_id"],
            self.supply["root"],
        ):
            raise contract.CaseRejected("live_selection_unknown")
        return current

    def expected_selection(self) -> dict[str, object]:
        r = self.supply["registration"]
        return {
            "activation_id": self.last_activation
            if self.last_activation is not None
            else r["activation_id"],
            "supply_id": self.supply["supply_id"],
            "install_id": self.supply["install_id"],
            "snapshot_id": self.last_snapshot
            if self.last_snapshot is not None
            else self.original_snapshot,
            "root_id": r["root_id"],
            "root_path": self.supply["root"],
        }

    def assert_current_expected(self) -> None:
        c = self._current()
        actual = {
            "activation_id": c.activation_id,
            "supply_id": c.supply_id,
            "install_id": c.install_id,
            "snapshot_id": c.snapshot_id,
            "root_id": c.root_id,
            "root_path": str(c.root_path),
        }
        if actual != self.expected_selection():
            raise contract.CaseRejected("live_selection_drift")

    def preflight(self) -> dict[str, object]:
        from paper_radar.config import compile_config
        from paper_radar.pi_execution.isolation import isolation_capability
        from paper_radar.pi_execution.resources import (
            check_credentials_directory,
            check_cwd,
        )
        from scripts.issue167_live_ipc import run_ipc_preflight

        check_core_site(self.root, self.case.uid)
        check_cwd()
        if any(
            not path.is_relative_to(Path("/home"))
            for path in (Path(os.readlink("/proc/self/exe")), Path(self.supply["node"]))
        ):
            raise contract.CaseRejected("live_core_applicability_unknown")
        if isolation_capability() < 6:
            raise contract.CaseRejected("live_isolation_unknown")
        current = self._current()
        if (
            current.activation_id != self.supply["registration"]["activation_id"]
            or current.snapshot_id != self.original_snapshot
        ):
            raise contract.CaseRejected("live_selection_unknown")
        self.record_selection("original", self.expected_selection())
        check_credentials_directory(self.credentials, self.execution_roots())
        auth_directory_metadata(self.credentials, self.case.uid)
        ipc = run_ipc_preflight(
            self.case.worker_root / "ipc", min(self.deadline, time.monotonic() + 180)
        )
        if (
            ipc.get("result") != "observed_expected"
            or ipc.get("integrity") != "complete"
        ):
            raise contract.CaseRejected("live_ipc_unknown")
        from paper_radar.pi_execution.resources import SETTINGS_JSON
        from scripts.issue167_fork_observation import CgroupReader
        from scripts.issue167_session_observation import ClassifiedSessionObservation

        observer_root = self.case.worker_root / "observer-preflight"
        observer_root.mkdir(mode=0o700)
        for name in ("home", "tmp", "agent"):
            (observer_root / name).mkdir(mode=0o700)
        (observer_root / "agent/settings.json").write_bytes(SETTINGS_JSON)
        with ClassifiedSessionObservation(
            observer_root,
            CgroupReader(self.case.base_plan()),
            expected_settings=SETTINGS_JSON,
        ) as observed:
            observed.start()
            observed.seal_terminal()
            observed.ready_for_delete()
            import shutil

            shutil.rmtree(observer_root)
            observed.check_deleted()
            if observed.receipt()["result"] != "session_window_complete":
                raise contract.CaseRejected("live_observer_preflight_unknown")
        for level in ("low", "high"):
            snapshot = compile_config(
                self.materials / "config" / f"settings-{level}.yaml", self.database
            )
            expected_ids = {
                c["snapshot_id"]
                for c in self.manifest["cases"]
                if c["thinking"] == level
            }
            if expected_ids != {snapshot.snapshot_id}:
                raise contract.CaseRejected("live_snapshot_unknown")
        from paper_radar.reading.acceptance_v2 import validate_read_output_v2
        from paper_radar.screening.validation import validate_output

        for name in contract.ORDER:
            description, _message, context = self._input(name)
            expected = (
                self.materials / name / "expected-valid-output.json"
            ).read_bytes()
            if description.stage == "read":
                validate_read_output_v2(expected, context, attempt_ordinal=1)
            elif description.stage == "value":
                validate_output("value_prediction", expected, context)
            else:
                validate_output("boundary", expected)
        result = {
            "result": "observed_expected",
            "ipc_integrity": "complete",
            "ipc": ipc,
            "synthetic_snapshots_registered": 2,
            "credential_contents_read": False,
            "observer_backend_initialized": True,
        }
        contract.validate_preflight(result)
        local.publish(self.case.worker_root / "preflight-result.json", result)
        return result

    def record_selection(self, action: str, selection: dict[str, object]) -> None:
        row = {
            "run_id": self.case.run_id,
            "sequence": len(self.journal),
            "action": action,
            "selection": selection,
        }
        contract.validate_journal_entry(len(self.journal), row, run_id=self.case.run_id)
        local.publish(
            self.case.worker_root / f"selection-{len(self.journal)}.json", row
        )
        self.journal.append(row)

    def record_auth(
        self, sequence: int, phase: str, *, completed: bool = False
    ) -> dict[str, object]:
        row: dict[str, object] = {
            "scope": "persistent_auth_metadata_checkpoint",
            "run_id": self.case.run_id,
            "sequence": sequence,
            "phase": phase,
            "result": "metadata_verified"
            if phase == "before"
            else "authentication_completed"
            if completed
            else "unknown",
            "first_network_refresh_planned": sequence == 1,
            "metadata": None,
        }
        try:
            row["metadata"] = auth_directory_metadata(self.credentials, self.case.uid)
        except contract.CaseRejected:
            row["result"] = "unknown"
        self.auth_metadata_journal.append(row)
        local.publish(
            self.case.worker_root / f"auth-metadata-{sequence}-{phase}.json", row
        )
        contract.validate_auth_checkpoint(
            row, sequence=sequence, phase=phase, run_id=self.case.run_id
        )
        return row

    @contextmanager
    def credential_phase(
        self, sequence: int, description: Any
    ) -> Iterator[tuple[Any, dict[str, object]]]:
        from paper_radar.pi_execution import prepare_launch

        before = self.record_auth(sequence, "before")
        try:
            with prepare_launch(
                self.database,
                description,
                roots=self.execution_roots(),
                credentials_dir=self.credentials,
                auth_mode="chatgpt_subscription",
                attempt_timeout=300,
                auth_timeout=30,
            ) as prepared:
                after = self.record_auth(sequence, "after", completed=True)
                receipt: dict[str, object] = {
                    "scope": "persistent_auth_directory_separate_from_model",
                    "history": "not_assessed",
                    "lifecycle": "persistent_not_deleted",
                    "input_source": "owner_readonly_structure_review",
                    "before": before,
                    "after": after,
                }
                yield prepared, receipt
        finally:
            if not any(
                row["sequence"] == sequence and row["phase"] == "after"
                for row in self.auth_metadata_journal
            ):
                # The CLI might have rotated credentials before it failed. Keep
                # only fixed metadata, preserve the directory and do not retry.
                self.record_auth(sequence, "after")

    def execution_roots(self) -> Any:
        from paper_radar.pi_execution.resources import ExecutionRoots

        return ExecutionRoots(
            self.database.parent,
            self.materials / "config",
            self.materials,
            Path(self.supply["root"]),
        )

    def _input(self, name: str) -> tuple[Any, bytes, Any]:
        from paper_radar.config import StageName, load_config_snapshot
        from paper_radar.fulltext.models import EvidenceMap
        from paper_radar.fulltext.quality import reconstruct_context
        from paper_radar.llm import build_call, render_request
        from paper_radar.reading.context import ExtractionIdentity
        from paper_radar.stage_inputs import replay_stage_input

        item = next(c for c in self.manifest["cases"] if c["case"] == name)
        snapshot = load_config_snapshot(self.database, item["snapshot_id"])
        folder = self.materials / name
        stage = replay_stage_input(
            (folder / "stage-input.json").read_bytes(),
            item["fingerprint"],
            snapshot=snapshot,
        )
        context: Any = None
        reading = None
        if stage.stage is StageName.READ:
            extraction_raw = (folder / "extraction-input.json").read_bytes()
            extraction = replay_stage_input(
                extraction_raw,
                hashlib.sha256(extraction_raw).hexdigest(),
                snapshot=snapshot,
            )
            reading = (self.materials / "source/reading.md").read_bytes()
            map_raw = (self.materials / "source/evidence-map.json").read_bytes()
            identity = ExtractionIdentity(
                extraction.fingerprint,
                hashlib.sha256(reading).hexdigest(),
                hashlib.sha256(map_raw).hexdigest(),
            )
            context = reconstruct_context(
                EvidenceMap.model_validate_json(map_raw),
                identity,
                expected_language="zh",
            )
        elif stage.stage is StageName.VALUE:
            context = stage.value_prediction_context(
                snapshot, original_title_is_zh=False
            )
        description = build_call(
            stage,
            snapshot,
            snapshot,
            read_context=context if stage.stage is StageName.READ else None,
            reading=reading,
        )
        actual = {
            k: v.decode() if type(v) is bytes else v
            for k, v in dataclasses.asdict(description).items()
        }
        if (
            actual != json.loads((folder / "description.json").read_bytes())
            or render_request(description) != (folder / "user.txt").read_bytes()
        ):
            raise contract.CaseRejected("live_input_unknown")
        return description, render_request(description), context

    def run_cell(self, sequence: int) -> dict[str, object]:
        from paper_radar.llm.rpc import run_call
        from paper_radar.llm.rpc_frames import command_frame
        from paper_radar.llm.rpc_types import RpcCandidate
        from paper_radar.pi_execution.resources import expected_cwd_section
        from paper_radar.reading.acceptance_v2 import validate_read_output_v2
        from paper_radar.screening.validation import validate_output
        from scripts.issue167_fork_observation import CgroupReader
        from scripts.issue167_live_resources import observe_launch_resources

        name = contract.ORDER[sequence - 1]
        item = next(c for c in self.manifest["cases"] if c["case"] == name)
        self.wait(f"gate-auth-{sequence}.json", sequence)
        if self.deadline - time.monotonic() < 350:
            raise contract.CaseRejected("live_batch_deadline_unknown")
        started_monotonic = time.monotonic()
        started_at_utc = utc_now()
        check_core_site(self.root, self.case.uid)
        runtime.verify_binding(self.binding)
        local.reserve(
            self.case.worker_root / f"case-{sequence}-reserved.json", self.case.run_id
        )
        current = self._current()
        if (
            current.activation_id != self.expected_selection()["activation_id"]
            or current.snapshot_id != self.expected_selection()["snapshot_id"]
        ):
            raise contract.CaseRejected("live_selection_drift")
        activation = guarded_activate(
            self.database,
            self.supply["supply_id"],
            item["snapshot_id"],
            self.expected_selection(),
        )
        self.last_activation = activation.activation_id
        self.last_snapshot = activation.snapshot_id
        self.assert_current_expected()
        self.record_selection("batch_activation", self.expected_selection())
        description, message, context = self._input(name)
        if (
            description.provider,
            description.model,
            description.protocol,
            description.sampling,
            description.temperature,
            description.top_p,
        ) != ("openai", "gpt-6.1-sol", "prompt_only", "provider_default", None, None):
            raise contract.CaseRejected("live_model_unknown")
        meter = None
        factory_count = 0
        reader = CgroupReader(self.case.base_plan())
        with observe_launch_resources(reader, classified=True) as observed:
            with self.credential_phase(sequence, description) as (
                prepared,
                persistent_auth,
            ):
                if (
                    prepared.identity.supply_id,
                    prepared.identity.install_id,
                    prepared.identity.proxy_used,
                ) != (self.supply["supply_id"], self.supply["install_id"], False):
                    raise contract.CaseRejected("live_launch_identity_unknown")
                local.publish(
                    self.case.worker_root / f"auth-ready-{sequence}.json",
                    {
                        "run_id": self.case.run_id,
                        "sequence": sequence,
                        "auth_cli_completed": True,
                        "first_network_refresh_planned": sequence == 1,
                    },
                )
                self.wait(f"gate-model-{sequence}.json", sequence)
                self.assert_current_expected()

                def factory(desc: Any) -> Any:
                    nonlocal meter, factory_count
                    if desc != description or factory_count:
                        raise contract.CaseRejected("live_factory_unknown")
                    factory_count += 1
                    meter = SessionMeter(
                        prepared(desc),
                        command_frame("rpc-9", "prompt", message=message.decode()),
                        description.thinking_level,
                    )
                    return meter

                result: Any = run_call(
                    description,
                    message,
                    factory,
                    expected_cwd_section=expected_cwd_section(),
                )
            observed.assert_complete()
            if (
                not isinstance(result, RpcCandidate)
                or (result.provider, result.model) != ("openai", "gpt-6.1-sol")
                or meter is None
            ):
                raise contract.CaseRejected("live_rpc_unknown")
            if description.stage == "read":
                validate_read_output_v2(result.raw_response, context, attempt_ordinal=1)
            elif description.stage == "value":
                validate_output("value_prediction", result.raw_response, context)
            else:
                validate_output("boundary", result.raw_response)
            if len(observed.receipts) != 1:
                raise contract.CaseRejected("live_file_facts_unknown")
            window = contract.validate_window(
                observed.receipts[0], run_id=self.case.run_id
            )
            row = {
                "case": name,
                "sequence": sequence,
                "result": "observed_expected",
                "auth_cli_completed": True,
                "model_factory_entered": factory_count == 1,
                "explicit_prompt_completed": meter.prompt_completed == 1,
                "rpc_initial_state_clean": meter.clean,
                "rpc_commands_empty": meter.commands,
                "rpc_settled": meter.settled,
                "rpc_exit_zero": meter.exit_code == 0
                and meter.eof
                and meter.stderr_eof,
                "public_terminate_returned": meter.terminated,
                "business_validated": True,
                "model_identity_matches": True,
                "tokens": meter.usage,
                "request_counts": {
                    "model_http_lower_bound": 0,
                    "model_http_upper": "unknown",
                    "refresh_http_lower_bound": 0,
                    "refresh_http_upper": "unknown",
                    "meaning": "no_independent_HTTP_sender_observation",
                },
                "window": window,
                "protocol_metadata": {
                    "event_counts": dict(meter.counts),
                    "total_records": meter.records,
                    "prompt_frames_completed": meter.prompt_completed,
                    "prompt_ack_count": meter.prompt_ack_count,
                    "first_prompt_ack_sequence": meter.prompt_ack_sequence,
                    "first_agent_start_sequence": meter.agent_start_sequence,
                },
                "persistent_auth": persistent_auth,
            }
            result = None
        check_core_site(self.root, self.case.uid)
        runtime.verify_binding(self.binding)
        self.assert_current_expected()
        row.update(verification_timing(started_at_utc, started_monotonic))
        contract.validate_cell(sequence, row, run_id=self.case.run_id)
        local.publish(self.case.worker_root / f"case-result-{sequence}.json", row)
        return row

    def restore_selection(self) -> dict[str, object]:
        current = self._current()
        expected = self.expected_selection()
        if (
            current.activation_id != expected["activation_id"]
            or current.snapshot_id != expected["snapshot_id"]
        ):
            raise contract.CaseRejected("live_selection_restore_unknown")
        if current.snapshot_id == self.original_snapshot:
            return {
                "result": "original_selection_restored",
                "append_only_history_retained": True,
            }
        if (
            self.last_activation is None
            or current.activation_id != self.last_activation
        ):
            raise contract.CaseRejected("live_selection_restore_unknown")
        restored = guarded_activate(
            self.database,
            self.supply["supply_id"],
            self.original_snapshot,
            self.expected_selection(),
        )
        self.last_activation = restored.activation_id
        self.last_snapshot = restored.snapshot_id
        self.assert_current_expected()
        self.record_selection("restore_activation", self.expected_selection())
        if restored.snapshot_id != self.original_snapshot:
            raise contract.CaseRejected("live_selection_restore_unknown")
        return {
            "result": "original_selection_restored",
            "append_only_history_retained": True,
        }


def execute(root: Path) -> dict[str, object]:
    loaded, _, _ = contract.verify_installation(root)
    case = cast(contract.Case, loaded)
    info = case.worker_root.lstat()
    if (
        os.getuid() != case.uid
        or os.geteuid() != case.uid
        or not stat.S_ISDIR(info.st_mode)
        or info.st_uid != case.uid
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise contract.CaseRejected("live_worker_identity_unknown")
    local.reserve(case.worker_root / "worker-started.json", case.run_id)
    binding = runtime.load_binding(
        root / "live-context.json", key="application_runtime"
    )
    with runtime.application_runtime(binding, root):
        ready = local.own_metadata(case)
        local.publish(case.worker_root / "ready.json", ready)
        operations = ApplicationOperations(case, root, ready)
        operations.wait("gate-preflight.json", 0)
        result = {
            **ready,
            **run_batch(operations, run_id=case.run_id),
            "selection_journal": [
                contract.project_journal_entry(i, row, run_id=case.run_id)
                for i, row in enumerate(operations.journal)
            ],
        }
        if result["result"] == "observed_expected":
            contract.validate_result(case, result)
    local.publish(case.worker_root / "worker-result.json", result)
    if result["result"] == "observed_expected":
        operations.wait("gate-exit.json", 7)
    return result


def main() -> int:
    def interrupted(_sig: int, _frame: object) -> None:
        raise KeyboardInterrupt

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, interrupted)
    try:
        result = execute(Path(__file__).absolute().parent)
    except (Exception, KeyboardInterrupt):
        return 1
    return 0 if result["result"] == "observed_expected" else 1
