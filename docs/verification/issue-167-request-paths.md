# #167 A3：固定源码请求路径核查

2026-11-07，基线 `c0bee235f4ebb0a88be4a60c392c96619ec61683`。本次只读工作区 EXP-2 固定安装的包源码，未启动 Node/Pi、未联网，未读认证文件或 token 派生值。供给/实例及 20 项已登记材料重新哈希结果见 [A1](issue-167-facts.md)。本文件的额外源码阅读不是扩充旧 20 项冻结清单，也不是实际请求计数。

## 调用路径与受控范围

以下上游路径均相对 `app/node_modules/@earendil-works/`。核查对象是首批 `openai / gpt-6.1-sol / prompt_only / provider_default / chatgpt_subscription`。不是对包内任意 provider、扩展、动态加载或第三方依赖的穷尽证明。

| 类别 | 固定源码接缝 / 开关 | 本轮结论与计数要求 |
| --- | --- | --- |
| 前台 prompt | `pi-agent-core/dist/agent-loop.js` runAgentLoop → runLoop / default stream；`pi-coding-agent/dist/core/sdk.js:194–202` 构造有 provider retry 设置的 Models；`pi-ai/dist/models.js:457–477` stream/streamSimple → applyAuth → provider.stream/streamSimple | prompt 是上层派发，Models 请求观察是中层观察；一个 prompt 不能充当底层请求计数。两阶段两档及 Read 独立绑定 |
| 首批 OpenAI 路由 | `pi-ai/dist/providers/openai.js:7–30` 指定 `openAIResponsesApi`；`pi-ai/dist/api/openai-responses.js:132–160` 构造 client 并执行 `client.responses.create(...).withResponse()` | 首批直接 Responses 路由；`options.fetch` 由 createClient 接入。实际网络调用次数须在请求出口独立观察；onResponse 只覆盖收到响应的路径，会漏连接前/响应前失败 |
| SDK/供应商 retry | `openai-responses.js:144–153` SDK 单次 `maxRetries:0`，外包 `retryProviderRequest`；`pi-ai/dist/utils/provider-retry.js` 中每次重试重新执行 request；`sdk.js:194–202` 映射 `getProviderRetrySettings` | 生产 settings `retry.provider.maxRetries=0` 抑制该层。不能只看 SDK 的0就漏掉外层循环；每个实际发送尝试均计数。重试 wrapper 的观察不等于真实传输观察 |
| Agent retry | `pi-coding-agent/dist/core/agent-session.js:3090–3099` 的 `_prepareRetry` 先读 `settings.enabled`；settings 中 `retry.enabled=false` | 禁止自动 Agent 重试；RPC 内核额外回合拒绝是事后协议防御，不能据此证明底层未先发请求。与 Python task attempt 上限分别记账 |
| Cache warmer / 预热 | `agent-session.js:683–690` 在 settled 事件前调用 warmer；`cache-warmer.js:91–93` mode off；`:200–245` timer→refresh→models.streamSimple(maxTokens1,maxRetries0) | `cacheWarming=off` 是关闭依据，仍需完整实际窗口计数。仅在 settled 后观察会漏掉这一路；预热应另计类别，不能因不属于主输出就排除 |
| Compaction / summarization | `agent-session.js:2391–2394` 自动 compaction settings guard；该文件 compaction、branch summarization 与调用 streamFunction 的路径（含3340、3578附近） | `compaction.enabled=false` 只关闭相应自动路径；显式 compact/branch/其他 RPC 命令必须由有界命令集拒绝，扩展资源关闭。总结模型调用若发生也要计数，不能只hook前台prompt |
| 后续 turn / follow-up / tools | `pi-agent-core/dist/agent-loop.js:178–212` 的 continue、steering、follow-up 路径 | 空工具与禁资源/队列初始化、RPC封闭事件共同约束。对任意扩展代码无穷尽保证；未批准命令/额外请求立即停止，A4出站策略不能替代请求级观察 |
| 宿主认证 CLI | PaperRadar `pi_execution/auth.py` 以固定受保护 CLI 取 bearer；固定包 auth resolution 路径为 `pi-ai/dist/auth/resolve.js:62–115`，低寿命 OAuth 在锁内 refresh 并持久化 | CLI调用计数独立于 refresh HTTP。锁等待取消与已经开始的 refresh/持久化不同，源码明确 refresh 开始后使用独立有界时限。父调用结束不能直接当刷新已经停止，需宿主角色/cgroup回收观察 |
| 首批宿主 refresh HTTP | `pi-ai/dist/providers/openai.js:14–19` → lazy ChatGPT OAuth；`pi-ai/dist/auth/oauth/openai-chatgpt.js:172–183` refreshAccessToken→requestToken；`:110–128` 对 TOKEN_URL fetch；`:258–260` refresh/toAuth | requestToken 是登录授权码交换与刷新共享函数，应在入口按受控 operation 类别区分；首次 login/浏览器回调不是本轮刷新配额。只记类别/次数/关联，不记录参数、headers/body或异常原文 |
| 模型进程 auth | `pi_execution/launcher.py` 明确 env 的短期 OPENAI_API_KEY；隔离不放行宿主凭据目录；`pi-ai/dist/auth/resolve.js:17–38` 区分显式 key、stored credential、ambient route | 本轮沙箱不应有 stored OAuth 或 refresh 能力；不能只靠这项推导独立证明现场零刷新。认证与模型出口必须分角色观测。读取 token 内容来判定路线不是本票观察方法 |
| 替代 provider：Codex HTTP/WS | `pi-ai/dist/providers/openai-codex.js` 指定另一个 `openAICodexResponsesApi`；`openai-codex-responses.js:187–246` 默认auto，WS特定错误重试及首事件前转SSE；`:261–324` SSE独立retry；`:1179–1212` WS response创建/续接 | 这是固定包中的替代 provider 路线，**不等于首批 openai 实际走WS**。future路由变更时仅hook fetch会漏WS；maxRetries0仅限相应SSE循环，不自动关闭WS特殊重试/降级。首批若出现WS即绑定漂移，不能无授权采纳。连接握手与response.create还应分别计数 |
| 其他 provider / OAuth / MCP | 包内另有 openai-codex、Anthropic、GitHub、Kimi、xAI、OpenRouter 等 auth fetch，及 MCP OAuth；本轮只做文件定位，无逐条穷尽核验 | 首批模型/auth/provider闭集与 `--no-mcp`、禁extensions共同限定可达范围。任何改 provider、MCP/extension 或自定义 fetch/transport 都使适用性重新审查；不允许以本表宣称覆盖它们 |

## 观察方案结论

1. 必须分别记录 prompt、CLI、模型 HTTP send、认证 refresh HTTP send、TLS连接/packet。若支持WS，另分握手与response.create；首批WS预期为0。中层 Models hook 可辅助关联前台/预热/总结，但不能代替最低实际发送接缝。
2. 在出口仅保存封闭类别、角色、合成关联ID、单调序号/次数及观察完整性；请求内容、认证、完整流和第三方异常原文均不进回执。缺hook、动态绕过、观察失败或类别未知应阻断，不能填0。
3. 合成对端只能验证计数器遇到显式事件时如何计数/拒绝，不证明固定 Pi 中所有实际调用都会经过该接缝。本轮没有把自定义 fetch/SDK patch、解密代理、安装/启动策略变更作为自动授权的实现细节。
4. 固定SDK的fetch与第三方OpenAI client的实际传输实现、动态加载、依赖内部连接/重定向及宿主网络路径尚无端到端覆盖证明。实际可部署的无秘密底层接缝仍须与固定安装/策略绑定，若必须换供给或改启动策略，先 H1/H4；真实计数与新调用计划由 H2/H3 授权。现阶段模型HTTP与refresh实际次数继续 unknown。

## 对准入的影响

A3 已补限定路径清单和离线计数方案；**不能据此把“所有请求路径已真实观测”改为 passed**。当前没有适用于固定供给的完整出口采集桥接，所以 A6 真实调用仍受该前置阻断。额外调用/刷新上限不是追加预算许可；源码发现路径也不是已消耗次数。所有者若裁决有限探索，需逐项保留未验主张及阻断对象。

## 本次额外源码材料身份

下表由本次只读计算，供复核此次推导，不追溯修改旧来源摘要。

| 相对路径 | SHA-256 |
| --- | --- |
| `pi-coding-agent/dist/core/sdk.js` | `992a539079e42f9dc577064e971afa9972a01dbffedb035f7cb68ab204d36964` |
| `pi-ai/dist/models.js` | `de6323034ca216eefecdfc44dd5c93f22713b34a01f2eb21a6d0a5ce85f9bb19` |
| `pi-ai/dist/providers/openai.js` | `9dc3881e858b0280e809ec04b8b17f22580fcb1871da2edf3cfbdfa3c13747b3` |
| `pi-ai/dist/api/openai-responses.js` | `002f15414b7c7b62a32610a8a915bdf1a01eed930b8b45d7691e8a5c475fa9b5` |
| `pi-ai/dist/utils/provider-retry.js` | `46da2f14c0f5d58164a44c1b2837d8ab7674ded3ae4c732d02ae62c87b39b939` |
| `pi-ai/dist/auth/resolve.js` | `3fcec09018831324d9c7fb02f4aea707e8a9e4fec5a2bdf1b3d84d716fd3091e` |
| `pi-ai/dist/auth/oauth/openai-chatgpt.js` | `4cf9fc758a07ffe4ee022326404b5dcc86767ee4154945c0417c7f95eaecdcc2` |
| `pi-ai/dist/providers/openai-codex.js` | `44087142be22adfd09cf1a87edbbdb74ce155b5fd34e70fa4666f3a9f8a9a680` |
| `pi-ai/dist/api/openai-codex-responses.js` | `339c75c5799ec3baca669114e3779988f819a5479e2b2c43dfa0b0f05b921c92` |
| `pi-ai/dist/auth/oauth/openai-codex.js` | `0b94a219ddb5982f0ee543ef03138ed0254ce6ee0a57c9d89d39c242e2eaf6f6` |
