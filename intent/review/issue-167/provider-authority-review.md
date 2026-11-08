# #167：固定模型、参数与订阅通道的官方资料复核

本文件是供 H4 审阅的一次性研究材料。检索日期为 2026-11-08；时间核对点为 02:28 UTC（10:28 上海时间）。只研究固定元组 `openai / gpt-6.1-sol / prompt_only / provider_default / chatgpt_subscription` 及 `low/high`，不改变配置、准入规则或既有历史结论。

官方资料已明确公布 `gpt-6.1-sol` 及其 `low/high` 配置支持，也有直接适用于开源客户端订阅 OAuth 的公开说明。它们补充“供应商公布的模型与配置语义”这一层；当前固定 Pi 实际请求是否获得对应效力、日期 alias 的确切对应关系、当前账号实际可用模型与剩余额度，仍无本轮证据。公开能力声明不能直接登记为当前运行验证通过。

## 逐主张与适用边界

| 主张 | 实际打开的官方来源及支持范围 | 本轮不能据此证明 |
| --- | --- | --- |
| 精确模型 `gpt-6.1-sol` 已公布 | [GPT-6.1 Sol 专页](https://developers.openai.com/api/docs/models/gpt-6.1-sol) 明确模型 ID；[API changelog](https://developers.openai.com/api/docs/changelog) 的 2026-09-29 项记录发布。这里的日期是发布记录 | 当前账号已获授权；Pi 本次实际服务的底层快照；发布日就是可调用日期模型后缀 |
| `low/high` 是该模型公开支持的 reasoning 配置 | [模型专页](https://developers.openai.com/api/docs/models/gpt-6.1-sol) 列出 `reasoning.effort` 支持 `low, medium, high, xhigh, max`，缺省为 `medium` | Pi 的 `thinkingLevel` 或请求回显已经证明供应商处理了该字段；每次 high 都比 low 质量更好；固定任务质量已通过 |
| reasoning effort 有公开行为语义 | [ChatGPT Learn Models（CLI）](https://learn.chatgpt.com/docs/models?surface=cli) 说明 effort 调节思考工作量，较高档位可能改善复杂任务，并增加耗时和 token；可用控制受账号、客户端和 workspace 影响 | 两次输出或耗时差异能识别因果效力；某次延迟长就说明 high 生效；API 缺省值等于所有客户端缺省值 |
| 存在适用于开源客户端的 ChatGPT 订阅 OAuth 通道 | [Models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference) 明确使用 OAuth access token 调用公共 `POST https://api.openai.com/v1/responses`，示例恰为 `gpt-6.1-sol`；要求 `store=false`、`stream=true`。SDK 的参数名 `api_key` 在该示例承载 OAuth bearer，不能据名称解释为 API key 计费 | 只因 endpoint 与普通 API 相同就套用 API key 的账户层级、配额或定价；当前 Pi 版本与账号已经满足此通道全部要求 |
| Pi 属于官方列举的开源集成 | [Sign in with ChatGPT](https://learn.chatgpt.com/docs/sign-in-with-chatgpt) 的开源集成名单包含 Pi；使用计划与单纯登录为分开的授权 | 官方验证过 PaperRadar 的固定 Pi 1.4.0、启动参数、当前凭据、账户与每次推理；名单等于项目部署认证 |
| 账号可用模型需要账号级事实 | [Models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference) 要求用同一账号 token 获取其模型目录；还明确 Codex app-server 的目录可能为 bundled/cached | 本地或公开 catalog 就是账号当前权威可用集合；目录支持档位就说明实际推理生效。本轮没有执行该认证请求 |
| 订阅使用量是共享资源，并有 app cap | [Sign in with ChatGPT](https://learn.chatgpt.com/docs/sign-in-with-chatgpt) 说明 app 使用消耗原有计划限额，不新增额度；app 的每周百分比上限不是预留额度。[Accounts and sessions](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions) 说明 Plus 的五小时限额跨所有使用该计划的 app 共享，Pro 不适用该五小时限额 | Pro 没有任何其他限制；当前账号属于哪种计划、Pi 的 cap、剩余量或重置时刻；有 app cap 就已经为 Pi 保留了可用余额 |
| 公开使用估计不能替代当前余额 | [ChatGPT Learn Pricing](https://learn.chatgpt.com/docs/pricing) 说明模型、上下文、reasoning、工具及缓存影响用量，公开消息数量是估计；API token 价格与订阅使用分开 | 从 prompt 长度、旧六格 Pi usage、API RPM/TPM 或 API 余额倒推本次订阅可用次数；把 Codex 消息估计直接当 Pi 的固定调用额度 |
| 订阅超限错误也有有限解释 | [Errors and recovery](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery) 将 `subscription_sharing_usage_limit_exceeded` 列为 429，明确不能单凭它断言整个计划耗尽或推断重置时间，因为也可能是 app limit | 已发生过该错误；故意超额测试有必要；RPC 本机错误可以冒充真实供应商 429 |
| 通道能力必须与通道自身约束相交 | [Preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations) 明确该订阅路线适用的输入/参数/工具限制，含省略 `temperature/top_p` 等字段 | API 模型页列出的所有能力都在订阅路线可用；本文准许新增工具、参数或其他 endpoint |

以上均是供应商公开文档支持的声明或其明确边界，不包含本轮账号探测。公开订阅文档的存在，纠正了“只能找到 API key 材料”的研究缺口；它没有消除固定部署与账号事实的缺口。

## 日期模型、alias 与实际效力的保留项

[模型专页的 Snapshots 节](https://developers.openai.com/api/docs/models/gpt-6.1-sol) 在本次获取内容中仅列出 `gpt-6.1-sol`，没有列出日期后缀模型或该名称到日期 snapshot 的映射。2026-09-29 的[发布记录](https://developers.openai.com/api/docs/changelog)没有建立该映射。本轮没有找到适用于这条订阅路线、明确说明该名称是否固定或何时滚动，以及供应商响应可能返回何种日期名称的官方政策。**这是检索范围内的未确立事实，不是“该模型／日期模型不存在”的结论。** 不猜测 `gpt-6.1-sol-2026-09-29`，不引用别的模型的 alias 规则代替。

项目 [pi-rpc Contract](../../../docs/contracts/pi-rpc.md) 已区分 Pi 请求回显与可选供应商侧 `responseModel`，并对已出现的 `responseModel` 严格核对，不维护日期 alias 表。[剩余准备材料](remaining-after-six.md)记录固定实现目前没有把这些供应商字段完整投射为可信效力证明。本轮没有重新审计固定源码，也没有实际响应可核对。公开配置语义、Pi 参数映射、实际供应商处理和质量验收应分别保留；不能从成功输出、耗时、token 变化或 catalog 猜出实际效力。

当前[规格 §7.7](../../draft.md#77-pi-rpc-适配边界)仍要求日期别名政策、模型能力等准入；[ADR-0048](../../../docs/adr/0048-accept-bounded-request-observability.md)只裁决请求可观测性与 Pi token 预算口径。它没有预先豁免本文件的参数效力、alias 或账号限额缺口。本文件不将任何 unknown 改为 passed，也不改 Contract 的 strict mismatch 行为。

## 供 H4 选择的低成本补充材料

以下是待所有者选择的材料方案，不是现场执行授权，不新增默认调用预算。

| 补充方案 | 具体最小材料 | 成本、可解决范围与保留项 |
| --- | --- | --- |
| 公开语义先纳入研究依据 | H4 可逐项认可上表的模型存在、effort 公布支持、订阅 OAuth 与共享限额语义为“公开资料已支持”；保留固定运行效力 unknown | 无新认证／模型请求。只能补公开依据，不能以认可公开资料替代现场准入 |
| 所有者提供当前账号的非秘密界面声明 | 所有者自行核对已登录设置，提供核对时间、计划种类、用于固定 Pi 的同一账号／app 的对应声明、是否授予计划使用、app cap、是否允许额外 credits、可见剩余百分比及重置时间；缺字段写 unknown，隐去邮箱／账号 ID／client ID／凭据及其他 app 信息 | 通常一次人工只读核对，模型请求 0；本轮 agent 不登录、不访问私有界面、不读 token。只能证明该时点及所见字段，无法预留额度，也不证明推理支持或日期 alias |
| 针对效力与日期 alias 的供应商权威补充 | 若公开文档仍不明确，请所有者提供适用于开源 Sign in with ChatGPT / 公共 Responses / 精确 `gpt-6.1-sol` 的官方答复或官方页面：low/high 的保证边界、是否允许返回日期名称、精确映射及更新规则；记录取得时间与适用通道 | 本轮不向外发送消息。无需为“看是否更慢”另发模型请求；取得答复的人工成本未知。一般 API 或其他模型的答复仍不足 |
| 保持 corresponding unknown／阻断 | H4 逐主张列出接受的有限探索事实、仍阻断的准入对象、补证责任与后继条件；若保持原标准，则缺证项继续阻断 | 模型请求 0。只有所有者明确的新裁决才可能改变适用要求；本文件不自行接受豁免或用“已移交”宣布完成 |

不建议为核实额度故意耗尽计划，或为参数效力增加两次比较调用；这些动作有成本且不能保证解决问题。即使以后考虑官方账号模型目录请求，也需要独立的认证访问授权与无秘密材料方案；本轮不执行。

## 检索记录与执行边界

先读取根 AGENTS.md、OpenAI Docs 与 research 技能，然后第一实质研究动作即官方域 search，并实际 open 模型专页、CLI Models 与 Reasoning models；没有先检查代码或读取 route reference。后续沿官方订阅文档打开正文，只使用 `developers.openai.com`、`platform.openai.com`、`learn.chatgpt.com` 域。未跟随指向账户、Help Center 或其他域的链接。

检索包含下列精确 query（域过滤同上；Codex reasoning 查询限 developers，订阅初查限 developers／learn）：

- `"gpt-6.1-sol" reasoning`
- `Codex reasoning effort low high`
- `Codex ChatGPT subscription OAuth limits`
- `"gpt-6.1-sol" snapshot alias`
- `Codex authentication ChatGPT subscription OAuth limits`
- `"chatgpt_subscription" "gpt-6.1-sol"`
- `"Sign in with ChatGPT" OAuth limits third-party`
- `"gpt-6.1-sol" "2026-09-29" snapshot`
- `"gpt-6.1-sol" "reasoning" "chatgpt.tokens.use.direct"`
- `"gpt-6.1-sol" "snapshot" "alias"`
- `"chatgpt_subscription" limits`

`chatgpt_subscription` 在本文件首先是项目绑定名称；搜索没有给出把这个字符串定义为官方计费／协议名称的直接规范。通道适用性以公开 Sign in with ChatGPT 文档和项目当前绑定分别论证，不能仅凭同名或无命中判定。

正文以实际打开的 HTML 为据。尝试 `.md` 页面时 web 工具报不支持 `text/markdown`；Responses create reference 的完整 open 因内容过大失败，未把其 search snippet 当已读证据。未引用失败页面支撑结论。动态页面可能在以后变化，本材料记录的是本次读取范围，不是永久快照承诺。

只新增本文件；没有修改原历史材料、规格、ADR、Contract、登记或路线图。没有执行 Pi/Node、认证、刷新、模型请求、DNS/TLS、宿主配置、真实安装锁或业务数据库；没有读取凭据、token 派生值、进程环境、内存、日志、core 或 root ledger。未运行 Python、现场测试、完整离线门禁；本轮验证限于官方正文及本文件的引用／差异检查。
