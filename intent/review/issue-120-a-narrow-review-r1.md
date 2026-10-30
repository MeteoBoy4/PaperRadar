# Issue #120 A 窄收口双轴审查与统一修复 R1

审查起点：`3439453efce1a0afcc164589fe4b9a8981d2f7cd`；审查冻结集成候选：
`6d0f0c86b111df916edd2017e2b4a65dfcc24d43`。唯一全新修复 implementer 在
`fix/120-review-findings` 独立工作树实施；未修改 main、其他工作树或 Issue，未 push/PR，
未启动子代理。以下原始双轴报告完整保留；修复结果单列，不改变两轴的严重度与判断性质。

## 原始完整审查

# Issue #120 双轴代码审查

固定点：3439453efce1a0afcc164589fe4b9a8981d2f7cd；候选：6d0f0c86b111df916edd2017e2b4a65dfcc24d43。

## Standards

Standards：2 项 finding（1 项明确规范违反，1 项 smell 判断），均为 P3；未发现阻断性问题。

范围：只读审查 `3439453efce1a0afcc164589fe4b9a8981d2f7cd...6d0f0c86b111df916edd2017e2b4a65dfcc24d43`，差异命令 `git diff 3439453efce1a0afcc164589fe4b9a8981d2f7cd...HEAD`，覆盖 69 个变更文件。不包含 Spec 轴结论，未读取其他审查报告；b04c8d5 的用户既有 roadmap 编辑不列为实现问题。

1. **[P3，明确规范违反] applicability 应使用封闭领域类型。**
   文件：`src/paper_radar/eligibility/models.py:130`，同类位置 `:151`、`:204`。
   规则：`docs/agents/python-conventions.md:8`：“用明确的领域类型和受控 enum / reason 表达状态与原因。”
   新增 hunk 为 `applicability: str = "undeterminable"` / `applicability: str`，把已有三态词表放宽为任意字符串；A7 的 `SuccessView.applicability` 已使用封闭 Literal。
   复现：对身份合法的合成 PaperProjection，设置 `screening=ArtifactFact(Presence.PRESENT, "synthetic-reference", "v1", "curent")`；构造成功，求值返回 `screening_unknown`。影响：装配代码的拼写错误无法由现有字段类型发现，会伪装为真实适用性未知。建议三个字段统一使用封闭 Literal 或领域 enum；不要求纯规则承担外部解析职责。这是编码标准问题，不主张它已造成有效输入下的资格绕过。

2. **[P3，判断：possible Duplicated Code] 制品存在性检查重复。**
   文件：`src/paper_radar/eligibility/rules.py:94` 与 `:335`。
   baseline 原文：“the same logic shape appears in more than one hunk or file in the change.”
   两处 hunk 都是 `presence is not Presence.PRESENT and (...)`，检查 `reference`、`version_id`、`applicability != "undeterminable"`，再分 ABSENT/UNKNOWN。
   触发：输入 absent/unknown 但携带制品引用时，两路执行同构矛盾检查；以后调整这项共享一致性条件须双点修改，存在维护漂移风险。建议只抽取共同检查，保留 Screening/PDF 各自原因及当前性差异。此项是维护判断，没有认定现有资格结果错误。

验证：`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 UV_CACHE_DIR=/tmp/paperradar-issue-120/reviewer-uv-cache uv run --offline --locked --no-sync pytest -q -p no:cacheprovider --basetemp=/tmp/paperradar-issue-120/standards-pytest tests/test_eligibility.py tests/test_runtime_logging_files.py tests/test_doctor_readonly.py`：**62 passed，0.95s**。另用同一 uv 模式运行纯合成 applicability 拼写复现，通过断言。文件/数据库测试事实仅位于指定 `/tmp` 测试根；未改仓库，结束时工作树干净。

未运行完整门禁或 live；真实 Pi/RPC、cwd 隔离、外部来源、Docling、正式校准、NAS 及真实消费者接线均未验证。

## Spec

仅 Spec 轴；2 项 finding：1 项硬违反、1 项接口覆盖判断，均为 P2。审查 `3439453efce1a0afcc164589fe4b9a8981d2f7cd...6d0f0c86b111df916edd2017e2b4a65dfcc24d43` 的 69 文件差异。以下代码路径相对 `/home/meteoboy4/Projects/PaperRadar/.scratch/issue-120/integration`。

1. **[P2][硬违反；实现错误／额外限制] 人工精读请求错误要求既有 accepted 来自人工。** 定位：`src/paper_radar/eligibility/rules.py:184–187`；关联新 Contract `docs/contracts/eligibility-visibility.md:133`。规格 `intent/draft.md:758` 原文：“已经 accepted 的论文只新增精读请求。”触发：当前系统 accepted、当前 Screening、gate enabled、正文等前置全部满足，加入引用该生效决定的人工请求。`effective_screening_decision` 和自动 Read 前置均通过，`requested_manual_read` 却返回 `manual_decision_required`。影响：合法请求无法取得共享资格，消费方若为通过而追加人工 accepted，又违背“只新增精读请求”。应接受已生效的系统 accepted，无须另造人工决定；现有同名负例测试与新 Contract 固化了此错误。

2. **[P2][判断；需求部分覆盖] 缺少不以人工请求为条件的实验单篇 Read 前置结果。** 定位：`src/paper_radar/eligibility/rules.py:166–172`（结果出口 `:207–217`）。D4 原文（`/tmp/paperradar-issue-120/comment-1.md:50`）：“`experiment` + 逐文档门槛通过且其余前置满足 → 可读”；ADR-0036 `:24`：“实验为显式单篇执行，不扫描自动队列；只有显式人工精读请求不占自动 Read 名额”。触发：人工 accepted、production 执行来源、实验根、document gate 通过、其余正文前置齐全，但无人工请求。两个公开 Read 结果均拒绝，原因分别为 `experiment_no_auto_queue`、`manual_request_absent`。接口因而无法表达这种单篇执行的前置资格；消费方须复制规则或额外造请求。建议暴露共享 Read 前置判定，继续单独拒绝实验自动队列；本项不要求新增队列或执行器。判为覆盖缺口是对 D4 与 ADR 联读的判断，区别于第 1 项直接文字冲突。

验证：`uv run --offline --locked pytest` 对 eligibility、visibility、doctor readonly、runtime logging audit/tasks/files、A narrow composition 七个模块执行相关子集，**102 passed**；全部合成材料位于 `/tmp`。另以相同离线入口运行 `/tmp/paperradar-issue-120/review_spec_probes.py`，**2 failed**，分别复现上述结果；使用 `PYTHONDONTWRITEBYTECODE=1`、`-p no:cacheprovider` 与 `/tmp` basetemp/cache。

仓库未修改，HEAD 未变，工作树干净。未读取 Standards 报告，未运行完整门禁或 live。未将 b04c8d5 用户既有变动、候选 roadmap 状态或审查后才启动的最终 gate 作为缺陷。未证明 Pi/Live/Cwd、四刊审计、Docling、正式校准或 NAS 行为；完整 A 仍未通过。

Standards：2项，轴内最高P3（1规范违反、1smell判断）；Spec：2项，轴内最高P2（1硬违反、1接口覆盖判断）。四项统一交单一新实现代理修复，不在轴间合并或重排。


## 逐项修复结果

| 轴／发现 | 结果与最小改动 | 公共证据 |
| --- | --- | --- |
| Standards S1，P3，明确违反：applicability 自由 str | 已修复。将 A7 SuccessView 原有 Literal 三态命名为 `Applicability`；ArtifactFact、ExtractionFact、DecisionFact 复用同一类型。无新词表或运行时解析器；通过 TYPE_CHECKING 保持纯规则依赖方向。 | `test_applicability_fields_share_a7_closed_vocabulary` 先红后绿；审查原 `curent` 合成触发在三个公共构造器均得到 mypy `arg-type`。 |
| Standards S2，P3，重复代码判断 | 已修复。只提取 `_artifact_presence_contradictory`：非 PRESENT 却携带 reference/version/applicability 的共同矛盾条件。Screening/PDF 的 absent/unknown、原因、历史和版本判断各自保留；未合并质量或提取规则。 | `test_absent_and_unknown_artifact_references_are_consistently_rejected` 覆盖两个入口、两种存在性与四类引用；抽取前后均通过。隔离副本禁用共同检查时公共回归失败。此项原来没有行为错误，不伪称原实现会出现功能红灯。 |
| Spec P1，P2，硬违反：系统 accepted 人工请求 | 已修复。请求要求当前生效 accepted，不再要求决定必须来自人工。去掉额外来源限制及错误原因 `manual_decision_required`；修正原独立模块错误预期。系统决定仍须当前依据、当前制品、enabled 和许可才能生效。 | `test_current_system_accepted_only_needs_a_request` 使用报告真实合成触发，原来返回 manual_decision_required，修后通过且 decisions 不变。门禁四态、旧/未知系统依据、交叉引用、后来人工 denied、请求身份与替换依据均有受控拒绝。 |
| Spec P2，P2，接口覆盖判断：实验无请求的单篇 Read | 已修复。增加 `Concept.READ_PREREQUISITES`，由已有 `evaluate_paper/evaluate_concept` 返回，不新增调用方算法。结果直接使用已有共同 Read 前置，partial scope 明确不包含排名、名额、领取、预算。 | `test_experiment_single_read_prerequisites_do_not_require_a_request` 先红后绿：人工 accepted、production 来源、实验根、document gate、其余前置齐全且无请求时为 true；自动结果仍 experiment_no_auto_queue，人工请求结果仍 manual_request_absent。 |

全部新增公共回归位于 [test_eligibility_review.py](../../tests/test_eligibility_review.py)，
未纳入历史 required 集合。原 [test_eligibility.py](../../tests/test_eligibility.py) 仅修正一个
既有错误预期/名称与 helper 类型，50 个节点的独立模块分母不变；历史固定测试模块未修改。

## 语义复核

- `manual_request` 是请求存在性事实；`requested_manual_read` 是请求连同 Read 前置的结果。
  请求不能替代 accepted、不能把旧系统建议变为当前，也不能放行门禁 paused/disabled/unknown。
- 当前 pending/denied（人工或系统）即使携带请求仍返回 decision_not_accepted。纯规则不
  自动追加事件；调用方须同事务先追加人工 accepted，再创建请求，失败均不提交。
- 人工 accepted 的 current/historical/undeterminable 依据 × 门禁四态 × 生产/实验根组合均
  不依赖系统自动门禁。后来的人工 denied 仍优先于旧系统 accepted，旧请求保留但无资格。
- 通用 Read 前置不依赖请求存在，坏请求不污染通用前置或自动结果。无请求实验路径仍检查
  最低元数据、当前 PDF/成功提取、质量依据、根用途、执行来源和共享 visibility。
- 生产根仍拒绝 experiment_document_gate；test/unknown 执行来源仍拒绝；质量 failed、absent、
  unknown 和引用矛盾仍拒绝。单篇结果与按概念批量结果一致，既有全概念排列测试覆盖新概念。
- 实验单篇前置通过不授予普通生产消费资格，不授予人工请求的名额豁免；预算、串行资源、
  租约、已成功分析与重跑许可由消费者事务复核。没有新持久化表或调度器，ADR-0036 隔离不变。

当前公共语义已同步到 [共享 Contract](../../docs/contracts/eligibility-visibility.md)、
[README](../../README.md) 与 [覆盖台账](../../docs/verification/a-narrow-delivery.md)。
长期 Contract 只描述现状，不保存本轮票级过程；规格/ADR 无需求变化，不改其原文。

## 验证与材料绑定

所有 Python 入口使用 `uv run --offline --locked`；合成事实与临时数据库位于 `/tmp`。

- 冻结基线：分支/HEAD/工作树干净及 integration 祖先核对通过；eligibility + A 组合 `58 passed`。
  基线只读 scope 审计 exit_code=0、issues=[]。
- TDD 原始日志：`fixes-red-system.log`（1 failed）、`fixes-green-system.log`（51 passed）；
  `fixes-red-experiment.log`（新概念缺失，1 failed/1 passed）、`fixes-green-experiment.log`
  （60 passed）；`fixes-red-type.log`（1 failed/2 passed）、`fixes-green-type.log`（53 passed）。
  重复条件抽取前后各 `19 passed`；`fixes-dedup-sensitivity.log` 为隔离副本预期的 1 failed。
  `fixes-type-probe.log` 为三次预期的 arg-type 拒绝；不将预期负例当成通过的类型检查。
- 相关 pytest：eligibility（原、新、架构）、visibility（行为、架构）、A 组合、A7 boundary/value
  成功/完整性/适用性/查询、A9/A10 scope，共 `231 passed`。
- 触发的兼容组合 `./scripts/check-compatibility all`：`176 passed in 291.11s`，入口退出码 0；
  覆盖验收绑定与公共导入兼容，不是完整门禁。
- Ruff check、Ruff format --check 全仓通过；mypy 全仓 `687 source files` 通过。
- 完成前已执行 `git merge integration/a-narrow-120`，结果 Already up to date；最新 integration
  仍为审查冻结候选，祖先关系核对通过。
- scope：改绑定材料前再次只读审计无漂移；修改后只读审计只有 README 与 success_models
  两个实际材料引起的五处 hash_drift，issues=[]。原因审查后仅更新 a7/a8/a9/a10_scope
  的既有材料哈希及引用 DAG 下游，共 11 处摘要；AST 归一核对除摘要外结构、路径、常量不变。
  `audit-verification-scope --json --collect` 最终 exit_code=0、issues=[]、affected_groups=[]、
  文件全 ok，285 个历史模块 collection=ok、execution=not_run。未扩展分母/required/后缀，
  未改冻结 JSON 或 stage_a_verified。

原始日志与重绑前后 JSON、摘要变更明细均保存于 `/tmp/paperradar-issue-120/`，
以 `fixes-` 开头；最终提交 SHA 和交接只写该目录，避免写回受身份材料。

## 剩余边界与交接

本阶段未运行 `./scripts/check-offline` 或 live，未发布 D01/完整 A 通过结论。
最终 integration 完整门禁仍由原 #125 唯一执行者在集成这些修复后启动。
Pi/Live/Cwd、四刊审计、Docling、正式校准与 NAS 均未验证；真实动作服务的原子请求写入、
根标记/执行来源装配、生产隔离、预算与资源领取仍由 B/Body/D/G 等消费者承接。
未发现本轮所触及模块之外必须一并修复的新架构问题。
