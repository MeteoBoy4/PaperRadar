# Issue #7 复用升级验证 — 独立代码审查（HEAD~2..HEAD）

- 审查范围：`git diff HEAD~2...HEAD`，两笔提交：
  - `127d8a4` Implement reuse assessment validation (#7)
  - `d6a7e92` Address reuse validation review findings (#7)
- 固定点：`HEAD~2` = `e6dd0d8`（`git log HEAD~2..HEAD --oneline` 已验证恰好为上述两笔）。
- 规格来源：GitHub Issue #7「A1-06：验证复用升级的摘录引用」正文 + 全部 comments（以 comment 2 对 comment 1 的修正为准），及其引用的 `intent/draft.md` §7.4 / §4.5、`docs/adr/0022-conditionally-upgrade-reuse-feasibility-from-fulltext-excerpts.md`、`CONTEXT.md`。
- 审查方式：只读；Standards 与 Spec 两轴由独立并行子代理完成，未修改代码、未创建 commit、未触碰 Issue。

## Standards

以 AGENTS.md、CONTEXT.md、docs/agents/、docs/contracts/、ADR 0022 及 Fowler 气味基线为准。

### (a) 文档化标准违规

未发现硬性违规。逐项核对结果：

- **AGENTS.md「文档维护」**：README、`docs/contracts/screening-validation.md` 已随公共面变化同步更新；`docs/contracts/frozen-contracts.md` 未动但仍准确（复用升级确实只有验证、无冻结快照）。✓
- **AGENTS.md「LLM 与证据规则」**：`ReuseAssessmentOutput` 无 confidence、标签、决定字段；`excerpt_ids` 必须引用上下文中存在的 ID（`src/paper_radar/screening/validation.py:215-236`），不伪造 evidence；泄漏测试（`tests/test_reuse_assessment_validation.py:399-418`）验证错误面不含 secret marker、Pydantic 内部文本和 traceback。✓
- **文档自身声明 vs 代码**：`screening-validation.md:190` 称「严格包含原方案 §7.4 的五个必填字段」——与 `intent/draft.md:971-977` 逐字段一致；`:207` 称未归一化 `data` 报 `context_mismatch`——与 `validation.py:262-275`（非 missing 一律 CONTEXT_MISMATCH）及测试一致；`both` 必须两类齐全、`data` 归入 `methods` 与 ADR 0022（availability 优先、methods/data 次之）一致。✓
- **CONTEXT.md / domain.md 词汇**：`ExcerptKind`、`ReuseAssessmentOutput` 使用既有术语（复用可行性升级、摘录），未引入 glossary 避免的同义词。✓
- **离线/架构纪律**：新测试无网络/DB；`excerpt_kinds.py` 不触发 `test_screening_architecture.py` 的禁导入表；无新依赖，符合 lockfile 纪律。✓

### (b) Baseline 气味（均为判断性意见）

1. **Duplicated Code（兼 Data Clumps）— `src/paper_radar/screening/validation.py:330-365`**。`VALUE_PREDICTION` 与 `REUSE_ASSESSMENT` 两个分支形状完全相同（`_validate_context` → `_validate_model` → business issues → raise/return），且 (model, known_fields) 成对反复出现（第 26-30 行的四个 `_KNOWN_*` 常量与 model 类一一对应、一起旅行）。影响：后续新增「原因组合」kind 时会第三次复制同一形状。最小修复：建立 `dict[OutputKind, tuple[context_model, output_model, known_fields, business_fn]]` 注册表，把 dispatch 折成一个循环；不紧急，可在下一个 kind 落地时再做。

2. **Duplicated Code — `src/paper_radar/screening/excerpt_kinds.py:19-22` vs `schema.py:20-23`**。`_require_excerpt_kind_string` 与 `_require_value_type_string` 逻辑同构，仅枚举类型和中文报错不同。影响低（各 4 行、消息须区分）。最小修复：可抽一个 `_require_enum_string(enum_cls, message)` 工厂；也可接受现状。

3. **`ReuseAssessmentContext.excerpt_kinds` 可变性与「只读」声明的张力 — `src/paper_radar/screening/context.py:23`**。模型 `frozen=True` 但字段类型是可变 `dict`；文档（`docs/contracts/screening-validation.md:79、203`）称「只读映射」。相邻的 `ValuePredictionContext` 用了真正不可变的 `frozenset`。影响：调用方可在两次 `validate_output` 之间原地改 dict，而 `isinstance` 快路径（`validation.py:249`）会跳过再验证——纯进程内信任边界，风险低。最小修复：改用 `Mapping` + `MappingProxyType` 包装，或在文档中把「只读」弱化为「验证器不修改」。

4. **重复+未知 ID 同位双 issue — `src/paper_radar/screening/validation.py:215-225`**。同一 `excerpt_id` 既是重复又未知时，`$.excerpt_ids[i]` 会收到两条 category 相同的 issue。文档未承诺去重，测试也未覆盖该组合；影响仅是错误列表噪声。判断性意见，可不改。

其余气味类别（Mysterious Name、Feature Envy、Primitive Obsession、Repeated Switches、Shotgun Surgery、Divergent Change、Speculative Generality、Message Chains、Middle Man、Refused Bequest）：未发现。特别说明——`_validate_context` 的泛化有两个真实调用点支撑，非 Speculative Generality；kind dispatch 仍是 if 级联而非 switch-map，暂不构成 Repeated Switches（仅三处、语义不同），但与发现 1 同源，随注册表一并解决。

## Spec

以 Issue #7 正文 5 条 AC、两条评论（以评论 2 为准）及 §7.4/§4.5/ADR 0022 为准。已实际运行验证：`uv run pytest tests/test_reuse_assessment_validation.py`（42 passed）与 `scripts/check-offline`（246 passed + 冻结契约一致，均通过）。

### (a) 规格要求但缺失或部分实现

无实质缺失。逐条核验结果：

- AC1：五字段与 §7.4（`intent/draft.md:971-977`）完全一致且全部必填（`src/paper_radar/screening/schema.py:60-69`）；`_OneToFiveScore` strict int + ge/le（`schema.py:30`）；理由与 adaptations 逐项走 `is_meaningful_text`（`validation.py:195-209`）；缺失/额外/错类型/截断 JSON 均有测试。
- AC2：上下文必需（`validation.py:245-248`）；`excerpt_ids` 非空、去重、存在性、子集允许均实现（`validation.py:210-236`）。
- AC3：`ExcerptKind` 仅 availability/methods/both（`excerpt_kinds.py:240-245`）；both 用集合相等强制两类（`validation.py:230-236`）；未新增 data 枚举。
- AC4：纯验证、无持久化、无 accepted/denied 字段（extra="forbid"），reuse 分支不调用价值预测逻辑（`validation.py:348-365`）。
- AC5：要求的测试矩阵齐全；不导出快照（`contracts/screening/` 仍只有 boundary）、不接 CLI；离线入口通过。
- 评论 2：上下文仅 availability/methods，`ContextExcerptKind` 拒绝 both 与 data（`excerpt_kinds.py:254-267`）；合并留给调用方并在 `docs/contracts/screening-validation.md` 说明；CONTEXT.md 保留 data 词汇（`CONTEXT.md:130`）；无 inferable 字段、不套用 `states_input_is_insufficient`、adaptations 不去重——全部符合。

轻微覆盖空隙（非阻塞）：缺「`excerpt_ids` 含空字符串」与「`excerpt_kinds` 为空映射」的边界测试；现有规则下前者只在上下文也含 `""` 键时才可能通过，后者必然以 unknown ID 失败，语义仍安全。最小修复：在 `tests/test_reuse_assessment_validation.py` 各加一例参数化。

### (b) 规格未要求的行为（scope creep）

无。`_validate_value_prediction_context` 泛化为 `_validate_context`（`validation.py:240-281`）是复用同一上下文校验流程的最小改动；README 更新是修正「价值预测尚未实现」的过期陈述（该能力由 #5/#6 交付）；`tests/test_boundary_validation.py` 把 unknown-kind 用例从 `reuse_assessment` 改为 `read_analysis` 是注册新 kind 后的必要跟进。

### (c) 看似实现但实现有误

仅一处低严重度诊断完整性问题：

- `src/paper_radar/screening/validation.py:226`：`if not has_unknown_excerpt:` 在存在未知 ID 时整体跳过种类一致性检查。规格依据：AC3「种类与实际引用一致，both 必须引用两类」与评论「未知 ID 或种类不满足声明报 business_rule」。实际影响：当 `excerpt_ids` 同时含未知 ID 和种类冲突（如 kind=`availability` 引用 `["methods-1", "ghost"]`）时，只报未知 ID，`$.excerpt_kind` 的 business_rule 被吞掉；调用仍失败，只是诊断不完整。这可以理解为避免对未知 ID 推断种类的误导性级联，属于可接受取舍；若要严格对齐，最小修复是只用已知 ID 计算 `referenced_kinds`，在它与 `expected_kinds` 不可能相等（如 both 缺类）时仍追加 issue。

## 总结

- **Standards**：0 项硬性违规，4 项判断性气味；最值得注意的是 `validation.py` 两个 OutputKind 分支的形状重复（发现 1），建议随下一个 kind 落地时以注册表收敛。
- **Spec**：5 条 AC 与评论 2 全部实现且离线验证通过，无 scope creep；最严重（亦仅低严重度）的问题是未知 ID 存在时种类冲突诊断被跳过（`validation.py:226`），不影响验证正确性。

## 实施复核与处理（2026-09-20）

以下结论由实现方逐条对照 Issue #7、最新评论、父 Issue #1 和当前代码核实；上方独立
审查原文保留不改。

1. **kind dispatch 重复：暂不采纳注册表建议。** 当前只有两个需要上下文的输出
   kind，且各自返回类型和业务函数不同；现在引入异构注册表主要服务后续 ticket，
   会增加类型编排和间接层。待新增第三个同形分支时再依据真实接口收敛。
2. **enum 字符串前置校验重复：不采纳。** 两处各只有一个类型检查，但对应不同领域
   enum 和诊断文本。抽取带 `enum_cls`、消息参数的工厂不会减少领域知识，反而使
   Schema 的严格输入规则更难就近阅读。
3. **上下文映射可变：采纳。** `ReuseAssessmentContext.excerpt_kinds` 改为经
   `MappingProxyType` 包装的 `Mapping`，避免 `frozen=True` 下仍可原地修改；同时
   拒绝空白摘录 ID，使“只读的实际摘录 ID 映射”成为可执行约束。新增不可变性及
   空 ID 回归测试，并同步 `docs/contracts/screening-validation.md`。
4. **重复且未知 ID 产生同位双 issue：采纳。** 每个首次出现的未知 ID 报存在性
   错误；后续同 ID 只报重复错误，不再为同一位置追加第二条相同 category。
5. **空 ID / 空上下文映射覆盖：采纳。** 新测试覆盖输出空 ID、上下文空映射及上下文
   自身包含空 ID。前两者保持 `business_rule`，格式错误的上下文 ID 报
   `context_mismatch`。
6. **未知 ID 时跳过全部种类诊断：部分采纳。** 现在会根据已知引用报告可以确定的
   冲突，例如声明 `availability` 却已引用 `methods`；若未知 ID 仍可能补齐 `both`
   缺失类别，则只报未知 ID，避免制造无法确定的 kind 冲突。两种路径均有回归测试。

处理后已运行 `./scripts/check-offline`：锁文件、格式、Ruff、mypy、253 个离线测试
及 `boundary/v1` 冻结契约一致性检查全部通过；其中复用升级验证测试为 49 项。
