# 代码审查：A1-01 可安装 CLI 基础（b0d15bb）

- **审查对象**：`b0d15bb Implement installable CLI foundation (#2)`（HEAD）
- **固定点**：`HEAD^`（03703fd），diff 命令 `git diff HEAD^...HEAD`（8 文件，+660/-1）
- **规格来源**：GitHub Issue #2「A1-01：建立可安装的 CLI 与无副作用中文帮助」（无 comments）；父 spec Issue #1 与原方案 `intent/draft.md` 作背景约束
- **标准来源**：`AGENTS.md`、`pyproject.toml` 工具链配置、`CONTEXT.md`、`intent/draft.md`、`docs/adr/*`、`docs/agents/*` + Fowler 气味基线
- **审查方式**：Standards 与 Spec 两个独立只读子代理并行审查后聚合，两轴不混合排序
- **日期**：2026-09-19

## Standards

### 硬违规（文档标准）

**1. `pyproject.toml:12` — 声明了代码中未使用的 pydantic 依赖（文档标准间存在张力，需显式裁决）**

- **依据**：AGENTS.md「依赖与外部服务」：“除非新依赖能够明显简化当前需求，否则不要新增依赖”；「范围控制」：“只实现当前任务明确需要的内容”。
- **事实**：全仓 grep 确认 `src/` 与 `tests/` 无任何 pydantic import，仅 README、pyproject、uv.lock 提及；本 commit 的当前需求（可安装 CLI + 中文帮助）只用到 typer。
- **冲突说明**：`intent/draft.md:1341` 的技术栈建议包含 Pydantic 且要求“具体版本在阶段 A 锁定并进入验收证据”，Issue #2 验收标准第 1 条也明确要求“锁定本次需要的 Pydantic v2”。按 AGENTS.md「开始编码前」的冲突处理规则（“不要自行猜测解决方式……明确指出冲突”），此张力应显式裁决而非静默处理：因任务 spec 明确要求锁定 Pydantic v2，倾向认定为合规，但建议在 issue/合并记录中留一句依据（引用 draft.md:1341 与 Issue #2 AC1），避免“提前引入未使用依赖”被先例化。
- **实际影响**：若按违规处理——引入了一个当前无任何代码使用的运行时依赖，扩大锁定与审计面；若按合规处理——影响仅是需要一句书面依据。
- **最小修复**：在 Issue #2 或合并记录中注明“pydantic 为 Issue #2 AC1 与 draft.md:1341 明确要求锁定的阶段 A 技术栈”，或在后续契约 ticket 落地前移除 pydantic 并重生成 uv.lock（二选一，推荐前者）。

### 基线气味（判断性提示，非硬违规）

**2. `README.md:15-21` — possible Duplicated Code（文档漂移风险）**

- **依据**：气味基线 Duplicated Code——README 硬编码锁定精确版本（Pydantic 2.13.5、Typer 0.27.2、pytest 8.4.2、Ruff 0.16.8、mypy 1.20.2），与 `uv.lock` 内容重复。
- **实际影响**：每次依赖升级都需人工同步 README，遗漏则文档静默失真；AGENTS.md 要求文档与行为同步。
- **最小修复**：删去精确版本号，改为指向 `uv.lock`（保留工具清单即可）。

**3. `tests/deny_external_io/sitecustomize.py:14-16` — possible Duplicated Code（轻微）**

- **依据**：气味基线 Duplicated Code——三行同形 `setattr(..., _deny_operation)  # noqa: B010`。
- **实际影响**：新增屏蔽目标时继续复制带 noqa 的行，噪声累积；影响轻微。
- **最小修复**：以 `(module, "attr")` 元组列表加单次循环替换。

### 已核对合规（无发现）

- `intent/draft.md:1122` 帮助契约：ROOT_HELP（`src/paper_radar/cli.py:7-26`）覆盖用途/参数/副作用/配额/输出去向/常见失败/示例七要素，`tests/test_cli_help.py` 逐项断言。
- AGENTS.md「面向用户的行为」：帮助全中文；术语（Screening、复用升级、全文精读）与 `CONTEXT.md` 一致；错误信息给出可操作原因。
- AGENTS.md「CLI --help 不得触发网络请求或数据库写入」：sitecustomize 在子进程屏蔽 socket/sqlite3 并断言无文件落盘。
- AGENTS.md「离线测试」「遵守 lockfile」「文档同步」：`scripts/check-offline` 全部 uv 调用带 `--offline`/`--locked`。
- 气味基线其余条目（Mysterious Name、Feature Envy、Data Clumps、Primitive Obsession、Repeated Switches、Shotgun Surgery、Divergent Change、Speculative Generality 代码侧、Message Chains、Middle Man、Refused Bequest）在本 diff 未发现；`main()`→`app()` 与空 `root()` 属 Typer 入口惯例与帮助契约载体，不按 Middle Man 标记。

## Spec

**Spec 轴未发现问题。** Issue #2 五条验收标准全部经实际运行验证通过，未发现缺失/部分实现、范围蔓延或错误实现。

### 逐条核查与实测证据

- **AC1（uv 工程与锁定依赖）— 通过**：`pyproject.toml:10` 固定 Python `>=3.12,<3.15`（与 README 声明的 3.12/3.13/3.14 一致）；`uv.lock` 已提交并锁定 pydantic 2.13.5、typer 0.27.2、pytest 8.4.2、ruff 0.16.8、mypy 1.20.2；uv.lock 全部 23 个包均为上述工具的传递依赖，无数据库/网络/LLM 依赖。spec 明确要求“锁定本次需要的 Pydantic v2”，pydantic 不算蔓延。
- **AC2（真实入口 --help 返回 0 且要素齐全）— 通过**：实测在 /tmp 空目录用绝对路径运行 `.venv/bin/paper-radar --help`，退出码 0，输出覆盖七要素：用途（`cli.py:10`）、参数与选项（`cli.py:13`）、副作用（`cli.py:15-16`）、零配额（`cli.py:18`）、输出去向（`cli.py:20`）、常见失败（`cli.py:22-23`）、可复制示例（`cli.py:25`）。
- **AC3（无副作用）— 通过**：实测空目录运行后零新增文件；`tests/test_cli_help.py:26-37` 做文件系统前后对比且 env 仅保留 PATH 等四项（无 HOME/配置/凭据）；哨兵实测有效——`PYTHONPATH=tests/deny_external_io` 下 `socket.socket`、`socket.create_connection`、`sqlite3.connect` 均被 AssertionError 拦截（`sitecustomize.py:14-16`）；未提前初始化数据目录。
- **AC4（完整离线检查入口）— 通过**：实测 `bash scripts/check-offline` 在 HEAD 退出 0，依次执行 `uv lock --check --offline`、ruff format --check、ruff check、mypy、pytest（`scripts/check-offline:18-22`）；所有 uv 调用带 `--offline --locked`。另用 `git archive` 解到 /tmp 的干净副本（无 .venv、空缓存）实测：退出码 1、明确报错「Network connectivity is disabled」、不联网补装、不改写 lockfile，符合“失败返回非零”。
- **AC5（测试、文档、不夸大就绪状态）— 通过**：外部行为测试走真实安装入口（`test_cli_help.py:9-10` 取 `sys.executable` 同目录的 paper-radar）；README 安装/帮助/离线验证说明与实测一致；`README.md:3-4` 明确“Screening 契约…尚未实现”，测试断言帮助中不出现 `contracts`/`run-due`（`test_cli_help.py:46-47`），符合“尚未实现的能力不报告为就绪”。

### 附带观察（非 spec 违背，供参考）

- 裸运行 `paper-radar`（无参数）实测静默退出 0：`no_args_is_help=True`（`cli.py:31`）因 Typer 单命令提升机制未生效。spec 只要求 `--help` 行为，帮助文本亦写明“使用 --help 显示本说明”，不构成 spec 违背；如希望裸运行打印帮助，最小修复是显式 `invoke_without_command` 的 callback 或在多命令出现后自然生效。
- 哨兵将 `sqlite3.connect` 整体拒绝（含只读连接），略严于 spec 的“数据库写入被拒绝”，属无害的过度覆盖。

## 汇总

- **Standards 轴：3 项 finding**（1 项需显式裁决的文档标准张力 + 2 项判断性气味提示）；最严重为 pydantic 未使用依赖的标准张力（建议以一句书面依据裁决，而非改代码）。
- **Spec 轴：0 项 finding**；五条验收标准全部实测通过，无最严重问题。
