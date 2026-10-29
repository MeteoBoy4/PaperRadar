# 历史候选晋级后才补全元数据

状态：决策记录（原文未单列接受状态）；日期：原文未单列；依据：[基线裁决原文](https://github.com/MeteoBoy4/PaperRadar/blob/91e5d02e199f1921ca8afd2b7bdb8f257e6264f3/docs/adr/0015-delay-historical-enrichment-until-promotion.md)；补充／部分取代：无另列关系；正文边界继续适用。

PaperRadar 对尚未晋级的历史候选只保存原始参考文献、来源位置和可以直接规范化的强标识；只有强标识确认相同时，多篇 RSS 种子的引用才合并计数。计数只采用当前有效的 `accepted` RSS 种子，因此种子决定被纠正后可以下降；候选达到两次引用或由用户选择并晋级后，则不再自动降级，并从那时起调用外部提供方补全元数据和进入 Screening。这个选择减少外部调用并避免模糊题录形成错误晋级，代价是没有 DOI 等强标识的同一历史论文可能无法自动累计到阈值。
