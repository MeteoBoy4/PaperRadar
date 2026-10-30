# Pi RPC 适配器配置

权威 Pydantic 类型为 [`PiAdapter`、`PiPolicy`、`PiSystemPrompt`](../../src/paper_radar/config/adapters.py)。
本契约定义 settings 的三槽 adapter 选择、Pi 材料、声明系统指令与只读语义身份。
公共 `paper_radar.config.check_config(settings_path, database)`、
`compile_config(settings_path, database)`、`load_config_snapshot(database, snapshot_id)`
均返回 `RuntimeConfigSnapshot`；必须使用既有且已迁移到当前 revision 的数据库。
公共服务、CLI 参数、数据库前置与恢复规则由[运行配置契约](runtime-config.md)定义。
工程合成示例为 [`examples/config/settings-pi.yaml`](../../examples/config/settings-pi.yaml)，
不代表真实 Profile、模型或执行就绪。

## 选择、材料与版本

settings 接受可省略的 `adapters` 映射，三个槽 `screening/reuse_assessment/reading`
各为声明版本或 `null`，省略与 `null` 同为未配置。整个映射不能为 `null`。
每槽独立选择，可以共享材料；文件存在不意味着默认选择。

```yaml
adapters:
  screening: pi-v1
  reuse_assessment: pi-v1
  reading: pi-read-v2
```

selector 精确选择 settings 相邻的 `adapters/<version>.yaml`，文件内 `version`
必须相同，声明版本格式见[运行配置契约](runtime-config.md#输入与路径)。中性材料种类为 `ADAPTER`（`adapter`），
V1 封闭逻辑名为 `pi-rpc`，登记键为 `(adapter, pi-rpc, declared_version)`。
不定义通用 harness、插件或自由资源注册表。

V1 唯一显式资源为登记的声明系统指令，复用 `PROMPT` 登记机制，封闭逻辑名
`pi-system`，与 `boundary/value/reuse/reading` 分开，即使同为 `v1` 也不共用登记键。
版本来自资源引用，正文无需内嵌声明；位置为 settings 相邻的
`prompts/pi-system-<version>.md`。系统指令与业务 Prompt 分开选择和登记；
业务 Prompt 的路径、selector 与契约选择见[运行配置契约](runtime-config.md#输入与路径)。

```yaml
version: pi-v1
backend: pi-rpc
pi_version: 1.1.0
adapter_version: transport-v1
thinking_level: low
policy:
  version: bounded-rpc-v1
resources:
  - kind: system_prompt
    name: pi-system
    version: v1
    sha256: 8b0188e425cc6a77059940a6a5c371f39f8eb28346ef504c5a3ec6b247747c25
```

上例对应 [`examples/config/adapters/pi-v1.yaml`](../../examples/config/adapters/pi-v1.yaml)
与[合成 Prompt](../../examples/config/prompts/pi-system-v1.md)；`1.1.0` 是审计示例，
不选择实际安装版本，也不证明已核对 Pi 的有效输入。

配置登记接受严格三段正式版本，不以当前离线协议档案限制登记范围。
调用描述目前只支持 boundary/value 和 `1.4.0`；其双快照前置、未登记版本的领取前拒绝
及不占预算保证由 [RPC Contract](pi-rpc.md#调用描述与只读准备)定义。
`bounded-rpc-v1` 对应的 `render_format=1` 及语义渲染版本约束见
[RPC 渲染规则](pi-rpc.md#bounded-rpc-v1-的首次渲染)。

## 字段、默认值与固定策略

严格校验所有对象，拒绝未知字段。以下字段均不接受 `null`。

| 字段 | 必填性、默认值与约束 |
| --- | --- |
| `version` | 必填普通声明版本，与 selector 相同。 |
| `backend` | 可省略，固定 `pi-rpc`。 |
| `pi_version` | 必填精确三段非负整数版本；禁止前导零、范围、latest、路径或命令。不探测本机安装。 |
| `adapter_version` | 必填执行审计版本，沿用声明版本格式；标识纯 RPC 传输实现，不替代行为策略版本。 |
| `thinking_level` | 必填受控文本 `off/minimal/low/medium/high/xhigh/max`；不继承个人默认值。 |
| `policy` | 可省略，展开下表的全部固定 V1 值；禁止放宽。 |
| `resources` | 必填单元素列表；只接受系统 Prompt，不接受空清单、多资源、extension、skill、MCP 或路径。 |
| `resources[0].kind/name` | 可省略，固定 `system_prompt` / `pi-system`。 |
| `resources[0].version` | 必填声明版本，指向 UTF-8 Prompt。 |
| `resources[0].sha256` | 必填 64 位小写 SHA-256，核对精确 Prompt 字节。 |

推理档位是配置词汇，不证明所选 Pi/provider/model 实际支持该档位。
本边界不探测上游 clamp、采样参数映射或个人设置，不能将登记成功解释为它们已受控。

| policy 字段 | 唯一支持的 V1 值 |
| --- | --- |
| `version` | `bounded-rpc-v1`，代码受控的策略语义身份。 |
| `session` | `ephemeral_per_attempt`。 |
| `agent_retry/provider_retry` | `disabled`。 |
| `compaction/summarization` | `disabled`。 |
| `session_persistence/resource_discovery` | `disabled`；禁止个人/项目 context、skills、prompts、extensions 等隐式资源。 |
| `extra_model_turns/mcp` | `disabled`。 |
| `tools` | 空列表 `[]`。 |

这些值是登记的固定策略，不是会话隔离、禁用隐含调用或 OS 权限约束已生效的证明。
可观察的协议接收边界见 [RPC Contract](pi-rpc.md#固定协议与生命周期)。

权威输出通道由 models 的 `prompt_only` 唯一指定，不在 adapter 重复定义协议。
已选 adapter 对应模型槽的非空 protocol 只能为 `prompt_only`；槽或 protocol
尚未配置也可保存不完整快照。明确选择 json_schema/json_object 时整次检查/编译
拒绝，未选 adapter 的既有协议仍合法且可回放。provider/model/temperature/top_p
仍由 models 唯一决定。最多两次 Python attempt 不开放为参数；timeout、内存、
凭据/引用、任意 CLI 参数和命令均未定义。

## 错误与拒绝

沿用[严格 YAML 与错误规则](runtime-config.md#模型提示词与契约)：仅接受 UTF-8 单文档映射；
重复键、锚点/别名、合并键、自定义 tag、非有限浮点数、错误类型与未知字段均拒绝。
selector 与文件内声明版本不一致、材料缺失/不可读、Prompt 非 UTF-8、资源哈希不符、
固定策略被放宽、资源数量或种类不符及 models 协议冲突也使整次 check/compile 失败。
错误为脱敏 `ConfigError`；CLI 返回 2，只给字段路径与受控原因及处理指引，
不回显值、Prompt、原始异常或可执行命令。
同声明键不同字节、数据库缺失/未迁移、锁等待失败和历史损坏的错误及恢复方式见
[运行配置契约](runtime-config.md#并发失败与恢复)，不会覆盖登记或回退当前文件。

## 登记、回放与完整性

沿用包络 `format_version: 1` 与 `config_versions`、`runtime_config_snapshots`、
`snapshot_version_refs` 三表。仅在非空 adapter 选择
时增加 `selectors.adapters`；无选择的旧快照保持原 JSON、身份和含义，不合成
默认 Pi 材料。check 只读，compile 原子登记原始 YAML、Prompt 精确字节、哈希、
编译值、快照和引用。同键同字节幂等，同键任何字节变化（含注释）拒绝。失败
整体回滚。load 只读 SQLite，核对选择、哈希、资源依赖及载荷，不回退到当前文件。

公共 `RuntimeConfigSnapshot.adapters` 为三个槽到 `AdapterSemantics | None` 的只读映射。
`adapter_selections` 为已选槽到声明版本的只读映射，不含未选槽；
`adapter_slots` 分别返回 `unconfigured/configured/placeholder`；合法材料的 Prompt
strip 后为空或精确为 `...` 时为 placeholder，仍可保存明确不完整的快照。
模型槽和既有业务阶段完整性独立报告；没有 adapter 的业务配置完整性不证明
Pi 就绪，已配置 adapter 也不证明执行就绪。Read 另须显式选择 `contracts.read: v1`
并配齐业务材料；就绪规则见[运行配置契约](runtime-config.md#当前就绪范围)。
已选择但 Prompt 占位的 adapter 使实际消费者阶段未就绪；受控缺项分别为
`screening_adapter_prompt_placeholder`（boundary/value）、
`reuse_adapter_prompt_placeholder`（reuse）、`read_adapter_prompt_placeholder`（Read）。
未选择 adapter 时保持旧业务配置完整性含义，不合成默认策略。

## 语义与消费者依赖

每槽的不可变 `AdapterSemantics` 暴露 `backend`、`thinking_level`、展开默认值后的
`policy`、`system_prompt_text`、`system_prompt_sha256`、`payload_json` 和 `semantics_id`。
系统 Prompt 是登记的声明文本，不包含 Pi 强制追加的 cwd 段，不冒充完整有效系统指令。
文本与语义载荷不进入 repr，但公共属性仍含原文，不应写终端或日志。载荷包含
`kind: adapter_semantics` 和独立格式版本 **1**，规范序列化沿用配置身份规则。
保留实际文本空白、资源逻辑名和策略语义版本，排除普通声明版本、YAML 原始哈希、
Pi/adapter 执行审计版本、机器路径、时间和临时身份。`semantics_id` 是完整规范载荷
UTF-8 字节的 SHA-256。完整材料仍保存审计版本。
同一 adapter 语义格式固定载荷字段与编码；改变这些规则须显式演进该独立格式，
不能只更换传输审计版本。分量身份变化经 `semantics_id` 传导到实际消费者，
不因此一律提升其他投影格式。这是统一阶段投影的 adapter 分量，不是完整阶段投影、阶段指纹或校准基线。

| 槽 | adapter_dependencies | calibration_adapter_slots |
| --- | --- | --- |
| screening | boundary、value | 包含 |
| reuse_assessment | reuse | 包含 |
| reading | read | 排除 |

共有资源按实际消费者传播，纯 Read 变化不影响其他 adapter 分量。普通声明改名
或仅改注释只改变完整登记/快照身份；声明系统指令或推理档位变化改变对应分量。
单快照重建与 diff 按上述消费者引用 `AdapterSemantics.semantics_id`，见
[阶段配置投影与比较](config-projections.md)；此处不重复定义投影与基线载荷。
共享材料只切换一槽时不改变其他槽的投影；仅变 Pi/adapter 执行审计版本不改变任何投影或基线。

改动 `pi_version` 或 `adapter_version` 同样受不可变登记约束：必须新建适配器声明版本，
通过 selector 显式选用，不能以“纯审计变化”为由覆盖已登记字节。
锁定版本、相同语义 ID 或完整供给树哈希都不构成兼容性证明；无法判断行为影响时不能宣称
校准兼容。升级及语义身份更新纪律见[规格 §7.8](../../intent/draft.md#78-pi-固定版本供给)。

## 不提供／不证明

- 本边界不安装 Pi/Node、不执行 RPC、不检查凭据或 provider 参数能力、不启用流水线。
  固定供给由 [Pi 供给契约](pi-supply.md)定义；生产启动器与参数映射由
  [Pi](../roadmap.md#module-pi)、实际安装/RPC 验证由 [Live](../roadmap.md#module-live)承接。
- 配置只保存声明系统指令与固定策略，不证明实际有效指令、资源隔离或 OS 权限已受控。
  Pi 1.4.0 的有效指令另含强制追加的 cwd 段，本配置不选择或核验它。
  `/srv/pi-cwd` 的显式提供、唯一白名单及首次 prompt 前现场隔离门槛见
  [规格准入要求](../../intent/draft.md#pi-生产启动器准入)；离线协议档案不能代替现场隔离。
  现场验证由[Cwd](../roadmap.md#module-cwd)与 [Live](../roadmap.md#module-live)承接。
- 配置就绪、离线协议版本准入和语义比较不授予生产 `rpc_compatibility`、模型执行或
  自动精读资格。配置与比较不产生 `minor/major`、`enable` 或 calibration evaluation 事件；
  校准审计与门禁由 [D](../roadmap.md#module-d)承接。

## 相关

依据：[#26](https://github.com/MeteoBoy4/PaperRadar/issues/26)、[#85](https://github.com/MeteoBoy4/PaperRadar/issues/85)、[#111](https://github.com/MeteoBoy4/PaperRadar/issues/111)。

[规格 §7.7](../../intent/draft.md#77-pi-rpc-适配边界)；
[ADR-0026](../adr/0026-control-pi-through-a-bounded-rpc-adapter.md)；
[ADR-0023](../adr/0023-separate-runtime-config-snapshots-from-calibration-baselines.md)；
[运行配置](runtime-config.md)；[配置投影](config-projections.md)；[RPC](pi-rpc.md)；
[路线图承接](../roadmap.md#module-pi)。
