# 阶段 A10 双轴审查 r2（#100 / #101–#108）

- 固定点：`main` = `4ec450fc43950ae96b8a8ed8acb29b641af5a7b3`（= `origin/main`）
- 被审：HEAD = `8f653711986266403a7b7e25c2d98a24c2ece896`（分支 `integration/a10-fixture-audit`）
- diff：`git diff main...HEAD`（三点，对 merge-base）＝ **169 files, +89882 / −211**；`git log main..HEAD --oneline` 共 **38 提交**（19 个 merge + 19 个功能/修复提交）
- 提交列表：`de1efb7`(#101) → `c08c385`/`295d21f`(#102) → `c501dd3`/`a0ce648`/`c193125`/`e67120d`(#103) → `052f79f`/`6043913`/`1b3e2ea`(#104) → `34bc2ec`/`a935a55`(#105) → `6ddd426`/`718407c`(#106) → `2a7bb75`(#107) → `ce10659`/`814ad37`(#108) → `97db787`/`3a38392`（审查清理）→ `8f65371`（merge），间以 19 个 merge
- 与 `intent/review/issue-100-a10-fixture-audit-review-r1.md` 的关系：该 r1 为**另一并行会话**在本次审阅进行中生成的文件（`07:47:38`，未跟踪，本 r2 未读取其结论作为输入、未修改该文件）。本文件是该分支的**第二次独立双轴审阅**，两轴报告独立生成，不继承 r1 的结论。
- 执行说明：按 skill 设计两轴应并行；本 harness 每轮只接受一次 `subagent` 调用（第二次在首轮被拒），因此实际按 **Standards → Spec** 顺序执行，两轴各自独立上下文、互不共享报告。两轴均使用 `oracle` 角色，**具备 `bash`**（满足「确保两个 subagent 均被赋予 bash 权限」）。
- 聚合者未修改任何代码、未创建 commit、未改 Issue 状态/标签。审阅开始时 `git status --porcelain` 为空；结束时仅新增未跟踪文件 r1（他人生成）与本 r2（本次要求）。

## 工具与来源（两轴共同）

- **规格来源**（按 `docs/agents/issue-tracker.md`，`gh` 只读）：`/tmp/a10-review/spec.txt`（1292 行，156 KB），由 `gh api repos/MeteoBoy4/PaperRadar/issues/{100..108}` 与 `/comments --paginate` 逐字落盘，含 **#100 正文＋6 条评论**（四项裁决、获取边界更正、接线补充、通道枚举裁决）与 **#101–#108 正文＋全部评论**（补充澄清、集成修复记录、完成报告）。优先级：后续 owner 评论 > 早先「建议默认」> #100 正文 > 子票正文 > 实现者完成报告（完成报告只作线索）。
- **Issue 图核对**（`gh api`，关系计数完整）：#100 `OPEN`、`assignees=[]`、`blockedBy` 4/4、`subIssues 8/8 completed`；#101–#108 全部 `CLOSED`（assignee `MeteoBoy4`）。
- **标准来源**（仓库无 `CODING_STANDARDS.md` / `CONTRIBUTING.md`）：`AGENTS.md`、`CLAUDE.md`、`docs/agents/{python-conventions,testing,invariants,llm-evidence,documentation,cli-output,scope,refactor,domain,calibration}.md`、`GLOSSARY.md`、`README.md`、`docs/adr/`（0011/0012/0027/0032/0033/0034）、`docs/contracts/{fixture-audit,artifact-store,backup-restore,verification-status,paper-facts,stage-inputs}.md`、`docs/verification/{offline-evidence,a10-requirements,a10-scope-review}.md`、`scripts/{check-offline,dev-environment,verification_status.py,a10_scope.py,a10_acceptance.py,a10_coverage.py}`、`pyproject.toml`，另加 skill 的 smell baseline（已在两轴提示词中全文粘贴，含增强要求与 800 词上限）。
- **两轴实际工具**：`read`/`grep`/`find`/`ls` + `bash`（只读 `git`/`rg`/`sed`/`python3`/`uv run --offline --locked`，临时库只建在 `/tmp`）。**无 `write`/`edit`/`gh` 写操作**，未改仓库、未建 commit、未改 Issue、未运行 live。
- **两轴均未运行**：完整 `./scripts/check-offline`（约 27 分钟，会写根目录 `verification-runs/`；提示词禁止，改由只读 `verification-status` + 聚合者核对替代）；全部 live（真实网络/模型/Pi/PDF 下载/Docling/NAS/凭据）。
- **缺失来源**：无。两轴均声明「本轴完成」，覆盖面收缩见各轴「未验证范围」。

## 聚合者独立验证（本轮实际执行，只读）

| 核对项 | 命令 | 结果 |
| --- | --- | --- |
| 固定点/差异 | `git rev-parse main`、`git diff main...HEAD --shortstat`、`git log main..HEAD --oneline \| wc -l` | `4ec450f…`；169 files +89882/−211；38 提交 |
| Issue 图 | `gh api repos/…/issues/{100..108}` | #100 OPEN / 4 blockers / 8 子票完成；#101–108 全 CLOSED |
| 冻结 run 终态 | `./scripts/verification-status aec731e203e54e11b712da6d65dabf96 --runs-dir verification-runs --json` | `passed/verified`、6/6、5251 collected/passed、0 failed/skipped/deselected、`exit_code=0`、`terminal.code={commit:8f65371,dirty:false}`、14 份 JSON 齐备；**`applicability=different`**（见下） |
| 适用性复算 | 按 `scripts/verification_identity.py::_worktree_sha256` 复算 `git ls-files -z --cached --others --exclude-standard` | 当前 `858833e…`；**排除未跟踪的 r1 审阅文件后 = `ac39bd7b…`，与 run 记录逐字相同**。故 `different` 仅由本次会话期间他人新增的未跟踪 r1 文件引起，代码身份（commit/dirty/被跟踪字节）与冻结 run 一致；本 r2 写入后会再次改变该哈希，属预期 |
| 包依赖环（S1） | 自写 AST 扫描 `src/paper_radar` 包级 import 边并求 SCC | HEAD：`backup ↔ fixture_audit` 环成立；**`main` 已有 `backup → papers → backup` 环**（`papers/cli.py` 同样 import `backup.cli_support`），且 `main` 的 `backup/cli_support.py` docstring 已是「备份与隔离恢复共用」→ S1 的「硬违规/边界失效」判据**有反证，标「未核实」并交 owner 裁决** |
| S-1 契约依据 | 读 `docs/contracts/fixture-audit.md:142`、`sampling_service.py:285-291`、`abstract_service.py:241` | 契约原文「继续前核对代码、parser、策略、选样/类别规则身份」；`continue_audit_sampling → advance(continuing=True)` 只比 `code_identity`/`sampling_rules_version`/`category_rules_version`；`resume` 走 `validate_execution_identity`（10 个版本槽）→ **契约槽位确有缺口** |
| 质量门禁抽样 | `uv run --offline --locked ruff check src/paper_radar/fixture_audit`；`mypy src/paper_radar/fixture_audit`；`pytest -q tests/test_fixture_{registry,cli}.py tests/test_audit_{replay,resume,sampling,sampling_feed_safety}.py -p no:randomly` | Ruff `All checks passed!`；mypy `Success: no issues found in 41 source files`；**43 passed / 25.63s** |
| 台账与迁移 | 读 `tests/fixtures/a10_coverage.json` 统计、`a1001_fixture_audit.py` | 693 需求＝550 covered / 7 superseded / 28 not_assessed / 108 operational；7 capabilities、12 条 `not_assessed`、12 条 extra 断言、79 条 behavior、`open_items=[]`、`owner_conflicts=[]`；`revision=a1001_fixture_audit`、`down_revision=a704_screening_retry` |
| 文案/产物 | `rg "十二\|十四" scripts/check-offline docs/verification/offline-evidence.md` | 「十二份主要文件…共十四份 JSON」一致；`.a10.json` 已登记 |

---

## Standards

> 以下为 Standards 轴子 agent 报告（轻整理：补正 S3 的 `Literal` 路径笔误 `abstract_rules.py:102 → sampling_rules.py:102`，其余保留原结论与排序）。

### 工具与来源

- 只读工具：`read`/`grep`/`find`/`ls` + `bash`（`git`/`rg`/`sed`/`python3`/`uv run --offline --locked`）。无 `write`/`edit`，未改仓库、未建 commit、未动 Issue、未运行 live；审阅前后 `git status --porcelain` 为空（r1 文件出现前）。
- 实读：`AGENTS.md`、`CLAUDE.md`、`docs/agents/{python-conventions,testing,invariants,documentation,cli-output,refactor,llm-evidence}.md`、`GLOSSARY.md`、`README.md`、`docs/adr/{0011,0033,0034}`、`docs/contracts/{fixture-audit,backup-restore}.md`、`docs/verification/{offline-evidence,a10-requirements,a10-scope-review}.md`、`pyproject.toml`、`scripts/{check-offline,verification_status.py,a10_scope.py,a10_acceptance.py}`、`src/paper_radar/fixture_audit/*.py`（8032 行）、`intent/review/issue-29-a3-full-review.md`。
- 实跑：`ruff check`（fixture_audit + 相关 tests + `scripts/a10_*`）→ All checks passed；`ruff format --check` → 44 files already formatted；`mypy src/paper_radar/fixture_audit` → Success（41 files）；`pytest -q tests/test_fixture_{registry,cli,pdf,recovery}.py tests/test_audit_http.py -p no:randomly` → **73 passed / 4.98s**；空 cwd 下 `fixture --help`/`audit --help` → exit 0、stderr 0 字节、未创建文件。
- 未运行：完整 `./scripts/check-offline`、全部 live。
- **本轴完成**。覆盖收缩：169 文件 / +89882 行的逐行复核集中在新增 `fixture_audit` 包、其测试与 `scripts/a10_*`；既有 scope 哈希表与 `tests/fixtures/a10_coverage.json`（69k 行）未逐条重算/整读（抽样与脚本统计）；文档只核对同步性。

### 发现

**S1｜硬违规（文档化规则）｜`fixture_audit` 与 `backup` 形成包级依赖环**（聚合者注：判据有反证，标「未核实」，交 owner 裁决）

- **影响**：新功能包反向依赖备份包；A3 审阅把这组 CLI 助手限定为「仅供备份/恢复使用」，现被第三个功能包复用，边界失效。运行期因 lazy import 未失败，P3。
- **位置**：`src/paper_radar/fixture_audit/cli.py:10`、`audit_cli.py:10`（`from paper_radar.backup.cli_support import ...`）；`src/paper_radar/backup/service.py:178`（函数内 `from paper_radar.fixture_audit import ...`）。
- **引用**：`docs/agents/refactor.md:5`「模块间无循环依赖」；`intent/review/issue-29-a3-full-review.md:89`「提取**仅供备份/恢复使用**的 `backup/cli_support.py`」。
- **已有测试核查**：结构问题，测试不适用；工具不检查该规则（ruff/mypy 通过不构成反驳）。已核对 `main` 亦存在 `backup↔papers`、`papers↔screening_tasks` 等 lazy 边，故属「新引入同类边」，非首次破例——请 owner 裁决。
- **复现**：`python3` AST 扫描 `src/paper_radar` 包级 import 边 → 输出 `CYCLE backup fixture_audit`（已执行）。
- **最小建议**：把 `BatchGroup`/`BatchCommand` 移入中性模块（如 `src/paper_radar/cli_support.py`），改 4 处 import 与 `scripts/a3_scope.py:125`、`scripts/a10_scope.py:391` 路径；成本中等（a3/a10 scope 哈希级联重绑，须出新 scope 审阅）。退路：把 docstring 改为中性表述，风险最低但不消除环。

**S2｜判断建议（Duplicated Code）｜三个审计 service 各自复制 `list_audits`/`show_audit`/`_raw`**

- **影响**：同一「只读事务读视图 + 未找到报错」「按执行 ID 读保留字节」形状出现 3–4 份；错误 `path` 字符串已有漂移（`sampling.material` / `abstract.material` / `data_root`），后续改动易只改一处。
- **位置**：`acquisition_service.py:77-95`、`sampling_service.py:69-105`、`abstract_service.py:65-97`、`interpretation_service.py:354-356`。
- **引用**：`docs/agents/refactor.md`「每个模块职责单一」；smell baseline Duplicated Code。
- **已有测试核查**：`tests/test_fixture_recovery.py`、`tests/test_audit_*` 断言具体 `path`（如 `EVIDENCE_REQUIRED, path="sampling.material"`），抽取必须逐字保参；已实跑子集 73 passed（聚合者另跑 43 passed）。
- **未验证限制**：维护性判断，无运行期反例（未复现缺陷）。
- **最小建议**：抽出 `read_material(store, execution, *, path)` 与 `load_view(loader, *, path)`（约 40 行），成本低、风险集中在错误路径字符串需保持不变。

**S3｜判断建议（Primitive Obsession / Repeated Switches）｜类别闭集字符串重复且该拒绝分支无测试**

- **影响**：`journal_article/non_journal_article/unknown/conflict` 在 `interpretation_service.py:48-53` 以裸字符串集合重列，与 `sampling_rules.py:102` 的 `Literal`、`sampling_models.py:66` 平行；新增或改名类别时漏改会把合法值降级为 `INVALID_REQUEST（audit.parser_output）`——且该分支被 `except Exception` 掩盖，难以察觉。
- **位置**：`src/paper_radar/fixture_audit/interpretation_service.py:45-54`（`field_value`；调用点在 `:388-394`）。
- **引用**：`docs/agents/python-conventions.md`「用明确的领域类型和受控 enum / reason 表达状态与原因」。
- **已有测试核查**：`tests/test_audit_reinterpret.py:27` 只覆盖合法值 `"unknown"`；`rg '"category": "' tests/` 无非法/新增值用例，`rg parser_output tests/` 无命中 → **无覆盖**（非覆盖不足）。
- **未验证限制**：无运行期缺陷，纯漂移风险；未复现。
- **最小建议**：复用 `sampling_rules.category_result` 的 `Literal`（`typing.get_args`）作为判定集合，并加一个「解析器返回表外类别 → `INVALID_REQUEST/audit.parser_output`」的负例测试（约 10 行，机械可执行）。

**S4｜判断建议（Mysterious Name / 隐式默认）｜`fixture list` 用 `Path(".")` 填充缺失的 `--data-root`**

- **影响**：`ArtifactStore(self.database, self.data_root or Path("."))` 把「未提供制品根」伪装成「当前目录」；当前 `verify_bytes=False` 不触达文件系统，但同一 store 上的 `get_artifact`/未来 `read_artifact` 会静默依赖 cwd。
- **位置**：`src/paper_radar/fixture_audit/service.py:411-414`。
- **引用**：`docs/contracts/fixture-audit.md`「省略只核验声明/引用」「查询不创建业务目录」；smell baseline Mysterious Name。
- **已有测试核查**：`tests/test_fixture_cli.py:14`（不带 `--data-root` 的 `list` 成功）与 `tests/test_fixture_cli.py:55` `test_fixture_help_has_no_business_side_effects`（cwd 无新文件）证明当前无副作用。
- **未验证限制**：**未复现**（当前无可触发路径）。
- **最小建议**：改为 `ArtifactStore | None`（`load_pdf_states` 已支持 `store=None`），或显式命名 `_unused_root`；约 5 行，风险低。

**S5｜判断建议（机械可执行检查）｜`FixtureReason` → `_GUIDANCE` 完整性无守卫**

- **影响**：`errors.py` 两张表当前 21/21 对齐（已脚本核对），但新增 reason 时 `_GUIDANCE[reason]` 会抛 `KeyError`（`errors.py:62`），以未受控异常取代受控错误与下一步指引。
- **位置**：`src/paper_radar/fixture_audit/errors.py:8-63`。
- **引用**：`docs/agents/cli-output.md`「错误信息写明具体原因和用户可采取的下一步」。
- **已有测试核查**：`rg "for reason in FixtureReason" tests/` 无命中；`_GUIDANCE` 无直接测试 → 无覆盖。
- **未验证限制**：未复现（当前无缺失项）。
- **最小建议**：加一个遍历 `FixtureReason` 断言 guidance 存在的测试，或 `__init__` 改 `_GUIDANCE.get(reason, "…请核对声明")`；约 10 行，机械。

**Standards 计数：硬违规 1（S1，聚合者复核后标「未核实/待 owner 裁决」）/ 判断建议 4（S2–S5）。**

### Standards 轴未验证范围

完整 `./scripts/check-offline`；全部 live；`tests/fixtures/a10_coverage.json` 仅抽样；`scripts/a*_scope.py` 哈希表按同模式抽样；Issue 裁决原文未由本轴直接读取（以 ADR/契约内嵌引用为准，聚合者已另行落盘核对）。

---

## Spec

> 以下为 Spec 轴子 agent 报告（保留原结论与排序）。聚合者在其后补入 `docs/contracts/fixture-audit.md:142` 的契约原文作为 S-1 的补充依据。

### 来源与工具

- 只读工具：`read`/`grep`/`find`/`ls` + `bash`（`git`/`rg`/`python3`/`uv run --offline --locked` 只读；临时库只建在 `/tmp`）。未改仓库、未建 commit、未动 Issue/标签、未运行 live。
- 规格：`/tmp/a10-review/spec.txt`（#100 正文＋6 评论、#101–#108 正文＋全部评论；评论优先）。仓库材料：`docs/verification/a10-requirements.md`、`docs/verification/a10-scope-review.md`、`docs/contracts/fixture-audit.md`、`intent/draft.md`、`GLOSSARY.md`、`fixtures/a10/historical-v1.json`、`tests/a10-recovery-coverage.md`。
- 独立核对：`gh api` 只读比对 `tests/fixtures/a10_coverage.json` 的 37 份来源原文 → **逐字一致 37/37、自哈希一致**；台账 693 项＝550 covered / 7 superseded / 28 not_assessed / 108 operational，`open_items=[]`、`owner_conflicts=[]`、12 项 extra 断言、79 项 behavior。
- 实跑：`pytest -q`（9 个 fixture/acquisition 文件）**110 passed/12.2s**；sampling+matrix 9 文件 **71 passed/86.0s**；resume/replay/reinterpret/processes 7 文件 **26 passed/48.1s**；a10 acceptance/behavior/coverage/entry/scope/status+references **81 passed/98.6s**；a10 integrity/isolation/reference/complete-recovery **126 passed/95.6s**；`./scripts/verification-status aec731e2… --json` → `passed/verified/applicability=same`、6/6、5251/5251、退出 0，`terminal.code={commit:8f65371,dirty:false}`、14 份 JSON 齐备、`a10.json` 的 `stage_a_verified/live_verified/rpc_verified=false`。空 cwd 下 `fixture --help`/`audit --help` → 退出 0、stderr 0 字节、未建目录/库。
- **本轴完成**；缺失来源：无。未运行完整 `./scripts/check-offline` 与任何 live。未验证：693 项台账「期望由规格独立编写」的**来源事实**（无法从运行结果反证）；`a10_coverage.json` 未逐行整读；A6 历史来源假设、四刊 live、渲染/授权/PDF/Docling/模型/NAS 按 NOT_ASSESSED 保留。

### 发现

**S-1｜部分（服务 API 层）｜选样级「显式继续」未核验全部冻结规则版本（P3）**

- **影响**：程序升级改变解析/HTTP 规则、但计划仍标记 `audit-parser-v1` 时，公共服务可在**不拒绝**的情况下用新规则续跑被暂停的期刊，并把 Feed 冻结记录写成旧 `parser_version`，形成「材料字节由 v2 规则解析、记录声明 v1」的混合证明。用户可见的 `audit resume` 路径已完整校验，故当前无用户可见故障；影响面为公共服务 API 的调用者与后续接入者。
- **位置**：`src/paper_radar/fixture_audit/service.py:694`（`FixtureAudit.continue_audit_sampling`）、`service.py:682`（`select_audit_samples`），二者只调用 `SamplingService.advance`；`sampling_service.py:283-290` 的推进前检查只比较 `code_identity`、`sampling_rules_version`、`category_rules_version`，未比较 `parser_version`/`http_rules_version`/`channels_version`/`ua_template_version`/`acquisition_strategy_version`（`AuditPlan` 已冻结这些字段，见 `acquisition_models.py:66-81`）。
- **需求/裁决引用**：#104 正文 AC「暂时性失败停住本刊游标…**恢复推进前核验计划代码/规则/策略身份，不一致拒绝**」；#100 评论二-5「resume 必须与计划的代码身份和规则版本一致，不一致时拒绝」（`#issuecomment-6395756759`）；#100 评论「`acquisition_strategy_version`…resume 拒绝不同策略版本」（`#issuecomment-6405695568`）；#106 评论「`commit + dirty=true` 不能区分同一提交后的不同工作树内容」（`#issuecomment-6411119180`）说明规则版本比较正是独立防线。
- **聚合者补充依据**：`docs/contracts/fixture-audit.md:142` 明确写「`continue_audit_sampling` 是显式联网写入继续……**继续前核对代码、parser、策略、选样/类别规则身份**，变化须新计划」——即该 API 的契约槽位本身包含 `parser` 与「策略」，缺口属契约文本未落地，而非仅「窄化语义未声明」。
- **已有测试核查**：`tests/test_audit_sampling.py::test_plan_freezes_sampling_rules_and_rejects_changed_execution_before_http`（`:166-188`）只 monkeypatch `CATEGORY_RULES_VERSION` 并断言 `plan_identity_mismatch` + 零 HTTP；`tests/test_audit_resume.py::test_resume_checks_full_execution_identity_before_any_mutation_or_http` 覆盖的是 `resume_audit`。台账 `behavior_catalog["sampling_execution_identity"].limits` 亦自述「代码身份不同/采样规则不同及策略不同的选样 continue 组合不能从该用例自动推断已独立断言」。**属覆盖不足**（不是测试失真：现有断言确实证明了它声明的那一槽）。
- **复现**（子 agent 实际运行，`/tmp/a10_version_probe2.py`，`uv run --offline --locked python`）：AIES Feed 连续两次 503 → `aies=blocked_pending, feed_unavailable`；随后把模块常量 `acquisition_models.PARSER_VERSION` 改为 `audit-parser-v2`（模拟升级、commit 不变）：
  - `resume_audit(...)` → `plan_identity_mismatch | code_identity`（正确拒绝）；
  - `continue_audit_sampling(...)` → **无拒绝**，四刊全 `complete`，HTTP 调用 11→15，`plan.parser_version` 仍为 `audit-parser-v1`，冻结 Feed 的 `parser_version` 也为 `audit-parser-v1`。
  合成 `code_identity`（`tests/audit_sampling_support.CODE`）与真实数据无关，脚本只写 `/tmp`。聚合者未重跑该探针，仅静态核对上述三处代码路径（`service.py:682/694`、`sampling_service.py:285-291`、`abstract_service.py:241`）确认槽位差异成立。
- **最小建议**：在 `continue_audit_sampling`（或 `advance(continuing=True)`）取锁、任何 I/O 之前调用已存在的 `resume_rules.validate_execution_identity(view.plan, code_identity)`（该函数已比较 10 个版本槽），并补一条 0-HTTP 回归用例（parametrize `PARSER_VERSION`/`HTTP_RULES_VERSION`）；若有意让该 API 只承担 sampling/category 级继续，则须在 Contract 改写窄化语义与理由，不能只在台账 `limits` 里披露。改动成本低、风险低（只前置一次只读比较）。

### 已核对未发现问题（摘要）

注册格式四用途/三依据、`(purpose, journal, key)` 身份与显式 `replaces` 当前项、同键同字节幂等/异字节拒绝、历史种子六 DOI＋JGR DOI/handle＋四刊版式且无假哈希/许可/parser 结果、a1001 单 revision（down=`a704_screening_retry`）、无 lockfile/依赖变化、无 playwright/selenium、五份 Frozen Contract 不变；四刊端点/query/current 限定、50 条与 N=5–10、每刊独立去重、三态台账、暂停续跑同成员；doiRA 路由与 `agency_unsupported/agency_unknown`（404 亦归 unknown）、类别闭集（Wiley 分节仅存原值）、主区块与前置/尾随剥离、5 类截断信号、逐字段 A6 仲裁与「高优先级疑似截断 vs 低优先级未截断」计数、`channel_not_installed`/`not_attempted` 分列、零分母不显示成功率；HTTP 两轮/每轮 30s 共用期限/10s connect/8 MiB 解压/5 跳/Retry-After>5s deferred/串行限速/无 Cookie 与环境凭据/邮箱不入库；`audit run/resume/list/show/replay`、无 `plan`、无 `reinterpret` CLI、中文帮助零 I/O；#107 feed 单刊/`abstract_audit` 四刊快照绑定、仅 complete 可登记、孤儿制品合法、`source_unavailable` 与损坏分离；#108 `.a10.json`、12/14 份文案、425 固定分母、A6 源码绑定、A2-01 仍 optional。

**Spec 发现总数：1（部分 1 / 缺失 0 / scope creep 0 / 实现错误 0）。**

### Spec 轴未验证范围

完整 `./scripts/check-offline` 未由本轴重跑（以只读 `verification-status` 复核替代）；全部 live；693 项台账「来源事实」与映射正确性抽样核对；`a10_coverage.json` 未逐行整读；scope 审阅过程真实性未独立重演。聚合者复跑 `verification-status` 得到 `applicability=different`，已按上表复算证明差异仅来自新增的未跟踪 r1 文件（排除后与 run 记录 `ac39bd7b…` 逐字相同），两轴原报的 `same` 在各自执行时点成立。

---

## 一行总结

- **Standards**：5 项发现（硬违规 1：S1；判断建议 4：S2–S5）；本轴最重 = **S1**（`fixture_audit` 与 `backup` 的包级依赖环，但聚合者复算显示 `main` 已有同型环、`papers/cli.py` 同样复用 `backup.cli_support`，故「硬违规」标「未核实」并交 owner 裁决）。
- **Spec**：1 项发现（部分：S-1）；本轴最重 = **S-1**（`continue_audit_sampling` 只校验 3 个版本槽，`docs/contracts/fixture-audit.md:142` 要求的 parser/策略校验在服务 API 层缺口；CLI `audit resume` 路径已完整校验，当前无用户可见故障）。

## 剩余风险与未验证范围

- 未重跑完整 `./scripts/check-offline`（约 27 分钟、写根目录 `verification-runs/`）；`#108` 的 `passed/verified/5251` 声明由冻结 run `aec731e2…` 的只读复核背书，`applicability` 现为 `different`（原因已复算：仅未跟踪的 r1 审阅文件；被跟踪内容与 run 身份一致）。
- 未运行任何 live：四刊真实来源、来源稳定/B 判据、渲染/授权/API/仓储运行时、PDF/Docling、真实模型/Pi RPC、校准/NAS、完整阶段 A 均按 `NOT_ASSESSED` 保留，本 r2 不改变其状态。
- `tests/fixtures/a10_coverage.json`（69,393 行）未逐行验证；693 项需求的映射正确性依赖登记自述 `review_state=reviewed`，聚合者只核对计数与结构。
- 两轴各自的 pytest/探针结果（73/110/71/26/81/126 等）为各轴自报，聚合者只独立复跑了 43 例抽样与 ruff/mypy，未重跑全部子集。
- 工作树现含他人生成的未跟踪 r1 与本 r2 文件；两者均未纳入 Git，未改任何代码或 commit。


## 本次逐项核实与处置（#100 follow-up）

原报告以上内容逐字保留；以下是实现者针对基线 `8f653711986266403a7b7e25c2d98a24c2ece896` 的独立核实。r1/r2重叠项合并实现，每个编号分别结论。公共测试seam沿用已批准的FixtureAudit、真实临时SQLite、ArtifactStore、backup/restore和HTTP替换边界；不引入live、新依赖、Frozen/A6/migration或已登记版本变化。范围与独立计数见 `docs/verification/a10-scope-review.md`，台账指针见 `tests/fixtures/a10_coverage.json`。

| 编号 | 性质与结论 | 证据、理由与改动/验证指针 |
| --- | --- | --- |
| Standards S1 | 拒绝“硬违规”认定与本次搬迁 | 粗包聚合图会把backup.service与backup.cli_support折成一个节点，不能证明真实模块环。`backup.cli_support`仅依赖manifest/restore_contract和Typer；这两个数据契约不回引backup.service或fixture_audit。`backup.__init__`公开函数在调用时延迟导入服务，CLI import不会执行它们。旧审查“仅供备份/恢复”是该次改动描述，不是当前规范；本次无真实模块循环证据，不以main同类边为豁免理由，也不通过改docstring假称消环。无需新增产品测试；既有禁I/O帮助与完整静态门禁继续验证。 |
| Standards S2 | 维护建议，采纳一致行为 | 与r1 F1/F3共同实现service_reads窄助手，保持三层各自loader/短写事务/原错误path，不将不同层查询提升成全层视图。`test_audit_sampling.py`、`test_fixture_audit_references.py`及恢复子集验证。 |
| Standards S3 | 维护风险与负例缺口成立，采纳 | sampling_models定义明确 `CategoryDecision`/`CategoryResult` alias，sampling_rules与interpretation共用；get_args针对真实alias，不读取future注解字符串。公共 `test_parser_category_outside_closed_table_is_controlled_and_atomic` 断言表外category→`invalid_request/audit.parser_output`、无部分解释、HTTP和原审计不变，并同request_key合法重交成功。原拒绝分支本已正确，此新增是行为守卫，不冒充修前失败bug。 |
| Standards S4 | 维护隐患成立，采纳动机；拒绝直接store=None跳验 | service不再构造cwd假根。`load_pdf_states` 无store时显式复用现有 `read_registration(Engine, id)` 只读登记核验，仍检查original_pdf/完整成员/SHA/长度，verify_bytes仍要求真实根。该函数另开只读事务，与原get_artifact相同，不扩storage公共API。扩既有 `test_declaration_check_and_local_pdf_integrity_are_independent`：坏blob仍能rootless查、validate_all缺根拒绝、坏登记受控拒绝且空cwd不生成文件。 |
| Standards S5 | 维护风险成立，采纳守卫；拒绝generic fallback | `test_every_declared_fixture_reason_has_chinese_actionable_guidance` 通过公共FixtureError遍历全部21已声明reason，断言reason/path及中文原因和行动信息；不镜像私有_GUIDANCE、不用fallback掩盖漏项。当前表原本完整，并非已存在KeyError缺陷。 |
| Spec S-1 | 契约缺口成立，采纳并修复 | `SamplingService.advance` 的局部三槽检查换成锁/写入/HTTP之前共用 `validate_execution_identity`，同时保护初次select与显式continue。22参数回归=代码身份+十槽版本×两个入口；continue先真实HTTP 503暂停Feed。每例断言 `plan_identity_mismatch/code_identity`、零新增HTTP、公共视图完全不变。修前20失败2通过：原三个静态比较确实存在，原采样/类别常量经from-import绑定副本，权威模块版本升级替身不能更新该副本，故这两槽也在该模拟下失败；不能据此声称原实现只检查一槽。修后22例全部通过。 |

本次已实际执行的验证（均 `uv run --offline --locked`、`-p no:randomly`、离线）：

- red：`pytest -q tests/test_audit_sampling.py -k full_execution` → **20 failed / 2 passed**（修前证据；预期失败）。
- green：`pytest -q tests/test_audit_sampling.py` → **25 passed**。
- 公共行为批次：`pytest -q tests/test_audit_sampling.py tests/test_audit_reinterpret.py tests/test_audit_replay.py tests/test_fixture_registry.py tests/test_fixture_pdf.py tests/test_fixture_audit_references.py` → **91 passed**。
- 恢复/HTTP批次：`pytest -q tests/test_fixture_pdf.py tests/test_fixture_recovery.py tests/test_fixture_pdf_recovery.py tests/test_audit_http.py tests/test_audit_sampling_recovery.py tests/test_audit_matrix_recovery.py tests/test_audit_resume.py` → **75 passed**。
- `ruff check .` → **All checks passed**；`mypy src/paper_radar/fixture_audit` → **42 source files通过**。

A10固定分母由425→448（37模块保持），旧scope计数不变；只读scope审计/收集不代替执行。最终门槛为代码、台账和本两份处置报告提交到当前分支且稳定后，重新实际运行 `./scripts/check-offline` 退出0，并以 `./scripts/verification-status <新run_id> --json` 复核 `passed/verified/applicability=same`。实际run_id和最终结果保存在忽略的verification-runs及工作树外 `/tmp/paperradar-a10-review-followup/result.md`，不在完成后回填本报告导致身份变化。此处不借用旧run 5251通过替代新门禁。

未运行/未授予资格：四刊live、来源长期稳定/B阻断判据、渲染/授权/API/仓储运行时、PDF/Docling、生产模型/Pi RPC、校准、NAS及完整阶段A；本次离线修复不改变这些NOT_ASSESSED边界。

提交前补充实跑：`pytest -q tests/test_a10_scope.py tests/test_a10_coverage.py tests/test_audit_matrix.py tests/test_audit_matrix_boundaries.py tests/test_audit_acquisition.py -p no:randomly` → **79 passed**；`./scripts/audit-verification-scope --collect --json` → **exit0 / collection=ok / issues=[] / affected_groups=[]**；正式配置 `uv run --offline --locked mypy` → **619 source files通过**；全树Ruff format/check通过。一次额外 `mypy .` 把Git忽略的旧verification-runs维护脚本纳入而失败（587 errors/10历史脚本），没有修改那些历史材料；正式门禁配置范围通过。
