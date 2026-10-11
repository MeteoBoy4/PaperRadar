# 允许把论文内容发送给明确配置的外部 LLM

PaperRadar 第一版允许 Screening 将题名、摘要和 Research Profile，允许条件式复用升级发送合法结构化来源或正文提取物中的 availability、methods/data 摘录与 Profile，允许 Read 发送合法取得的正文提取物与 Profile。启动检查必须按阶段显示数据边界，日志不得记录完整摘录、全文、完整提示词、认证信息或密钥。正式校准固定引用 Screening 侧的校准语义基线；Read 模型另行版本化选择，不改变该基线。这个决定让论文内容可能离开本机，具体供应商条款必须在选择实际模型时核对。

2026-10-11 补充（[ADR-0026](0026-control-pi-through-a-bounded-rpc-adapter.md)）：输入经 Pi RPC 发送给固定外部模型，数据许可边界不扩大。每阶段与每 attempt 隔离临时会话，Read 全文、复用摘录和历史隐藏结果不能串入摘要筛选。完整 session/RPC/JSONL transcript 不永久保存，stderr 与工具错误也只提取脱敏摘要；必要成功输出作为受访问控制的业务制品保留，盲评可见性规则适用于这些结果。
