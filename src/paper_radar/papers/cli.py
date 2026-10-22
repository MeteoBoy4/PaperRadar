"""论文事实只读命令;不提供生产写入口。"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from paper_radar.papers.models import PaperTrace, PaperView

import typer

from paper_radar.backup.cli_support import BatchCommand, BatchGroup
from paper_radar.papers.errors import PaperError
from paper_radar.storage.errors import StorageError

HELP = """\
当前用途：只读查看论文当前事实、四类来源、人工修正、版本关系及 Feed 历史。
不写入、不调用模型。
仅覆盖论文事实；尚未计算完整任务资格。

参数与选项：show/trace 接受 PAPER_ID、必填 --database；可选 --data-root、
--json、--show-abstract。trace 可用 --verify-source-bytes 只读核验来源字节，
使用时必须同时提供 --data-root。

副作用：只读既有数据库；字节核验才访问既有制品根。帮助不连接数据库、不创建目录、不联网。

自动配额：消耗 0 次模型配额。

输出去向：事实写入标准输出；默认隐藏所有摘要，
显式 --show-abstract 才展开；不转储原响应。

常见失败：请先显式 db upgrade 迁移既有库；缺失 ID 请核对，损坏请检查备份。
受控失败退出 1，参数错误退出 2。

示例：paper-radar paper show PAPER_ID --database data/paper-radar.sqlite3
示例：paper-radar paper trace PAPER_ID --database data/paper-radar.sqlite3 --json
"""


class PaperGroup(BatchGroup):
    parameter_error = "论文查询参数不正确；请运行 paper-radar paper --help"
    unknown_command_error = "论文查询子命令不受支持；请使用 show 或 trace"


class PaperCommand(BatchCommand):
    parameter_error = "论文查询参数不正确；请查看该命令 --help"


paper_app = typer.Typer(
    cls=PaperGroup, help=HELP, no_args_is_help=True, rich_markup_mode=None
)
Database = Annotated[Path, typer.Option("--database", help="既有 SQLite 数据库路径")]
DataRoot = Annotated[
    Path | None, typer.Option("--data-root", help="既有制品根（字节核验必填）")
]


def _redact_abstracts(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _redact_abstracts(item) if key != "abstract" else _hide_abstract(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_abstracts(item) for item in value]
    return value


def _hide_abstract(value: object) -> object:
    if isinstance(value, dict):
        field = dict(value)
        abstract = field.get("value")
        if isinstance(abstract, dict):
            field["value"] = {
                key: item for key, item in abstract.items() if key != "text"
            }
        return field
    return value


def _text_result(
    result: "PaperView | PaperTrace", *, trace: bool, show_abstract: bool
) -> None:
    from paper_radar.papers.models import AbstractValue, PaperTrace

    view = result.current if isinstance(result, PaperTrace) else result
    typer.echo("论文来源历史（只读）" if trace else "论文当前事实（只读）")
    typer.echo(view.scope)
    title = view.fields.get("title")
    typer.echo(f"题名：{title.value if title else '（缺失）'}")
    typer.echo(
        f"论文：{view.paper_id}；版本：{view.version_id}；修订：{view.revision_no}"
    )
    typer.echo(f"DOI：{view.doi or '（尚未登记）'}；类别：{view.version_kind}")
    if not trace and view.selection:
        selection = view.selection
        typer.echo(
            f"当前版本选择：{selection.selection_id}/{selection.version_id}；"
            f"{selection.reason}；{selection.selected_at}"
        )
    typer.echo(
        "字段来源："
        + "、".join(f"{name}={fact.source_kind}" for name, fact in view.fields.items())
    )
    abstract = view.fields.get("abstract")
    if abstract and isinstance(abstract.value, AbstractValue):
        marker = {None: "未知", True: "疑似截断", False: "完整"}[
            abstract.value.is_truncated
        ]
        typer.echo(f"摘要：存在；完整性：{marker}")
    else:
        typer.echo("摘要：（缺失）")
    for name, fact in view.fields.items():
        if name not in {"title", "abstract"}:
            typer.echo(f"{name}：{fact.value}")
    typer.echo(
        "获选依据："
        + " | ".join(
            f"{name}={fact.source_kind}/{fact.provider}；取得 {fact.observed_at}；"
            f"parser_version={fact.parser_version}；locator={fact.locator}"
            for name, fact in view.fields.items()
        )
        + "；按来源优先级及来源内确定排序"
    )
    if isinstance(result, PaperTrace):
        typer.echo(
            f"历史：{len(result.revisions)} 次修订、"
            f"{len(result.observations)} 份解释、"
            f"{len(result.discoveries)} 条 Feed 发现；版本选择："
            + " | ".join(
                f"{event.selection_id}/{event.version_id}；{event.reason}；{event.selected_at}"
                for event in result.selections
            )
        )
        typer.echo(result.manual_correction_scope)
        if result.selection_conflicts:
            typer.echo(
                "同级版本歧义（保持既有选择）：" + "、".join(result.selection_conflicts)
            )
        for relation in result.relations:
            label = {
                "endpoint_missing": "版本关系（端点尚未出现）",
                "requires_merge": "未生效版本关系（等待合并）",
                "effective": "版本关系（已生效）",
            }[relation.state]
            typer.echo(
                f"{label}：{relation.preprint_doi} → {relation.journal_doi}；"
                f"预印本 Paper={relation.preprint_paper_id or '尚未出现'}；"
                f"正式版 Paper={relation.journal_paper_id or '尚未出现'}；"
                f"来源={relation.source_kind}/{relation.provider}；locator={relation.locator}"
            )
        for revision in result.revisions:
            typer.echo(
                f"修订 {revision.revision_no}：版本 {revision.version_id}；"
                + "、".join(
                    f"{name}={fact.candidate_id}"
                    for name, fact in revision.fields.items()
                )
            )
        typer.echo(
            "候选获选说明："
            + " | ".join(
                f"{decision.field_name}/{decision.candidate_id}；"
                f"取得 {decision.acquisition_id}；{decision.reason}"
                for decision in result.decisions
            )
        )
        for source in result.observations:
            typer.echo(
                f"来源 {source.source_kind}：{source.provider}；{source.query_key}；"
                f"parser_version={source.parser_version}；"
                + " | ".join(
                    f"候选 {name}：{fact.value}；locator={fact.locator}"
                    for name, fact in source.fields.items()
                    if name != "abstract"
                )
            )
        for event in result.corrections:
            typer.echo(
                f"人工事件 {event.event_no}：{event.actor}；{event.reason}；"
                f"请求 {event.request_id}；版本 {event.version_id}"
            )
        for discovery in result.discoveries:
            typer.echo(
                f"Feed {discovery.feed_id}；entry_id={discovery.entry_id}；"
                f"item_fingerprint={discovery.item_fingerprint}"
            )
            parsers = [parsed.parser_version for parsed in discovery.interpretations]
            typer.echo(
                f"首次：{discovery.first_seen}；最近：{discovery.last_seen}；解释："
                + "、".join(f"parser_version={version}" for version in parsers)
            )
    if show_abstract:
        sources = result.observations if isinstance(result, PaperTrace) else (view,)
        for abstract_source in sources:
            abstract = abstract_source.fields.get("abstract")
            if abstract and isinstance(abstract.value, AbstractValue):
                typer.echo(f"摘要（{abstract.source_kind}）：{abstract.value.text}")


def _query(
    paper_id: str,
    database: Path,
    data_root: Path | None,
    trace: bool,
    as_json: bool,
    show_abstract: bool,
    verify_source_bytes: bool = False,
) -> None:
    from paper_radar.papers.service import PaperFacts

    try:
        service = PaperFacts(database, data_root)
        result = (
            service.trace(paper_id, verify_source_bytes=verify_source_bytes)
            if trace
            else service.show(paper_id)
        )
        payload: object = result.model_dump(mode="json")
        if not show_abstract:
            payload = _redact_abstracts(payload)
        if as_json:
            typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _text_result(result, trace=trace, show_abstract=show_abstract)
    except (PaperError, StorageError) as error:
        typer.echo(f"论文查询失败 [{error.reason.value}]：{error}", err=True)
        raise typer.Exit(1) from None


@paper_app.command("show", cls=PaperCommand, help=HELP)
def show_command(
    paper_id: Annotated[str, typer.Argument(help="论文 UUID")],
    database: Database,
    data_root: DataRoot = None,
    as_json: Annotated[bool, typer.Option("--json", help="受控 JSON 输出")] = False,
    show_abstract: Annotated[
        bool, typer.Option("--show-abstract", help="显式展开摘要")
    ] = False,
) -> None:
    _query(paper_id, database, data_root, False, as_json, show_abstract)


@paper_app.command("trace", cls=PaperCommand, help=HELP)
def trace_command(
    paper_id: Annotated[str, typer.Argument(help="论文 UUID")],
    database: Database,
    data_root: DataRoot = None,
    as_json: Annotated[bool, typer.Option("--json", help="受控 JSON 输出")] = False,
    show_abstract: Annotated[
        bool, typer.Option("--show-abstract", help="显式展开包括未获选候选的摘要")
    ] = False,
    verify_source_bytes: Annotated[
        bool, typer.Option("--verify-source-bytes", help="只读核验来源字节，不转储正文")
    ] = False,
) -> None:
    if verify_source_bytes and data_root is None:
        typer.echo(
            "论文查询参数不正确：--verify-source-bytes 需要 --data-root", err=True
        )
        raise typer.Exit(2)
    _query(
        paper_id, database, data_root, True, as_json, show_abstract, verify_source_bytes
    )
