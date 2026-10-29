# 永久保留源文件和承载正式分析的制品

状态：决策记录（原文未单列接受状态）；日期：原文未单列；依据：[基线裁决原文](https://github.com/MeteoBoy4/PaperRadar/blob/91e5d02e199f1921ca8afd2b7bdb8f257e6264f3/docs/adr/0017-retain-only-source-and-analysis-bearing-artifacts.md)；补充／部分取代：[ADR-0026](0026-control-pi-through-a-bounded-rpc-adapter.md)。

PaperRadar 永久保留 Feed 发现事实、有效来源快照、原始 PDF、模型原始成功响应、正式分析，以及被正式分析、筛选建议、校准成员或复用升级引用的 Docling 制品。被新版取代、未被这些历史结果引用且已经验证可从原 PDF 与锁定配置重建的派生 Docling 制品可以清理；失败临时文件和普通 HTTP 缓存按期限删除。复用升级扩大了“承载判断”的范围，因此用于盲评共同输入或建议升级的摘录与底层制品不能按“未精读”误删。

## 补充裁决

2026-10-11 补充（[ADR-0026](0026-control-pi-through-a-bounded-rpc-adapter.md)）：Pi 的“模型原始成功响应”只包括通过 PaperRadar 权威校验的最终 assistant 输出正文，或显式升级后被接收的专用提交工具参数，按业务制品保留且不写普通日志。完整 session、RPC 消息、JSONL transcript 与失败输出全文不是永久保留制品；只保留脱敏执行事实，不能把会话文件当作恢复或校准事实源。
