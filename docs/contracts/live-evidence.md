# Live 分项证据、受保护账本与共享准入判定

## 用途与范围

`paper_radar.live_evidence` 提供带版本的能力登记、普通值领域模型与纯判定函数。
`evaluate_admission` 只消费显式输入，不读墙钟、主机、业务库或账本，不接收或激活证据。
`receipt` 与 `receipt_v2` 提供 Pydantic 权威回执与批准计划；`EvidenceLedger` 提供受保护接收与只读查询，
`live-evidence receive/show/activate/revoke` 暴露所有者入口。
`service.load_admission_evidence` 对完整请求加载受保护事实并调用同一纯判定，返回结构化投影；
`pi_execution.admission.load_admission_evidence` 延迟转交该完整请求，旧的不完整 EvidenceBinding 仍返回 None。
Screening／Read 正式三检查点与 doctor 消费共享判定，分别见所属 Contract。
`collector`、`sealed_runtime` 与 `deployment` 提供零请求 β 采集、冻结构建与封印脚本；`model_collector` 提供独立批准的固定合成模型采集闭环。实际 root 权限、封印安装和证据激活由所有者现场验证。

## 规则

### 准入用途与独立维度

初始登记版本为 `live-admission-v1`，包含以下六格，均显式分类全部能力：

| 调用点 | 消费者格 | 档位 |
| --- | --- | --- |
| `PiExecution.run_attempt` | boundary、value | 各 low、high |
| `read_execution` | read | low、high |

准入用途不包含或推导根用途。未定义用途被拒绝；登记拒绝空必需集合、重复用途、重复能力、缺少能力分类与必需项空依赖。
版本经引用后冻结，版本变更须创建新版本；旧版本的证据激活不满足新版本。
每个能力 × 准入用途只能输入一条事实；重复输入不论顺序或状态均拒绝，真实历史的唯一事实由账本读取权威按原接收时点与原接收事件序选择。
同格同能力的新失败／unknown 不回退到旧 verified，即使之后合并恢复旧快照也保持。
缺本格记录返回 `evidence_missing` 与 `claim=None`，其他消费者格或档位的状态、时间不填入本格投影。

`CapabilityClaim` 保存原始 verified／not_assessed／unknown、依据、范围、原验证时间和可选观察时点；
`CapabilityEvidence` 另保存 received、evidence_active、revoked、当前适用性、登记版本与执行绑定。
`CapabilityAssessment` 分字段输出这些维度及 expires_at、expired、结构化 reasons；不回写原主张。
其中 applicability 是本次判定的当前适用性：已知执行依赖漂移，或 material_dependent 能力的材料身份缺失／不匹配时，
输出 not_applicable；其他情况保留输入适用性，缺记录为 unknown。输入记录及其原主张不变，未受影响能力的适用性、状态与时间保持。
登记版本、接收、证据激活、到期和撤销仍为独立维度，不单因这些资格缺口改写 applicability。
必需项全部 qualified 才可能 executable；不强制最终 executable=false，也不从站点证据推定整体可执行。
披露型缺证据或资格缺口输出 `disclosure_unknown=true` 和原主张，渲染方必须提示 unknown 及下一动作。
不适用项保持原状态，不单独输出资格阻断；它不表示对应历史 unknown 已处理或已验。

### 到期类别与依赖

以下是初始逐项登记；逗号分列的能力分别有自己的主张与时点。
依赖名称是受控 `BindingComponent`；运行身份的各值都是完整规范身份，不是配置 passed 声明。

| 能力 | 要求 | 到期类别 | 依赖组件 |
| --- | --- | --- | --- |
| auth_cache_current | 必需 | 站点 | auth_cache_current（当前属主、权限、无符号链接） |
| auth_cache_baseline | 必需 | 站点 | auth_cache_baseline（固定接收基线成员与不变量相符） |
| cwd_ancestors | 必需 | 站点 | cwd_ancestors |
| file_isolation | 必需 | 站点 | file_isolation、isolation_policy |
| ipv4_egress | 必需 | 站点 | ipv4_egress |
| zero_core | 必需 | 站点 | core_limits |
| apport_identity | 必需 | 站点 | apport |
| rpc_completion、rpc_eof、rpc_terminate | 各必需 | 未分类 | pi_version、launch_policy |
| model_identity | 必需 | 供应商 | model_tuple |
| single_dispatch | 必需 | 工程 | launch_policy、observer（本地显式派发） |
| no_extra_turns | 必需 | 供应商 | model_tuple、observer |
| supply_tree | 必需 | 站点 | supply、supply_tree |
| instance_tree | 必需 | 站点 | instance、instance_tree |
| pi_version | 必需 | 站点 | pi_version、node_platform |
| launch_policy | 必需 | 工程 | launch_policy |
| isolation_policy | 必需 | 工程 | isolation_policy |
| host_runtime | 必需 | 站点 | host、boot、kernel、landlock_abi |
| pi_public_300_seconds、provider_latency、provider_errors | 各披露型 | 供应商 | model_tuple（并保留各自范围） |
| thinking_effect、date_alias、account_models、account_limits | 各披露型 | 供应商 | model_tuple（并保留各自范围） |
| exact_request_count | 披露型 | 供应商 | model_tuple、observer |
| auth_cache_history、auth_cache_writer | 各披露型 | 未分类 | auth_cache_baseline、observer（不推定历史完整性） |
| external_interrupt（含 E01） | 不适用 | 工程 | pi_version、launch_policy |
| supervisor_exit、ipv6、new_platform、unattended、nas | 各不适用 | 未分类 | 不参与当前资格 |

供应商和未分类能力精确从原 verified_at 起 30×24h 到期；登记可用较短 maximum_age_days 收紧，不能延长 30 天。
接收或证据激活不续期，第 29 天激活只剩 1 天；等于到期即拒绝。格与档不互借。
`earliest_verified_at` 只对显式给定且全部 verified 的主张取最早 UTC 原时点，不生成跨格资格。
站点／工程类免时限要求全部 dependencies 属于本次 checked_components 或 privileged_components；
否则必须有登记的有限 maximum_age_days，无上限且覆盖不足返回 coverage_incomplete。
特权证明的来源与当前有效性由外层的受保护账本和逐调用观察校验服务核验；纯判定函数不读取这些来源，集合本身不是产品授予入口。

当前 now 及可选 ledger_watermark 均显式传入。无时区 now／水位线、当前时间低于水位线时拒绝；
verified 缺原时间、not_assessed／unknown 带 verified_at、无时区或未来验证／观察时点产生受控错误；非法时间输入整体拒绝，不由披露型或不适用分类掩盖。
所有比较转换或等价比较 UTC，保留微秒，不按自然日或接收日取整。

### 绑定分层

`ExecutionBinding` 必须包含全部受控执行组件且每项非空，不接受缺项或重复。
能力按登记依赖精确匹配；组件漂移输出 binding_drift 参数，其他能力的原状态与时间保持。
执行身份包括模型元组中的 provider/model/thinking/sampling/temperature/top_p/protocol_profile/auth_mode；
完整规范身份由 `current_binding.build_admission_request` 只读构造，
`recheck_admission_request` 在领取前复核；范围见[当次完整执行绑定](#当次完整执行绑定)。
材料身份单独传入，仅 material_dependent 的能力要求非空且精确匹配。
初始登记的能力均与材料内容无关；合成材料证明可用于真实资料，但调用方仍须执行现有材料形状、路径和完整帧上限检查。
外发确认、校准与质量资格独立判断。

### 回执与批准计划

回执格式 `v1` 的唯一 Schema 来源为 `receipt.EvidenceReceipt`，冻结名为 `live-evidence/v1`，
目录为 `contracts/live-evidence/live-evidence/v1/`。字段包括登记版本、批准计划身份与摘要、
采集器摘要、轮次、起止时间、完整执行绑定、案例结果／观测计数、失败历史和逐格分项主张。
所有执行组件仅保存 64 hex 身份摘要，模型元组等明文构造由采集方负责；无敏感路径、
Prompt／Profile、token、凭据正文、完整流或错误正文。依据、范围及失败原因使用封闭枚举，
不接受自由描述、额外字段或配置 passed。案例与能力／格不能重复；verified 必须引用成功案例和原时点，
unknown／not_assessed 不带 verified_at；全部观察与原验证时点位于有时区的本轮时间窗口。

v1 批准计划由 `ApprovedPlan` 定义，保存所有者批准的案例顺序、采集器身份、有效窗口、
认证／模型／网络请求上限、轮数及首失败即停条件。计划通过所有者保护入口独立批准，
不从回执自行批准；同 plan_id 同字节幂等，换字节拒绝。`site_beta` 三类请求上限均为零，
只允许现场能力的 site_probe/current_site verified 主张，不能自造供应商或真实 RPC 观察。
接收检查计划摘要、采集器、案例顺序、计数、轮次、窗口和失败历史一致性；
中途停止须最后案例为失败，v1 失败后不能继续本轮或接受计划后续轮。轮次连续且唯一。
这些计数是回执内部观测值，不证明供应商隐藏请求不存在，不代替业务库的 attempt／配额原子预占。

规范回执为 UTF-8 JSON，键排序、紧凑分隔、结尾换行；输入必须已是该规范字节，
因此重复 JSON 键或不同排版不能成为另一种等价来源。完整 SHA-256 绑定规范字节，
其前 16 hex 为 `receipt_id`，接收幂等与后继激活确认共用。重复 ID 且同完整摘要返回既有记录，
追加 receive_duplicate 审计；前缀碰撞或计划同轮不同回执拒绝。接收不激活、不安装、不认证或调用模型。
回执格式版本与账本 schema 版本各自独立；升级回执格式不代表旧账本可读。

### v2 采集额度、失败类与续跑

`receipt_v2.ApprovedPlanV2` 与 `EvidenceReceiptV2` 定义 v2；冻结回执为
`contracts/live-evidence/live-evidence/v2/`。v1 原模型、Schema、规范字节及旧读者保持，
新版按 `format_version` 显式分派，未知版本拒绝。v2 增加固定 `domain_id=live-177`、
`round_id`、`history_sha256`、`prior_receipts` 与 `reservation_ids`。
`cases` 只包含本轮实际执行的未通过模板后缀，最后一项失败时恰好有对应失败记录。
原轮与续跑轮分别保存分项主张；先前主张的原 verified_at 不进入新时间窗口，不被刷新。

`collection.ProtectedCollection` 是封印 root collector 的公共边界。所有者先对既有受保护
账本显式调用 `initialize`，从 schema 1 增量建立 schema 2 的 `collection_facts` 和固定域；
既有计划、回执及事件不改写。重复初始化只核验既有谱系，不建新域、不清历史；缺失表、
缺失事实、未知版本、摘要链／独立审计不一致均拒绝。域的授权来源是 #177 的 Live 40/40
裁决和这次所有者 cutover，计划没有创建其他域的接口。重部署沿用同一个 root 账本，
collector 不能因库或谱系缺失重新建立零余额。这里的额度不属于业务 task/attempt 预算。

每次宿主 auth CLI 计 `auth` 1，每次独立 network 操作（含出站负对照）计 `network` 1，
联网总额度为两者之和、累计最多 40；每次向 Pi stdin 写 prompt 前计 `model` 1、累计最多 40。
auth CLI 内部往返不重复计；模型自身 DNS/TLS、开发工具、所有者操作及 loopback 不计独立
联网操作。`start_round` 绑定当前完整执行身份和首个未通过案例；`reserve` 每次创建新的
单次操作预占，在 root 保护事务中核全域与计划余额并持久化，再由受信调用方派发一次。
预占不能重放、退回或跨轮复用；预占后崩溃和结果未知仍消费。派发前准入拒绝不预占，
空轮可 `cancel_round`，不伪造成失败轮；已有预占的轮不能取消。

同模板同失败原因连续递增，原因变化建立当前新类、从 1 开始；只有本模板成功清零，
其他模板成功不影响它。类键是模板 ID × `FailureRecordV2.reason`，不含计划、轮、文件名。
第三次同类失败持久停止整个域；安全类首次停止；第六个累计失败轮全局熔断。
安全原因是 `isolation_failed`、`identity_mismatch`、`sensitive_output`、`permission_failed`、
`ledger_untrusted`、`source_untrusted`、`interrupted`；协议／资源／collector 普通故障不能
用来改写安全事实。凭据成员意外变化、core/report 和出站意外放行归 isolation；WS 归 identity。
成功不清累计失败轮数、消耗或停止事实。

`complete_round` 在同一受保护事实中核本轮案例顺序、完整绑定、预占 ID 与逐案例计数、
跨轮来源和历史摘要，再保存结果、通过模板和失败状态；它不接收或激活证据。
所有者 `receive` 另核精确 root 完成事实，并要求 `prior_receipts` 的原来源已经受信接收且
完整存在，故先接收早轮，再接收依赖它的续跑轮。未知完成结果不能凭普通 JSON 补成成功。
续跑核当前窗口、类停止、熔断、剩余额度和计划轮数；仅相同完整绑定的通过模板跳过。
`recover_interrupted` 仅在调用者已持有 collector 独占锁并确认旧进程结束后使用，未终结轮
按 interrupted 持久停止；不会重新派发旧预占。

三个例子：A/protocol 失败，随后 B 成功，再 A/protocol 失败，A 的当前链为 2；
预占 auth 后进程崩溃，用量仍为 1，恢复后 interrupted 首停；计划 P 已通过 A、在 B 失败，
所有者批准 Q 的同模板顺序后，Q 仍共享原消耗和失败链，只重试 B，并引用 P 的原回执。
改名计划不增加余额或消除停止。业务预算、接收和显式激活仍分别判断。

### 账本信任与查询

默认位置为 `/var/lib/paperradar/live-evidence/ledger.sqlite3`，受保护来源留存在相邻 `inbox/`。
`EvidenceLedger.initialize` 只在已受保护的 root 目录与 inbox 内建空库；不创建或修复部署。
写连接要求 euid 为受信属主，产品入口使用固定 root 策略，不提供 uid、路径或信任策略 CLI 覆盖。
源码 API 的 `LedgerTrust` 可替换 OS fixture，离线测试使用临时锚与模拟不同产品 uid；
它不是产品接受外来账本的授权入口。同 uid 修改源码仍在本权限威胁模型之外。

账本、来源及通向 `/` 的全部祖先必须 root 所有，无符号链接，无组／其他用户写权限。
来源必须是固定 inbox 的普通单链接 `.json` 文件，最多 1 MiB，读取使用 NOFOLLOW；
数据库也须普通单链接文件。读写前发现任意 journal/WAL/SHM 残留均保守拒绝，不尝试热恢复。
数据库要求 DELETE rollback journal、quick_check 通过且包含必需表列；不使用业务 Alembic。
账本初建为 schema 1；显式采集 cutover 后为 schema 2，与回执版本分开管理。新版支持这两种
已知布局，schema 2 必须有采集事实表；旧版拒绝 schema 2，未知更高版本既不写也不读。
兼容演进不使用业务 Alembic，回执格式升版不推断账本兼容。

`approve_plan`、`approve_plan_source` 与 `receive` 使用保护写事务，成功与重复接收和受控拒绝均追加审计，
事实不被覆盖；账本自身不可信时不补写失败事件。`show`、`show_plan`、`list_received`、`audit` 只读打开，
不创建文件。回执查询重新核对原来源存在、权限与精确字节，以及计划／回执摘要；来源丢失或改变即拒绝。
`connection(writable=False)` 提供受保护只读连接；写连接检查特权身份。
账本与受保护回执需单独备份；恢复失效与重新激活规则见 ADR-0055 及下文。
`received_in(connection)` 供共享读取在同一 SQLite 快照中核验来源；只读连接显式开启读取事务。

`paper-radar live-evidence show [--receipt-id <ID>]` 显示回执脱敏摘要，
`show --plan-id <ID>` 只读查询批准计划；v2 另从权威事实显示 auth／独立 network／联网合计／模型
已用与剩余、各模板当前失败原因和连续数、累计失败轮数、停止／熔断与下一动作，两种选择互斥。
查询不初始化账本或采集域、不创建文件、不联网。
`receive --source <固定inbox回执> [--plan <受保护计划>]` 只经所有者 sudo 的封印入口使用，
可先显式批准计划再接收；不能从用户可写仓库或虚拟环境执行 sudo Python。
未部署封印入口时不能将当前仓库命令当成受保护入口。所有 `--help` 不打开账本、不联网。

### 证据激活与不可逆撤销

`EvidenceLifecycle.review` 展示完整脱敏回执 JSON、全部绑定摘要、准入用途、登记版本、
分项原状态／原 verified_at／expires_at、本次 eligible 原因及恢复屏障序号。
`activate` 要求准确输入回执的 16 hex 短 ID，写入前在保护事务内重新判定；
激活范围只等于本回执当前仍为最新事实、有效且适用的 verified 分项与本格 required 集合的交集。
空集合拒绝，unknown、披露型和缺失模型能力不会因此取得资格。接收、审阅与激活均不续期。
写入前重新生成的完整审核摘要与 eligible 集合必须和所有者确认的内容相同；
来源、登记、主张、期限、撤销、最新事实或恢复屏障改变时拒绝，不能静默激活剩余子集。
阅读耗时不作为能力或观察期限；同一有效范围重复激活返回 existing，不追加授予。
恢复屏障后必须重新审阅确认。
记录绑定回执、准入用途、登记版本与具体能力，登记升版不会扩大既有范围。

`EvidenceLifecycle.tighten` 按登记依赖撤销受影响能力；传入未知影响时保守撤销本格全部主张，
指定失败能力同样只能收紧。重复撤销保持同一资格结果并追加审计，原主张与时点不变。
撤销不可逆，被撤销旧回执不能重新激活；须以新的有效证据和新回执取得资格。
`mark` 追加待撤销事实并同时拒绝相关资格，合并前后保留待撤销披露。
产品不写账本；所有者 CLI 与 helper 均只使用固定 root 信任策略，写连接检查特权身份。

`live-evidence activate --receipt-id <ID> --use-id boundary-low` 在完整摘要后提示短 ID；
只有所有者输密码授权的封印 sudo 入口可以授予。`revoke` 接受相同选择，撤销整格回执资格。
NOPASSWD helper 的固定安装入口为 `/usr/libexec/paperradar/live-evidence-tighten`，
模块入口 `paper_radar.live_evidence.tightening.tightening_main` 仅接受：

- `tick`：用 helper 自己的 UTC 墙钟打点，不接受外部时间；
- `revoke|mark <16hex回执ID> <准入用途> <逗号分隔组件或unknown> <逗号分隔失败能力>`。

组件与能力均使用闭合枚举；未知动作、自由路径、自由时间、接收、激活与恢复参数全部拒绝。
特权操作只使用 root 所有的固定冻结部署入口，仓库／venv 中的代码不能作为 sudo 执行来源。

### 当前观察与认证/cache 基线

所有者 activate 固定读取 `/var/lib/paperradar/live-evidence/inbox/current-observation.json`，
由封印采集器产生规范 UTF-8 JSON（同 canonical_bytes 的排序、紧凑分隔与末换行规则）。
内部 `CurrentObservation` 只有 `observed_at`、`binding`、`checked_components`：
前者为有时区的 UTC 时点；binding 完整覆盖全部 BindingComponent，值为 64 hex 摘要；
checked_components 无重复，只列本次确实覆盖的组件，不是 passed／verified 或激活声明。
`load_current_observation` 重新验证来源保护与规范字节，拒绝 naive、未来时点及超过 60 秒的观察。
等于 60 秒仍可读取。所有者手动输入准确短 ID 后，入口调用已部署的固定零参数
`/usr/libexec/paperradar/live-evidence-refresh`，经固定 sudo -n 入口、清空环境且不传入自由路径或参数；
失败、超时或不可用均拒绝。入口重新读取同一保护来源，要求观察时点不早于本次刷新开始，
完整 binding 与 checked_components 集合和已审核观察相同；新的 observed_at 本身不视为事实漂移。
最后用真实当前时间再次核观察的 60 秒时效，再在保护事务内核同一审核内容并追加激活。
阅读可超过 60 秒；60 秒仅约束执行前的当前观察，不改变能力原 verified_at 或期限。
事实变化、原证据到期、时钟回退或当前覆盖撤回均拒绝，须所有者重新审阅。
普通产品请求不能自行声明特权证明；未观测组件不能填入 checked_components。

例行刷新入口 `protected_observer.refresh_once` 在同一个 `collector.lock` 内核实际固定
固定 nft JSON/native/JSON 三视图、受保护 `placement-target-v1.json` 与实际
`/proc`/cgroup 祖先、锚定身份；本地上下文在不可逆降权的 product uid 子进程内只读重算，
metadata_only 模式跳过隔离探针及 Node 执行，不重复完整 β。`observer_identity` 哈希 `OBSERVER_MEMBERS` 列出的
封印运行时观察代码、入口、配置及封印清单；PID/启动时间不构成 observer 身份。
`egress_identity` 绑定实际规则与放置上下文，忽略 metainfo 及计数器 packet/byte 数值。
nftables 1.1.6 的 JSON 输出遗漏 socket cgroupv2 level；固定读取同时查询带 handle 的
native 文本，并逐 table/chain/rule handle、comment、顺序与 RHS 关联，仅从实际 native
规则补齐 level。完整读取前后分别用固定只读 Netlink GETGEN 核相同非零 u32 generation；
包络、来源、代际未知或改变均拒绝。这是有限宽度代际一致性检查，不宣称排除无界完整回绕。
代际稳定且两实际视图库存一致时，表丢失、selector 缺失/变更、额外 chain/表达式等已确认
实际结构变化仍返回实际快照，由例行刷新判为漂移并持久收紧；不因找不到预期 selector
改报临时不可用。generation 失败或双视图不一致则保持本次观察不可用，不冒充已确认漂移。
generation 不进入稳定 egress 身份；其他表在两次独立采集之间的变更不改变相同项目规则身份。
实际 level 进入 egress 摘要和负对照前后 counter 结构比较。规则核验只对完整正确的
IPv4 地址与 TCP/UDP 端口固定签名约简可由 payload 协议蕴含的 nfproto/l4proto 依赖；
对应同版官方 golden 的两 payload 回读形式，地址、端口、协议、顺序与其余表达式仍精确比较，
额外或错误 meta、缺少限制均拒绝。所有安装、观察及 counter
消费者共用此固定读取，不从预期规则补造缺失字段。
封印清单传递绑定 nft 模块字节，入口在导入前逐成员验 SHA；`OBSERVER_MEMBERS` 清单保持
既有成员，历史 runtime 的 observer 身份仍按原字节计算，不要求旧树含后继新增模块。
封印部署负责安装这些固定来源，入口不接受调用方自报摘要或自由命令。

候选核验后原子发布；`observation-refresh.json` 保存独立 `RefreshStatus` v1（result、
recorded_at、snapshot_sha256、changed_components、pending_revocation、placement_mismatch），
`observation-refresh-history.jsonl` 保留受保护追加历史。临时失败只追加不可用结果，保留上次
成功快照及原 observed_at；即使旧快照在60秒内，当前调用仍拒绝。进程重启保留文件，只有
新有效快照才恢复新鲜度。规则/目标/绑定漂移按登记依赖持久收紧；来源失信保守收紧六格。
漂移优先于 stale，落账失败保留拒绝 marker 与待撤销披露。无锁读者跨过原子发布而无法配对
快照与刷新摘要时只拒绝本次，不把读时配对未知误报为已确认来源失信。后续成功不复活撤销、不更新
任何案例 verified_at、不领取或重置计划/失败/联网/模型/业务额度，也不形成 verified、
receive 或 activate。`protected_collection_lock` 与 `refresh_under_lock(lock_fd=...)` 供
封印 collector 在同一实际锁 fd 内组合，不能持独立 fd 锁再调用自锁入口。

首次严格 β 在实际模型证据前执行；其生成 site-only 观察后，首次实际保护刷新将占位变化
记录为漂移而保持拒绝，再次独立核验相同事实才可恢复新鲜度。旧收紧和失败不清除，随后
真实出站/模型证据仍须独立采集、接收及所有者激活；不自动重定真实漂移基线。

`auth_cache_stat.metadata_digest` 是采集与消费者当次比较共用的 `auth-cache-stat-v2` 算法。
首次 v2 基线来自受保护批准采集，经过既有 receive 与所有者显式证据激活；不从旧 v1 漂移或当前目录自拍建立可信资格。
输入固定为单元素 `(credentials_dir,)`，只打开目录 fd 和 stat 成员，不打开成员正文。
清单按根索引和目录内名称排序，以相对名记录目录和普通单链接文件；成员名、集合、类型、
dev、mode、uid、gid、nlink 均参与固定摘要。仅根 `.` 和直接成员 `auth.json`、`models-store.json`
豁免 ino、size、mtime_ns、ctime_ns；其他成员全部九个 stat 字段保持比较，目录 nlink 仍按基线比较。
对象 format/members 经排序键、紧凑 UTF-8 JSON、末换行后 SHA-256；路径绝对名不进入摘要或错误。
最多 4096 项、32 层，拒绝软链、普通文件硬链接、特殊节点、`node-compile-cache`、读取失败和采样期间变化。
遍历期间即使是可演进字段也以完整 stat 复核，根被替换也拒绝；未知目录／成员改变摘要而无法取得既有资格。
固定基线不随正常刷新、原子替换或失败自动更新，正常演进不刷新 verified_at 或期限。
当前根／祖先属主权限与隔离另行检查，stat 不证明 `auth_cache_history`／`auth_cache_writer`，两项保持披露型。

`baseline.metadata_digest` 的 `auth-cache-stat-v1` 算法和旧读者保留原字节，仅供历史严格比较；
v1 未豁免任何字段，其证据不会被转换为 v2 资格。新启动／准入策略变化还会单独阻断旧策略资格。

### 当次完整执行绑定

`pi_execution.current_binding.build_admission_request(database, binding, *, use,
credentials_dir, now)` 是执行消费者和诊断共用的只读构造入口。
供给/实例整树经现有只读安装保护复核；当前 manifest、Node/平台、启动/隔离/准入策略、
模型元组、host/boot/kernel/Landlock、cwd/祖先、文件隔离与零 core 策略均逐次绑定。
Apport 绑定公开 dpkg 准确包版本、程序和整个 `/etc/apport` 配置目录、
`/etc/default/apport`、core_pattern 与 suid_dumpable；不运行认证、模型或网络探测。
模型元组沿 ADR-0054；材料正文不进入该身份。显式代理属于启动上下文，改变即改变摘要。
组件普通值经规范紧凑 UTF-8 JSON SHA-256；供给/实例树沿既有 tree-v1，
host/boot 和公开文件按原字节摘要；认证/cache 沿 auth-cache-stat-v2。
专用凭据目录同时是本通道固定的认证/cache 根，固定输入顺序为单元素 `(credentials_dir,)`；
不扫描个人 Pi、环境目录，不读取成员内容。

IPv4 出站和 observer 只由当前固定受保护观察补足覆盖。
只有其站点本地上下文与本次复核一致，才使用该观察声明的覆盖；仅 MODEL_TUPLE 不属于
站点保护上下文，每格完整请求及模型证据仍精确比对该组件。其余组件不匹配时保留当前身份，
舍弃旧特权覆盖，让共享判定拒绝缺口。观察不是能力证据，不提升 unknown。
`recheck_admission_request(request, now=...)` 在领取内只重读同一小型保护来源，
核新鲜度、绑定及特权覆盖未撤回；不重复整树工作。
`local_binding_components` 与 `site_binding_components` 供封印采集侧复用相同摘要规范，
它们本身不授予、不接收、不证据激活。内核身份使用 `os.uname()` 的五个原生字段
（system、node、release、version、machine），不调用外部命令查询 processor；
该摘要随准入策略版本绑定，旧策略的六字段摘要不能取得新策略资格。

### 单一加载与投影

`AdmissionRequest(use, binding, checked_components, observation=None, refresh=None)` 描述当次身份与观察范围，
后两项只携带构造时受保护观察的诊断信息，不接收证据或授予参数。
`service.load_admission_evidence(request, now=...)` 使用固定受保护账本，加载原主张与独立资格维度，
再调用 evaluate_admission；不联网、不认证、不调用 helper、不写任何事实。
返回 `AdmissionProjection(decision, watermark, pending_revocation, sources, observation, refresh)`：
sources 是本格每个能力选中的回执 ID；decision 的原状态、依据、范围、时间、到期与原因均来自共享判定。
Screening 正式三检查点消费这个投影；Read 与 doctor 的消费者现状分别见所属 Contract，不能各自重述能力要求。
完整当前执行绑定的宿主采集由消费方集中构造，doctor 复用相同只读构造入口；
只读采样在观察复核失败时也改用同一拒绝投影，同时清除可执行及qualified结论；原因与doctor片段不沿用复核前结果。
本接口不把回执自身 binding 当作当前身份，不把短时观察或普通请求当作证据授予。
`unavailable_projection(use, LedgerError)` 为来源/观察失效生成同一受控拒绝投影，避免展示方复制原因映射。

`request_revocation` 先把闭合用途、来源／影响和UTC时点追加到固定
`/var/lib/paperradar/live-evidence-intents/pending.jsonl` 并fsync，再调用固定sudo -n helper。
账本仍产品零写入；该独立日志是ADR-0056接受的只能追加收紧事实的例外，不存授予。
目录最终root所有0755，文件root:封印产品gid、0660、regular单链接且必须有FS_APPEND_FL。
每次读／写核完整祖先、fd属主／组／模式／类型／链接数与ioctl属性，不接受产品创建的日志、
用户pending、业务快照或来源缺失作为空记录。内核只追加与root父目录阻止同uid删除、截断、
覆盖、替换、硬链接或清旗标；真实OS效果须owner现场验证，不由离线模型证明。

只有owner冻结部署的 `provision-intents` 可初始化；不在NOPASSWD helper中。
初始化先持久封闭目录为0700，原子追加恢复屏障并撤销全部cutover前回执的六格资格，
不读旧用户pending，也不将其缺失当干净。写入绑定账本cutover身份的首记录、0660权限、
设置只追加属性并fsync／fd复核后，才公布目录0755；任何部分状态保留阻断，不自动补建或修复。
已有完整日志仅核验，不清空、轮转或复位；卸载、重装、账本恢复与业务恢复均保留。
旧原主张／verified_at、失败、stopped、预算和归档保持；新受信计划／实际新证据仍须owner手动激活。

即使账本暂不可读，也可向已经封印的日志追加；helper失败返回false但日志拒绝跨进程保留。
若日志写入/fsync失败仍尝试现有helper，只有root事务成功才返回true；两者都失败则受控错误，
不能声称已持久。满8MiB、单记录超过16KiB、损坏／残缺、未知版本、失信／缺失或不支持ioctl均拒绝，
不以普通文件降级。首记录必须匹配同一受保护账本的cutover事件，日志事实只可使旧资格更窄。

`request_use_revocation` 在首次物理来源丢失／失信或已知漂移导致绑定构造失败、尚无sources时收紧本格；
意图按接收时点截止覆盖当时已有来源，新接收仍须独立核验和owner激活。
固定helper的 `revoke-use` 只按受保护receipts登记追加本格撤销，不读丢失inbox、不接受自由路径或时间。
observation_stale、能力自然到期、未测或未激活只拒绝当前执行，不产生不可逆收紧；
与已知漂移或明确失败并存时，也不把这些普通资格缺口额外计为失败能力；未知影响仍保守收紧。
同事实的新鲜观察可恢复适用性，不续原verified_at，不解除真正撤销。
root冻结owner的 `load_owner_admission_evidence` 复用同一日志／账本判定core并核root身份，
安全回执把raw_active与当前active／qualified分开，不绕过pending；产品入口仍只用固定OS来源。
`request_time_tick` 只请求固定 helper 用自身时间打点；失败必须由执行消费者拒绝，不能当作已记录。

### Live 封印审阅包

显式新模式为 `uv run --offline --locked python scripts/seal_live_bundle.py derive|build`。
`derive` 接收所有者选定的私有 baseline 和完整 SHA，仅读最新 activation，保留原根、uid/gid、
模型元组与用途，仅派生 launch/isolation 当前常量及 snapshot/supply/install 三元组。
它显示字段 diff、完整私有派生 JSON 和按当日 +08:00 计算的未确认窗口候选；输出文件为 0600。
`build` 再核派生输入与 baseline 的允许差异，并在临时编译前后各独立检查五字段。
错误携带已知 expected 字段；空历史、读取失败或任一错配均在创建输出目录前拒绝。
构建同时核当前源码守卫向量的策略与每个源码 SHA，拒绝旧向量配新 root 代码。
窗口必须有显式时区、至少七天；strict β、六格和四负对照共用 UTC 窗口。
日期和网络适用性来源可明确 pending；此时包可审阅，安装入口在资源变更前拒绝。

新模式保留旧 `seal_site_evidence.py` 的 wire、字节生成语义与旧读者，独立输出
`payload.tar`、`run-live.sh`、`REVIEW.md`、`SHA256SUMS`。归档含冻结 Python/stdlib/依赖/源码、
原始 source 身份与版本向量、完整成员 SHA、strict β v1 单轮计划、七份 v2 计划、
六格真实纯编译合成材料、owner 网络适用声明、固定 wrappers/sudoers、管理员 user unit、
resolver、部署配置和安装/卸载/恢复代码。模型材料和请求由权威编译器重建，合成 snapshot 不写业务库。
四负对照与模型均消费既有 `live-177` 累计域；新包不清历史、不receive、不激活、不执行模型或认证。

`run-live.sh install|uninstall|recover` 是 owner 密码入口。普通用户先核完整归档 SHA，
sudo 后只从入口 stdin 内嵌的相同字节建立 root 所有、以 payload SHA 命名的 staging，
核归档/成员清单 SHA、完整文件/目录库存、无软硬链接和保护链，再以空环境及 `-I -S -B`
执行冻结安装器。未知 staging、partial copy、额外成员、旧身份不符及归档冲突均拒绝并保留。
归档和清单不互相包含自身摘要；payload 标记只在 root 已核归档后写入。

Linux x86_64 包含固定汇编构建的静态无 libc anchor；构建依赖本机 `cc`，root 不编译。
管理员 unit 在 `/etc/systemd/user/`，anchor 使用产品 uid 的 user manager，仅保持项目 slice；
其 `LimitCORE=0`，静态程序不读用户 manager 环境。安装核 manager=running、linger=yes、
实际 FragmentPath/DropInPaths、额外执行命令为空、ExecStart/Slice、实际 `/proc` exe/uid/core 限额，
独立读取 cgroup2 全部祖先 dev/inode，并核 subtree 只有 anchor。degraded 或未知 ABI 拒绝。
宿主 systemctl/loginctl/nft/visudo 的解析路径与字节 SHA 由包记录并在安装前复核；
系统动态链接器、共享库和内核仍属于受信 OS 边界。

实际 cgroup 身份部署后确定，以真实层级安装独占 `inet paperradar` 表：四固定 comment 的
独立 drop counter 在允许项之前，允许 ADR-0050 的池 TCP443 与 router UDP/TCP53，
其他项目 IPv4/IPv6 流量 drop。全表结构、实际 handle 与独立目标读回复核，
`egress_identity` 生成受保护 `placement-target-v1.json`；不从规则右值倒推 CG 身份。
resolver 是 `/run/paper-radar/resolv.conf` 的 root 只读来源，由公共 placement wrapper
绑定到私有命名空间；不改全机 resolver、上游路由或 host capability。

NOPASSWD 仅包括固定零参数 collect/refresh/model-collect 以及既有有限收紧入口。
root 只执行冻结代码；持密 auth 和模型由产品 uid 执行，预算、窗口、停止和 inbox 发布
继续由现有 collector 权威控制。严格 β 内有合成 Landlock 拒绝/允许与零 core 对照，
负对照仍是实际 socket 与 counter 归属验证，离线结果不授予现场资格。
首 β 成功后第一次真实 refresh 将 placeholder→实际观察保留为 drift 并收紧；
第二次独立同事实观察才 available，随后才运行四对照/六格；不得清撤销或用新 plan 绕过。

旧 credentials 下若实际存在 `node-compile-cache`，构建仅读其根 lstat，封印完整 metadata。
owner 审阅并停止相关调用后，安装器在不可逆降权、关闭 root fd 的产品子进程内，
按固定 metadata 用同 FS `RENAME_NOREPLACE` 迁到凭据根同级辅助归档；不列目录/读正文、
不复制、不删、不覆盖。未知来源、目的地已有、权限/跨设备错误均拒绝，初次 v2 β 不豁免旧成员。

`deployment-v2.json` 记录准确 payload/manifest、阶段与 prior journal；它不是准入授予。
旧格式升级先核旧全树、三个旧入口及 sudoers，再原样归档；后继 v2 升级另保留 prior journal，
关闭旧观察/dispatch、核空项目范围后退役旧目标再部署。全部 ledger/inbox、intents、失败、
stopped、撤销、已预占额度和旧 runtime 均保留。同 SHA 已安装重跑只核现状，
不重跑已通过案例或初始化谱系；已识别的阶段可续行，部分/未知状态不猜测回滚或清理。

`LinuxLiveHost.unit_properties` 仅接受两个固定项目 unit；anchor 的六个额外执行数组由
固定 `/usr/bin/busctl --user --json=short get-property` 从 systemd Service 接口读取。
六行必须各自明确为 `a(sasbttttuii)` 空数组，缺行、重复键、类型/结构异常、非空或工具失败
继续拒绝；`systemctl show` 省略字段不视为空。FragmentPath、DropInPaths、ExecStart、
Slice 与软硬 LimitCORE 继续独立核对；`busctl` 纳入封印 `host_tools` 的解析路径与 SHA。

更换字节的 `recover` 仅另接受明确的 `resources` 中断：新包的 `upgrade_from` 精确指向
pending payload/manifest；原 journal 可以是至多 16 层、无重复 payload 的完整
`resources` 链，每层必须为准确 canonical journal，phase、payload/manifest、
`upgrade_from`、封印 deployment 声明、独立 ancestor archive 与原 history 字节逐项一致，
链末的 `previous=null` 仍精确绑定原 legacy 升级归档。pending runtime 和全部已发布资源
均逐字核验。所有待替换 resources 祖先及新包的 strict β 与七计划均不得有计划登记、回执、
事件、计划来源、停止标记、部署 epoch 或 target；其他 plan ID 的登记/回执/inbox
若属于旧新 collector 也拒绝。schema1 只读核原三表及无 v2 事件，
schema2 重放已有谱系，不在预检初始化或升级。其他 legacy 历史允许保留；旧观察若属于
pending/新包 observer 则拒绝。普通安装、更早/更晚中断阶段及未知来源不取得此能力。
固定宿主检查要求无项目 nft 表、管理员 anchor 身份正确且项目 subtree 只有该 anchor。
首次替换的任何旧资源变更及新 history/journal 发布前，先用完整固定 native nft 程序在
root 子进程的独立网络 namespace 内提交、双实际视图回读并校验，确认子 namespace 与宿主
不同才允许临时提交；随后以相同程序对宿主执行 `nft --check`。没有网络流量、宿主规则
修改或其他 namespace 设置，预检失败保留原资源与 journal。实际配置时再次检查同一程序，
由固定 native 批次原子提交；仍使用实际 cgroupv2 level 与独立 dev/ino，四 counter、
原三允许及剩余 drop 不变。工具拒绝只公开固定 stage reason，不输出 raw stderr。
核对完成后保留原 journal，记录 `replacing_resources`，封闭旧观察并仅停止已核 anchor；
核空 subtree 后记录 `resources_stopped`，精确移除已核资源并原样归档 pending runtime，
随后进入原 `archived` 安装路径。各已记录断点按旧新身份重核后续行，未知字节和其他进程
均阻断，不停止其他 scope、删除未知 nft 或清空旧历史，不恢复激活。

卸载先封闭当前观察、移除 dispatch，再停止项目 slice，独立核无活进程后移除本包资源。
恢复重新核实际资源/CG/规则；重启后的 `/run` 或 CG 丢失需要 owner 显式 `recover`，
不常驻 root 自愈。不恢复旧激活，不改变旧回执/成功时点；新绑定不符原 strict β 来源时，
模型继续拒绝，需要新的已审计划/包取得新来源。正常刷新由下述独立事件评审；缺来源保持 unknown/未验及停止 gate，不能以三次调用、stat 演进或成功模型响应替代。

### β 站点采集与封印部署

非特权构建入口为 `uv run --offline --locked python scripts/seal_site_evidence.py`，
显式接收 `--site`、含时区的 `--starts-at/--ends-at` 和不存在的 `--output`。
`--help` 纯本地，不读站点、凭据或数据库。`SiteConfiguration` 保存所有者选择的产品 uid/gid、
业务数据库和当前snapshot、固定安装路径、四根、专用凭据目录、完整声明绑定与主张准入用途；它是私有部署配置，不进入回执或公开输出。
构建输出固定的部署/卸载脚本、单个普通用户入口run-g2.sh、封印owner-workflow.sh、
无链接payload、批准计划、站点配置、REVIEW.md与SHA256SUMS。
Python 解释器、标准库、锁定依赖、PaperRadar 源码和入口一起复制；部署后不从仓库、`.venv`、
PYTHONPATH、用户 site、`.pth` 或环境读取运行代码。宿主系统动态链接器/系统共享库仍属于受信 OS 边界。
collector_sha256 是 site/plan 之前的冻结运行闭包逐文件摘要清单身份；脚本另绑定 payload 的完整 SHA256。

所有者审阅确切字节后，只运行REVIEW所列run-g2.sh，输入一次sudo密码，其他G2步骤由脚本执行；
没有其他read确认或手动chown/复制步骤。入口先核包内四件固定SHA，再一次sudo -k只用系统工具
从入口内嵌精确字节冻结owner-workflow/deploy/uninstall/payload到root所有的固定`/var/lib/paperradar/live-evidence-staging/`，
冻结脚本与大payload经stdin传输，不进入exec参数；root不读取用户可换链来源。
核对同四SHA，再执行root冻结owner-workflow。脚本拒绝参数、非root、错误执行位置、软链、
非root属主或组/其他可写的完整路径链。普通deploy在任何chown/install前核对既有目标，
不将不受信旧目录转换成信任根。

owner-workflow是该次所有者审阅的显式空cwd预配，不由普通deploy或NOPASSWD入口调用。
它只接受固定`/srv/pi-cwd`为所选产品uid/gid、0700的无链接空目录，或已预配root:root0755空目录；
完整祖先链须root所有且组/其他不可写。将目录chown root:root、chmod0755后，
重新核对属主、权限与空目录，再走原deploy/collect/receive链。非空、链接或其他状态拒绝，
不读取、删除或移动成员；后检失败保留竞态写入数据，不自动回滚权限。
owner预配cwd不算本包创建，默认卸载保留。全部执行代码来自root冻结副本，
不从repo/.venv执行root代码；run-g2只以普通用户运行。新入口/workflow字节均须重新审阅。

阶段与结果持续输出，receive返回实际receipt_id；成功末行明确G3证据激活未执行。
拒绝保持原退出码，stderr输出受控原因、固定stage/resource及所有者下一步。
SHA OK只证明对应复制校验，不能证明部署/采集/接收完成。
run-g2仅自动化G2，不包含activate或G3短ID确认，不使产品executable=true。
普通 deploy 对已存在 runtime 仅接受相同 payload 身份，文件清单每次启动复核；不同字节拒绝。
非特权构建可同时指定 `--upgrade-from-payload <旧payload SHA256>` 与
`--upgrade-from-manifest <旧manifest.sha256文件SHA256>`，生成单独 `run-upgrade.sh`／`upgrade.sh`。
两个值必须成对且为小写64 hex，校验在创建输出目录前完成；普通包保持原入口及行为。
升级包的 build-identity.json 另记录两个旧身份，REVIEW.md展示归档、失败与独立G3边界。
新root字节仍须所有者重新完整审阅，旧包批准不能迁移。

run-upgrade先在普通用户态核包内固定SHA，再一次sudo -k从入口内嵌字节冻结到root所有staging并核相同SHA，
只从root冻结upgrade运行。它先核现有ledger/inbox保护及root所有0755空cwd，
再核旧payload标记规范字节、旧manifest文件SHA、完整文件与目录闭包及逐文件哈希。
所有成员须root所有、无链接，文件单链接且为0644/0755、目录0755；额外空目录也拒绝。
三个旧入口须root所有、单链接、0755且逐字节等于旧wrappers，sudoers须0440且等于旧副本。
任何旧身份、成员、保护或字节变化，以及已有归档／runtime.new，均在归档前拒绝。

通过后只将旧runtime原样移动到同级 `live-evidence-runtime.archive-<旧payload SHA256>`，
不覆盖任何已有对象；只移除刚核对过的旧入口／sudoers，其原字节仍完整保存在归档中。
随后调用新冻结deploy安装不同的新runtime，并按新collector身份的新计划真实零请求采集与接收。
旧账本/inbox/回执/计划/撤销/stopped/失败历史和业务预算均保留；不重装Pi、不compile或写业务库。
升级输出实际新receipt_id，不声称旧回执已由新代码核验，不自动激活或扩大能力。
未选择 `--owner-closure` 时，G3由所有者另行完整审阅新回执并本人手动确认；新owner入口在确认后真实刷新当前观察。
升级成功重复执行同包拒绝旧身份不匹配；中断保留归档与当前状态，不自动删除、回滚或续跑。
所有者须核明现场再准备恢复方案。默认uninstall保留旧runtime归档及全部历史。
源代码准入策略为 `pi-admission-v17`，[当前 D7 显式清单](../../tests/fixtures/live-admission-source-guard-v17.json)
与源码守卫共同固定相关实现；v1–v15 的 D7 向量与摘要锚原字节保留。
v7 增加共享用户 scope 双阶段放置、封装、只读 resolver 和只读诊断；保留固定认证基线 v2、helper 临时布局与 v2 额度／回执／账本错误权威，继续显式覆盖两份 after-backup 续行工具、共享检查点、站点回执构造、树身份与所有者入口。
策略身份变化后不能继承旧策略的执行资格；新包须所有者重新审阅、部署并按新证据显式激活。
源码守卫约束审阅流程，不防范同 uid 同时篡改源码和守卫本身。

既有部署器仅安装固定零参数 `/usr/libexec/paperradar/live-evidence-collect` 与仅收紧的 `live-evidence-tighten`；后者由有限解析器核对 revoke/mark/revoke-use/tick。
额外的固定零参数观察刷新和模型采集入口分别路由到 `runtime_main refresh` 与 `runtime_main collect-models`，新 Live 封印模式安装精确 wrapper/sudoers 和完整库存；这两个入口不接受路径、模型或动作参数。
`live-evidence-owner` 不在 NOPASSWD 中，接收/批准/激活/恢复等放宽动作均须所有者明确授权。
部署脚本的固定计划批准及 receive 属于该次所有者审阅命令的一部分，不自动激活。
真实安装时，所有者须私下确认产品用户没有等价 root 的组成员资格、能力或任意 sudo 通道。

采集 root 父进程只管理固定受保护输出和冻结代码。现场观察 fork 后清空环境与补充组、不可逆
降到产品 uid/gid 并禁 ptrace，不在降权与观察之间执行用户环境；业务库、整树与认证/cache 元数据
均以产品身份只读复核供给/安装仍为当前选择，再复用 `local_binding_components`、`site_binding_components` 和 `auth-cache-stat-v2`。
首次 β 与封印模型 collector 另严格复核冻结 snapshot 三元组；例行 metadata-only 观察读取最新有效配置快照，同一供给/安装的材料快照演进不成为执行资格前置。所有本地执行组件、策略及逐调用模型元组仍精确比较，构建器继续要求最新 activation 三元组与封印选择相符。
需要合成子进程的隔离检查也保持产品 uid：只读取合成外部文件，只尝试匿名临时写入，
通过标准严格为 EACCES/EPERM 拒绝；另证实 attempt 写入允许与软/硬 core 限额都为0。
Node 只以产品 uid 执行 `--version`，比对声明版本；不执行认证、Pi prompt 或网络请求。
固定私有配置另记录当前安装绝对目录。root 使用独立 fd/O_NOFOLLOW 读取器从实际文件重算 tree-v1，
不从业务库取得 root 观测值；逐文件拒绝非产品属主、硬链接、特殊文件、外部软链或扫描中元数据变化，
实际摘要必须与产品 uid 的 acquire_install 核验结果一致，否则整轮失败。
后者自身也在返回 expected_tree 前重算实际实例树；root 独立观测进一步避免把库声明当作特权事实。
core 设置仅作用于合成子进程，不修改其他程序或全局 Apport/core 配置。

| β 案例／观察 | 必需能力对齐 | 回执与当前覆盖 |
| --- | --- | --- |
| cwd 与全部祖先元数据 | cwd_ancestors | 成功时 verified；规范组件逐调用复核 |
| 已登记供给与实例整树、版本、Node/平台 | supply_tree、instance_tree、pi_version | 整树与实际 Node 版本均成功才给相应 verified |
| host/boot/kernel/Landlock ABI | host_runtime | 当前公开身份摘要，失败不补值 |
| outside-read/cwd-write/install-write 拒绝与 attempt-write 允许 | file_isolation、isolation_policy | 每个拒绝标准是独立 CaseResult；全通过才给隔离 verified |
| 子进程软/硬零 core | zero_core | 实测通过才 checked；不制造真实 core |
| core_pattern、Apport 版本及配置身份 | apport_identity | 公开身份观察；不读崩溃/日志正文 |
| 专用凭据单根当前元数据与成员 stat 清单 | auth_cache_current、auth_cache_baseline | 不打开成员内容，与逐调用算法相同 |
| 固定启动及隔离策略 | launch_policy、isolation_policy | 仅当前冻结代码/策略身份，不声称真实 Pi 行为 |
| IPv4、observer | ipv4_egress、single_dispatch、no_extra_turns 的相关依赖 | unknown，组件不列 checked；部署工程留 Live |
| RPC、模型真实身份与供应商行为 | rpc_completion/eof/terminate、model_identity 等 | unknown，无认证/模型调用，格/档不互借 |

批准计划为独立 ID、单轮、0认证/模型/网络预算，案例按固定顺序，首失败停止。
每轮持久追加受保护 collector-history.jsonl 的时间/有限案例/摘要，再发布规范回执；失败时先封闭当前观察。
首轮回执和原 verified_at 不覆盖；相同成功计划重跑只刷新60秒观察，不能续能力期限或生成新授予。
任何首失败使该计划持久 stopped，后续不借刷新重试探针；新计划须重新封印并由所有者明确批准。
首次严格 β 模式失败先原子发布mode000观察，普通产品uid无法读取或自行解封；root读取只用于受控诊断，
不把此屏障视为账本撤销已经成功。然后记录受保护待收紧意图，按当前安装INSTANCE摘要，
对所有已接收回执/用途调用既有tighten(components=None)，未知影响保守扩大范围。
原回执字节、主张及verified_at不变。落账失败返回拒绝、保留待收紧意图与不可读观察，不能声称已持久撤销；
后续先重放收紧，全部落账后才移除待办。已停止计划仍不重试探针或恢复观察。
新受信成功计划仅在待收紧工作完成后恢复可读当前观察，不能复活已撤销的旧激活。
未观察组件用带组件名的 unobserved 摘要占位以保持完整绑定，其 checked_components 为空缺，
相应主张始终 unknown；占位不是合成健康值。所有分项都经过既有 receive 规范和 show 回查。
同轮可对六格分别记录全部35能力共210条主张，只复用内容无关的站点测量，不增加认证/模型或探针次数。
CurrentObservation保持当前供给选择的low声明上下文；高档本地消费者重算自身MODEL_TUPLE，
站点能力仅按本能力依赖适用，高档模型/RPC/observer没有verified主张，不表示六格完整可执行。

AUTH_CACHE_BASELINE 递归专用 credentials 全根，按[固定基线 v2](#当前观察与认证cache-基线)比较。
宿主 helper 的 HOME/TMPDIR 为独占临时资源，退出后删除并核验；凭据根出现 `node-compile-cache` 拒绝。
正常订阅刷新只豁免获准对象的指定字段，不重定基线、不追认成员，也不把 metadata 当作完整写史。
普通 metadata I/O 故障与本次完整 stat 并发复核不稳定报告 `observation_unavailable`；失败保留上一成功快照字节和 `observed_at`、原证据状态/时点，只拒绝当次，不领取调用、伪造失败轮或撤销。已经确认的非法节点、成员、权限、供给/安装错配仍报告绑定失信或实际摘要漂移；root 刷新与正式 guard 持久收紧，移除异常不能恢复旧资格。产品 uid 与 root 之间仅传这两类受控失败 token，不传异常正文、凭据或敏感路径。
资源准备可创建临时目录；准备失败不产生任务、attempt、预算或证据激活。

默认 uninstall.sh 移除本包 sudoers、三个入口与冻结 runtime；保留账本、inbox 回执/计划、
失败历史、stopped 标记和 staging。若 cwd 由本部署创建，只在仍为空且受保护时移除；原有 cwd 不动。
同 SHA 可重复卸载/部署恢复，历史与撤销事实不清空；清理账本需要所有者另行显式选择。
中断留下的 runtime.new 不自动删除，须所有者核对后处理，避免覆盖未知部署物。

### 固定模型采集闭环

`runtime_main collect-models` 只接受零参数，读取受保护 `model-manifest.json`、`site.json`、固定材料库存和 `network-owner-confirmation.json`。六格固定顺序为 boundary-low、boundary-high、value-low、value-high、read-low、read-high，各 plan 仅含 `model-<use>` 模板；四对照另用一份 `site_beta` v2 plan，全部共享 `live-177`。所有计划必须已由所有者批准，窗口、collector 摘要、实际 latest activation 三元组、每格可预知静态组件预期、材料／请求 SHA 与确认适用 plan 集合均受检查；入口不初始化账本、不批准、不 receive、不激活。

每次入口持 `protected_collection_lock` 的同一个 fd，通过 `refresh_under_lock` 复用观察。封印集合只允许供给／实例／版本／策略和模型元组等可预知静态组件预期；不嵌入 observer、IPv4、认证/cache 基线或其他部署后现场值。root 同锁真实刷新后，从严格 β 完成源按每项站点依赖精确核对当前观察，结合受保护 placement target 和固定模型元组组装每格完整真实 binding。`inbox/collection-bindings-<manifestSHA>.json` 固定 manifest、站点完成回执、target、owner 确认摘要及完整六格绑定；后续必须逐字相等，已有完成史时缺该来源不能重新登记。没有 baseline 自拍／忽略漂移，也不要求构建时知道未来 cgroup inode 或把包自身 observer 哈希写回包。站点前置读取受保护已完成 β 来源并按登记依赖核对，可尚未 receive/activate；当前观察本身不替代站点成功。`completed_case` 只读重放完整绑定与原完成回执，按模板继续首个未通过案例，既有成功的原 verified_at 不刷新。完成与 inbox 发布之间用受保护 pending 区分中断：只重发已落账、仍有原 pending 的规范字节；已经发布后丢失的来源继续拒绝，不以恢复发布补造来源。可选 metadata sidecar 丢失保持未观测，不重建用量。一格失败即结束本次组调用，普通／安全停止沿既有 v2 状态机，不跨格补证。

产品 worker 清空环境与补充组、不可逆降权、禁止 dump，并关闭继承的 root fd。仅私有有界 socketpair 传输固定 case、阶段／序号、摘要、受控 RPC／校验／终态事实与 nullable tokens；ACK 在 root 原子 `reserve` 后发送。认证在实际 exec-stop 核验后且 DETACH 前预占 auth；prompt 在严格初始化及无主尾记录检查后、首字节前预占 model。失联和中断保留消耗并安全停止；已知放置组只按原核验 PID/start/group 回收。

封印材料经公共纯 `compile_materials`、`build_stage_input`、`build_call` 和 `render_request`，不保存合成 snapshot。显式 `CollectionExecutionContext` 把合成描述与实际 latest activation 安装分开，正式默认仍使用 `use_install` 与完整 guard。`prepare_launch`／`run_call` 复用正式放置及协议内核；boundary/value 分别经权威 Screening 校验及实际 value context，Read 经规范 evidence map 重建上下文及 `validate_read_output_v2(attempt_ordinal=1)`。ACK、进程退出码、仅 Pydantic 或末次降级均不能代替通过。

模型回执只发本格六项 RPC 能力和实际复合 IPv4 项，不重发站点的其余 unknown。错模型与 WebSocket 为 identity_mismatch 首停；协议／usage 失败不伪造供应商错误。缺 usage 保留原 usage_shape 拒绝；totalTokens=0 的用量为 unknown。终态目录只读有界 lstat 与独立删除检查分别记录；完整会话写史保持 not_assessed。额外 metadata sidecar 披露已预占 CLI／prompt 下界、观察层、精确供应商请求及隐藏调用 unknown，不改变 v2 回执 wire。

四对照模板为池外 TCP443、非 router UDP53、非 router TCP53、UDP443，固定无秘密 socket worker 同样经 `PlacedProcess(attempt=None)`；不依赖模型内层 TCP53 拒绝。四条规则以固定 `paperradar-negative-<case>` comment 唯一标识，root 从当前受保护 nft 快照取得实际 handle，不把未来 handle 或 egress_digest 放入 payload。root 每次在目标释放前预占 network，核实际放置／项目子树无并发污染、前后规则身份和对应 drop/reject counter 精确增加一个 packet，其余规则 counter 保持不变。没有实际 socket 发起、counter 无法归属／倒退／额外增长、并发或规则变化均不通过；意外响应为 isolation_failed 首停。所有四项通过后，每格实际 auth/模型权威成功及最终当前复核，才关联四个完成源、owner 确认 SHA 与 egress 摘要形成该格 ipv4_egress。负对照回执本身仍只记录 IPv4 unknown，不能提前授予复合资格。

| 层 | 事实 | 资格意义 |
| --- | --- | --- |
| passed | 固定模板、精确绑定及权威校验已完成，原 verified_at 产生 | collector 成功事实 |
| received | owner 接收受保护来源 | 不等于证据激活 |
| activated | owner 明确启用本格非空分项 | 不补齐 unknown 或失败 |
| qualified | 当前登记、依赖绑定、期限、来源和当前观察均成立 | 正式消费者才可继续完整 guard |

正常刷新没有本次无秘密事件与提交来源时保持未知；metadata 变化、auth 或模型成功不能证明刷新发生。当前 manifest v2 在既有六格操作中分批观察共享封印认证路径，不增加独立探测；供应商真实到期保持 unknown，具体见[正常认证刷新闭环](#正常认证刷新闭环)。

### 封印放置策略生命周期

新 Live 构建在计算 collector 摘要和计划 ID 前冻结 `placement-pre/post` 静态 ELF、`placement/program.json`、native 源码/生成头、AppArmor 原文、未压缩 compiled binary、固定 ABI/include/config 与构建工具/链接输入；`placement/security.json` 同时绑定实际 parser、`true/systemd-run/systemctl/loginctl` 固定工具和两个已启用的 `apparmor_restrict_unprivileged_unconfined/userns=1`。全部产物进入归档 manifest，C/h 进入 source auxiliary 身份；站点字段仍由原 SiteConfiguration 派生，网络 owner_input 全对象及共同 UTC 窗口不变。

策略只附着固定 runtime 的两个专用入口，源码和 binary 保留在受保护 runtime，不写 `/etc/apparmor.d` 或设置自动启动源码编译。安装器只调用已封印固定 parser 加载确切 binary，并逐字回读 kernel raw_data、独立 raw_sha256、wire raw_abi、enforce、attachment 与整包精确 profile 集合；同名未知、未知 attachment、异字节、额外成员或接口/权限不足全部拒绝。只 add，不 replace。旧 v16 依据已经核验的旧 manifest/inventory 没有这些成员，不能用新代码强制要求旧 profile；新 source inventory 声明 native 而整套成员缺失则拒绝。已有 placement 的完整封印身份变化时当前升级拒绝（包括 policy binary 相同但 native/build/security 不同），不能借卸载或“修复”覆盖策略、重绑 marker；本轮旧 v16 没有 placement，首次迁入不受此后续升级边界影响。

旧 installed 升级先完成 epoch/祖先/账本来源认证及新策略只读冲突检查，在第一次旧 history/journal/业务资源写入前准备新策略。独立 `placement-policy-v1-<binarySHA>.json` 绑定全部封印对象身份和 `preparing/prepared/removing/removed` 阶段；加载或无秘密预检失败保留可识别现场。owner root 的短命子进程只创建私有 mount namespace，将已核 staged runtime 和 resolver 绑定在固定路径并保留用户 bus，撤到产品 UID 后执行固定无秘密 true 预检。`--preflight` 只核 native namespace/map/只读 resolver/cap 撤除/seccomp/profile/NNP 链；已有 root 已核 target 时还调用闭合 `--preflight-traced`，在实际 user scope 核 post 的 R、产品 controller SEIZE、单字节 G/EOF、真正 true exec-stop 和同 PID/start/exe/core0/cap0/NNP/namespace 后 detach。installed 升级有旧 target 时在旧资源首写前做完整 traced 预检；初装/停后先准备策略，实际新 target 建立后、安装完成和 epoch 初始化前强制完整 traced 预检，失败留在 resources 阶段。两个模式都不读取凭据、不运行认证/网络/模型，不领取业务预算、刷新 lease 或生成资格/证据。root fork 子进程先枚举并关闭全部非 stdio 继承句柄；只在 root 私有设置阶段临时持固定已认证 resolver/user-runtime fd，设置完成后关闭全部句柄并重定向 stdio、清环境/安全 cwd，再永久移除 supplementary groups、resgid/resuid；产品 Python controller 从不持 root 可写锁/账本 fd，root 不作为 tracer。编译 initial user/mnt dev/inode 必须与 host 父端实际 self/1 一致，预检子端只允许已认证的私有 mount 差异；resolver 规范目标、现有 sysctl 和工具身份每次重核，不修改系统默认策略。

resources、target、已安装恢复和卸载按同一精确策略接缝核验；先禁观察/派发并停止真实项目进程，再移除本项目 exact policy。默认 partial 拒绝，仅明确 recover 且已有精确 preparing/removing 记录时允许处理已知部分，未知成员保持原样。target 退役以按 payload 命名的受保护本轮 pointer 和逐 targetSHA 归档闭合 rename 前/后中断，不选择“最新”归档；同 SHA 多次显式卸载/恢复保留每轮原 target。旧 history、回执、额度、epoch、intents、撤销与 stopped 均保留，不把退役对象或时钟继承当当前资格。

`verify_installed` 和 root observer 都核同一 loaded policy 的精确身份；root observer 读取全部新成员前先核完整保护链并用 O_NOFOLLOW 的受保护 fd，失信 symlink 不产生目标预读，非法工具描述在封印读取层受控拒绝。新封印成员、工具、sysctl/namespace 和 loaded policy 状态纳入原 `observer` 动态组件，不扩 BindingComponent wire；旧 runtime 的原 observer 闭包保持。稳定缺失/异字节属于 `observation_drift`，持久按依赖收紧；跨读 revision 变化、权限/接口暂不可用只报告 `observation_unavailable`，保留上次快照字节、observed_at 和原证据时点。不能把 temporarily unavailable 当来源失信。

同 SHA 恢复要求全部封印身份和可识别阶段仍成立；若实际 initial namespace 身份改变，需新封印审阅，不能照抄旧 audit 绕过。真实 reboot、profile attach、userns/mount/cap/seccomp、scope/ptrace、认证/模型仍未由离线替身证明。[独立 D1 覆盖](../verification/issue-184-apparmor-lifecycle.md) 不增加既有验收分母。

### 时钟与独立恢复

水位线取所有 events 中接收、批准、重复／拒绝、激活、撤销、mark、tick 与恢复时间的单调最大值。
每笔追加均检查下限，读取也检查显式 now；naive 或倒退时间拒绝且写事务回滚。
原验证时间仍由纯规则与接收窗口检查，最大已记录时间不为其续期。

`EvidenceLifecycle.backup` 仅在受保护位置建立独立 SQLite 快照；inbox 原来源必须另行保存。
`restore` 是受保护历史合并入口：在保护事务内核验快照版本、完整性、两个时间下限、来源与摘要，
不覆盖当前尾部接收／撤销事实，保存原接收排序和历史审计，并追加 evidence_restored 屏障。
全部屏障之前的激活失效，不能导入旧激活来放行；有效且未撤销的证据须重新人工审阅激活。
恢复失败整体回滚。损坏在线账本拒绝自动覆盖、修复或重建，需所有者另行恢复受保护部署。
采集 schema 2 的备份包含完整采集事实。恢复旧快照只接受当前谱系的前缀，保留当前预占、失败和停止尾部；不能以备份替换累计历史。谱系分叉或尝试从未知零状态导入另一份域时拒绝。
业务库不参与此备份／恢复，账本操作不连接业务库、不修改 attempt、重试代际或预算。
直接由 root 用旧文件替换整个信任根属于 root 篡改边界，不能由用户态水位线防范。

schema1 的 plans／receipts／events 表定义与 receipt v1 原字节保持；生命周期只追加新的受控事件动作，
新动作的 events.reason 使用 LifecyclePayload 封闭载荷，旧事件 reason 的既有含义保持。
恢复历史事件以 history_ 动作保留原时点，不能被当作新授予。

### 所有者单次收口审阅包

封印构建 `--owner-closure` 把同源owner工作流与新计划选择冻结进payload，必须显式包含六格主张。
`run-upgrade.sh` 仍一次sudo密码，root先核旧字节并原样归档，再执行cutover／新采集／接收。
冻结stdin传输完成后只从 `/dev/tty` 接收本人确认；不能管道传入短ID。没有终端即拒绝。
按新计划在root账本中选择唯一实际新回执；先本人确认boundary-low，再本人确认临时value-low，
备份后做产品uid文件操作／helper失败拒绝演练，root撤销、恢复屏障，最后本人再次审阅并手动确认boundary-low。

owner的产品uid子进程只触碰固定日志与合成临时文件，实际验证删除／截断／覆盖／替换／硬链／清旗标拒绝。
它不可逆降权、清环境／组并设不可dump及no_new_privs，只在该子进程禁止固定sudo helper提权；
通过正式request_revocation记录value-low后必须观察helper失败，新进程共享投影仍拒绝，才继续root撤销。
不改变sudoers／部署权限，失败或未知停止，不把模型替身当作本机支持证明。
恢复保留日志拒绝与root撤销，全部旧激活失效；最终非空站点分项当前适用才写root安全回执。
业务库只读必要预算ID、指纹、代际与attempt计数，前后全部比较，不读取payload／token／正文。
任务及其他写入必须先暂停；journal存在、非空WAL、单独SHM或类型／uid／单链接失信仍拒绝。
允许无侧文件，或metadata证明WAL为0字节（无frames）并有可选可信SHM；不读取WAL／SHM正文，
不删除、checkpoint或切换journal模式。主库路径与固定fd的inode／类型／链接／权限／属主／大小及纳秒mtime／ctime
在打开、每次查询前和结束均复核稳定；自身只读访问可改变的atime不作内容变化证据。
immutable连接只读主文件并跳过锁／变化检测，不是并发保证；显式稳定性检查与暂停写入前提不能省略。
这些条件仅适用于业务预算采样，受保护准入账本的journal／WAL／SHM拒绝规则不变。
原验证时点不续、stopped不重启，不认证／模型／网络、不compile或重装Pi；新进程重读不证明主机重启。

`scripts/issue176_closure.py` 为已经部署并明确人工证据激活的当前同策略 runtime 构建独立包；
它核目标payload／manifest、当前准入策略并内嵌字节，不能拿旧策略现场执行新工作流或替代首次cutover。
v5 新发 owner 配置使用 `initial_evidence_activation`；`initial_activation` 仅作为冻结 v4 配置的只读兼容键。
专用 `issue176_resume_after_backup*.py` 仍只针对其冻结 v4 runtime 与原检查点，不接受当前 v5 runtime 代替旧恢复目标。
旧配置、事件与安全回执字段不迁移，旧部署包原字节保留。
部分／中断状态只保留root检查点，不自动回滚、清理、恢复资格或重新初始化日志。
原 v4 专项操作与续行前提见[对应 owner 方案](../../intent/review/issue-168/closure-owner-plan.md)，不作为新策略的执行批准。
现场验证与正式只读采样的证据归属见[现场安全验证](../verification/issue-168-176-owner-safety-verification.md)。
各次现场结论仅约束其记录的身份与范围，不替代当前树的离线验证。

## 错误与拒绝

`AdmissionReason` 使用闭合 ReasonCode，能力参数为 Capability，组件参数为 BindingComponent；
`capability_required:<能力>` 与 `binding_drift:<组件>` 的 token 由受控参数生成，不接收自由字符串。
其他原因包括 evidence_missing、evidence_not_received、evidence_not_activated、evidence_revoked、
evidence_expired、evidence_not_applicable、evidence_applicability_unknown、registry_version_mismatch、
admission_use_undefined、evidence_scope_mismatch、evidence_conflict、material_mismatch、coverage_incomplete、
evidence_time_invalid、evidence_time_future、clock_rollback、ledger_untrusted。
账本以 `LedgerError.category` 报告 ledger_untrusted、ledger_schema_unsupported、protected_entry_required、
source_untrusted、source_integrity、receipt_invalid、plan_missing／conflict／mismatch／round_conflict／stopped、
receipt_conflict／missing、plan_complete、reservation_invalid、collection_history_mismatch、evidence_activation_empty、evidence_activation_confirmation_mismatch、
observation_invalid／stale／changed、binding_observation_unavailable、pending_revocation_unavailable 等受控原因，错误不包含输入或敏感路径。来源与版本失信的 `reason` 映射为 ledger_untrusted；
纯层不认证账本。CLI 失败返回 2，提示所有者检查受保护部署、计划与来源。
该词表与现有闭合 ExecutionReason 分开，任务结算映射由消费者接线维护，不改写旧 token。

## 不提供／不证明

封印包提供项目 unit/CG/nft／模型采集库存的部署安装及按需受保护观察；不提供常驻特权观察服务或离线现场证明。现场职责见[路线图](../roadmap.md#module-live)。
真实 OS 特权证明与所有者激活不由离线构建提供；独立覆盖和各次验证范围见[覆盖记录](../verification/issue-168-176-review-r1-r2-fixes.md)。旧不完整调用不能自动升级成完整请求。
接收权威只核来源、完整性与内部一致性，不能独立证明没有遗漏的失败；失败历史完备性由采集器与 sudoers 边界承担。
离线构建与合成覆盖不证明真实 root、供应商或模型行为，不替代所有者激活、真实材料外发确认、根用途或校准资格。
威胁模型防范同 uid 产品进程、测试、Agent 工具伪造或篡改受保护证据及激活记录和配置 passed 自证；
纯层本身没有写入或授予路径，接收／计划批准也不产生激活资格。不防范同 uid 直接修改源码，该边界由代码审阅与策略版本守卫承担。
真实 OS 信任根与抗回滚保证不由这些普通值或离线测试建立。

## 相关

固定 nft 规则规格与字节保持的独立覆盖：[审阅收尾台账](../verification/issue-183-nft-review-followup.md)。
采集与部署依据：[#172](https://github.com/MeteoBoy4/PaperRadar/issues/172)；独立覆盖见 [β 采集台账](../verification/issue-168-172-site-collector.md)。
依据：[父票裁决](https://github.com/MeteoBoy4/PaperRadar/issues/168#issuecomment-6722370306)、[#169](https://github.com/MeteoBoy4/PaperRadar/issues/169)、[ADR-0051](../adr/0051-separate-live-binding-capabilities-and-activation.md)。
补充决策：[ADR-0052](../adr/0052-version-admission-uses-and-capability-requirements.md)、[ADR-0053](../adr/0053-expire-capabilities-by-evidence-class-and-coverage.md)、[ADR-0054](../adr/0054-separate-execution-binding-from-call-materials.md)。
独立账本决策：[ADR-0055](../adr/0055-separate-protected-admission-ledger-from-business-facts.md)；
只追加收紧依据：[ADR-0056](../adr/0056-protect-pending-revocations-with-an-append-only-log.md)。
采集额度与停止依据：[#177 最终裁决](https://github.com/MeteoBoy4/PaperRadar/issues/177#issuecomment-6768256547)、[#178](https://github.com/MeteoBoy4/PaperRadar/issues/178)；补充决策草案：[ADR-0057](../adr/0057-reserve-live-collection-quotas-and-persist-stop-history.md)。
现有产品边界：[Pi 执行](pi-execution.md)、[Read 执行](read-execution.md)。

### 正常认证刷新闭环

`ModelManifestV2` 是独立封印 envelope：`format_version=2`、固定 `normal-auth-refresh-v1` 和批次 A=`boundary-low`、B=`boundary-high`、C=`value-low/value-high/read-low/read-high`。七份单案例／负对照 plan 仍为原 v2 wire，原 manifest v1 的一次六格与通过案例跳过语义保留；不增加计划、操作或重跑已通过格。一次零参数入口只执行下一批，批间返回，不持锁、不留 open round、reservation 或持密进程，不自动定时等待。外部由所有者在共同批准窗口内选择调用时点，不能从未读取的 expiry 猜测固定等待可触发刷新。

正式与 collector 共用 [宿主认证边界](pi-execution.md#宿主认证边界)。认证释放前仍 auth1 原子预占，未知不退款；40/40、失败分类、三次／六轮、安全首停及三检查点不变。`WorkerMessageV2`／`ModelObservationV2` 显式携带 `auth-refresh-metadata` v1；旧 worker／observation 类型和 receipt v1/v2 原格式保持。root 核对固定来源 ID、已核放置进程 pid/start/unit、预占操作、UTC 时序和当前 binding，追加 `inbox/auth-operation-v1-<receiptSHA>.json`，只含固定身份与五个 bool/unknown 事实，不含 credential、token、JWT、秘密摘要或自由错误。源码 ID 对应本包受保护成员与静态 API 源码绑定，产品不能自报任意源码字段。

受保护 `normal-auth-refresh-v1-<firstPlanSHA>.json` 只重放原完成源：A 成功，随后 B 成功且其本次 `need_refresh/refresh_called/refresh_succeeded/store_committed` 全 true，再随后 C 首格成功并有另一更晚真实刷新提交。比较跨格完整站点绑定时只排除各自模型元组，不能把一格模型证据转授另一格。源缺失、提交未知、重复／逆序事件或事件不足均不通过；B 或 C 首格已成功但事件不足时持久 `unknown/stopped`，后续入口只返回原已通过事实，不能继续花额度寻找事件。没有现场来源初值为 `not_assessed`，不预置 passed。C 首格成立后才在同批继续剩余三格，六格资格仍分别接收、激活与判定；本评审不授予准入能力。

`normal-auth-epoch-v1-<firstPlanSHA>.json` 记录首次可信部署完成 UTC、固定 collector 及七 plan IDs；路径名称保留，读取兼容原 format 1 和独立继承 format 2。同 SHA 重跑、卸载／恢复不更改时点。既有安装或执行历史缺该来源时拒绝，不能用 now 补造。部署后72小时是六格目标，评审分开披露目标时点、是否逾期及六格目标结果；不新增准入停止条件，不自动补跑或延长共同授权窗口。原部署 journal／SQLite schema 不变。

已 installed 的升版包须在受封印 `deployment.json.epoch_upgrade` 携带 `EpochUpgrade`：由原 runtime、原 model manifest／首 plan 和原 epoch 原字节派生 SHA、原 UTC、共同窗口、owner 输入和连续身份。`describe_epoch_upgrade` 仅派生候选；安装器在同一 collector 锁内、首次 history／journal／资源写入之前重验旧 runtime、所有 previous／history／archive 祖先、原 epoch、七计划／严格计划窗口、owner 原文及产品／站点／供给／材料身份。只允许启动策略及其派生 collector／plan 身份变化；缺源、冲突或窗口变化拒绝，resources 的无执行史恢复不承担已 installed 升级。

公开 `scripts/seal_live_bundle.py build` 用配对 `--epoch-from-runtime` / `--epoch-source` 只读原 runtime 与原 epoch 原字节，经 `describe_epoch_upgrade` 派生 pair 和 descriptor 后传入构建器。旧 payload/manifest flags 若给出必须与该真实来源相等；仅给旧 pair 而无 epoch 来源在构建阶段拒绝，`derive` 不接受这些升版输入。没有自由 `deployed_at` 参数。该 CLI 新升版路径只处理有原 epoch 的 V2 继承候选；旧 β 入口与无执行史 resources 的专用已审 API 保持独立。候选仍不带 root 信任，安装时重验完整来源。

新计划的 format 2 epoch 将已验证原 UTC 与完整 `inherited_from` 放在单个原子来源中发布；原 epoch 保留原路径和原字节。读取沿有限、无循环谱系逐字核对每代源 SHA、collector、七 plan IDs、UTC 与共同窗口；同字节发布幂等，不同来源／时点拒绝。retiring、archive、runtime、target 中断后每次恢复重新认证相同来源。旧 received、累计额度、失败／stopped、撤销及 intents 只读重放并保留；有 intent cutover 事件而日志缺失时拒绝，不能新 provision。继承时钟不继承资格、认证刷新事件、verified_at 或通过格。[独立部署 metadata Schema](../schemas/live-epoch-upgrade-v1.json) 与 [epoch format 2 Schema](../schemas/normal-auth-epoch-v2.json) 从权威 Pydantic 生成，不加入 receipt v1/v2 的 Frozen Contract。

正常提前刷新符合 [ADR-0063](../adr/0063-observe-normal-oauth-refresh-in-product-process.md) 已决验收语义。`was_expired_by_pi` 只是回调 UTC 时越过 Pi 存储阈值；供应商真实有效期到点始终 `unknown`。stat、调用成功、旧到期时点、另一进程提交、通用 store 的 best-effort 注释都不替代这次固定具体 backend 的事件与成功返回。文件写调用完成不承诺 fsync／断电耐久，认证全写史／writer、完整会话写史和隐藏请求数继续按既有边界披露。
