# 阶段 A9 双轴审查 r2（#92 / #93–#99）

- 固定点：`main` = `04ed7073172fdf6db9427dd68670b169140c2748`
- 被审：HEAD = `4d559c495b5158d5bd079e672a8fde6f540ba277`（分支 `integration/issue-92-read-contract`）；审阅开始时工作树干净（`git status --porcelain` 为空）
- diff：`git diff main...HEAD`（三点，对 merge-base）＝ 89 files, +9437/−204；`git log main..HEAD --oneline` 共 22 个提交（含 8 个 merge）
- 提交列表：`192a51f`(#93) → `24a8741`(merge) → `592cd9c`(#97) → `4ef5288`(merge) → `1dbd3da`(#94) → `e926cec`(merge) → `a5e6ad4`(docs) → `c2d38b7`(merge) → `e285058`(#96) → `2939463`(merge) → `e76267d`(#95) → `f6ef808`(merge) → `49dbca6`(docs) → `9a67733`(merge) → `676aaa5`(#98) → `a719943`(merge) → `26ed341`(#99) → `9e44d35`(merge) → `c2200c7`(审阅修复) → `3da9170`(merge) → `c446011`(门禁修复) → `4d559c4`(merge)
- 两轴分别由独立只读子 agent（`oracle`，**均具备 `bash`**）执行，互不共享上下文；本文按轴分列，**未跨轴合并或重排**
- 与 #99 完成评论所称「双轴审查发现的 3 项规范问题、3 项数值规格问题已修复并由原审查代理复核关闭」的关系：本条为该分支的第二次独立双轴审阅（r2），结论按本次两轴报告独立给出，不继承此前结论

## 工具与来源（两轴共同）

- **规格来源**（按 `docs/agents/issue-tracker.md`，`gh` 可用；评论优先于正文，已落盘于工作树外）：
  - `/tmp/a9_spec.txt`（885 行）：父票 **#92** 正文（Problem Statement / Solution / 42 条 User Stories / 21 条 Implementation Decisions / Testing Decisions 验收面表 / DoD / Out of Scope / Further Notes）＋其 4 条评论（补充裁决点、五项裁决结果、契约所有权与字段闭集、最终裁决确认）＋子票 **#93–#99** 正文与实现者完成评论
  - 优先级（两轴均按此执行）：后续所有者裁决 > 早先「建议默认」> 父票正文 > 子票正文 > 实现者完成报告；完成报告只作线索，须与代码核对
  - Issue 图（已核对，`subIssues.totalCount`/`blockedBy.totalCount` 与 nodes 数一致）：#92 `state=OPEN`、`assignees=[]`、`blockedBy=[29,15,1]`；原生子票 #93–#99 全部 `CLOSED`，`subSummary={completed:7,total:7}`；依赖链 #93→#94/#97，#94→#95/#96，#97+#96+#95→#98→#99
- **标准来源**（仓库无 `CODING_STANDARDS.md` / `CONTRIBUTING.md`）：`AGENTS.md`、`CLAUDE.md`、`docs/agents/{python-conventions,testing,invariants,llm-evidence,documentation,cli-output,scope,refactor,domain,calibration}.md`、`GLOSSARY.md`、`README.md`、`docs/adr/`（0008/0010/0023/0025/0026/0027/0030）、`docs/contracts/{frozen-contracts,read-validation,runtime-config,config-snapshots,config-projections,stage-inputs,backup-restore,verification-status}.md`、`docs/verification/{offline-evidence,a9-scope-review}.md`、`scripts/{check-offline,verification_status.py,offline_evidence.py,a9_scope.py,a9_acceptance.py,audit_verification_scope.py}`、`intent/draft.md` 相关章节，另加 skill 指定的 smell baseline（已在两轴提示词 `/tmp/a9_standards_prompt.md`、`/tmp/a9_spec_prompt.md` 中全文粘贴）
- **两轴子 agent 实际工具**：均使用 `oracle` 角色，**具备 `bash`**（只读 `git`/`rg`/`sed`/`python3`/`pytest`/`ruff`/`mypy`）以及 `read`/`grep`/`find`/`ls`；**无 `edit`/`write`/`gh`**，未改仓库、未建 commit、未改 Issue 状态或标签、未运行 live
- **两轴子 agent 实跑**：两轴各自执行 `uv run --offline --locked python -m pytest -q tests/test_read_*.py tests/test_a9_*.py -p no:randomly` → **541 passed**（Standards 51.83s / Spec 48.83s）；Standards 轴另跑 `ruff check`（All checks passed）与 `mypy src/paper_radar/reading`（Success, 10 files），并核对 `reading` 包未导入 `config`/`llm`/`screening_tasks`
- **聚合者独立复核**（本轮实际执行，均为只读）：
  - `contracts check --contract read --contract boundary --contract value-prediction --contract reuse-assessment --contract decision-reasons --version v1 --target contracts` → 5/5 `passed`，退出 0；`read v1` SHA-256 = `1ac06948024aab610c6b2c1098d0a53596632c940704d32fae860a03ed5d6111`，与 #99 完成评论所称一致，且与 `docs/contracts/frozen-contracts.md:130` 登记值一致
  - `./scripts/verification-status 6d02e607ba2d40b78a694acf88e92187` → **passed / verified / applicability=same**、6/6 检查、1254s、`collected=4811 passed=4811`、failed/skipped/deselected/incomplete 均 0、退出 0；`terminal.json` 记录 `code.commit=4d559c4…`、`dirty=false`（**#99 的 4811 与可信终态声明已独立复现，非未核实**）
  - 该 run 的 13 份 JSON 齐备（a1/a2/a2-full/a3–a9 + 主证据 + `.pytest.json` + `.terminal.json`），与 `scripts/check-offline --help`「十一份主要文件…共十三份 JSON」一致
  - `a9.json`：`story_coverage.count=42`、`coverage_review` 含 21 决策/20 测试面/4 评论、`a9_verified=true`、`live_verified=false`、`stage_a_verified=false`、`rpc_verified=false`、`migration_revision=a704_screening_retry`、`contracts=[{name:read,version:v1,result:passed,schema_sha256:1ac0694…}]`；`tests/fixtures/a9_coverage.json` 实为 42 stories / 21 decisions / 20 testing / 4 comments
  - `scripts/a9_scope.py` 绑定 `tests/test_a9_scope.py` 但**不**绑定 `scripts/a9_scope.py` 自身（符合所有者批准的 self-reference 例外）；`REQUIRED_TEST_CASE_COUNTS` 合计 **541**，与 #99 所称 A9 固定范围一致
  - 契约冻结面：`contracts/read/read/v1/schema.json` `$id=urn:paper-radar:contracts:read:read:v1`、`ReadAnalysisOutput` 恰 18 字段、`value_types` 属性描述「精读分析允许返回的七类受控价值。」、`$defs.ValueType.description`「精读分析允许返回的七类受控价值。」（Read 自有措辞，非继承 Screening 文案）、`next_action` 无 description/无约束（仅字符串）
  - 文档/文案：`scripts/check-offline --help` 已改十一/十三份；`src/paper_radar/cli.py:92`「当前可选五份契约；A1 历史离线计划仍显式选择四份契约」；`_CHECK_ALL_EXAMPLE` 保持四份；`src/paper_radar/config/cli.py:30` 已改为「通过 `settings.contracts.read` 显式选择权威 read/v1；缺少选择时保留 `read_contract`」；`scripts/offline_evidence.py:217` 的 `_contract_metadata` 已改为 `build_selected_contract` + `snapshot_parts` 派生路径（原写死 `"screening"` area 已消除）；`tests/test_offline_evidence.py:247` 已改为显式四契约集合
  - 新增示例 `examples/config/settings-read-ready.yaml:2` 明确写出「旧 `settings-read.yaml` 保留历史字节；它未选择 `contracts.read`，因此仍缺 `read_contract`」，旧示例字节未改
- **未运行**：完整 `./scripts/check-offline`（约 20 分钟；由 run `6d02e607…` 的 `verification-status` 只读复核替代，未重跑）；全部 live（真实模型/Pi/Node/Docling/PDF/网络/凭据/NAS/常量 cwd）
- **缺失来源**：无。**两轴均声明「本轴完成」**，但覆盖面有下文明示的收缩

## Standards

### 工具与来源

可用：`bash`（只读 `git`/`rg`/`python3`/`pytest`/`ruff`/`mypy`）、`read`/`grep`/`find`/`ls`；无 `write`/`edit`，未改仓库、未建 commit、未改 Issue。固定点 `main`=`04ed707`，HEAD=`4d559c4`，`git diff main...HEAD`＝89 文件 +9437/−204 / 22 提交。实读：`AGENTS.md`、`docs/agents/{python-conventions,testing,documentation}.md`、`GLOSSARY.md`、`README.md`、`docs/contracts/{frozen-contracts,read-validation,runtime-config}.md`、`docs/verification/a9-scope-review.md`、`scripts/check-offline`。

实跑：`pytest -q tests/test_read_*.py tests/test_a9_*.py -p no:randomly` → **541 passed / 51.83s**；`ruff check src/paper_radar/reading tests/test_read_*.py tests/test_a9_*.py` → All checks passed；`mypy src/paper_radar/reading` → Success（10 source files）；`rg "import.*(config|llm|screening_tasks)" src/paper_radar/reading/` → 无命中；`contracts/read/read/v1/schema.json` 的 `$id` 核对通过。

未运行：完整 `./scripts/check-offline`（约 20 分钟）；全部 live。缺失来源：无。**本轴完成**，并明示覆盖收缩（见下）。

### 发现

**零发现**（0 硬违规 / 0 判断建议）。

已核对且未发现违规的具体点：

- **架构隔离**（`docs/agents/python-conventions.md`；A9-02 验收「不导入数据库、文件 I/O、网络、配置、LLM、ScreeningTasks 或 Docling」）：`src/paper_radar/reading/` 未导入 `config`/`llm`/`screening_tasks`/Docling，仅复用规格明确允许的 `screening.text` 文本规则。
- **异常语义分离**（裁决二-6）：`src/paper_radar/reading/errors.py:58` `ReadContextError` 与 `:69` `ReadOutputError` 各有独立语义与 docstring；`tests/test_read_context.py`、`tests/test_read_validation.py` 覆盖两条独立触发路径。
- **Read 自有价值词汇**（裁决一-11 / 最终方案 A）：`src/paper_radar/reading/value_types.py:8-18` 自持 7 个 wire 值，不 import `screening.ValueType`；`tests/test_read_contract.py:87-104` 以固定历史向量断言「冻结时刻与 Screening v1 相等」，不重建未来耦合。
- **规则版本身份**（裁决二-10）：`reading/context.py:25` `EVIDENCE_RULE_VERSION`、`reading/numbers.py:262` `NUMERIC_RULE_VERSION`，并在 `reading/validation.py:212-214` 写入结果。
- **文档同步**（`docs/agents/documentation.md`）：新公共契约同步到 `docs/contracts/read-validation.md`（449 行）、`README.md`、`docs/contracts/frozen-contracts.md`（SHA 表 `:130` 含 `read/v1`）。
- **工具门禁**：Ruff / mypy / 541 项 Read+A9 pytest 全绿，无一被基线 smell 掩盖的明显实例。

**覆盖收缩披露**：本轴未逐文件审完 89 份 diff，主要抽检 `src/paper_radar/reading/{validation,context,errors,numbers,value_types}.py`、`docs/contracts/read-validation.md`、`scripts/check-offline` 与既有测试架构；`scripts/a9_scope.py`(613)/`scripts/a9_acceptance.py`(571)/`tests/fixtures/a9_coverage.json`(826) 等大文件的内部结构未逐段核查。基线 smell 中 **possible Shotgun Surgery / Divergent Change** 需要跨 A1–A8 scope 文件比对，本轴未展开（`docs/verification/a9-scope-review.md` 已由另一路径审阅，见 Spec 轴）。`context.py`(360)/`numbers.py`(283)/`validation.py`(234) 的模块规模在可接受范围，未见单一职责明显违反。零发现不等于「已穷尽全部 89 文件」，只等于「已核查范围内未发现」。

## Spec

### 工具与来源

可用：`bash`（只读 `git`/`rg`/`sed`/`python3`/`pytest`）、`read`/`grep`/`find`/`ls`；无 `write`/`edit`/`gh`，未改仓库、Issue 或分支。规格：`/tmp/a9_spec.txt`（884 行，已完整读取），父票 #92 正文 + 4 条评论 + 子票 #93–#99。

实跑：`git diff main...HEAD --stat` → 89 files +9437/−204；`pytest -q tests/test_read_*.py tests/test_a9_*.py` → **541 passed / 48.83s**；只读核对 `$id`/`area=read`、`reading/value_types.py` 自持 7 值、`ExtractionIdentity` 三元组（`context.py:13-16`）、`ReadContextError`/`ReadOutputError` 分离（`errors.py:64,74`）、`NUMERIC_RULE_VERSION`（`numbers.py:9`）、`_check_read()` 显式调用 `check_frozen_contracts(("read",), "v1")`（`scripts/a9_acceptance.py:243-261`）、run `6d02e607…` 的 `stage_a_verified=False / live_verified=False / rpc_verified=False`、覆盖表（`docs/contracts/read-validation.md:420-488`）。

未运行：完整 `./scripts/check-offline`（约 20 分钟）；只读确认 run `6d02e607…` 的 13 份 JSON 与 `terminal.json` exit 0，未亲自重跑 `verification-status`（**聚合者已代为复核，见本文「聚合者独立复核」**）；未运行 live。**本轴完成**。

### 发现

**零发现**（0 缺失 / 0 部分 / 0 越界实现 / 0 实现错误 / 0 测试缺口）。

已核对且未发现偏差的具体点：

- **42 条 User Stories / 21 条 Implementation Decisions / 20 个 Testing Decisions / 4 条评论裁决** 全部在 `docs/contracts/read-validation.md:420-488` 覆盖表中映射到实现票，并分「已实现 / 目标能力 / 明确未验证」三列；`tests/fixtures/a9_coverage.json` 与 `a9.json` 的 `story_coverage.count=42`、`coverage_review` 一致（聚合者已复核）。
- **关键裁决逐条落地**：`area="read"`（`src/paper_radar/contracts/schema.py:84`、`schema.json` `$id`）；Read 自持 7 值（`reading/value_types.py:8-32`）；A5 三元组（`context.py:13-16`）；异常分离（`errors.py:64,74`）；数值规则 v1（`numbers.py:9`）；A9 显式 read 检查（`scripts/a9_acceptance.py:243-261`）。
- **明确未验证项如实保留**：`stage_a_verified`/`live_verified`/`rpc_verified` 恒 false；orig 哈希归属、真实 PDF/正文质量、map 来源链、Read StageInput/任务/预算、生产 Pi/模型/校准/NAS 均记为未验证，未被提升为「完整 Read」或「阶段 A 通过」。
- **范围收缩与默认执行项**：A9 非空恢复按评论五收缩为「配置快照 + `model_success_response` 原字节 + 测试常量重建上下文」；A9 scope 不哈希绑定自身但保留 self_reference/cycle 拒绝；`CONTRACT_NAMES` 六项检查计划与 A1 四契约范围保持不变。

**覆盖收缩披露**：本轴未亲自重跑完整门禁，也未逐格执行 `read-validation.md` 验收表的每个正反例（仅跑 541 项 Read+A9 子集，其分母与 `a9_scope.py` 固定值一致）。规格的「已实现」列取自覆盖表与代码静态核对，未对每格做独立反例注入；`scripts/a9_scope.py`/`scripts/a9_acceptance.py` 的内部反例逻辑未逐行审计。

## 汇总

- **Standards**：0 条发现（0 硬违规 / 0 判断建议）；最严重问题：无。
- **Spec**：0 条发现（0 缺失 / 0 越界 / 0 实现错误 / 0 测试缺口）；最严重问题：无。
- 两轴均声明完成、无缺失来源；共同未验证范围为完整 `./scripts/check-offline` 重跑与全部 live 行为，且两轴均明示了各自的文件覆盖收缩（未逐文件审完 89 份 diff、未逐格注入验收反例）。聚合者独立复核了 5 份冻结契约 check、run `6d02e607…` 的可信终态与 4811 测试声明、覆盖台账计数、`a9_scope` 计数与 self-reference 例外、以及六处文案/文档断言，均与 #99 声明一致。


## 本轮核实与处置（关联 #92、#94、#99）

核实基线为 `4d559c495b5158d5bd079e672a8fde6f540ba277`。本报告原文完整保留；
下表逐项说明其可核对结论的适用范围，不把零发现扩大为无缺陷保证。
原文 SHA-256：`313c9291a0ac4ea9470d1f856a7cddba80eb2a3a5dd51c730a9ec130fcaa463e`。

| 原报告结论 | 本轮判断及核实 |
| --- | --- |
| Standards：架构隔离 | 认可已核查范围；Reading 仍为纯消费/验证层，新增连字符修复没有引入 I/O 或 config/llm/screening_tasks 依赖。既有架构/隐私测试随 Read 回归通过。 |
| Standards：异常分离 | 认可；ReadContextError 与 ReadOutputError 仍为两个独立公共边界，本轮没有改变异常语义。 |
| Standards：Read 自有词汇 | 认可；权威 Read Schema 仍有7个自有 wire 值，不动态依赖 Screening 枚举。 |
| Standards：规则身份 | 认可；read-evidence-v1、read-numeric-v1 保持，当前修改是已规定连字符范围的漏检修复。 |
| Standards：文档同步 | 已列举的 Read Contract/README/Schema 登记事实成立；其抽检未覆盖 r1 S1 指出的离线证据文案遗漏。本轮采纳 r1 S1 修复，不以本报告零发现否定它。 |
| Standards：工具门禁 | 原报告的541项子集和静态检查是历史执行记录；本轮实际执行数值94项、全部Read436项。新增15项后旧541不再是当前A9预期。 |
| Spec：42/21/20/4覆盖台账 | 核实固定JSON仍对应42故事、21实现决定、20测试面和4条评论；本轮不改变这些规格计数。 |
| Spec：关键裁决 | 核实read的URN/area、18字段、7值、正文三元组、异常分离及writer显式Read检查；本轮不修改这些边界。 |
| Spec：未验证边界 | 认可；真实PDF/provenance、orig哈希归属、map来源链、生产Read/Pi/模型、Docling/NAS及完整阶段A仍未验证。 |
| Spec：恢复收缩及scope例外 | 认可；恢复仍只保存历史配置和原始成功候选，用固定测试常量重建上下文；A9 scope没有自身哈希绑定，self_reference/cycle保护继续保留。 |
| 聚合者：旧run/13份JSON/可信状态 | 已核实旧run `6d02e607ba2d40b78a694acf88e92187` 的4811 passed、13份JSON和A9通过仍是可信历史事实。加入报告/修复后适用性为different是工作树变化的预期结果，不改写原报告当时的same。新提交须另跑完整门禁。 |
| 聚合者：契约及示例 | 权威Read Schema的URN为urn:paper-radar:contracts:read:read:v1，18字段、7值及SHA 1ac06948024aab610c6b2c1098d0a53596632c940704d32fae860a03ed5d6111保持；旧四契约、示例和显式选择语义未改。 |
| 两轴零发现及覆盖收缩 | 接受其已披露的抽检范围和零发现记录；r1 F1有可重复的公共入口反例，足以证明该零发现不能排除连字符范围缺陷。本轮已采纳并修复F1。 |

本报告没有提出需执行或拒绝的具体修改建议；本轮没有虚构拒绝项。两轴未逐文件/
逐格穷尽审阅的限制继续保留。私有提示词和其他Agent的历史工具过程未在本轮重演，
不据此增加新的事实声明。实际新测试与scope审阅记录见r1追加处置及
`docs/verification/a9-scope-review.md`；完整门禁由最终提交的同次证据另行记录。


本轮提交前最终Read/A9组合556项实际通过，Ruff/format/mypy528文件通过；
独立scope收集审计exit0，数值预期94与实际一致，A9总556，旧组分母不变。
完整门禁仍须由根代理在最终提交上实际执行，不沿用旧run替代。
