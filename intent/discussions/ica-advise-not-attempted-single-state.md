# ica-advise：#2 not_attempted 保持单一状态（选 a）

日期：2026-09-22
状态：已决。
来源：架构审视报告候选 #2；grilling Q3。前序：ica-advise-export-batch-partial-failure.md（Q2）。

## 决策是什么

`not_attempted` 有两种成因：预检阶段他项失败整批放弃（export.py:288-315，预检循环跑完才抛，目标零写入）；发布阶段他项失败未轮到（export.py:317-334，首次失败立即抛，同批可能有 created 项落盘）。Q3 在三种收法中抉择：

- (a) 合并为单一 `not_attempted`；
- (b) 拆成 `blocked_by_preflight` / `not_reached` 两态；
- (c) 单态 + `ContractBatchExportResult` 上批次级"是否已开始发布"字段。

**选定 (a)。** 两种成因共用同一 outcome 与同一指引文本。

## 为什么

- 两种成因的补救动作逐字相同：重跑原命令；幂等性由核心不变量"相同输入重复运行幂等"及既有实现保证（unchanged 不改写、缺失项补齐）。
- 区分信息已由 items 免费承载：批内存在 `created` 行即"这批已部分写入"；无 `created` 行即零落盘。唯一拆不出的角落是"发布开始后第一项即失败"——该情况磁盘状态与补救动作和预检中止完全相同（零字节、重跑同命令），区分无接收方。
- `docs/contracts/frozen-contracts.md:142-146` 已对两种情况使用同一"未完成"措辞与同一补救指引（"修复故障后使用完全相同的命令重跑……不会回滚已发布的历史版本"）；拆两态反而要改动已发布文档的产品语义。
- (b) 使受控词汇、文档表格与测试矩阵翻倍，但不改变用户任何动作，违背 V1 的 attention_overload 优先级。(c) 是无消费者的投机字段（唯一调用方 CLI 不需要，check 侧亦无对应物），按"Speculative 项默认暂缓"处理。

附带约束：not_attempted 指引文本保持"批量导出已停止；修复上述问题后原命令重跑即可补齐。"，两种成因同文；不新增批次级 publish_started 类字段；随 Q2 更新的受控 outcome 表中 not_attempted 单行，"含义与操作"说明含两种成因、操作相同；幂等重跑与不回滚承诺不变。

## 是否改变外部行为

否。CLI 输出与今天完全一致（两种成因本就打印同一句话）；Python 接口词汇与 Q2 决定一致，不新增状态或字段；文档 prose 不变，仅在 Q2 已要求的 outcome 表更新中体现单行 not_attempted。

## 是否需要 ADR

否。词汇粒度选择不触碰领域不变量、持久化或校准语义；与 `intent/draft.md` 及现有文档承诺一致，属接口内部组织。
