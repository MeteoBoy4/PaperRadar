# A8 逐项要求与绑定台账（实施中）

父规格 [#85](https://github.com/MeteoBoy4/PaperRadar/issues/85)，顺序子票 #86→#87→#88→#89→#90→#91。
正文与评论合并读取，较晚明确裁决优先；D1–D4/P3 已接受。#86 基于本地 `7473c1c`，
工作树外只读 scope 审计已执行，结果 affected_groups=[]、无哈希漂移。审计不是验收。

## 绑定边界与归属

#86–#90 全部新增代码/测试/材料不修改既有 A1–A7 源码、支撑、固定分母或验收脚本。
GLOSSARY、README、ADR-0026、adapter-config/screening-tasks/pi-rpc Contract、draft
不在当前直接文件绑定中；最终仍由 #91 根据实际 scope 闭包一次重绑，不凭静态清单猜测。

| 工单/要求 | 实现与材料归属 | 验证归属/目前状态 |
| --- | --- | --- |
| #86 AC1，D1–D4/P3 文档一致 | GLOSSARY；ADR-0026；intent/draft §2.4/7.7；adapter-config、screening-tasks、pi-rpc | 同票文档审查；不修改父 Issue 正文 |
| #86 AC2，规格逐项与哈希边界 | 本台账；只读 audit-verification-scope 基线报告在工作树外 | #91 重新实际审计并闭包重绑 |
| #86 AC3，独立真实配置档案库 | tests/a8_call_support.py；真实 migration/config/PaperFacts | test_a8_call_description.py、test_a8_request_vectors.py |
| #86 AC4/5，双 snapshot/封闭 1.4.0 准入 | llm/models.py、calls.py；test support prepare_call | 审计升级同预算/同字节、未登记版本先于领取；test_a8_call_description.py |
| #86 AC6/7/8，历史只读/拒绝/P3 | llm/calls.py；a8_call_support.prepare_call | test_a8_call_rejections.py；数据库字节与次数不变；无会话工厂入口 |
| #86 AC9/10/11，渲染/隔离/修正 | llm.calls.render_request；render_format=1；request-vectors.json | 两篇×两阶段×三类请求，12 个独立完整字节向量 |
| #86 AC12，跨进程与恶意文本 | tests/a8_call_worker.py；固定向量 | test_a8_request_vectors.py；不同 hashseed/cwd、删除当前配置/Prompt 后历史重建 |
| #86 AC13，20 份材料/三态来源 | tests/fixtures/pi_rpc/1.4.0/README | 20 个哈希实际复算一致；DOC/DERIVED-01…10/SYNTH；不是运行观测 |
| #86 AC14，生产前置与可证明范围 | pi-rpc Contract 的 D4/not_assessed；adapter-config 与 ADR | 逐 DERIVED 编号留待生产启动器；autoCompaction 只证明读回值 |
| #86 AC15，术语/依赖/隐私 | GLOSSARY；llm/models.py 与 calls.py | test_a8_llm_architecture.py；repr/log/stdout/stderr 隐私负例 |
| #87 AC1/2，单次公共服务/显式会话/A7 接线 | llm/rpc.py、rpc_types.py；tests/a8_rpc_task_support.py | test_a8_rpc_boundary.py：真实迁移/任务/接收/原字节，无生产来源 |
| #87 AC3，LF/UTF-8/JSON 严格外层与上限 | llm/rpc_frames.py；rpc.py 的流量计数 | test_a8_rpc_protocol.py：1/2/13 字节分包、CRLF、中文/emoji/U+2028/2029、重复键/非有限数/尾帧/超限 |
| #87 AC4/5，串行初始化和干净回读 | llm/rpc.py 固定命令链与发送前无主响应拒绝 | test_a8_rpc_protocol.py：模型重置档位、开关 ACK、模型/档位/队列/sessionFile 回读 |
| #87 AC6–10，ACK 与完整正常候选 | llm/rpc_messages.py；tests/a8_rpc_support.py 固定合成形状 | test_a8_rpc_protocol.py：started、ACK 不足、完成早于 ACK、重复终局、正常关闭 |
| #87 AC11–13，模型归属/权威接收/失败结算 | A8 test 接线转精确 SuccessCandidate/FailureReport | test_a8_rpc_boundary.py：model_mismatch、output_invalid、剩余一次、失败隐私；A7 不改 |
| #87 AC14/15，固定上限与前置/隐私 | rpc_types 常量；validate_request；A8 prepare 映射 audit snapshot 损坏 | test_a8_rpc_preflight.py：audit 损坏、外层转义膨胀均 0 预算/0 会话；期限常量关系 |
| #88 AC1，value 历史同源接收 | 既有 a8_rpc_task_support.run_attempt，无新增接收规则 | test_a8_rpc_value.py：历史配置切换并删除原目录、两种冻结语言标记、回读 ValuePredictionOutput；标记不发送 |
| #88 AC2–4，事件/角色/枚举/输入边界 | llm/rpc_messages.py；固定合成会话 | test_a8_rpc_candidates.py：允许六类 update；完整禁用事件、空 queue、角色、未知枚举、重复/缺结束、system/user 违例，精确原因 |
| #88 AC5/6，完整消息和停止/文本 | 完整副本递归类型比较；text 原序拼接 | test_a8_rpc_candidates.py：bool/整数伪相等红→绿；矛盾副本、签名/redacted、diagnostics/endTurn、多 text、无 text 与非 stop |
| #88 AC7/8，D2 模型与档位命名空间 | 最终 provider/responseModel→A7；规范 thinkingLevel 核对 | test_a8_rpc_candidates.py、test_a8_rpc_value.py：缺必需/可选字段畸形、responseModel 优先、日期模型不符、第二次模型修正、provider 档位不比较 |
| #88 AC9–11，D3 用量与审计身份 | rpc_messages._usage；DERIVED-08；Contract | 严格数值/成本/四项和；零未知；reasoning/cacheWrite1h 不重复；流式用量不拼接；RPC/responseId 不填 provider_request_id |
| #88 AC12，合法近界合并帧 | DERIVED-11；固定 256 KiB/64 KiB/4 MiB/16 MiB | test_a8_rpc_candidates.py：同时接近请求/候选/agent_end 边界，三份回显含 thinking/signature；超候选不返回半结果 |
| #88 AC13/14，权威业务拒绝与隔离 | test_a8_rpc_value.py；既有 12 请求向量 | 评分、未知/禁用/重复主题、中文显示题名、坏内层 JSON/空文本均 output_invalid；失败原文不落盘；第二篇独立会话可继续 |
| #88 AC15，原因全集/依赖/隐私/来源 | 封闭 RpcReason/RpcCategory 表；既有 A7 四种 executor FailureKind | 两文件穷举映射及 repr/log/数据库/制品隐私；Contract、来源 README、DERIVED-11 同步；A7 绑定不改 |
| #89 AC1/2，已启动句柄/并发管道/背压 | llm/rpc_pipes.PipeSession；a8_pipe_support/worker | test_a8_rpc_pipes.py：共享组先拒绝、大 stdin/双输出背压、stderr 洪泛不泄漏 |
| #89 AC3/4，注入时钟/有限资源/租约 | rpc.py、RpcLimits 常量；总期限含初始化/正常排空，取消另用 close 宽限，整组回收另用 terminate | test_a8_rpc_lifecycle.py：fake 无 sleep、精确期限、写入/读取/关闭期限；既有小于 600s 常量关系测试继续通过 |
| #89 AC5/6，取消锁定/正常收尾/整组终止 | clear_queue→abort 匹配 ACK；settled 后即时关 stdin 不发命令；成功也清整组 | 两测试模块：丢/错 ACK、半帧取消、迟到完整输出不可翻转；leader 退出且孙进程已关 pipes 仍回收 |
| #89 AC7/8，异常分流/A7 语义不变 | 原 RpcReason/RpcCategory→既有 FailureReport；finally 清理 | lifecycle：原样 KeyboardInterrupt/SystemExit，attempt 未结算，601s 按既有规则 outcome_unknown；受控失败 origin=executor |
| #89 AC9–12，真实夹具/敏感边界/隔离失败/权限 | 纯标准库 Python/最小 env/deny_external_io；Linux pidfd+/proc；Contract/DERIVED-09 | 6 类场景加背压/孙进程变体及共享组拒绝，共 9 个实际进程用例；正常/取消均核对 pidfd、pipes、句柄数与空 fixture 目录；前篇失败后另一论文可成功 |
| #90，预算/接线/非空恢复 | A8 test executor 支撑与组合测试 | 待 #90；不改 A7 预算或失败词汇 |
| #91，独立组/可信终态/集中重绑 | a8_scope/a8_acceptance、registry/status/check-offline 与文档 | 待 #91；固定分母、同次真实回执、可信终态全部必须交付 |

## 测试边界与后续验收

已由 #85 Testing Decisions 确认：最高业务 seam 为 ScreeningTasks.run_once → 公共
RPC 单次调用 → 既有 A1/A7 接收和制品库；描述/渲染和协议错误通过公共服务集中验证。
#86 prepare 只读、尚无会话工厂，因此不会实例化外部会话；后续 run_attempt 的拒绝
用例须同时断言工厂零实例化、已用预算不变与无失败行。prepare 不是预算权威。

#91 收口时固定全部新增产品源码/支撑/fixtures/文档与用例分母；不使用实测数量回填
预期，不改历史证据、scope 不自绑定。状态工具支持 .a8.json，终态绑定完整组；
完整 ./scripts/check-offline 返回 0 且 verification-status=passed/verified/same 后才关闭
#85。A1–A7 原 not_assessed 历史含义保持。rpc_verified/live_verified/stage_a_verified
持续为 false；完整 not_assessed 见 pi-rpc Contract。本台账的“待”不构成已交付声明。

#86 交付前局部验证：新增描述/请求向量/依赖守卫 29 用例通过；新源码与支撑的 Ruff、
严格 mypy 通过；只读 scope 审计仍返回 0。TDD 记录包括初始接口缺失、冻结载荷与对象
字段不一致、合法占位历史快照拒绝类别三轮 red→green。完整全量入口留至 #91 同次
组登记后执行；这些局部结果不替代独立 A8 或完整门禁结论。

## #88 已新增范围与验证

仅修改前票新增的 llm/rpc_messages.py：完整消息副本按类型递归比较，补齐签名/
redacted 及可选 usage 数值类型。继续复用原 run_attempt 与 A1/A7，不新增领域依赖。
新增 test_a8_rpc_candidates.py（按参数矩阵审阅 219 项）、test_a8_rpc_value.py（22 项）；
含前票 91 项的 A8 子集共 332 passed。Ruff/格式与严格 mypy（20 文件）通过；
只读 scope 审计返回 0，affected_groups=[]、issues=[]，无既有哈希漂移。
TDD 红→绿分别为 bool/整数矛盾副本（4）、签名/redacted 类型（3）、可选 usage
数值类型（14）。矩阵数量供 #91 审阅，不替代其独立固定分母及同次实际执行。

本票未运行完整 check-offline；按顺序实施安排由 #91 注册全 A8 后统一执行。
截至 #88 只证明离线协议/test 接线，不代表独立 A8 验收通过；当时管道及取消握手
尚未交付，现由下述 #89 补齐。真实 Pi/Node/模型、生产 cwd 白名单、参数生效与
语言事实生产来源仍未验收。

## #87 已新增范围与验证

新增产品文件为 llm/rpc.py、rpc_types.py、rpc_frames.py、rpc_messages.py；接线/字节会话
支撑为 tests/a8_rpc_task_support.py、a8_rpc_support.py。只修改前票新增的
a8_call_support.py 以映射回执审计 snapshot 损坏，不改任何既有 A1–A7 支撑。
独立新增 test_a8_rpc_protocol.py（53）、test_a8_rpc_boundary.py（7）、
test_a8_rpc_preflight.py（2），按参数化审阅本票 62 个；含前票 29 个共 91 个。
分母在 #91 固定审阅，不以当次实测回填期望。#87 子集、Ruff/mypy 与既有 scope 审计
用于本票验证；完整标准入口与可信终态仍待 #91。真实工厂、管道与取消握手未在 #87 证明。

## #89 已新增范围与验证

新增生产 Linux PipeSession 仅包装已启动的 Popen，不启动 Pi/Node、不构造命令/env/cwd。
selectors 非阻塞双读与部分写；stderr 只计数。终局前关 stdin，排空、退出零之后还须
有界 SIGKILL 整组并用 /proc/pidfd 核验，finally 释放 selector/pipes；能力不可用安全
失败。组回收不等于权限隔离，不覆盖主动逃组。生产任意执行 API 和 A7 代码均未增加。

生命周期新增 36 项（含精确期限、取消 ACK、半帧/迟到、收尾失败、独立论文、中断未
结算及原租约恢复）；实际 Python 夹具新增 9 项，对应正常、挂住、提前退出、双管道
背压/洪泛、取消、持有/已关闭 pipes 的孙进程及共享组拒绝。用 ready pipe 和 pidfd
同步，期限为 200–500 ms，A8 测试无 sleep。实际进程组 9 passed/1.88s；含前票的
全 A8 子集 377 passed/20.07s，最慢用例 0.66s，没有以紧墙钟断言决定语义成功。
Ruff/格式与严格 mypy（25 文件）通过，scope 审计无既有绑定漂移。

TDD 红→绿包含缺少 PipeSession、取消未发送 clear_queue/abort、正常成功未清组、
settled 后取消仍发送命令四个行为缺口。原 A8 正例同步要求成功也清组，没有改变任何
A1–A7 分母/受绑定文件。独立 A8 登记、非空恢复与完整门禁仍依 #90/#91 收口；本票
未运行完整 check-offline，不将当前子集结论冒充阶段 A 或 live 通过。
