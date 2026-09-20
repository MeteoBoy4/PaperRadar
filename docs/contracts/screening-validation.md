# Screening 输出验证接口

当前交付研究边界判断及其 `boundary/v1` 冻结契约。价值预测、复用可行性升级、
原因组合和批量导出仍由后续 ticket 实现，不能据此视为就绪。冻结格式、
版本纪律、导出与只读检查命令见[冻结契约导出](frozen-contracts.md)。

## 公共入口

调用方只使用 `paper_radar.screening` 暴露的公共对象：

```python
from paper_radar.screening import (
    BoundaryOutput,
    OutputKind,
    OutputValidationError,
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
```

当前完整公共面为：

- `BoundaryOutput`：研究边界判断的权威 Pydantic 类型；
- `OutputKind`：已注册输出种类；
- `OutputErrorCategory`：受控错误类别；
- `OutputValidationIssue`：单个脱敏验证问题；
- `OutputValidationError`：公共验证失败异常；
- `EXPLICIT_PLACEHOLDER_TEXTS`：明确占位文本共享词汇；
- `validate_output`：统一验证入口。

`validate_output(kind, payload, context=None)` 接受原始 JSON 字符串/字节或结构
数据。当前唯一注册的 kind 是 `boundary`。`BoundaryOutput` 只包含：

- `boundary`：`in_scope`、`out_of_scope` 或 `uncertain`；
- `reason_zh`：非空、非占位的理由文本。

缺字段、额外字段、错误类型、非法枚举和不完整 JSON 都会失败，入口不会补字段、
修复 JSON、改写理由或修改调用方数据。boundary 不需要业务上下文；`None` 或空
mapping 合法，且验证器不会修改它。显式非空 context 或其他 context 类型会以
`context_mismatch` 失败。

验证成功返回冻结的权威 Pydantic 类型。失败抛出 `OutputValidationError`；其
`issues` 仅包含 `location`、`category` 和中文 `guidance_zh`。错误文本不包含输入值、
完整 Pydantic 异常或 traceback。纯验证包不访问 CLI、数据库、网络、LLM 或
Docling。

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
