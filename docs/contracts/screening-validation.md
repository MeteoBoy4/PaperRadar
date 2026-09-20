# Screening 输出验证接口

当前交付研究边界判断、摘要层价值预测、复用可行性升级验证，以及研究边界的
`boundary/v1` 冻结契约。价值预测和复用可行性升级只提供公共验证能力，不产出冻结
快照，也不新增 CLI；原因组合和批量导出仍由后续 ticket 实现，不能据此视为就绪。
冻结格式、版本纪律、导出与只读检查命令见[冻结契约导出](frozen-contracts.md)。

## 公共入口

调用方只使用 `paper_radar.screening` 暴露的公共对象：

```python
from paper_radar.screening import (
    BoundaryOutput,
    ExcerptKind,
    OutputKind,
    OutputValidationError,
    ReuseAssessmentContext,
    ReuseAssessmentOutput,
    ValuePredictionContext,
    ValuePredictionOutput,
    validate_output,
)

result = validate_output(
    OutputKind.BOUNDARY,
    {
        "boundary": "in_scope",
        "reason_zh": "该研究直接讨论目标区域的极端降水机制。",
    },
)
assert isinstance(result, BoundaryOutput)

value_result = validate_output(
    OutputKind.VALUE_PREDICTION,
    {
        "research_value": 4,
        "research_value_reason_zh": "该方法能改进区域降水诊断。",
        "reuse_feasibility": 3,
        "reuse_feasibility_reason_zh": "需要调整现有 ERA5 数据处理流程。",
        "reuse_feasibility_inferable": True,
        "value_types": ["method"],
        "topic_ids": ["extreme-rainfall"],
        "abstract_brief_zh": "研究提出一种新的极端降水诊断方法。",
        "why_it_may_matter_zh": "可用于改进当前的区域降水分析。",
    },
    context=ValuePredictionContext(
        enabled_topic_ids=frozenset({"extreme-rainfall"}),
        original_title_is_zh=False,
    ),
)
assert isinstance(value_result, ValuePredictionOutput)

reuse_result = validate_output(
    OutputKind.REUSE_ASSESSMENT,
    {
        "reuse_feasibility": 4,
        "reuse_feasibility_reason_zh": "数据开放，方法可在调整网格后复用。",
        "required_adaptations": ["将输入资料转换为本地网格。"],
        "excerpt_kind": "both",
        "excerpt_ids": ["availability-1", "methods-1"],
    },
    context=ReuseAssessmentContext(
        excerpt_kinds={
            "availability-1": ExcerptKind.AVAILABILITY,
            "methods-1": ExcerptKind.METHODS,
        }
    ),
)
assert isinstance(reuse_result, ReuseAssessmentOutput)
```

当前完整公共面为：

- `BoundaryOutput`：研究边界判断的权威 Pydantic 类型；
- `ValuePredictionOutput`：摘要层价值预测的权威 Pydantic 类型；
- `ValuePredictionContext`：已启用主题集合与原题名语言事实的只读上下文；
- `ReuseAssessmentOutput`：条件式复用可行性升级的独立权威类型；
- `ReuseAssessmentContext`：当次选择器摘录 ID 到契约种类的只读映射；
- `ExcerptKind`：`availability`、`methods`、`both` 的受控序列化词汇；
- `ValueType`、`VALUE_TYPE_DESCRIPTIONS_ZH`：七类价值的序列化值与中文说明；
- `OutputKind`：已注册输出种类；
- `OutputErrorCategory`：受控错误类别；
- `OutputValidationIssue`：单个脱敏验证问题；
- `OutputValidationError`：公共验证失败异常；
- `EXPLICIT_PLACEHOLDER_TEXTS`：明确占位文本共享词汇；
- `INSUFFICIENT_INPUT_MARKERS`：摘要层输入不足理由的固定片段；
- `validate_output`：统一验证入口。

`validate_output(kind, payload, context=None)` 接受原始 JSON 字符串/字节或结构
数据。当前注册的 kind 是 `boundary`、`value_prediction` 和
`reuse_assessment`。成功返回意味着结构与该 kind 的全部适用业务规则都已通过；
验证器不修复输入、不改写文本，也不调用模型判断科学语义。

### 研究边界

`BoundaryOutput` 只包含：

- `boundary`：`in_scope`、`out_of_scope` 或 `uncertain`；
- `reason_zh`：非空、非占位的理由文本。

缺字段、额外字段、错误类型、非法枚举和不完整 JSON 都会失败，入口不会补字段、
修复 JSON、改写理由或修改调用方数据。boundary 不需要业务上下文；`None` 或空
mapping 合法，且验证器不会修改它。显式非空 context 或其他 context 类型会以
`context_mismatch` 失败。

### 价值预测结构

`ValuePredictionOutput` 严格包含：

- `research_value`：1–5 整数；
- `research_value_reason_zh`：研究价值中文理由；
- `reuse_feasibility`：1–5 初步整数评分；
- `reuse_feasibility_reason_zh`：复用可行性中文理由；
- `reuse_feasibility_inferable`：真正的布尔值；
- `value_types`：零个或多个受控价值类型；
- `topic_ids`：零个或多个已启用主题 ID；
- `display_title_zh`：唯一可缺省的字段，默认 `null`；
- `abstract_brief_zh`：中文摘要速览；
- `why_it_may_matter_zh`：中文价值说明。

其他字段全部必填。评分拒绝布尔、浮点、数字字符串、0 和 6；可判断性拒绝数字或
字符串布尔值；列表必须是真正的 JSON/Python list。额外字段一律拒绝，因此最终
决定、期刊信誉、Rank、priority、urgency、自由标签、主题权重和置信分均不能进入
该制品。不完整 JSON 不会被修复。

### 价值预测上下文

价值预测必须同时提供以下只读业务事实：

- `enabled_topic_ids: frozenset[str]`：本次可用的已启用主题 ID 集合；
- `original_title_is_zh: bool`：上游提供的原题名是否中文事实。

推荐调用方显式构造冻结的 `ValuePredictionContext`。公共入口也接受字段完全匹配的
mapping，并先将其验证为该受控类型；不会把自由键值直接传给业务规则。缺少上下文
或必需键报 `missing_context`，类型错误、额外键或不适用的上下文报
`context_mismatch`。验证器只信任 `original_title_is_zh`，不实现语言识别器。

输出中的主题 ID 必须属于 `enabled_topic_ids` 且不得重复；未知或已停用 ID 都按
“未启用”拒绝。零匹配合法，不会新增 `unclassified_value` 等模型输出字段。
boundary 仍只接受 `None` 或空 mapping，上述价值预测上下文不能用于 boundary。

### 价值类型 vocabulary

| 序列化值 | 中文说明 |
| --- | --- |
| `method` | 方法 |
| `data` | 数据 |
| `code_tool` | 代码/工具 |
| `theory_mechanism` | 理论/机制 |
| `evidence_conclusion` | 证据/结论 |
| `question_hypothesis` | 问题/假设 |
| `review_knowledge_map` | 综述/知识地图 |

没有 `other`。未知值和重复值失败；研究价值为 3、4 或 5 时至少需要一类，1 或 2
时允许空列表。主题和价值类型都不形成权重或综合 Rank。

### 题名、文本与可判断性

原题名为中文时，省略 `display_title_zh` 与显式 `null` 等价且合法，任何非 null
值报 `context_mismatch`。原题名非中文时，该字段仍可省略或为 null；提供值时必须
是非空、非占位文本。

四个必填文本字段
`research_value_reason_zh`、`reuse_feasibility_reason_zh`、
`abstract_brief_zh` 和 `why_it_may_matter_zh` 共用下述明确占位规则。合法的
英文缩写、数据集名和原文术语逐字保留，程序不尝试翻译或改写。

`reuse_feasibility_inferable=false` 时，1–5 初步分仍然必填，且仅
`reuse_feasibility_reason_zh` 必须含有至少一个以下固定片段，以明确当前摘要层输入
不足：

- `当前输入不足`、`信息不足`、`摘要未说明`、`摘要未提供`、`摘要未披露`；
- `仅凭摘要无法判断`、`无法从摘要判断`；
- `insufficient information`、`not reported in the abstract`、
  `not provided in the abstract`、`not disclosed in the abstract`、
  `unclear from the abstract`（英文比较不区分大小写）。

例如“摘要未说明 GPU memory 与训练时长，因此复用条件仍不明确”合法；“需要调整
ERA5 preprocessing pipeline”虽是有效文本，但没有说明输入不足，不能配合
`inferable=false`。该约定只做可审计的机械检查，不证明评分或理由在科学上正确。

验证成功返回冻结的权威 Pydantic 类型。失败抛出 `OutputValidationError`；其
`issues` 仅包含 `location`、`category` 和中文 `guidance_zh`。错误文本不包含输入值、
完整 Pydantic 异常或 traceback。纯验证包不访问 CLI、数据库、网络、LLM 或
Docling。

### 复用可行性升级

`ReuseAssessmentOutput` 严格包含原方案 §7.4 的五个必填字段：

- `reuse_feasibility`：1–5 的严格整数；
- `reuse_feasibility_reason_zh`：非空、非占位的中文理由；
- `required_adaptations`：所需改造文本列表，可以为空，重复项也合法；
- `excerpt_kind`：`availability`、`methods` 或 `both`；
- `excerpt_ids`：实际支持判断的摘录 ID，必须非空且不得重复。

该输出没有 `reuse_feasibility_inferable` 字段，不套用摘要层“输入不足理由”规则。
额外字段一律失败，因此它不能携带筛选决定、provenance、正文质量结论或其他阶段
事实。验证成功只返回独立的 `ReuseAssessmentOutput`，不会覆盖摘要层价值预测，也
不会产生 `accepted`、`pending` 或 `denied`。

验证时必须提供 `ReuseAssessmentContext(excerpt_kinds=...)`。映射的键是当次确定性
选择器实际提供的摘录 ID，值只允许 `availability` 或 `methods`。选择器级的
`data` 摘录应由调用方在构造上下文时归入 `methods`；上下文不新增 `data` 值，
输出枚举也不新增 `data`。缺少上下文或必需键报 `missing_context`，错误类型、额外
键或未归一化的 `data` 报 `context_mismatch`。

`excerpt_ids` 中每个 ID 都必须存在于该映射，但无需引用映射中的全部摘录，因而合法
子集不会被扩成全集。声明为 `availability` 时引用集合只能含 availability；声明为
`methods` 时只能含 methods（包括上游归类后的 data）；声明为 `both` 时必须同时含
两类。未知、重复或种类不一致都报 `business_rule`。验证器不执行摘录选择，不判断
来源是否合法或正文是否通过质量门槛，也不修改输出或上下文。

## 受控错误类别

以下序列化值是共享词汇；后续输出种类复用这些类别，不另建同义类别：

| 类别 | 含义 |
| --- | --- |
| `unknown_kind` | 输出种类尚未注册 |
| `invalid_json` | JSON 语法错误或被截断 |
| `missing_field` | 缺少必填字段 |
| `extra_field` | 出现契约外字段 |
| `invalid_type` | 值或载荷类型错误 |
| `invalid_enum` | 值不在受控枚举中 |
| `invalid_text` | 文本为空白或是明确占位文本 |
| `missing_context` | 某输出缺少必需的只读上下文 |
| `context_mismatch` | 上下文类型或适用范围与输出不匹配 |
| `business_rule` | 结构合法但违反该输出的确定性业务规则 |

字段位置以 `$` 为根，例如 `$.boundary`。额外字段的调用方字段名可能包含敏感
内容，因此统一显示为 `$.<额外字段>`。

## 明确占位文本

文本规则只拒绝空白以及以下完整文本；比较时忽略首尾空白，英文不区分大小写：

`无`、`暂无`、`未知`、`待定`、`待补充`、`稍后补充`、`占位`、`无内容`、
`不详`、`-`、`--`、`...`、`…`、`N/A`、`NA`、`TBD`、`TODO`、
`placeholder`。

规则不做子串匹配。例如“`N/A` 是来源字段名；该文仍明确讨论 ENSO 对极端降水
的影响。”是合法理由，并会逐字保留。机械规则只判断文本是否明显缺失，不判断
科学结论是否正确。
