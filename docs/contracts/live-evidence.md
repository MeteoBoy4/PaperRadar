# Live 分项证据与纯准入判定

## 用途与范围

`paper_radar.live_evidence` 提供带版本的能力登记、普通值领域模型与纯判定函数。
`evaluate_admission` 只消费显式输入，不读墙钟、主机、业务库或账本，不接收或激活证据。
产品 `load_admission_evidence` 仍返回 None；Screening／Read 的现有缺证据拒绝保持。

## 规则

### 准入用途与独立维度

初始登记版本为 `live-admission-v1`，包含以下六格，均显式分类全部能力：

| 调用点 | 消费者格 | 档位 |
| --- | --- | --- |
| `PiExecution.run_attempt` | boundary、value | 各 low、high |
| `read_execution` | read | low、high |

准入用途不包含或推导根用途。未定义用途被拒绝；登记拒绝空必需集合、重复用途、重复能力、缺少能力分类与必需项空依赖。
版本经引用后冻结，版本变更须创建新版本；旧版本的证据激活不满足新版本。
每个能力 × 准入用途只能输入一条事实；重复输入不论顺序或状态均拒绝，真实历史的唯一事实由后续账本读取权威选择。
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

## 错误与拒绝

`AdmissionReason` 使用闭合 ReasonCode，能力参数为 Capability，组件参数为 BindingComponent；
`capability_required:<能力>` 与 `binding_drift:<组件>` 的 token 由受控参数生成，不接收自由字符串。
其他原因包括 evidence_missing、evidence_not_received、evidence_not_activated、evidence_revoked、
evidence_expired、evidence_not_applicable、evidence_applicability_unknown、registry_version_mismatch、
admission_use_undefined、evidence_scope_mismatch、evidence_conflict、material_mismatch、coverage_incomplete、
evidence_time_invalid、evidence_time_future、clock_rollback、ledger_untrusted。
ledger_untrusted 在词表中预留给真实账本读取；纯层不认证账本。
该词表与现有闭合 ExecutionReason 分开，任务结算映射由消费者接线维护，不改写旧 token。

## 不提供／不证明

不提供受信回执、计划预算实体、接收／证据激活／撤销账本、特权证明验证、站点采集、CLI 或 doctor／日报接线。
这些责任由 [Live 前置任务](https://github.com/MeteoBoy4/PaperRadar/issues/168) 的 #170–#175 承接，消费闭包由 #176 收口。
不提供真实 root、供应商或模型实测，不替代所有者激活、真实材料外发确认、根用途或校准资格。
威胁模型防范同 uid 产品进程、测试、Agent 工具伪造或篡改受保护证据及激活记录和配置 passed 自证；
纯层本身没有写入或授予路径。不防范同 uid 直接修改源码，该边界由代码审阅与策略版本守卫承担。
真实 OS 信任根与抗回滚保证不由这些普通值或离线测试建立。

## 相关

依据：[父票裁决](https://github.com/MeteoBoy4/PaperRadar/issues/168#issuecomment-6722370306)、[#169](https://github.com/MeteoBoy4/PaperRadar/issues/169)、[ADR-0051](../adr/0051-separate-live-binding-capabilities-and-activation.md)。
提议补充：[ADR-0052](../adr/0052-version-admission-uses-and-capability-requirements.md)、[ADR-0053](../adr/0053-expire-capabilities-by-evidence-class-and-coverage.md)、[ADR-0054](../adr/0054-separate-execution-binding-from-call-materials.md)，均待所有者接受，后继实施保持 G1 闸门。
现有产品边界：[Pi 执行](pi-execution.md)、[Read 执行](read-execution.md)。
