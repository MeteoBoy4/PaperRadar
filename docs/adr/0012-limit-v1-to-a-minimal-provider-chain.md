# 第一版只保留最小外部数据链

状态：决策记录（原文未单列接受状态）；日期：2026-10-25；依据：[基线裁决原文](https://github.com/MeteoBoy4/PaperRadar/blob/91e5d02e199f1921ca8afd2b7bdb8f257e6264f3/docs/adr/0012-limit-v1-to-a-minimal-provider-chain.md)；补充／部分取代：[ADR-0032](0032-relax-paper-acquisition-without-evading-access-controls.md)。

2026-10-25：OpenAlex 作为摘要与全文位置的必要时补充渠道已由 [ADR-0032](0032-relax-paper-acquisition-without-evading-access-controls.md) 允许；引用关系、被引次数与排序仍不采集，Semantic Scholar 与 OpenCitations 仍不接入。以下原文其余部分继续适用。

PaperRadar 第一版只接入四刊 Feed 与出版者适配器、Crossref/DataCite DOI 路由、Unpaywall 开放全文定位，以及满足条件时用于参考文献的 GROBID。OpenAlex、Semantic Scholar、OpenCitations、被引次数采集和由此产生的刷新任务不进入第一版。出版者与 Crossref 仍可能漏掉整份参考文献，因此这个精简不能删除已经决定的合法 PDF + GROBID 高风险兜底。该选择减少了身份冲突、限流、快照与重试状态，使第一版专注检验发现、筛选和精读价值；代价是减少聚合图谱可能提供的身份补全与引用召回。
