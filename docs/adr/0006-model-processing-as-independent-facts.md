# 用独立事实代替论文主状态机

状态：决策记录（原文未单列接受状态）；日期：原文未单列；依据：[基线裁决原文](https://github.com/MeteoBoy4/PaperRadar/blob/91e5d02e199f1921ca8afd2b7bdb8f257e6264f3/docs/adr/0006-model-processing-as-independent-facts.md)；补充／部分取代：无另列关系；正文边界继续适用。

PaperRadar 不在论文记录上维护 `new → metadata_ready → accepted → fulltext_ready → analyzed → delivered` 这样的单一主状态。元数据就绪、筛选决定、参考文献取得与解析、全文准备、精读分析和用户行为各自独立记录，任务资格由这些事实共同推导；这样全文与参考文献可以并行，当前版本变化可以让新分析待处理而不抹除旧分析，用户行为也不会冒充处理进度。代价是任务查询需要同时检查多个条件，但避免了一个主状态无法真实表达并行和历史的矛盾。
