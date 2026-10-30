# Screening 输出验证历史说明

本页只保存从现状 Contract 迁出的既有说明，不是本轮新增验收结论。
原文时点为 #76 D3(a) 严格解析调整；迁出原文取自基线
`2ad8f354e8d2497719b22eb1a543223d4c8d98aa` 的
`docs/contracts/screening-validation.md`「原始 JSON 的单一解析语义」小节。
其中“不变”“新回归”均指当时调整，不代表当前全量检查通过、生产或 live 就绪。

## 原文

这是 #76 D3(a) 的受控收紧：重复键由旧的后值覆盖改为拒绝；NaN/Infinity 原先可能
按字段 `invalid_type` 拒绝，现在统一归为 JSON 层 `invalid_json`。四份冻结 JSON
Schema、登记版本和 A5 阶段输入格式不变；新回归位于独立测试模块，既有固定分母不变。

## 相关

- [当前输出验证契约](../contracts/screening-validation.md#原始-json-的单一解析语义)。
- [#76](https://github.com/MeteoBoy4/PaperRadar/issues/76)、
  [ADR-0031](../adr/0031-screening-budget-and-derived-applicability.md)。
- [原 A7 需求与证据](a7-requirements.md)、
  [严格解析回归](../../tests/test_screening_strict_json.py)。
