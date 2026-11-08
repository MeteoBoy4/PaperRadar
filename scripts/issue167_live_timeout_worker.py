"""Single-case T1 instrumentation. Import never launches a process or reads auth."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import signal
import stat
import time
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from scripts import issue167_live_case as previous_contract
from scripts import issue167_live_runtime as runtime
from scripts import issue167_live_timeout_case as contract
from scripts import issue167_live_worker as previous_worker
from scripts import issue167_resolver_worker as local
from scripts.issue167_live_worker import SessionMeter


def extract_materials(root: Path, destination: Path, expected: str) -> dict[str, Any]:
    destination.mkdir(mode=0o700)
    with zipfile.ZipFile(root / "materials.zip") as archive:
        entries = archive.infolist()
        if (
            len(entries) != len({i.filename for i in entries})
            or not 6 <= len(entries) <= 40
        ):
            raise contract.CaseRejected("timeout_materials_unknown")
        total = 0
        for entry in entries:
            path = Path(entry.filename)
            total += entry.file_size
            if (
                path.is_absolute()
                or ".." in path.parts
                or entry.is_dir()
                or entry.file_size > 4 * 1024 * 1024
                or total > 16 * 1024 * 1024
                or stat.S_IFMT(entry.external_attr >> 16) != stat.S_IFREG
            ):
                raise contract.CaseRejected("timeout_materials_unknown")
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(archive.read(entry))
    raw = (destination / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise contract.CaseRejected("timeout_materials_unknown")
    value = json.loads(raw)
    if (
        type(value) is not dict
        or set(value) != {"kind", "configuration_sha256", "cases"}
        or value["kind"] != "synthetic_T1_value_low_only"
        or type(value["cases"]) is not list
        or len(value["cases"]) != 1
        or value["cases"][0]["case"] != "value-low-T1"
    ):
        raise contract.CaseRejected("timeout_materials_unknown")
    expected_files = dict(value["configuration_sha256"])
    expected_files.update(
        {
            "value-low-T1/" + name: sha
            for name, sha in value["cases"][0]["sha256"].items()
        }
    )
    if {
        str(p.relative_to(destination)) for p in destination.rglob("*") if p.is_file()
    } != {"manifest.json", *expected_files}:
        raise contract.CaseRejected("timeout_materials_unknown")
    for name, sha in expected_files.items():
        if hashlib.sha256((destination / name).read_bytes()).hexdigest() != sha:
            raise contract.CaseRejected("timeout_materials_unknown")
    return value


def credential_snapshot(
    directory: Path, uid: int, gid: int, *, run_id: str, phase: str
) -> dict[str, object]:
    """Only bounded directory metadata; never open regular files for reading."""
    top = {
        "auth.json": False,
        "models-store.json": False,
        "exp2-installation-id": False,
        "node-compile-cache": True,
    }
    if (
        phase not in {"before", "after"}
        or not directory.is_absolute()
        or any(p.is_symlink() for p in (directory, *directory.parents))
    ):
        raise contract.CaseRejected("timeout_auth_snapshot_unknown")
    started = datetime.now(UTC).isoformat()
    mount_points = importlib.import_module(
        "scripts.issue167_live_timeout_cleanup"
    ).mount_points

    try:
        with Path("/proc/self/mountinfo").open("rb") as mounts:
            if any(
                point.is_relative_to(directory)
                for point in mount_points(mounts.read(1048577))
            ):
                raise ValueError
    except (OSError, ValueError):
        raise contract.CaseRejected("timeout_auth_snapshot_unknown") from None
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fds: dict[str, int] = {}
    ancestors: list[int] = []
    edges: list[tuple[int, str, int, tuple[int, ...]]] = []

    def stamp(info: os.stat_result) -> tuple[int, ...]:
        return (
            info.st_dev,
            info.st_ino,
            info.st_mode,
            info.st_uid,
            info.st_gid,
            info.st_nlink,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        )

    def check_ancestors() -> None:
        for parent, name, child, expected in edges:
            if (
                stamp(os.stat(name, dir_fd=parent, follow_symlinks=False))[:5]
                != expected
                or stamp(os.fstat(child))[:5] != expected
            ):
                raise contract.CaseRejected("timeout_auth_snapshot_unknown")

    def collect() -> dict[str, tuple[int, ...]]:
        root = os.fstat(fds["."])
        if (
            not stat.S_ISDIR(root.st_mode)
            or root.st_uid != uid
            or root.st_gid != gid
            or stat.S_IMODE(root.st_mode) != 0o700
        ):
            raise contract.CaseRejected("timeout_auth_snapshot_unknown")
        rows = {".": stamp(root)}
        pending = [(".", 0)]
        while pending:
            parent, depth = pending.pop()
            names = os.listdir(fds[parent])
            if len(names) > 64 or (parent == "." and set(names) != set(top)):
                raise contract.CaseRejected("timeout_auth_snapshot_unknown")
            for name in sorted(names):
                relative = name if parent == "." else parent + "/" + name
                if len(name.encode()) > 255 or name in {".", ".."} or "/" in name:
                    raise contract.CaseRejected("timeout_auth_snapshot_unknown")
                info = os.stat(name, dir_fd=fds[parent], follow_symlinks=False)
                directory_kind = stat.S_ISDIR(info.st_mode)
                if (
                    info.st_uid != uid
                    or info.st_gid != gid
                    or info.st_dev != root.st_dev
                    or info.st_mode & 0o022
                    or stat.S_IMODE(info.st_mode) & 0o7000
                    or not (
                        directory_kind
                        or (stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
                    )
                    or (parent == "." and directory_kind != top[name])
                    or (
                        name in {"auth.json", "models-store.json"}
                        and parent == "."
                        and stat.S_IMODE(info.st_mode) != 0o600
                    )
                ):
                    raise contract.CaseRejected("timeout_auth_snapshot_unknown")
                rows[relative] = stamp(info)
                if len(rows) > 64 or depth + 1 > 6:
                    raise contract.CaseRejected("timeout_auth_snapshot_unknown")
                if directory_kind:
                    if not (
                        relative == "node-compile-cache"
                        or relative.startswith("node-compile-cache/")
                    ):
                        raise contract.CaseRejected("timeout_auth_snapshot_unknown")
                    if relative not in fds:
                        fds[relative] = os.open(name, flags, dir_fd=fds[parent])
                    if stamp(os.fstat(fds[relative])) != stamp(info):
                        raise contract.CaseRejected("timeout_auth_snapshot_unknown")
                    pending.append((relative, depth + 1))
        check_ancestors()
        return rows

    try:
        ancestors.append(os.open("/", flags))
        for name in directory.parts[1:]:
            parent_fd = ancestors[-1]
            before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode):
                raise contract.CaseRejected("timeout_auth_snapshot_unknown")
            child_fd = os.open(name, flags, dir_fd=parent_fd)
            ancestors.append(child_fd)
            expected = stamp(before)[:5]
            if stamp(os.fstat(child_fd))[:5] != expected:
                raise contract.CaseRejected("timeout_auth_snapshot_unknown")
            edges.append((parent_fd, name, child_fd, expected))
        check_ancestors()
        fds["."] = ancestors[-1]
        first = collect()
        second = collect()
        if first != second or set(fds) != {
            k for k, v in first.items() if stat.S_ISDIR(v[2])
        }:
            raise contract.CaseRejected("timeout_auth_snapshot_unknown")
    except (OSError, UnicodeError):
        raise contract.CaseRejected("timeout_auth_snapshot_unknown") from None
    finally:
        for fd in set(fds.values()) | set(ancestors):
            os.close(fd)
    # Internal identity/permission checks above are never exported as additional
    # snapshot fields. Only the four owner-authorized stat values and path set.
    nodes = {
        name: {"inode": row[1], "size": row[6], "mtime_ns": row[7], "ctime_ns": row[8]}
        for name, row in sorted(first.items())
    }
    snapshot = {
        "scope": "bounded_auth_and_cache_metadata_only",
        "integrity": "complete",
        "nodes": nodes,
        "node_count": len(nodes),
        "max_nodes": 64,
        "max_depth": 6,
        "regular_contents_read": False,
        "marker_content_used_as_authority": False,
        "write_history": "not_assessed",
        "writer_identity": "not_assessed",
    }
    if len(json.dumps(snapshot, sort_keys=True).encode()) > 16384:
        raise contract.CaseRejected("timeout_auth_snapshot_unknown")
    return {
        "started_at_utc": started,
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "snapshot": snapshot,
    }


class ApplicationOperations(previous_worker.ApplicationOperations):
    """Independent case loop; stable public auth/resource helpers are reused."""

    case: Any

    def __init__(
        self,
        case: contract.Case,
        root: Path,
        ready: dict[str, object],
        window: TimeoutWindow,
    ) -> None:
        self.case = case
        self.root = root
        self.ready = ready
        self.window = window
        self.deadline = time.monotonic() + case.worker_timeout_s
        self.context: dict[str, Any] = contract.read_metadata(
            root / "live-context.json", owner=0, limit=contract.CONTEXT_LIMIT
        )  # type: ignore[assignment]
        self.binding = runtime.load_binding(
            root / "live-context.json", key="application_runtime"
        )
        self.project = Path(self.binding["source_parent"]).parent
        self.database = self.project / ".scratch/exp-2/data/exp2.sqlite3"
        self.credentials = self.project / ".scratch/exp-2/credentials"
        self.supply = self.context["supply"]
        self.materials = case.worker_root / "materials"
        self.manifest = extract_materials(
            root, self.materials, self.context["synthetic_manifest_sha256"]
        )
        if self.manifest["cases"][0]["fingerprint"] != window.fingerprint:
            raise contract.CaseRejected("timeout_materials_unknown")
        self.last_activation = None
        self.last_snapshot = None
        self.journal: list[dict[str, object]] = []
        self.auth_metadata_journal: list[dict[str, object]] = []
        self.original_snapshot = self.supply["registration"]["snapshot_id"]

    def preflight(self) -> dict[str, object]:
        import shutil

        from paper_radar.config import compile_config
        from paper_radar.pi_execution.isolation import isolation_capability
        from paper_radar.pi_execution.resources import (
            SETTINGS_JSON,
            check_credentials_directory,
            check_cwd,
        )
        from paper_radar.screening.validation import validate_output
        from scripts.issue167_fork_observation import CgroupReader
        from scripts.issue167_live_ipc import run_ipc_preflight
        from scripts.issue167_session_observation import ClassifiedSessionObservation

        previous_worker.check_core_site(self.root, self.case.uid)
        check_cwd()
        if any(
            not p.is_relative_to(Path("/home"))
            for p in (Path(os.readlink("/proc/self/exe")), Path(self.supply["node"]))
        ):
            raise contract.CaseRejected("live_core_applicability_unknown")
        if isolation_capability() < 6:
            raise contract.CaseRejected("live_isolation_unknown")
        self.assert_current_expected()
        self.record_selection("original", self.expected_selection())
        check_credentials_directory(self.credentials, self.execution_roots())
        previous_worker.auth_directory_metadata(self.credentials, self.case.uid)
        ipc = run_ipc_preflight(
            self.case.worker_root / "ipc", min(self.deadline, time.monotonic() + 180)
        )
        if (
            ipc.get("result") != "observed_expected"
            or ipc.get("integrity") != "complete"
        ):
            raise contract.CaseRejected("live_ipc_unknown")
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
            shutil.rmtree(observer_root)
            observed.check_deleted()
            if observed.receipt()["result"] != "session_window_complete":
                raise contract.CaseRejected("live_observer_preflight_unknown")
        snapshot = compile_config(
            self.materials / "config/settings-low.yaml", self.database
        )
        if snapshot.snapshot_id != self.manifest["cases"][0]["snapshot_id"]:
            raise contract.CaseRejected("live_snapshot_unknown")
        _description, _message, context = self._input("value-low-T1")
        validate_output(
            "value_prediction",
            (self.materials / "value-low-T1/expected-valid-output.json").read_bytes(),
            context,
        )
        result = {
            "result": "observed_expected",
            "ipc_integrity": "complete",
            "ipc": ipc,
            "synthetic_snapshots_registered": 1,
            "credential_contents_read": False,
            "observer_backend_initialized": True,
        }
        local.publish(self.case.worker_root / "preflight-result.json", result)
        return result

    def record_auth(
        self, sequence: int, phase: str, *, completed: bool = False
    ) -> dict[str, object]:
        if sequence != 1 or phase not in {"before", "after"}:
            raise contract.CaseRejected("timeout_auth_observation_unknown")
        row: dict[str, object] = {
            "scope": "persistent_auth_metadata_checkpoint",
            "run_id": self.case.run_id,
            "sequence": 1,
            "phase": phase,
            "result": "metadata_verified"
            if phase == "before"
            else "authentication_completed"
            if completed
            else "unknown",
            "refresh": "possible_not_independently_observed",
            "metadata": previous_worker.auth_directory_metadata(
                self.credentials, self.case.uid
            ),
            "filesystem_snapshot": credential_snapshot(
                self.credentials,
                self.case.uid,
                self.case.gid,
                run_id=self.case.run_id,
                phase=phase,
            ),
        }
        self.auth_metadata_journal.append(row)
        local.publish(self.case.worker_root / f"auth-metadata-1-{phase}.json", row)
        return row

    @contextmanager
    def credential_phase(
        self, sequence: int, description: Any
    ) -> Iterator[tuple[Any, dict[str, object]]]:
        from paper_radar.pi_execution import prepare_launch

        self.window.phase = "auth"
        before = self.record_auth(1, "before")
        auth_started = datetime.now(UTC).isoformat()
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
                auth_returned = datetime.now(UTC).isoformat()
                after = self.record_auth(1, "after", completed=True)
                self.window.phase = "prepared"
                yield (
                    prepared,
                    {
                        "scope": "persistent_auth_directory_separate_from_model",
                        "history": "not_assessed",
                        "lifecycle": "persistent_not_deleted",
                        "input_source": "conditional_H2_plan",
                        "before": before,
                        "after": after,
                        "execution_interval": {
                            "scope": "public_prepare_launch_including_auth",
                            "started_at_utc": auth_started,
                            "returned_at_utc": auth_returned,
                            "outcome": "returned_prepared",
                            "exact_cli_pid_or_writer_attribution": "not_assessed",
                        },
                    },
                )
        finally:
            if not any(r["phase"] == "after" for r in self.auth_metadata_journal):
                self.record_auth(1, "after")

    def run_case(self) -> dict[str, object]:
        from paper_radar.llm.rpc import run_call
        from paper_radar.llm.rpc_frames import command_frame
        from paper_radar.llm.rpc_types import RpcCandidate, RpcFailure
        from paper_radar.pi_execution.resources import expected_cwd_section
        from paper_radar.screening.validation import validate_output
        from scripts.issue167_fork_observation import CgroupReader
        from scripts.issue167_live_resources import observe_launch_resources

        self.wait("gate-auth-1.json", 1)
        local.reserve(self.case.worker_root / "case-1-reserved.json", self.case.run_id)
        started = time.monotonic()
        started_utc = previous_worker.utc_now()
        previous_worker.check_core_site(self.root, self.case.uid)
        runtime.verify_binding(self.binding)
        self.assert_current_expected()
        item = self.manifest["cases"][0]
        activation = previous_worker.guarded_activate(
            self.database,
            self.supply["supply_id"],
            item["snapshot_id"],
            self.expected_selection(),
        )
        self.last_activation, self.last_snapshot = (
            activation.activation_id,
            activation.snapshot_id,
        )
        self.assert_current_expected()
        self.record_selection("batch_activation", self.expected_selection())
        description, message, context = self._input(contract.CASE_NAME)
        expected_identity = {
            "provider": "openai",
            "model": "gpt-6.1-sol",
            "stage": "value",
            "thinking_level": "low",
            "protocol": "prompt_only",
            "sampling": "provider_default",
            "temperature": None,
            "top_p": None,
            "auth_mode": "chatgpt_subscription",
        }
        if {
            k: getattr(description, k) for k in expected_identity if k != "auth_mode"
        } != {k: v for k, v in expected_identity.items() if k != "auth_mode"}:
            raise contract.CaseRejected("live_model_unknown")
        meter: TimeoutMeter | None = None
        factory_count = 0
        normal_validated = False
        normal_completion = None
        persistent_auth: dict[str, object] | None = None
        with observe_launch_resources(
            CgroupReader(self.case.base_plan()), classified=True
        ) as observed:
            with self.credential_phase(1, description) as (prepared, persistent_auth):
                if (
                    prepared.identity.supply_id,
                    prepared.identity.install_id,
                    prepared.identity.proxy_used,
                ) != (self.supply["supply_id"], self.supply["install_id"], False):
                    raise contract.CaseRejected("live_launch_identity_unknown")
                local.publish(
                    self.case.worker_root / "auth-ready-1.json",
                    {
                        "run_id": self.case.run_id,
                        "sequence": 1,
                        "auth_cli_completed": True,
                        "logical_refresh_plan": contract.AUTH_REFRESH_PLAN,
                    },
                )
                self.wait("gate-model-1.json", 1)
                self.assert_current_expected()

                def factory(desc: Any) -> TimeoutMeter:
                    nonlocal meter, factory_count
                    if desc != description or factory_count:
                        raise contract.CaseRejected("live_factory_unknown")
                    factory_count += 1
                    self.window.factory_entered = time.monotonic()
                    meter = TimeoutMeter(
                        prepared(desc),
                        command_frame("rpc-9", "prompt", message=message.decode()),
                        "low",
                        self.window,
                        lambda value: local.publish(
                            self.case.worker_root / "timeout-ready.json", value
                        ),
                    )
                    return meter

                self.window.phase = "model_call"
                public_started = time.monotonic()
                try:
                    candidate: Any = run_call(
                        description,
                        message,
                        factory,
                        expected_cwd_section=expected_cwd_section(),
                    )
                finally:
                    public_returned = time.monotonic()
                    self.window.phase = "model_cleanup"
                if meter is None:
                    raise contract.CaseRejected("timeout_observation_unknown")
                if isinstance(candidate, RpcCandidate):
                    if (candidate.provider, candidate.model) != (
                        "openai",
                        "gpt-6.1-sol",
                    ):
                        raise contract.CaseRejected("live_rpc_unknown")
                    validate_output("value_prediction", candidate.raw_response, context)
                    normal_completion = {
                        "candidate_validated": True,
                        "response_identity_matches": True,
                        "agent_settled": meter.settled,
                        "stdout_eof": meter.eof,
                        "stderr_eof": meter.stderr_eof,
                        "exit_zero": meter.exit_code == 0,
                        "public_terminate_returned": meter.terminated,
                    }
                    normal_validated = True
                    public_reason = "candidate"
                    candidate = None
                elif isinstance(candidate, RpcFailure):
                    public_reason = candidate.reason.value
                else:
                    raise contract.CaseRejected("live_rpc_unknown")
            observed.assert_complete()
            if persistent_auth is None or len(observed.receipts) != 1:
                raise contract.CaseRejected("timeout_observation_unknown")
            timeout_row = self.window.finish(
                factory_count=factory_count,
                reason=public_reason,
                started=public_started,
                returned=public_returned,
            )
            result = (
                "observed_expected"
                if public_reason == "timeout" and self.window.marker_publications == 1
                else "not_triggered"
            )
            usage = (
                meter.usage
                if meter.usage is not None and meter.usage["totalTokens"] > 0
                else None
            )
            row = {
                "scope": contract.SCOPE,
                "run_id": self.case.run_id,
                "case": contract.CASE_NAME,
                "result": result,
                "candidate_committed": False,
                "auth_cli_completed": True,
                "timeout": timeout_row,
                "window": previous_contract.validate_window(
                    observed.receipts[0], run_id=self.case.run_id
                ),
                "fingerprint": self.window.fingerprint,
                "requested_identity": expected_identity,
                "rpc_initial_state_clean": meter.clean,
                "rpc_commands_empty": meter.commands,
                "normal_candidate_validated": normal_validated,
                "normal_completion": normal_completion,
                "protocol_metadata": {
                    "event_counts": dict(meter.counts),
                    "total_records": meter.records,
                    "prompt_frames_completed": meter.prompt_completed,
                    "prompt_ack_count": meter.prompt_ack_count,
                    "first_prompt_ack_sequence": meter.prompt_ack_sequence,
                    "first_agent_start_sequence": meter.agent_start_sequence,
                },
                "persistent_auth": persistent_auth,
                "tokens": usage,
                "token_status": "pi_reported" if usage is not None else "unknown",
                "request_counts": {
                    "model_http_lower_bound": 0,
                    "model_http_upper": "unknown",
                    "refresh_http_lower_bound": 0,
                    "refresh_http_upper": "unknown",
                    "meaning": "no_independent_HTTP_sender_observation",
                },
            }
        previous_worker.check_core_site(self.root, self.case.uid)
        runtime.verify_binding(self.binding)
        self.assert_current_expected()
        row.update(previous_worker.verification_timing(started_utc, started))
        contract.validate_row(row, run_id=self.case.run_id)
        return row

    def restore_selection(self) -> dict[str, object]:
        self.window.phase = "restoring"
        return super().restore_selection()

    def auth_journal(self) -> list[dict[str, object]]:
        return [contract.auth_reference(row) for row in self.auth_metadata_journal]


class TimeoutWindow:
    """Only decoded metadata is published; the reader never waits for a gate."""

    def __init__(self, run_id: str, fingerprint: str) -> None:
        self.run_id = run_id
        self.fingerprint = fingerprint
        self.phase = "before_auth"
        self.marker_publications = 0
        self.marker: dict[str, object] | None = None
        self.meter: TimeoutMeter | None = None
        self.factory_entered: float | None = None

    def observe(
        self, text_sequence: int | None, publish: Callable[[dict[str, object]], None]
    ) -> None:
        meter = self.meter
        if (
            self.marker_publications
            or text_sequence is None
            or self.phase != "model_call"
            or meter is None
            or meter.closing
            or meter.terminal_seen
            or meter.prompt_completed != 1
            or meter.prompt_ack_count != 1
            or meter.prompt_ack_sequence is None
            or meter.agent_start_sequence is None
            or meter.counts["agent_start"] != 1
            or meter.counts["agent_settled"] != 0
            or meter.settled
            or meter.eof
            or meter.stderr_eof
            or meter.terminated
            or meter.exit_code is not None
        ):
            return
        marker = {
            "scope": contract.SCOPE,
            "run_id": self.run_id,
            "category": "decoded_nonempty_text_duplex_window",
            "sequence": 1,
            "count": 1,
            "fingerprint": self.fingerprint,
            "prompt_frames_completed": 1,
            "prompt_ack_count": 1,
            "agent_settled": False,
            "closing": False,
            "integrity": "complete",
            "prompt_ack_sequence": meter.prompt_ack_sequence,
            "agent_start_sequence": meter.agent_start_sequence,
            "text_delta_sequence": text_sequence,
            "observed_monotonic": time.monotonic(),
        }
        contract.validate_marker(
            marker, run_id=self.run_id, fingerprint=self.fingerprint
        )
        self.marker_publications = 1
        self.marker = marker
        publish(marker)

    def finish(
        self, *, factory_count: int, reason: str, started: float, returned: float
    ) -> dict[str, object]:
        self.phase = "complete"
        meter = self.meter
        value = {
            "phase": self.phase,
            "marker_publications": self.marker_publications,
            "marker": self.marker,
            "public_reason": reason,
            "public_started_monotonic": started,
            "public_returned_monotonic": returned,
            "public_elapsed_seconds": returned - started,
            "factory_entered_monotonic": self.factory_entered,
            "model_factory_count": factory_count,
            "public_terminate_returned": meter is not None and meter.terminated,
            "owner_reconciliation_required": True,
            "model_error_terminal_count": meter.model_error_terminal_count
            if meter is not None
            else 0,
        }
        contract.validate_timeout(
            value, run_id=self.run_id, fingerprint=self.fingerprint
        )
        return value


class TimeoutMeter(SessionMeter):
    """Preserve transport and decode entire batch before one text marker decision."""

    def __init__(
        self,
        session: Any,
        prompt: bytes,
        level: str,
        window: TimeoutWindow,
        publish: Callable[[dict[str, object]], None],
    ) -> None:
        from paper_radar.llm.rpc_frames import FrameDecoder

        super().__init__(session, prompt, level)
        if window.meter is not None:
            raise contract.CaseRejected("timeout_factory_reused")
        window.meter = self
        self.window = window
        self.publish = publish
        self.closing = False
        self.terminal_seen = False
        self.model_error_terminal_count = 0
        self.observation_decoder = FrameDecoder()
        self.observation_records = 0

    def pump(self, pending: bytes, timeout: float, /) -> Any:
        event = super().pump(pending, timeout)
        first_text = None
        for record in self.observation_decoder.feed(event.stdout):
            self.observation_records += 1
            kind = record.get("type")
            if kind in {"turn_end", "agent_end", "agent_settled"}:
                self.terminal_seen = True
            if kind == "message_end":
                ended = record.get("message")
                # Normal user/system message lifecycle precedes assistant text.
                # Unknown message shapes are ineligible, never guessed safe.
                if type(ended) is not dict or ended.get("role") not in {
                    "user",
                    "system",
                }:
                    self.terminal_seen = True
            if kind == "message_end":
                message = record.get("message")
                if (
                    type(message) is dict
                    and message.get("role") == "assistant"
                    and message.get("stopReason") == "error"
                ):
                    self.model_error_terminal_count += 1
            update = (
                record.get("assistantMessageEvent")
                if kind == "message_update"
                else None
            )
            if (
                first_text is None
                and type(update) is dict
                and update.get("type") == "text_delta"
                and type(update.get("delta")) is str
                and bool(update["delta"])
                and type(update.get("contentIndex")) is int
                and update["contentIndex"] >= 0
            ):
                first_text = self.observation_records
        if event.stdout_eof:
            self.observation_decoder.finish()
        if self.observation_records != self.records:
            raise contract.CaseRejected("timeout_observation_unknown")
        self.window.observe(first_text, self.publish)
        return event

    def close_stdin(self) -> None:
        self.closing = True
        self.window.phase = "model_cleanup"
        super().close_stdin()

    def terminate(self, timeout: float, /) -> None:
        self.closing = True
        self.window.phase = "model_cleanup"
        super().terminate(timeout)


class CaseOperations(Protocol):
    def preflight(self) -> dict[str, object]: ...
    def run_case(self) -> dict[str, object]: ...
    def restore_selection(self) -> dict[str, object]: ...
    def auth_journal(self) -> list[dict[str, object]]: ...


def run_one(operations: CaseOperations, *, run_id: str) -> dict[str, object]:
    """One nonrefundable case, then public selection restoration and metadata."""
    from scripts.issue167_resolver_owner import cleanup_signals, metadata_equal

    result: dict[str, object] = {
        "scope": contract.SCOPE,
        "run_id": run_id,
        "result": "unknown",
        "limits": dict(contract.LIMITS),
        "preflight": None,
        "case": None,
        "selection_restoration": None,
        "auth_metadata_journal": [],
    }
    try:
        result["preflight"] = contract.validate_preflight(operations.preflight())
        row = contract.validate_row(operations.run_case(), run_id=run_id)
        result["case"] = row
        result["result"] = row["result"]
    except (Exception, KeyboardInterrupt, SystemExit):
        result["failure_reason"] = "timeout_case_unknown"
    finally:
        try:
            with cleanup_signals():
                restored = operations.restore_selection()
            if not metadata_equal(
                restored,
                {
                    "result": "original_selection_restored",
                    "append_only_history_retained": True,
                },
            ):
                raise contract.CaseRejected("timeout_selection_restore_unknown")
            result["selection_restoration"] = restored
        except BaseException:
            result["result"] = "unknown"
            result["selection_restoration"] = {
                "result": "unknown",
                "append_only_history_retained": True,
            }
        try:
            result["auth_metadata_journal"] = operations.auth_journal()
        except BaseException:
            result["result"] = "unknown"
            result["auth_metadata_error"] = "timeout_auth_observation_unknown"
    return result


def execute(root: Path) -> dict[str, object]:
    loaded, _, _ = contract.verify_installation(root)
    case = loaded
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
    window = TimeoutWindow(case.run_id, case.case_fingerprint)  # type: ignore[attr-defined]
    with runtime.application_runtime(binding, root):
        ready = local.own_metadata(case)
        local.publish(case.worker_root / "ready.json", ready)
        operations = ApplicationOperations(case, root, ready, window)  # type: ignore[arg-type]
        operations.wait("gate-preflight.json", 0)
        result = {
            **ready,
            **run_one(operations, run_id=case.run_id),
            "selection_journal": [
                previous_contract.project_journal_entry(i, r, run_id=case.run_id)
                for i, r in enumerate(operations.journal)
            ],
        }
    if result["result"] in {"observed_expected", "not_triggered"}:
        try:
            contract.validate_result(case, result)
            local.publish(case.worker_root / "case-result-1.json", result["case"])
        except (Exception, KeyboardInterrupt, SystemExit):
            result.update(
                result="unknown", failure_reason="timeout_final_evidence_unknown"
            )
    local.publish(case.worker_root / "worker-result.json", result)
    if result["result"] in {"observed_expected", "not_triggered"}:
        operations.wait("gate-exit.json", 7)
    return result


def main() -> int:
    def interrupted(_sig: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        result = execute(Path(__file__).absolute().parent)
    except (Exception, KeyboardInterrupt, SystemExit):
        return 1
    return 0 if result["result"] in {"observed_expected", "not_triggered"} else 1
