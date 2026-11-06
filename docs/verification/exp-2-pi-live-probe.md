# EXP-2：固定 Pi 1.4.0 现场与真实 RPC 实验报告

## 结论与证明边界

依据 [#166](https://github.com/MeteoBoy4/PaperRadar/issues/166)，本次建议为 **受限继续实验；普通产品执行仍阻断**。

本机固定安装、文件哨兵与 IPv4 端点约束、专用 OAuth 供给、固定 CLI 取 token、boundary/value/单篇 Read 正常调用，以及明确标注的本机取消/时钟故障/子进程异常与恢复取得证据。**没有足够证据声明全部现场与 Live 准入完成、B 可开始或正常生产/正式校准可用。** 产品 `read_evidence()` 仍返回缺失，没有生产证据导入或任务成功接线。

本报告冻结的是本次实验观察，不修改规格、Contract、历史 ADR、DERIVED 来源分类或 A1–A10 分母。没有推翻或重写既有协议字段契约；发现的 nft 表示/编排错误只修在私有实验接线。所有者已接受本次“受限继续＋未验移交”的实验交付范围；此接受不解除剩余 EXP-2 条件或授予模块完成。[证据移交记录](https://github.com/MeteoBoy4/PaperRadar/issues/166#issuecomment-6682951812)只维护票级交付；后续[所有者归并裁决](https://github.com/MeteoBoy4/PaperRadar/issues/166#issuecomment-6683324540)将原 Cwd 与 EXP-2 未完成责任统一交给 Live，按 [ADR-0046](../adr/0046-consolidate-pi-readiness-under-live.md)维护。Cwd 独立交付取消不是验收通过，Live/B 安全门槛不变。

### 本次绑定

| 项目 | 固定身份/范围 |
| --- | --- |
| 发布及执行代码基线 | `main@c960e7cdb03af9c4d2856692ab814839e270c5b2` |
| Pi / Node / npm | `1.4.0 / 22.23.4 / 10.9.9`，绝对入口、项目独立供给 |
| 供给 | `50eb56a3a7fab3c1dcdb3c54ea41a8ff1ca808af65182365368e1b3ef06c6587` |
| 安装实例 | `9b8e342f8bb64a29b1b1b0aa51b68c85`，Linux x86_64 glibc |
| 启动/隔离 | `pi-launch-1.4.0-v1 / pi-landlock-v1`，本机 Landlock ABI 8 |
| 唯一 cwd | `/srv/pi-cwd`，不迁移到其他路径/主机 |
| 模型/档位/通道 | `openai / gpt-6.1-sol / low / prompt_only` |
| 采样 | models 格式2 `provider_default`，temperature/top_p 均 null；不承诺温度零/确定性 |
| 认证 | `chatgpt_subscription / owner_provisioned_dir`；无 API key/legacy/其他 provider 路线 |
| 代理/IPv6 | 客户端不设代理、不继承代理环境；所有者接受上游 fake-IP/透明代理但不检查或调整；IPv6 **not_assessed** |
| D5 | 首次独立供给的行为影响判定 **unknown**，没有可比较的项目真实行为基线，不推断校准兼容 |

四次正常候选分属独立冻结阶段输入，不能因模型元组相同就把 Screening 证明外推到 Read。完整 snapshot/指纹、请求字节、源码/规则/boot/kernel 封印及回执在本机私有索引，不含认证内容。

## 方法与数据边界

仅使用所有者逐批确认的虚构 Profile、玩具估计量题名/摘要/主题及单页生成 PDF。未发送真实个人资料、真实论文、出版方凭据或真实正文。必要 cwd 字符串只使用规格已裁决常量。

私有验收、专用认证及材料备份分根保存。只保留必要正常候选 raw、权威处理视图和受控元数据；不永久保存完整 RPC/session/JSONL、thinking/signature、模型失败原文或 stderr。认证 token、前缀/长度/哈希等派生值均不登记，agent 不读取 auth.json 内容。凭据、安装树和模型缓存不混入普通证据备份。

### 首次探测路径

普通 `PiExecution` 缺少 Live 证据应继续拒绝。实验专用路径先核对真实组件回执、现场元数据、固定安装、冻结输入及外发确认，再复用公共 `prepare_launch`、一次 `SessionFactory`、`run_call` 和严格业务验证。RPC 兼容性是输出，不伪造成输入 `passed`；不使用测试私有证据注入、不把真实候选放进 test 接收器。

本次不创建 Paper、模型任务、建议、正式 Read analysis 或生产成功行。私有 exclusive 操作登记只约束本次实验，不另建生产预算权威；重启/改名不重置，潜在执行不明保守视为已用。每轮失败与新授权保留，未以更新指纹或重建进程自动重发。

## 现场隔离与固定供给

### 已观察

- cwd 为真实空目录，路径组件无符号链接；cwd 及祖先没有 `.pi`、`AGENTS.md`、`CLAUDE.md` 等发现资源。模型进程 cwd 只读，严格 RPC cwd section 为 `<cwd>\n/srv/pi-cwd\n</cwd>`。
- 固定 Node 在原样生产 Landlock 下通过15项无敏感哨兵观察：业务 DB/blob、个人资源、出版方凭据、宿主及专用认证目录拒绝；安装只读、cwd 只读、attempt 可写、resolver/CA 可读；子进程继承、`no_new_privs` 和空 capabilities 观察通过。此组件探测的具体 attempt 回收已确认，不外推到全部后续 Pi attempt 的独立目录观察。
- 公共供给 prepare/verify/activate/export/use_install、固定工具链/平台/完整树核验通过；使用保护及继承 fd 由公共启动器持有，没有个人 Pi/PATH 入口或供给 fallback。
- 主机级 cgroup 限制经允许→拒绝→再允许、本机 TCP/UDP 哨兵及后代继承核查。最终精确 IPv4 端点在裸 Node 与原样 Landlock Node 各完成 API/Auth DNS+TLS，4次 TLSv1.3 证书核验通过，无 HTTP。拒绝错误涉及 EHOSTUNREACH 时要求精确规则正计数、前后正对照及零 marker 增量，不单凭错误码认定阻断。
- 模型批次先 Auth-only，再以单次本表 nft 事务切为 API-only，读取本表 JSON 逐表达式核对；只开放冻结 IPv4 TCP443 和本地 stub UDP53，不授予模型刷新端点权限。匹配仅影响本次 cgroup，不改全机默认策略。

### 网络与主机限制

Landlock TCP 端口规则不是目标主机白名单，也不约束 UDP/DNS；本次依赖额外主机策略补齐。精确 IP 也不是完整 FQDN 身份/专用地址保证，DNS 可查询内容与共享地址仍有限制。端点变动不自动扩容或换代理；没有检查上游、没有端到端直连证明，不外推 IPv6 或其他部署机。

原 Node 被 io_uring 默认 kill 的失败保留，经所有者确认仅将三个 io_uring 拒绝改为 EPERM，未放行；bpf 继续拒绝。生产文件白名单没有为了跑通而扩大。

## 认证与 core 隐私边界

所有者独立完成官方 OAuth，SDK 只做凭据供给，不构造 AgentSession；未复制个人 Pi 认证。SSH 下手动完整回调在隐藏输入中成功，链接/回调/token 未进入证据。临时 localhost 回调仅首次登录使用，不进入模型网络策略。

实际模型调用由同一受保护的固定 CLI `auth print-bearer-token --provider openai --min-expiry 900s` 一次处理每例专用目录；成功返回及形状拒绝规则有效，不在沙箱刷新。CLI 成功不构成独立 token 寿命、订阅额度、供应商参数或刷新网络次数测量，`sk-` 拒绝仍只是形状启发式，未改模式或绕过拒绝。

本机原 core handler 为管道，仅 RLIMIT_CORE=0 不能阻止 handler 留存。经所有者逐窗口批准，固定 root 前/后置保存原值/CAS串行化，临时转固定丢弃 handler，PID1 有限守卫与 worker 依赖逆序回收，确认组停止后恢复，原值哈希/本次 nft/服务/cgroup回收复核通过。**这是单用户现场实验的临时全机影响，不是可无人值守部署的通用 core 方案。** 外部变更不覆盖、活动组不明不提前恢复，异常可需人工介入。

## 调用账本与实际结果

累计 **7条实际派发 prompt、7次固定取 token CLI**。正常实验候选4、预期本机故障3。供应商实际 HTTP 请求总数未独立可见，SDK实际 refresh 数保留 **unknown，范围0..7**；不把 CLI、prompt、连接或 packet 数当作供应商调用/计费数。没有故意耗尽额度或自动 fallback/retry。

| 案例 | 请求帧 bytes（含LF） | 实际结论 | 主要限制 |
| --- | ---: | --- | --- |
| boundary 正常 | 2484 | 完整RPC、精确模型、权威 boundary 接收通过 | 合成摘要，不是模型质量/正式筛选 |
| value 正常 | 5310 | 完整RPC与主题/语言等权威业务约束通过 | 虚构上下文 |
| 派发后取消 | 2449 | `cancelled`，clear_queue/abort 各1个成功关联ACK，无候选，回收通过 | 不证明供应商已开始或已停止计量 |
| 注入clock超时 | 2416 | `timeout`，无候选，回收通过 | 本机局部单调时钟故障，不是墙钟300秒或供应商迟延 |
| 精确子进程SIGKILL | 2433 | 退出-9、`unexpected_exit`，无候选，回收通过 | 只以PPid/UID/组/cgroup/Node executable及pidfd定位，不读environ/argv/内存；不是供应商错误 |
| 故障后独立value | 5310 | 新组/会话，初始干净，正常接收通过 | 与首个value同指纹的第二次明确观察，上限2，不是失败补跑或确定性证明 |
| single Read 正常 | 8368 | 首序号Read v2接收，discard/diagnostic/model warning均0，正常回收 | 仅单页toy来源，不授予真实正文/生产Read资格 |

正常案例均完整消费至 settled，严格系统/用户/模型与最终副本一致性、stop、EOF、退出0及公共整组收尾通过；其后所有相关unit/cgroup/nft与core恢复已取得回执并独立复核。故障case的 `passed` 表示预期失败路径与回收，不算业务成功，未保存部分输出。

### Pi用量与真实流量

| 正常案例 | input / output / cacheRead / cacheWrite / total | stdout bytes / LF帧 / 最大帧 |
| --- | --- | --- |
| boundary | 594 / 74 / 0 / 0 / 668 | 33141 / 93 / 3823 |
| value前 | 1274 / 323 / 0 / 0 / 1597 | 107276 / 342 / 7581 |
| value后 | 1274 / 323 / 0 / 0 / 1597 | 107306 / 342 / 7587 |
| Read | 1968 / 762 / 0 / 0 / 2730 | 232938 / 781 / 12430 |

reasoning不另重复计入；故障中途全零或缺失用量不解释为零计费。上述是Pi报告口径，不是独立账单；仅小输入，不能证明4MiB单帧/16MiB累计近界或更长正文可接收。

## DERIVED-01…11：原假设、方法、结果

来源编号沿用 [冻结来源摘要](../../tests/fixtures/pi_rpc/1.4.0/README)，所有结论只适用于上表固定组合及本次正常流。

| 编号/原假设 | 方法与实际观察 | 结论/未证明部分 |
| --- | --- | --- |
| 01 精确system补丁/preamble，无默认或工具注入 | 生产公共内核在四个正常流严格核对content空、sections仅preamble/cwd、preamble逐字等于冻结system，无工具补丁 | 本例符合；消息形状不独立证明OS/全部不可见资源路径 |
| 02 唯一cwd包装 | `expected_cwd_section()`严格比较常量段通过 | 本机本路径符合，不外推其他cwd/主机 |
| 03 user原样单text | 四个正常流完整user逐字等于冻结请求 | 本例符合；不证明没有不可观察的等价内部处理 |
| 04 完整system/user/assistant和重复回显 | 实际公共内核递归严格比类型/值及最终副本，一组完整生命周期 | 正常流符合；不把故障丢失副本当成功 |
| 05 新临时会话空消息/队列、sessionFile缺失 | 实际初始state通过、独立工厂/进程组 | 部分符合；目录终态清单/删除独立核对及全运行写入历史未验（A） |
| 06 资源关闭时commands空 | 四个正常流与故障前初始化均观察commands空，无工具或额外turn | 部分符合；空列表不独立证明没有一切扩展副作用/文件写入 |
| 07 ACK/事件正常顺序与set_model后档位 | 串行8条初始化及关联、后置low/state/通知核对通过；取消clear_queue/abort及ACK观察通过 | 初始化/取消有观察；prompt ACK相对agent_start精确先后未独立留序，内核容忍防御性迟到ACK，不能由通过反推该先后假设全部成立 |
| 08 token合计口径 | 四次非零usage满足input+output+cacheRead+cacheWrite=total | 本次Pi口径符合，不作供应商计费/额度保证；零值仍未知 |
| 09 settled后排空及回收，无额外协议记录 | 正常流关stdin、两EOF、退出0、公有terminate及外层组停止/卸载通过；受控故障无候选回收 | 可观察协议/回收符合；额外HTTP/预热请求独立计数、无人值守core方案未验 |
| 10 请求档位/模型与responseModel可能性 | 实际有效reported provider/model匹配，Pi回读及最终thinkingLevel=low；providerThinkingLevel未提供 | 记录匹配符合；供应商实际推理/采样效力、alias政策及账号限额未独立验明，不能把回显当参数生效 |
| 11 三倍回显及thinking/signature预算 | 真实内核处理完整副本/更新，记录上表帧/累计量；正文/签名不永久落盘 | 本例小流量观察，不证明更大材料/近界/长文 |

没有把源码推导整体改为实测，也没有基于一次“没发生”证明所有隐含请求关闭。当前固定argv/env/settings与源码、ACK/state和运行事件为不同证据层；没有独立provider请求计量的部分保留未验。

## 失败与修正边界（原件保留）

| 暴露点 | 处理/证据边界 |
| --- | --- |
| io_uring默认kill、拒绝错误仅EHOSTUNREACH | 原失败保留，限定EPERM拒绝与root精确counter/前后正对照；未开放syscall或网段 |
| `RestrictAddressFamilies=none` transient属性被拒 | 非root最小复现定位编码；守卫sleep改显式socket/socketpair拒绝，认证worker仍AF_INET。一次无凭据uv全socket拒绝诊断触发SIGABRT的失败保留，未读删core/report；不作为通过 |
| guard引用保留已退出auth unit | 原整体false保留，另做只读清理证明；新编排先inactive/cgroup空再停guard，后要求卸载，不能把引用保留误当活动进程 |
| nft拒绝码只认数值3 | 真实本表快照复现symbolic `admin-prohibited`，本机内核枚举确认等价；仅兼容该icmpx表示，其他码/type/地址/端口/表达式仍拒绝。旧失败/余额不改，新执行由所有者明确授权 |
| value缺少既有业务标记指引 | 离线候选被公共business_rule拒绝，未冒充真实模型失败；获准新Prompt版本，仅重冻value两例，三故障字节不变，不改Schema/规则/预算 |
| 提取配方缩进审计JSON不能canonical回放 | 原审计件保留，用公共build从历史配置+真实合成PDF SHA重建，指纹与已发布三元组一致；未重跑解析/手填私有输入 |

这些是具体实验接线/观察修正，不扩大既有公共能力或重写历史离线结论。实现过程与临时命令不成为长期公共Contract。

## 明确承接与产品闸门

| 剩余项 | 承接责任与完成条件 | 当前闸门 |
| --- | --- | --- |
| A：Pi attempt终态清单/目录删除独立核对 | **Live**补最小公开无秘密元数据接缝，明确观测时点，绑定固定供给/实例/策略后现场补测；**B**消费/准入/报告必须保留缺项，不把公有terminate返回改称独立目录验收 | not_assessed；无此证据不放行对应产品主张 |
| 全运行零session写入历史 | **Live**设计完整受控观测；终态清单不能替代历史追踪；B保留限制 | not_assessed |
| 产品证据接收/绑定/失效 | **Live**提供真实接收权威与用途边界、对完整EvidenceBinding核对及变更失效；不能任意JSON/Markdown自证passed | 产品read_evidence=None，普通任务阻断 |
| 供应商真实参数/alias/限额/刷新失败与次数 | **Live**另冻安全方法，不故意耗尽额度、不记录token派生值；不把目录列出模型/请求回显/成功一例当完整能力 | 未验部分保留，provider_default不当温度零 |
| 额外模型HTTP/预热独立计数 | **Live**补能区别单prompt与真实provider请求的受控方法；不能仅靠TLS/packet/settled推断 | not_assessed |
| 外部SIGINT/KBInterrupt、墙钟/网络挂起、供应商错误 | **Live**按风险另冻故障与调用预算；无法安全触发时明确未测，不拿本机注入替代 | 本次未测，不自动补跑 |
| 大输入/长Read与复杂证据 | **B/F/G**按阶段补材料/质量/输入预算与真实流量；F补真实四刊/复杂版式/公式 | 本小样本不授予质量或长文资格 |
| 产品入口/真实样本/日志/用途/任务预算 | **B**实现受限实验根与Screening/Read真实产品接线及独立资格，保留test拒绝/来源与用途分离 | 本票无业务task/正式analysis/建议写入 |
| NAS/无人值守/core部署适配 | **Live**承担core/现场部署接线，**I**承担NAS及最终聚合验收；本地同目录备份不作灾备证明 | 未验 |

原 Cwd 的部署适用性、cwd/祖先资源、文件与主机出站、UDP/DNS、端点漂移及 core 隐私未完成责任一并由 Live 承担。Live 的模块前置改为 Pi，B 仍依赖完整 Live；该责任归并不改变 GitHub 历史原生关系或任何准入条件，不给本票顺带新增通用证据平台。后续负责人应在具体票中消费本索引与绑定，不能只复制“通过”标签。

## 验证、恢复与证据保管

本次均按显式 `uv run --offline --locked …` 执行相关子集；阶段性组合包括462项私有/公共协议与启动回归、162项矩阵/公共生命周期组合、165项单次Read/公开接收组合。各组有重叠，**不得相加为唯一测试数**。Ruff、Bash语法、固定Node语法与wizard库字节分别核对。这些不是A1–A10正式回执或完整离线门禁；本次未获全门禁指令，没有运行 `./scripts/check-offline`。

实际合成Docling输入通过公共backup create→verify→隔离restore→恢复库/制品公共Read准备，字节/FP/context重建一致。未隐藏原根、未恢复认证或安装树、未测试NAS；不宣称物理灾备。普通归档仅本机私有根，排除credentials和模型/安装缓存。

私有证据索引为仓库忽略目录下 `.scratch/exp-2/evidence/exp2-summary-index-v1.json`，包含计划、封印、原失败、真实观察、独立复核、必要成功/来源成员及本地备份身份。它不随Git公开，不是产品证据导入接口。公开报告不包含个人绝对目录、账号、OAuth链接/回调、任何credential或完整真实输入/输出。

## 复现与后续决策

私有向导只说明本次明确授权的可复现形状，现有exclusive余额均保留，**不能直接重跑旧命令**。需要新的实际调用时，先核对供给/主机/端点/根与旧证据适用性、另冻材料/限额/停止条件，并取得所有者新授权；Root动作仍由人工审阅，不由agent提权。

所有者已接受本实验以“受限继续＋未验移交”交付，并明确将原 Cwd 与 EXP-2 未完成责任合并到 Live；实验票按[收口记录](https://github.com/MeteoBoy4/PaperRadar/issues/166#issuecomment-6683529220)关闭。移交以本报告的[明确承接表](#明确承接与产品闸门)、[ADR-0046](../adr/0046-consolidate-pi-readiness-under-live.md)及私有证据索引为准；后续必须重新判断事实适用性，不继承旧执行余额或未取得的通过结论。剩余问题纳入 Live，不继续单列 EXP-2/Cwd 交付前置；Live/B 不标完成，模块、前沿和依赖按[路线图维护](../agents/roadmap.md)维护，实验票的完成不记入模块“已完成”表。

依据：[Pi执行](../contracts/pi-execution.md)、[RPC](../contracts/pi-rpc.md)、[固定供给](../contracts/pi-supply.md)、[Read输入](../contracts/read-inputs.md)、[Read接收](../contracts/read-validation.md)、[ADR-0036](../adr/0036-isolate-stage-b-read-experiment.md)、[ADR-0039](../adr/0039-isolate-pi-with-landlock.md)、[ADR-0040](../adr/0040-declare-provider-default-sampling.md)。
