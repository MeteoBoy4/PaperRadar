"""显式实验 Read 的安全查询、恢复和获准内容视图。"""

import json
from datetime import UTC, datetime
from typing import Annotated, NoReturn

import typer

from paper_radar.backup.cli_support import BatchGroup
from paper_radar.experiment.cli import ExperimentCommand, RootOption


class ReadingGroup(BatchGroup):
    parameter_error = "Read 参数不正确;请查看 paper-radar reading --help。"
    unknown_command_error = (
        "Read 子命令不受支持;请使用 tasks/failures/reclaim/retry/analysis。"
    )


reading_app = typer.Typer(
    cls=ReadingGroup,
    no_args_is_help=True,
    help=(
        "显式 Read 查询与恢复;每项须 --root，自动配额 0;帮助不联网、不开库、不建目录。"
    ),
)


def reading_clock() -> datetime:
    """执行与恢复共享的可注入 UTC 时钟。"""
    return datetime.now(UTC)


def reading_error(error: BaseException) -> NoReturn:
    from paper_radar.body.models import BodyError
    from paper_radar.config import ConfigError
    from paper_radar.experiment import ExperimentError
    from paper_radar.experiment.egress import EgressError
    from paper_radar.experiment.layout import LayoutError
    from paper_radar.experiment.pdf import PdfError
    from paper_radar.experiment.reading import ReadingError
    from paper_radar.fulltext.models import FulltextError
    from paper_radar.pi_execution import ExecutionError
    from paper_radar.read_tasks import ReadTaskError
    from paper_radar.storage.artifact_contract import ArtifactError

    if isinstance(error, KeyboardInterrupt):
        typer.echo("interrupted：请查询任务，过期后显式 reclaim;次数不退还。", err=True)
        raise typer.Exit(130) from None
    if isinstance(error, (SystemExit, typer.Exit)):
        raise error
    reason = (
        str(error.reason)
        if isinstance(
            error,
            (
                BodyError,
                ConfigError,
                ExperimentError,
                EgressError,
                LayoutError,
                PdfError,
                ReadingError,
                ExecutionError,
                ReadTaskError,
                FulltextError,
                ArtifactError,
            ),
        )
        else "execution_failed"
    )
    if reason == "ambiguous_task":
        typer.echo(
            "ambiguous_task：当前失败父代不唯一；"
            "请用 reading failures --snapshot 查询，"
            "再提供 --task-id 明确当前 failed 父代。",
            err=True,
        )
        raise typer.Exit(2) from None
    typer.echo(
        f"{reason}：Read 操作停止;核对当前资格、外发授权与 doctor;"
        "用 reading tasks 查询，running 待租约后显式 reclaim，耗尽后 retry;"
        "ready 用 experiment read --task-id 继续。",
        err=True,
    )
    raise typer.Exit(4 if reason == "budget_exhausted" else 2) from None


@reading_app.command(
    "tasks",
    cls=ExperimentCommand,
    help="""只读全库 Read 任务与租约，不限当前样本。
参数：--root，可选 --paper。副作用：无，不建日志，不结算过期租约;自动配额 0。
输出去向：stdout 安全 JSON。常见失败：核对实验根;帮助不联网、不开库、不建目录。
退出码：成功 0;拒绝 2;中断 130。示例：paper-radar reading tasks --root /tmp/experiment
""",
)
def tasks(
    root: RootOption,
    paper: Annotated[str | None, typer.Option("--paper", help="可选论文。")] = None,
) -> None:
    from paper_radar.experiment import ExperimentRoot
    from paper_radar.experiment.reading import task_payload
    from paper_radar.read_tasks import ReadTasks

    try:
        selected = ExperimentRoot(root)
        selected.require()
        service = ReadTasks(selected.database, selected.data_root)
        result = [
            task_payload(t)
            for p in ((paper,) if paper else service.papers())
            for t in service.history(p)
        ]
    except BaseException as error:
        reading_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False))


@reading_app.command(
    "failures",
    cls=ExperimentCommand,
    help="""只读全库当前输入的最新 failed Read 代际。
参数：--root、--snapshot。副作用：无，不结算过期租约，不建日志;自动配额 0。
输出去向：stdout 安全 JSON;不局限当前选样。常见失败：配置/正文无法映射时不伪造 failed。
帮助不联网、不开库、不建目录。退出码：成功 0;拒绝 2;中断 130。
示例：paper-radar reading failures --root /tmp/experiment --snapshot SNAP
""",
)
def failures(
    root: RootOption,
    snapshot: Annotated[
        str, typer.Option("--snapshot", help="当前输入的明确配置参照。")
    ],
) -> None:
    from paper_radar.config import resolve_config_snapshot_reference
    from paper_radar.experiment import ExperimentRoot
    from paper_radar.experiment.reading import task_payload
    from paper_radar.read_tasks import ReadTasks

    try:
        selected = ExperimentRoot(root)
        selected.require()
        identifier = resolve_config_snapshot_reference(selected.database, snapshot)
        result = [
            task_payload(t)
            for t in ReadTasks(selected.database, selected.data_root).failures(
                snapshot_id=identifier
            )
        ]
    except BaseException as error:
        reading_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False))


@reading_app.command(
    "reclaim",
    cls=ExperimentCommand,
    help="""显式结算指定 Read 的过期租约为 outcome_unknown。
参数：TASK、--root。副作用：只追加过期结算，不执行模型、不退次数;自动配额 0。
写所选根 logs/。
输出去向：stdout 安全任务。常见失败：未过期保持 running;之后显式 --task-id 或 retry。
帮助不联网、不开库、不建目录。退出码：成功 0;拒绝 2;中断 130。
示例：paper-radar reading reclaim TASK --root /tmp/experiment
""",
)
def reclaim(task: str, root: RootOption) -> None:
    from paper_radar.experiment import ExperimentRoot
    from paper_radar.experiment.reading import READING_ERRORS, task_payload
    from paper_radar.read_tasks import ReadTasks
    from paper_radar.runtime_logging import FileSink, RuntimeLog

    try:
        selected = ExperimentRoot(root)
        selected.require()
        sink = FileSink(selected.root)
        with RuntimeLog(sink).execution("experiment", controlled=READING_ERRORS):
            result = task_payload(
                ReadTasks(
                    selected.database,
                    selected.data_root,
                    sink=sink,
                    clock=reading_clock,
                ).reclaim(task)
            )
    except BaseException as error:
        reading_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False))


@reading_app.command(
    "retry",
    cls=ExperimentCommand,
    help="""为已结算两次失败的 Read 追加唯一后继，不调用模型。
参数：PAPER、--root、--snapshot、--request-id、--reason、--actor。
副作用：追加代际/登记和所选根 logs/。
自动配额 0。
输出去向：stdout 原登记回执;精确重放不继续执行。常见失败：running 先显式 reclaim;
从当前 failed 唯一定位父代；歧义拒绝，可用 --task-id 明确。
明确任务仍须属于该论文/快照的当前输入、latest、failed，不绕当前资格。
非当前正文/选样、成功/running/ready/过期未结算不能 retry。
过期须先显式 reclaim；精确旧请求先回原回执，不受后继推进或选择变化影响。
后继 ready 用 experiment read --task-id 继续。
帮助不联网、不开库、不建目录。退出码：成功 0;拒绝 2;中断 130。
示例：paper-radar reading retry PAPER --root /tmp/experiment --snapshot SNAP
--request-id retry-1
--reason 修正执行环境 --actor owner
""",
)
def retry(
    paper: str,
    snapshot: Annotated[
        str, typer.Option("--snapshot", help="明确当前 Read 输入配置。")
    ],
    root: RootOption,
    request_id: Annotated[str, typer.Option("--request-id", help="唯一幂等请求。")],
    reason: Annotated[
        str, typer.Option("--reason", help="所有者重试原因，仅存业务库。")
    ],
    actor: Annotated[
        str, typer.Option("--actor", help="决定重试者，本地说明不是认证。")
    ],
    task_id: Annotated[
        str | None,
        typer.Option("--task-id", help="可选明确父代，仍须属于本论文当前failed。"),
    ] = None,
) -> None:
    from sqlalchemy import Connection

    from paper_radar.body import BodyService
    from paper_radar.config import resolve_config_snapshot_reference
    from paper_radar.experiment import ExperimentRoot
    from paper_radar.experiment.pdf import PdfSamples
    from paper_radar.experiment.reading import (
        READING_ERRORS,
        ReadingError,
        registration_receipt,
    )
    from paper_radar.read_tasks import ReadTasks
    from paper_radar.read_tasks.preconditions import require_facts
    from paper_radar.runtime_logging import FileSink, RuntimeLog

    try:
        selected = ExperimentRoot(root)
        selected.require()
        sink = FileSink(selected.root)
        service = ReadTasks(
            selected.database, selected.data_root, sink=sink, clock=reading_clock
        )
        snapshot_id = resolve_config_snapshot_reference(selected.database, snapshot)
        replayed = service.replay_retry_paper(
            paper,
            snapshot_id=snapshot_id,
            request_id=request_id,
            reason=reason,
            actor=actor,
            task_id=task_id,
        )
        sample = None
        identity = None
        if replayed is None:
            sample = PdfSamples(
                selected.database, selected.data_root
            ).require_current_sample(paper)
            identity = (
                BodyService(selected.database, selected.data_root)
                .current_body(paper)
                .identity
            )
            if identity is None:
                raise ReadingError("body_identity_mismatch")

        def check(connection: Connection) -> None:
            if sample is None or identity is None:
                raise ReadingError("request_conflict")
            PdfSamples(
                selected.database, selected.data_root
            ).require_current_sample_in_connection(connection, sample)
            require_facts(
                BodyService(selected.database, selected.data_root),
                connection,
                paper,
                identity,
            )

        with RuntimeLog(sink).execution("experiment", controlled=READING_ERRORS):
            service.retry_paper(
                paper,
                snapshot_id=snapshot_id,
                task_id=task_id,
                request_id=request_id,
                reason=reason,
                actor=actor,
                retry_guard=check,
            )
        result = registration_receipt(service, request_id)
    except BaseException as error:
        reading_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False))


@reading_app.command(
    "analysis",
    cls=ExperimentCommand,
    help="""获准的实验分析私有查询，含结构结果和逐字 evidence。
参数：ANALYSIS、--root，可选 --snapshot。副作用：无，不建日志;自动配额 0。
输出去向：stdout 私有内容，禁止复制到日志/公开诊断。
显著显示受限内容未核对、丢弃标记与各类计数。
常见失败：可见性拒绝须退出;普通消费始终拒绝实验分析。帮助不联网、不开库、不建目录。
退出码：成功 0;拒绝 2;中断 130。示例：paper-radar reading analysis ANALYSIS
--root /tmp/experiment
""",
)
def analysis(
    analysis: str,
    root: RootOption,
    snapshot: Annotated[
        str | None, typer.Option("--snapshot", help="明确配置参照。")
    ] = None,
) -> None:
    from paper_radar.config import resolve_config_snapshot_reference
    from paper_radar.experiment import ExperimentRoot
    from paper_radar.experiment.reading import analysis_payload

    try:
        selected = ExperimentRoot(root)
        selected.require()
        identifier = (
            resolve_config_snapshot_reference(selected.database, snapshot)
            if snapshot
            else None
        )
        result = analysis_payload(
            selected.database, selected.data_root, analysis, snapshot_id=identifier
        )
    except BaseException as error:
        reading_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False))
