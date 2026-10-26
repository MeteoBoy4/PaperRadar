"""A10 同库恢复材料与稳定公共投影;旧库按真实 a704 schema 装载。"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from paper_radar.fixture_audit import FixtureAudit
from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
from paper_radar.papers import PaperFacts
from paper_radar.pi_supply import activation_history, list_supplies, show_supply
from paper_radar.screening_tasks import ScreeningTasks, SuccessCandidate, SuccessReceipt
from paper_radar.storage import database as database_module
from paper_radar.storage.database import upgrade_database
from tests.a7_registration_support import Archive, request_for
from tests.a7_retry_support import exhaust, retry_for
from tests.audit_matrix_support import MatrixSources
from tests.audit_sampling_support import SamplingClock
from tests.paper_recovery_reader import digest
from tests.pi_supply_support import inputs, prepare
from tests.restore_support import history_view
from tests.test_a7_complete_recovery import BOUNDARY
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def hash_value(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


def old_projection(
    database: Path, data_root: Path, ids: dict[str, Any]
) -> dict[str, str]:
    tasks = ScreeningTasks(database, data_root, clock=lambda: NOW)
    papers = PaperFacts(database, data_root)
    return {
        "config_and_artifacts": hash_value(history_view(database, data_root)),
        "pi": hash_value(
            [
                asdict(show_supply(database, item.supply_id))
                for item in list_supplies(database)
            ]
        ),
        "activation": hash_value(
            [asdict(value) for value in activation_history(database)]
        ),
        "papers": hash_value(
            [
                papers.trace(paper, verify_source_bytes=True).model_dump(mode="json")
                for paper in ids["papers"]
            ]
        ),
        "tasks": hash_value(
            [
                asdict(
                    tasks.query(
                        paper_id=paper, stage="boundary", snapshot_id=ids["snapshot"]
                    )
                )
                for paper in ids["papers"]
            ]
        ),
        "inputs": hash_value(
            [
                tasks.load_input(receipt).stage_input.payload_bytes.hex()
                for receipt in ids["receipts"]
            ]
        ),
        "success": hashlib.sha256(
            tasks.load_success(ids["success"]).raw_response
        ).hexdigest(),
    }


def copy_to_real_a704(
    source: Path, target: Path
) -> tuple[dict[str, list[str]], dict[str, list[tuple[Any, ...]]]]:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            config.attributes["connection"] = connection
            command.upgrade(config, "a704_screening_retry")
            connection.commit()
    finally:
        engine.dispose()
    with (
        closing(sqlite3.connect(source)) as seed,
        closing(sqlite3.connect(target)) as old,
    ):
        names = [
            row[0]
            for row in old.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name!='alembic_version' ORDER BY name"
            )
        ]
        columns = {
            name: [row[1] for row in old.execute(f"PRAGMA table_info({name})")]
            for name in names
        }
        expected = {
            name: seed.execute(
                f"SELECT {','.join(columns[name])} FROM {name} ORDER BY rowid"
            ).fetchall()
            for name in names
        }
        for name, rows in expected.items():
            old.execute(f"DELETE FROM {name}")
            if rows:
                old.executemany(
                    f"INSERT INTO {name} VALUES ({','.join('?' for _ in rows[0])})",
                    rows,
                )
        old.commit()
        assert old.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "a704_screening_retry",
        )
        assert not old.execute("PRAGMA foreign_key_check").fetchall()
    return columns, expected


def upgraded_legacy(root: Path) -> tuple[Path, Path, dict[str, Any]]:
    database, snapshot, request, download, runner = inputs(root)
    prepare(root, (database, snapshot, request, download, runner))
    data_root = root / "data"
    papers = PaperFacts(database, data_root)
    first = papers.submit(
        observation(
            doi="10.1234/legacy-success",
            fields=screening_fields(),
            payload=b"legacy successful paper",
        )
    )
    other = papers.submit(
        observation(
            doi="10.1234/legacy-failure",
            fields=screening_fields(),
            payload=b"legacy failed paper",
        )
    )
    assert first.paper_id and first.version_id and other.paper_id
    archive = Archive(
        root / "config/settings.yaml",
        database,
        data_root,
        snapshot,
        first.paper_id,
        first.version_id,
    )
    tasks = ScreeningTasks(database, data_root, clock=lambda: NOW)
    succeeded = tasks.register(request_for(archive))
    accepted = tasks.run_once(
        succeeded.receipt_id, lambda *_: SuccessCandidate(BOUNDARY)
    )
    assert isinstance(accepted, SuccessReceipt)
    failed = tasks.register(request_for(archive, paper_id=other.paper_id))
    exhaust(tasks, failed)
    successor = tasks.retry(retry_for(archive, failed, paper_id=other.paper_id))
    ids = {
        "papers": [first.paper_id, other.paper_id],
        "snapshot": snapshot,
        "receipts": [succeeded.receipt_id, failed.receipt_id, successor.receipt_id],
        "success": accepted.success_id,
    }
    before = old_projection(database, data_root, ids)
    target = root / "legacy-a704.sqlite3"
    columns, expected = copy_to_real_a704(database, target)
    assert expected["config_versions"] and expected["pi_supplies"]
    assert expected["paper_observations"] and expected["screening_successes"]
    assert expected["screening_failures"] and len(expected["screening_requests"]) == 3
    assert upgrade_database(target) == "a1001_fixture_audit"
    assert upgrade_database(target) == "a1001_fixture_audit"
    with closing(sqlite3.connect(target)) as upgraded:
        assert not upgraded.execute("PRAGMA foreign_key_check").fetchall()
        assert {
            name: upgraded.execute(
                f"SELECT {','.join(columns[name])} FROM {name} ORDER BY rowid"
            ).fetchall()
            for name in columns
        } == expected
    assert old_projection(target, data_root, ids) == before
    return target, data_root, ids


def audit_service(
    database: Path, data_root: Path, sources: MatrixSources
) -> FixtureAudit:
    clock = SamplingClock()
    executor = SourceHTTPExecutor(
        transport=httpx.MockTransport(sources),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    return FixtureAudit(database, data_root, source_executors={"http": executor})


def audit_projection(service: FixtureAudit) -> dict[str, Any]:
    records = service.list(history=True)
    audits = service.list_audits()
    result: dict[str, Any] = {
        "fixtures": digest([record.model_dump(mode="json") for record in records]),
        "declarations": {
            record.declaration_id: hashlib.sha256(
                service.read_declaration(record.declaration_id)
            ).hexdigest()
            for record in records
        },
        "audits": {},
        "interpretations": {},
        "text": {},
    }
    for audit in audits:
        plan = audit.plan.plan_id
        result["audits"][plan] = digest(
            service.replay_audit(plan).model_dump(mode="json")
        )
        result["interpretations"][plan] = digest(
            [
                value.model_dump(mode="json")
                for value in service.list_audit_interpretations(plan)
            ]
        )
        for member in audit.members:
            candidate = member.final_abstract_candidate_id
            if candidate:
                result["text"][candidate] = hashlib.sha256(
                    service.read_audit_text(plan, candidate).encode()
                ).hexdigest()
    return result
