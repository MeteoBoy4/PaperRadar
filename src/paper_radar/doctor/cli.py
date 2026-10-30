"""只读诊断的中文投影。"""

import json
from pathlib import Path

import typer

from paper_radar.config import (
    ConfigError,
    StageName,
    check_config,
    load_config_snapshot,
    project_config,
    resolve_config_snapshot_reference,
)
from paper_radar.config.readiness import configuration_missing
from paper_radar.doctor.service import Check, Result, basic_checks

SUCCESS_NOTICE = (
    "result=passed 仅表示本范围必要检查通过；"
    "screening/reuse/read 的 readiness 与未验收能力见下，"
    "0 不代表任何阶段可运行。"
)

# §14 的九类。不查询审计库或推导未来 live 结论。
CAPABILITIES = (
    ("feed", "Feed readiness", "Audit/Source", "完成四刊审计并由 Source 判定 JGR。"),
    (
        "pi_adapter",
        "Pi adapter readiness",
        "Pi/Cwd/Live",
        "启动器未交付；cwd 白名单与现场隔离未验。另用 doctor --scope pi-supply "
        "--database <库> --snapshot <引用> 诊断供给。",
    ),
    ("calibration", "校准 readiness", "D", "配置 Profile/模型并完成正式校准。"),
    ("auto_read", "自动精读 gate", "D/G", "核实校准门禁与自动名额。"),
    (
        "fulltext_credentials",
        "全文凭证 gate",
        "F",
        "通过运行时凭据边界验收；本命令不读取凭据。",
    ),
    (
        "docling_fixture",
        "Docling fixture gate",
        "Extra/Body/F",
        "安装兼容探测并验收四刊 fixture 与内存。",
    ),
    ("backup_restore", "backup/restore gate", "I", "完成备份恢复与 NAS 演练。"),
    (
        "unattended",
        "unattended automation gate",
        "H/I",
        "确认时间、时区、容量及无人值守验收。",
    ),
)


def _show(check: Check) -> None:
    typer.echo(
        f"check={check.name} result={check.result.value} reason={check.reason} "
        f"下一步：{check.next_step}"
    )


def diagnose(
    scope: str,
    database: Path,
    *,
    settings: Path | None = None,
    snapshot: str | None = None,
) -> None:
    checks = list(basic_checks(database))
    failure = next((c for c in checks if c.result is not Result.PASSED), None)
    selected = None
    if scope == "config" and all(c.result is Result.PASSED for c in checks):
        try:
            if settings is not None:
                selected = check_config(settings, database)
            elif snapshot is not None:
                selected = load_config_snapshot(
                    database, resolve_config_snapshot_reference(database, snapshot)
                )
            else:
                checks.append(
                    Check(
                        "selection",
                        Result.MISSING,
                        "configuration_unselected",
                        "请显式选择 settings 或 snapshot。",
                    )
                )
        except ConfigError as error:
            checks.append(
                Check(
                    "selection",
                    Result.INVALID,
                    error.reason.value,
                    "所选材料不可读或非法；请使用 config check / "
                    "config snapshots list 检查并修正显式选择。",
                )
            )
        else:
            if selected is not None:
                checks.append(
                    Check(
                        "selection",
                        Result.PASSED,
                        "configuration_valid",
                        "显式材料已检查；不保存快照。",
                    )
                )
    passed = all(check.result is Result.PASSED for check in checks)
    typer.echo(f"scope={scope} result={'passed' if passed else 'failed'}")
    category_result = failure.result.value if failure else "passed"
    typer.echo(
        f"category=basic 基础工程 readiness result={category_result} "
        f"reason={failure.reason if failure else 'required_checks_passed'}"
    )
    for check in checks:
        _show(check)
    if scope == "basic":
        _show(
            Check(
                "selection",
                Result.MISSING,
                "configuration_unselected",
                "如需配置检查，请用 --scope config 并恰选 --settings 或 --snapshot。",
            )
        )
        for stage in StageName:
            typer.echo(
                f"stage={stage.value} result=missing reason=configuration_unselected "
                "下一步：使用 config 范围显式选择配置后检查。"
            )
    if selected is not None:
        typer.echo(
            "业务配置缺项（独立披露）："
            + (", ".join(configuration_missing(selected)) or "无")
        )
        if (
            selected.profile_status != "configured"
            or selected.model_slots["screening"] != "configured"
        ):
            typer.echo(
                "Profile/模型未配置，不能校准；下一步：补齐显式配置后交 D 验收。"
            )
        projections = project_config(selected).projections
        for stage in StageName:
            readiness = selected.stages[stage]
            ready = readiness.status == "ready"
            reason = ",".join(r.value for r in readiness.missing) or "configured"
            next_step = (
                "配置就绪；运行能力仍需承接模块验收。"
                if ready
                else "补齐所列版本化配置并重新检查。"
            )
            typer.echo(
                f"stage={stage.value} result={'passed' if ready else 'missing'} "
                f"reason={reason} 下一步：{next_step}"
            )
        typer.echo(
            "实际执行时，以下数据会离开本机并发送给所选外部 provider/model；"
            "本次只读诊断不发送。"
        )
        for stage, categories in (
            (StageName.BOUNDARY, "Profile,题名,摘要,截断事实"),
            (StageName.VALUE, "Profile,题名,摘要,截断事实,启用主题"),
            (
                StageName.REUSE,
                "Profile,合法结构化来源或正文的 availability/methods/data 摘录",
            ),
            (StageName.READ, "Profile,论文元数据,合法正文提取物"),
        ):
            model = json.loads(projections[stage].payload_json)["components"]["model"]
            # JSON 编码防止控制字符制造伪诊断行。来源仅为本次已验证选择。
            provider = json.dumps(
                model["provider"] if model else None, ensure_ascii=False
            )
            name = json.dumps(model["model"] if model else None, ensure_ascii=False)
            typer.echo(
                f"outbound_stage={stage.value} provider={provider} model={name} "
                f"外发数据类别={categories}；仅说明配置，不发送数据。"
            )
    for name, label, owner, next_step in CAPABILITIES:
        typer.echo(
            f"category={name} {label} result=not_assessed "
            f"reason=evidence_not_assessed owner={owner} 下一步：{next_step}"
        )
    if passed:
        typer.echo(SUCCESS_NOTICE)
    else:
        raise typer.Exit(2)
