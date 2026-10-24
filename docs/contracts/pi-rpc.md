# Pi 单次 RPC 调用 Contract

状态：#86 交付冻结调用描述与 render_format=1；#87 交付显式注入会话的单次协议服务、
严格解帧/初始化及 boundary 的 A7 test 接线。value 与完整负例、真实管道及取消握手、
恢复和独立 A8 验收由 #88–#91 完成。以下把已裁决目标与目前证明范围分开记录。
依据为 [#85](https://github.com/MeteoBoy4/PaperRadar/issues/85) 正文及后续 D1–D4/P3。
本 Contract 不新增 migration、业务 Schema、任务来源或生产命令。

## 调用描述与只读准备

公共 `paper_radar.llm.build_call(stage_input, semantic_snapshot, audit_snapshot)` 只
消费已验证的配置/阶段输入公共面。语义 snapshot 必须为任务预算首次冻结的历史
snapshot；执行审计 snapshot 必须为 `get_receipt(receipt_id).snapshot_id` 的历史
加载结果。`tests/a8_call_support.py.prepare_call` 只读取得两者，不读当前 selector、
个人安装、网络或凭据。`load_input` 的 snapshot 来源是预算行，不能用回执替代。

先严格回放 StageInput 并核对对象字段，再核对两份 snapshot 的同阶段投影格式和
projection_id 相等；只支持 boundary/value。系统指令、业务 Prompt、Profile、Schema、
模型、档位、temperature/top_p 和固定策略来自语义 snapshot；`pi_version` 与
`adapter_version` 仅来自审计 snapshot。它们和 snapshot ID/指纹只保存在描述中，不
进入模型消息。审计升级可以共享旧预算和原请求字节，不把执行版本变成语义输入。
描述为不可变值，输入原文、模型名称、请求、系统指令不出现在 repr。

封闭 `PROTOCOL_PROFILES` 仅含 `1.4.0 → pi-rpc-1.4.0-v1`。这是本票离线协议支持
范围，不是生产 rpc_compatibility、固定安装或模型兼容证明。配置可保存其他正式
版本，但 prepare 必须在 `run_once` 前拒绝未登记版本，不领取、不占次数、不写失败。
A8 独立测试档案库通过真实 migration 和配置登记使用非占位系统 Prompt、prompt_only、
1.4.0；不消费或改写 examples 的 1.1.0 与 A4 的 1.3.0 供给材料。

| 描述拒绝 | DescriptionReason | prepare 的既有 TaskReason |
| --- | --- | --- |
| 未登记版本、错误阶段/协议、缺 adapter、未就绪/占位、请求超限 | invalid_context | INVALID_CONTEXT |
| 两份 snapshot 的同阶段投影不等 | projection_mismatch | CONTEXT_CONFLICT |
| 无法回放、对象与载荷不符、材料损坏、其他不可归类错误 | corrupt_reference | CORRUPT_REFERENCE |
| 请求回执不存在 | 沿用 A7 查询错误 | REQUEST_NOT_FOUND |

P3 不新增 TaskReason、GUIDANCE、TaskError 字段或 A7 原因词汇；描述错误不伪造语言
校验的 build_reason/field。异常只有封闭原因，不携原文或外部异常。prepare 不检查
running/lease_expired，不回收、不续租，不作为第二份预算或资格权威。接线顺序为
prepare→run_once；executor 内才准备描述会错误消耗预算，禁止这样接线。

## bounded-rpc-v1 的首次渲染

`RENDER_FORMAT=1`、固定头部精确为 UTF-8 `PaperRadar bounded-rpc-v1\n`，随后恰好一
个规范 JSON 对象；不加尾换行。JSON 固定 ensure_ascii=false、sort_keys=true、
separators=(",", ":")、allow_nan=false。作为 RPC `prompt.message` 再整体编码后，
只有外层完整对象的末尾 LF 是命令分隔；摘要内斜杠/换行不会生成命令。

对象含 stage、prompt、profile、contract、paper、correction；value 另有 topics。
业务 Prompt 精确保留。profile 是按下列顺序的六项 `{name,text}` 数组：background、
core_questions、transferable_methods、available_data_and_tools、
theory_and_cognitive_interests、constraints_and_exclusions；段落文本精确保留。
contract 仅取相应投影的 schema 对象，规范 JSON，不含 manifest。paper 仅含冻结
题名 title、摘要 abstract 和严格布尔 abstract_truncated。value topics 只含启用项
id/name/description，按既有投影 ID 顺序；boundary 没有 topics 键。

correction 始终保留槽位：首次为 null，后续为 A7 在领取后产生的受控说明字符串。
prepare 只可核验 correction=None 的首次字节；executor 用实际 correction 重新渲染。
修正可带 A1 安全字段/类别，不得拼入失败原文、上一轮输出或消息。修正不进指纹，
也不能由是否为空推断 attempt 编号。独立完整字节向量见
[request-vectors.json](../../tests/fixtures/pi_rpc/1.4.0/request-vectors.json)。

系统指令作为 `CallDescription.system_prompt` 的独立 bytes 交会话工厂启动期消费，
绝不拼入 user。模型、档位、temperature/top_p 在描述完整保留；fake 接收这些参数
只证明测试传递，不能证明真实 Pi 已映射采样参数。声明版本/原文件哈希/注释、路径、
时间、内部 ID、期刊信誉、主题权重、其他阶段结果、原题名语言验证标记均不渲染。
语义渲染改变须提升 adapter policy 版本，不能只换 adapter_version 或传输审计版本。

## 公共单次协议与字节会话

`paper_radar.llm.rpc.run_call(description, user_message, factory, *, clock,
cancelled, limits)` 返回 `RpcCandidate | RpcFailure`。user_message 是已渲染 UTF-8
bytes，描述与渲染层之外的协议内核不依赖配置、阶段输入、任务、论文或存储。
必须显式提供 SessionFactory，没有默认 Pi 启动器、命令/env API、PATH 或凭据读取。
factory 每次只创建一个专属会话，接收完整描述及独立的 system_prompt；构造必须有界，
其时间计入初始化/总期限。模型和采样参数在测试工厂可见，不证明生产映射生效。

`ByteSession.pump(pending_bytes, timeout)` 在有限等待内同时推进部分 stdin 写入与
stdout/stderr 消费，返回 SessionEvent：written、stdout、stderr_bytes、stdout_eof、
stderr_eof、exit_code。stderr 原文在会话内丢弃，只传计数。空 pending 仅表示没有待写
数据；关闭输入必须显式 close_stdin()。EOF 与暂无数据、退出未知与退出 0 分开表达；
leader 退出不能替代两条管道 EOF。terminate(timeout) 的契约是有界回收整组，包括
leader 已退出的子孙；生产管道包装器在 #89 实现，不由测试替身冒充产品能力。

validate_request(user_message) 在不开会话时核对实际 prompt JSON 帧上限，返回安全
失败或 None。tests/a8_rpc_task_support.py 的 run_attempt 先 prepare、渲染并做这项
检查，再调用原有 run_once。双重 JSON 转义可能使合法 user 字节膨胀超限，也在领取前
拒绝。预算首次与本次审计 snapshot 任一损坏都映射既有 CORRUPT_REFERENCE，不泄漏
ConfigError。executor 只核对 StageInput 的 stage/fingerprint/payload，不读取 claim
或猜 attempt，不向对端传续租能力。

正常结果是未验证的 RpcCandidate，原始文本及 provider/model 隐于 repr；只在接线层
转换为精确的 SuccessCandidate(executor_kind=test)。失败是封闭原因的 RpcFailure，
其 category 由内核唯一映射，接线层只一对一换成既有 FailureReport。没有生产执行来源。

## 固定协议与生命周期

每 attempt 一个独立会话，一次服务至多一条 prompt；无自动重发、fallback 或重建重发。
stdin 为完整 JSON 对象+LF；stdout 只按 LF 分帧，可剥 LF 前一个 CR，不用 splitlines。
UTF-8 多字节、U+2028/U+2029 和同包多帧保持正确；坏 UTF-8/JSON、重复键、非对象、
非有限数、超限与 EOF 尾帧受控拒绝，不搜索局部 JSON。stderr 并发计数后丢弃。

固定上限：实际请求帧（含 LF）256 KiB、候选 64 KiB、单帧 4 MiB、累计 stdout 16 MiB、
stderr 1 MiB；rpc_types.py 登记初始化 30 s、总期限 300 s、关闭宽限 10 s、
强杀等待 10 s，单次 pump 至多轮询 50 ms。RpcLimits 只允许缩短前四项期限，不能放大。
总期限从工厂构造前开始，包含初始化和正常收尾；关闭还受独立 10 s 宽限约束，失败后
另有最多 10 s 回收等待。保守叠加 initialization+total+close+terminate=350 s，小于
600 s 租约并留余量，不续租。单帧须容纳 prompt+system+候选+thinking，累计
须容纳三份回显。初始化+运行+关闭+强杀等待总界限严格小于 A7 600 秒租约并留余量。
时间使用可注入单调时钟，独立于 A7 UTC 事实时钟；心跳不延长总期限。

控制命令必须严格一问一答，顺序为 new_session → set_auto_retry(false) →
set_auto_compaction(false) → set_model → get_available_thinking_levels →
set_thinking_level → get_commands → get_state → prompt。响应 id/command 逐一匹配，
初始化只容忍已知 thinking_level_changed 通知。set_model 可能重置档位，故档位设置
必须后置；设置后出现不同档位通知也拒绝。发送每条命令前非阻塞消费已到达记录，
无主/重复/预发未来 ACK 不能通过“随后发送对应命令”变成合法。get_commands 必须空；
state 回读固定模型、档位、autoCompactionEnabled=false、
isStreaming=false、isCompacting=false、messageCount=0、pendingMessageCount=0、
sessionFile 缺失或 null。state 无 retry 查询字段，不臆造；开关 ACK 不能证明持久写盘
或隔离生效。autoCompactionEnabled=false 只证明回读值，不能证明没加载项目 settings。

运行允许一组 agent_start/turn_start；system、user、assistant 各一对 start/end；
text_*/thinking_* message_update；空 toolResults 的 turn_end；agent_end；agent_settled。
system content=""、sections 只能有 preamble/cwd、preamble 精确等于描述中的系统
指令，不能有 toolsAdded/toolsRemoved；user 一项 text 必须逐字等于发送消息。
最终 assistant 在 message_end/turn_end/agent_end 中的副本一致；agent_end.messages
为 [system,user,assistant]。partial assistant_start 不要求等于最终消息。

ACK 不是完成；等待唯一 started ACK、唯一完整最终消息、agent_end、未 aborted 的
agent_settled 和正常进程关闭。防御性合成覆盖完成早于 ACK；此时 settled 立即关闭
stdin，只允许尚欠的唯一匹配 prompt ACK 补齐条件，其他后续记录仍拒绝。仅 stop 合法；length、
error、aborted、pending、toolUse、deferred 不合法。额外 turn、工具、queue、retry、
compaction、summarization、extension UI/错误、未知事件/角色/内容块/停止枚举均拒绝。
已知记录的未知附加字段可容忍，必需字段类型严格。发送第一条命令前、settled 后
有额外记录均失败；settled 后立即关 stdin 并排空等待退出，不能此刻提前返回成功。

最终候选只拼接完整 assistant 消息中的 text 块，按原序无分隔保留空白；thinking、
签名不拼接。不从 delta 或 get_last_assistant_text 兜底。没有 text 块为协议失败；
存在空/纯空白 text 则返回候选，由 A1 判 invalid_json。内层围栏、重复键、非有限数、
评分、主题、中文显示题名等均由 A1/A7 原权威路径拒绝，RPC 不清洗业务输出。

取消的完整握手由 #89 补齐：先 clear_queue 再 abort，队列返回原文立即丢弃。#87 已在
每次等待前后锁定超时/注入取消并有界关闭/终止，迟到结果不能翻转，但尚不声称已实现
clear_queue/abort。超时/取消观察后锁定失败，迟到
stop/settled 不能翻转。失联、断管、关闭不响应需有界回收独立进程组。KeyboardInterrupt/
SystemExit 在 finally 回收后原样上抛，attempt 保持未结算，租约到期保守结算 outcome_unknown。
管道会话只包装已启动进程，核对独立进程组并承担双管道消费/有界写入/整组终止；
不提供自由命令或 env 产品 API。进程组回收不是 OS 沙箱。

| RPC 粗分类 | 情形 | 既有 A7 FailureKind |
| --- | --- | --- |
| timeout | 初始化、读写或总期限超时 | timeout |
| cancelled | 注入的取消信号 | cancelled |
| environment | new_session cancelled、模型/认证初始化失败、启动/EOF/断管/异常退出 | executor_error |
| protocol | 关联不符、执行违例、停止/通道/档位/模型回读错误、超限 | protocol_error |

封闭细分原因由 rpc_types.RpcReason 登记；当前粗类固定如下，不回显自由文本：

| 粗类 | RpcReason |
| --- | --- |
| timeout | timeout、close_timeout |
| cancelled | cancelled |
| environment | session_cancelled、model_rejected、startup_error、transport_error、eof、unexpected_exit |
| protocol | invalid_description、invalid_utf8、invalid_json、non_object、duplicate_key、non_finite、frame_limit、stdout_limit、stderr_limit、request_limit、candidate_limit、partial_frame、early_record、response_mismatch、command_rejected、model_state、thinking_unsupported、thinking_state、dirty_state、commands_present、prompt_disposition、event_sequence、event_not_allowed、message_shape、message_mismatch、system_mismatch、user_mismatch、stop_reason、channel、usage_shape |

set_model 失败单独为 model_rejected/environment；其他失败控制 ACK 是
command_rejected/protocol。EOF 前未终止的尾帧是 partial_frame/protocol；正常帧之后
缺少必要完成条件则是 eof/environment 或期限失败。关闭异常不得返回候选。

受控失败返回精确 FailureReport，不抛普通异常、不包装 SuccessCandidate。内层输出
无效由接收器产生 output_invalid；最终模型不符由接收器产生 model_mismatch。一次
run_once 至多一次 RPC，不改变两次预算、retry 代际父链、租约或保守结算。其他论文
失败隔离。A7 续租句柄、数据库能力不传对端。

## D2/D3：执行观察与 A7 权威接收

最终消息必需 provider/model；协议完整时内核不比较最终模型身份，只返回 provider
及存在的 responseModel（否则 model）。provider/model 主要是 Pi 请求回显，不是
供应商证明；responseModel 是可选供应商侧模型信息。接线填 reported_provider/model，
由既有 A7 model_matches 严格比较，不符 model_mismatch 且原文不落盘。初始化模型
回读不符仍属协议失败；thinkingLevel 存在时必须等于请求档位，providerThinkingLevel
是另一命名空间。严格 responseModel 会拒绝某些日期快照别名，A8 不增别名表。

Pi 报告 totalTokens==0 时 input_tokens/output_tokens 都为 null；否则 input_tokens=
input+cacheRead+cacheWrite、output_tokens=output。reasoning 已包含在 output，
不得再加。口径为 Pi 报告的总提示量（含缓存读），不是独立测量、计费输入或成本。
1.4.0 全零初始化无法区别未报告和真实零；缓存拆分、成本不保存，不新增字段。
RPC command ID 与可选 responseId 都不假称 provider_request_id，该字段保持未知。
完整事件、prompt、profile、摘要、thinking、stderr、错误自由文本不得进入 repr、日志、
异常、数据库、制品或验收结果；只保留受控原因、标识摘要、计数和必要成功文本。

## D4、来源推导与 not_assessed

Pi 1.4.0 强制追加 cwd，section 实际是 `<cwd>\n<归一化路径>\n</cwd>`；preamble 不
包装。有效指令=登记声明指令+Pi cwd 段的已知缺口。所有者仅许可不含个人信息、每次
相同、内容无意义的常量执行 cwd；A8 不选常量、不把合成路径用于生产白名单。

来源摘要与三态登记见 [固定材料 README](../../tests/fixtures/pi_rpc/1.4.0/README)。
DERIVED-01(system补丁)、02(cwd包装)、03(user回显)、04(aggregate副本)、05(临时状态)、
06(空commands)、07(ACK/档位顺序)、08(token总和)、09(settled后收尾)、10(请求回显)
都只按源码推导 fail closed，尚未由真实 Pi 运行逐项确认。对应检查只证明与固定源码
一致，不能把其升级成运行观测或生产隔离结论。

生产启动器票必须在任何真实调用前完成以下准入，并逐项按 DERIVED 编号复核：

- 复用相同管道会话和协议内核；启动描述由上层显式构造命令、env、cwd、系统指令，
  没有默认值、不继承宿主环境；每并发会话独立 PI_CODING_AGENT_DIR 或整体串行化。
- 启动前在隔离 PI_CODING_AGENT_DIR/settings.json 预写 cacheWarming="off" 与
  retry.provider.maxRetries=0；两个 RPC 开关会写全局设置，ACK 不证明写入/隔离。
  没观察到预热不等于关闭预热（其触发另有 cache TTL/节省条件）。
- --offline --no-session -ne -ns -np -nc -nt，PI_SKIP_VERSION_CHECK=1、PI_TELEMETRY=0；
  验证禁止自动网络活动（目录刷新、版本检查、遥测、缓存预热、隐含 provider retry）。
- 通过 --system-prompt 精确传入声明系统指令；防止参数被当成文件路径。确认无默认
  prompt、个人设置、项目资源、skills/extensions/MCP、AGENTS.md/CLAUDE.md 等注入。
- 回到所有者确认常量中性 cwd 和白名单；该目录无 .pi/、AGENTS.md、CLAUDE.md 或
  其他项目资源，验证本机路径只在已裁决常量例外内。DERIVED-01/02/03/05/06 必须实测。
- 在领取任何任务前预检固定供给、模型/凭据可用；验收参数映射、单次模型请求、日期
  别名政策、模型能力、实际用量/停止与事件（DERIVED-04/07/08/09/10），落实 OS 隔离。

rpc_verified、live_verified、stage_a_verified 继续为 false。not_assessed 还包括真实 Pi
运行与供给激活、凭据、参数效果、OS 文件/进程/网络权限、自动外发抑制、原题名语言
生产来源、reuse/Read等其他阶段任务、业务资格/编排/每日配额、校准可见性/门禁、CLI、
真实论文来源/Docling/NAS/无人值守。A8 只有离线协议与 test 任务接线证明范围。
