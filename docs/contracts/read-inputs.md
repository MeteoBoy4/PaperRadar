# 单篇 Read 输入准备与调用前预算

## 用途与范围

`paper_radar.read_inputs` 将明确登记的正文制品与历史配置组合为不可变
`PreparedReadInput(stage_input, context, description, budget)`。它只读准备完整 single
输入，不领取任务、不判断用途、质量资格或 Pi 执行准入；任务消费者在自己的领取事务复核这些事实。

## 规则

`prepare_read_input(artifacts, artifact_id, extraction_input, semantic_snapshot,
audit_snapshot, *, expected_identity, output_language='zh')` 接收 #156 的
`FulltextArtifacts`、登记的正文三元组和 extraction StageInput，不接受裸 extraction 指纹。
先严格回放 extraction 配方，再核对预期三元组，调用 `FulltextArtifacts.load` 核对持久成员，
从源字符恢复完整 `ReadContext` 并执行 `validate_read_context_v2`。不导入 Docling 或模型 SDK。
extraction 配方可来自另一份历史提取配置；Read 语义配置不改写正文提取依据。

Read StageInput 只包含三元组和 zh/en，详见 [StageInput](stage-inputs.md#read-格式-1)。
模型、业务 Prompt、Profile、Contract、系统指令、档位和策略来自明确语义 snapshot；
审计 snapshot 只有同阶段投影一致才可用于取得 Pi/adapter 执行版本。配置从登记历史恢复，
不读取当前 settings，不使用“最新快照”作为默认配置。两个 snapshot 的用途见 [RPC](pi-rpc.md)。

`bounded-rpc-v1` 与 `chunking_version=v1` 的唯一冻结映射为 `read-render-v1`：
完整 reading UTF-8 原样作为 `body.reading`，另有 `body.render_version` 和按 context
顺序排列的 `body.evidence=[{evidence_id,pages}]`，页码去重升序。reading 中的 evidence
锚点、标题、受限占位和生成候选标记由持久正文生产规则提供，不再截取或重新编号。
候选和占位没有 evidence 锚点；源文本中的伪锚点已转义。Read 请求含 output_language，
没有 Screening 的 paper/title/abstract/topics。正文全部发送，不丢章节。

此映射是已有 reading adapter policy 与 chunking v1 的冻结语义，不新增可变 selector，
不改变已有投影字节。渲染或锚点语义变化必须升级相关 adapter policy 或 chunking；
未知 policy/chunking 受控拒绝，不能把未来版本映射回 v1。指纹归属见
[配置投影](config-projections.md#read-语义映射)。

`read_input_budget(description)` 是同一纯计量入口；B trace、Read 领取和 G 消费它，
不复制预算逻辑。返回 first_frame_bytes、correction_frame_bytes（最坏上界）、
cumulative_frame_bytes、accepted、reason。预算冻结为：

```text
C = 36                     # v1 安全类别闭集数
P = 192                    # 每类最长安全字段路径字符数
E = 12                     # 内层 JSON + 外层 RPC JSON 的每字符编码字节上界
F = 1024                   # 类别名、分隔符、固定中文指令等余量
S = C * P * E + F = 83968  # 最坏修正槽字节
B1 = len(UTF8(rpc-9 prompt(render_request(description, correction=None))))
B2 = B1 + S
cumulative = B1 + B2
accepted = B1 <= 262144 and B2 <= 262144
```

完整帧包含外层 `id=rpc-9/type=prompt/message`、两层 JSON 转义和末尾 LF；不是字符数、
内层消息长度或 token 估算。两次 attempt 各为独立会话，两帧分别受单次 256 KiB 上限约束；
累计值只供审计，不把两次合成一次模型上下文。语义常数由
[`llm/read_limits.py`](../../src/paper_radar/llm/read_limits.py) 唯一维护，改变阈值、公式或
修正构造规则须升 chunking 版本。

任务服务使用 `build_read_correction(issues)` 唯一构造修正：只接受 v2 安全 issue 和冻结
36 类，每类选字典序最小的安全位置、类别排序，每类至多一次。字段白名单、十进制下标
至多 19 位，路径至多 192 字符；超长、自由字段或非法路径整体折叠为 `$`，不截取原字符串。
不复制 guidance、坏 ID、引文或上轮输出。路径自身保留安全条目序号；重复位置不会扩大槽。
固定失败重试可使用同构造器的空 issue 通用修正，不拼接外部错误文本。
render_request 对 Read 的实际 correction 再核对整个外层编码增量不超过 S。

## 错误与拒绝

正文缺失、篡改、三元组不符或不可回放沿用 FulltextArtifacts 的封闭拒绝；上下文错误
沿用 v2 安全 issues；调用描述沿用 CallDescriptionError。超额不抛任务失败，返回
`accepted=false, reason=read_input_over_budget`，两个字节数均保留，可由相同制品与历史
配置重算。服务不写数据库、不建原因表、不占 attempt、不调用模型，也不截断正文。
消费者必须在领取前检查 accepted；配置 ready 或首次帧可发送均不足以领取。

Read 渲染本身允许得到完整超额字节以便纯计量；执行 RPC 仍核验完整帧硬上限。
任何实际修正超出冻结槽在渲染时受控拒绝，不能把它当作模型失败扣次数。

## 不提供／不证明

没有产品 CLI、人工请求持久层、资格门禁、任务预算表、调度或 map/reduce。
这些接口不证明真实 Docling 质量、现场 Pi 或模型质量；任务持久接线由 Body，
产品 trace 与实验根由 [B](../roadmap.md#module-b)，长文由 [G](../roadmap.md#module-g) 承接。

## 相关

依据：[#160](https://github.com/MeteoBoy4/PaperRadar/issues/160)、[ADR-0044](../adr/0044-freeze-read-input-rendering-and-preclaim-budget.md)。
[正文制品](fulltext-extraction.md)、[RPC](pi-rpc.md)、[Read 接收](read-validation.md)。
独立 D1：[Read 输入覆盖](../verification/issue-160-read-input-delivery.md)。
