# Issue #6 价值预测验证 — 双轴独立代码审查

- 审查范围:`git diff HEAD~2...HEAD`(固定点 `0ebfc20`),恰好两笔提交:
  - `fb11834` Implement value prediction validation (#6)
  - `132e0be` Address value validation review findings (#6)
- 规格来源:GitHub Issue #6(A1-05:验证完整的价值预测与主题上下文)正文 + 全部 2 条 comments。
- Standards 依据:`AGENTS.md`、`CONTEXT.md`、`docs/agents/domain.md` + Fowler smell 基线(repo 文档优先,工具已强制项跳过)。
- 审查方式:Standards 与 Spec 两个独立只读子代理并行审查,关键行号引用经抽查复核;Spec 轴实测 `scripts/check-offline` 全绿(ruff、mypy、203 项测试、冻结契约 check)。
- 审查性质:只读;未修改代码、未创建 commit、未评论/关闭 Issue。

## Standards

**硬性违规(文档化标准):无。** 逐项核对通过,且多处是主动落实标准:

- 字段与权威定义一致:`ValuePredictionOutput`(src/paper_radar/screening/schema.py:42-56)与 `intent/draft.md` §7.4 逐字段吻合;§7.4 业务规则全部落地于 `_value_prediction_business_issues`(validation.py:128-180)。
- 制品禁令:`extra="forbid"` + 显式禁字段测试(tests/test_value_prediction_validation.py:487-510)落实 CONTEXT.md "制品不含最终决定、期刊信誉、权重、紧急性、自由标签或数值置信度"。
- 错误脱敏:错误仅含 location/category/guidance_zh,测试断言 `__cause__`/`__context__` 为 None(tests:545-546)。`_validate_model`(validation.py:104-125)的 None-init+assert 写法正是为满足此要求,不予标记。
- 文档同步:公共契约变更已同步 `docs/contracts/screening-validation.md`,符合 AGENTS.md 文档维护要求。

**判断性发现(均为 baseline smell,非违规):**

1. **术语微漂移(低,接近标准问题)**:CONTEXT.md 权威表述为"代码或工具、理论或机制、证据或结论、问题或假设、综述或知识地图",而 `VALUE_TYPE_DESCRIPTIONS_ZH`(src/paper_radar/screening/value_types.py:21-30)与文档表格用"代码/工具、理论/机制……"。docs/agents/domain.md 要求以 CONTEXT.md 为准、不漂移近义词。影响仅展示文案;最小修复:统一其中一侧措辞。
2. **公共面不一致(低)**:`INSUFFICIENT_INPUT_MARKERS`(src/paper_radar/screening/text.py:28-43)是契约级词汇(文档逐字列出,提示词构造方必须让模型使用这些片段),却未像 `EXPLICIT_PLACEHOLDER_TEXTS` 一样从 `__init__.py` 导出,也未列入文档"当前完整公共面"。调用方只能抄散文文档,有漂移风险;最小修复:导出该常量并补入文档公共面清单。
3. **Possible Duplicated Code(低)**:validation.py:165-171 与 173-179 两个 seen-set 去重循环同形。可提取 `_membership_issues(items, location_prefix, allowed=None)`;仅两处,不提取也可接受。
4. **Magic strings(低)**:`_REQUIRED_VALUE_TEXT_FIELDS`(validation.py:23-28)+ `getattr`(validation.py:134),与 AGENTS.md "避免 magic string" 精神略抵触;字段重命名只能靠运行时 AttributeError 暴露。可从 `model_fields` 派生或加注释锚定。
5. **类型过宽(微)**:validation.py:165 `seen_value_types: set[object]` 应为 `set[ValueType]`。
6. **Possible Repeated Switches(提示,暂不处理)**:`validate_output` 的 kind 分支 + 三组 overload;kinds.py 注明"后续 ticket 只在此追加成员"。当前两个 kind 保持 if 符合最小改动原则;第三个 kind 落地时建议改为分派表。

## Spec

**(a) 缺失或部分实现的需求 —— 未发现。** 六条验收标准与两条评论逐句核对全部落实:

- AC1(§7.4 严格结构):schema.py:42-56 十字段逐一对应,仅 `display_title_zh` 可缺省 null;`_OneToFiveScore`(schema.py:29)strict int 拒绝布尔/浮点/数字字符串,`StrictBool` 拒绝 0/1/"true";必填缺失、额外字段、截断 JSON 均有测试(tests:392-484)。
- AC2:七类序列化值与中文说明一一对应(value_types.py:9-31,文档表格同步);未知/`other`→INVALID_ENUM、重复→BUSINESS_RULE(validation.py:165-171);research_value≥3 非空(:162-163);主题未知/停用/重复拒绝、零匹配合法(:173-179);未新增输出字段。
- AC3:题名语言规则(validation.py:137-148);上下文缺失/错配不能绕过(:183-195,实测 list/set/int 型 context 均被 context_mismatch 拒绝);无语言识别器。
- AC4:四个必填文本共用占位检查(validation.py:133-135);inferable=false 的输入不足约定只作用于 `reuse_feasibility_reason_zh`(:150-160),符合评论 2"只作用于"限定;文档含固定片段清单与正反例。
- AC5:评分边界、七类、主题状态、题名语言、文本、可判断性均有公共接口测试;输入不变(tests:41-52、189-199)、敏感标记不泄露(:513-556)、禁止字段拒绝(:487-510)覆盖。
- AC6:文档已更新;boundary 仍接受 None/空 mapping(validation.py:274),boundary 测试同步;契约导出只注册 BoundaryOutput(contracts/schema.py:60-68),`contracts/screening/` 仅有 boundary/v1 —— "暂不发布冻结文件、不依赖 export/check、不实现建议或模型调用"全部满足。
- 评论 1/2:受控只读上下文(context.py:9-14,frozen+strict+extra-forbid);缺键报 `missing_context`、不适用报 `context_mismatch`;省略与显式 null 等价(tests:269-283);EXPLICIT_PLACEHOLDER_TEXTS 复用未重定义。

**(b) 未被要求的行为 —— 无实质 scope creep,两处说明:**

1. text.py:37-41 输入不足标记含 5 个英文片段,超出纯中文直觉范围;但属"固定有文档的确定性约定"(文档已列明且不区分大小写),与评论 2 的文档化要求一致,不算越界。
2. `CONTEXT_MISMATCH` 指引文案改动(validation.py:39)影响 boundary 错误文本,属 kind 扩展的必要泛化,boundary 测试已同步。

**(c) 看似实现但有误 —— 仅一处轻微类型标注问题:**

1. src/paper_radar/screening/validation.py:233-238:VALUE_PREDICTION 的 overload 仍写 `context: object = None`,静态类型层面暗示可省略,但运行时缺 context 必报 `missing_context`。spec 依据:评论 2 "缺少上下文或必需键报 missing_context"(运行时已正确)。影响:类型检查器用户无法在编译期发现漏传。最小修复:该 overload 去掉 `= None` 默认值(或要求必传 context)。

## 总结

Standards 轴 6 项发现(0 硬违规,全为低严重度判断性 smell;最重为 value_types.py:21-30 与 CONTEXT.md 的术语微漂移及 text.py:28-43 公共面未导出);Spec 轴 1 项发现(0 缺失、0 scope creep;唯一为 validation.py:233-238 overload 类型标注 nit,不影响运行时)。两笔提交对 Issue #6 实现完整,可合入;建议将上述低严重度项记入后续 ticket 顺手处理。

## 实施 Agent 逐条核实与处理

本节记录收到审查后的实际处理；原审查结论保留不改写。

1. **术语微漂移：不采纳。** Issue #6、父 Issue #1 和 `intent/draft.md`
   §3.5 均明确使用“代码/工具、理论/机制、证据/结论、问题/假设、
   综述/知识地图”作为本票的七类中文说明。当前实现遵循 ticket 的直接规格；不在
   本票中反向修改 `CONTEXT.md` 或改成另一组展示文字。
2. **输入不足标记未进入公共面：采纳。** 从 `paper_radar.screening` 导出
   `INSUFFICIENT_INPUT_MARKERS`，在公共接口文档中列明，并用公共接口测试固定完整
   vocabulary，避免提示词或 adapter 复制散文清单。
3. **两个 seen-set 循环重复：不采纳。** 价值类型循环只检查重复，主题循环同时
   检查重复和已启用集合成员资格；当前两段短逻辑各自表达领域规则。为两个调用点
   引入带可选参数的通用 helper 会增加本票没有要求的抽象。
4. **必填文本字段使用字符串加 `getattr`：采纳。** 改为显式访问四个 Pydantic
   属性，并仅将稳定的公共 location 与值配对；字段重命名现在可由静态检查发现。
5. **`seen_value_types` 类型过宽：采纳。** 收窄为 `set[ValueType]`。
6. **kind 分支未来可能重复：暂不处理。** 当前只有两个 kind；按审查建议，等第三种
   输出实际落地时再判断是否需要分派表，避免 speculative generality。
7. **value-prediction overload 的 context 可省略：采纳。** 该 overload 现在要求
   `ValuePredictionContext | Mapping[str, object]`，且 catch-all overload 也要求显式
   context，使类型检查器能在 literal value-prediction 调用遗漏上下文时报告错误；
   运行时仍保留 `missing_context` 受控失败。
