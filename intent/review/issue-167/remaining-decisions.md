# #167：A4/A6 剩余可执行性审查与 H1/H4 选择材料

本文件是对前轮[部署候选](deployment-plan.md)和[现场计划](field-plan.md)的独立审查，不是新授权或部署指令。核查基线 `c0bee235f4ebb0a88be4a60c392c96619ec61683`，只读当前 Python 源码、已有无认证请求路径报告与本机 man；未读取认证内容、token 或派生值，未运行 Pi/Node/网络，未改宿主配置。既定 Q1–Q10、固定模型元组、30 天硬到期、人工激活和原安全门槛全部保留。下面需要的是新暴露实现取舍的具体裁决，不能通过“继续推进”推定 H1/H2 已批准。

## 所有者最新终局的适用范围

core不选全机分发器、暂不选全局“不外流+可清理”路线；按ADR-0049验证并要求项目exec前软硬RLIMIT_CORE=0及服务LimitCORE=0，依赖适用Apport limit0早退/非打包分支不生成report。root内存读取环境但不落盘的残余由所有者接受；collector漂移长期doctor核查交后续工程。两例无秘密合成验证见[终局证据](../../../docs/verification/issue-167-final-core-validation.md)，不构成真实Pi/Node或产品部署通过。

计数按ADR-0048采用可证近似下界+unknown和Pi报告token口径；不采用新启动策略身份、不重跑EXP-2、不将loader接产品或登记覆盖/分母，精确计数交I无人值守/NAS重新评估。以下旧候选仅保留设计比较，不作为本轮实现指令；独立精确计数缺失不再单独阻断本轮准入，其余边界仍成立。

## 现方案尚不能直接安装的原因

| 阻断 | 具体事实 | 影响与归属 |
| --- | --- | --- |
| B01：跨 unit 安装保护 | 当前 `prepare_launch` 持 `use_install`，auth 和模型都是它直接 `Popen` 的子进程，以 `pass_fds=install.pass_fds` 继承同一 open file description（OFD）。systemd 服务由 manager 创建，不会天然继承调用 systemd 客户端的 Python fd | 双 unit 方案必须实现显式 fd 传递/确认，不能用另一次打开同名锁代替原 OFD 或在 manager 启动后才加锁。沿已存在单worker直接fork链可避免这一跨unit障碍；若改双unit再单独审H4/H1，不能把旧双unit提案当当前必需前置 |
| B02：同 uid 不等于进程隔离 | 模型 Landlock 限文件访问，不能据此证明所有跨进程内存系统调用受限。本机 systemd.exec 的 `ProtectProc=invisible` 隐藏其他用户的进程，同 uid 仍需另外约束 | 双 worker 用相同项目 uid 时，要验证 `ptrace`、`process_vm_readv/writev`、`pidfd_getfd`、跨进程信号及 `/proc` fd/内存路径的拒绝；不能只列 ProtectHome/ProtectProc。不同 uid 又会触及供给根 owner/读取权限和凭据归属。[本轮process_vm_readv合成对照](../../../docs/verification/issue-167-landlock-process.md)已对一个具体域关系取得正负结果，未外推其他syscall；H1/H3继续按实际边界验证 |
| B03：token 不能走 unit 属性 | 当前 token 仅在受控 Python 内存及模型子进程 env，未传 unit。systemd.exec 明确 unit `Environment=` 不适合秘密，会通过 manager IPC 等暴露 | 不得写 Environment/EnvironmentFile/ExecStart 参数、journal、状态文案或普通凭据文件；LoadCredential 也会新增文件与生命周期，不能自动作为“内存桥”。需要受审 bootstrap/管道，H1/H4 |
| B04：core 方案覆盖时间不完整 | exec 前设置 dumpable 候选必须核对普通 exec 重置语义；仅在 JS preload 后设置也不能覆盖 Node 启动到 preload 期间已存在 env token 的窗口 | 实际测量见[本轮 core 专项](../../../docs/verification/issue-167-core-feasibility.md)；ADR-0049第三路已明确接受root内存瞬时采集残余，按适用Apport行为验证不持久化；生产子进程已接零软硬限额，服务实际部署与其他准入仍独立，不改全机策略 |
| B05：真实出口尚未有收集权威 | 现 RequestLedger 只对输入事件核对。固定包有前台、provider/Agent retry、warmer/summary、refresh 等路径；首批 openai 与替代 codex provider 分开 | 自定义 fetch/loader、SDK patch 或解密代理均可能改变供给/启动身份与隐私边界。不能当普通观测实现细节自动采用。计数H4已按ADR-0048终局为下界/unknown并移交I精确重评，不启用这些新接缝；H2仍单独批准实际调用 |
| B06：文件观察与可信回收未接线 | 原型 `descendants_reaped()` 来自合成驱动声明，新目录竞态、挂载别名/mmap 等不能证明完整 session 历史 | 终态快照/删除/历史继续分开。需要可信 cgroup 生命周期和明确观察边界，缺口不填零；H1/H3 |
| B07：网络候选尚无具体现场身份 | uid、真实角色 cgroup 路径/层级、规则优先级、端点/解析/透明代理、IPv6和允许正对照未封印 | 模板不得直接加载，不能用共享 uid 匹配、不增加网段或全部 UDP。H1先审路径化规则，H2审端点，H3验证 |
| B08：计划尚无抗重启的许可消费权威 | 原型内存状态不能防止 controller 重启后消耗/撤销丢失；公开 manifest 是材料封印，不是执行许可 | 调用前原子预占预算/案例，失败或结果未知不返还；重启保留历史，缺日志阻断。不能靠换 run_id 重置。[预算离线原型](../../../docs/verification/issue-167-budget.md)已验证重启不返还/未知阻断，真实消费权威与抗回滚仍属后续工程 |
| B09：能力与真实故障未测 | 参数回显不能证明效力，alias/限额、真实供应商错误、真实超时未安全覆盖 | 不故意耗尽额度、不把本机故障当供应商错误。先 H4 逐主张记录安全触发方法或未完成责任，H2逐批批准，不默认豁免 |

## H4-拓扑：保留现有 fork 链还是实现双 unit 桥

| 候选 | 需要实现的内容 | 收益、成本与残余风险 |
| --- | --- | --- |
| T1：单个项目 controller，保持当前直接子进程链；外层服务只管理整个实验 | controller 持原锁，auth/模型仍分别新进程；通过受审的子 cgroup/角色边界控制刷新期与模型期，必须在放行前确认角色归属。若用委派子 cgroup，controller有管理权但模型不得继承管理fd或访问cgroup控制文件；现模板 `Delegate=no` 不能原样沿用 | 继承同一OFD、现有token内存路径最接近当前实现，减少桥接秘密面。仍需解决auth读取白名单、角色出站、同uid内存隔离、core；不能把整服务cgroup空替代每角色观察，也不能无审阅开启Delegate |
| T2：保留双 unit，受信 broker 向一次性 bootstrap 传 fd/内存token | broker持有原锁；在受保护的私有 pathname Unix socket上校验 peer uid/PID/cgroup/本轮不可复用身份；用 SCM_RIGHTS传原OFD，收到接管ACK之前broker不释放；bootstrap拿到锁后复核固定绑定，门闩未放行不得认证/建模型。token仅由auth匿名输出管道进入broker，再经一次性有界匿名管道给模型bootstrap，后者直接构造现模型env并exec | 独立角色unit较易表达mount/出站策略，增加受信broker、peer认证、fd泄露/关闭、半连接/超时回收、manager重启等复杂度。不能把安装锁路径暴露给模型重新open；不能把socket pathname可达当peer可信；不能把broker存活当后代锁已继承 |
| T3：双 unit，manager fd-store/credential机制 | 必须证明fd-store传递的是已持锁OFD且生命周期不跨轮保留；token机制须符合不落普通文件/不泄漏manager属性的约束，另审权限与回收 | 本机man提供fd-store/OpenFile等能力，不等于现broker已经接入。`OpenFile=`重新open路径不能自行取得当前OFD；文件型credential新增文件生命周期也不能默认为已获许可。此候选没有现成最小接线，不建议在未验证前选作捷径 |

建议先做 **T1/T2共同需要的无秘密协议验证**：真实父子继承与SCM_RIGHTS只传合成锁fd/哨兵，不传任何凭据；父被杀后活后代仍阻止独立EX锁，ACK前后故障均不能释放最后保护；token桥只用固定非秘密哨兵并验证没有manager属性/文件/日志出口。之后根据测得复杂度提交 T1/T2 的最终差异选择。这个建议不是已经接受的新架构；现有 launcher 与生产供给不在本轮自动改动。

同 uid候选必须显式列拒绝的跨进程系统调用、proc视图、signal scope、已打开fd与子孙继承规则，并以合成兄弟进程测试；不同 uid候选须证明受信broker保留供给root归属验证，worker仅获得只读安装视图和原锁fd，不以批量chmod/chown现有固定树获得“可用”。任何权限放宽都先H1/H4。

## H4-core：可选择的具体方向

1. **仅pre-exec dumpable/仅JS preload：不作为完整候选。** 普通exec语义及启动早期窗口必须证明，不由Node正常返回反推。JS preload若在环境已经含token后运行，只能覆盖其后期间；失效应阻断。
2. **项目专用启动原语/原生代码在秘密进入前设置并保持不可dump。** 需证明从认证进程首次读取auth内容前，到controller传输、Node启动、所有后代退出的全过程。若需要改Node或固定安装/启动策略，必须新身份、重新核验及H4批准；不能在原manifest树内直接patch。成本是维护/供给变化，优点是控制点可能接近真正秘密生命周期。
3. **项目专用core路由/处理器。** 只有在可按不可伪造项目身份精确拒收/丢弃并保持非项目行为时才可考虑。全机 `core_pattern` 包装器会接触所有程序的分发链，不能称“只影响项目”而自动安装；必须逐项说明非项目透明转发、失败模式、秘密是否在handler内存、恢复方式和验证成本，再由H4决定是否属于允许范围。不得以全机 `Storage=none`/`ProcessSizeMax=0` 代替项目方案。

core选择需等待专项实测；本文不预判任一路径可行。无论选哪条，先用无秘密worker验证，不在未证core边界时提供真正凭据。

## H4-观测：固定供给与出口可观测性的选择

| 候选 | 在本票内可继续的准备 | 需要所有者决定的代价与边界 |
| --- | --- | --- |
| O1：保持供给不变，利用固定实现现成底层事件源 | 只读核对 SDK/HTTP client是否支持仅类别/次数的既有事件；用合成对端证明失败/重试/预热/重定向都覆盖。日志接口若只含完整请求或响应，不启用它 | 没有完整事件源就保持unknown/阻断，不能降为packet计数。若观察选项需新启动参数，依然属于H4的启动身份变化 |
| O2：独立审阅的最小loader/transport观察桥，安装树只读 | 固定源码哈希、观察代码白名单字段、合成出口拒绝/漏计/重复与观察器失败测试；本轮不注入真实Node/Pi | 尽管树不变，effective runtime已改变；需独立启动策略/观察器身份，证明没有绕过出口并重测DERIVED与core。不记录URL/headers/body/token、完整流，不能泛化成任意SDK hook许可 |
| O3：新的观测供给或项目专用代理 | 可以先列精确patch/接口与回滚方案，但不生成或启用真实供给、不安装CA、不解密真实流 | 改供给要新身份和供给核验；代理可能看到认证/body，扩大受信面与隐私成本。票明确须单独裁决，不能在通用“允许最小计数”下自动实施 |

推荐先完成 O1 的现成事件源穷尽核查（限定首批provider），若不满足就直接提交O2/O3的具体差异供H4。不能为了先发六个prompt而临时把HTTP次数标unknown并放行。首批发现替代provider/WS即停止，不自行切换 transport 或增加余额。

## 最小下一轮，不先请求真实调用

1. **AFK继续**：补无秘密的OFD传递/故障/后代测试、预算持久性拒绝原型、core无崩溃生命周期探针，核对固定client既有事件源。测试只用临时根和合成哨兵，不能读取认证、启动Pi或修改宿主。
2. **H4先裁决必要变更**：拿实际代码差异在T1/T2、可行core方向及O1/O2/O3间逐项选择。没有可行方案时保留对应unknown，不需要重问既定Q1–Q10，也不接受泛泛“全部批准”代替具体选择。
3. **H1先做无凭据部署轮**：最终package应含路径化unit/nft、bootstrap/broker/observer代码哈希、差异与卸载恢复、角色读写/出站/内存与fd矩阵、合成负对照、停机条件。所有者只审阅执行root动作；此轮没有auth/model请求，不接触真实凭据。现未具备这些字节，不应马上提交安装批准问题。
4. **H3验证H1适用部分**：先文件/进程/出站/core/回收合成对照，独立复核cgroup空与恢复，失败保留不补跑。只有通过适用隔离后，才能提交下一步H2。
5. **H2再审六格轮**：使用已有六格封印，另冻结真实端点/专用认证元数据、各层预算、完整性观察源、停止/回收与供应商能力/故障方法。任何观察缺口仍阻断。凭据由所有者供给，agent不读内容。H5结论审阅与产品显式激活继续分开。

## 核查来源与本轮验证

- 当前实现：`src/paper_radar/pi_execution/auth.py`、`launcher.py`、`process.py`；`src/paper_radar/pi_supply/protection.py`。`pass_fds`、上下文持有期和父close语义来自这些代码与 ADR-0029。
- 决策：ADR-0029、0039、0046、0047；[A3固定路径报告](../../../docs/verification/issue-167-request-paths.md)。没有修改现有ADR或Contract。
- 本机文档：`systemd.exec(5)` 的 Environment、ProtectProc、ProcSubset；`systemd.service(5)` 的 fd-store/OpenFile。只是本机文档指针，不代表本机kernel支持或部署已通过。`OpenFile`是按路径打开，不能据此宣称已传原锁OFD。
- 本轮仅新增本审查文档；未运行测试/完整门禁，未更改旧证据或固定登记。由主代理合并进行链接/diff与固定范围只读审计。所有需要真实现场验证的主张仍未验。
