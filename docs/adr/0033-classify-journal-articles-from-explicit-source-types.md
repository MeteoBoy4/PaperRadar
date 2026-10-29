# 仅按封闭的来源类型字段判定期刊文章候选

状态：决策记录（原文未单列接受状态）；日期：原文未单列；依据：[基线裁决原文](https://github.com/MeteoBoy4/PaperRadar/blob/91e5d02e199f1921ca8afd2b7bdb8f257e6264f3/docs/adr/0033-classify-journal-articles-from-explicit-source-types.md)；补充／部分取代：无另列关系；正文边界继续适用。

依据 #100 四项裁决，类别依据固定为（路线、字段定位、值）的封闭表：Crossref `message.type=journal-article`、DataCite `types.resourceTypeGeneral=JournalArticle`、《大气科学》current Feed `dc:type=article` 与文章页 `dc.type=论文`。前两者的其他明确值属于非 journal-article，平台表外值或缺字段属于未知；不同明确判定互斥时单列冲突。Wiley `category`/`prism:section` 只原样记录，不用于预过滤，DOI 前缀、题名、URL 和 Feed 位置均不是类别依据。

该选择保留 ADR-0011 接受社论等初筛噪声的边界，同时避免将 ISTIC 期刊因 Crossref 无记录而结构性排除。代价是每个平台显式字段须登记，表外值保守退为未知，不能以位置推断兜底。A10 仅审计来源，不产生 Paper 或 Screening 资格。
