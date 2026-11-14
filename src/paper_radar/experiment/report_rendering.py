"""冻结输入的确定性 Markdown;不查询当前事实,不解释 Read 接收规则。"""

import html
import json
from datetime import date
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import Field

from paper_radar.experiment.candidates import SnapshotModel


class ReportEntry(SnapshotModel):
    position: int = Field(ge=1, le=5)
    display_number: Literal["N1", "N2", "N3", "N4", "N5"]
    paper_id: str
    version_id: str
    revision_no: int = Field(ge=1)
    primary_kind: Literal["analysis", "pending", "blocked"]
    primary_ref: str
    analysis_id: str | None = None
    supporting_success_id: str | None = None
    section: Literal["transferable", "cognitive", "pending", "blocked"]
    first_publication_key: str
    available_at: str
    title: str
    # 获准的历史投影;Read schema/receiver 仍由 ReadQueries/analysis_payload 唯一拥有。
    basis: dict[str, Any] = Field(repr=False)


class ReportInput(SnapshotModel):
    renderer_version: Literal[1] = 1
    report_id: str
    kind: Literal["daily", "paper"]
    scope: Literal["experiment"] = "experiment"
    root_id: str
    report_date: str
    timezone: str
    snapshot_id: str | None
    frozen_at: str
    admission_fragment: str
    summary: dict[str, int]
    warnings: tuple[str, ...]
    entries: tuple[ReportEntry, ...]

    @property
    def relative_path(self) -> str:
        return f"{self.report_date}/{self.report_id}.md"


def validate_input(value: ReportInput) -> None:
    if (
        str(UUID(value.report_id)) != value.report_id
        or date.fromisoformat(value.report_date).isoformat() != value.report_date
        or not ZoneInfo(value.timezone)
        or len(value.entries) > 5
        or sum(e.primary_kind == "analysis" for e in value.entries) > 3
        or len({e.first_publication_key for e in value.entries}) != len(value.entries)
        or (
            value.kind == "paper"
            and (len(value.entries) != 1 or value.entries[0].primary_kind != "analysis")
        )
    ):
        raise ValueError("registration_invalid")
    for position, entry in enumerate(value.entries, 1):
        if (
            (entry.position, entry.display_number) != (position, f"N{position}")
            or entry.first_publication_key
            != f"{entry.primary_kind}:{entry.primary_ref}"
            or (entry.primary_kind == "analysis") != (entry.analysis_id is not None)
            or (
                entry.analysis_id is not None and entry.analysis_id != entry.primary_ref
            )
        ):
            raise ValueError("registration_invalid")


def _block(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    fence = "`" * max(
        3, max((len(s) for s in text.split() if set(s) == {"`"}), default=0) + 1
    )
    # JSON 字符串中的反引号可能含代码围栏,转义为等价 JSON 字符保持内容。
    text = text.replace("`", "\\u0060")
    return f"{fence}json\n{text}\n{fence}"


def _title(value: str) -> str:
    # Markdown 元字符用字符实体显示原字面文本;模型/题名不能制造链接、HTML 或围栏。
    special = frozenset("\\`*_{}[]()#+-.!|\r\n")
    return "".join(
        f"&#{ord(char)};" if char in special else html.escape(char) for char in value
    )


def render(value: ReportInput) -> bytes:
    validate_input(value)
    lines = [
        "# 最小实验日报" if value.kind == "daily" else "# 实验单篇报告",
        "",
        "**实验范围：experiment；实验建议与报告无自动决定权。**",
        f"报告：{value.report_id}；日期：{value.report_date}；时区：{value.timezone}；"
        f"固定时点：{value.frozen_at}；renderer=1",
        "",
        "## 运行摘要",
        "；".join(f"{key}={count}" for key, count in sorted(value.summary.items())),
    ]
    if value.warnings:
        lines.extend(
            ("", "告警（故障不解释为无新结果）：", *(f"- {w}" for w in value.warnings))
        )
    if not value.entries:
        lines.extend(("", "因故障没有结果。" if value.warnings else "无新结果。"))
    lines.extend(("", "## 执行能力与证据披露", value.admission_fragment))
    headings = {
        "transferable": "可转化成果",
        "cognitive": "认知增益",
        "pending": "摘要速览／待决定",
        "blocked": "全文受阻",
    }
    for section, heading in headings.items():
        entries = [e for e in value.entries if e.section == section]
        if not entries:
            continue
        lines.extend(("", f"## {heading}"))
        for entry in entries:
            lines.extend(
                (
                    "",
                    f'<a id="{entry.display_number}"></a>',
                    f"### {entry.display_number} {_title(entry.title)}",
                    f"paper={entry.paper_id}；primary={entry.primary_kind}:{entry.primary_ref}；"
                    f"first-publication key={entry.first_publication_key}",
                    "",
                    "### Screening（实验非决定支撑）",
                    _block(entry.basis.get("screening")),
                    "",
                )
            )
            acceptance = entry.basis.get("acceptance")
            lines.extend(
                (
                    "### 决定来源：所有者授权 + Agent 代执行"
                    if acceptance is not None
                    else "### 决定来源：尚无代执行接受决定（保留选样授权）",
                    _block(
                        acceptance
                        if acceptance is not None
                        else entry.basis.get("authorization")
                    ),
                )
            )
            if entry.primary_kind == "analysis":
                payload = entry.basis["analysis"]
                lines.extend(
                    (
                        "",
                        "**受限内容未核对：表格精确值、公式及不可靠字符必须回查 PDF；"
                        "本报告不表示已核对。**",
                        "",
                        "### 固定分析／PDF 哈希／正文三元组与规则身份",
                        _block(
                            {
                                k: payload[k]
                                for k in (
                                    "analysis_id",
                                    "task_id",
                                    "snapshot_id",
                                    "pdf_sha256",
                                    "sample_id",
                                    "identity",
                                    "rule_versions",
                                )
                            }
                        ),
                        "",
                        "### Read 结构化输出",
                        _block(payload["output"]),
                        "",
                        "### 丢弃标记与每类计数",
                        _block(
                            {
                                k: payload[k]
                                for k in ("has_discards", "discard_counts", "discards")
                            }
                        ),
                        "",
                        "### Evidence（页码／章节／bbox／charspan）",
                        "page_no 为原页码；char_span=start:end；"
                        "章节=unknown（未提供稳定章节定位）。",
                        _block(payload["evidence"]),
                    )
                )
            else:
                lines.extend(
                    ("", "### 摘要／受阻依据与下一步", _block(entry.basis.get("fact")))
                )
    lines.extend(
        (
            "",
            "## 固定成员",
            *(
                f"- [{e.display_number}](#{e.display_number}) "
                f"{e.primary_kind}:{e.primary_ref}"
                for e in value.entries
            ),
            "",
        )
    )
    return "\n".join(lines).encode("utf-8")
