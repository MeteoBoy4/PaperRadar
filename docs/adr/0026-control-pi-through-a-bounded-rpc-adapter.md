# 通过有界 RPC 适配器控制 Pi，保留 PaperRadar 的接收权威

2026-10-11：用户接受 [Pi 可行性研究](../../intent/discussions/pi-agent-contract-feasibility.md) §5 及其中“我的决策”，Python 主程序通过 RPC 控制本机 Pi 子进程，作为 V1 的有界 LLM/Agent adapter，取代原 PydanticAI 调用实现选择。Pi 负责固定模型的结构输出调用，PaperRadar 的权威 Pydantic Schema 与业务规则决定能否接收；建议、决定、任务资格、校准、证据构造与持久化继续由确定性程序控制。采用 RPC 是为了让 Python 明确控制隔离、取消、预算与完成边界；代价是需要锁定并管理 Node/Pi 子进程、事件协议和显式运行资源。

V1 首次使用 `prompt_only`，严格接收最终 assistant 的纯 JSON 文本；专用提交工具作为已验证可行的备用升级，能力可共存于适配器层，按阶段版本化配置选择，但每次运行只有一个权威通道，不自动切换或双通道竞争。提交工具的 TypeBox 参数 Schema 从 Pydantic JSON Schema 导入，仍由 Python 权威校验，成功才返回 validated artifact 并终结 run。提交工具不因参数带 Schema 就成为 provider 原生 `json_schema`；其配置协议名称与映射需在启用升级前明确定义，V1 默认验收不要求启用它。

每个阶段、Read map/reduce 输入及每次 attempt 使用隔离临时会话。固定实际 provider/model、有效系统提示词、Contract、Profile、工具声明与运行策略；禁用自动发现资源、MCP、个人上下文、会话持久化、Pi agent/provider 隐含 retry、自动 compaction/summarization 和额外模型回合。一次 attempt 最多一次模型调用，Python 对同一阶段输入最多两次；进程重建不重置预算。RPC ACK 与退出码不是成功：必须消费到 `agent_settled`，核对最终消息 stopReason、实际模型及所选通道，排除超时、取消与进程异常，再通过严格解析、Schema 和业务校验。任一失败均不能提交部分结果，也不能阻断同批无关任务。

`prompt_only` 不开放工具；升级后仅开放专用提交工具，通用 bash、文件读写、网络、数据库、全文获取、Docling 与 evidence 查询工具均不开放给 Agent。`--tools` 不是 OS sandbox，子进程和扩展必须另有实际权限约束。研究 §6 的灵活模型、全文、PDF 与 evidence 工具不进入 V1，也不改变 ADR-0010/ADR-0025 的既定 Docling 能力。只保留脱敏执行事实与必要成功制品，完整 session/RPC/JSONL transcript 不永久落盘；未揭晓校准结果仍受既有可见性边界保护。

会改变阶段语义的输出协议、有效系统提示词、工具声明与实现及运行策略进入相应阶段指纹，Screening/reuse 相关部分进入校准语义基线（ADR-0008、ADR-0023），变化交由用户按 ADR-0020 分级。Pi/adapter 锁定版本与资源哈希用于执行审计，其中可能影响模型行为的升级须更新语义身份；进程 ID、临时会话 ID、路径、时间和纯传输重构不成为语义输入。纯 Read 配置不影响 Screening 校准，共有策略按实际受影响阶段判断，不能因本次架构选择自动继承或开启门禁。

本 ADR 记录目标架构，本次只更新文档；现有代码、版本化配置、快照与 Frozen Contract 不被改写。Pi 配置映射、权限约束、生产 Read 权威 Schema/验证器、恢复幂等与 fixtures 仍需在后续实现票中验收。研究临时 Read Schema 和已暴露样本不能冒充生产契约或正式盲评；正式采集时登记样本排除。可行性实测证明了接入方式，不证明生产质量、校准通过或自动精读资格。

2026-10-24：按 #85 D1–D4/P3 裁决补充：A8 封闭协议档案仅登记 1.4.0，构造期拒绝
其他版本而不领取。调用语义取预算首次 snapshot，执行审计版本取本次回执 snapshot，
两者同阶段投影相等才可组合。完整协议中的最终模型观察交由 A7 判 `model_mismatch`，
初始化模型/档位不符仍属于协议拒绝，不改变 A7 接收规则。Pi `totalTokens==0` 时两项
token 均未知，否则输入为 input+cacheRead+cacheWrite，输出为 output；这是 Pi 报告的
总提示量，非独立测量或计费量。prepare 拒绝复用现有 TaskReason，不扩展 A7 词汇。

所有者接受 §2.4 的有限扩展：Pi 强制追加的 cwd 段只能是不含个人信息、每次相同、
内容无意义的常量执行 cwd。A8 核对 system 补丁形状和登记 preamble，不选定常量；
具体常量、白名单、无项目资源与实际隔离须由生产启动器票回到所有者确认，并在任何
真实调用之前验收。系统指令以启动期输入单独交会话工厂，不拼入 user 消息。

2026-10-18 补充（供给与升级决策，[主方案 §7.8](../../intent/draft.md)）：用户裁决每次 Pi 升级都必须新建适配器声明版本并重新登记，不允许以“仅审计版本”复用原语义材料原地改写 `pi_version`；V1 不承诺脱网重建执行环境，也不交付预存 npm/Node 制品；`pi_version` 保持严格三段正式版本，不支持预发布或四段版本；保留当前与最近三个旧安装，清理只能由用户先出计划再执行，且不删除当前、在途引用与最近验收通过的版本；每份供给清单必须记录升级的行为影响判定、依据与证据引用，后两者按“可能影响”处理。这些决策不改变“锁定版本不构成兼容性证明”，也不把安装树、`supply_id` 或审计版本提升为阶段语义；供给命令、安装器、清理与验收仍待后续实现。
