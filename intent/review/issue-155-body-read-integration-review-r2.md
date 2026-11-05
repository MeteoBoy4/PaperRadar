# Body / Read 集成分支两轴审查（fixed point: main）

- **审查范围**：`git diff main...HEAD`；固定点 `main = c1a57f11c70521cd506bf8eba0145deef9d0cb60`，分支 `integration/body-155` 实际 HEAD = `6e15d1cdfea10353437c7394f5966fedf0017ea8`（26 个提交，175 文件，+21910/−279）。#165 回帖所称“最终冻结提交”为 `65a5c12`，其后的 `6e15d1c` 是本次 diff 内的 docs-only 提交。
- **Spec 来源**：GitHub Issues `#155`–`#165`（含正文与全部评论，用 `gh issue view --comments` 预取）、`intent/draft.md` §4.9/§4.10、`docs/roadmap.md`、ADR-0041–0045、牵连的 `docs/contracts/*`、`docs/verification/issue-155…165`。
- **Standards 来源**：`AGENTS.md`、`CLAUDE.md`、`docs/agents/{python-conventions,testing,documentation,invariants,llm-evidence,verification-scope,cli-output,domain,scope,calibration,refactor}.md`、`GLOSSARY.md`、牵连的 Contract/ADR，另加 Fowler smell 基线（skill 固定清单）。
- **方法**：Standards 与 Spec 各由一个独立只读子代理执行，两者均具备 `bash`（只读）并行运行；聚合者只做证据抽查、行号校正与分轴陈列，不跨轴合并或重排。两轴原始报告分别置于 `## Standards`、`## Spec`。
- **只读保证**：未修改工作树、未创建 commit、未运行 pytest / `scripts/check-offline` / 兼容组合，未访问 live 或外部网络。测试一律“未运行”；结论为静态审查。
- **完成状态**：两轴均已完成。Standards 为按风险定向抽样（未逐行阅读全部 175 文件）；Spec 覆盖全部目标票与高风险语义。未覆盖范围与缺失来源在各轴开头披露。
- **聚合者复核**：抽查了 Standards 发现 1/2/4/5/6/7/8 与 Spec 发现 1 的代码、契约和材料证据；Standards 发现 7 的行号已按实际文件校正（`models.py:29/47`），发现 1 追加一条复核注。其余未复核结论保持子代理原文并标注“未核实/未复现”。

---

## Standards

STDS_DONE 之前先给披露与发现。

**披露**

- 已读 47 个文件：`docs/agents/` 9（python-conventions、testing、documentation、invariants、llm-evidence、verification-scope、cli-output、domain、scope）、`docs/contracts/` 6（read-tasks 全文、read-validation 节选 228–250、read-inputs/body-persistence/docling-execution 关键行）、ADR 0041/0044/0045、`docs/verification/` 3（issue-165、issue-160、issue-164 检索）、`src/` 22（body/*、read_tasks/*、read_queries/*、read_inputs/*、stage_inputs/service、llm/calls+read_limits、docling_execution/{sandbox,deployment,process,models}、docling_executor、fulltext/{models,execution_audit}、storage/{schema,artifacts,artifact_repository}、eligibility/{models,presentation}）、`tests/` 12、`scripts/` 4（a3/a5/a9_scope、verification_scope_materials）+ 38 个 D1 模块函数计数。
- 抽样方式：按任务优先级读模块首尾与关键分支，配 `git diff main...HEAD` 定点核；未逐行读 175 文件。
- 未覆盖：`docling_execution/{sdk,worker,mapping}`、`fulltext/{artifacts,canonical,normalization,quality}`、`feed_metadata/*`、`reading/acceptance_v2` 340 行后、`backup/*`、`intent/draft.md`、ADR-0042/0043 正文、a9/a10 acceptance。
- 不可用来源：子代理未直接访问 GitHub（Issue 内容由主 agent 预取）；因此“裁决是否覆盖某处”只能凭 `docs/verification/` 台账。
- 测试运行状态：**未运行**；全部结论为静态推断或未复现。另注：任务描述把 `65a5c12` 标为 HEAD，实际分支 HEAD = `6e15d1c`（多 1 个 docs-only 提交）；`main...HEAD` 仍为 175 文件 +21910/−279，报告基于 `6e15d1c`。

**发现（按严重度）**

1. **文档化硬性违反（Contract 规则）+ Mysterious Name** — `AnalysisView.restricted_content_warning` 的判定规则只存在于代码：`any(d.get("reason") != "evidence_item_discarded" …)`（`src/paper_radar/read_queries/service.py:107-110`、`read_queries/models.py:46`）。`docs/contracts/read-tasks.md:144` 只把字段名列入清单，从未定义语义；而普通未支撑数值也会置真——`tests/test_read_acceptance_v2.py:228` 的 `("text", False, "得到 99 km。", ["number_not_supported"])` 是被接受分析，走 `_view` 时该字段为 True，与字段名“受限内容”不对应。影响：B/H 展示会把一般数值警告当受限内容告警；契约读者无法判断该字段。测试核查：`tests/test_read_queries.py:176-199` 只覆盖公式（`restricted_source_reference`）正例，**未找到** `number_not_supported` 的断言。标准：`docs/agents/documentation.md`「每项行为的详细规则只在所属 Contract 定义」。建议：在 read-tasks.md 定义该字段（或改名为 `unsupported_content_warning`），并补一条 `number_not_supported` 用例；改动 3 文件，风险低（公开 DTO 改名需同步 B/H）。
   - **聚合者复核注**：机制已核对属实（`read_tasks/validation.py:42` 将 `number_not_supported` 归入诊断；`read_queries/service.py:107-110` 只要存在非丢弃诊断即为 True）。但 `GLOSSARY.md:419`「降级诊断」的域是“数值**或**受限源内容”，因此“数值也置真”本身可能是有意行为；可确证的问题是字段名与 Contract 未定义语义，而不是数值纳入本身。风险表述应从“值错误”收窄为“命名/契约不清 + 缺数值用例”。

2. **可能 smell（Primitive Obsession + Data Clumps）** — 领取依据以 `dict[str, str | None]` 在 `BodyService.read_basis_in_connection`（`src/paper_radar/body/service.py:444-454`）与 `validate_read_basis_in_connection`（`:474-484`）之间传递，9 个键在生产者字面量与消费者 `keys` 集合各写一遍，同一形状再流入 `ReadAttempt.basis`（`read_tasks/models.py:70`）与 `basis_json`。影响：增删键必改两处，键名漂移只会在回放时以 `corrupt_reference` 出现。测试：`tests/test_read_tasks_recovery.py:250/315/323`、`tests/test_body_read_closure_integrity.py` 覆盖回放与损坏，但没有独立于两份字面量的键集断言。建议：抽 frozen dataclass `ReadBasis` 单点 `encode/decode`；约 60 行，风险低。

3. **可能 smell（受控 enum 退化为裸字符串）** — 已存在枚举却被字符串绕过：`body/service.py:516,536,552,582-584`（`"production"/"experiment"/"formal_gate"/"experiment_document_gate"`）、`read_tasks/service.py:627,630`、`read_queries/service.py:38,108`（`"evidence_item_discarded"`）；同类问题见 `docling_executor.py:24-40,137` 的 `DoclingPreflightError(reason: str)`（未校验闭集，未知 reason 落到通用指引），而仓库其它模块均为 StrEnum（`BodyReason/ReadReason/FulltextReason/BuildReason`）。影响：StrEnum 与 str 比较恒不报错，拼错即静默改变放行方向；预检 reason 未闭集。测试：`test_read_tasks_preconditions.py:236`、`test_read_queries.py:162`、`test_body_read_closure.py:40`、`test_docling_executor.py:31/173/318` 断言当前字面值，不防拼写回归。标准：`docs/agents/python-conventions.md`「用明确的领域类型和受控 enum / reason」。建议：改枚举比较 + 预检 reason 枚举化；改动极小。

4. **未复现缺陷风险** — `src/paper_radar/body/extraction.py:319-327` 的 `except FulltextError` 读取 `result.peak_memory_bytes`，而 `result` 仅在 `executor.convert` 成功后绑定；若 parser 在 `convert` 内抛 `FulltextError`（`CanonicalParser` Protocol 未禁止），结算分支抛 `UnboundLocalError`，尝试停留未结算，只能等 `reclaim` 记 `outcome_unknown`。测试：现有用例只经 `publish()` 触发该分支（`tests/test_body_extraction.py:147,169`），parser 侧仅抛 `ParserFailure`（`:194`），该路径**未覆盖**。建议：`result` 预置 None 或取 `getattr(result, "peak_memory_bytes", 0)`；改动 1 行。

5. **文档-代码不一致 + 重复常量** — `src/paper_radar/read_tasks/validation.py:102,107-108` 内联 `"read-evidence-v1"`、`"read-numeric-v1"`、`"none"`，而 `docs/contracts/read-validation.md:240-242` 明确 v1 常量为 `read-evidence-v1`/`read-numeric-v1`（定义在 `reading/context.py:11`、`reading/numbers.py:10`），且 v1 的 `limitation_rule_version="none"` 在任何 Contract 中**无定义**（仅 `tests/test_read_tasks_recovery.py:195` 隐含）。影响：v1 常量改名时历史分支静默漂移；“none”是未文档化的魔字符串。建议：导入 v1 常量；给该历史值在 Contract 增一行说明；不动列名（避免 migration），成本小。

6. **可能 smell（Duplicated Code）** — `body/repository.py:28-31,57-69` 与 `read_tasks/repository.py:21-26,44-64` 的 `digest/required/transaction` 形状几乎相同，错误类型不同，且 JSON 规范化**不一致**（前者 `json.dumps(sort_keys=True)` 含默认空格，后者 `separators=(",",":")` 紧凑）。影响：两套 request_hash 规范化并存，跨服务共用验证或迁移时易错配。测试：幂等/冲突用例各自成立（`test_body_facts.py:20`、`test_read_tasks_preconditions.py:148`），**未找到**跨模块一致性断言。建议：抽共享短事务/规范化模块，错误类型参数化；约 80 行重构，中低风险。

7. **可能 smell（重复字面量）** — `docling_execution/models.py:29` 定义 `WorkerWarning` 别名（`sdk.py:199` 在用），但 `WorkerResponse.warnings`（`models.py:47-48`）再手写同一 Literal，`max_length=2` 也是隐式耦合。影响：新增警告类型需改两处。测试缺口语义上还有：`formula_candidate_unavailable`/`table_source_unavailable` 全仓库**没有任何断言**（检索 tests 无命中），`ExtractionManifest.warnings: tuple[str, ...]`（`fulltext/models.py:69`）为开放串元组。建议：改用别名 `tuple[WorkerWarning, ...]`，并补一条映射层断言。

8. **可能 smell（Middle Man / 私有成员跨模块、隐式默认）** — `stage_inputs/service.py:405-428` 新增 `_set_read_facts` 只被 `ReadFacts.__init__` 调用一次，兄弟 `ExtractionFacts`（`:355-362`）直接内联 `object.__setattr__`；`read_tasks/preconditions.py:70` 用 `PaperProjection(paper_id, …).quality` 取默认值（等价 `QualityFact()`，且把无关的 `paper_id/version_id` 变成入参）；`read_tasks/{acceptance,validation}.py` 有 8 处访问 `service._owned/_now/_prepare`（main 分支 `screening_tasks` 无此先例）。影响：阅读成本与隐式默认依赖，私有边界名不副实。建议：内联 helper、直接用 `QualityFact()`、把这些成员改名为显式包内 API；改动小。

STDS_DONE findings=8 hard=1 judgement=7

---

## Spec

SPEC 轴审查完成。以下为报告。

---

**已读范围**：#155 正文 + 全部 11 条评论（含 7 条裁决链）、#156–#165 全部正文与评论、`intent/draft.md` §4.9/§4.10/§8.4/§11/§12、`docs/roadmap.md`、`GLOSSARY.md`、ADR-0041/0042/0043/0045（0044 经 Contract 交叉核对）、`docs/contracts/{read-validation,read-tasks,read-execution,read-inputs,body-persistence,docling-execution,fulltext-extraction,eligibility-visibility,backup-restore,artifact-store,config-projections,stage-inputs}.md`、`docs/verification/issue-15x/16x-*.md` 与 `issue-165-body-read-materials.json`、`src/paper_radar/{reading/acceptance_v2,body,read_tasks,read_inputs,read_queries,read_execution,docling_execution,fulltext,storage/schema,llm,backup}`、对应 38 个 D1 测试模块。
**抽样方式**：按父票 9 条高风险语义逐条走「裁决句 → 实现符号 → 测试名」三点核对；D1 节点数按 `def test_` 计数（203）+ parametrize 展开抽查（`test_read_query_config.py` 13、`test_read_tasks*` 5/6/5），未逐模块复算。
**未覆盖/不可用**：ADR-0044 全文、`issue-154.md`、全部 `docs/verification/a*-requirements` 历史材料未逐字读；**测试一律未运行**（禁 pytest/uv/门禁），故 376 节点、285 模块/5281 passed、"两次真实无 extra 冷恢复"、"16 页/216 源/139 evidence" 等实测数字仅做静态与材料一致性核对，不构成复现。审查固定点 `65a5c12` 与实际分支 HEAD `6e15d1c` 不同（见发现 1）。

## 文档-实现不符

**1｜门禁与材料身份绑定在 `65a5c12`，分支 HEAD 已前进到未登记的 live 文档**
- **影响**：唯一完整离线门禁的 `passed/verified/same` 只能归属 `65a5c12`；被审树（HEAD）含一份不在材料清单中的 live 文档，台账自身"HEAD/完整树变化均重新证明"的规则在当前树未满足。功能面无数值影响，属登记/结论适用范围问题。
- **位置**：`docs/verification/issue-165-body-read-closure.md:9-11`（"HEAD、目标或任何受身份约束材料变化均重新证明…最终 run_id 留树外"）；`docs/verification/issue-165-body-read-materials.json`（`identity_rule`="all live documents are protected by final HEAD/full worktree identity"，`material_count=133` 不含该路径）；新增文件 `docs/verification/issue-164-docling-supplement-2026jd047706.md`。
- **需求/裁决引用**：#165 AC「完整离线门禁…由唯一执行者于**最终冻结树**…成功必须为同次退出 0 和 passed/verified/same」；#164 评论 6/7 允许该补充报告提交，且评论 7 自述「当前新增文档提交的 applicability=different，不能沿用为新 HEAD 的 same 结论」——即实现者已披露，但台账与材料 JSON 未同步该限定。
- **已有测试核查**：不适用（登记/门禁事实，非公共行为）；材料侧核对 `material_count=133`、133 项全路径不含该文件；`git diff --name-status 65a5c12..HEAD` 仅该 1 个新增文件（+179 行）。
- **复现/限制**：`git rev-parse HEAD`=`6e15d1c`，`git diff --stat 65a5c12..HEAD`=1 file/179 insertions；门禁**未运行**（禁运行），因此只断言"结论不可外推到 HEAD"，不断言任何检查失败。
- **最小建议**：二选一并写入台账与材料 JSON：①把该文档并入材料清单、把冻结身份改到 HEAD 并重跑门禁；②成本更低——在 `issue-165-body-read-closure.md` 与材料 JSON 明写"门禁适用树=`65a5c12`/完整树 `6142604b…`；其后的 docs-only 提交按 applicability=different 单列，不宣称最终树 passed"。

## 已核对且与裁决一致的条目（无发现）

- **Read v2 接收**：非末次任意指针错误整份 `output_invalid`、末次仅丢弃三类列表项、两项评分理由任何尝试整份拒绝、全空下限（`had_subject_content`）、Schema `min_length`/空串 ID 不降级、`unknown_source` 归上下文、`evidence_not_allowed` 仅 reduce —— 见 `acceptance_v2/__init__.py:441-520`、`_pointers`、`_whole_candidate_issues`；测试 `test_read_acceptance_v2.py` 20 条含 `test_final_attempt_discards_whole_item_and_preserves_other_content`、`test_score_reason_bad_pointer_always_rejects`、`test_drop_cannot_hide_bad_text_or_schema`、`test_reduce_not_allowed_discards_with_resolvable_safe_positions`。
- **ordinal 闭集与不可伪造**：`{1,2}`、`degrade_policy` 闭集、`submit` 从持久 attempt 行取 ordinal（`acceptance.py:66-70`）、候选自带字段按额外字段拒绝（`test_read_tasks.py::test_candidate_cannot_supply_attempt_identity_as_extra_json_field`）。
- **持久任务**：预算键 `(paper_id,"read",fingerprint)` 唯一约束、每代两次、`read_analyses.task_id UNIQUE` 唯一成功、`outcome_unknown` 与租约到期均不退款、显式 `reclaim` 才结算、retry 仅失败终态建唯一后继且重复同边幂等、预检失败不建预算/attempt —— `service.py:150-360`、`schema.py:316-465`；测试 `test_read_tasks_leases.py` 6 条、`test_read_tasks_preconditions.py::test_a_b_a_…`、`::test_real_complete_frame_over_budget_rejected_without_task_or_attempt`。
- **Read 输入**：facts 仅三元组+语言（`stage_inputs/service.py` `ReadFacts`）、坏指针拒绝、`read_input_over_budget` 为纯返回原因、最坏修正槽 83,968 与 `SINGLE_FRAME_BYTES=262144` 一致、三规则版本不入指纹（`config-projections.md` Read 语义映射、`build_call` 只含 `READ_RENDER_VERSION`）。
- **只读查询**：正文轴/配置轴分离、`unknown ≠ old`、`rowid` 提交序取最新、幂等重放不刷新、`transaction(write=False)` READ_ONLY、零写/不回收/不耗预算（`test_read_query_readonly.py`、`test_read_query_config.py::test_unknown_reference_never_enters_old_list`）。
- **Body 前置事实**：根用途仅 SQLite 且 hash 校验不可变、人工决定只 append + sequence 唯一/并列拒绝、样本只追加、PDF 当前选择事件流、质量两层且人工否决永久（`layout_conflict`）、`formal_gate` 无生产者、`ExecutionSource` 取决定引用历史成功且任一 test→test、无引用 unknown。
- **Docling 执行**：probe → 逐文件 SHA → 取锁 → 复核 → 领取（`extract`/`DoclingParser.preflight`）、`start_new_session` + `killpg`、`RLIMIT_AS`、`wait4 ru_maxrss`、`HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE`、doctor 未改、失败白名单 fail-closed 到 `executor_error`。
- **制品/恢复**：四角色不变、evidence-map 承载 orig 并被 `evidence_map_sha256` 覆盖、`unsupported_rule_version` 与 `registration_invalid` 分离、v1 分析按 v1 重放（`replay_analysis`）。
- **迁移/收口**：feed07→body01→body02 两节点线性、旧 migration 仅新增、head 常量/10 scope/A3/两份 Contract 同步 `body02_read_tasks`、五次已批准 A5 变更落实、A9 冻结面零字节差。
- **#164 分支结论**：三分类（display/inline/unknown）、零样本写"未覆盖"、仅工程 smoke、不冒充四刊/现场。

`SPEC_DONE findings=1 missing=0 partial=0 creep=0 wrong=0`（findings 计为「文档-实现不符 1」，不计入 missing/partial/creep/wrong 四类）

---

## 汇总

- **Standards：8 项发现（硬性 1 / 判断 7）**，本轴最严重者为 `restricted_content_warning` 契约未定义语义且数值诊断也置真（已复核：可确证的是命名/契约不清与缺数值用例）。
- **Spec：1 项发现（文档-实现不符）**，本轴最严重者为完整门禁结论仍绑定 `65a5c12`，而分支 HEAD `6e15d1c` 新增的 live 文档未进入材料清单、台账未标注 applicability=different。

两轴保持独立，不做跨轴排序。测试、完整门禁与 live 均**未运行**；Spec 轴核对到的“与裁决一致”条目为静态核对，不构成验收结论。


---

## 后续逐条核实、勘误与处置（#155 整改；与原静态审查分开）

以上为用户提供的原报告，原字节前缀保留。以下是本轮唯一 fresh implementer 的独立核实，
不把报告优先级当作已复现事实。实施基线为
`6e15d1cdfea10353437c7394f5966fedf0017ea8`；逐项 source/Contract 依据、测试节点、
红绿实测和材料 SHA 详见[独立增量台账](../../docs/verification/issue-155-review-remediation.md)。

| 原发现与子建议 | 处置 | 依据与验证 | 剩余风险 |
| --- | --- | --- | --- |
| Standards 1：Contract/名称/数值用例 | 部分采纳 | 明确兼容字段指所有非丢弃程序降级诊断；GLOSSARY 的域含数值，数值置真不是已证实值错误。采纳契约与 numeric/discard-only/model-only 三对照测试；拒绝 DTO 改名及擅改警告政策。 | B/H 仍须正确显著展示；字段兼容名保留。 |
| Standards 2：九键/codec/独立键集断言 | 采纳 | 内部 frozen ReadBasis 统一 encode/decode；公开 basis 字典与原 JSON 编码保持。新五节点按人工九键预期验证领取、缺/多键、bool/int 拒绝及历史字节不改；原历史回放与恢复组合见台账。 | 字段仍保持原 str 或 None 接受形状，资格语义继续由历史引用核验。 |
| Standards 3：枚举比较 | 采纳并校正命名 | 使用 RootPurpose/QualityBasis/ExecutionSource 与实际诊断枚举 ReadV2DiagnosticReason；原文所称 ReadIssue 本身是 dataclass。普通消费、用途和查询分支由相关组合验证。 | 不改变旧序列化值或历史等值比较。 |
| Standards 3：DoclingPreflightError 闭集 | 采纳 | 实际五类 dependency/platform 失败、selection_invalid、runtime_selection_invalid、model_deployment_invalid 保持值；参数仍由 Pydantic 拒绝。新八合法原因与一未知拒绝测试，外加原公共预检无领取组合。 | 未知直接构造安全拒绝而不回显；SDK/native/模型初始化仍在领取后按 executor_error 结算。 |
| Standards 4：未赋值 result | 采纳真实 Bug | 新 BodyService.extract 回归先 RED：UnboundLocalError；预置峰值 0、convert 返回立即保存峰值后 GREEN。另补 publish 拒绝保留 4096 峰值、永久结算和已花预算。拒绝只写 getattr(result,...)，那仍会访问未绑定变量。 | 0 表示没有测量，不表示零内存。 |
| Standards 5：v1 常量/none 文档 | 采纳 | 只读导入冻结 v1 两常量，Contract 定义 limitation_rule_version="none" 历史含义；既有 `test_synthetic_v1_history_replays_using_frozen_v1_acceptance` 与恢复组合验证。 | 原 v1 源码、规则值、存储形状和 Schema 不改，无 migration。 |
| Standards 6：digest 统一/跨服务相等测试 | 拒绝 | 核实 Body 默认 JSON 空格、Read 紧凑 JSON 已各自参与持久 request_hash；两服务没有共用请求或哈希相等需求。统一会破坏旧幂等，跨模块相等断言无规格依据。两 repository 原字节保留，现有幂等/冲突/恢复组合验证。 | 两种历史编码有意保留，未来共用请求需独立版本决策。 |
| Standards 6：required/短事务泛型抽取 | 拒绝 | 代码短且错误边界独立，抽错误工厂参数化增加耦合；ADR-0045 已选独立 Read 内核。相关事务原子性、租约与恢复组合见台账。 | 不承诺未来跨服务内核；没有为表面相似扩大公共 API。 |
| Standards 7：WorkerWarning alias/max_length | 采纳 alias，保留边界 | warnings 使用 tuple[WorkerWarning,...]；max_length=2 仍是显式旧协议上界，新 too_long/literal_error 负例验证。 | 新增警告类别时须另行审阅数量限制，不能自动扩大。 |
| Standards 7：两警告测试缺口 | 采纳 | 新四节点用真实 SDK 数据/选项与真实 mapping，在外部 DocumentConverter/backend 边界注入替身，精确断言 formula_candidate_unavailable/table_source_unavailable、并发缺失及均不缺失；回包往返验证。 | 没有真实模型或 PDF，不是 smoke 或真实保真证明。 |
| Standards 7：ExtractionManifest 收紧 | 拒绝 | manifest 警告承载历史/其它 CanonicalParser，不能被当前 worker Literal 追溯约束；保留开放 tuple[str,...] 和旧 manifest 字节兼容组合。 | 历史警告并不因此获得当前 worker 协议资格。 |
| Standards 8：_set_read_facts 内联 | 拒绝并勘误 | 实际在 ReadFacts.__init__ 与 `_replay_facts` 历史 replay 调用两次，原文“一次”前提错误；保留共享 hash/语言校验，stage_inputs/service.py 原字节不改。 | 不为机械内联复制冻结输入校验。 |
| Standards 8：QualityFact 默认 | 采纳 | 直接 QualityFact() 代替构造无关 PaperProjection 取默认；既有缺前置/质量测试验证。 | 默认 absent 语义不变。 |
| Standards 8：私有成员改显式包内 API | 拒绝 | acceptance/validation 是同包 ReadTasks 内部实现；_owned/_now/_prepare 分别保护凭据租约、严格时钟、历史重建，没有独立公开需求。为改名新增 API 或拆回大类不改善边界。 | Python 下划线是内部约定；继续用公共 seam 验证所有权、接收和恢复。 |
| Spec 1：6e15d1c 补充文档/旧门禁台账 | 范围排除 | 用户明确忽略最后补充性文档提交。不改已发布 #165/133 项 JSON；原门禁只属于65a5c12，当前树未取得新 same。原文称新增文档为 live 也不是分类依据，未知文档按固定材料。 | 不复用旧门禁为新树结论；本轮未重验补充 smoke，也未运行完整门禁。 |

所有实际子集计数/耗时、静态和 scope 结果在独立台账逐项列出，不拼接不同运行成
完整门禁。R1 Spec 缺失保持缺失；本附录不宣称两轮 Spec 全面通过。
