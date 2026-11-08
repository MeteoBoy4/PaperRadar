"""Independent D1: closed batch/DB-CAS gates; no actual credentials or runtime."""

import hashlib
import json
import os
import pwd
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy import create_engine

from scripts import issue167_live_case as contract
from scripts import issue167_live_owner as owner
from scripts import issue167_live_worker as worker
from scripts.issue167_resolver_owner import OwnerRejected

RUN = "e93f7b82c461"


def protocol() -> dict[str, Any]:
    counts = {
        "response": 9,
        "agent_start": 1,
        "turn_start": 1,
        "message_start": 3,
        "message_update": 0,
        "message_end": 3,
        "turn_end": 1,
        "agent_end": 1,
        "agent_settled": 1,
        "thinking_level_changed": 0,
    }
    return {
        "event_counts": counts,
        "total_records": 20,
        "prompt_frames_completed": 1,
        "prompt_ack_count": 1,
        "first_prompt_ack_sequence": 9,
        "first_agent_start_sequence": 10,
    }


def auth_metadata() -> dict[str, Any]:
    return {
        "scope": "fixed_auth_metadata_paths_only",
        "directory_private_owned": True,
        "auth_regular_private_owned": True,
        "models_configuration_absent": True,
        "models_store": "regular_private_owned",
        "compile_cache": "directory_owned",
        "contents_read": False,
        "content_shape_verified_by_agent": False,
    }


def persistent_auth(sequence: int) -> dict[str, Any]:
    value: dict[str, Any] = {
        "scope": "persistent_auth_directory_separate_from_model",
        "history": "not_assessed",
        "lifecycle": "persistent_not_deleted",
        "input_source": "owner_readonly_structure_review",
    }
    for phase in ("before", "after"):
        value[phase] = {
            "scope": "persistent_auth_metadata_checkpoint",
            "run_id": RUN,
            "sequence": sequence,
            "phase": phase,
            "result": "metadata_verified"
            if phase == "before"
            else "authentication_completed",
            "first_network_refresh_planned": sequence == 1,
            "metadata": auth_metadata(),
        }
    return value


def cell(sequence: int = 1) -> dict[str, Any]:
    inventory = {
        name: {"regular": 0, "directory": 0, "other": 0}
        for name in (
            "baseline",
            "auth_store",
            "model_store",
            "store_lock",
            "compile_cache",
            "session",
            "unknown",
        )
    }
    inventory["baseline"] = {"regular": 1, "directory": 3, "other": 0}
    inventory["auth_store"]["regular"] = 1
    inventory["model_store"]["regular"] = 1
    inventory["compile_cache"] = {"regular": 2, "directory": 2, "other": 0}
    window = {
        "scope": "classified_session_observation",
        "run_id": RUN,
        "source": "kernel_own_cgroup_metadata",
        "event_source": "inotify",
        "result": "session_window_complete",
        "category": "attempt_files",
        "sequence": 1,
        "session_history": "zero_observed",
        "session_mutation_events": 0,
        "session_integrity": "complete",
        "guard_integrity": "complete",
        "unknown_mutation_events": 0,
        "known_non_session_history": "not_assessed",
        "non_session_event_lower_bounds": {
            "auth_store": 1,
            "model_store": 1,
            "store_lock": 1,
            "compile_cache": 1,
            "control_settings": 1,
        },
        "event_count_semantics": "observed_inotify_records_lower_bound_not_write_count",
        "settings_semantics": True,
        "terminal_status": "classified_snapshot",
        "terminal_inventory": inventory,
        "terminal_integrity": "complete",
        "directory_deleted": True,
        "cleanup_integrity": "complete",
        "post_terminal_write_events": 0,
        "reasons": [],
    }
    row = {
        "case": contract.ORDER[sequence - 1],
        "sequence": sequence,
        "result": "observed_expected",
        "tokens": {
            "input": 1,
            "output": 1,
            "cacheRead": 0,
            "cacheWrite": 0,
            "totalTokens": 2,
        },
        "request_counts": {
            "model_http_lower_bound": 0,
            "model_http_upper": "unknown",
            "refresh_http_lower_bound": 0,
            "refresh_http_upper": "unknown",
            "meaning": "no_independent_HTTP_sender_observation",
        },
        "window": window,
        "protocol_metadata": protocol(),
        "persistent_auth": persistent_auth(sequence),
        "started_at_utc": "2000-01-01T00:00:00+00:00",
        "verified_at_utc": "2000-01-01T00:00:01+00:00",
        "started_monotonic": 1.0,
        "verified_monotonic": 2.0,
        "elapsed_seconds": 1.0,
    }
    row.update(
        {
            key: True
            for key in (
                "auth_cli_completed",
                "model_factory_entered",
                "explicit_prompt_completed",
                "rpc_initial_state_clean",
                "rpc_commands_empty",
                "rpc_settled",
                "rpc_exit_zero",
                "public_terminate_returned",
                "business_validated",
                "model_identity_matches",
            )
        }
    )
    return row


@pytest.mark.parametrize(
    "change",
    [
        "bool_lower",
        "bool_token",
        "other_run",
        "other_scope",
        "mutation",
        "empty_protocol",
        "bool_sequence",
        "missing_ack",
        "extra_raw",
    ],
)
def test_cell_refuses_partial_or_misbound_facts(change: str) -> None:
    row = cell()
    if change == "bool_lower":
        row["request_counts"]["model_http_lower_bound"] = False
    elif change == "bool_token":
        row["tokens"]["input"] = True
    elif change == "other_run":
        row["window"]["run_id"] = "a" * 12
    elif change == "other_scope":
        row["window"]["scope"] = "other"
    elif change == "mutation":
        row["window"]["session_mutation_events"] = 1
        row["window"]["session_history"] = "observed_mutation"
    elif change == "empty_protocol":
        row["protocol_metadata"] = {}
    elif change == "bool_sequence":
        row["protocol_metadata"]["first_prompt_ack_sequence"] = True
    elif change == "missing_ack":
        row["protocol_metadata"]["prompt_ack_count"] = 0
    else:
        row["raw_response"] = "synthetic forbidden content"
    with pytest.raises(contract.CaseRejected, match="live_"):
        contract.validate_cell(1, row, run_id=RUN)


def test_valid_cell_is_small_and_retains_independent_unknown_HTTP() -> None:
    row = contract.validate_cell(1, cell(), run_id=RUN)
    counts = row["request_counts"]
    assert isinstance(counts, dict)
    assert counts["model_http_upper"] == "unknown"
    assert len(json.dumps(row)) < 5000


def test_known_cache_writes_do_not_become_session_or_exact_write_counts() -> None:
    row = cast(dict[str, Any], contract.validate_cell(1, cell(), run_id=RUN))
    assert row["window"]["known_non_session_history"] == "not_assessed"
    assert row["window"]["terminal_inventory"]["compile_cache"]["regular"] == 2
    assert row["persistent_auth"]["history"] == "not_assessed"
    assert row["persistent_auth"]["lifecycle"] == "persistent_not_deleted"


@pytest.mark.parametrize("value", [False, 1, "true"])
def test_public_control_settings_semantics_must_be_verified_boolean(
    value: object,
) -> None:
    row = cell()
    row["window"]["settings_semantics"] = value
    with pytest.raises(contract.CaseRejected, match="live_file_facts_unknown"):
        contract.validate_cell(1, row, run_id=RUN)


@pytest.mark.parametrize("change", ["none", "pattern", "missing", "source"])
def test_current_core_pipe_and_all_bound_collector_sources_are_required(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    sources = {
        Path("/synthetic/handler"): b"synthetic-collector",
        Path("/synthetic/fileutils"): b"synthetic-fileutils",
        Path("/synthetic/report"): b"synthetic-report",
    }
    hashes = {path: hashlib.sha256(raw).hexdigest() for path, raw in sources.items()}
    monkeypatch.setattr(worker, "_CORE_SOURCE_HASHES", hashes)

    def read(path: Path, _limit: int) -> bytes:
        if path == Path("/proc/sys/kernel/core_pattern"):
            if change == "pattern":
                return b"|/synthetic/other-handler\n"
            return worker._CORE_PATTERN
        if change == "missing":
            raise FileNotFoundError
        if change == "source" and path.name == "fileutils":
            return b"changed-public-source"
        return sources[path]

    if change == "none":
        worker.check_core_policy(reader=read)
    else:
        with pytest.raises(
            contract.CaseRejected, match="live_core_applicability_unknown"
        ):
            worker.check_core_policy(reader=read)


@pytest.mark.parametrize("state", ["absent", "permission_unknown", "present"])
def test_core_settings_absence_is_not_inferred_from_stat_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(pwd, "getpwuid", lambda _: SimpleNamespace(pw_dir=str(home)))
    original = Path.lstat

    def lstat(path: Path) -> Any:
        if path == home / ".config/apport/settings":
            if state == "absent":
                raise FileNotFoundError
            if state == "permission_unknown":
                raise PermissionError
            return SimpleNamespace()
        return original(path)

    monkeypatch.setattr(Path, "lstat", lstat)
    if state == "absent":
        worker.check_user_core_config(1000)
    else:
        with pytest.raises(
            contract.CaseRejected, match="live_core_applicability_unknown"
        ):
            worker.check_user_core_config(1000)


@pytest.mark.parametrize(
    "category,field,count",
    [
        ("auth_store", "regular", 2),
        ("model_store", "directory", 1),
        ("store_lock", "regular", 1),
        ("store_lock", "directory", 4),
        ("compile_cache", "directory", 0),
        ("compile_cache", "regular", 100001),
    ],
)
def test_terminal_known_category_shapes_cannot_be_self_attested(
    category: str, field: str, count: int
) -> None:
    row = cell()
    row["window"]["terminal_inventory"][category][field] = count
    with pytest.raises(contract.CaseRejected, match="live_file_facts_unknown"):
        contract.validate_cell(1, row, run_id=RUN)


def test_three_source_bound_lock_directories_are_known_but_fourth_is_not() -> None:
    row = cell()
    row["window"]["terminal_inventory"]["store_lock"]["directory"] = 3
    contract.validate_cell(1, row, run_id=RUN)


def test_lower_bound_totals_cannot_exceed_total_decoded_event_cap() -> None:
    row = cell()
    row["window"]["non_session_event_lower_bounds"] = {
        category: 100000
        for category in (
            "auth_store",
            "model_store",
            "store_lock",
            "compile_cache",
            "control_settings",
        )
    }
    with pytest.raises(contract.CaseRejected, match="live_file_facts_unknown"):
        contract.validate_cell(1, row, run_id=RUN)


@pytest.mark.parametrize(
    "change",
    [
        "owner_not_source",
        "bool_plan",
        "wrong_seq",
        "content_read",
        "pretend_zero_history",
    ],
)
def test_persistent_auth_checkpoints_never_claim_content_or_full_history(
    change: str,
) -> None:
    row = cell()
    value = row["persistent_auth"]
    if change == "owner_not_source":
        value["input_source"] = "agent_verified_contents"
    elif change == "bool_plan":
        value["after"]["first_network_refresh_planned"] = 1
    elif change == "wrong_seq":
        value["after"]["sequence"] = 2
    elif change == "content_read":
        value["before"]["metadata"]["contents_read"] = True
    else:
        value["history"] = "zero_observed"
    with pytest.raises(contract.CaseRejected, match="live_auth_"):
        contract.validate_cell(1, row, run_id=RUN)


@pytest.fixture
def auth_directory(tmp_path: Path) -> Path:
    root = tmp_path / "private-auth"
    root.mkdir(mode=0o700)
    (root / "auth.json").write_bytes(b"synthetic-private-never-read")
    (root / "auth.json").chmod(0o600)
    (root / "models-store.json").write_bytes(b"synthetic-catalog-never-read")
    (root / "models-store.json").chmod(0o600)
    (root / "node-compile-cache").mkdir(mode=0o700)
    return root


def test_auth_checkpoints_only_lstat_fixed_paths(
    auth_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(
            Path, "read_bytes", lambda *_: pytest.fail("credential_bytes_forbidden")
        )
        patch.setattr(
            Path, "open", lambda *_a, **_kw: pytest.fail("credential_open_forbidden")
        )
        value = worker.auth_directory_metadata(auth_directory, os.getuid())
    assert value == auth_metadata()


@pytest.mark.parametrize(
    "change", ["models_override", "auth_link", "public_auth", "store_link"]
)
def test_auth_metadata_uncertainty_stops_before_CLI(
    auth_directory: Path, change: str
) -> None:
    if change == "models_override":
        (auth_directory / "models.json").touch()
    elif change == "public_auth":
        (auth_directory / "auth.json").chmod(0o644)
    elif change == "auth_link":
        (auth_directory / "auth.json").unlink()
        (auth_directory / "auth.json").symlink_to("models-store.json")
    else:
        (auth_directory / "models-store.json").unlink()
        (auth_directory / "models-store.json").symlink_to("auth.json")
    with pytest.raises(contract.CaseRejected, match="live_auth_metadata_unknown"):
        worker.auth_directory_metadata(auth_directory, os.getuid())


def test_failed_authentication_keeps_unknown_metadata_and_input(
    auth_directory: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar import pi_execution

    ops = worker.ApplicationOperations.__new__(worker.ApplicationOperations)
    ops.credentials = auth_directory
    ops.database = tmp_path / "not-opened.sqlite3"
    control = tmp_path / "controller"
    control.mkdir()
    ops.case = contract.Case(
        RUN, os.getuid(), os.getgid(), "a" * 64, "b" * 64, "c" * 64
    )
    monkeypatch.setattr(type(ops.case), "worker_root", property(lambda _: control))
    ops.auth_metadata_journal = []
    monkeypatch.setattr(ops, "execution_roots", lambda: None)
    calls: list[str] = []

    @contextmanager
    def fail_refresh(*_a: Any, **_kw: Any) -> Any:
        calls.append("auth")
        raise ValueError("synthetic-network-refresh-failure")
        yield

    monkeypatch.setattr(pi_execution, "prepare_launch", fail_refresh)
    with (
        pytest.raises(contract.CaseRejected, match="live_auth_checkpoint_unknown"),
        ops.credential_phase(1, object()),
    ):
        pytest.fail("model_must_not_start")
    assert len(ops.auth_metadata_journal) == 2
    assert calls == ["auth"]
    assert ops.auth_metadata_journal[0]["first_network_refresh_planned"] is True
    assert ops.auth_metadata_journal[1]["result"] == "unknown"
    assert (auth_directory / "auth.json").is_file()
    assert (auth_directory / "models-store.json").is_file()


@pytest.mark.parametrize("sequence,after", [(1, (0, 0)), (1, (2, 0)), (2, (0, 0))])
def test_first_auth_is_network_phase_but_packets_are_not_refresh_HTTP_count(
    monkeypatch: pytest.MonkeyPatch, sequence: int, after: tuple[int, int]
) -> None:
    ops = owner.LiveOperations.__new__(owner.LiveOperations)
    ops.case = contract.Case(RUN, 1000, 1000, "a" * 64, "b" * 64, "c" * 64)
    ops.previous_counts = (0, 0)
    monkeypatch.setattr(
        ops,
        "_wait",
        lambda _: {
            "run_id": RUN,
            "sequence": sequence,
            "auth_cli_completed": True,
            "first_network_refresh_planned": sequence == 1,
        },
    )
    monkeypatch.setattr(ops, "_verify", lambda _: after)
    if sequence == 1 and after[0] == 0:
        with pytest.raises(OwnerRejected, match="first_auth_network_evidence_unknown"):
            ops.auth_ready(sequence)
    else:
        ops.auth_ready(sequence)
    assert contract.LIMITS["first_auth_logical_refresh_planned"] == 1
    assert contract.LIMITS["refresh_http"] == "unknown"


def test_verification_timing_uses_explicit_end_clock_after_acceptance() -> None:
    value = worker.verification_timing(
        "2000-01-01T00:00:00+00:00",
        10.0,
        clock=lambda: 12.5,
        utc_clock=lambda: "2000-01-01T00:00:02.500000+00:00",
    )
    assert value["elapsed_seconds"] == 2.5
    assert value["verified_at_utc"] == "2000-01-01T00:00:02.500000+00:00"


@pytest.mark.parametrize(
    "field,value",
    [
        ("started_at_utc", "2000-01-01T00:00:00"),
        ("verified_at_utc", "2000-01-01T01:00:00+01:00"),
        ("verified_at_utc", "1999-12-31T23:59:59+00:00"),
        ("verified_monotonic", True),
        ("verified_monotonic", float("inf")),
        ("elapsed_seconds", -1),
        ("elapsed_seconds", 2),
    ],
)
def test_cell_verification_time_is_strict_and_ordered(
    field: str, value: object
) -> None:
    row = cell()
    row[field] = value
    with pytest.raises(contract.CaseRejected, match="live_verification_time_unknown"):
        contract.validate_cell(1, row, run_id=RUN)


class FakeSession:
    def __init__(self) -> None:
        self.calls = 0

    def pump(self, pending: bytes, timeout: float) -> Any:
        from paper_radar.llm.rpc_types import SessionEvent

        self.calls += 1
        if self.calls == 1:
            return SessionEvent(written=4)
        return SessionEvent(
            written=len(pending),
            stdout=b'{"type":"agent_start"}\n{"type":"response","id":"rpc-9","command":"prompt","success":true,"data":{"disposition":"started"}}\n',
        )


def test_partial_prompt_writes_count_once_and_preserve_ack_order() -> None:
    from paper_radar.llm.rpc_frames import command_frame

    frame = command_frame("rpc-9", "prompt", message="synthetic")
    meter = worker.SessionMeter(FakeSession(), frame, "low")
    meter.pump(frame, 1)
    meter.pump(frame[4:], 1)
    assert meter.prompt_completed == 1
    assert meter.agent_start_sequence == 1 and meter.prompt_ack_sequence == 2
    assert meter.counts["response"] == 1


def test_guarded_public_activation_rolls_back_event_on_concurrent_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar import pi_supply
    from paper_radar.pi_supply import repository
    from paper_radar.pi_supply.errors import SupplyError

    db = tmp_path / "synthetic.sqlite3"
    engine = create_engine(f"sqlite:///{db}")
    expected = {
        "activation_id": 1,
        "supply_id": "s",
        "install_id": "i",
        "snapshot_id": "old",
        "root_id": "r",
        "root_path": "/tmp/install",
    }
    with engine.begin() as con:
        con.exec_driver_sql(
            "CREATE TABLE pi_current_selection(singleton INTEGER PRIMARY KEY,"
            "activation_id INTEGER)"
        )
        con.exec_driver_sql(
            "CREATE TABLE pi_activation_events(activation_id INTEGER PRIMARY KEY,"
            "supply_id TEXT,install_id TEXT,snapshot_id TEXT,"
            "root_id TEXT,root_path TEXT)"
        )
        for aid, snap in ((1, "old"), (3, "external")):
            con.exec_driver_sql(
                "INSERT INTO pi_activation_events VALUES(?,?,?,?,?,?)",
                (aid, "s", "i", snap, "r", "/tmp/install"),
            )
        con.exec_driver_sql("INSERT INTO pi_current_selection VALUES(1,3)")

    def fake_public(*_args: object) -> None:
        with engine.connect() as con:
            con.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                con.exec_driver_sql(
                    "INSERT INTO pi_activation_events "
                    "VALUES(2,'s','i','new','r','/tmp/install')"
                )
                repository._select_activation(con, 2)
                con.commit()
            except BaseException:
                con.rollback()
                raise

    original = repository._select_activation
    monkeypatch.setattr(pi_supply, "activate_supply", fake_public)
    with pytest.raises(SupplyError, match="selection_changed"):
        worker.guarded_activate(db, "s", "new", expected)
    assert repository._select_activation is original
    with engine.connect() as con:
        assert (
            con.exec_driver_sql(
                "SELECT activation_id FROM pi_current_selection"
            ).scalar_one()
            == 3
        )
        assert (
            con.exec_driver_sql(
                "SELECT activation_id FROM pi_activation_events WHERE activation_id=2"
            ).first()
            is None
        )
    engine.dispose()


def test_sealed_original_selection_is_not_replaced_by_latest_same_install() -> None:
    ops = worker.ApplicationOperations.__new__(worker.ApplicationOperations)
    ops.supply = {
        "supply_id": "s",
        "install_id": "i",
        "root": "/tmp/install",
        "registration": {"activation_id": 1, "root_id": "r", "snapshot_id": "sealed"},
    }
    ops.original_snapshot = "sealed"
    ops.last_activation = None
    ops.last_snapshot = None
    assert (
        ops.expected_selection()["activation_id"] == 1
        and ops.expected_selection()["snapshot_id"] == "sealed"
    )


@pytest.mark.parametrize("wrong_field", ["install_id", "snapshot_id"])
def test_public_activation_cannot_commit_unapproved_new_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wrong_field: str
) -> None:
    from paper_radar import pi_supply
    from paper_radar.pi_supply import repository
    from paper_radar.pi_supply.errors import SupplyError

    db = tmp_path / "synthetic.sqlite3"
    engine = create_engine(f"sqlite:///{db}")
    expected = {
        "activation_id": 1,
        "supply_id": "s",
        "install_id": "approved-install",
        "snapshot_id": "old",
        "root_id": "r",
        "root_path": "/tmp/install",
    }
    with engine.begin() as con:
        con.exec_driver_sql(
            "CREATE TABLE pi_current_selection(singleton INTEGER PRIMARY KEY,"
            "activation_id INTEGER)"
        )
        con.exec_driver_sql(
            "CREATE TABLE pi_activation_events(activation_id INTEGER PRIMARY KEY,"
            "supply_id TEXT,install_id TEXT,snapshot_id TEXT,"
            "root_id TEXT,root_path TEXT)"
        )
        con.exec_driver_sql(
            "INSERT INTO pi_activation_events "
            "VALUES(1,'s','approved-install','old','r','/tmp/install')"
        )
        con.exec_driver_sql("INSERT INTO pi_current_selection VALUES(1,1)")

    def fake_public(*_args: object) -> None:
        install = (
            "another-install" if wrong_field == "install_id" else "approved-install"
        )
        snapshot = "another-snapshot" if wrong_field == "snapshot_id" else "new"
        with engine.connect() as con:
            con.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                con.exec_driver_sql(
                    "INSERT INTO pi_activation_events "
                    "VALUES(2,'s',?,?,'r','/tmp/install')",
                    (install, snapshot),
                )
                repository._select_activation(con, 2)
                con.commit()
            except BaseException:
                con.rollback()
                raise

    monkeypatch.setattr(pi_supply, "activate_supply", fake_public)
    with pytest.raises(SupplyError, match="selection_changed"):
        worker.guarded_activate(db, "s", "new", expected)
    with engine.connect() as con:
        assert (
            con.exec_driver_sql(
                "SELECT activation_id FROM pi_current_selection"
            ).scalar_one()
            == 1
        )
        assert (
            con.exec_driver_sql(
                "SELECT activation_id FROM pi_activation_events WHERE activation_id=2"
            ).first()
            is None
        )
    engine.dispose()


def test_journal_requires_current_run_and_strict_activation_number() -> None:
    row = {
        "run_id": RUN,
        "sequence": 0,
        "action": "original",
        "selection": {
            "activation_id": True,
            "supply_id": "a" * 64,
            "install_id": "b" * 32,
            "snapshot_id": "c" * 64,
            "root_id": "d" * 32,
            "root_path": "/tmp/install",
        },
    }
    with pytest.raises(contract.CaseRejected, match="live_selection_journal_unknown"):
        contract.validate_journal_entry(0, row, run_id=RUN)


def test_receipt_journal_omits_username_path_but_control_remains_recoverable() -> None:
    row: dict[str, Any] = {
        "run_id": RUN,
        "sequence": 0,
        "action": "original",
        "selection": {
            "activation_id": 1,
            "supply_id": "a" * 64,
            "install_id": "b" * 32,
            "snapshot_id": "c" * 64,
            "root_id": "d" * 32,
            "root_path": "/home/synthetic-owner/private-install",
        },
    }
    contract.validate_journal_entry(0, row, run_id=RUN)
    exported = cast(dict[str, Any], contract.project_journal_entry(0, row, run_id=RUN))
    assert row["selection"]["root_path"] == "/home/synthetic-owner/private-install"
    assert "synthetic-owner" not in json.dumps(exported)
    assert "root_path" not in exported["selection"]
    assert (
        exported["selection"]["root_path_identity"]
        == hashlib.sha256(b"/home/synthetic-owner/private-install").hexdigest()
    )
    with pytest.raises(contract.CaseRejected, match="live_selection_journal_unknown"):
        contract.validate_receipt_journal_entry(0, row, run_id=RUN)


class OwnerFake:
    def __init__(self, *, journal_error: bool = False) -> None:
        self.finished = False
        self.journal_error = journal_error

    def preflight(self) -> None:
        pass

    def reserve(self) -> None:
        pass

    def install(self) -> None:
        pass

    def start(self) -> None:
        pass

    def ready(self) -> dict[str, object]:
        return {}

    def exercise_rules(self) -> dict[str, object]:
        return {}

    def phase_gate(self, *args: object) -> None:
        pass

    def preflight_result(self) -> dict[str, object]:
        return {}

    def activate(self) -> None:
        pass

    def auth_ready(self, sequence: int) -> None:
        pass

    def cell_result(self, sequence: int) -> dict[str, object]:
        return cell(sequence)

    def collect(self) -> dict[str, object]:
        return {
            "selection_journal": [],
            "preflight": {},
            "cases": [cell(i) for i in range(1, 7)],
        }

    def wait_exit(self) -> None:
        pass

    def restore(self) -> dict[str, object]:
        return {
            "result": "host_policy_restored",
            "global_resolver_unchanged": True,
            "ledger_retained": True,
            "table_absent": True,
            "unit_absent": True,
        }

    def finish(self) -> dict[str, object]:
        self.finished = True
        return {"result": "successful_artifacts_removed", "ledger_retained": True}

    def write_ledger(self, value: object) -> None:
        pass

    def selection_journal(self) -> dict[str, object]:
        if self.journal_error:
            raise OSError("synthetic journal read failure")
        return {"entries": [], "completeness": "captured"}

    def database_restoration(self) -> dict[str, object]:
        return {
            "result": "original_selection_restored",
            "append_only_history_retained": True,
            "source": "trusted_worker_public_API_CAS",
        }


def test_last_journal_failure_prevents_finish_despite_host_restored() -> None:
    case = contract.Case(RUN, 1000, 1000, "a" * 64, "b" * 64, "c" * 64)
    ops = OwnerFake(journal_error=True)
    result = owner.run_owner(case, ops)
    assert result["result"] == "unknown" and not ops.finished
    assert result["database_evidence_error"] == "live_selection_restore_unknown"


@pytest.mark.parametrize("changed", ["tokens", "preflight"])
def test_final_worker_metadata_cannot_contradict_already_received_phases(
    changed: str,
) -> None:
    class Ops(OwnerFake):
        def collect(self) -> dict[str, Any]:
            value = super().collect()
            if changed == "tokens":
                cases = cast(list[dict[str, Any]], value["cases"])
                cases[0]["tokens"]["input"] += 1
                cases[0]["tokens"]["totalTokens"] += 1
                contract.validate_cell(1, cases[0], run_id=RUN)
            else:
                value["preflight"] = {"different": True}
            return value

    case = contract.Case(RUN, 1000, 1000, "a" * 64, "b" * 64, "c" * 64)
    ops = Ops()
    result = owner.run_owner(case, ops)
    assert result["result"] == "unknown" and not ops.finished
    assert result["failure_stage"] == "worker_result"


@pytest.mark.parametrize("sequence", range(1, 7))
def test_failed_cell_does_not_start_later_auth_and_still_restores(
    sequence: int,
) -> None:
    class Ops:
        def __init__(self) -> None:
            self.calls: list[int] = []

        restored = False

        def preflight(self) -> dict[str, object]:
            return {}

        def run_cell(self, seq: int) -> dict[str, object]:
            self.calls.append(seq)
            if seq == sequence:
                raise ValueError("synthetic failure")
            return cell(seq)

        def restore_selection(self) -> dict[str, object]:
            self.restored = True
            return {
                "result": "original_selection_restored",
                "append_only_history_retained": True,
            }

    ops = Ops()
    ops.calls = []
    result = worker.run_batch(ops, run_id=RUN)
    assert result["result"] == "unknown" and ops.restored
    assert ops.calls == list(range(1, sequence + 1))
