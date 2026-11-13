"""B 显式实验命令;帮助与导入不访问业务根。"""

import json
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

参数：必填 --root。固定数据库 paper-radar.sqlite3，制品 blobs/sha256，配置
config/settings.yaml，日志 logs/，私有视图 views/；不猜测根。
副作用：创建目录与数据库；同根重放保持根身份；不改登记 production/unknown 库。
帮助不联网、不开库、不建目录；自动配额 0，不调用模型。
输出去向：stdout 安全 JSON，错误写 stderr，不输出私有绝对路径。
退出码：成功 0；参数错误或受控拒绝 2；中断 130。
常见失败：根用途不符或布局不安全；请使用独立空根，不迁移既有未知用途库。
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
    typer.echo(
        json.dumps(
            dict(
                root_id=registered.root_id,
                purpose=registered.purpose.value,
                database="paper-radar.sqlite3",
                data_root=".",
                blobs="blobs/sha256",
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
