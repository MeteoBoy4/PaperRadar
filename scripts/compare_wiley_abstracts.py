"""离线复算 Wiley v1/v2 字段差异;只在临时副本迁移,不追加审计事实。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import NoReturn
from unittest.mock import patch
from urllib.parse import quote

from paper_radar.feed_ingestion.parser import ParsedItem, parse_items
from paper_radar.fixture_audit import FixtureAudit, FixtureError
from paper_radar.fixture_audit.abstract_models import AbstractAuditView
from paper_radar.fixture_audit.abstract_parser import parse_material
from paper_radar.fixture_audit.abstract_rules import project
from paper_radar.fixture_audit.abstract_versions import (
    ABSTRACT_RULES_VERSION,
    WILEY_ABSTRACT_RULES_VERSION,
)
from paper_radar.fixture_audit.sampling_models import SamplingAuditView
from paper_radar.papers.models import AbstractValue
from paper_radar.storage.artifact_contract import ArtifactError
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import upgrade_database
from paper_radar.storage.errors import StorageError


def _arbitration(view: AbstractAuditView, member_id: str) -> dict[str, object]:
    member = next(value for value in view.members if value.member_id == member_id)
    candidate = next(
        (
            candidate
            for row in view.matrix
            for candidate in row.candidates
            if candidate.candidate_id == member.final_abstract_candidate_id
        ),
        None,
    )
    return dict(
        source=member.final_abstract_source,
        text_sha256=candidate.text_sha256 if candidate else None,
        codepoints=candidate.codepoints if candidate else None,
        signals=candidate.signals if candidate else None,
    )


def _production_fields(item: ParsedItem) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, candidate in item.fields.items():
        value = candidate.value
        text = value.text if isinstance(value, AbstractValue) else value
        if not isinstance(text, str):
            raise ValueError("unsupported_comparison_field")
        result[name] = dict(
            text_sha256=hashlib.sha256(text.encode()).hexdigest(),
            codepoints=len(text),
            locator=candidate.locator,
            is_truncated=value.is_truncated
            if isinstance(value, AbstractValue)
            else None,
            rule=value.rule if isinstance(value, AbstractValue) else None,
        )
    return result


def _report(
    service: FixtureAudit, store: ArtifactStore, plan_id: str
) -> dict[str, object]:
    before = service.replay_audit(plan_id)
    view = before.view
    if view.plan.abstract_rules_version != ABSTRACT_RULES_VERSION:
        raise ValueError("comparison_requires_v1_plan")
    rows = list(view.matrix_history)
    records: list[dict[str, object]] = []
    production: list[dict[str, object]] = []
    for state in view.sampling:
        if state.journal not in {"jgr", "qjrms"}:
            continue
        if state.feed is None:
            raise ValueError("comparison_requires_frozen_wiley_feeds")
        for member in state.members:
            row = next(
                row
                for row in rows
                if row.member_id == member.member_id and row.request.route == "feed"
            )
            execution = next(
                value
                for value in view.executions
                if value.execution_id == row.acquisition_id
            )
            settlement = execution.settlement
            if settlement is None or settlement.artifact_id is None:
                raise ValueError("comparison_requires_retained_material")
            event = next(
                value
                for value in state.history
                if value.event_id == member.selection_event_id
            )
            if event.candidate is None:
                raise ValueError("comparison_requires_member_locator")
            raw = store.read_artifact(settlement.artifact_id)["payload"]
            decoding = settlement.content_decoding or "utf-8"
            parsed, excluded, _, _ = parse_material(
                row.request,
                raw,
                decoding=decoding,
                acquisition_id=execution.execution_id,
                entry_locator=event.candidate.entry_locator,
                rules_version=WILEY_ABSTRACT_RULES_VERSION,
            )
            old_fields = {
                value.field: value.model_dump(mode="json") for value in row.candidates
            }
            new_fields = {
                value.field: value.model_dump(mode="json") for value in parsed
            }
            records.append(
                dict(
                    journal=state.journal,
                    position=member.position,
                    doi=member.doi,
                    old=old_fields,
                    new=new_fields,
                    added=sorted(new_fields.keys() - old_fields.keys()),
                    removed=sorted(old_fields.keys() - new_fields.keys()),
                    changed=sorted(
                        key
                        for key in old_fields.keys() & new_fields.keys()
                        if old_fields[key] != new_fields[key]
                    ),
                    member_id=member.member_id,
                )
            )
            # A transient pure projection only; never write these rows to SQLite.
            rows[rows.index(row)] = row.model_copy(
                update=dict(
                    candidates=parsed,
                    excluded_blocks=excluded,
                    abstract_rules_version=WILEY_ABSTRACT_RULES_VERSION,
                    reason="acquired"
                    if "abstract" in new_fields
                    else "record_without_abstract",
                )
            )
            if state.journal == "jgr":
                index = int(event.candidate.entry_locator.split("[")[1].rstrip("]")) - 1
                old_item = parse_items(raw, decoding, parser_version=1)[index]
                new_item = parse_items(raw, decoding, parser_version=2)[index]
                production.append(
                    dict(
                        position=member.position,
                        doi=member.doi,
                        entry_id_unchanged=old_item.candidate.entry_id
                        == new_item.candidate.entry_id,
                        doi_unchanged=old_item.candidate.doi == new_item.candidate.doi,
                        categories_unchanged=old_item.candidate.raw_categories
                        == new_item.candidate.raw_categories,
                        raw_range_unchanged=(old_item.start, old_item.end)
                        == (new_item.start, new_item.end),
                        old=_production_fields(old_item),
                        new=_production_fields(new_item),
                    )
                )
    sampling = SamplingAuditView.model_validate(
        view.model_dump(include=set(SamplingAuditView.model_fields))
    )
    transient = project(sampling, tuple(rows))
    for record in records:
        member_id = record["member_id"]
        assert isinstance(member_id, str)
        record["old_arbitration"] = _arbitration(view, member_id)
        record["new_arbitration"] = _arbitration(transient, member_id)
    if service.replay_audit(plan_id) != before:
        raise ValueError("comparison_changed_original_projection")
    return dict(
        kind="offline_transient_comparison_not_audit_interpretation",
        plan_id=plan_id,
        status=view.status,
        original_semantic_sha256=before.semantic_sha256,
        original_unchanged=True,
        network_attempts=0,
        records=records,
        production_jgr=production,
    )


def compare_wiley_abstracts(
    database: Path, data_root: Path, plan_id: str
) -> dict[str, object]:
    """读取原库一致副本;返回可与历史 JSON 比较的安全投影。"""

    def deny_network(*args: object, **kwargs: object) -> NoReturn:
        raise ValueError("comparison_network_forbidden")

    with ExitStack() as guard, TemporaryDirectory(prefix="wiley-comparison-") as folder:
        for target in (
            "socket.socket.connect",
            "socket.socket.connect_ex",
            "socket.create_connection",
            "socket.getaddrinfo",
        ):
            guard.enter_context(patch(target, side_effect=deny_network))
        copied = Path(folder) / "comparison.sqlite3"
        with (
            sqlite3.connect(
                f"file:{quote(str(database.resolve()))}?mode=ro", uri=True
            ) as original,
            sqlite3.connect(copied) as copy,
        ):
            original.backup(copy)
        upgrade_database(copied)
        return _report(
            FixtureAudit(copied, data_root), ArtifactStore(copied, data_root), plan_id
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="离线复算 Wiley 主摘要差异；只迁移临时副本，不联网。"
    )
    parser.add_argument("--database", type=Path, required=True, help="保留原审计数据库")
    parser.add_argument("--data-root", type=Path, required=True, help="保留来源制品根")
    parser.add_argument("--plan-id", required=True, help="冻结计划身份")
    parser.add_argument(
        "--check", type=Path, help="与已保存安全 JSON 逐字段比较；一致才返回0"
    )
    arguments = parser.parse_args(argv)
    try:
        report = compare_wiley_abstracts(
            arguments.database, arguments.data_root, arguments.plan_id
        )
        if arguments.check is not None:
            if json.loads(json.dumps(report)) != json.loads(
                arguments.check.read_bytes()
            ):
                print("差异不一致；请核对计划、材料和规则身份，不覆盖历史报告。")
                return 1
            print("离线差异与保存报告逐字段一致；原计划未改写，未联网。")
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
    except (
        OSError,
        ValueError,
        sqlite3.Error,
        FixtureError,
        StorageError,
        ArtifactError,
    ):
        print("无法复算；请核对保留数据库、制品根和计划身份，不修改原材料。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
