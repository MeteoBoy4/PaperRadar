# Read 输入保持纯身份，完整帧预算在领取前预留最坏修正

状态：已接受；日期：2026-11-05；依据：[#155 评论 2](https://github.com/MeteoBoy4/PaperRadar/issues/155#issuecomment-6631023698)、[#160](https://github.com/MeteoBoy4/PaperRadar/issues/160)；补充 [ADR-0008](0008-invalidate-artifacts-with-stage-specific-fingerprints.md)、[ADR-0026](0026-control-pi-through-a-bounded-rpc-adapter.md)、[ADR-0042](0042-accept-read-v2-with-final-attempt-degradation.md)。

Read 模型输入既需要真实持久正文，又不能把用途、执行环境和领取规则混入纯阶段身份。
因此 StageInput 格式 1 只绑定正文消费三元组、输出语言和明确历史配置投影；读取持久成员、
v2 上下文预检、请求渲染与预算由独立组合边界承担，根用途与领取资格由事务消费者判断。
不接收裸配置指纹作为语义权威。Profile/模型等输入变化改变指纹，但不替代正文当前性或
让旧配置分析自动失效。三接收/诊断规则只处理候选，不加入模型指纹，不刷新模型预算。

single 模式必须完整发送正文。若只量首次或内层消息，第二次修正可能在领取后才超额，
白耗有限预算。选择完整 UTF-8 rpc-9 帧的保守上界而非 tokenizer 或截断：领取前同时检查
首次与最坏第二次帧，每帧 256 KiB；修正槽为冻结 36 类 × 最长安全路径 192 字符 × 双层
JSON 编码上界 12 字节 + 1024 固定余量。修正由一个公共纯构造器去重、排序并折叠非法或
超长路径为根位置，不拼入模型输出或坏 ID。超额只返回可重算原因，不建持久原因事实。

正文与 evidence 的模型呈现属于适配器语义。现有 bounded-rpc-v1 与 chunking v1 冻结映射
read-render-v1，原页码、锚点和受限占位由持久正文及 context 提供；无另一份可变渲染开关。
呈现或预算语义变化必须升级相应 adapter policy 或 chunking，未知映射拒绝。代价是保守
修正预留会提前拒绝部分原本可能容纳的论文；通用长文由 G 另行演进，不能沿用 v1 改路。
