# Calibration 安全

Calibration 是自动全文精读的门禁。术语见 `GLOSSARY.md` 的 Evaluation 一节；门禁依据见 ADR-0002，变更分级流程见 ADR-0020。

- Blind calibration batch 揭示前，隐藏的 Agent 结果在任何输出中保持隐藏。
- 用户决策优先于系统建议。
- 可能改变 Screening 语义的修改（受影响项的完整列表见 ADR-0020）走 calibration change workflow：记录校准相关差异、暂停自动精读、等待用户附理由标为 `minor` 或 `major`。
- `minor` / `major` 由用户判定；代码和 Agent 只提示风险。
- 自动全文精读保持关闭，直到规定 gate 明确通过且用户显式启用。
