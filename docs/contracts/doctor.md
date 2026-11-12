# 只读 doctor Contract

## 用途与范围

`paper-radar doctor` 诊断显式范围的基础工程和配置，并提供显式 Pi 执行及 Docling 依赖诊断，保留既有供给诊断。
每个检查项使用四态结论；一次命令可以同时有 `passed`、`missing` 与 `not_assessed`。
输出为中文终端文本，受控 token 便于识别检查范围与原因，不提供 JSON 输出。

## 规则

### 显式选择

| scope | 必填 | 读取与证明 |
| --- | --- | --- |
| `basic` | `--database` | 随包唯一迁移 head 可读；显式库存在、可读且 revision 等于 head。 |
| `config` | `--database`，`--settings` / `--snapshot` 恰好一个 | 包含 basic；以只读 check 或历史 load 检查显式材料，展示六阶段配置 readiness。 |
| `docling-runtime` | `--database`，`--settings` / `--snapshot` 恰好一个 | 包含 basic；显式材料校验后，按所选工具链检查当前平台、顶层发现与精确版本。 |
| `pi-supply` | `--database`、`--snapshot` | 沿用 [Pi 供给诊断](pi-supply.md#原子激活与只读诊断)的完整材料闭包与现场检查、输出字节和退出语义。 |
| `pi-exec` | `--database`、`--snapshot`、`--credentials-dir` | 历史快照、供给现场、cwd/凭据元数据、本机隔离能力与共享执行证据准入；不解析凭据或执行程序。 |

`basic` 不接受 settings/snapshot；`pi-supply/pi-exec` 不接受 settings。
仅 `pi-exec` 接受凭据目录；无 cwd、安装、auth_mode、任意命令或证据导入参数。
快照支持完整 ID 或唯一 8–63 位前缀，沿用[引用解析](config-snapshots.md#引用规则)。
没有默认 scope、隐式最新快照、安装树回退或当前配置回退；选择非法时不展示另一材料的 provider/model。

### 检查项四态与汇总

| 检查项 result | 来源与受控 reason |
| --- | --- |
| `missing` | `database_missing`、`database_uninitialized`、`upgrade_required`；未选择配置 `configuration_unselected`；阶段使用现有 MissingReason（包括 null/unconfigured/placeholder）。 |
| `invalid` | `unknown_revision`、`database_revision_corrupt`、`database_unreadable`、`package_migrations_invalid`；显式选定的 settings/材料不存在或不可读为 `selected_file_unreadable`；YAML/字段非法、字节冲突、契约漂移、快照缺失/损坏为 `content_invalid`。 |
| `passed` | 随包 `head_readable`、库 `current_revision`、选择层 `configuration_valid`、阶段 `configured`。 |
| `not_assessed` | 当前范围没有检查或验收的运行能力，`evidence_not_assessed`；保留承接模块和下一步。该状态不表示发现故障或未来一定失败。 |

基础项复用 `open_database(READ_ONLY)` / `require_current_revision`；不解析中文错误分类。
配置错误保留旧 `ConfigError` 消息，增加 `ConfigReason` 附加类别；嵌套 adapter 读取保留类别。
`paper_radar.config.readiness.configuration_missing(snapshot)` 查询经过验证的快照，合并阶段缺项、
未配置 Profile 和 `model:<slot>`，去重排序，供 config 与旧 pi-supply 共用；不接触现场。

`scope=basic/config result=passed|failed` 是必要检查的汇总，不是检查项四态。
`category=basic` 只汇总基础检查，选择层另列 `check=selection`，因此基础通过与选择非法可同时出现。
config 的必要项为基础检查与选择层；阶段级缺项、basic 中未选择配置以及未验收能力不改变退出码。
必要项全部通过退出 0，否则退出 2。参数用法错误退出 2，不硬套检查项四态。

basic/config 退出 0 固定输出：

> result=passed 仅表示本范围必要检查通过；screening/reuse/read 的 readiness 与未验收能力见下，0 不代表任何阶段可运行。

basic 明示未选配置；config 逐项列出 boundary/value/reuse/extraction/read/suggestion 的结果、
MissingReason 和下一步。Profile 或 Screening 模型未配置时明确提示「Profile/模型未配置，不能校准」。
配置 `ready` 只证明对应配置完整，不证明运行能力、正式校准或自动精读资格。

### Docling 依赖诊断

`scope=docling-runtime result=passed|failed` 的必要项为基础检查、材料选择、extraction
选择、平台与所选清单依赖。missing/invalid 均阻断并退出 2；全部通过退出 0。
未知关键平台事实为 invalid，不能因 marker 跳过或包已安装判为成功。
输出限于基础、选择、平台、依赖与 Docling 未验项；不展示其他阶段 readiness、
Profile 或外发说明。范围成功提示仅说明这些必要检查，不改变 basic/config 的提示。

检查项归属既有 `docling_fixture` 类；模型运行、native ABI、fixture/质量与资源单列为
非必要 not_assessed，整个 fixture 类仍为 not_assessed，不套用 pi-exec 对所有未评项
的失败汇总。范围通过不授予 executable、Read/reuse 或阶段运行资格；basic/config
仍不探测这些现场事实。公共探测结果、受控 reason、中文下一步与消费者责任见
[Docling 运行依赖探测](docling-runtime.md)，本命令不导入 SDK 或执行 parser。

### Pi 执行诊断

诊断只读版本化所有者选择。有效豁免单列“证据前提已由所有者豁免（ADR-0068）”及原因码 `owner_evidence_prerequisite_waived`，不建立能力资格，不改变原证据三态；未评估仍显示 `not_assessed`。缺失选择默认严格，损坏或未知版本拒绝，不自行开启、修复或写入选择。
豁免下不把缺失 root 部署、观察、nft/cgroup/resolver 证明当作产品执行阻断；固定供给、cwd、凭据元数据和 Landlock 能力仍检查。此诊断不刷新认证，不证明 DNS、RPC、模型参数或主机级出站已验。


`scope=pi-exec result=passed|failed executable=true|false` 汇总必要工程项与共享准入结论；
必要工程项或严格模式的必要证据项 missing、invalid 或 not_assessed 时退出 2；有效所有者豁免免除证据前提，其他必要检查仍决定退出码。
披露型 unknown 独立显示，不改变退出码，也不因整体 passed 而成为已验证。
该范围只诊断显式快照的 **Screening 当前档位 boundary/value 两格**，两格均须通过；
输出始终注明 Read 此命令未选择、未诊断，不借用 Screening 证据，也不生成 Read 原状态。
这里的 executable 不替代执行服务领取前的真实四根、外发授权、质量或逐调用复核。

`paper_radar.doctor.pi_exec.execution_checks` 复用基础只读检查、历史快照加载和
`doctor_supply` 的供给/版本/树/保护事实，不安装、不激活、不持执行生命周期保护。
从已验证 snapshot 的 Screening 模型槽、adapter 与当前供给投影 `EvidenceBinding`，
使用执行服务共用的只读 `build_admission_request` 构造完整当次请求，严格模式再调用唯一
`load_admission_evidence` 取得 `AdmissionProjection`。账本、待撤销意图与受保护观察均只读；
严格模式不可读或失信为 invalid/ledger_untrusted，不降级为 not_assessed；豁免模式不请求受保护证据来换取执行许可，原事实不重写。
不创建任务、回执或 StageInput，不调用生产 preflight、prepare_launch、认证刷新或 dry_run。
模型与采样字段仍由[运行配置](runtime-config.md)唯一定义；完整绑定与准入规则见
[Live evidence](live-evidence.md)和[执行组合](pi-execution.md)。

| 检查项 | 四态与边界 |
| --- | --- |
| selection | 历史快照有效为 passed/configuration_valid；缺失/损坏引用保留 ConfigReason，invalid。 |
| supply | 无选择/安装/adapter 为 missing；树、版本或登记不符为 invalid；必要项通过为 passed/supply_valid。 |
| owner_waiver | 独立持久选择；启用为 passed/owner_evidence_prerequisite_waived，关闭为 passed/owner_waiver_disabled；记录损坏为 invalid，不替代隔离检查或能力事实。 |
| admission | 严格模式按两格各自的共享 decision 计算；可执行为 passed/admitted；全部缺证据为 missing/evidence_missing；其他分项或全局拒绝为 invalid，保留 ledger_untrusted、clock_rollback、evidence_expired 等受控原因。豁免时显示 owner_evidence_prerequisite_waived，另列非必要 admission_evidence=not_assessed/evidence_not_assessed；缺 Screening 配置为 missing/screening_configuration_missing；未支持采样、版本、认证模式或用途继续受控拒绝。 |
| cwd | 缺常量目录为 missing/cwd_missing；复用路径形状、无链接、为空规则；非法为 invalid，通过为 passed/cwd_metadata_valid。 |
| credentials_metadata | 缺目录/auth.json 为 missing/credentials_missing；owner、0700、无链接、普通文件检查非法为 invalid/credentials_invalid，否则 passed/metadata_valid。不读取 auth.json 内容。 |
| isolation | 最低内核能力通过为 passed/isolation_capability；不足为 invalid/isolation_unavailable；不证明实际 Pi/TLS/DNS 可行。 |
| credential_roots | 非必要上下文披露 not_assessed/credential_roots_not_assessed；此 CLI 未选择真实业务/配置/材料四根，执行时仍须独立检查。 |
| authentication | 非必要上下文披露 not_assessed/authentication_not_assessed；不解析 token、不验证有效期、不刷新。所需能力资格由共享准入分项独立决定。 |
| model_parameters | 非必要上下文披露 not_assessed/model_parameters_not_assessed；不调用模型或探测额度，参数与账号能力的必需/披露分类只取共享登记。 |

诊断 result 与证据字段采用以下固定映射，不合并枚举：

| 权威分项 | result | evidence | original_state |
| --- | --- | --- | --- |
| 必需且 qualified | passed | verified | 原 verified |
| 必需且无原记录 | missing | unknown | absent |
| 必需且有记录但不合资格 | invalid | unknown | 原 verified/not_assessed/unknown |
| 披露型且 qualified | passed | verified | 原 verified |
| 披露型且不合资格 | passed | unknown | 原 verified/not_assessed/unknown，缺记录为 absent |
| 登记为不适用 | passed，不独立阻断 | unknown | 原状态或 absent，不提升历史状态 |

每行还保留当前 use/call_site、requirement、原依据与范围、未测/未触发原因、evidence_at、原 verified_at、
expires_at/expired、received、evidence_active、revoked、当前 applicability/qualified、来源及下一动作。
全局账本/时钟拒绝保留原原因和水位线，不编造不可读的历史分项。
字符串用 JSON 编码，控制字符不能伪造诊断行。待撤销单列显示；原激活和原 verified
仍可同时存在，但不会据此继续获得资格。健康汇总和空论文报告均保留披露行。
Apport/core 只展示共享投影的当次绑定结论，不另做长期漂移诊断。

`paper_radar.doctor.admission.admission_rows` 提供结构化行；
`render_admission_fragment` 提供供 B/H 嵌入的中文片段，二者消费同一个 AdmissionProjection，
不重判能力或改写原始事实。接口也接受 Read 格的共享投影，但不使本 CLI 自动诊断 Read。
片段不计入每日五项/全文三项论文容量；日报嵌入的后继工作见[路线图](../roadmap.md)。
本接口不实现整套日报或论文筛选排版。
`UsageDisclosure` 保留请求可证下界及观察层/来源/窗口、精确请求数 unknown 与 Pi 自报 token；
隐藏重试、预热、刷新可能不可见，缺失或 totalTokens=0 不代表零成本，不推算供应商独立账单。

### 九类与数据边界

九类沿用规格 §14：基础工程、Feed、Pi adapter、校准、自动精读、全文凭证、Docling fixture、
backup/restore、unattended automation。basic/config 中基础/选择/阶段项由 A 检查，其余能力均为 `not_assessed`；
pi-exec 专门展开 Pi adapter 的检查项；docling-runtime 展开 Docling 安装依赖子项，
两者均不推定其他类别就绪。
Feed 承接 Audit/Source；Pi adapter 承接 Pi/Live；校准承接 D；自动精读承接 D/G；
全文凭证承接 F；Docling 承接 Extra/Body/F；恢复承接 I；无人值守承接 H/I。

config 仅提示另用 `--scope pi-supply` 或 `--scope pi-exec`，不遍历安装树、不查询供给或审计事实、不计算 JGR 判据。
basic/config 不检查 cwd 现场隔离或 Live 分项资格；pi-exec 按当前绑定单列，
不在 doctor 复制 cwd 白名单字面常量。

config 范围的外发说明只取本次验证的显式 settings/snapshot，分别显示 Screening（boundary/value）、reuse、Read
的 provider/model；缺槽显示 null，不补齐。终端字符串使用 JSON 编码，控制字符不成为新诊断行。
实际执行时数据会离开本机：Screening 的 Profile/题名/摘要及 value 启用主题；reuse 的 Profile 与合法结构化来源或正文的 availability/methods/data 摘录；Read 的 Profile、论文元数据与合法正文提取物。
本命令不发送数据，不读取或显示凭据内容、Profile 正文、提示词或模型响应。

## 错误与拒绝

无参数退出 2 并提示 `basic/config/pi-supply/pi-exec/docling-runtime`；未知 scope、`all`、`--json`、config/docling-runtime 选择冲突/缺失、
pi-supply 缺快照或带 settings、pi-exec 缺快照/凭据目录或带 settings、
其他 scope 带凭据目录均退出 2。敏感参数不回显；读取错误只显示受控类别与中文修复入口。
中断退出 130。不可读路径由服务分类，不由参数转换提前降为用法错误。

当前观察诊断只读同一受保护快照与刷新结果，不调用刷新入口或启动守护进程。
`observation_unavailable`／`observation_stale` 显示「观察不可用（临时）」；实际放置不符
显示「放置不符」，`observation_drift` 显示「漂移（已收紧）」并独立披露待撤销标记。
共享中文片段保留原证据三态、verified_at、observed_at、refresh_result、refresh_at 与下一动作；
临时失败不伪报健康，不把失败前的 qualified 结论沿用到本次。

## 不提供／不证明

帮助与所有诊断成功/失败分支均不建库、不迁移、不保存快照、不创建配置/数据/日志/报告目录，
不安装/激活供给、不联网、不执行 Pi/Node/模型/Docling、不消耗预算。
只读 SQLite 允许生成内部 sidecar；只读证据比较逻辑库内容与忽略 sidecar 的文件树。

基础与配置检查不证明来源/JGR 达标、真实 RPC/认证/隔离、正式校准、自动 Read、
Docling fixture/内存、NAS 或无人值守就绪；上述承接见[路线图](../roadmap.md#模块承接索引)。

## 相关

依据：[ADR-0068](../adr/0068-replace-live-prerequisites-with-explicit-owner-waiver.md)；#168、#175、ADR-0052–0055；#144、#140 最终 B/N/C/D；#124、#120 最终 D1–D7；规格 §2.4、§14，ADR-0023、ADR-0026、ADR-0031。

- [运行配置](runtime-config.md)、[历史快照](config-snapshots.md)、[Pi 供给](pi-supply.md)
- [运行日志](runtime-logging.md)、[共享资格／可见性](eligibility-visibility.md)、[组合覆盖台账](../verification/a-narrow-delivery.md)
- [独立 doctor 证据](../verification/doctor-readonly.md)、[独立 T07 映射](../verification/t07-call-isolation.md)
