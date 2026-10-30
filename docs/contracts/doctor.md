# 只读 doctor Contract

## 用途与范围

`paper-radar doctor` 诊断显式范围的基础工程和配置，并保留既有供给诊断。
每个检查项使用四态结论；一次命令可以同时有 `passed`、`missing` 与 `not_assessed`。
输出为中文终端文本，受控 token 便于识别检查范围与原因，不提供 JSON 输出。

## 规则

### 显式选择

| scope | 必填 | 读取与证明 |
| --- | --- | --- |
| `basic` | `--database` | 随包唯一迁移 head 可读；显式库存在、可读且 revision 等于 head。 |
| `config` | `--database`，`--settings` / `--snapshot` 恰好一个 | 包含 basic；以只读 check 或历史 load 检查显式材料，展示六阶段配置 readiness。 |
| `pi-supply` | `--database`、`--snapshot` | 沿用 [Pi 供给诊断](pi-supply.md#原子激活与只读诊断)的完整材料闭包与现场检查、输出字节和退出语义。 |

`basic` 不接受 settings/snapshot；`pi-supply` 不接受 settings。
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

新范围退出 0 固定输出：

> result=passed 仅表示本范围必要检查通过；screening/reuse/read 的 readiness 与未验收能力见下，0 不代表任何阶段可运行。

basic 明示未选配置；config 逐项列出 boundary/value/reuse/extraction/read/suggestion 的结果、
MissingReason 和下一步。Profile 或 Screening 模型未配置时明确提示「Profile/模型未配置，不能校准」。
配置 `ready` 只证明对应配置完整，不证明运行能力、正式校准或自动精读资格。

### 九类与数据边界

九类沿用规格 §14：基础工程、Feed、Pi adapter、校准、自动精读、全文凭证、Docling fixture、
backup/restore、unattended automation。基础/选择/阶段项由 A 检查；其余能力均为 `not_assessed`。
Feed 承接 Audit/Source；Pi adapter 承接 Pi/Cwd/Live；校准承接 D；自动精读承接 D/G；
全文凭证承接 F；Docling 承接 Extra/Body/F；恢复承接 I；无人值守承接 H/I。

config 仅提示另用 `--scope pi-supply`，不遍历安装树、不查询供给或审计事实、不计算 JGR 判据。
启动器与 cwd 现场隔离单列未验，不在 doctor 复制 cwd 白名单字面常量。

外发说明只取本次验证的显式 settings/snapshot，分别显示 Screening（boundary/value）、reuse、Read
的 provider/model；缺槽显示 null，不补齐。终端字符串使用 JSON 编码，控制字符不成为新诊断行。
实际执行时数据会离开本机：Screening 的 Profile/题名/摘要及 value 启用主题；reuse 的 Profile 与合法结构化来源或正文的 availability/methods/data 摘录；Read 的 Profile、论文元数据与合法正文提取物。
本命令不发送数据，不读取或显示凭据、Profile 正文、提示词或模型响应。

## 错误与拒绝

无参数退出 2 并提示 `basic/config/pi-supply`；未知 scope、`all`、`--json`、config 选择冲突/缺失、
pi-supply 缺快照或带 settings 均退出 2。敏感参数不回显；读取错误只显示受控类别与中文修复入口。
中断退出 130。不可读路径由服务分类，不由参数转换提前降为用法错误。

## 不提供／不证明

帮助与所有诊断成功/失败分支均不建库、不迁移、不保存快照、不创建配置/数据/日志/报告目录，
不安装/激活供给、不联网、不执行 Pi/Node/模型/Docling、不消耗预算。
只读 SQLite 允许生成内部 sidecar；只读证据比较逻辑库内容与忽略 sidecar 的文件树。

基础与配置检查不证明来源/JGR 达标、真实 RPC/认证/隔离、正式校准、自动 Read、
Docling fixture/内存、NAS 或无人值守就绪；上述承接见[路线图](../roadmap.md#模块承接索引)。

## 相关

依据：#124、#120 最终 D1–D7；规格 §2.4、§14，ADR-0023、ADR-0026、ADR-0031。

- [运行配置](runtime-config.md)、[历史快照](config-snapshots.md)、[Pi 供给](pi-supply.md)
- [运行日志](runtime-logging.md)、[共享资格／可见性](eligibility-visibility.md)、[组合覆盖台账](../verification/a-narrow-delivery.md)
- [独立 doctor 证据](../verification/doctor-readonly.md)、[独立 T07 映射](../verification/t07-call-isolation.md)
