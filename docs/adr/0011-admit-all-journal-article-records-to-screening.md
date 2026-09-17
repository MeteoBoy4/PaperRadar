# 让所有 journal-article 记录进入 Screening

PaperRadar 第一版把来源标为 `journal-article` 的 Feed 记录全部视为可筛选候选，不在 Screening 前继续判断它究竟是研究论文、综述、社论、勘误或其他期刊内容。这样避免子类型缺失或不一致漏掉研究论文，但接受非目标内容消耗 Screening 的可能。若全部适用来源和 7 天延迟复查后仍缺题名或摘要，记录形成 `metadata_unobtainable`，不调用 Screening 或进入校准；若只有疑似截断摘要，则继续尝试其他来源，最终仍只有片段时允许带标记筛选并在校准中披露。第一版不新增文章类型 Agent 或自动类型过滤器。
