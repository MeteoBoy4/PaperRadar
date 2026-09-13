# 第一版只保留最小外部数据链

PaperRadar 第一版只接入四刊 Feed 与出版者适配器、Crossref/DataCite DOI 路由、Unpaywall 开放全文定位，以及满足条件时用于参考文献的 GROBID。OpenAlex、Semantic Scholar、OpenCitations、被引次数采集和由此产生的刷新任务不进入第一版。出版者与 Crossref 仍可能漏掉整份参考文献，因此这个精简不能删除已经决定的合法 PDF + GROBID 高风险兜底。该选择减少了身份冲突、限流、快照与重试状态，使第一版专注检验发现、筛选和精读价值；代价是减少聚合图谱可能提供的身份补全与引用召回。
