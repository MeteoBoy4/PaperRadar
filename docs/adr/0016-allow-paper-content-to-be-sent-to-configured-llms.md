# 允许把论文内容发送给明确配置的外部 LLM

PaperRadar 第一版允许 Screening 将题名、摘要和 Research Profile，允许条件式复用升级发送合法结构化来源或正文提取物中的 availability、methods/data 摘录与 Profile，允许 Read 发送合法取得的正文提取物与 Profile。启动检查必须按阶段显示数据边界，日志不得记录完整摘录、全文、完整提示词、认证信息或密钥。正式校准只冻结 Screening 侧模型和语义组合；Read 模型另行版本化选择。这个决定让论文内容可能离开本机，具体供应商条款必须在选择实际模型时核对。
