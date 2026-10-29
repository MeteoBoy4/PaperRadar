# 只依据强标识自动合并论文

状态：决策记录（原文未单列接受状态）；日期：原文未单列；依据：[基线裁决原文](https://github.com/MeteoBoy4/PaperRadar/blob/91e5d02e199f1921ca8afd2b7bdb8f257e6264f3/docs/adr/0005-only-merge-papers-automatically-on-strong-identifiers.md)；补充／部分取代：无另列关系；正文边界继续适用。

PaperRadar 只在规范 DOI、arXiv ID、PMID 等强标识相同，或权威来源明确声明预印本与正式版关系时自动合并论文。题名、作者、年份、URL 或模糊相似度只能产生等待用户确认的重复候选；错误合并会混淆全文、精读结果和引用关系，其损害高于暂时保留两条可能重复的记录。自动和人工合并都记录可撤销事件，被吸收记录及其原有关系作为不可见历史保留；人工合并还必须先预览受影响关系。
