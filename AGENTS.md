# PaperRadar

面向单用户的学术论文发现、筛选、全文精读、证据追踪和每日审阅流水线（V1）。

## 环境与验证

- Python 环境由 `uv` 管理；命令统一用 `uv run --offline --locked …`。
- 当我明确指示「运行完整离线门禁」时进行全量测试，完成门槛：`./scripts/check-offline` 返回 0（lockfile、Ruff、mypy、全部 pytest、冻结契约）。开发中涉及代码改动时跑相关的 `pytest` 子集。

## 必读文档

- `docs/roadmap.md`：当前前沿与计划。

- `GLOSSARY.md`、`docs/adr/`：具体见 `docs/agents/domain.md`。
- `intent/draft.md`：V1 规格与验收依据；先看文首「任务阅读导航」，按任务读取主要章节与联动约束。

上述来源之间或与任务冲突时，保持已有安全行为，向用户指出冲突并由用户裁决。

## 每个任务

- 改动范围以任务所需为界；拆分、整理只在本次触及的模块内进行，其他架构问题写进最终回复。
- 保留工作区中与任务无关的用户修改。
- 用中文回复用户（包括分析和最终回复）；代码标识符、命令和原文引用保持原样。
- 最终回复：改了什么、跑了哪些验证及结果、剩余风险与未验证的 live 行为。

## 按需阅读

- [路线图维护](docs/agents/roadmap.md)：to-spec 发布、implement-spec 收尾，或依赖、状态、待裁决、待探索及承接责任变化时。

- [V1 范围](docs/agents/scope.md)：判断能力是否属于 V1 时。
- [领域不变量](docs/agents/invariants.md)：改动持久化、Paper 身份与合并、Adapter、版本化配置或 Stage fingerprint 前。
- [Calibration](docs/agents/calibration.md)：改动 Screening 模型、Prompt、Profile 或自动精读门禁前。
- [LLM 与证据](docs/agents/llm-evidence.md)：改动模型调用、输出校验、Read evidence 或日志前。
- [Python 编码约定](docs/agents/python-conventions.md)：写代码、新增依赖、接入外部服务时。
- [测试](docs/agents/testing.md)：写测试、修 Bug、改 migration 或运行 live 验收时。
- [CLI 与用户输出](docs/agents/cli-output.md)：改动 CLI、错误信息或报告文本时。
- [文档维护](docs/agents/documentation.md)：改动公共 Contract、Schema、vocabulary、版本语义或架构时。
- [重构](docs/agents/refactor.md)：用户明确把任务定为重构时（例如 issue 本身就是重构），或新增模块前。

## Agent skills

### Issue tracker

Issues 与规格使用 GitHub Issues，见 `docs/agents/issue-tracker.md`。

### Triage labels

使用默认五角色标签，见 `docs/agents/triage-labels.md`。

### Domain docs

使用 single-context 布局：根目录 `GLOSSARY.md` 与 `docs/adr/`，见 `docs/agents/domain.md`。
