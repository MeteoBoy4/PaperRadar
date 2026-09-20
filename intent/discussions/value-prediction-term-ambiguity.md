# 「价值预测」术语粒度歧义与阶段产物对照

状态：已决，采用方案 B+；领域词汇已同步到 `CONTEXT.md`。
触发问题：修改前的 `CONTEXT.md`「价值预测」定义提到「可选的条件式复用摘录」，而该摘录属于条件式复用升级（第三制品）。提问者据此怀疑顺序颠倒。

参照文件：

- `CONTEXT.md` 的筛选建议、筛选制品、研究边界判断、价值预测、复用可行性升级和有效复用可行性词条
- `intent/draft.md` §3.4（阶段输入指纹）、§3.7（筛选建议规则）、§4.5（两阶段 Screening 与条件式复用升级）、§7.4（Screening 输出权威 Schema）、§10 表格（`screening_artifacts` / `reuse_assessment_artifacts` / `screening_suggestions`）
- 当前实现：`src/paper_radar/screening/schema.py`、`src/paper_radar/screening/kinds.py`

## 一、结论

提问者的理解基本正确，没有顺序颠倒。修改前的 CONTEXT.md 在同一页混用了两种术语粒度：

- 「价值预测」在**定义条目**里是伞形领域概念，覆盖阶段二预测加上（命中升级时的）升级结果；
- 「价值预测」在**筛选建议条目**里又指阶段二产物本身（写为「摘要层价值预测」）。

`ValuePredictionOutput` 是**阶段二**的 Pydantic 类型，它永远不读摘录；读摘录的是**独立**的 `ReuseAssessmentOutput`。

## 二、阶段与制品对照

Screening 规范上是**两次顺序调用**；复用升级是条件触发的**独立制品**，不是 Screening 的第三个阶段。

| 阶段 / 制品 | 权威类型 | 字段 | 输入 |
|---|---|---|---|
| 阶段一 | `BoundaryOutput` | `boundary`（in_scope / out_of_scope / uncertain）、`reason_zh` | 原题名、摘要、摘要完整性标记、完整 Research Profile、Prompt、输出 Schema |
| 阶段二 | `ValuePredictionOutput` | `research_value` 1–5、`research_value_reason_zh`、`reuse_feasibility` 1–5、`reuse_feasibility_reason_zh`、`reuse_feasibility_inferable`、`value_types`、`topic_ids`、`display_title_zh`（可选）、`abstract_brief_zh`、`why_it_may_matter_zh` | 同上（阶段二不引入摘要以外的输入） |
| 条件式复用升级 | `ReuseAssessmentOutput` | `reuse_feasibility` 1–5、`reuse_feasibility_reason_zh`、`required_adaptations`、`excerpt_kind`（availability / methods / both）、`excerpt_ids` | 仅确定性选择器已固定的 availability / methods / data 摘录 + Research Profile |

支撑要点：

1. `intent/draft.md` §7.4 原文称 `ReuseAssessmentOutput` 为「条件触发的独立第三制品」，并规定「阶段一和阶段二是可独立恢复的调用」。
2. 升级拥有独立的模型配置槽（`reuse_assessment`，可与 Screening 选同一模型但仍是独立 provenance）、独立的输入指纹（§3.4）、独立的每日配额（`auto_reuse_assessment` 20）、独立的持久化表（`reuse_assessment_artifacts`）。
3. 触发方向是下游：阶段二给出 `research_value ∈ reuse_escalation_research_values`（V1 为 `{3}`）且 `reuse_feasibility_inferable=false` 时，才建立非阻塞升级任务。因此「阶段二产物被第三制品用到」不成立，只有反向。
4. 有效值合并规则在 §3.7：`effective_reuse_feasibility` 在升级制品存在时取升级结果，否则取阶段二初步预测；升级不覆盖阶段二字段，两者都保留并展示。

## 三、CONTEXT.md 修改前的措辞歧义

修改前的同一份文档出现两种粒度：

- 修改前的「筛选建议」条目：模型输入被列为「研究边界判断、**摘要层价值预测**和可选复用升级制品」，即 `价值预测 = 阶段二`，升级制品与其并列。
- 修改前的「价值预测」条目：输入含「**可选的条件式复用摘录**」，即 `价值预测 = 阶段二 ∪ 升级`。
- 「筛选制品」条目明确只覆盖阶段一、阶段二；升级单独存表。可见旧定义把阶段二类型名与伞形概念混用了。

即：「价值预测」一词同时承担了阶段二类型名和覆盖多个制品的伞形概念。后者并不对应独立制品，也没有必要成为规范领域术语。

按 AGENTS.md「来源之间冲突时不自行猜测、优先保持已有安全行为并明确指出冲突」的要求，先记录冲突，再由用户确认下述决定。

## 四、采用的澄清方案

采用方案 B+，不改变任何行为、契约或指纹：

1. 「价值预测」只指阶段二的摘要层预测制品，不读取条件式复用摘录。
2. 「复用可行性升级」仍指条件触发、读取固定摘录的独立制品。
3. 新增「有效复用可行性」，表示筛选建议规则从阶段二初步预测和可选升级制品中选择出的派生值；它不是新制品，也不覆盖历史。
4. 不引入「价值判断」作为规范伞形术语；需要合称时直接描述筛选建议所依据的价值相关制品。

没有采用原方案 A。虽然它改动行数较少，但会引入一个没有独立 Schema、持久化或 provenance 的伞形概念，而且容易让人误以为摘录同时更新研究价值和价值类型。

配套检查确认：`intent/draft.md`、相关 ADR、README 和契约说明已经将摘要层价值预测与可选复用升级作为不同能力或制品表述；只需在 `intent/draft.md` 的既有英文派生名旁补充「有效复用可行性」这一中文术语。`CONTEXT.md` 中期刊文章候选原先使用的泛称「价值判断」改为直接描述 Screening 与筛选建议，避免形成新的同义词。

该决定只澄清领域 vocabulary，不改变模型输入、建议规则、校准行为或阶段指纹，因此不触发 calibration change workflow，也不需要新增 ADR。

## 五、附带确认的事实

- 当前代码只实现了阶段一：`OutputKind` 仅注册 `BOUNDARY`（`src/paper_radar/screening/kinds.py`），`schema.py` 仅定义 `BoundaryOutput`。`ValuePredictionOutput` 与 `ReuseAssessmentOutput` 仍属后续 ticket，`docs/contracts/screening-validation.md` 已如实声明它们「仍由后续 ticket 实现，不能据此视为就绪」。
- 因此本次讨论不涉及代码改动，也不涉及 `contracts/` 冻结快照。
