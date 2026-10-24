# LLM 与证据

此处“模型”指流水线中调用的 LLM / Agent，而不是编写代码的 Agent。

- 模型产出结构化 artifact；流程控制和状态推进由确定性代码负责。
- 模型输出同时通过权威 Pydantic Schema 和业务规则验证（Screening 见 `docs/contracts/screening-validation.md`，Read 原始输出与消费上下文见 `docs/contracts/read-validation.md`）。
- 模型输出只包含规格定义的字段；Topic、最终流程状态、自由标签、Rank、urgency 和规格未定义的 confidence score 均不由模型产生。
- Screening 的模型输入不含期刊声誉。
- Read 阶段需要证据支持的结论引用有效的 evidence ID。
- 表格、公式、图片或文本不可用时，如实记录为不可用，不生成对应 evidence。
- 日志只记录标识符和摘要性信息；secret、完整 Prompt、完整 Profile、全文和完整 excerpt 不进入日志。
