# ica-advise：#2 四种 outcome 中文文本随词汇住在模块（选 a）

日期：2026-09-22
状态：已决。
来源：架构审视报告候选 #2；grilling Q7。前序：ica-advise-export-batch-partial-failure.md（Q2）、ica-advise-not-attempted-single-state.md（Q3）、ica-advise-outcome-literal-narrowing.md（Q6）。

## 决策是什么

export 四种 outcome 的中文文本的家：全部由 export.py 放进 `item.message_zh`，CLI 只管行格式与输出流（a）；或仅 failed / not_attempted 文本进 item、两句成功文本留在 CLI（b）。

**选定 (a)。**

## 为什么

- check 侧已是 模式：通过文本"冻结契约一致："在 check.py:252，失败文本亦在模块内，CLI 只拼行。选 是把 export 对齐到同包既有先例，两个批量命令的 item 渲染循环从此同构——兑现 #2"两个渲染函数并成一个 for 循环"的前提。
- 仓库普适模式是"受控词汇与中文文本同住"：screening/reasons.py 的 `SCREENING_RESULT_DESCRIPTIONS_ZH` / `DECISION_REASON_DESCRIPTIONS_ZH` 等均如此。Q6 刚把四值 outcome 收成一份词汇，其中文句子留在 CLI 等于在词汇表旁再开第二来源。
- (b) 保留的分裂正是 #2 的病灶："批量导出已停止；修复上述问题后原命令重跑即可补齐。"是 not_attempted 的业务指引（Q3 已定性），业务事实住在表现层即审视报告点名的泄漏；成功文本留在 CLI 也使测试只能对屏幕文字断言成功场景。

附带约束：CLI 输出逐字不变（成功行 / 未完成 [类别] 行 / 未完成：行三种模板与 stdout/stderr 分流保持，"未完成"等行模板词归 CLI）；四句文本逐字迁移（"已创建冻结契约"、"冻结契约内容一致，未改写"、失败指引来自 Q1/Q4 判决表、not_attempted 指引）；check 侧不动；随 Q2 更新的文档 outcome 表将四句指引列为词汇的中文描述。

## 是否改变外部行为

否。CLI 输出与退出码逐字不变；文本仅在模块与 CLI 之间搬家；文档按 Q2 既定要求同步，无新承诺。

## 是否需要 ADR

否。文本归属与渲染分工调整，不触碰领域不变量与文档契约语义。
