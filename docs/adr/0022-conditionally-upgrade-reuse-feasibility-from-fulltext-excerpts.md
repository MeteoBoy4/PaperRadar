# 只在摘要难以决定边界时用全文摘录升级复用可行性

状态：决策记录（原文未单列接受状态）；日期：原文未单列；依据：[基线裁决原文](https://github.com/MeteoBoy4/PaperRadar/blob/91e5d02e199f1921ca8afd2b7bdb8f257e6264f3/docs/adr/0022-conditionally-upgrade-reuse-feasibility-from-fulltext-excerpts.md)；补充／部分取代：[ADR-0026](0026-control-pi-through-a-bounded-rpc-adapter.md)。

摘要通常不足以判断代码、数据、前置条件和改造成本，但把 PDF 取得与解析放在所有 Screening 之前，会让 Wiley 等受阻来源频繁要求人工介入并拖慢一天内速览。PaperRadar 因此先完成题名摘要 Screening；V1 只有研究价值命中版本化触发参数（初值为 3）且复用可行性不可判断时，才非阻塞地尝试 availability 优先、methods/data 次之的合法摘录，并保存独立的复用升级制品。取不到摘录时论文保持 pending 而不是阻塞或猜测；研究价值至少 4 的论文仍直接 accepted，队列归属升级留到以后。

升级使用与 Read 相同、通过质量门槛的 Docling 制品或可追溯的结构化来源，不建立第二套解析器，也不覆盖摘要层预测。正式盲评必须向用户展示 Agent 使用的同一冻结摘录；批次创建不等待人工 PDF，未就绪成员冻结为升级不可用。触发参数、摘录选择器、模型、提示词和契约都进入运行配置快照、相关阶段输入指纹及校准语义基线；能够改变摘录的解析配置也属于校准相关语义。改变它们必须走校准变更分级，但只改变无关的 Read 配置不触发分级。

## 补充裁决

2026-10-11 补充（[ADR-0026](0026-control-pi-through-a-bounded-rpc-adapter.md)）：Pi 仅对 Python 已选定的冻结摘录产生候选升级制品，使用独立临时会话和权威校验；全文取得、Docling 解析、摘录定位与升级资格仍由 PaperRadar 控制，不开放为 Agent 工具。reuse 的适配器语义纳入本阶段指纹与校准语义基线，不能因其接入 Pi 而变为自主全文精读。
