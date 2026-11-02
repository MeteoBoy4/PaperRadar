# 只读 doctor Contract

## 用途与范围

`paper-radar doctor` 诊断显式范围的基础工程和配置，并提供显式 Pi 执行诊断，保留既有供给诊断。
每个检查项使用四态结论；一次命令可以同时有 `passed`、`missing` 与 `not_assessed`。
输出为中文终端文本，受控 token 便于识别检查范围与原因，不提供 JSON 输出。

## 规则

### 显式选择

| scope | 必填 | 读取与证明 |
| --- | --- | --- |
| `basic` | `--database` | 随包唯一迁移 head 可读；显式库存在、可读且 revision 等于 head。 |
| `config` | `--database`，`--settings` / `--snapshot` 恰好一个 | 包含 basic；以只读 check 或历史 load 检查显式材料，展示六阶段配置 readiness。 |
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

### Pi 执行诊断

`scope=pi-exec result=failed executable=false` 汇总所有必要项；任何必要项
missing、invalid 或 not_assessed 都退出 2。它不采用 config 对阶段缺项的宽松汇总。
当前产品没有 Cwd/Live 证据来源，且认证/计划能力有意不观测，因此始终不可执行。
单项 passed 只证明那项离线检查通过，不能推出真实兼容、认证或可运行。

`paper_radar.doctor.pi_exec.execution_checks` 先复用基础只读检查和历史快照加载，
再复用 `doctor_supply` 的供给/版本/树/保护事实，不安装、不激活、不持执行生命周期保护。
从已验证 snapshot 的 Screening 模型槽、adapter 和当前供给构造普通
`EvidenceBinding`，复用纯 `admit` 判定且当前证据固定缺失；
产品没有证据读取来源，doctor 不接收执行服务测试私有的正例注入；不创建任务、回执或
StageInput，不调用生产 preflight、prepare_launch 或 dry_run。
模型与采样字段仍由[运行配置](runtime-config.md)唯一定义，绑定与执行判定见[执行组合](pi-execution.md)。

| 检查项 | 四态与边界 |
| --- | --- |
| selection | 历史快照有效为 passed/configuration_valid；缺失/损坏引用保留 ConfigReason，invalid。 |
| supply | 无选择/安装/adapter 为 missing；树、版本或登记不符为 invalid；供给必要项通过为 passed/supply_valid。 |
| admission | 缺 Screening 配置为 missing/screening_configuration_missing；缺当前准入证据为 missing/evidence_missing；未支持采样、版本或认证模式为 invalid，复用执行受控原因。当前始终非 passed，没有 admitted token。screening_configuration_missing 属于本诊断项的公共词汇，不属于 ExecutionReason。 |
| cwd | 缺常量目录为 missing/cwd_missing；复用执行路径形状/无链接/为空规则，非法为 invalid，满足为 passed/cwd_metadata_valid。祖先现场资源仍交 Cwd。 |
| credentials_metadata | 缺目录/auth.json 为 missing/credentials_missing；复用 owner、0700、无链接、普通文件检查，非法为 invalid/credentials_invalid，否则 passed/metadata_valid。不读取 auth.json。 |
| isolation | 内核能力满足为 passed/isolation_capability；不足为 invalid/isolation_unavailable；不证明实际 Pi/TLS/DNS 运行可行。 |
| credential_roots | not_assessed/credential_roots_not_assessed；该 CLI 没有执行服务的显式四根，不猜测路径或把元数据通过冒称根隔离通过。执行时仍检查真实四根。 |
| authentication | not_assessed/authentication_not_assessed；不检查 token 内容、前缀或有效期，不刷新。 |
| model_parameters | not_assessed/model_parameters_not_assessed；不探测计划模型权限、订阅额度或参数能力。 |

下一步与事实配对：cwd、祖先资源和现场隔离交 Cwd；RPC/DERIVED、订阅刷新、token
通道/前缀启发式、计划模型权限与额度、参数映射、TLS/DNS 和主机级出站交 Live。
供给元数据、历史成功或旧诊断都不能替代当前准入，执行仍须独立复核并持保护。

### 九类与数据边界

九类沿用规格 §14：基础工程、Feed、Pi adapter、校准、自动精读、全文凭证、Docling fixture、
backup/restore、unattended automation。basic/config 中基础/选择/阶段项由 A 检查，其余能力均为 `not_assessed`；
pi-exec 专门展开 Pi adapter 的检查项，不推定其他类别就绪。
Feed 承接 Audit/Source；Pi adapter 承接 Pi/Cwd/Live；校准承接 D；自动精读承接 D/G；
全文凭证承接 F；Docling 承接 Extra/Body/F；恢复承接 I；无人值守承接 H/I。

config 仅提示另用 `--scope pi-supply` 或 `--scope pi-exec`，不遍历安装树、不查询供给或审计事实、不计算 JGR 判据。
受控执行资源已提供，cwd 现场隔离与 Cwd/Live 准入单列未验，不在 doctor 复制 cwd 白名单字面常量。

外发说明只取本次验证的显式 settings/snapshot，分别显示 Screening（boundary/value）、reuse、Read
的 provider/model；缺槽显示 null，不补齐。终端字符串使用 JSON 编码，控制字符不成为新诊断行。
实际执行时数据会离开本机：Screening 的 Profile/题名/摘要及 value 启用主题；reuse 的 Profile 与合法结构化来源或正文的 availability/methods/data 摘录；Read 的 Profile、论文元数据与合法正文提取物。
本命令不发送数据，不读取或显示凭据内容、Profile 正文、提示词或模型响应。

## 错误与拒绝

无参数退出 2 并提示 `basic/config/pi-supply/pi-exec`；未知 scope、`all`、`--json`、config 选择冲突/缺失、
pi-supply 缺快照或带 settings、pi-exec 缺快照/凭据目录或带 settings、
其他 scope 带凭据目录均退出 2。敏感参数不回显；读取错误只显示受控类别与中文修复入口。
中断退出 130。不可读路径由服务分类，不由参数转换提前降为用法错误。

## 不提供／不证明

帮助与所有诊断成功/失败分支均不建库、不迁移、不保存快照、不创建配置/数据/日志/报告目录，
不安装/激活供给、不联网、不执行 Pi/Node/模型/Docling、不消耗预算。
只读 SQLite 允许生成内部 sidecar；只读证据比较逻辑库内容与忽略 sidecar 的文件树。

基础与配置检查不证明来源/JGR 达标、真实 RPC/认证/隔离、正式校准、自动 Read、
Docling fixture/内存、NAS 或无人值守就绪；上述承接见[路线图](../roadmap.md#模块承接索引)。

## 相关

依据：#144、#140 最终 B/N/C/D；#124、#120 最终 D1–D7；规格 §2.4、§14，ADR-0023、ADR-0026、ADR-0031。

- [运行配置](runtime-config.md)、[历史快照](config-snapshots.md)、[Pi 供给](pi-supply.md)
- [运行日志](runtime-logging.md)、[共享资格／可见性](eligibility-visibility.md)、[组合覆盖台账](../verification/a-narrow-delivery.md)
- [独立 doctor 证据](../verification/doctor-readonly.md)、[独立 T07 映射](../verification/t07-call-isolation.md)
