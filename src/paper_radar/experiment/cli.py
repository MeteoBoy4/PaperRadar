"""B 显式实验命令;帮助与导入不访问业务根。"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer
from typer.core import TyperCommand


class ExperimentCommand(TyperCommand):
    """参数诊断不回显未知参数、自由文本或私有根路径。"""

    def parse_args(self, ctx: Any, args: list[str]) -> list[str]:
        try:
            return super().parse_args(ctx, args)
        except (typer.Exit, typer.Abort):
            raise
        except Exception:
            typer.echo(
                "invalid_arguments：参数不完整或不受支持；"
                "请查看该命令 --help 并显式提供必填选项。",
                err=True,
            )
            raise typer.Exit(2) from None


def report_component_error(error: Exception) -> None:
    """只输出权威封闭原因;字段位置必须在本入口的白名单内。"""
    from paper_radar.body.models import BodyError
    from paper_radar.feed_pipeline import PipelineError
    from paper_radar.fixture_audit.errors import FixtureError
    from paper_radar.papers.errors import PaperError
    from paper_radar.screening_tasks import TaskError
    from paper_radar.storage.artifact_contract import ArtifactError
    from paper_radar.storage.errors import StorageError

    reason = "execution_failed"
    path = "component"
    if isinstance(
        error,
        (BodyError, FixtureError, PaperError, TaskError, ArtifactError, StorageError),
    ):
        reason = str(error.reason.value)
    elif isinstance(error, PipelineError):
        reason = error.reason
    if isinstance(error, (FixtureError, PaperError)) and error.path in {
        "request_id",
        "contact_email",
        "parser_version",
        "abstract_rules_version",
        "feed_check",
        "feed_item_commit",
        "metadata",
        "database",
    }:
        path = error.path
    typer.echo(
        f"{reason}（{path}）：操作未完成；请检查实验根用途、联系邮箱、请求标识与数据库版本，回查原检查后显式重跑；冲突不可覆盖。",
        err=True,
    )


EXPERIMENT_HELP = """在显式实验根内执行 B 工作流。

参数：每个命令必须提供 --root，不从 cwd 或父目录寻找根。
init 显式迁移数据库并登记不可改写的 experiment 用途。
副作用：执行命令只写所选根；帮助不联网、不开库、不建目录。
自动配额：0；不扫描自动任务队列。
输出去向：安全 JSON 写 stdout；受控错误写 stderr，私有视图保存在根内。
常见失败：参数错误、用途不符、布局或执行失败退出 2；中断退出 130；成功退出 0。
下一步：先运行 init，再按子命令帮助提供显式参数。
示例：paper-radar experiment init --root /tmp/my-experiment
"""

INIT_HELP = """初始化独立实验根，显式迁移并一次性登记 experiment 用途。

参数：必填 --root。固定数据库 paper-radar.sqlite3，制品 data/blobs/sha256，配置
config/settings.yaml，日志 logs/，私有视图 views/；不猜测根。
副作用：创建目录与数据库；同根重放保持根身份；不改登记 production/unknown 库。
帮助不联网、不开库、不建目录；自动配额 0，不调用模型。
输出去向：stdout 安全 JSON，错误写 stderr，不输出私有绝对路径。
退出码：成功 0；参数错误或受控拒绝 2；中断 130。
常见失败：根用途不符或布局不安全；请使用独立空根，不迁移既有未知用途库。
旧顶层 blobs/ 或 tmp/ 非空以 legacy_layout 拒绝；请保留原库材料，另行安排显式迁移。
示例：paper-radar experiment init --root /tmp/my-experiment
"""

FEED_HELP = """在已登记的实验根内经生产路径取得 JGR Feed 与最低元数据。

参数：必填 --root、--request-id 和 --contact-email；邮箱只作 HTTP 联系标识。
显式采用 jgr-feed-parser-v2 与 audit-abstract-v2；同 request 重放沿用原检查。
副作用：访问来源 HTTP，追加检查、发现、元数据与 v1 语言依据；日志写所选根 logs/。
自动配额 0；不调用模型，不登记 Screening/Read 任务。
输出去向：安全 JSON 写 stdout，仅含身份、HTTP/条目状态、缺项及语言依据，不展开摘要。
304 返回 not_modified 并关联原 source_check_id 的成员；失败不解释为“无新论文”。
帮助不联网、不开库、不建目录。
退出码：完整非截断元数据或 304 可重放依据成功 0；参数错误、用途不符、
HTTP/条目失败、缺项或执行失败 2；中断 130。
常见失败：非实验根先 init；来源受阻或元数据缺项请回查安全原因，
未完成请求用同一 request 重跑。
示例：paper-radar experiment feed-fetch --root /tmp/my-experiment
--request-id round-1 --contact-email contact@example.org
"""

experiment_app = typer.Typer(
    help=EXPERIMENT_HELP, no_args_is_help=True, rich_markup_mode="markdown"
)

RootOption = Annotated[Path, typer.Option("--root", help="必填的显式实验根。")]


@experiment_app.command(
    "extract",
    cls=ExperimentCommand,
    help="""对当前冻结样本显式执行一次 Docling 提取。

参数：必填 PAPER、--root、--snapshot、--model-root、--timeout-seconds、--threads。
模型根的 deployment.json 与全部所选文件必须核验；不下载模型。
副作用：根锁前核验当前进程 cgroup memory.max ≤8 GiB、swap=0，
主机 MemAvailable 仅披露；临时模型快照要求完整所选文件大小的磁盘空间。
显式设置 32 GiB RLIMIT_AS，它不是物理内存上限；超时与线程使用显式参数。
只领取一次既有 Body attempt；质量失败永久阻断，其他失败遵守两次预算。
自动配额 0；不调用 Read，不截断、不自动重试或换样。
输出去向：stdout 安全 JSON，worker ru_maxrss 与 cgroup 历史组峰值分列；
日志写所选根 logs/，正文制品留 data/；峰值不可读明确为 unknown。
帮助不联网、不开库、不建目录。
退出码：成功或已成功重放 0；参数、资源、模型预检、样本变化或提取失败 2；中断 130。
常见失败：请核对 cgroup/部署/冻结样本；失败后回查 paper trace，
由所有者选择显式重试或换样并说明理由，不能绕过质量或预算。
示例：paper-radar experiment extract PAPER --root /tmp/my-experiment
--snapshot SNAP --model-root /tmp/models --timeout-seconds 300 --threads 4
""",
)
def extract(
    paper: Annotated[str, typer.Argument(help="当前已冻结样本的论文身份。")],
    root: RootOption,
    snapshot: Annotated[str, typer.Option("--snapshot", help="显式配置快照。")],
    model_root: Annotated[Path, typer.Option("--model-root", help="已部署模型根。")],
    timeout_seconds: Annotated[
        float, typer.Option("--timeout-seconds", help="显式超时秒数。")
    ],
    threads: Annotated[int, typer.Option("--threads", help="显式 CPU 线程数，1–32。")],
) -> None:
    from paper_radar.docling_executor import DoclingPreflightError
    from paper_radar.experiment.extraction import ExtractionError, extract_once
    from paper_radar.experiment.pdf import PdfError
    from paper_radar.experiment.root import ExperimentError, ExperimentRoot

    try:
        result = extract_once(
            ExperimentRoot(root),
            paper_id=paper,
            snapshot=snapshot,
            model_root=model_root,
            timeout_seconds=timeout_seconds,
            threads=threads,
        )
    except (ExtractionError, PdfError, ExperimentError, DoclingPreflightError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo(
            "interrupted：提取中断；先回查 trace，再显式重跑；不退款。", err=True
        )
        raise typer.Exit(130) from None
    except Exception as error:
        report_component_error(error)
        raise typer.Exit(2) from None
    typer.echo(json.dumps(result, ensure_ascii=False))
    if not result["succeeded"]:
        typer.echo(
            "extraction_failed：实验停止；回查原因，由所有者选择重试或换样，不能绕过预算或永久失败。",
            err=True,
        )
        raise typer.Exit(2)


@experiment_app.command(
    "accept",
    cls=ExperimentCommand,
    help="""依所有者预先选样授权，由 Agent 显式代记 accepted。

参数：必填 PAPER、--root、--selection-id、--snapshot、--request-id。
前置：同论文同版本有效选样、当前 pi_rpc boundary（非 out_of_scope）与 value 成功。
value 实验预测无需为 accepted；不声称所有者看过模型输出。
副作用：同一事务追加 Body 决定与授权关联，日志写所选根 logs/；重放不追加。
不调用模型、不领取任务，自动配额 0；帮助不联网、不开库、不建目录。
输出去向：stdout 安全 JSON 引用与授权者/代执行者；错误写 stderr，不输出理由或模型正文。
退出码：成功或精确重放 0；参数、授权/版本变化、缺成功、test 来源、
out_of_scope、visibility 拒绝、请求冲突或执行失败 2；中断 130。
常见失败：请回查 selection、paper trace --snapshot 与两阶段成功，
需要时由所有者重新选样或显式 retry；请求冲突不能覆盖。
示例：paper-radar experiment accept PAPER --root /tmp/my-experiment
--selection-id SELECTION --snapshot SNAPSHOT --request-id accept-1
""",
)
def accept(
    paper: Annotated[str, typer.Argument(help="选样冻结的论文身份。")],
    root: RootOption,
    selection_id: Annotated[
        str, typer.Option("--selection-id", help="有效的预先选样授权。")
    ],
    snapshot: Annotated[str, typer.Option("--snapshot", help="两阶段适用性所用快照。")],
    request_id: Annotated[
        str, typer.Option("--request-id", help="幂等请求标识；异内容不可覆盖。")
    ],
) -> None:
    from paper_radar.body.models import BodyError
    from paper_radar.experiment.acceptance import AcceptanceError, Acceptances, receipt
    from paper_radar.experiment.root import ExperimentError, ExperimentRoot
    from paper_radar.experiment.selections import SelectionError
    from paper_radar.runtime_logging import FileSink, RuntimeLog
    from paper_radar.screening_tasks import TaskError

    try:
        selected = ExperimentRoot(root)
        selected.require()
        log = RuntimeLog(FileSink(selected.root))
        with log.execution(
            "experiment",
            controlled=(
                AcceptanceError,
                ExperimentError,
                SelectionError,
                BodyError,
                TaskError,
            ),
            paper_id=paper,
        ):
            record, replayed = Acceptances(
                selected.database, selected.data_root
            ).accept(
                selected,
                paper_id=paper,
                selection_id=selection_id,
                snapshot=snapshot,
                request_id=request_id,
            )
    except (AcceptanceError, ExperimentError, SelectionError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo(
            "interrupted：登记中断；请先回查 trace，再以同 request 显式重跑。", err=True
        )
        raise typer.Exit(130) from None
    except Exception as error:
        report_component_error(error)
        raise typer.Exit(2) from None
    typer.echo(json.dumps(receipt(record, replayed=replayed), ensure_ascii=False))


@experiment_app.command(
    "probe-models",
    cls=ExperimentCommand,
    help="""显式执行无 prompt 的模型映射探测，screening 与 reading 独立核对。

参数：必填 --root、--snapshot、--credentials-dir、--material-root、--install-root；
--slot 可选 screening 或 reading，默认两槽。只核实精确模型与推理档位可设置。
副作用：调用认证 helper，可能刷新并写回专用凭据目录；不是只读预检。
创建独占 /tmp 根，完成后回收进程组并清理；日志写所选根 logs/。
不发送 prompt、Profile、摘要或正文，不登记任务、attempt 或预算；自动配额 0。
输出去向：stdout 安全 JSON 槽和原因；错误写 stderr；不保存准入证据。
帮助不联网、不开库、不建目录。
常见失败：无授权、缺严格证据或豁免、隔离不可用、模型/档位不可用、超时、清理失败；
请核对 egress、owner-waiver、固定供给和精确配置；升级须按 §7.8 交所有者裁决。
退出码：成功 0；参数、受控拒绝或失败 2；中断 130。
示例：paper-radar experiment probe-models --root /tmp/my-experiment --snapshot SNAP
--credentials-dir /tmp/auth --material-root /tmp/materials --install-root /tmp/install
""",
)
def probe_models(
    root: RootOption,
    snapshot: Annotated[str, typer.Option("--snapshot", help="显式历史快照。")],
    credentials_dir: Annotated[
        Path, typer.Option("--credentials-dir", help="独立认证目录。")
    ],
    material_root: Annotated[
        Path, typer.Option("--material-root", help="显式材料根。")
    ],
    install_root: Annotated[
        Path, typer.Option("--install-root", help="当前固定安装根。")
    ],
    slot: Annotated[
        str | None, typer.Option("--slot", help="screening 或 reading；默认两槽。")
    ] = None,
) -> None:
    from paper_radar.experiment import ExperimentError, ExperimentRoot
    from paper_radar.experiment.egress import EgressError
    from paper_radar.experiment.model_mapping import probe_models as execute
    from paper_radar.pi_execution.errors import ExecutionError
    from paper_radar.runtime_logging import FileSink, RuntimeLog

    if slot not in {None, "screening", "reading"}:
        typer.echo(
            "invalid_arguments：--slot 须为 screening 或 reading；查看 --help。",
            err=True,
        )
        raise typer.Exit(2)
    try:
        selected = ExperimentRoot(root)
        selected.require()
        log = RuntimeLog(FileSink(selected.root))
        with log.execution(
            "experiment", controlled=(ExperimentError, EgressError, ExecutionError)
        ):
            result = execute(
                selected,
                snapshot=snapshot,
                credentials_dir=credentials_dir,
                material_root=material_root,
                install_root=install_root,
                slot=slot,
            )
    except (ExperimentError, EgressError, ExecutionError) as error:
        typer.echo(
            f"{error.reason}：探测停止；核对外发授权、豁免/严格证据、"
            "固定供给及隔离后显式重跑；模型升级交所有者按 §7.8 裁决。",
            err=True,
        )
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo("interrupted：探测中断；回查隔离与清理后显式重跑。", err=True)
        raise typer.Exit(130) from None
    except Exception as error:
        report_component_error(error)
        raise typer.Exit(2) from None
    typer.echo(json.dumps(result, ensure_ascii=False))
    if any(item["state"] != "mapping_settable" for item in result):
        typer.echo(
            "mapping_probe_failed：仅回读映射，未取得生成或参数有效性证明；"
            "请核对精确模型、档位及清理，升级按 §7.8 交所有者裁决。",
            err=True,
        )
        raise typer.Exit(2)


@experiment_app.command(
    "candidates",
    cls=ExperimentCommand,
    help="""生成或重建一次 Feed 检查的私有只读候选清单。

参数：必填 --root；--check-id 生成新事实视图，或 --view-id 重建固定历史视图，两者互斥。
副作用：只读取已取得的 Feed 和元数据，登记候选快照并写 views/candidates/；不访问来源。
自动配额 0；不调用模型、不领取任务；帮助不联网、不开库、不建目录。
输出去向：stdout 仅安全 JSON 身份、数量和相对文件名；完整题名、摘要只在私有视图中。
常见失败：未知根、损坏检查／快照或不安全布局退出 2；请核对原检查与备份后重跑。
退出码：成功 0（含未就绪候选）；参数错误或受控拒绝 2；中断 130。
示例：paper-radar experiment candidates --root /tmp/my-experiment --check-id CHECK
""",
)
def candidates(
    root: RootOption,
    check_id: Annotated[
        str | None, typer.Option("--check-id", help="已取得的 Feed 检查身份。")
    ] = None,
    view_id: Annotated[
        str | None, typer.Option("--view-id", help="既有候选快照身份；字节稳定重建。")
    ] = None,
) -> None:
    from paper_radar.experiment import ExperimentError, ExperimentRoot
    from paper_radar.experiment.candidates import CandidateViews

    if (check_id is None) == (view_id is None):
        typer.echo(
            "invalid_arguments：请提供 --check-id 或 --view-id 之一；查看 --help。",
            err=True,
        )
        raise typer.Exit(2)
    try:
        views = CandidateViews(ExperimentRoot(root))
        identifier = views.create(check_id) if check_id is not None else view_id
        assert identifier is not None
        result = views.render(identifier)
    except ExperimentError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo("interrupted：渲染中断；请按同一检查或视图身份重跑。", err=True)
        raise typer.Exit(130) from None
    except Exception as error:
        report_component_error(error)
        raise typer.Exit(2) from None
    typer.echo(json.dumps(result, ensure_ascii=False))


@experiment_app.command("init", cls=ExperimentCommand, help=INIT_HELP)
def initialize(root: RootOption) -> None:
    from paper_radar.body.models import BodyError
    from paper_radar.experiment import ExperimentError, ExperimentRoot
    from paper_radar.storage.errors import StorageError

    try:
        registered = ExperimentRoot(root).initialize()
    except ExperimentError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    except (BodyError, StorageError) as error:
        report_component_error(error)
        raise typer.Exit(2) from None
    except OSError:
        typer.echo(
            "unsafe_layout：初始化失败；请检查独立根布局和权限后重试。", err=True
        )
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo("interrupted：初始化中断；请使用同一显式根重跑 init。", err=True)
        raise typer.Exit(130) from None
    except Exception as error:
        report_component_error(error)
        raise typer.Exit(2) from None
    typer.echo(
        json.dumps(
            dict(
                root_id=registered.root_id,
                purpose=registered.purpose.value,
                database="paper-radar.sqlite3",
                data_root="data",
                blobs="data/blobs/sha256",
                config="config/settings.yaml",
                logs="logs",
                views="views",
            ),
            ensure_ascii=False,
        )
    )


@experiment_app.command("feed-fetch", cls=ExperimentCommand, help=FEED_HELP)
def feed_fetch(
    root: RootOption,
    request_id: Annotated[
        str, typer.Option("--request-id", help="幂等请求标识，1–128 字符。")
    ],
    contact_email: Annotated[
        str, typer.Option("--contact-email", help="显式 HTTP 联系邮箱；不保存在日志。")
    ],
) -> None:
    from paper_radar.experiment import ExperimentError, ExperimentRoot
    from paper_radar.experiment.feed import fetch_feed

    try:
        result = fetch_feed(
            ExperimentRoot(root), request_id=request_id, contact_email=contact_email
        )
    except ExperimentError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo(
            "interrupted：取得中断；请使用同一 request-id 与实验根重跑。", err=True
        )
        raise typer.Exit(130) from None
    except Exception as error:
        report_component_error(error)
        raise typer.Exit(2) from None
    typer.echo(json.dumps(result, ensure_ascii=False))
    if (
        result["reason"] not in {"acquired", "not_modified"}
        or not result["complete"]
        or any(
            item["reason"] is not None
            or not item["nontruncated_complete"]
            or item["language"] is None
            or item["language"]["status"] != "resolved"
            for item in result["items"]
        )
    ):
        raise typer.Exit(2)


EGRESS_HELP = """追加所有者对本实验根、阶段、provider/model 与数据类别的外发授权。

参数：必填 --root、--snapshot、--stage（boundary/value/read，可重复）和 --reason。
默认启用；--disabled 显式撤销。每次只授权所列阶段，其他阶段拒绝。
副作用：只追加版本化所有者决定与所选根安全日志；不调用模型，自动配额 0。
Screening 包含 Profile、题名摘要；Read 另包含合法正文提取物。
输出去向：stdout 安全 JSON，不回显理由正文或根路径；错误写 stderr。
常见失败：快照缺模型、授权损坏或根失配；请核对显式选择后重新登记。
帮助不联网、不开库、不建目录。退出码：成功 0；受控拒绝 2；中断 130。
示例：paper-radar experiment egress-authorize --root /tmp/my-experiment
--snapshot snapshot-id --stage boundary --stage value --stage read --reason 所有者批准
"""

EGRESS_STATUS_HELP = """只读查看所有者外发授权的安全状态与范围，不输出理由正文。

参数：必填 --root；副作用：无，不建日志、不写业务库；自动配额 0。
输出去向：stdout 安全 JSON，缺记录显示未授权；损坏不退回缺省。
常见失败：用途不符或链损坏；请核对实验根和授权历史，修复前保持拒绝。
帮助不联网、不开库、不建目录。退出码：成功 0；受控拒绝 2；中断 130。
示例：paper-radar experiment egress-status --root /tmp/my-experiment
"""


def _egress_error(error: Exception) -> None:
    from paper_radar.config import ConfigError
    from paper_radar.experiment.egress import EgressError
    from paper_radar.experiment.root import ExperimentError

    if isinstance(error, ExperimentError):
        typer.echo(str(error), err=True)
    else:
        reason = (
            error.reason
            if isinstance(error, (EgressError, ConfigError))
            else "egress_unavailable"
        )
        typer.echo(
            f"{reason}：授权未完成；请核对实验根、显式快照、阶段和完整授权链后重试。",
            err=True,
        )


@experiment_app.command("egress-authorize", cls=ExperimentCommand, help=EGRESS_HELP)
def egress_authorize(
    root: RootOption,
    snapshot: Annotated[str, typer.Option("--snapshot", help="显式历史配置快照。")],
    stage: Annotated[
        list[str], typer.Option("--stage", help="明确授权的阶段，可重复。")
    ],
    reason: Annotated[
        str, typer.Option("--reason", help="所有者理由，持久保存但不回显。")
    ],
    disabled: Annotated[
        bool, typer.Option("--disabled", help="追加撤销决定。")
    ] = False,
) -> None:
    from datetime import UTC, datetime

    from paper_radar.config import (
        load_config_snapshot,
        resolve_config_snapshot_reference,
    )
    from paper_radar.experiment.egress import (
        record_egress_authorization,
        selected_grants,
    )
    from paper_radar.experiment.root import ExperimentRoot
    from paper_radar.runtime_logging import FileSink, RuntimeLog

    selected = ExperimentRoot(root)
    try:
        selected.require()
        config = load_config_snapshot(
            selected.database,
            resolve_config_snapshot_reference(selected.database, snapshot),
        )
        grants = selected_grants(config, stage)
        log = RuntimeLog(FileSink(root))
        with log.operation("experiment", run=True):
            state = record_egress_authorization(
                selected,
                enabled=not disabled,
                reason=reason,
                grants=grants,
                now=datetime.now(UTC),
            )
    except KeyboardInterrupt:
        typer.echo("interrupted：登记中断；请只读核对授权后显式重试。", err=True)
        raise typer.Exit(130) from None
    except Exception as error:
        _egress_error(error)
        raise typer.Exit(2) from None
    typer.echo(state.model_dump_json())


@experiment_app.command("egress-status", cls=ExperimentCommand, help=EGRESS_STATUS_HELP)
def egress_status(root: RootOption) -> None:
    from paper_radar.experiment.egress import egress_authorization
    from paper_radar.experiment.root import ExperimentRoot

    try:
        selected = ExperimentRoot(root)
        selected.require()
        state = egress_authorization(selected.database)
    except KeyboardInterrupt:
        typer.echo("interrupted：查询中断；请重新查询授权。", err=True)
        raise typer.Exit(130) from None
    except Exception as error:
        _egress_error(error)
        raise typer.Exit(2) from None
    typer.echo(state.model_dump_json())


EGRESS_CHECK_HELP = """只读核对所选根、阶段、provider/model 与数据类别的外发授权。

参数：必填 --root、--snapshot、--stage（boundary/value/read，可重复）。
副作用：无；不刷新认证、不建日志、不领取任务；自动配额 0。
输出去向：stdout 安全 JSON，错误写 stderr，不回显理由正文。
常见失败：未授权、根/阶段/模型/类别不符或链损坏；请由所有者显式重新登记。
帮助不联网、不开库、不建目录。退出码：成功 0；受控拒绝 2；中断 130。
示例：paper-radar experiment egress-check --root /tmp/my-experiment
--snapshot snapshot-id --stage boundary
"""


@experiment_app.command("egress-check", cls=ExperimentCommand, help=EGRESS_CHECK_HELP)
def egress_check(
    root: RootOption,
    snapshot: Annotated[str, typer.Option("--snapshot", help="显式历史配置快照。")],
    stage: Annotated[list[str], typer.Option("--stage", help="核对阶段，可重复。")],
) -> None:
    from paper_radar.config import (
        load_config_snapshot,
        resolve_config_snapshot_reference,
    )
    from paper_radar.experiment.egress import (
        require_egress_authorization,
        selected_grants,
    )
    from paper_radar.experiment.root import ExperimentRoot

    try:
        selected = ExperimentRoot(root)
        selected.require()
        config = load_config_snapshot(
            selected.database,
            resolve_config_snapshot_reference(selected.database, snapshot),
        )
        for grant in selected_grants(config, stage):
            require_egress_authorization(
                selected,
                stage=grant.stage,
                provider=grant.provider,
                model=grant.model,
                categories=grant.categories,
            )
    except KeyboardInterrupt:
        typer.echo("interrupted：核对中断；请重新核对授权。", err=True)
        raise typer.Exit(130) from None
    except Exception as error:
        _egress_error(error)
        raise typer.Exit(2) from None
    typer.echo(json.dumps(dict(authorized=True, stages=stage), ensure_ascii=False))


PREFLIGHT_HELP = """汇总 B 静态执行阻断。
不领取任务、不刷新认证、不启动 Pi/Docling、不联网。

参数：必填 --root、--snapshot、--credentials-dir、--material-root、--install-root、
--attempt-root 和 --model-root；数据/配置根取实验根固定布局，其余根显式提供。
副作用：无；只读历史配置、供给、授权、凭据元数据与主机资源，不建日志；自动配额 0。
分别检查 Screening boundary/value 与 Read 所选槽，不借用另一槽证据。
主机 MemAvailable 仅披露实测值或 unknown，不设可用内存硬下限，不单独阻断。
输出去向：stdout 四态、受控原因和中文下一步；不输出私有载荷、理由或凭据。
常见失败：缺供给、授权、cwd、凭据元数据、隔离、cgroup 能力或模型快照磁盘；
按逐项下一步修复，内存采集成功不表示容量足够。
帮助不联网、不开库、不建目录。退出码：必要项全部通过 0；受控拒绝或阻断 2；中断 130。
示例：paper-radar experiment preflight --root /tmp/my-experiment --snapshot snapshot-id
--credentials-dir /tmp/credentials --material-root /tmp/materials --install-root /tmp/pi
--attempt-root /tmp/attempt --model-root /tmp/models
"""


@experiment_app.command("preflight", cls=ExperimentCommand, help=PREFLIGHT_HELP)
def preflight(
    root: RootOption,
    snapshot: Annotated[str, typer.Option("--snapshot", help="显式历史配置快照。")],
    credentials_dir: Annotated[
        Path, typer.Option("--credentials-dir", help="仅检查凭据元数据的目录。")
    ],
    material_root: Annotated[
        Path, typer.Option("--material-root", help="显式材料根。")
    ],
    install_root: Annotated[
        Path, typer.Option("--install-root", help="显式固定供给安装根。")
    ],
    attempt_root: Annotated[
        Path, typer.Option("--attempt-root", help="计划使用的 attempt 临时根，不创建。")
    ],
    model_root: Annotated[
        Path, typer.Option("--model-root", help="模型部署根，不下载或运行。")
    ],
) -> None:
    from paper_radar.doctor.cli import _show
    from paper_radar.doctor.service import Result
    from paper_radar.experiment.preflight import preflight_checks
    from paper_radar.experiment.root import ExperimentRoot

    try:
        checks = preflight_checks(
            ExperimentRoot(root),
            snapshot=snapshot,
            credentials_dir=credentials_dir,
            material_root=material_root,
            install_root=install_root,
            attempt_root=attempt_root,
            model_root=model_root,
        )
    except KeyboardInterrupt:
        typer.echo("interrupted：预检中断；请重新执行静态预检。", err=True)
        raise typer.Exit(130) from None
    except Exception as error:
        _egress_error(error)
        raise typer.Exit(2) from None
    passed = all(check.result is Result.PASSED for check in checks if check.required)
    typer.echo(
        f"scope=experiment-static result={'passed' if passed else 'failed'} "
        "自动配额=0；不证明真实执行已验。"
    )
    for check in checks:
        _show(check)
    if not passed:
        raise typer.Exit(2)


@experiment_app.command(
    "select",
    cls=ExperimentCommand,
    help="""按候选编号或 DOI 记录所有者选样与接受授权。

参数：必填 --root、--view-id、--request-id、--reason（所有者原文）、
--actor owner/agent；
--position 与 --doi 二选一；换样须提供 --replaces 与 --replacement-reason。
副作用：只追加本根授权并写 logs/；不调用模型，不产生 accepted 决定；自动配额 0。
同 request 重放仅返回原回执，不许可继续执行。
actor/授权者只是本地审计说明，不是认证或签名。
输出去向：stdout 安全 JSON；stderr 受控原因与下一步；理由仅保存在私有数据库。
帮助不联网、不开库、不建目录。常见失败：request_conflict、candidate_not_ready、
basis_changed、selection_changed；请回查 selection，
必要时生成新 candidates 并请所有者重选。
退出码：成功 0；参数错误、受控拒绝或执行失败 2；中断 130。
示例：paper-radar experiment select --root /tmp/my-experiment --view-id VIEW
--position 1 --reason '研究问题相关' --actor agent --request-id selection-1
""",
)
def select_candidate(
    root: RootOption,
    view_id: Annotated[str, typer.Option("--view-id", help="所有者所见候选视图身份。")],
    request_id: Annotated[str, typer.Option("--request-id", help="幂等请求标识。")],
    reason: Annotated[
        str, typer.Option("--reason", help="所有者原文选样理由；不输出到终端。")
    ],
    actor: Annotated[
        str, typer.Option("--actor", help="录入者 owner 或 agent；不是认证。")
    ],
    position: Annotated[
        int | None, typer.Option("--position", help="检查中的固定原位次。")
    ] = None,
    doi: Annotated[
        str | None, typer.Option("--doi", help="该检查中唯一论文 DOI。")
    ] = None,
    replaces: Annotated[
        str | None, typer.Option("--replaces", help="换样引用当前 selection-id。")
    ] = None,
    replacement_reason: Annotated[
        str | None, typer.Option("--replacement-reason", help="所有者原文换样理由。")
    ] = None,
) -> None:
    from paper_radar.experiment import ExperimentError, ExperimentRoot
    from paper_radar.experiment.selections import SelectionError, Selections, receipt
    from paper_radar.runtime_logging import FileSink, RuntimeLog

    try:
        selected = ExperimentRoot(root)
        selected.require()
        log = RuntimeLog(FileSink(selected.root))
        with log.execution("experiment", controlled=(SelectionError, ExperimentError)):
            record, replayed = Selections(selected.database, selected.data_root).select(
                view_id=view_id,
                request_id=request_id,
                reason=reason,
                actor=actor,
                position=position,
                doi=doi,
                replaces=replaces,
                replacement_reason=replacement_reason,
            )
    except (ExperimentError, SelectionError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo(
            "interrupted：选样中断；请使用同一 request-id 回查或重放授权。", err=True
        )
        raise typer.Exit(130) from None
    except Exception as error:
        report_component_error(error)
        raise typer.Exit(2) from None
    typer.echo(json.dumps(receipt(record, replayed=replayed), ensure_ascii=False))


@experiment_app.command(
    "selection",
    cls=ExperimentCommand,
    help="""只读查询当前选择及授权历史的安全投影。

参数：必填 --root。副作用：无，不创建日志；自动配额 0，不调用模型。
输出去向：stdout JSON 身份历史，不含原文理由或摘要；错误写 stderr。
帮助不联网、不开库、不建目录。常见失败：未知根或 registration_invalid，请核对可信备份。
退出码：成功 0（包括未选样）；参数错误或拒绝 2；中断 130。
示例：paper-radar experiment selection --root /tmp/my-experiment
""",
)
def selection_history(root: RootOption) -> None:
    from paper_radar.experiment import ExperimentError, ExperimentRoot
    from paper_radar.experiment.selections import SelectionError, Selections, receipt

    try:
        selected = ExperimentRoot(root)
        selected.require()
        records = Selections(selected.database, selected.data_root).history()
    except (ExperimentError, SelectionError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo("interrupted：查询中断；请重新查询 selection。", err=True)
        raise typer.Exit(130) from None
    except Exception as error:
        report_component_error(error)
        raise typer.Exit(2) from None
    typer.echo(
        json.dumps(
            dict(
                current_selection_id=records[-1].selection_id if records else None,
                history=[receipt(record) for record in records],
            ),
            ensure_ascii=False,
        )
    )


@experiment_app.command(
    "screen",
    cls=ExperimentCommand,
    help="""显式执行有效选样的 boundary → value 两阶段 Screening。

参数：必填 --root、--selection-id、--snapshot、--credentials-dir、--material-root、
--install-root。副作用：登记 manual 请求、领取当前代际剩余尝试、认证与 RPC 外发；
日志写所选根 logs/。自动配额 0；成功后不自动决定、Read 或 reuse。
可选 --receipt-id 只执行该回执，不登记请求、不继续另一阶段或增代；仍重新核对当前
选样、冻结版本、快照与代际；value 须有当前生产 boundary。成功/非当前回执拒绝，
末次租约过期未结算须先显式结算；ready 可显式继续，默认重放不代表继续许可。
可选 --continue-value 与 --receipt-id 互斥：从当前 pi_rpc 非 out_of_scope boundary
显式生产登记 value，只有首次新登记才执行；重复只回原 value 回执，ready 另用
--receipt-id。前置失败后可先执行 boundary 回执，再 --continue-value 完成两阶段。
输出去向：stdout 安全 JSON 回执，不展开摘要、Prompt 或模型正文；错误写 stderr。
帮助不联网、不开库、不建目录。常见失败：前置拒绝请核对选样、版本、外发授权与
豁免/严格证据；耗尽后显式 retry；out_of_scope 请所有者换样。精确重放只返回原回执。
退出码：成功/精确重放 0；前置或运行拒绝 2；out_of_scope 停止 3；预算耗尽 4；中断 130。
示例：paper-radar experiment screen --root /tmp/my-experiment --selection-id SELECTION
--snapshot SNAPSHOT --credentials-dir /tmp/credentials --material-root /tmp/materials
--install-root /tmp/pi
""",
)
def screen(
    root: RootOption,
    selection_id: Annotated[
        str, typer.Option("--selection-id", help="冻结的选样授权。")
    ],
    snapshot: Annotated[str, typer.Option("--snapshot", help="显式历史配置快照。")],
    credentials_dir: Annotated[
        Path, typer.Option("--credentials-dir", help="专用认证目录。")
    ],
    material_root: Annotated[
        Path, typer.Option("--material-root", help="显式材料根。")
    ],
    install_root: Annotated[
        Path, typer.Option("--install-root", help="所选固定安装根。")
    ],
    continue_value: Annotated[
        bool,
        typer.Option(
            "--continue-value",
            help="从当前生产boundary显式登记value；与--receipt-id互斥。",
        ),
    ] = False,
    receipt_id: Annotated[
        str | None,
        typer.Option("--receipt-id", help="只执行明确回执，不登记请求或自动增代。"),
    ] = None,
) -> None:
    from paper_radar.config import ConfigError
    from paper_radar.experiment import ExperimentError, ExperimentRoot
    from paper_radar.experiment.screening import ScreenError, Screening
    from paper_radar.feed_pipeline import PipelineError
    from paper_radar.pi_execution import ExecutionError
    from paper_radar.runtime_logging import FileSink, RuntimeLog
    from paper_radar.screening_tasks import TaskError, TaskReason

    try:
        selected = ExperimentRoot(root)
        selected.require()
        sink = FileSink(selected.root)
        log = RuntimeLog(sink)
        with log.execution(
            "experiment",
            controlled=(
                ScreenError,
                ExperimentError,
                ExecutionError,
                TaskError,
                ConfigError,
                PipelineError,
            ),
        ):
            result = Screening(
                selected,
                snapshot=snapshot,
                credentials_dir=credentials_dir,
                material_root=material_root,
                install_root=install_root,
                sink=sink,
            ).run(selection_id, receipt_id=receipt_id, continue_value=continue_value)
    except (ScreenError, ExperimentError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(
            4
            if isinstance(error, ScreenError) and error.reason == "budget_exhausted"
            else 2
        ) from None
    except ExecutionError as error:
        typer.echo(
            f"{error.reason}：执行前置未满足；请核对 doctor、供给及所有者豁免。",
            err=True,
        )
        raise typer.Exit(2) from None
    except TaskError as error:
        report_component_error(error)
        raise typer.Exit(
            4 if error.reason is TaskReason.BUDGET_EXHAUSTED else 2
        ) from None
    except KeyboardInterrupt:
        typer.echo(
            "interrupted：执行中断；请回查任务与租约，精确重放不继续执行。", err=True
        )
        raise typer.Exit(130) from None
    except Exception as error:
        report_component_error(error)
        raise typer.Exit(2) from None
    typer.echo(json.dumps(result, ensure_ascii=False))
    state = result["state"]
    if state == "out_of_scope":
        typer.echo("out_of_scope：已停止 value；请由所有者从候选清单换样。", err=True)
        raise typer.Exit(3)
    if state == "budget_exhausted":
        typer.echo(
            "budget_exhausted：当前代际已耗尽；请查询失败并显式 retry。", err=True
        )
        raise typer.Exit(4)


@experiment_app.command(
    "attach-pdf",
    cls=ExperimentCommand,
    help="""登记所有者独立确认,把合法 PDF 附加到选样冻结版本并冻结样本。

参数：必填 PAPER、--root、--selection-id、--version-id、--pdf、--sha256、
--owner-confirmed、--actor owner/agent、--request-id；owner-confirmed 同时表达所有者
已确认论文/版本归属及副本合法性；选样接受授权不替代该确认或六项版式核查。
不通过 DOI 检测文件归属；签名须为 PDF、至少 1024 字节且 SHA-256 完全一致。
副作用：先保存确认,再发布 PDF 制品,同事务附加/冻结/关联；日志写所选根 logs/。
中断可同 request 续办；版本/选样变化或最新样本与当前 PDF 不符则拒绝。
不调用模型/Docling、不扫描队列，自动配额 0；帮助不联网、不开库、不建目录。
输出去向：stdout 安全 JSON 引用,stderr 受控原因与下一步；不输出文件路径、理由或正文。
退出码：成功/精确重放 0；参数、未确认、版本/哈希/样本不符、
visibility 或执行失败 2；中断 130。
常见失败：请核对所有者确认、selection/accepted 和冻结版本；新文件用新 request，
旧 request 内容冲突不能覆盖；缺确认不能靠接受授权放行。
示例：paper-radar experiment attach-pdf PAPER --root /tmp/my-experiment
--selection-id SELECTION --version-id VERSION --pdf /tmp/sample.pdf --sha256 SHA256
--owner-confirmed --actor agent --request-id pdf-1
""",
)
def attach_pdf(
    paper: Annotated[str, typer.Argument(help="所有者明确确认的论文身份。")],
    root: RootOption,
    selection_id: Annotated[str, typer.Option("--selection-id", help="当前选样授权。")],
    version_id: Annotated[
        str, typer.Option("--version-id", help="所有者确认的选样冻结版本。")
    ],
    pdf: Annotated[Path, typer.Option("--pdf", help="所有者提供的合法 PDF。")],
    sha256: Annotated[str, typer.Option("--sha256", help="明确核对的 PDF SHA-256。")],
    actor: Annotated[str, typer.Option("--actor", help="确认代录者 owner 或 agent。")],
    request_id: Annotated[
        str, typer.Option("--request-id", help="幂等请求；中断可同 request 续办。")
    ],
    owner_confirmed: Annotated[
        bool, typer.Option("--owner-confirmed", help="所有者已独立确认归属和合法性。")
    ] = False,
) -> None:
    from paper_radar.body.models import BodyError
    from paper_radar.experiment.acceptance import AcceptanceError
    from paper_radar.experiment.pdf import PdfError, PdfSamples, receipt
    from paper_radar.experiment.root import ExperimentError, ExperimentRoot
    from paper_radar.experiment.selections import SelectionError
    from paper_radar.runtime_logging import FileSink, RuntimeLog

    try:
        selected = ExperimentRoot(root)
        selected.require()
        log = RuntimeLog(FileSink(selected.root))
        with log.execution(
            "experiment",
            controlled=(
                PdfError,
                ExperimentError,
                SelectionError,
                AcceptanceError,
                BodyError,
            ),
            paper_id=paper,
        ):
            if not owner_confirmed:
                raise PdfError("owner_confirmation_required")
            try:
                raw = pdf.read_bytes()
            except OSError:
                raise PdfError("pdf_unreadable") from None
            record, sample, replayed = PdfSamples(
                selected.database, selected.data_root
            ).attach(
                selected,
                paper_id=paper,
                version_id=version_id,
                selection_id=selection_id,
                pdf=raw,
                pdf_sha256=sha256,
                request_id=request_id,
                owner_confirmed=owner_confirmed,
                actor=actor,
            )
    except (PdfError, ExperimentError, SelectionError, AcceptanceError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo(
            "interrupted：PDF 登记中断；回查 trace 后以同 request 显式续办。", err=True
        )
        raise typer.Exit(130) from None
    except Exception as error:
        report_component_error(error)
        raise typer.Exit(2) from None
    typer.echo(
        json.dumps(receipt(record, sample, replayed=replayed), ensure_ascii=False)
    )


_LAYOUT_HELP = """生成六项私有版式材料或代录所有者六项布尔核查。

参数：必填 PAPER、--root、--fingerprint、--reading-sha256、--evidence-map-sha256；
绑定明确正文三元组；多个成功正文身份拒绝，不猜最新。
副作用：materials 只写 views/ 可重建材料，不改业务事实，不建日志；review 追加核查与
所有者/代录者关联，日志写 logs/。不重跑 Docling、不调用模型，自动配额 0。
输出去向：stdout 安全 JSON 身份及受控相对路径；正文/可选说明仅在私有根内。
帮助不联网、不开库、不建目录；渲染延迟导入已锁定 pypdfium2/Pillow，缺依赖受控拒绝。
常见失败：body_identity_mismatch、ambiguous_extractions、owner_conclusions_required、
layout_conflict、renderer_dependency_missing；核对当前样本与所有者输入，否决不可覆盖。
退出码：成功 0；参数错误或受控拒绝 2；中断 130。
示例：paper-radar experiment layout-materials PAPER --root /tmp/my-experiment
--fingerprint SHA --reading-sha256 SHA --evidence-map-sha256 SHA
"""


@experiment_app.command("layout-materials", cls=ExperimentCommand, help=_LAYOUT_HELP)
def layout_materials(
    paper: Annotated[str, typer.Argument(help="已冻结样本论文。")],
    root: RootOption,
    fingerprint: Annotated[str, typer.Option("--fingerprint", help="正文提取指纹。")],
    reading_sha256: Annotated[
        str, typer.Option("--reading-sha256", help="阅读成员哈希。")
    ],
    evidence_map_sha256: Annotated[
        str, typer.Option("--evidence-map-sha256", help="证据成员哈希。")
    ],
) -> None:
    from paper_radar.experiment.layout import Materials
    from paper_radar.experiment.root import ExperimentRoot
    from paper_radar.reading.context import ExtractionIdentity

    _layout_run(
        lambda: Materials(ExperimentRoot(root)).generate(
            paper, ExtractionIdentity(fingerprint, reading_sha256, evidence_map_sha256)
        )
    )


@experiment_app.command(
    "layout-review",
    cls=ExperimentCommand,
    help=_LAYOUT_HELP
    + """
review 参数：六个必填 --body-boundary、--reading-order、--sections、--headers-footers、
--provenance、--restricted-content 各为 true/false；--reviewer 必须 owner，
--recorder 必须 agent，--request-id 幂等；--note 可选所有者说明，不默认展示。
这些值必须来自所有者；本地身份说明不是认证，材料不预填判断。
示例：paper-radar experiment layout-review PAPER --root /tmp/my-experiment
--fingerprint SHA --reading-sha256 SHA --evidence-map-sha256 SHA --reviewer owner
--recorder agent --request-id review-1 --body-boundary true --reading-order true
--sections true --headers-footers true --provenance true --restricted-content false
""",
)
def layout_review(
    paper: Annotated[str, typer.Argument(help="已冻结样本论文。")],
    root: RootOption,
    fingerprint: Annotated[str, typer.Option("--fingerprint", help="正文提取指纹。")],
    reading_sha256: Annotated[
        str, typer.Option("--reading-sha256", help="阅读成员哈希。")
    ],
    evidence_map_sha256: Annotated[
        str, typer.Option("--evidence-map-sha256", help="证据成员哈希。")
    ],
    reviewer: Annotated[
        str, typer.Option("--reviewer", help="提供结论的所有者 owner。")
    ],
    recorder: Annotated[str, typer.Option("--recorder", help="代录者 agent。")],
    request_id: Annotated[str, typer.Option("--request-id", help="幂等请求标识。")],
    body_boundary: Annotated[
        str, typer.Option("--body-boundary", help="所有者正文边界结论 true/false。")
    ],
    reading_order: Annotated[
        str, typer.Option("--reading-order", help="所有者阅读顺序结论 true/false。")
    ],
    sections: Annotated[
        str, typer.Option("--sections", help="所有者标题层级结论 true/false。")
    ],
    headers_footers: Annotated[
        str, typer.Option("--headers-footers", help="所有者页眉页脚结论 true/false。")
    ],
    provenance: Annotated[
        str, typer.Option("--provenance", help="所有者证据定位结论 true/false。")
    ],
    restricted_content: Annotated[
        str,
        typer.Option("--restricted-content", help="所有者受限内容结论 true/false。"),
    ],
    note: Annotated[
        str, typer.Option("--note", help="所有者可选说明，仅私有保存。")
    ] = "",
) -> None:
    from paper_radar.experiment.layout import LayoutError, LayoutReviews
    from paper_radar.experiment.root import ExperimentRoot
    from paper_radar.reading.context import ExtractionIdentity

    def record() -> dict[str, object]:
        checks = dict(
            body_boundary=body_boundary,
            reading_order=reading_order,
            sections=sections,
            headers_footers=headers_footers,
            provenance=provenance,
            restricted_content=restricted_content,
        )
        if any(value not in {"true", "false"} for value in checks.values()):
            raise LayoutError("owner_conclusions_required")
        selected = ExperimentRoot(root)
        return LayoutReviews(selected.database, selected.data_root).record(
            selected,
            paper,
            ExtractionIdentity(fingerprint, reading_sha256, evidence_map_sha256),
            checks={key: value == "true" for key, value in checks.items()},
            reviewer=reviewer,
            recorder=recorder,
            request_id=request_id,
            note=note,
        )

    _layout_run(record)


def _layout_run(action: Callable[[], dict[str, object]]) -> None:
    from paper_radar.body.models import BodyError
    from paper_radar.experiment.layout import LayoutError
    from paper_radar.experiment.pdf import PdfError
    from paper_radar.experiment.root import ExperimentError
    from paper_radar.fulltext.models import FulltextError

    try:
        result = action()
    except (LayoutError, ExperimentError, PdfError, BodyError, FulltextError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo(
            "interrupted：操作中断；回查 trace 后显式重建或同 request 重放。", err=True
        )
        raise typer.Exit(130) from None
    except Exception as error:
        report_component_error(error)
        raise typer.Exit(2) from None
    typer.echo(json.dumps(result, ensure_ascii=False))


@experiment_app.command(
    "read",
    cls=ExperimentCommand,
    help="""显式新登记默认中文 Read，或继续已有任务。

参数：PAPER、--root、--snapshot、明确正文三元组、认证/材料/安装根；
--request-id 与 --task-id 二选一。新登记默认 zh/label=manual。
不创建 manual_read_request。
已有任务由 --task-id 继承其冻结 output_language/指纹，不登记新请求或新预算。
副作用：新登记最多执行当前代际剩余两次尝试，认证与 RPC 外发，写任务及所选根 logs/。
自动配额 0；不扫描队列。输出去向：stdout 安全回执。
分析内容另用 reading analysis 私有视图。
精确 --request-id 重放只回原登记身份，不继续；ready 用 --task-id 继续。
常见失败：先核对当前选样/PDF/正文、所有者六项和外发授权/豁免。
失败查询 reading failures，
过期租约必须 reading reclaim 显式结算，再用 --task-id 继续或 reading retry 追加后继。
输入超额拒绝，不截正文或丢章节。帮助不联网、不开库、不建目录。
退出码：成功/重放 0；前置/运行拒绝 2；预算耗尽 4；中断 130。
示例：paper-radar experiment read PAPER --root /tmp/experiment --snapshot SNAP
--fingerprint SHA --reading-sha256 SHA --evidence-map-sha256 SHA --request-id read-1
--credentials-dir /tmp/credentials --material-root /tmp/materials --install-root /tmp/pi
""",
)
def read(
    paper: str,
    root: RootOption,
    snapshot: Annotated[str, typer.Option("--snapshot", help="明确历史快照。")],
    fingerprint: Annotated[
        str, typer.Option("--fingerprint", help="当前正文提取指纹。")
    ],
    reading_sha256: Annotated[
        str, typer.Option("--reading-sha256", help="阅读成员哈希。")
    ],
    evidence_map_sha256: Annotated[
        str, typer.Option("--evidence-map-sha256", help="证据成员哈希。")
    ],
    credentials_dir: Annotated[
        Path, typer.Option("--credentials-dir", help="专用认证目录。")
    ],
    material_root: Annotated[
        Path, typer.Option("--material-root", help="显式材料根。")
    ],
    install_root: Annotated[Path, typer.Option("--install-root", help="所选安装根。")],
    request_id: Annotated[
        str | None, typer.Option("--request-id", help="幂等登记请求。")
    ] = None,
    task_id: Annotated[
        str | None,
        typer.Option("--task-id", help="继续明确已有代际，沿用冻结语言/指纹。"),
    ] = None,
) -> None:
    from paper_radar.experiment import ExperimentRoot
    from paper_radar.experiment.reading import READING_ERRORS, Reading
    from paper_radar.pi_execution import ExecutionError
    from paper_radar.reading.context import ExtractionIdentity
    from paper_radar.reading_cli import reading_clock, reading_error
    from paper_radar.runtime_logging import FileSink, RuntimeLog

    try:
        selected = ExperimentRoot(root)
        selected.require()
        sink = FileSink(selected.root)
        with RuntimeLog(sink).execution(
            "experiment", controlled=(*READING_ERRORS, ExecutionError)
        ):
            result = Reading(
                selected,
                snapshot=snapshot,
                credentials_dir=credentials_dir,
                material_root=material_root,
                install_root=install_root,
                sink=sink,
                clock=reading_clock,
            ).run(
                paper,
                identity=ExtractionIdentity(
                    fingerprint, reading_sha256, evidence_map_sha256
                ),
                request_id=request_id,
                task_id=task_id,
            )
    except BaseException as error:
        reading_error(error)
    typer.echo(json.dumps(result, ensure_ascii=False))
    if result["state"] == "failed":
        typer.echo("budget_exhausted：请 reading failures 查询并显式 retry。", err=True)
        raise typer.Exit(4)


report_app = typer.Typer(
    help="""实验范围的固定日报与成功分析单篇报告。

参数：必填 --root，render 另需 --date 与 --timezone，可选 --analysis-id 生成单篇。
副作用：render 固定数据库输入并原子发布；rebuild 仅写私有视图；verify 只读。
自动配额 0，不调用模型、不登记任务。帮助不联网、不开库、不建目录。
输出去向：安全 JSON 写 stdout；内容留所选根 views/；render 日志写 logs/。
退出码：成功 0；参数或受控拒绝 2；中断 130。
常见失败：身份、固定引用、证据或路径损坏；先 verify，保留历史后显式 rebuild。
示例：paper-radar experiment report render --root /tmp/my-experiment
--date 2026-11-14 --timezone Asia/Shanghai
""",
    no_args_is_help=True,
)
experiment_app.add_typer(report_app, name="report")


def _reports(root: Path, *, logging: bool = False) -> Any:
    from paper_radar.experiment.reports import Reports
    from paper_radar.experiment.root import ExperimentRoot
    from paper_radar.runtime_logging import FileSink

    selected = ExperimentRoot(root)
    selected.require()
    return Reports(
        selected.database,
        selected.data_root,
        selected.views,
        sink=FileSink(selected.root) if logging else None,
    )


def _report_error(error: Exception) -> None:
    from paper_radar.experiment.reports import ReportError
    from paper_radar.experiment.root import ExperimentError

    if isinstance(error, (ReportError, ExperimentError)):
        typer.echo(str(error), err=True)
    else:
        report_component_error(error)


@report_app.command(
    "render",
    cls=ExperimentCommand,
    help="""发布固定中文实验日报或成功分析单篇报告。

参数：必填 --root、--date（YYYY-MM-DD）、--timezone（IANA 时区）；
--analysis-id 选择单篇；--snapshot 可固定准入披露配置，缺失配置如实 unknown。
副作用：先固定库内 run/entry，再同目录临时文件、校验、fsync、原子替换、标记 published。
同日日报一发布即固定；当日晚到成功可生成单篇并等待次日日报。
自动配额 0；不调用模型、不新建任务。帮助不联网、不开库、不建目录。
输出去向：stdout 安全 JSON；私有内容 views/日期/UUID.md；文件日志 logs/。
退出码：成功 0；参数、分析不存在、闭包/路径失败 2；中断 130。
常见失败：先 verify 回查原成员，显式 rebuild 重建；不覆盖历史成员。
示例：paper-radar experiment report render --root /tmp/my-experiment
--date 2026-11-14 --timezone Asia/Shanghai
""",
)
def report_render(
    root: RootOption,
    day: Annotated[str, typer.Option("--date", help="受控报告日期 YYYY-MM-DD。")],
    timezone: Annotated[str, typer.Option("--timezone", help="显式 IANA 时区。")],
    analysis_id: Annotated[
        str | None, typer.Option("--analysis-id", help="成功分析身份；指定则生成单篇。")
    ] = None,
    snapshot: Annotated[
        str | None, typer.Option("--snapshot", help="准入披露的显式配置快照。")
    ] = None,
) -> None:
    try:
        result = _reports(root, logging=True).render(
            day=day, timezone=timezone, analysis_id=analysis_id, snapshot_id=snapshot
        )
        typer.echo(json.dumps(result, ensure_ascii=False))
    except KeyboardInterrupt:
        typer.echo("interrupted：发布中断；保留原 run，显式重跑完成发布。", err=True)
        raise typer.Exit(130) from None
    except Exception as error:
        _report_error(error)
        raise typer.Exit(2) from None


@report_app.command(
    "rebuild",
    cls=ExperimentCommand,
    help="""从冻结输入只读重建原报告。

参数：REPORT 与必填 --root。副作用：只写原 views/日期/UUID.md，不写数据库或日志。
自动配额 0；不调用模型、不读当前准入/主机/认证。帮助不联网、不开库、不建目录。
输出去向：stdout 安全 JSON，私有视图 views/。成功 0；身份、证据、路径损坏 2；中断 130。
常见失败：核对 backup verify 与固定成员，不能重新选样。
示例：paper-radar experiment report rebuild REPORT --root /tmp/my-experiment
""",
)
def report_rebuild(
    report_id: Annotated[str, typer.Argument(help="固定报告 UUID。")], root: RootOption
) -> None:
    _report_read_action(root, report_id, rebuild=True)


@report_app.command(
    "verify",
    cls=ExperimentCommand,
    help="""只读核对报告字节、固定成员、evidence 与受控路径。

参数：REPORT 与必填 --root。无写副作用、不建日志；自动配额 0，不调用模型。
帮助不联网、不开库、不建目录。输出去向：stdout 安全 JSON；错误 stderr。
退出码：成功 0；缺失、篡改、引用或不安全路径 2；中断 130。
常见失败：保留损坏诊断，核对备份后显式 rebuild。
示例：paper-radar experiment report verify REPORT --root /tmp/my-experiment
""",
)
def report_verify(
    report_id: Annotated[str, typer.Argument(help="固定报告 UUID。")], root: RootOption
) -> None:
    _report_read_action(root, report_id, rebuild=False)


def _report_read_action(root: Path, report_id: str, *, rebuild: bool) -> None:
    try:
        service = _reports(root)
        result = service.rebuild(report_id) if rebuild else service.verify(report_id)
        typer.echo(json.dumps(result, ensure_ascii=False))
    except KeyboardInterrupt:
        typer.echo("interrupted：报告核对中断；保留原成员后显式重试。", err=True)
        raise typer.Exit(130) from None
    except Exception as error:
        _report_error(error)
        raise typer.Exit(2) from None
