# Live 分项证据、受保护账本与共享准入判定

## 用途与范围

`paper_radar.live_evidence` 提供带版本的能力登记、普通值领域模型与纯判定函数。
`evaluate_admission` 只消费显式输入，不读墙钟、主机、业务库或账本，不接收或激活证据。
`receipt` 提供 Pydantic 权威回执与批准计划；`EvidenceLedger` 提供受保护接收与只读查询，
`live-evidence receive/show/activate/revoke` 暴露所有者入口。
`service.load_admission_evidence` 对完整请求加载受保护事实并调用同一纯判定，返回结构化投影；
`pi_execution.admission.load_admission_evidence` 延迟转交该完整请求，旧的不完整 EvidenceBinding 仍返回 None。
Screening／Read 正式三检查点与 doctor 消费共享判定，分别见所属 Contract。
`collector`、`sealed_runtime` 与 `deployment` 提供零请求 β 采集、冻结构建与封印脚本；实际 root 权限和证据激活由所有者现场验证。

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
| auth_cache_baseline | 必需 | 站点 | auth_cache_baseline（自接收基线无新增／变化成员） |
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
特权证明的来源与当前有效性由未来账本／检查调用方验证，纯层的集合不是产品授予入口。

当前 now 及可选 ledger_watermark 均显式传入。无时区 now／水位线、当前时间低于水位线时拒绝；
verified 缺原时间、not_assessed／unknown 带 verified_at、无时区或未来验证／观察时点产生受控错误；非法时间输入整体拒绝，不由披露型或不适用分类掩盖。
所有比较转换或等价比较 UTC，保留微秒，不按自然日或接收日取整。

### 绑定分层

`ExecutionBinding` 必须包含全部受控执行组件且每项非空，不接受缺项或重复。
能力按登记依赖精确匹配；组件漂移输出 binding_drift 参数，其他能力的原状态与时间保持。
执行身份包括模型元组中的 provider/model/thinking/sampling/temperature/top_p/protocol_profile/auth_mode；
完整规范身份的可信构造与逐调用主机重采样由后续接线负责。
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

批准计划由 `ApprovedPlan` 定义，保存所有者批准的案例顺序、采集器身份、有效窗口、
认证／模型／网络请求上限、轮数及首失败即停条件。计划通过所有者保护入口独立批准，
不从回执自行批准；同 plan_id 同字节幂等，换字节拒绝。`site_beta` 三类请求上限均为零，
只允许现场能力的 site_probe/current_site verified 主张，不能自造供应商或真实 RPC 观察。
接收检查计划摘要、采集器、案例顺序、计数、轮次、窗口和失败历史一致性；
中途停止须最后案例为失败，失败后不能继续本轮或接受计划后续轮。轮次连续且唯一。
这些计数是回执内部观测值，不证明供应商隐藏请求不存在，不代替业务库的 attempt／配额原子预占。

规范回执为 UTF-8 JSON，键排序、紧凑分隔、结尾换行；输入必须已是该规范字节，
因此重复 JSON 键或不同排版不能成为另一种等价来源。完整 SHA-256 绑定规范字节，
其前 16 hex 为 `receipt_id`，接收幂等与后继激活确认共用。重复 ID 且同完整摘要返回既有记录，
追加 receive_duplicate 审计；前缀碰撞或计划同轮不同回执拒绝。接收不激活、不安装、不认证或调用模型。
回执格式版本与账本 schema 版本各自独立；升级回执格式不代表旧账本可读。

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
账本 schema 当前为 1，与回执 `v1` 分开管理；只接受明确支持的账本版本，
更高版本既不写也不读，兼容升级须由特权维护者另行实现，回执格式升版不推断账本兼容。

`approve_plan`、`approve_plan_source` 与 `receive` 使用保护写事务，成功与重复接收和受控拒绝均追加审计，
事实不被覆盖；账本自身不可信时不补写失败事件。`show`、`show_plan`、`list_received`、`audit` 只读打开，
不创建文件。回执查询重新核对原来源存在、权限与精确字节，以及计划／回执摘要；来源丢失或改变即拒绝。
`connection(writable=False)` 是后继服务复用的受保护连接边界；写连接仍检查特权身份。
账本与受保护回执需单独备份；恢复失效与重新激活规则见 ADR-0055 及下文。
`received_in(connection)` 供共享读取在同一 SQLite 快照中核验来源；只读连接显式开启读取事务。

`paper-radar live-evidence show [--receipt-id <ID>]` 显示回执脱敏摘要，
`show --plan-id <ID>` 只读查询批准计划；两种选择互斥。
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
这个模块仅是供 #172 冻结部署的入口，仓库／venv 中的代码不能作为 sudo 执行来源。

### 当前观察与认证/cache 基线

所有者 activate 固定读取 `/var/lib/paperradar/live-evidence/inbox/current-observation.json`，
由封印采集器产生规范 UTF-8 JSON（同 canonical_bytes 的排序、紧凑分隔与末换行规则）。
内部 `CurrentObservation` 只有 `observed_at`、`binding`、`checked_components`：
前者为有时区的 UTC 时点；binding 完整覆盖全部 BindingComponent，值为 64 hex 摘要；
checked_components 无重复，只列本次确实覆盖的组件，不是 passed／verified 或激活声明。
`load_current_observation` 重新验证来源保护与规范字节，拒绝 naive、未来时点及超过 60 秒的观察。
等于 60 秒仍可读取。所有者手动输入准确短 ID 后，入口调用已部署的固定零参数
`/usr/libexec/paperradar/live-evidence-collect`，清空环境且不传入自由路径或参数；
失败、超时或不可用均拒绝。入口重新读取同一保护来源，要求观察时点不早于本次刷新开始，
完整 binding 与 checked_components 集合和已审核观察相同；新的 observed_at 本身不视为事实漂移。
最后用真实当前时间再次核观察的 60 秒时效，再在保护事务内核同一审核内容并追加激活。
阅读可超过 60 秒；60 秒仅约束执行前的当前观察，不改变能力原 verified_at 或期限。
事实变化、原证据到期、时钟回退或当前覆盖撤回均拒绝，须所有者重新审阅。
普通产品请求不能自行声明特权证明；未观测组件不能填入 checked_components。

`baseline.metadata_digest` 是 #172 接收基线与消费者当次比较共用的 `auth-cache-stat-v1` 算法。
输入为消费方固定顺序的认证／cache 根；只打开目录 fd，stat 成员，不打开或读取成员内容。
清单按根索引和目录内成员名排序，路径为相对名，包含目录与普通单链接文件；
每项记录 dev、ino、mode、uid、gid、nlink、size、mtime_ns、ctime_ns。
规范对象为 format 与 members，UTF-8、键排序、紧凑 JSON、末换行后 SHA-256；绝对路径不进入摘要输入或错误。
最多 4096 项、32 层；软链、特殊节点、读取失败和观察到的并发变化拒绝。
新增／删除／改名／替换／权限或成员元数据变化改变基线摘要；
当前根／祖先属主权限与隔离仍由对应独立检查负责，不由这个摘要推导。

### 当次完整执行绑定

`pi_execution.current_binding.build_admission_request(database, binding, *, use,
credentials_dir, now)` 是执行消费者和诊断共用的只读构造入口。
供给/实例整树经现有只读安装保护复核；当前 manifest、Node/平台、启动/隔离/准入策略、
模型元组、host/boot/kernel/Landlock、cwd/祖先、文件隔离与零 core 策略均逐次绑定。
Apport 绑定公开 dpkg 准确包版本、程序和整个 `/etc/apport` 配置目录、
`/etc/default/apport`、core_pattern 与 suid_dumpable；不运行认证、模型或网络探测。
模型元组沿 ADR-0054；材料正文不进入该身份。显式代理属于启动上下文，改变即改变摘要。
组件普通值经规范紧凑 UTF-8 JSON SHA-256；供给/实例树沿既有 tree-v1，
host/boot 和公开文件按原字节摘要；认证/cache 沿 auth-cache-stat-v1。
专用凭据目录同时是本通道固定的认证/cache 根，固定输入顺序为单元素 `(credentials_dir,)`；
不扫描个人 Pi、环境目录，不读取成员内容。

IPv4 出站和 observer 只由当前固定受保护观察补足覆盖。
只有其完整本地上下文与本次复核一致，才使用该观察声明的覆盖；不匹配时保留当前身份，
舍弃旧特权覆盖，让共享判定拒绝缺口。观察不是能力证据，不提升 unknown。
`recheck_admission_request(request, now=...)` 在领取内只重读同一小型保护来源，
核新鲜度、绑定及特权覆盖未撤回；不重复整树工作。
`local_binding_components` 与 `site_binding_components` 供封印采集侧复用相同摘要规范，
它们本身不授予、不接收、不证据激活。

### 单一加载与投影

`AdmissionRequest(use, binding, checked_components)` 只描述当次身份与观察范围，不接收证据或授予参数。
`service.load_admission_evidence(request, now=...)` 使用固定受保护账本，加载原主张与独立资格维度，
再调用 evaluate_admission；不联网、不认证、不调用 helper、不写任何事实。
返回 `AdmissionProjection(decision, watermark, pending_revocation, sources)`：
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
单纯observation_stale、能力自然到期、未测或未激活只拒绝当前执行，不产生不可逆收紧；
同事实的新鲜观察可恢复适用性，不续原verified_at，不解除真正撤销。
root冻结owner的 `load_owner_admission_evidence` 复用同一日志／账本判定core并核root身份，
安全回执把raw_active与当前active／qualified分开，不绕过pending；产品入口仍只用固定OS来源。
`request_time_tick` 只请求固定 helper 用自身时间打点；失败必须由执行消费者拒绝，不能当作已记录。

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
源代码准入策略为 `pi-admission-v4`；v1/v2/v3 的 D7 向量与摘要锚原字节保留，新策略不继承旧绑定资格。

固定零参数 `/usr/libexec/paperradar/live-evidence-collect` 与仅收紧的 `live-evidence-tighten`
是 sudoers 唯一 NOPASSWD 命令；后者由有限解析器核对 revoke/mark/revoke-use/tick。
`live-evidence-owner` 不在 NOPASSWD 中，接收/批准/激活/恢复等放宽动作均须所有者明确授权。
部署脚本的固定计划批准及 receive 属于该次所有者审阅命令的一部分，不自动激活。
真实安装时，所有者须私下确认产品用户没有等价 root 的组成员资格、能力或任意 sudo 通道。

采集 root 父进程只管理固定受保护输出和冻结代码。现场观察 fork 后清空环境与补充组、不可逆
降到产品 uid/gid 并禁 ptrace，不在降权与观察之间执行用户环境；业务库、整树与认证/cache 元数据
均以产品身份只读复核冻结的snapshot/供给/安装仍为当前选择，再复用 `local_binding_components`、`site_binding_components` 和 `auth-cache-stat-v1`。
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
失败刷新先原子发布mode000观察，普通产品uid无法读取或自行解封；root读取只用于受控诊断，
不把此屏障视为账本撤销已经成功。然后记录受保护待收紧意图，按当前安装INSTANCE摘要，
对所有已接收回执/用途调用既有tighten(components=None)，未知影响保守扩大范围。
原回执字节、主张及verified_at不变。落账失败返回拒绝、保留待收紧意图与不可读观察，不能声称已持久撤销；
后续先重放收紧，全部落账后才移除待办。已停止计划仍不重试探针或恢复观察。
新受信成功计划仅在待收紧工作完成后恢复可读当前观察，不能复活已撤销的旧激活。
未观察组件用带组件名的 unobserved 摘要占位以保持完整绑定，其 checked_components 为空缺，
相应主张始终 unknown；占位不是合成健康值。所有分项都经过既有 receive 规范和 show 回查。
同轮可对六格分别记录全部35能力共210条主张，只复用内容无关的站点测量，不增加认证/模型或探针次数。
CurrentObservation保持当前activation/snapshot的low声明上下文；高档本地消费者重算自身MODEL_TUPLE，
站点能力仅按本能力依赖适用，高档模型/RPC/observer没有verified主张，不表示六格完整可执行。

AUTH_CACHE_BASELINE递归专用credentials全根：auth.json、exp2-installation-id、models-store.json、
node-compile-cache及其成员均无排除，目录与regular文件的dev/ino/mode/uid/gid/nlink/size/mtime/ctime均参与。
宿主认证helper的HOME/TMPDIR为credentials，当前Pi入口启用Node compile cache；RPC子进程的TMPDIR则为attempt临时根。
正常认证cache写入或auth.json刷新同样改变基线，准备后检查拒绝且不领取attempt，不能静默视为安全例外。
更新基线需要新受信计划采集/重新审阅封印字节/人工激活；支持连续运行的缓存布局与允许演进保护留Live后继裁定。

默认 uninstall.sh 移除本包 sudoers、三个入口与冻结 runtime；保留账本、inbox 回执/计划、
失败历史、stopped 标记和 staging。若 cwd 由本部署创建，只在仍为空且受保护时移除；原有 cwd 不动。
同 SHA 可重复卸载/部署恢复，历史与撤销事实不清空；清理账本需要所有者另行显式选择。
中断留下的 runtime.new 不自动删除，须所有者核对后处理，避免覆盖未知部署物。

### 时钟与独立恢复

水位线取所有 events 中接收、批准、重复／拒绝、激活、撤销、mark、tick 与恢复时间的单调最大值。
每笔追加均检查下限，读取也检查显式 now；naive 或倒退时间拒绝且写事务回滚。
原验证时间仍由纯规则与接收窗口检查，最大已记录时间不为其续期。

`EvidenceLifecycle.backup` 仅在受保护位置建立独立 SQLite 快照；inbox 原来源必须另行保存。
`restore` 是受保护历史合并入口：在保护事务内核验快照版本、完整性、两个时间下限、来源与摘要，
不覆盖当前尾部接收／撤销事实，保存原接收排序和历史审计，并追加 evidence_restored 屏障。
全部屏障之前的激活失效，不能导入旧激活来放行；有效且未撤销的证据须重新人工审阅激活。
恢复失败整体回滚。损坏在线账本拒绝自动覆盖、修复或重建，需所有者另行恢复受保护部署。
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

`scripts/issue176_closure.py` 仍可为已经部署并明确新人工激活的v4构建独立包；
它核目标payload／manifest、当前准入策略并内嵌字节，不能拿现场v3执行新工作流或替代首次cutover。
部分／中断状态只保留root检查点，不自动回滚、清理、恢复资格或重新初始化日志。
具体流程与尚未执行边界见[owner方案](../../intent/review/issue-168/closure-owner-plan.md)及
[收口台账](../verification/issue-168-176-live-admission-closure.md)。

## 错误与拒绝

`AdmissionReason` 使用闭合 ReasonCode，能力参数为 Capability，组件参数为 BindingComponent；
`capability_required:<能力>` 与 `binding_drift:<组件>` 的 token 由受控参数生成，不接收自由字符串。
其他原因包括 evidence_missing、evidence_not_received、evidence_not_activated、evidence_revoked、
evidence_expired、evidence_not_applicable、evidence_applicability_unknown、registry_version_mismatch、
admission_use_undefined、evidence_scope_mismatch、evidence_conflict、material_mismatch、coverage_incomplete、
evidence_time_invalid、evidence_time_future、clock_rollback、ledger_untrusted。
账本以 `LedgerError.category` 报告 ledger_untrusted、ledger_schema_unsupported、protected_entry_required、
source_untrusted、source_integrity、receipt_invalid、plan_missing／conflict／mismatch／round_conflict／stopped、
receipt_conflict／missing、activation_empty、activation_confirmation_mismatch、
observation_invalid／stale／changed、binding_observation_unavailable、pending_revocation_unavailable 等受控原因，错误不包含输入或敏感路径。来源与版本失信的 `reason` 映射为 ledger_untrusted；
纯层不认证账本。CLI 失败返回 2，提示所有者检查受保护部署、计划与来源。
该词表与现有闭合 ExecutionReason 分开，任务结算映射由消费者接线维护，不改写旧 token。

## 不提供／不证明

不提供模型 collector、项目 unit/CG/nft/observer 产品化、特权持续观察或产品部署；这些由 Live 承接。
真实 OS 特权证明与所有者激活不由离线构建提供；消费闭包与当前待验边界见[收口台账](../verification/issue-168-176-live-admission-closure.md)。旧不完整调用不能自动升级成完整请求。
接收权威只核来源、完整性与内部一致性，不能独立证明没有遗漏的失败；失败历史完备性由采集器与 sudoers 边界承担。
离线构建与合成覆盖不证明真实 root、供应商或模型行为，不替代所有者激活、真实材料外发确认、根用途或校准资格。
威胁模型防范同 uid 产品进程、测试、Agent 工具伪造或篡改受保护证据及激活记录和配置 passed 自证；
纯层本身没有写入或授予路径，接收／计划批准也不产生激活资格。不防范同 uid 直接修改源码，该边界由代码审阅与策略版本守卫承担。
真实 OS 信任根与抗回滚保证不由这些普通值或离线测试建立。

## 相关

采集与部署依据：[#172](https://github.com/MeteoBoy4/PaperRadar/issues/172)；独立覆盖见 [β 采集台账](../verification/issue-168-172-site-collector.md)。
依据：[父票裁决](https://github.com/MeteoBoy4/PaperRadar/issues/168#issuecomment-6722370306)、[#169](https://github.com/MeteoBoy4/PaperRadar/issues/169)、[ADR-0051](../adr/0051-separate-live-binding-capabilities-and-activation.md)。
补充决策：[ADR-0052](../adr/0052-version-admission-uses-and-capability-requirements.md)、[ADR-0053](../adr/0053-expire-capabilities-by-evidence-class-and-coverage.md)、[ADR-0054](../adr/0054-separate-execution-binding-from-call-materials.md)。
独立账本决策：[ADR-0055](../adr/0055-separate-protected-admission-ledger-from-business-facts.md)；
只追加收紧依据：[ADR-0056](../adr/0056-protect-pending-revocations-with-an-append-only-log.md)。
现有产品边界：[Pi 执行](pi-execution.md)、[Read 执行](read-execution.md)。
