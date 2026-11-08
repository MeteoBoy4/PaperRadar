# #167 A3：首批客户端既有事件源核查

本次只读固定安装的明确源码文件，不运行Node/Pi或网络、不读取认证内容。绑定及前台/预热/重试/总结路径沿用[前轮路径表](issue-167-request-paths.md)。本轮补读它明确尚未核查的OpenAI client底层，不能把静态路径当实际计数。

| 既有接缝 | 当前源码事实 | 是否足以直接采用 |
| --- | --- | --- |
| Pi `options.onResponse` | `openai-responses.js:154` 收到响应后回调，参数含status与headers | 漏掉响应前失败；包含不允许保存的headers。不能启用原始输出充当计数 |
| Pi `options.fetch` | `openai-responses.js:138,213–243` 传入client；未供给时SDK自行取得default fetch | 是可替换函数接缝，不是已有受控计数输出；新增hook需要新启动/观察器身份并审阅覆盖 |
| SDK default fetch | `openai/internal/shims.mjs:8–9` 返回global fetch；`client.mjs:240` 初始化为显式fetch或default；`:988–1009`最终调用fetch | 首批默认路径可由此关联，但一次fetch可能内部重定向/连接尝试；仅包裹fetch不能自行证明所有实际HTTP发送数 |
| SDK retry | `client.mjs:752–923` 每次请求/重试/响应有日志；Pi上层另包provider retry，SDK每次maxRetries=0 | 只观察某一层不够；需分别覆盖provider循环、agent循环和底层请求；静态0不能当实测零重试 |
| SDK logger / logLevel | `client.mjs:230–240,752–923` debug经formatRequestDetails接收请求/响应详情，info亦含responseInfo和连接诊断 | 不是仅类别/次数的安全回执，且不覆盖宿主全局fetch刷新。不得打开SDK debug或保存这些外部原文；没看到日志也不证明没发送 |
| 宿主refresh | `openai-chatgpt.js:110–128` 直接global fetch，不经过OpenAI client/logger或模型onResponse | 模型SDK hook不能覆盖刷新，必须单独按宿主角色观察；授权码交换/刷新共用函数也须区分，不能误将新login纳入refresh许可 |
| Node diagnostics/底层计数 | 本轮未运行Node、未取得固定Node内建HTTP实现的逐事件覆盖证明 | 订阅即需要额外运行时代码；不得以“现成event API”为由绕过H4启动策略审阅。要验证发送前失败、重定向、连接复用及丢事件；不读取/保留事件内headers/body |

`CHATGPT_USAGE_URL`在首批文件中用于错误消息提示（:18,186），本轮没有把出现的URL字面量错误登记为一条实际用量HTTP请求。其他provider/身份路由不外推；动态fetch覆盖、代理、依赖内部实现和改变启动配置后均需重核。

## 结论与具体下一步

在本轮核查的首批provider/默认client中，**尚无可直接启用、同时覆盖模型实际发送与宿主刷新、只输出允许元数据的现成输出接口**。这不是证明任何观察永远不可能；O1现有材料仍不足以放行。现有日志/回调均不能把HTTP次数从unknown改0。

建议H4先裁决O2的最小设计：观察代码置于固定安装树之外，以新启动策略身份在目标入口之前加载；按封印角色/案例只输出category/sequence/count/完整性，模型/刷新出口独立，未知transport、观察失败或不完整都阻断。此处仅提出具体差异范围，**没有注入代码、增加参数、开启debug、替换fetch、patch供给或安装CA**。随后先用无凭据合成worker验证，再形成精确差异供H1/H2，不直接发六格模型请求。若O2不能证明底层覆盖，再提交O3新供给/代理的独立取舍，不自动扩权。

新增或变化的观察逻辑也不能解决[core生命周期缺口](issue-167-core-feasibility.md)：真实凭据进入前须单独通过core与宿主边界。探针通过不产生产品read_evidence。

## 本轮材料身份

下表SHA只标识本次只读依据，不扩充旧20项或10项的历史冻结登记。只有这些文件的明确行段经过本轮核查；没有穷尽整个SDK。

| 相对pi-ai包路径 | SHA-256 |
| --- | --- |
| `dist/api/openai-responses.js` | `002f15414b7c7b62a32610a8a915bdf1a01eed930b8b45d7691e8a5c475fa9b5` |
| `dist/auth/oauth/openai-chatgpt.js` | `4cf9fc758a07ffe4ee022326404b5dcc86767ee4154945c0417c7f95eaecdcc2` |
| `node_modules/openai/client.mjs` | `fc5b25a2e1a7a3a0f67e2cf1c21b4bd768d778aaeb877cbc3789088e3e1eca02` |
| `node_modules/openai/internal/shims.mjs` | `c3efc6139ee455036b862c7f83c4d1194b122bd40130d2de90123476bcea0dbc` |

纯只读分析未新增测试；相关组合与范围审计由本轮续办台账记录。
