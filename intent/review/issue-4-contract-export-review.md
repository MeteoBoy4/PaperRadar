# 代码审查：Issue #4 冻结契约导出（HEAD~3...HEAD）

- 固定点：`HEAD~3`（d2f42d1）
- 提交：`eef5f6e Implement immutable boundary contract export (#4)`、`b085f56 Address contract export review findings`、`d52963f Document contract export result vocabulary`（经 `git log HEAD~3..HEAD --oneline` 验证恰好三笔）
- 规格来源：GitHub Issue #4（正文 + 全部 2 条 comments）
- 审查方式：只读；未修改代码、未创建 commit、未对 Issue 做写操作
- 离线验证（由审查代理实际运行）：`uv run pytest tests/ -x -q` 65 通过；已提交的 `contracts/screening/boundary/v1/` 快照与导出器全新输出字节一致（sha `9fd5127a…8805a7`）

## Standards

整体合规：冻结契约由权威 Pydantic 模型直接生成（`schema.py:81`），不维护第二份手写 Schema；重复运行幂等；`--help` 无副作用且在 `deny_external_io` 下有测试；用户文本为中文；错误不泄漏底层异常文本（有测试钉住）。`FrozenContract` 保持纯值对象、I/O 全部落在 `export.py`，符合 AGENTS.md「将确定性逻辑与 I/O 分离」，故不报 Feature Envy。

### (a) 违反仓库明文规范（硬违规）

无发现。

### (b) Fowler 基线判断题

**J1. Duplicated Code / magic strings** — `src/paper_radar/contracts/export.py:134-145`
- 依据：Fowler 基线 Duplicated Code；AGENTS.md「优先使用明确的领域类型和受控 enum / reason，避免 magic string」。
- 问题：校验端用字面集合加字符串 `.get()` 键重新声明了 manifest 字段词汇，与写入端 `schema.py:90-98` 的 dict 构造重复。
- 实际影响：manifest 格式变化（如 `format_version` 升位、新增字段）需两处同步修改；一旦漂移，健康快照会被误报为 `damaged_snapshot`。
- 最小修复：在 `schema.py` 提供单一字段词汇定义（或「manifest 减去 hash」的期望结构），让校验端消费它。

**J2. Duplicated Code（Minor）** — `tests/test_contract_export.py:26-29`
- 问题：测试重新实现了 `_canonical_json`，而非从 `paper_radar.contracts.schema` 导入私有助手 `_canonical_json_bytes`。
- 实际影响：规范序列化规则变化时，伪造快照类测试会静默测试另一套格式。
- 最小修复：导入该私有助手。

**J3. 重复执行（Minor）** — `scripts/check-offline:20-23`
- 问题：三个契约测试文件单独跑一遍后，第 24 行的全量 `pytest` 又覆盖一遍；文件清单维护在两处。
- 实际影响：若意图是提前给出带标签的失败定位则合理；否则属冗余。
- 最小修复：如非刻意，删除该专项步骤。

**J4. 错误具体度（规范边缘，低优先级）** — `src/paper_radar/contracts/export.py:223`
- 依据：AGENTS.md「错误信息应说明可操作的具体原因」。
- 问题：「未知契约或无效声明版本。」把两种不同原因合并为一句。
- 实际影响：用户无法直接看出是契约名还是版本号无效；目前合法值各只有一个，列明成本极低。
- 最小修复：分别报出哪个选择无效及合法取值。

**J5. 术语表缺口（信息性）**
- 依据：`docs/agents/domain.md` 的单一上下文文档约定。
- 问题：本特性引入「冻结契约快照 / snapshot」，但 CONTEXT.md 目前只定义了「来源快照」（另一概念）。
- 实际影响：后续 ticket 的对接方可能混淆两个「快照」。
- 最小修复：在 CONTEXT.md 术语表中补记新词。

### 已评估未报

- `tests/test_contract_export.py` 不可写目标测试用 `chmod 0o500`，以 root 运行时不会失败——单用户目标环境下可接受。

## Spec

实现高度忠实。逐条验收结论：

- **AC1（权威生成 + 确定性字节）— 通过**：`build_frozen_contract` 直接调用 `BoundaryOutput.model_json_schema()`（`schema.py:81`），无手写字段副本；规范 JSON（排序键、UTF-8、无时间/绝对路径/随机值）固定在 `schema.py:62-72`；已提交快照可由导出器字节级重导（`tests/test_contract_schema.py:38-45` + 跨进程 CLI 测试钉住）。
- **AC2（CLI、退出码、路径防逃逸）— 通过**：三个选项显式必选（`cli.py:91-105`）；未知/无效选择退出码 2 且中文受控报错；symlink 逃逸防护在 `export.py:96-100`（`tests/test_contract_export.py:164-175` 实测）；仅注册 `boundary/v1`（`schema.py:51-59`）。
- **AC3（不可覆盖 + 三类判据分离）— 通过**：损坏/版本不一致/内容冲突为独立的 `ContractExportErrorCategory` 值，各有独立中文提示与确定性判据（`export.py:111-168`）及各自测试——精确满足 Comment 2；旧版本目录保留（`export.py:188-207` 不触碰兄弟目录，有测试）。
- **AC4（安全落盘 + 故障注入）— 通过**：staging 目录 + fsync + 原子 `os.replace` 发布（`export.py:188-207`）；monkeypatch `os.replace` 的中断注入证明无半文件且历史保持（`tests/test_contract_export.py:203-225`）；错误信息剥离注入的 secret 字符串；CLI 失败用例断言绝不伪报成功（`tests/test_contract_cli.py:95-114`）。
- **AC5（快照提交 + 中文帮助/无副作用）— 通过**：快照已提交；根、组、export 三级帮助均为中文且在 `deny_external_io` 下无副作用（`tests/test_cli_help.py:19-62`）；v1 与哈希已文档化（`docs/contracts/frozen-contracts.md:50-51`）。
- **AC6 — 部分实现**（唯一 finding，见 A1）。

### (a) 缺失/部分实现

**A1（低严重度）：冲突/历史/路径/中断未通过真实 CLI 验证** — `tests/test_contract_cli.py` 全体
- 依据：AC6「通过真实 CLI 和磁盘结果验证确定性、幂等、冲突、历史保留、路径与中断行为」。
- 问题：真实 CLI（子进程）测试只覆盖确定性、幂等、无效选择、输出失败；损坏/版本不一致/内容冲突、历史保留、路径逃逸、中断行为仅通过 Python API 在真实磁盘上测试（`tests/test_contract_export.py`）。
- 实际影响：低——CLI 是同一磁盘路径上的薄封装（`cli.py:107-111`）；但字面条文未完全满足，未来 CLI 层回归（如错误类别到退出码/消息的映射）无法端到端捕获。
- 最小修复：复用现有 `_run_cli` 增加 2–3 个子进程用例（如快照损坏 → stderr 含「损坏」；symlink 逃逸 → 非零退出），或在 `docs/contracts/frozen-contracts.md` 明确说明 API/CLI 测试分工。

### (b) 范围蔓延

无发现。未实现批处理导出、未实现只读 `check` 命令；help 与文档均按票据边界明确推迟到 A1-08/A1-04。

### (c) 实现有误

无发现。补充两点观察（不构成违规）：

- SIGKILL 落在 staging 写入与 `os.replace` 之间会在 `boundary/` 留下隐藏的 `.v1-XXXX` 残留目录（`export.py:190-207`）；校验只读取精确的 `v1` 路径，残留永不可能被误认为有效快照，故规格安全，但后续运行不会回收它。
- 中断测试用手写 `v0` 文件充当「历史」（`tests/test_contract_export.py:207-209`）而非导出器产物；因同版本同内容路径已被证明为 no-op，可接受。

## 小结

- Standards 轴：5 项 finding（0 项硬违规，5 项判断题）；最严重为 J1（`export.py:134-145` manifest 字段词汇两处维护，漂移会把健康快照误报为损坏）。
- Spec 轴：1 项 finding（1 项部分实现，低严重度）：A1（AC6 的冲突/历史/路径/中断未走真实 CLI）；无范围蔓延、无错误实现。
- 两轴均不构成 Issue #4 验收阻塞；J1 修复为提取共享定义级，A1 修复为补 2–3 个 CLI 用例级。

## 实施代理复核与处理

复核范围：逐条对照 Issue #4 正文、两条评论、父 Issue #1 的适用决定、当前实现与
公开 seam。以下处理由实施代理完成；原始审查内容保留，便于追踪建议与处置之间的
关系。

| Finding | 结论 | 处理 |
| --- | --- | --- |
| J1 manifest 字段词汇重复 | 合理，采纳 | 在 `schema.py` 增加内部受控 `_ManifestField` 与单一格式版本常量；生成端和校验端共同消费，消除字段名与格式版本的双写。 |
| J2 测试应导入生产私有序列化 helper | 不采纳该修复方式 | 测试导入 `_canonical_json_bytes` 会耦合私有实现，并让生产与期望由同一算法生成，违反公开 seam 和独立期望原则。测试编码已集中到 `tests/contract_snapshot_support.py`，明确作为已发布文件格式的独立测试依据；生产规范若变化，版本/冲突分类断言会失败而非静默通过。 |
| J3 完整离线入口重复执行契约测试 | 合理，采纳 | 删除专项 pytest 重跑；完整 `pytest` 会自动收集全部契约测试。README 同步说明全量测试已包含冻结契约覆盖。 |
| J4 未知契约与无效版本共用提示 | 合理，采纳 | 分别校验契约名和声明版本，分别列出当前合法值；未实现的合法组合另有独立可操作提示。真实 CLI 测试固定两类消息。 |
| J5 “冻结契约快照”术语缺口 | 合理，采纳 | 在 `CONTEXT.md` 增加规范术语“冻结契约”，明确其版本与不可覆盖语义，并与“来源快照”和手写 Schema 区分；无需 ADR。 |
| A1 部分场景未走真实 CLI | 合理，采纳 | 真实安装入口现覆盖损坏、版本不一致、内容冲突、历史保留、路径逃逸和发布中断；均断言非零退出、受控错误与磁盘不被覆盖。中断由测试子进程在 `os.replace` 系统边界固定注入，不向产品接口增加测试开关。 |

其他观察的处置：SIGKILL 可能留下隐藏 staging 目录，但不会形成有效 `v1` 快照或
伪报成功，且进程被强杀后无法依靠当前进程执行清理；本票不增加清理器。手写 `v0`
仅用于证明兄弟历史目录不被触碰，不冒充已实现版本，保留现状。不可写目录测试的
运行环境限制也保持原审查中的“已评估未报”结论。

处理后实际运行 `./scripts/check-offline`：lockfile、Ruff 格式、Ruff 静态检查、
mypy 和全部 70 项离线测试均通过；未运行任何 live source 验收。
