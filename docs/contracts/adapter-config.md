# Pi RPC 适配器配置

权威 Pydantic 类型为 `config/adapters.py`，沿用公共 check/compile/load 服务。
本票只登记配置事实，不安装 Pi/Node、不执行 RPC、不检查凭据或 provider 参数
能力、不启用流水线。工程合成示例为 `examples/config/settings-pi.yaml`。

## 选择、材料与版本

settings 新增可省略的 `adapters` 映射，三个槽 `screening/reuse_assessment/reading`
各为声明版本或 `null`，省略与 `null` 同为未配置。整个映射不能为 `null`。
每槽独立选择，可以共享材料；文件存在不意味着默认选择。

```yaml
adapters:
  screening: pi-v1
  reuse_assessment: pi-v1
  reading: pi-read-v2
```

selector 精确选择 settings 相邻的 `adapters/<version>.yaml`，文件内 `version`
必须相同，版本格式沿用运行配置契约。中性材料种类为 `ADAPTER`（`adapter`），
V1 封闭逻辑名为 `pi-rpc`，登记键为 `(adapter, pi-rpc, declared_version)`。
不定义通用 harness、插件或自由资源注册表。

V1 唯一显式资源为完整有效系统指令，复用 `PROMPT` 登记机制，封闭逻辑名
`pi-system`，与 `boundary/value/reuse/reading` 分开，即使同为 `v1` 也不共用登记键。
版本来自资源引用，正文无需内嵌声明；位置为 settings 相邻的
`prompts/pi-system-<version>.md`。Screening 业务 Prompt 在配置根的
`prompts/screening/<name>-<version>.md`，Read 业务 Prompt 在
`prompts/reading/<version>.md`，由 `settings.prompts.reading` 选择。

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

上例对应 examples 中的 adapter 与合成 Prompt；`1.1.0` 是审计示例，不选择实际
安装版本，也不证明已核对 Pi 的有效输入。

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

推理档位词汇参照 [Pi 官方 CLI](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/cli.md#models)。
执行器仍须核对实际能力与有效值，不能静默接受上游 clamp、忽略采样参数或使用个人设置。

| policy 字段 | 唯一支持的 V1 值 |
| --- | --- |
| `version` | `bounded-rpc-v1`，代码受控的策略语义身份。 |
| `session` | `ephemeral_per_attempt`；每阶段/attempt 和 Read map/reduce 各自临时隔离。 |
| `agent_retry/provider_retry` | `disabled`。 |
| `compaction/summarization` | `disabled`。 |
| `session_persistence/resource_discovery` | `disabled`；禁止个人/项目 context、skills、prompts、extensions 等隐式资源。 |
| `extra_model_turns/mcp` | `disabled`。 |
| `tools` | 空列表 `[]`。 |

权威输出通道由 models 的 `prompt_only` 唯一指定，不在 adapter 重复定义协议。
已选 adapter 对应模型槽的非空 protocol 只能为 `prompt_only`；槽或 protocol
尚未配置也可保存不完整快照。明确选择 json_schema/json_object 时整次检查/编译
拒绝，未选 adapter 的既有协议仍合法且可回放。provider/model/temperature/top_p
仍由 models 唯一决定。最多两次 Python attempt 不开放为参数；timeout、内存、
凭据/引用、任意 CLI 参数和命令均未定义。

重复 YAML 键、错误类型、未知字段、悬空引用、资源哈希不符和协议冲突返回脱敏
ConfigError；CLI 返回 2，不回显值、Prompt、原始异常或可执行命令。

## 登记、回放与完整性

沿用包络 `format_version: 1` 与既有三表，无需 migration。仅在非空 adapter 选择
时增加 `selectors.adapters`；无选择的旧快照保持原 JSON、身份和含义，不合成
默认 Pi 材料。check 只读，compile 原子登记原始 YAML、Prompt 精确字节、哈希、
编译值、快照和引用。同键同字节幂等，同键任何字节变化（含注释）拒绝。失败
整体回滚。load 只读 SQLite，核对选择、哈希、资源依赖及载荷，不回退到当前文件。

公共 `RuntimeConfigSnapshot.adapters` 为三个槽的只读映射，未配置为 None。
`adapter_slots` 分别返回 unconfigured/configured/placeholder；合法材料的 Prompt
strip 后为空或精确为 `...` 时为 placeholder，仍可保存明确不完整的快照。
模型槽和既有业务阶段完整性独立报告；没有 adapter 的业务配置完整性不证明
Pi 就绪，已配置 adapter 也不证明执行就绪。Read 仍缺权威契约。
已选择但 Prompt 占位的 adapter 使实际消费者阶段未就绪；受控缺项分别为
`screening_adapter_prompt_placeholder`（boundary/value）、
`reuse_adapter_prompt_placeholder`（reuse）、`read_adapter_prompt_placeholder`（Read）。
未选择 adapter 时保持旧业务配置完整性含义，不合成默认策略。

## 语义与消费者依赖

每槽的不可变 `AdapterSemantics` 含 backend、thinking_level、完整有效 policy、
系统 Prompt 原文/哈希，以及 `payload_json/semantics_id`。载荷包含
`kind: adapter_semantics` 和独立格式版本 **1**，规范序列化沿用配置身份规则。
保留实际文本空白、资源逻辑名和策略语义版本，排除普通声明版本、YAML 原始哈希、
Pi/adapter 执行审计版本、机器路径、时间和临时身份。完整材料仍保存审计版本。
这是统一阶段投影的 adapter 分量，不是完整阶段投影、阶段指纹或校准基线。

| 槽 | adapter_dependencies | calibration_adapter_slots |
| --- | --- | --- |
| screening | boundary、value | 包含 |
| reuse_assessment | reuse | 包含 |
| reading | read | 排除 |

共有资源按实际消费者传播，纯 Read 变化不影响其他 adapter 分量。普通声明改名
或仅改注释只改变完整登记/快照身份；有效指令、参数或受控策略语义变化改变对应
分量。新增行为字段必须进入载荷，并显式演进 adapter 分量格式；其身份变化传导
至实际消费者投影与基线，不因 adapter 独立演进而一律提升其他投影格式。

锁定执行版本不构成兼容性证明。无论是否涉及语义，改动 `pi_version` 或 `adapter_version`
都必须新建适配器声明版本并更新三槽 selector，已登记声明不能原地换字节；涉及语义时
还须创建新支持策略身份及材料版本，无法判断时不能宣称校准兼容。
纯传输重构只改变审计版本（仍须新建声明版本）；完整供给树哈希不整体传播为阶段语义。

统一单快照重建与 diff 已按上述消费者接入 adapter.semantics_id，见
[阶段配置投影与比较](config-projections.md)。共享材料只切换一槽时不改变其他槽的
投影；仅变 Pi/adapter 执行审计版本不改变任何投影或基线。
配置与比较不产生 minor/major、enable 或 calibration evaluation 事件。
