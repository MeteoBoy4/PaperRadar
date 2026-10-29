# 只对不可用或高风险不完整列表执行 PDF 参考文献提取

状态：决策记录（原文未单列接受状态）；日期：原文未单列；依据：[基线裁决原文](https://github.com/MeteoBoy4/PaperRadar/blob/91e5d02e199f1921ca8afd2b7bdb8f257e6264f3/docs/adr/0003-use-pdf-reference-extraction-only-for-high-risk-gaps.md)；补充／部分取代：无另列关系；正文边界继续适用。

PaperRadar 以出版者结构化列表和 Crossref 为参考文献主路径，只在没有取得任何条目，或来源自报数量不一致、可比来源条目数差距超过 20% 等证据表明列表存在高风险缺口时，才对合法取得的 PDF 调用 GROBID。普通的部分列表可以立即用于论文发现并保留不完整标记，不因缺少完整性佐证而一律承担 PDF 解析成本；因此第一版明确接受部分引用漏召回，但绝不把这类列表标为完整。当前版本的出版者列表已经确认完整时，即使 Crossref 为空或差异很大，也不触发无意义的兜底提取。
