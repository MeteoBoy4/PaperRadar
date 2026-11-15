# Issue #185 Stage B 集成双轴审查 r2

## 审查范围与来源

| 项 | 值 |
| --- | --- |
| 固定点 | `main` = `6f0c4e93d43b86cf25e87d90bf5130e7533d19d1` |
| HEAD | `3a25e6574d50348f8ea7f92cb8961f028e4fa024`（`integration/185-stage-b`） |
| Diff 命令 | `git diff main...HEAD`（三点，对 merge-base） |
| 规模 | 283 文件，+36763 / −505，73 提交 |
| 主规格 | GitHub Issue #185 正文 + 6 条评论（含「我的裁决」「主机内存仅披露」「显式正文选择」三条所有者裁决） |
| 子规格 | #186–#201、#204–#206（提交信息中的引用；#187–#193 正文与评论已实读，其余按提交与 diff 交叉核对） |
| 契约/决策 | `docs/contracts/stage-b-workflow.md`（新增 +708）、`reports.md`、`exposure-export.md`、`screening-tasks.md`、`read-tasks.md`、`body-persistence.md`、`backup-restore.md`、`fulltext-extraction.md`、ADR-0070/0071、`intent/draft.md` §11 B |
| 交付声明（非需求） | `docs/verification/stage-b-engineering-closure.md`、`stage-b-*-coverage/scope*.md|json`、`issue-18x/19x/20x-*.md` |

提交分组：`a0b3487`→`5e09cb5` #186 生产 Prompt v1；`28a57f6`→`1d23cfb` #187 实验根与 JGR v2；`485245d`→`41ea0e7` #188 候选事实与私有视图；`517c878`→`bb40265` #189 外发授权与静态预检（+`f980d77` 内存仅披露）；`1a908c2` #190 选样授权；`bc710f6` #191 无 prompt 模型映射探测；`8c43542`/`5596312` #192 两阶段筛查；`612c43e` #193 恢复与论文 trace；`0ff3c21` #194 委派验收；`368e55e`/`c162e46` #195 PDF 确认与冻结样本；`08d59cb` #196 有界提取；`ef7052c` #197 版式材料与复核；`6828732`/`8e4d111` #198 显式 Read 与论文范围重试；`422a156`/`28512e8`/`744d07f` #199 冻结报告与决定排序；`4373b36` #200 暴露导出；`53c46f1`/`2f89033` #201 脱网回放；`9b30d56`/`e935c07`/`489308c` 显式正文选择与提取规范化 v2；`3a065fd`/`1459625`/`935a6be`/`01c87a9` #206 收口与冻结；`375322e`/`3a25e65` 离线门禁兼容。

两轴均为独立上下文的只读子 agent，均被授予 `bash`（`git diff|show|log|blame`、`gh issue view --comments`、`rg`、`sed`、`find`、只读 `python3`），均未修改工作树、未创建提交、未改动 Issue 状态、未运行 live。受工具限制（单轮只允许一个 subagent 调用）两轴按先后而非同一时刻并发执行，上下文仍彼此隔离。

**两轴完成状态**

- Standards：完成。实读 `AGENTS.md`、`docs/agents/`（11 份）、6 份 Contract、ADR-0071、`pyproject.toml`；未逐句比对 `intent/draft.md` §11 B；283 文件中重点阅读 `experiment/` 12 个、`body/` 4 个、`replay/` 2 个；测试按需抽查；未运行任何 pytest，全部结论为静态推断。
- Spec：完成。GitHub 可达，#185 正文与 6 条评论、#191/#192/#193 正文已实读；#186–#206 未逐条展开正文。真实链 #202–#205 的材料仅在实现者完成报告与私有根，无法回查（未核实）；测试未运行。

---

## Standards

### 工具与来源披露（子 agent 原话）

- 实际可用：`read`、`bash`；只读 `git diff/log/show/rev-parse`、`rg`、`sed`、`python3`（AST 脚本在 `/tmp`）、`gh issue view`（#185 评论可读）。
- 实读来源：`AGENTS.md`、`docs/agents/`（python-conventions/testing/documentation/invariants/cli-output/llm-evidence/calibration/verification-scope/scope/refactor）、`docs/contracts/{body-persistence,reports,exposure-export,stage-b-workflow,backup-restore,fulltext-extraction}.md`、ADR-0071、`pyproject.toml`。
- 未核实：`intent/draft.md` §11 B 原文未逐句比对；283 文件中重点阅读 23 个 `experiment/` 模块中的 12 个、`body/` 4 个、`replay/` 2 个；101 个测试文件未逐份通读（按需抽查）；**未运行任何 pytest**（未运行），所有结论为静态推断。

### 发现

**F1｜基线 smell：Duplicated Code（判断性）**
- 影响：可见性闸门在本 diff 中被新写 5 份近似副本，其中两份已各自带参数化，日后新增 capability 或改判定条件要同步 6 处。
- 位置：`src/paper_radar/experiment/reports.py:57-64`（`_visible`）、`experiment/pdf.py:86-93`、`experiment/acceptance.py:67-74`、`experiment/layout.py:29-34`（唯一带 `capability` 参数）、`body/selection.py:70-77`（`require_visibility`）。hunk 差异仅在 `VisibilityCapability.*` 与错误类。
- 标准/smell 引用：Fowler Duplicated Code；未找到文档化豁免。`docs/agents/python-conventions.md`「I/O 与确定性逻辑分离」未要求重复实现。
- 已有测试核查：拒绝分支逐模块覆盖——`tests/test_experiment_reports_logging.py:76`、`tests/test_experiment_layout_cli.py:852`、`tests/test_experiment_pdf_cli.py:338`、`tests/test_experiment_accept_cli.py:390`、`tests/test_body_selection_facts.py:204`；重构须保留这些断言。
- 最小建议：`calibration.visibility` 增一个 `require(capability, error: type[ValueError])`，五处改为一行调用。

**F2｜文档化标准（判断性偏硬）：Primitive Obsession + 词汇分散**
- 影响：`("boundary","value","read")` 作为裸字符串出现在 7 个模块；`Stage = Literal[...]`（`experiment/egress.py:26`）只用于 `Grant.stage`，`required_categories(stage: str)`（`egress.py:70`）是唯一运行时守卫，裸写 `{"boundary","value","read"}`（`:71`）。调用点 `screening.py:172`、`reading.py:231`、`model_mapping.py:139-140`、`preflight.py:357-359`、`cli.py:552,624`、`acceptance.py:272` 均为未受控字面量，新增/笔误阶段名不会有类型错误，只会落到 `egress_scope_mismatch`。
- 标准：`docs/agents/python-conventions.md`「用明确的领域类型和受控 enum / reason 表达状态与原因」。
- 已有测试核查：`--stage bogus` 路径**未覆盖**（`tests/test_stage_b_egress_preflight.py` 只覆盖阶段范围不符，如 `:91,:95`；全仓无 `required_categories` 直接用例）。
- 最小建议：`required_categories(stage: Stage)` + `selected_grants(snapshot, stages: Sequence[Stage])`，并补一条 `--stage bogus` 负例断言具体 reason。

**F3｜基线 smell：Data Clumps / 语义撒谎（判断性）**
- 位置：`experiment/exposure.py:146`、`experiment/validation.py:36` 均为 `Reports(database, data_root, data_root)`，把 `data_root` 当 `output_dir` 传入，而 `docs/contracts/reports.md:85` 明示「`Reports(database, data_root, output_dir)` 接受显式位置」。
- 影响：今日无害（`validate_all`/`history` 不使用 `output_dir`；仅 `_path` 使用，`reports.py:791`），但这两个对象具备 `render/rebuild` 能力，后续任一处误用会把私有视图写进制品根。
- 已有测试核查：两条路径均有用例（`tests/test_experiment_reports_migrations.py`、`tests/test_experiment_exposure_*`），但**无断言**构造参数身份，故不会发现误用。
- 最小建议：把 `exposure_*_in_connection`/`validate_all` 抽成只读 `ReportHistory(database, data_root)`，`Reports` 组合它；`output_dir` 不再被伪造。

**F4｜基线 smell：Duplicated Code（判断性，成本高）**
- 位置：`experiment/cli.py` 中「受控异常→`Exit(2)` / `KeyboardInterrupt`→`Exit(130)` / `Exception`→`report_component_error`」三支结构重复 19 次（`:165,246,326,382,410,453,562,580,632,694,776,810,927,1030,1252,1437,1486,1524`），仅中断文案与受控元组不同；而 `_layout_run`（`:1232`）已实现同一形状并被复用 4 次（`:1078,1107,1142,1229`）。
- 影响：退出码策略与 19 条中文下一步文案分散，`docs/contracts/stage-b-workflow.md` 的退出码表变更时易漏改。
- 已有测试核查：退出码/文案由各 `tests/test_experiment_*_cli.py` 断言（如 `tests/test_experiment_reports_cli.py:206`），重构须整批跑这些模块；未运行。
- 最小建议：把 `_layout_run` 泛化为 `_run(action, controlled=..., interrupted="…")`，逐条保留原中断文案。

**F5｜基线 smell：Repeated Switches on 字符串判别式（判断性）**
- 位置：报告条目的 `fact` 是无类型 `dict[str, Any]`，以 `fact["kind"]` 字符串驱动构建与校验：`experiment/reports.py:322`（`_nonanalysis_entry`）、`:428,:446,:493,:522`（4 个 `kind="pending"/"blocked"` 分发点）、`:903,:910,:946`（`_validate_nonanalysis` 的 `if/elif fact["kind"]`）。
- 影响：新增一类受阻事实须同时改 3 处并手工保持键名一致；`fact` 内还持久化中文 `next_action` 散文，属于受控 vocabulary 之外的自由文本。
- 标准：`python-conventions.md`「用明确的领域类型…表达状态与原因」。
- 已有测试核查：三种 kind 均有覆盖——`tests/test_experiment_reports_cli.py:138`、`tests/test_stage_b_review_report_quality.py:76`（`layout_review`）、`tests/test_experiment_reports_cli.py` 的 extraction 分支；未知 `kind` 会被 `fact["kind"] != attempt.failure.value` 拒绝，故无静默通过路径。
- 最小建议：`Literal` 判别式 Pydantic union（`PendingFact/NeedsPdfFact/QualityFailedFact/ExtractionFailedFact`），构建与校验共用同一 `match`。

### 未展开与未验证

- `experiment/{candidates,preflight,layout_rendering,model_mapping}.py`、`screening_tasks/`、`read_tasks/`、`backup/` 仅做导入图与点状抽查；`fulltext/normalization.py:66-67` 对非法 version 抛 `invalid_members`（reason 语义与契约 `docs/contracts/fulltext-extraction.md:173`「Schema 或固定编码不符」勉强相符，且 mypy strict 下对已类型化调用者不可达）——低优先，未列为独立发现。
- 模块级循环依赖：AST 扫描显示本 diff 新增的环只有 `body/__init__` 再导出与 `query_records` 边，均属包 `__init__` 假阳性；`refactor.md` 的「无循环依赖」未据此判违规（未核实语义层依赖方向）。
- 无 live、无全量门禁：本人未运行测试；`#185` 评论记录同 SHA 完整门禁退出 0 属所有者执行，本人未复核其原始输出。

---

## Spec

### 审阅范围与可用来源（子 agent 原话）

- 工具：`read` + `bash`（只读）；实际执行 `git log/diff/show`、`gh issue view`、`rg`、`sed`。
- GitHub 可达：#185 正文 + 6 条评论（含「我的裁决」「主机内存仅披露」「显式正文选择」）、#191/#192/#193 正文均可读；未逐条展开 #186–#206 全部正文（部分仅通过提交信息与 diff 交叉核对）。
- 未核实：真实链（#202–#205）材料只存在于实现者完成报告与私有根，无法回查；NAS/跨副本、供应商参数效力、现场资源不在本 diff 可证范围。
- 测试：未运行（仅静态阅读；按约束未跑全量）。

### 发现

**发现 1（implemented-but-wrong）：`paper trace` 的选样授权段未按论文过滤**

- 位置：`src/paper_radar/paper_trace.py:186` 取 `Selections(...).history()`（`src/paper_radar/experiment/selections.py:337` 返回**全根**、无 paper 过滤），`src/paper_radar/paper_trace.py:279-295` 直接把全部记录转成 `SelectionReference` 放进 trace；同函数内其他字段都按论文过滤（`delegated_acceptances` 见 :297-301、`pdf_confirmations`/`frozen_samples` 见 :305-315），只有 selections 漏过滤。
- 影响：实验根存在换样（跨论文）历史时，`paper trace <A> --workflow` 会展示 B 的 selection_id、version、`replaces` 链、authorizer/actor、选中时间；#193 验收「`paper show/trace` 组合论文事实……**选样授权与换样链**」限定为该论文；#185 §9 同。也会让读者误判 A 的换样链。
- 已有测试：`tests/test_screening_recovery_trace_cli.py:616-617` 只断言 `workflow["selections"][0]`，夹具是单样本单选择 → 未覆盖跨论文场景。
- 复现：未复现（需在同根内制造两次跨论文 selection，成本高）；静态证据已确认无过滤分支。
- 最小建议：构造 `SelectionReference` 时加 `if item.paper_id == paper_id`，`current` 用过滤后序列末项判断。

**发现 2（partial）：报告 evidence 缺「章节」，且实现者契约自行放宽**

- 位置：`src/paper_radar/experiment/report_rendering.py:192` 硬编码 `章节=unknown（未提供稳定章节定位）`。
- 需求：#185 §31「单篇报告……固定引用 analysis ID、PDF 哈希、正文三元组与 evidence（**页码、章节**、bbox、charspan）」；`intent/draft.md:1975`「evidence 可回查页码/bbox/**章节**/源 charspan」。
- 实现者报告侧材料 `docs/contracts/reports.md:72` 把该要求改写为「没有稳定章节定位时显示 unknown」——属实现者完成报告，不是需求变更，未见所有者裁决批准这一放宽。
- 根因链：`src/paper_radar/reading/context.py` 的 SourceBlock/Evidence 无章节轴，自 A 阶段 #95/#96 起未变（`git log main -- src/paper_radar/reading/context.py` 最新为 `f6ef808`），故 B 无法从既有 evidence 取章节。
- 已有测试：`tests/test_experiment_reports_cli.py:92-112` 断言 `bbox`/`char_span`/`pdf_sha256`，未断言章节 → 未覆盖。
- 最小建议：请所有者裁决（a）认可 unknown 披露并把 `intent/draft.md:1975`/`§31` 同步放宽，或（b）在报告投影中由持久正文块层级派生章节后引用。

### 已核对且未发现偏离的关键条款（抽样）

- #185 裁决「维持原 run、只看题名/摘要不计暴露、不新增禁令」：`experiment/exposure.py:89-118` 只统计 selection/screening/read/decision/PDF/report 成员；`docs/adr/0070` 与 `intent/draft.md:1961` 已落地。
- 「主机内存仅披露」：`experiment/preflight.py:38-70` 只披露/unknown，`required=False`；cgroup ≤8 GiB 且 swap=0 在 `experiment/extraction.py:127-129` 领取前拒绝。
- out_of_scope 不调用 value、两阶段间重读、request 重放不视为继续许可：`experiment/screening.py:246-300`。
- 候选清单编号=原位次、全量不截断、调用 visibility：`experiment/candidates.py:101-135`、`:190-196`。
- 失败队列仅当前指纹最新代际 failed，retry 需非空 request/reason/actor 且写前 visibility：`screening_tasks/query.py:38-64`、`service.py:124-148`、`retry.py:46-58`。
- 回放自证隔离/禁网、原根拒绝、闭包与 DB 不变：`replay/worker.py:27-79`、`:150-183`、`replay/service.py:38-72`。

### 规格内部冲突（非缺陷，需知悉）

#185 §8 把「回放」列为须向所选根写 `logs/` 的执行入口，但 §34 要求恢复副本输出闭集、`replay` 帮助声明「不建日志」，且 `replay/worker.py:160-171` 的输出闭集校验会因日志文件失败。实现按 §34 处理，未按 §8——建议在规格或 `stage-b-workflow.md` 明确回放不写根日志，避免后续按 §8 复检时被判缺失。

### 结论

Spec 轴：发现 1 处实现错误（跨论文选样泄漏到 trace）、1 处部分缺失（报告 evidence 章节，受 A 阶段 evidence 模型限制并需所有者裁决）。其余抽样条款与 #185 三条所有者裁决一致；未发现明显 scope creep（`probe-models` 已由 #191 验收标准「预检的独立选项或命令」授权，`body-select` 由所有者补充裁决授权）。真实链与私有回执未核实，不构成通过结论。

---

## 两轴汇总（分列，不跨轴排序）

- Standards：5 条发现，**0 条文档化硬违规**，全部为判断性（F1/F3/F4/F5 基线 smell，F2 文档化标准但判断性偏硬）。轴内最重：**F3**——`Reports(database, data_root, data_root)` 把制品根当输出目录，当前无害但具备 `render/rebuild` 能力，误用即会写脏制品根。
- Spec：2 条发现——1 条 implemented-but-wrong（**发现 1**：跨论文选样历史泄漏进 `paper trace`）、1 条 partial（发现 2：报告 evidence 缺章节）。轴内最重：**发现 1**（错误的论文级事实泄漏，验收条款已限定范围）；另有 1 条规格内部冲突（§8 vs §34）需文档裁决。
