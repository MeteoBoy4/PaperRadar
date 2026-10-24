# A8 逐项要求与绑定台账

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
| #90 AC1/2/3，四类边界与失败映射 | 既有 prepare→run_once；a8_recovery_support 外部故障；全部 RpcReason→RpcCategory→既有 FailureKind | test_a8_rpc_recovery.py：封闭全集、精确类型接收、普通异常/包装/子类负例；TaskReason/Schema 不变 |
| #90 AC4/5/6，每代预算/安全修正/租约 | 既有 A7 claim/status/reclaim/submit 权威；单次 RPC 不续租 | recovery：两次耗尽、日期/新实例/会话不刷新、第三次/成功/在途零会话、prepare 零事实、实际 output_invalid/timeout/outcome_unknown 修正；history：过期未结算可提交、回收后失权 |
| #90 AC7，版本/输入历史与 D1 | a8_recovery_support.audit_upgrade 只创建新声明 | test_a8_rpc_history.py：首次 1.3.0 语义→1.4.0 回执执行/重试，1.3.0 回摆 prepare 拒绝；审计 A→B→A、输入 A→B→A 旧预算与同指纹跨版本 current |
| #90 AC8/9/10，非空 WAL 隔离恢复 | 既有 backup/restore；a8_recovery_worker 复用 A7 路径阻断支撑 | test_a8_rpc_backup.py：两阶段成功/协议与业务失败/retry/未结算，阻断原目录并移动恢复库，新解释器只读查询；唯一恢复后显式继续消耗剩余一次 |
| #90 AC11/12，隐私与文档 | pi-rpc Contract 四边界；无 A7 源码/支撑/绑定变更 | 备份无失败原文/完整事件/thinking/自由错误；原成功字节、test 审计、provider_request_id 未知和安全 issues 保持 |
| #91，独立组/可信终态/集中重绑 | a8_scope/a8_acceptance；a2_full_acceptance、a2_test_receipt、status/check-offline | 新验收测试固定范围见下；最终完整门禁在审查修复后的稳定 integration 执行 |

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

## #90 已新增范围与验证

本票补既有公开服务的组合证据，没有产品源码缺口，也没有为了制造红而改坏既有行为。
新增 test_a8_rpc_recovery.py（16）、test_a8_rpc_history.py（6）、
test_a8_rpc_backup.py（1）与 a8_recovery_support/worker；不改任何 A1–A7 受绑定文件。
prepare、执行失败、权威接收失败与未结算中断分别断言事实有无、次数与会话边界；
所有封闭 RpcReason 经 RpcCategory 穷举至既有四类 executor FailureKind，
output_invalid/model_mismatch/outcome_unknown 继续归 A7 权威接收或回收。

23 项新增组合通过；全部 A8 子集 400 passed/38.59s。单个非空恢复用例 7.59s，
包含同库备份验证及新解释器恢复/查询/一次显式继续，无 sleep；其余用例均小于 1s，
组总时长低于约 60s 的规模目标。两阶段原始成功、失败安全 issues、父链、首次历史
输入和未结算预算在阻断原目录且移动恢复路径后保持可查询；恢复查询没有导入 RPC
执行入口，树和数据库逻辑内容不变。唯一恢复后继续只消耗剩余一次。

Ruff 检查/格式（全部 A8 30 文件）和严格 mypy（src 与全部 A8 测试/支撑，共 178
文件）通过；git diff --check 通过，只读 scope 审计 affected_groups=[]、issues=[]。
提交前已合并当时最新 integration tip 297e092（Already up to date）。新增测试属于
已有能力的组合验证；最初的失败仅纠正测试对安全额外字段路径、取消时机与父链查询
位置的预期，没有改变 A7 接口、词汇、Schema、Frozen Contract 或恢复规则。

完整 check-offline 与独立 A8 组仍由 #91 注册后在稳定 integration 同次执行；本票未
运行真实 Pi/Node/模型、抓流 spike 或任何 live 来源。不把离线合成恢复升级为生产
RPC、权限隔离、采样参数生效、自动外发抑制或原题名语言来源的验收。


## #91 固定验收面与父规格收口

`a8_scope` 固定 ISSUE=85、PARENT_ISSUE=85（父规格身份，实施子票为 #91）、
SUFFIX=.a8.json、格式1、13项能力。直接前置为同次 A1、完整 A2、A3、A5、A6、A7，
A4 保持总门禁必需但安装检查不证明 RPC。`a8_acceptance` 检查实际原始字节链接、
身份、前置范围/格式/通过资格、生产格式、真实迁移 head、依赖与完整回执；发布前再
检查字节。terminal 由既有控制方自然绑定全部必需组；无可信 terminal 不声称成功。

不扩张 A1–A7 能力、分母、a704 head 或四份 Frozen Contract；基础 #12 的 llm 和
A7 历史 not_assessed 保留。A8 自己的 not_assessed 沿用 A7 词汇并补充系统指令/cwd、
生产参数映射、provider retry、cacheWarming、自动网络活动、实际会话资源权限隔离、
模型凭据预检和 DERIVED 真实核实；rpc_verified/live_verified/stage_a_verified 恒 false。

### 人工固定分母

下面逐一阅读测试定义与参数列表后相加，相邻乘数为多重参数化的笛卡尔积；没有用
当次 pytest collection 推导期望。request-vectors.json 独立冻结12项（两篇×两阶段×三类
修正），只用于向量用例参数。后续 `--collect` 仅比较这个人工分母，不能回填期望。

| 模块（均位于 tests/） | 独立推导 | 固定分母 |
|---|---|---|
| test_a8_call_description.py | 6个单例 | 6 |
| test_a8_call_rejections.py | 8个单例 | 8 |
| test_a8_request_vectors.py | 12个向量+2个hashseed | 14 |
| test_a8_llm_architecture.py | 1个依赖边界 | 1 |
| test_a8_rpc_protocol.py | 原53+7档+3描述类型+3通知类型+2合法poll+1放大poll | 69 |
| test_a8_rpc_boundary.py | 1+2+3+1 | 7 |
| test_a8_rpc_preflight.py | 2个单例 | 2 |
| test_a8_rpc_candidates.py | 2×2+3+6+9+22+9+10+9+6+10+6+7+1+5×7+5+5×6+1+1+1+1+7+3×4+3+2+5+2×7 | 219 |
| test_a8_rpc_value.py | 2+7+7+3+1+1+1 | 22 |
| test_a8_rpc_lifecycle.py | 2+1+13+1+9+1+2+2×2+4+1+3+1+3+1+1+2×3×2+2×4 | 67 |
| test_a8_rpc_pipes.py | 1+1+1+1+2+1+2+2×4+2 | 19 |
| test_a8_rpc_recovery.py | 5+3+2+1+4+1 | 16 |
| test_a8_rpc_history.py | 2+1+1+1+1 | 6 |
| test_a8_rpc_backup.py | 1个非空完整恢复 | 1 |
| test_a8_acceptance.py | 2个单例 | 2 |
| test_a8_integrity.py | 6前置×11故障+17回执+7版本×3伪类型+5漂移+1迁移+1中断+10身份伪值+1依赖+4空范围+9基础证据+1材料隐私 | 136 |
| test_a8_entry.py | 1+2发布失败+2字节替换+2总门禁+2嵌套回执 | 9 |
| test_a8_status.py | 1格式支持+9终态/字节/身份 | 10 |
| test_a8_test_receipt.py | passed/skipped/deselected/collect_only/failed/incomplete | 6 |
| test_a8_formats.py | 3个生产格式来源×3种漂移/伪类型 | 9 |
| 合计 | 功能457+验收172 | 629 |

### User Stories 逐项落点

简称 description/rejections/vectors/protocol/candidates/lifecycle/pipes/boundary/value/
recovery/history/backup 均指上表对应 test_a8_* 模块；实际固定绑定以 a8_scope 为准。

| #85 故事 | 落点或范围外 |
|---|---|
| 1 复用 A1–A7 | A8同次六前置+总门禁A4；旧能力/分母不扩义 |
| 2 固定1.4.0依据 | fixtures/pi_rpc/1.4.0/README，20材料哈希与三态来源 |
| 3 隐藏RPC公共服务 | paper_radar.llm.rpc.run_call；boundary/value 经 run_once 组合 |
| 4 只读冻结输入 | description/rejections/vectors/history，双snapshot来源 |
| 5 boundary 无主题/信誉 | vectors 的完整请求字节与 boundary |
| 6 value 启用主题投影 | vectors/value，只有 id/name/description |
| 7 独立调用上下文 | vectors 两篇×两阶段×修正；value/lifecycle 独立论文 |
| 8 参数诚实 | description 字段与工厂断言；生产映射明确范围外 |
| 9 字节分帧 | protocol 任意分包/UTF-8/CRLF/U+2028/2029 |
| 10 有限边界 | protocol/candidates/lifecycle/pipes；rpc_types 固定上限 |
| 11 关联ID/命令 | protocol 精确ID/command/boolean及未来/重复ACK |
| 12 仅started | protocol disposition 封闭拒绝 |
| 13 prompt 前消费 | protocol 极快完成早于ACK防御性合成 |
| 14 ACK/end 不足 | protocol 缺结束事件；candidates 缺终局 |
| 15 settled/正常stop | candidates 停止全集、aborted/willRetry；lifecycle收尾 |
| 16 实际模型不符 | D2：value/boundary→A7 model_mismatch，无原文 |
| 17 档位不符 | protocol初始化/回读；candidates规范thinkingLevel |
| 18 重复表达同消息 | candidates 完整副本/JSON类型严格比较 |
| 19 额外工作拒绝 | candidates turn/assistant、tool/retry/compaction/queue全集 |
| 20 最终完整文本 | candidates 多text/签名/thinking/无text；不取delta |
| 21 权威业务输出 | boundary/value→A1/A7 output_invalid，不修复 |
| 22 可区分生命周期 | lifecycle 精确RpcReason；recovery映射既有FailureKind |
| 23 取消清队列/关闭 | lifecycle/pipes clear_queue→abort 与缺/错ACK |
| 24 迟到不可成功 | lifecycle 锁定取消/超时；history A7失权边界 |
| 25 双管道与隐私 | pipes 背压/洪泛与句柄回收，不持久stderr |
| 26 安全修正与新会话 | recovery/history，真实A7 output_invalid/timeout/outcome_unknown修正 |
| 27 一次预算无重发 | recovery 两次耗尽，每次单prompt |
| 28 成功/耗尽不开会话 | recovery 新实例/日期/第三次/成功/在途均无新会话 |
| 29 协议完整业务无效 | boundary/value/recovery，output_invalid归A7 |
| 30 test来源 | boundary/value/backup executor_kind=test，不新增生产来源 |
| 31 同次审计与零未知 | candidates/value D3，totalTokens==0两项None |
| 32 三类ID区分 | value success审计与backup；provider_request_id=None |
| 33 原候选逐字节 | boundary/value/backup 含首尾空白原字节 |
| 34 失败隐私 | boundary/value/pipes/backup与结论材料篡改隐私 |
| 35 无关论文继续 | value/lifecycle 协议故障后独立成功 |
| 36 真实存储恢复 | backup WAL非空库→阻断原路径→移动恢复→新解释器查询 |
| 37 同次完整证明 | acceptance/integrity/entry/status/test_receipt/formats |
| 38 三类验收边界 | README/offline-evidence/pi-rpc：安装、离线协议、真实RPC分开 |
| 39 普通测试无需个人Pi | 仓库合成材料、Python夹具；architecture/deny边界 |
| 40 语言来源不代裁决 | 原语言严格bool只测试；生产来源仍not_assessed，无模型启用 |

### 实施决定、四条评论与子票 AC

| 来源 | 完整处理 |
|---|---|
| 正文 Decisions 1–3 | llm公共描述/内核/显式会话，无默认真实工厂；只接boundary/value |
| Decisions 4–6 | calls.py 与完整独立向量；bounded-rpc-v1/render1；参数只保留，生产映射未验收 |
| Decisions 7–10 | protocol 串行固定初始化、干净状态、分帧/关联/started，ACK非完成 |
| Decisions 11–14 | candidates 唯一完整消息/事件封闭表；D2覆盖正文旧模型措辞 |
| Decisions 15–16 | lifecycle/pipes 有界取消/终止/中断，封闭安全原因与隐私 |
| Decisions 17–20 | boundary/value/recovery/history 原A1/A7接收、预算、修正、先prepare后领取 |
| Decisions 21–22 | D3覆盖旧零值措辞；value审计/backup非空隔离恢复，未新增持久字段 |
| Decisions 23–24 | #91必需组/完整回执/终态/状态格式、本文与not_assessed |
| 第一次补充 §一 D1–D4 | 按较晚明确裁决；版本、双snapshot、模型接收归属、零未知、常量cwd有限例外 |
| 第一次补充 §二 1–8 | 初始化一问一答、全局开关读回限制、system/user回显、ACK来源、档位、预热限制、三倍回显预算：protocol/candidates及DERIVED-01…11 |
| 第一次补充 §三 1–9 | 描述与修正分离、system启动通道、生产PipeSession包装、期限/租约、中断原样、原因映射、记录/枚举严格度、空text及事件表：vectors/protocol/candidates/lifecycle/pipes/recovery |
| 第一次补充 §四 1–4 | 语义投影固定JSON数据块/非slash头、修正槽位、render_format=1；vectors |
| 第一次补充 §五 1–5 | llm依赖边界、无需A7 API、独立a8支撑、实际scope审计集中重绑与全部文档落点 |
| 第一次补充 §六 | 六子票顺序完成；真实进程9变体/非空恢复1项；可选spike范围外未执行 |
| 第一次补充 §七 | 完整生产准入见pi-rpc，不实现启动器 |
| 第二条评论 D1六条/D2/D3/D4 | description/history版本回摆；A7模型权威；usage严格整数与未知；system/cwd缺口。ADR-0026、draft、Contract已同步 |
| 第二次补充 §一 1–6 | 只读prepare、executor闭包、精确SuccessCandidate/FailureReport、prepare非状态权威、P3旧TaskReason、全部新增测试独立A8文件 |
| 第二次补充 §二 1–5 | compaction仅读回值（不证明未加载项目settings）；全局独立agent目录、预写cacheWarming/provider retry、所有自动网络活动、无会话落盘、并发隔离：生产前置 |
| 第二次补充 §三 | README三态来源与DERIVED-01…11稳定编号；尚无真实运行观测 |
| 第二次补充 §四 1–3 | 先实际audit、静态scope/格式1注册、集中按DAG重绑；不自绑定/不改历史证据 |
| 第二次补充 §五 | fake注入时钟无sleep；短期限Python夹具/最小env+deny；组回收非OS沙箱。功能400项约39秒；非空恢复约8秒，超过约5秒建议但覆盖真实完整恢复边界 |
| 第四条评论 P3 | 按建议复用旧TaskReason/Guidance/词汇格式1，不新增领域拒绝种类 |
| #86 AC1–15、#87 AC1–15 | 上方逐AC表及对应独立模块、来源/向量；本次scope纳入全部字节 |
| #88 AC1–15、#89 AC1–12、#90 AC1–12 | 上方逐AC表及候选/生命周期/管道/历史/恢复模块；不扩A7 |
| #91 AC1 | 实际基线审计无漂移，随后按本节下方DAG闭包重绑 |
| #91 AC2–5 | 固定scope/格式/能力/分母、六前置原字节、40故事、完整真实回执负例 |
| #91 AC6–8 | 同波登记writer/receipt/status/help/terminal、旧scope闭包、本文/Contract/README |
| #91 AC9–10 | 恒false及完整生产前置；未运行任何真实Pi/Node/live/spike |
| #91 AC11 | 适用子集/静态/collect先验证；合并双审与修复后由主agent在稳定commit执行完整check-offline与status same，完成前不关闭#91/#85 |
| #91 AC12 | 不新增安装/启动器/产品CLI/生产来源，不改父Issue内容/状态 |

### 实际 scope 审计与重绑闭包

#91 首次执行正式 `./scripts/audit-verification-scope --json`，基线无漂移、无issues，
affected_groups=[]。完整原始输出保存在工作树外 `issue-91-before-audit.json`。
实际DAG顺序为 a1_scope→a2_scope→a2_full_scope→a3_scope→a4_scope→a5_scope→
a6_scope→a7_scope；a2_scope无下游，a4虽非A5直接运行前置仍在哈希DAG中。

登记修改前读取实际files后确认：a2_full_acceptance/a2_test_receipt直接影响完整A2、
A3–A7；check-offline及完整入口/兼容测试局部适配触及A2-01与完整A2起始绑定（A1范围未漂移），
verification_status触及A6/A7；A4/A5/A6/A7 entry与A6/A7 status仅切换全组回执/当前
份数，既有用例分母不变。历史终端字节对照只排除新增A8输出行，旧固定transcripts原字节不变；带额外合成组的当前总份数为13。最终按实际变更后的audit输出逐层核对，顺序扩展至末尾
新增a8_scope；完整旧新SHA与受影响文件清单保存在工作树外审计报告，避免把最终
run_id写进本台账造成自失效。scope不自绑定，没有为了消除count_mismatch修改旧分母。

全部功能/文档/测试先稳定，再按order更新受触及文件的显式哈希及下游scope；最后
固定A8的llm源码、支撑、向量/来源/能力材料、公共文档、20个测试模块和六前置scope。
collection仅比对当前人工固定分母与旧范围；不运行真实Pi/Node。最终完整门禁证据须由稳定
integration提交产生，任何审查修复触及绑定字节时再次按DAG重绑；旧失败/中断证据保留。


## 双轴审阅修复（#85/#89/#91）

Spec P1：公共 run_call 在成功、受控失败、已有中断三种路径中，清理自身的
KeyboardInterrupt/SystemExit 均先完成有界清理，再保留最初中断对象上抛；已有通信
中断不能被清理中断替换。真实 grandchild_closed 夹具分别在 killpg 前、直接 child wait
和 pidfd 关闭时注入两种中断，以 pidfd 就绪、直接 wait 完成及全部句柄关闭证明回收；
所有断言均先于测试兜底。PipeSession 保留首次绝对期限，清理中断每步至多补做一次，
未完成不能标 finished。A7 在清理中断后仍 running、无失败结算，原租约 601 秒后仅由
既有 reclaim 形成 outcome_unknown；默认小于 600 秒的预算关系不变。

Spec P2：实际重读用户提供 Pi 1.4.0 docs/rpc-commands.md:109–127，仅阅读不运行。
clear_queue 的 steering/followUp 必须同时存在且均为字符串数组。缺 data、空对象、
分别缺字段、字段非数组、数组含非字符串共8种畸形响应不发 abort，立即有界终止并保持
cancelled；合法空数组继续 abort，合法文本立即丢弃。取消握手仍可丢弃迟到事件，
不改变正常 settled 后禁止新命令的规则。

Standards 局部建议：rpc_messages 将事件位置改为私有具名状态，并把状态与预期事件
显式关联；不增加新框架，不改变候选矩阵行为，不为状态命名增加镜像测试。

补充清理入口与期限边界：EOF 后外部时钟第1–4次采样分别注入中断，不能因 helper
已开始而跳过 finally；成功、受控失败、已有中断三路径分别覆盖剩余等待与恰耗尽预算。
真实进程同时覆盖 killpg 中断恰耗尽首次期限与首次 terminate(0)，仍立即 kill/close，
直接 child wait 只传0。测试在产品返回后等待 pidfd 就绪仅为退出证据，不扩产品期限。

人工新增分母：lifecycle 原36 + clear_queue畸形8 + 合法空队列1 + 公共清理中断
2种×3路径×2耗时12 + A7清理中断2 + EOF后时钟2种×4采样8 = 67；pipes 原9 +
2种中断×4个OS/期限边界8 + 首次零等待2 = 19。
新增41项，功能441、验收172、固定总数613。此表先按测试定义推导，后续 collection
仅核对。scope 审计的修复前闭包仅 A8；按实际 DAG 更新必要哈希，不改 A1–A7 的
能力/分母/head。完整 check-offline 仍由主agent在合并并复核后的稳定 integration 执行，
不在本台账写入最终 run_id；真实 Pi/Node、模型及 live 行为均未执行。

## 三份外部审查核实收口（#85/#89/#91）

逐项接受、部分接受及不改的依据追加在 intent/review/ 下三份原始报告末尾，保留原文。
本轮在 llm/models.py 唯一定义 ThinkingLevel Literal，并从 get_args 派生运行时词表；
rpc/rpc_messages 共用，保持内核不依赖配置层。description/通知中的不可信档位先验
str 类型，再检查成员，避免 list/dict 在 frozenset 查询时抛异常而误报 transport_error。
prompt 序号、关联 ID 与命令名局部具名化，wire 仍固定 rpc-9，不改初始化顺序或语义版本。

run_call seam 新增16项：Pi文档七档正常完成7，非法字符串/list/dict描述无会话3，
相同三种畸形通知保持thinking_state 3，默认/缩短poll成功2，放大poll创建会话前
invalid_description 1。先按参数定义推导，protocol从53增至69；功能457+验收172=629。
这些是现行安全行为的补充刻画与重构保护，原代码已通过新增用例，不伪造红→绿缺陷。
既有请求关联、候选、生命周期及架构守卫继续验证没有行为漂移。文案修正包括九组
write_*_conclusion、实际公共服务paper_radar.llm.rpc.run_call、poll同受默认上限约束。

规模说明：#90的400项/38.59s属于当票历史范围；后续登记与审阅修复扩展到613项，
三份外部审查测得完整A8约86–96s，非空恢复约7.6–8.2s。该单例保留真实WAL备份、
阻断原目录、独立解释器恢复与唯一剩余预算继续，不能用删减这条完整链来换墙钟目标。
test_a8_rpc_lifecycle.py::test_a8_tests_use_no_sleep_for_synchronization 已以AST检查
所有*a8_*.py，不再重复新增守卫。依#89补充采用注入期限/终局断言并披露耗时，
不设单例5s或组60s的硬失败阈值；替代规则同步pi-rpc Contract。

本轮先读现行scope审计：修改前无漂移；修改后实际闭包仅A8，8个绑定字节变化。
按审计order集中重绑，A1–A7能力、固定分母、head、格式与四份Frozen Contract不变。
本轮报告加入提交及整体工作树身份，不擅自扩大A8固定材料成员。受绑定台账只记录
验证入口及范围，最终完整check-offline和verification-status由稳定提交产生并在工作树
外保存；旧运行不会因受绑定材料未改就自动保持same，非忽略untracked报告也改变身份。

本轮全部A8子集629 passed/86.29s，最慢非空恢复7.53s；A8相关Ruff检查/格式与
严格mypy（39文件）通过。最终完整门禁仍由稳定提交运行，不将该子集当作完整验收。
