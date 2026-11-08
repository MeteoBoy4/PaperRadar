# #167 A1：固定 Pi 事实与覆盖矩阵

本次只读核查基线为 `c0bee235f4ebb0a88be4a60c392c96619ec61683`，日期 2026-11-07。范围是 [#167](https://github.com/MeteoBoy4/PaperRadar/issues/167) 的 A1；不运行 Pi、Node、认证 CLI、模型或现场网络，不读取认证文件、token 或其派生值。未修改历史材料。现场事实引用 [EXP-2 报告](exp-2-pi-live-probe.md)，本次没有重做现场验收。

## 来源层次与复核

- **实现**：`src/paper_radar/pi_execution/{admission,service,launcher,resources,isolation,process}.py`，以及 `src/paper_radar/llm/rpc_pipes.py`。实现能说明当前拒绝/启动/回收行为，不能证明供应商实际行为。
- **固定文档/源码**：[1.4.0 来源摘要](../../tests/fixtures/pi_rpc/1.4.0/README) 中登记的 20 项文件，本次从工作区 EXP-2 项目固定安装 `app/node_modules/@earendil-works/` 逐项读取、计算 SHA-256，与摘要逐项比较：**20/20 same**。未运行安装入口。复核只证明这 20 个材料身份，不代替完整安装树或供给核验。
- **源码复读**：复核摘要所列 `rpc-mode.js` 的 prompt/state/commands/shutdown、`agent-session.js` 的 system patch/prepare/start/settled、`system-prompt.js`、`agent-loop.js`、`openai-completions.js` 对应行段。其精确材料哈希和行号以来源摘要为准，不复制上游正文。runtime 等补充指针仍不是第 21 项冻结材料。
- **历史实测**：EXP-2 的四个正常候选、三个本机故障案例及隔离组件观察。正常/故障、协议/HTTP/计费、回显/参数效力分别判断；历史报告的未验项保持原值。
- **离线合成**：协议、管道、启动器和供给相关现有测试证明受控输入下的工程行为；本次 A1 未重跑这些测试，不继承其历史回执为当前树正式结论。

复核方法是用标准库读取来源摘要的 20 个明确相对路径和预期哈希，再读取固定安装中这些路径比较；没有递归读取认证目录、进程环境、内存或普通用户安装。

## 绑定与复用规则

历史观察绑定：Pi `1.4.0` / Node `22.23.4` / npm `10.9.9`；supply `50eb56a3a7fab3c1dcdb3c54ea41a8ff1ca808af65182365368e1b3ef06c6587`；install `9b8e342f8bb64a29b1b1b0aa51b68c85`；Linux x86_64 glibc / 当时 Landlock ABI 8；`pi-launch-1.4.0-v1` / `pi-landlock-v1`；唯一 cwd `/srv/pi-cwd`；`openai / gpt-6.1-sol / low / prompt_only / provider_default / chatgpt_subscription`，temperature/top_p 为 null。完整输入/主机/规则封印见历史私有索引，本次未把索引转为产品证据。

下表的“复用 B”均要求重新核对上述完整适用绑定、当前安装/策略/现场；按消费者分别判断 boundary、value、Read。历史只测 low，**high 无现场证据**；重复 value 不是新的阶段覆盖。绑定或代码/资源/端点/core/认证供给方式变化时，受影响主张重新验证；影响范围不明则扩大验证。源码同字节仅允许复用推导依据。供应商能力按 [ADR-0047](../adr/0047-expire-and-explicitly-activate-live-evidence.md) 从验证完成起 30 天硬到期，不能由重新激活或本次只读核查延长。

## 阶段 A 承接逐项核对

编号原文及历史处置以 [阶段 A 收口清单](stage-a-closure.md) 为准。

| 编号 / 主张 | 当前实现与依据 | 实际结论 / 未测项 | 复用、失效与承接 |
| --- | --- | --- | --- |
| I04 有界 Pi adapter、固定策略、prompt_only | RPC 内核、`PiExecution`、固定启动器及 `LaunchIdentity`；DERIVED-01…11 | 工程组件存在；普通 `read_evidence()` 始终 None，普通任务仍拒绝。历史真实候选不等于生产成功接线 | 复用 B；A2/A3/A5 准备观察与接收，H1–H3 补现场，B 产品消费 |
| I05 固定供给、检查、激活、保留/清理 | `pi_supply` 与 EXP-2 公共 prepare/verify/activate/export/use_install 观察 | 历史固定实例真实供给有据；安装检查不能替代 RPC/模型能力，D5 行为影响仍 unknown；1.3.0 历史不改 | 复用 B；实例、完整树、工具链、保护策略变化失效；H3 当前实例现场核对 |
| T05 ACK/settled/模型不符/取消/超时/退出及业务拒绝 | RPC/管道内核与合成测试；历史正常、派发后取消、注入 clock 超时、子进程 SIGKILL | 只接完整有效候选；clock 注入不等于真实墙钟/网络挂起，SIGKILL 不等于供应商错误；外部 SIGINT/KeyboardInterrupt 未测 | 复用 B；协议/计时/回收变化影响；A6 安全故障计划，H2/H3 授权执行，H4 不可安全触发项裁决 |
| T07 跨论文/阶段/attempt 会话隔离、资源不混入输入 | 新工厂/临时 HOME/TMPDIR/agent、禁资源 argv、严格回显、独立组；历史四个正常候选 | 初始 state 与可观察回显有据；终态清单、目录删除、全运行 session 写入历史未独立证明。reuse、map/reduce 不在本票阶段覆盖内 | 复用 B；输入/发现资源/路径/主机变化影响；A2/A4 原型，H1/H3 补完整窗口；D/G 保留职责 |
| T08 禁 retry/compaction/额外回合/工具，两次预算 | 固定 settings 显式 cacheWarming off、compaction false、retry false、provider maxRetries 0；RPC 封闭事件及任务预算 | 配置/可观察协议抑制存在；单 prompt、CLI、TLS/packet 不是独立模型 HTTP/refresh 计数；隐含网络实际抑制未全验 | 复用 B；settings/SDK/端点/参数变化影响；A3 计数接缝，H2/H3 现场观察；B 任务预算，D/G 后续消费 |
| T12 行为影响依据及证据引用、受保护安装显式清理 | `pi_supply` 冻结/计划/执行/保护、继承 fd；EXP-2 使用公共保护 | 工程覆盖及历史保护有据；unknown 是明确行为影响结论，不表示与旧模型行为等价或校准兼容 | 当前实例仍需完整复核；A1 不执行清理；H3 实例验收，B 生产消费者 |

## DERIVED 逐项矩阵

每行来源编号、上游文件/行号及三态来源属性沿用来源摘要；本表新增的是交叉核查结论，不改变其“源码推导”分类。

| 编号 / 主张 | 固定依据与实现 / 历史观察 | 未证明部分与下一动作 | 复用 / 失效 |
| --- | --- | --- | --- |
| DERIVED-01 system patch 唯一，preamble 原样，无工具/默认注入 | `agent-session.js` prepare 与 `system-prompt.js`；严格内核在四个正常流检查通过 | 内容形状不证明 OS/不可见资源；A4 列现场资源，H3 两阶段两档补测 | 复用 B；Prompt/资源加载/argv/settings/安装变化重验 |
| DERIVED-02 唯一 cwd 包装 | `system-prompt.js:110–118`；`expected_cwd_section()` 常量；历史 `/srv/pi-cwd` 精确匹配 | 不外推主机或其他路径；祖先资源与权限现场仍需 H3 | 复用 B；cwd/祖先/主机变化重验 |
| DERIVED-03 user 为单 text 且逐字相同 | `agent-session.js:1500–1509`；历史四流严格比较 | input handler/image/模板路径未因回显全被独立观察；A1 源码仅支持限定条件推导，H3 核实启动关闭项 | 复用 B；输入处理/发现/adapter 语义变化重验 |
| DERIVED-04 新 run 与最终消息副本完整一致 | `agent-session.js`、`agent-loop.js`；历史完整生命周期严格比较 | 不接受故障缺副本；长流/近界另测，不能由小样本推断 | 复用 B；协议/输入大小/输出预算变化影响；A6/H3 正常矩阵，B/F/G 大输入 |
| DERIVED-05 初始消息/队列空、sessionFile 缺失 | `rpc-mode.js` state、runtime 补充指针；历史 state 检查通过 | 三类文件事实均需独立观察；A2 原型分终态/删除/历史窗口，H3 真实 Pi 验证 | 复用 B；session/文件/进程/窗口/观察器变化重验；终态空不复用为历史零写入 |
| DERIVED-06 commands 空 | `rpc-mode.js:540–566`；历史正常及故障初始化为空 | 空列表不能独立证明无任意扩展副作用；A2 历史窗口、A4 文件边界，H3 现场 | 复用 B；扩展/skills/template/资源加载变化重验 |
| DERIVED-07 ACK 次序，set_model 后档位 | `rpc-mode.js` preflight、`agent-session.js` onStarted；历史初始化/取消关联 ACK 与 low 回读 | prompt ACK 相对 agent_start 先后未独立留序；内核容忍迟到 ACK 不证明其发生。A6 列最小序号观察，H3 新轮记录 | 复用 B；调度/协议/初始化序列变化重验；防御性合成保持原来源 |
| DERIVED-08 token 合计与零值未知 | `openai-completions.js` 初始化及 usage；历史四个正常流合计符合 | Pi 口径非供应商账单/额度证明，故障零值不能解释零计费；H3/H4 受控供应商证据 | 复用 B；provider/SDK/计量口径变化重验 |
| DERIVED-09 settled 后排空/退出/回收，无额外协议记录 | `agent-session.js` settled 前触发 cacheWarmer；`rpc-mode.js` shutdown；历史 EOF/退出0/组回收 | 不证明隐藏 HTTP、预热或 refresh 次数；core 临时全机方案非持久部署。A3/A4，H1–H3 | 复用 B；网络/SDK/cache/回收/core 变化重验 |
| DERIVED-10 请求模型/档位回显与 responseModel | `agent-loop.js:282–283` 明确记录请求档位；`openai-completions.js` 记录请求模型及差异 responseModel；历史 low 匹配 | 供应商实际推理/采样效力、alias/日期模型、账号限额未独立验明；high 未测。H2/H3 各消费者各档，H4 不可观察取舍 | 复用 B；模型/档位/通道/供应商行为变化或30天到期失效 |
| DERIVED-11 三倍回显与 thinking/signature 预算 | 同 DERIVED-04 源码；历史四流帧/累计量 | 小流量不能证明4MiB单帧/16MiB累计近界或长文；敏感 stream 不永久保存 | 复用 B；输入/候选/协议预算变化影响；A6 有界合成，B/F/G 大材料 |

## 现有接缝与产品工程缺口

1. `LaunchIdentity` 已提供供给/实例/Pi/Node/启动与隔离策略/auth 模式/代理形状的非秘密元数据；没有 stage consumer、实际主机/boot/kernel/祖先资源、端点/网络/core 策略或观察窗口。这些属于后续完整现场绑定要求，不能从旧字段补猜。
2. `EvidenceBinding` 有供给/实例/策略/cwd/provider/model/thinking/sampling/温度/top_p/protocol/auth；当前无来源完整性接收、消费者覆盖、现场绑定、激活、到期、撤销或针对性重验依赖模型。`AdmissionEvidence` 的三个 bool 只用于已有内部判定，不构成外部自证入口。A5 离线原型不得把它提升为产品 `read_evidence`。
3. `_OwnedSession.terminate()` 顺序是管道整组收尾后 `AttemptResources.close()`；`rmtree` 成功返回是实现结果，不是独立目录删除观察。资源分配点、启动前窗口、回收前终态窗口和回收后复核点需 A2 明确；读取终态文件内容并非必要。
4. Landlock 限 TCP 端口，不限制目标主机/UDP/DNS；ABI≥6 scope 不等于全部后代退出证明。已有组回收不能覆盖逃逸组的部署责任；A4 应由专用 cgroup 收束。IPv6、端点漂移及透明上游边界仍未验。
5. 历史 7 prompt / 7 token CLI，refresh 为 unknown `0..7`，provider HTTP 总数 unknown。A3 必须把各层计数拆开；读源码发现调用点不能登记实际请求数、额度或计费。

## AFK / HITL 交界

A1 交付的是本矩阵与源码身份复核。A2–A5 可仅在临时目录以合成对端/哨兵验证方法；A6 冻结授权计划，A7 记录相关验证与只读范围审计。所有现场安装/启动策略变更、root 配置、凭据供给、模型/刷新网络及额度使用仍交 H1/H2；H3 仅在适用授权与现场隔离满足后执行；不能安全观测或触发的项交 H4，保持 unknown/not_assessed；H5 审阅不等于激活。

没有新增 Live 完成声明，不将本票链接为 Live spec；普通执行继续缺证据阻断，B 等待完整 Live。reuse、长文、真实正文、四刊质量、正式校准、无人值守及 NAS 资格均未由此取得。
