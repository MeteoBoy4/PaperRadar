# Pi Agent 接入 PaperRadar：结构输出可行性实测

> 2026-10-10；研究实验，不是实现票、ADR、正式校准或自动精读验收。
> **结论：可行。推荐 Python 主程序通过 RPC 控制 Pi，继续由 PaperRadar 的权威 Pydantic Schema 与业务规则决定结果能否接收。Pi 的模式本身不保证业务 JSON 合法。**

## 1. 四种模式如何选择

Pi 官方文档明确四种 CLI 模式共用同一 agent、模型与工具：

| 模式 | 接口与寿命 | 在 PaperRadar 中的适用性 |
|---|---|---|
| Interactive | TUI，直到用户退出 | 人工预热、提示词探索；不适合无人值守阶段输出 |
| Print | 一次运行，stdout 为最后的 assistant 文本 | 最小接入验证，文本可以是 JSON，但需自行解析、校验 |
| JSON | 一次运行，stdout 为 JSONL 事件流 | 批处理及进度观察；须从最终消息取业务结果 |
| RPC | 长驻子进程，stdin/stdout 双向 JSONL | **推荐给 Python 主程序**：可控制会话、取消、重试配置、工具与完成边界 |

SDK 是额外的 TypeScript/Node 集成方式，**不是第五种 CLI mode**。Python 项目用 RPC 通常无需额外维护 Node 业务服务；Pi 自身仍是 Node 进程，并不变成 Python 包。

特别注意：`--mode json` 保证的是**外层事件协议**，并不会令模型回答自动满足 `BoundaryOutput` / `ReadAnalysisOutput`。RPC 的 `prompt` 成功响应只代表接收提示词；应消费到 `agent_settled`，再判断模型、工具、Schema 和业务结果是否成功。JSON 模式也不能只凭进程退出码判断模型成功。[P1–P4]

## 2. 实验材料及隔离

### 环境

- Pi：本机安装 `1.1.0`。
- 模型：显式固定 `openai-codex/gpt-6.1-sol`，thinking=`low`；沿用已配置 OAuth，无凭证复制、输出或模型 fallback。
- Python 校验与编排：项目 `.venv/bin/python`，Python `3.14.4`、Pydantic `2.13.5`，由 `uv run --offline --locked` 启动。精确实测版本同时记录在本地 manifest。
- PDF 解析：复用既有独立 `/tmp/paperradar-docling-check/.venv`，通过 `uv run --no-project --offline --python ...` 启动，不修改项目依赖或 lockfile。
- 隔离 cwd：`.scratch/pi-contract-probe/workspace/`。
- Pi 禁用会话持久化、自动发现 extensions/skills/prompts/context、MCP 和通用内置工具。提交工具实验只显式加载一份自写 extension。
- 关闭 Pi agent-level retry、provider-level retry 和自动 compaction；本次所有调用均首次成功，不运行修复重试。
- 提示词通过 stdin/内存发送；不落盘完整提示词、会话或事件流。保留成功模型制品、输入 fixture、校验结果与哈希，日志只记录摘要。
- 未打开业务数据库，未生成真实筛选决定，未改变配置、Frozen Contract、校准基线或门禁。

本次最初的 `pi auth check` 发现命令错误是**选项位置问题**：把普通运行选项放在 `auth` 前，CLI 没有走子命令解析。随后以 `pi auth check --provider openai-codex --json --no-refresh` 检查，返回 `ready`。不据此认定官方文档或认证有问题。

### 一篇真实 Feed 论文

选定规格中的《大气科学》Feed，然后在其当前 21 条记录中用固定种子 `20261010` 随机选择一条；不是按预期结论挑选：

- Feed：<https://www.iapjournals.ac.cn/dqkx/rss/current.xml>
- 题名：**影响重庆的西南涡强降水动态分布特征及成因分析**。
- DOI：`10.3878/j.issn.1006-9895.2508.25052`。
- 出版者页面：<https://www.iapjournals.ac.cn/dqkx/article/doi/10.3878/j.issn.1006-9895.2508.25052>
- 摘要：出版者页面 `dc.description`，去除 HTML 后 353 字符；Screening 输入只包含题名、摘要、完整性标记和合成 Profile，不包含期刊信誉。
- 下载：出版者页面公开 `citation_pdf_url`，无 cookie/token/机构凭证；HTTP 成功、PDF 签名、体积上限检查通过。
- PDF：22,936,131 bytes、16 页；SHA-256：`80c07925fc4f0cad13a59d881929d85877046f165b7b8a84122aeda08e679893`。

RSS 是带 namespace 的 RDF/RSS 1.0，最初不带 namespace 的 `.//item` 查询未发现条目；改为 `.//{*}item` 后正常解析。此为实验取样代码，不是已交付的 Feed adapter。

### 正文与 Profile

- Docling/PyPdfium2、CPU、OCR/公式/图片增强/远程插件关闭，表格结构开启，heading hierarchy 开启；使用既有探测环境本地模型。
- 解析成功，约 **12.98 秒、峰值 RSS 1968 MiB**；全原始制品基础 provenance 审计为 0 个错误，无 U+FFFD、无 Markdown/JSON base64 图片。
- 去除 PDF 第 1 页的出版者推荐页，排除参考文献；图表、公式及图注只提供降级提示，不提供它们作为精确证据。
- Read 提供 101 个文本证据块，ID 绑定 PDF 哈希、document 哈希和 Docling source_ref；保留原 PDF 页码、bbox、源字符串与 charspan。
- 合成六段 Profile 关注西南涡、强降水与动态合成，现有主题 ID 为 `heavy-rain` / `vortex-dynamics`；不声称这是真实研究画像。
- 复用升级仅提供从资料方法页取出的一个固定 methods 摘录，以 `methods-1` 为输入 ID。

**该解析器配置与手工实验规范化不是项目冻结的正文工具链/normalization v1，也没有通过四刊 fixtures；不能因此声明该制品取得正式 Read 资格。**本次只是给结构实验提供真实正文与可回查证据。[R1–R4]

该论文已经暴露模型建议，应作为“结构实验、已暴露样本”排除于未来正式盲评。当前业务来源/样本分配器尚未实现，因此没有向不存在的 registry 或数据库伪造排除事实；接入正式采集时需显式登记这个已暴露样本。

## 3. 校验口径

### Screening：使用已有权威实现

- Schema 来自 `screening/schema.py` 的 `model_json_schema()`，不另写字段列表。
- 最终结果交给现有 `validate_output()`。
- boundary、value_prediction、reuse_assessment 分别运行，不把不同阶段合成一个输出契约。
- value 使用只读已启用主题集合与“原题名中文”上下文。
- reuse 使用固定 excerpt ID / kind 上下文。
- 严格拒绝字段扩展、字符串/布尔评分、无效枚举、未知主题、重复项及相应业务规则违例。[R2]

### Read：临时校验器，不能冒充已交付权威实现

当前仓库没有 Read 的权威 Schema / validator；`intent/draft.md` §4.10 只有设计定义。[R1]

实验在 scratch 中以该节建立临时 Pydantic 模型，再从它生成 Schema：

- 检查所有设计字段、受控枚举、严格整数 1–5、未知字段拒绝。
- 必需文本非空；主要发现至少一项；有证据要求的每项 evidence 列表非空。
- 检查输出语言与输入一致、研究价值至少 3 时价值类型非空、类型不重复。
- 检查引用 ID 来自本次制品，并回查原 PDF 页码存在、bbox 在页面边界内、charspan 可回放且支持片段非空。
- 不向 Read 暴露图表等受限内容作为精确 evidence。

**没有完整实现数值字面量/范围/单位匹配与警告追加，也没有完成正文阅读顺序、全覆盖、四刊 fixtures 或语义蕴含验收。**`min_length` 非空与字段合法也不证明中文质量、评分可靠性或每个结论都被原文支持。Read 结果只能称为“临时结构 + 引用可回查检查通过”。

## 4. 实测结果

每格一次独立调用，同一篇论文、同一合成 Profile、同一模型；没有修复、围栏剥离、类型强转或截断补全：

| 输出通道 | Boundary | ValuePrediction | ReuseAssessment | Read 临时检查 |
|---|---:|---:|---:|---:|
| Print：最终纯 JSON 文本 | 通过 / 8.83s | 通过 / 19.41s | 通过 / 12.56s | 通过 / 60.13s |
| JSON：取最后 assistant `message_end` 文本 | 通过 / 8.20s | 通过 / 20.14s | 通过 / 13.08s | 通过 / 59.11s |
| RPC：完成事件后取最终文本 | 通过 / 4.87s | 通过 / 15.07s | 通过 / 9.68s | 通过 / 53.78s |
| RPC + 专用提交工具 | 未测 | 通过 / 17.44s | 未测 | 通过 / 49.11s |

- 共 **14 次真实模型调用，14 次首次通过**。
- JSON/RPC 事件确认实际 provider/model，均为固定模型；各一次 assistant turn，无 auto-retry 事件。Print 不暴露消息元数据，仅能记录显式 CLI 选择，生产审计不如 JSON/RPC 完整。
- 两次提交工具实验各一次 tool call；返回 `terminate: true` 后正常 settled，没有额外的解释性模型调用。
- 所有模式实测 stderr 为零；事件流仅在内存解析，不保存包含全文和提示词的 transcript。
- **这是 1 篇 × 1 个模型的小样本可行性证明，不是“生产成功率 100%”，也不能从这些秒数断言 RPC 更快或工具方式更省钱。**
- Print/JSON/普通 RPC 的 Read 研究价值为 5，工具 Read 为 4；四次复用可行性均为 3。字段合法不等于跨调用评分确定；Screening 语义和校准仍须独立验证。

### 反例

对真实成功结果做本地突变并再次校验，**11/11 被拒绝**：字符串评分、布尔评分、未知主题、价值类型缺失、重复主题、额外 Rank、`inferable=false` 未说明输入不足、未知 evidence ID、空 evidence、截断 JSON、Markdown 围栏。

反例是确定性 Python 校验测试，**不是另外 11 次模型调用**，也没有测试模型在被拒绝后能否在剩余一次预算内修好。

## 5. 推荐的接入边界

```text
PaperRadar Python 确定性流程
  → 构造阶段输入、版本/哈希/预算
  → Pi RPC（固定模型、工具 allowlist、临时会话）
  → 模型结构输出
  → PaperRadar Schema + 业务校验
  → 成功制品 / 受控失败
  → PaperRadar 自行产生建议、写事实、处理校准与任务资格
```

可选更明确的终结形式：

```text
Pi 模型调用 submit_artifact(阶段字段)
  → TypeBox 参数 Schema 从 Pydantic JSON Schema 导入
  → Python 权威校验
  → 成功才返回 validated artifact，并终结该 agent run
```

实验 extension 仅内联 `$defs` 以适配工具参数传输，**不手写第二套领域 Schema**；Python 校验仍是接收的最终边界。工具调用参数也不是无限制可靠：模型可以不调用工具、调用无效参数、缺字段或失败，必须 fail closed。此次没有实现生产级修复协议或无限 agent 工具循环。[P5]

建议：先把 Pi 做成一个有界、可测试的 **LLM/Agent adapter**，而非把 PaperRadar 整条领域流程搬入自主 Agent。正式接入时仍需要：

1. 一阶段一隔离会话（RPC 长驻时用 new_session/reset 或明确重建进程），防止历史 Profile、题名、隐藏校准结果和全文章节串入 Screening。
2. 固定 provider/model、prompt、contract、Profile、工具声明与运行策略身份；会改变阶段语义的工具集/提示词/代理行为进入相应 fingerprint 和校准 change workflow。
3. 重试统一计数：关闭 Pi 隐含 retry，权威程序对同一阶段输入最多两次；工具循环、provider retry、自动 compaction/summarization 等额外模型调用不能藏在一个 attempt 里。
4. 检查最终消息 stopReason、settled、工具接收结果、超时、取消及子进程异常，不能把 RPC ACK 或 JSON 退出码当成功。
5. 仅保留脱敏执行信息与必要成功制品；不要永久落盘 Pi 完整 session/JSONL，其中可能含全文、Profile 和提示词。
6. 使用受控工具，而不是给不可信论文文本一个通用 `bash`、网络、数据库写权限。`--tools` 不是 OS sandbox；正式工具隔离及权限约束需另外设计。
7. 对 config 中实际协议能力诚实建模：纯文本方式是 `prompt_only`；工具提交也不能仅因参数带 Schema 就假称 provider 原生严格 `json_schema`。现有 config slot/protocol 与 Pi adapter 的映射尚未实现。
8. Read 权威 Schema、全文质量门槛、数字警告和恢复/幂等行为仍待后续实现；不要把临时 Schema 发布为 Frozen Contract。

### 我的决策

V1 以纯文本（prompt_only）实现，工具提交作为已验证的备用升级。可以共存，但共存的位置是“适配器协议能力”层面，不是同一次调用里双通道并存。适配器同时支持两种协议能力，按 stage 配置选择，一次运行只有一个权威通道。不要让两条通道在同一次调用里竞争。

## 6. 更灵活的模型、全文和 PDF 工具能否放进 Agent？

技术上可以：Pi 的 extensions / SDK 能提供自定义工具，RPC 可以选择显式模型；工具可以包装合法全文获取、Docling 转换和 evidence 查询。[P1,P5,P6]

但“可以调用”不等于“可以自行决定”：

- **模型选择**：保留显式版本化模型；不能让 Agent 自主换 Screening 模型或自动 fallback。切换 Screening 侧语义仍须用户校准变更分级；Read 模型独立版本化。[R3]
- **全文取得**：可由受控工具实现多来源 I/O，但 adapter 只产生 observation；许可、凭证、访问阻断、预算、下载校验、幂等与来源仲裁仍归确定性代码。不能自动绕过反爬、付费墙或使用机构订阅。
- **PDF 提取**：可把 Docling 封装为工具，但 V1 仍只允许同一锁定 Docling 链与质量门槛。自主挑选解析器、OCR、多模态/图片理解、多 backend fallback 与当前规格/ADR 冲突，需明确另立变更，不能随着 Pi 接入静默启用。[R4]
- **Evidence**：工具可以按 ID 返回当前制品片段，不让模型创造坐标、页码或伪造 evidence。长文 map/reduce 的最终引用仍只能来自受控当前制品。
- **流程决定**：accepted/pending/denied、自动精读名额、Topic 创建、持久化与校准隔离不交给 Agent。

Pi 也**不是摆脱 LLM 服务的办法**：本次它仍然调用固定外部模型，只是替代了直接 API 调用上的 harness/transport/tool 层。更灵活是否更便宜、更准确、更稳定，本次均未证明。

`intent/draft.md` §7.6 当前描述 PydanticAI 隔离接口；若正式改选 Pi，须记录 adapter 架构决策并同步规格/配置语义，而非先改真实配置。此文只提出候选，不改既有决策。

## 7. 结果位置、复跑与验证

本地全部实验材料：`.scratch/pi-contract-probe/`（git ignored）。

- `probe.py`：Python 编排、临时 Read Schema、现有 Screening validator 调用与反例。
- `submit.ts`：唯一提交工具 extension，参数 Schema 从生成文件导入，调用 Python 校验。
- `feed.xml`、`feed-item.json`、`publisher.html`、`paper.json`、`paper.pdf`：真实来源 fixture。
- `profile.json`、`*-schema.json`、`reading-input.json`、`evidence.json`：实验输入与生成 Schema。
- `*-artifact.json`：成功制品；`*-result.json`、`negative-results.json`：摘要和校验结果。
- `experiment-manifest.json`：环境、输入/脚本/Schema/成功制品哈希、事件核对与 usage（不是实际账单）。
- `document.json`、`parse-manifest.json`、`summary.json`：解析来源及配置身份。

本地材料未作为生产代码提交；删除 scratch 或独立解析环境后，以下命令不构成自包含复跑包。此次没有新建生产 CLI、修改数据库或将实验代码放入 `src/`。

已有材料下（真实模型调用会消耗所配置服务额度）：

```bash
uv run --offline --locked python .scratch/pi-contract-probe/probe.py run --mode rpc --kind value_prediction
uv run --offline --locked python .scratch/pi-contract-probe/probe.py run --mode rpc --kind reading --submit
uv run --offline --locked python .scratch/pi-contract-probe/probe.py negative
```

这里 `uv --offline` 仅表示 Python 依赖解析不联网，Pi `--offline` 仅禁用启动自动网络活动，**模型调用仍会联网**。

验证：

- 上述 14 次 live 调用与 11 个本地拒绝反例实际运行。
- 最小相关离线测试：`test_boundary_validation.py`、`test_value_prediction_validation.py`、`test_reuse_assessment_validation.py`、`test_contract_schema.py`：**187 passed**。
- 完整仓库离线验证：`./scripts/check-offline` **通过**（lockfile、format、lint、types、tests、contracts；A1/A2-01 已实现离线范围结论 passed）。证据：`verification-runs/c4bd49a5c8cd42e8ab4d13feeecc0a90.json` 及对应 `.a1.json` / `.a2.json`；这不代表完整阶段 A、业务流水线或正式精读已验收。

## 8. 一手依据

### Pi（本机安装包完整文档、导出类型及实际运行）

本次阅读使用的包根目录：`/home/meteoboy4/.local/share/pi-node/node-v22.23.2-linux-x64/lib/node_modules/@earendil-works/pi-coding-agent/`。链接为上游相应官方文件；API 细节以本次本机版本和实测为准，不能假定未来 main 与 1.1.0 一致。

- [P1：CLI Integration](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/cli-integration.md)：四种模式、SDK 边界、JSON 非业务约束。
- [P2：Command Line](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/cli.md)：显式模型、资源/工具禁用、临时会话。
- [P3：RPC](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/rpc.md)、[RPC Commands](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/rpc-commands.md)：命令接收与完成区别、取消、会话控制、关闭。
- [P4：JSON Events](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/json.md)：最终 `message_end`、`agent_settled`、stop reason 和事件元数据。
- [P5：Extensions](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md)、[Hello Tool](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/hello.ts)：TypeBox 参数、自定义工具、`terminate` 和运行边界。
- [P6：SDK](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/sdk.md)、[Settings](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/settings.md)：模型/工具配置、重试与 compaction 控制。

### PaperRadar

- R1：[实施规格](../draft.md) §4.9、§4.10、§7.4、§7.6、§8.3；[当前交付范围](../../README.md)。
- R2：[权威 Screening Schema](../../src/paper_radar/screening/schema.py)、[业务验证](../../src/paper_radar/screening/validation.py)、[上下文](../../src/paper_radar/screening/context.py)。
- R3：[ADR-0004](../../docs/adr/0004-do-not-fallback-to-an-uncalibrated-screening-model.md)、[ADR-0016](../../docs/adr/0016-allow-paper-content-to-be-sent-to-configured-llms.md)。
- R4：[ADR-0010](../../docs/adr/0010-use-docling-as-the-only-body-parser.md)、[ADR-0025](../../docs/adr/0025-allow-local-formula-candidates-with-source-review.md)、[既有解析实验](docling-issue-20-live-probe.md)。

## 9. 用户指定 QJRMS PDF：subagent 中的独立 RPC 全契约实验

> 2026-10-10；这是第二篇独立样本，不改写上文中文论文的 14 次结果。四种 Agent 输出各测试普通 RPC 最终 JSON 与 RPC + 唯一提交工具。**8 格最终均通过相应结构与适用业务检查；实际共 9 次 RPC 启动尝试，其中 1 次基础设施中止，不能写成 8 次首次成功**。未运行新模型或输出方式 fallback。

### 9.1 样本、执行线程与环境

- 用户明确指定本地 `/tmp/paperradar-feedcheck/new/qjrms_qj70317.pdf`，没有重新下载、访问出版者或使用出版方/机构凭证；文件 **18,625,018 bytes、21 页**。
- 原题名：**Improving heavy precipitation forecasts through phase-aware nonlinear bias correction of all-sky infrared radiances using cloud top temperature differences**；DOI：`10.1002/qj.70317`。题名来自 PDF 第 1 页，DOI 在 PDF 的引用说明及下载页脚中核对，不从文件名猜测。
- PDF SHA-256：`13e8947a39c92f98871dfce0660b032613f010d80b12b9712b807a896cdcedc3`。
- 摘要是第 1 页 `Abstract` 到 `KEYWORDS` 之间的完整单块，**1862 字符**，source_ref=`#/texts/16`，charspan=`[0,1862]`，保留真实页码与 bbox；没有拼补摘要或只凭题名调用 Screening。完整性判断依据与哈希见 `abstract-provenance.json`。
- 唯一写入线程是子代理 `worker`，原 run ID：`66691ab2-b9b7-47cb-90ac-87abf84dd5ba`。原会话位置：`/home/meteoboy4/.pi/agent/sessions/--home-meteoboy4-Projects-PaperRadar--/2026-10-10T08-17-45-534Z_01a124e3-b63e-766c-886c-d1e850182f23/52732ac2-e691-4083-9ce9-ae640954b7e5/run-0/session.jsonl`（编排会话位置，不是实验 Pi transcript）。
- 原 worker 在全部模型实验成功制品保存后，父会话报告其基础设施状态为 **failed / WebSocket closed1000**；经父会话明确批准恢复，仅核对已有材料、补本地校验/manifest、跑离线验证并追加本节。恢复没有新增或重跑任何模型实验，也没有派生其他子代理。
- Pi **1.1.0**；固定 **openai-codex/gpt-6.1-sol、thinking low**。项目 Python **3.14.4** / Pydantic **2.13.5**，实际由 `uv run --offline --locked python` 启动。每格独立 RPC 子进程/会话，隔离 cwd=`.scratch/pi-contract-probe-qjrms/workspace/`。
- `--no-session -ne -ns -np -nc --no-themes --no-mcp --offline`，普通路径 `--no-tools`；工具路径只显式加载本次 `submit.ts`，`--tools submit_artifact`。关闭 agent/provider retry、自动 compaction 与 cache warming。`get_state` 核对固定模型、thinking 与无 sessionFile；原始 RPC 事件仅内存消费，不落盘完整 prompt/Profile/全文会话或事件流，不打印凭证。
- 合成六段 Profile 针对东亚强降水、全天空红外资料同化、云相态/云顶温度偏差、局部回归与小规模 WRFDA 测试条件；不是上一篇西南涡 Profile，也不是真实用户画像。主题仅 `all-sky-da`、`precipitation-forecast`，由实验输入预先固定。

### 9.2 本篇 Docling 与证据输入

未找到本篇既有 Docling 结果，因此在既有独立 `/tmp/paperradar-docling-check/.venv` 解析一次，没有新装依赖、切换解析器或覆盖旧结果：

```bash
uv run --no-project --offline --python /tmp/paperradar-docling-check/.venv/bin/python \
  /tmp/paperradar-docling-check/parse.py \
  /tmp/paperradar-feedcheck/new/qjrms_qj70317.pdf \
  pypdfium-default-hierarchy pi-contract-probe-qjrms
```

- 解析输出：`/tmp/paperradar-docling-check/outputs/pi-contract-probe-qjrms/qjrms_qj70317/`。
- Docling/slim **2.135.0**、core **2.101.1**、parse **7.22.2**、IBM models **4.0.3**、pypdfium2 **5.14.0**；torch **2.14.1+cpu**、torchvision **0.29.1+cpu**、transformers **5.19.0**。完整模型 commit/文件哈希和 pipeline/backend options 在 `parse-manifest.json` 中。
- CPU，单论文串行；OCR、公式/代码/图片/图表增强、远程服务与外部插件关闭；TableFormer accurate/cell matching、heading hierarchy 开启。
- 解析 `success`，**15.294 秒、峰值 RSS 1828.57 MiB**。基础审计 provenance issue **0**、U+FFFD **0**、JSON/Markdown 无 base64 图片；准备阶段另检查全部 **164 个非受限非空正文块**的 provenance、页边界与非空可回放 charspan，未伪造或修补坐标，也未靠忽略坏 provenance 继续。
- 本篇第 1 页就是论文首页，没有沿用上一篇“删除第 1 页封面”的逻辑。保留摘要及 introduction 至 availability；移除前置信息、下载水印/页脚碎片、ORCID 和参考文献。图表、公式、图注替换为明确占位，不作为精确证据提供。保留 **61 个文本 evidence**，ID 绑定本篇 PDF SHA、document SHA 和 source_ref，原页码不重编。
- 本地恢复审计逐项检查 61 个 evidence 的 source_text/provenance 与保存的 DoclingDocument 原项完全匹配。文档 SHA-256：`4b4654a70d68f7a9f833cb5170317927acb23d2a5579860d39751b3fd15cb6dd`。

**上述只证明本次输入的基础位置可回查，不证明正式正文质量门槛通过**。手工样本专属过滤不是 frozen normalization；阅读顺序/章节全覆盖、跨页合并与科学字符精度没有完成正式人工核查或四刊 fixtures。availability 有跨行词/URL 切分风险，保留源字符不静默修正。本次仍不是阶段 F/G 验收或正式 Read 资格。

### 9.3 四种 Agent 契约的边界与结果

三种 Screening 调用已有权威 `screening/schema.py`、`validate_output()`；Read 仍使用 scratch 中 draft §4.10 的**临时** Pydantic Schema/validator，不发布 Frozen Contract。

- Boundary 仅题名、完整摘要与 Profile，无 topics 或全文。
- ValuePrediction 仅题名、摘要、Profile 与固定现有主题，不消费正文/复用摘录；英文原题名正确使用 `original_title_is_zh=False`。
- ReuseAssessment 仅 Profile 与预先固定的 PDF 第 18 页 Data Availability 摘录，ID=`qjrms-availability-1`、kind=`availability`；用同一 ID/kind 的权威上下文校验，不冒充 methods 摘录。
- Read 使用本篇独立正文与 evidence。检查字段/类型/枚举/额外字段、严格整数 1..5、非空文本、价值类型规则；主要发现、两项评分理由、每个复用点/局限须有非空 evidence，ID 来自本制品且页码、bbox、charspan 可回放、支持片段非空，受限内容不作精确 evidence。
- 工具参数从各阶段 Pydantic `model_json_schema()` 生成并仅内联 `$defs`，Python 校验后才接收；成功返回 `terminate: true`。没有通用 bash/读写/网络工具交给模型。

| 契约 | 普通 RPC 最终 JSON | RPC + submit_artifact | 实际尝试数（普通 / 工具） |
|---|---|---|---:|
| BoundaryOutput | 通过 / 7.30s | 通过 / 8.27s | 1 / 1 |
| ValuePredictionOutput | 通过 / 16.23s | 通过 / 21.91s | 1 / 1 |
| ReuseAssessmentOutput | 通过 / 11.92s | 通过 / 16.04s | 1 / 1 |
| ReadAnalysisOutput（临时） | attempt1 中止 / 0.17s；attempt2 通过 / 51.27s | 通过 / 49.18s | **2 / 1** |

**基础设施失败与批准的修复：**首个 Read RPC 的 Python `asyncio.readline()` 默认 64 KiB 上限遇到长 JSONL 记录，抛出 `LimitOverrunError`，外层为 `ValueError`；不是 Schema 拒绝或 provider 失败。未取得 settled/合法结果，立即 kill 并等待原 Pi 进程退出，确认无遗留 RPC 进程。supervisor 明确批准后，仅在本专属 scratch 将 reader 改为 **4 MiB 有界帧**与 **240s 接收总期限**，保留 LF framing；同 RPC、同模型做 Read attempt2。第一次中止前是否已触发模型或消耗额度未知，保守计入该路径两次预算；它不算成功，也不据此断言免费。原失败摘要及原 reader 脚本分别保留为 `rpc-reading-attempt1-result.json`、`initial-reader-probe.py`。没有契约修复重试。

8 次合法完成均：`agent_settled`、exit code 0、stderr 0、实际固定 provider/model、一轮 assistant、无 auto-retry；普通路径 stopReason=`stop`，工具路径=`toolUse`、各一次成功验证工具调用，成功后无额外模型解释轮。ACK 只核对命令接收，不作为成功依据。各格独立 session ID 与 usage 见 result/manifest；usage 不是实际账单。

两条 Boundary 均 `in_scope`。这些格本来就是用户授权的隔离契约实验，不写任何 accepted/pending/denied 或正常业务资格；也没有从 Boundary 自动推进真实流程。普通/工具 Value 的研究价值分别 5/4、初步复用均 2 且不可判断；Reuse 与 Read 复用均 3，Read 研究价值均 4。这些评分只用于说明制品字段与调用间差异，**不是研究结论正确性或用户适用性证明**。

本篇合计 **9 次 RPC 尝试、8 次合法完成、1 次基础设施中止**。此前中文样本的 14 次首次通过保持不变；不能合并宣传为“22 次首次成功”或生产成功率。

### 9.4 本地反例、验证与未交付项

- 已保留的 Read 成功结果突变反例 **9/9 拒绝**：未知 evidence ID、额外 rank、评分 0/6、字符串/布尔分数、空 evidence、非法枚举、价值类型缺失。恢复只复用反例文件，未覆盖模型制品。
- 新增纯本地 `validate_screening_reason()` 测试：穷举 result/source/reason 的 **384** 个组合，再加额外字段/未知原因/缺字段/错误类型 **4** 个反例，共 **34 合法接受、354 非法拒绝**。这是权威确定性原因契约测试，**不是 388 次模型调用**；从未要求 LLM 输出最终 accepted/pending/denied。
- `check_local.py` 重新校验已有 8 个成功制品、61 个 evidence 到 document 的映射，核对四份生成 Schema 等于当前 Pydantic 导出，检查 settled/模型/stopReason/工具调用/ACK。没有重新跑模型。
- 先运行相关离线测试：`uv run --offline --locked pytest tests/test_boundary_validation.py tests/test_value_prediction_validation.py tests/test_reuse_assessment_validation.py tests/test_decision_reason_validation.py tests/test_contract_schema.py` → **250 passed in 0.20s**。
- 再运行 `./scripts/check-offline` → **通过**（lockfile、format、lint、types、tests、contracts）；证据：`verification-runs/219cf5491d7241df9db267f8a6422812.json`、同名 `.a1.json` / `.a2.json` 均 passed。仍只覆盖已交付 A1/A2-01 离线范围，不代表完整阶段 A 或 Read/校准门禁。

**仍未实现/未证明：**Read 权威 Schema/validator、关键数值字面量/范围/相邻单位的确定性匹配与 degraded warning 追加、语义蕴含、中文报告质量、研究评分正确性、全文阅读顺序及四刊 fixture gate。引用存在并可回放不等于原文蕴含结论。工具 allowlist 不是 OS sandbox；临时 validator 不是正式生产恢复/预算管理接口。

本篇已经暴露 Agent 结果，应作为“用户指定结构实验、已暴露样本”排除未来正式盲评；未写业务数据库或不存在的排除 registry，未来正式采集时需明确登记。未改 src/tests、uv.lock、正式配置、Frozen Contract、校准门禁或业务数据库；无 commit/push/staged files。git 仍只显示原有且已追加本节的未跟踪报告。

### 9.5 所有材料、安全摘要及复跑

专属材料根：`/home/meteoboy4/Projects/PaperRadar/.scratch/pi-contract-probe-qjrms/`；没有覆盖 `.scratch/pi-contract-probe/`，manifest 保留其文件哈希清单与本报告追加前字节哈希。

- `probe.py` / `submit.ts`：实际 RPC 编排与提交工具；`initial-reader-probe.py` / `adapt.py`：首次 reader 与历史适配过程，**不要再运行 adapt.py 覆盖当前脚本**。
- `paper.json`、`abstract-provenance.json`、`profile.json`、`reuse-input.json`、`reading-input.json`、`evidence.json`、四份 `*-schema.json`：仅实验输入/Schema 制品，不是运行日志。
- `document.json`、`parse-manifest.json`、`options.json`、`summary.json`、`preparation.json`：源映射与过滤依据；原解析目录见 §9.2（包含 `evidence-preview.json`、reading preview 等，完整 inventory 在 manifest）。
- `rpc-*-artifact.json`、`rpc-*-raw-success.txt/json`：8 份合法成功制品与原始最终文本/工具调用参数；`rpc-*-result.json`：9 次尝试的脱敏摘要，含首次失败。
- `negative-results.json`、`check_local.py`、`local-audit-results.json`：Read 反例、原因正反例及恢复核对；`finish_manifest.py` / `experiment-manifest.json`：环境、执行线程、失败/恢复、尝试数、输入/输出/脚本/官方 docs/旧实验哈希。
- `parse-safe-summary.log`、`parse-stderr.log`、`local-audit-safe-summary.log`、`focused-tests.log`、`check-offline.log`：安全执行摘要与实际验证结果；无完整 prompt/Profile/全文/事件 transcript。
- 子代理安全摘要：`/home/meteoboy4/.pi/agent/sessions/--home-meteoboy4-Projects-PaperRadar--/subagent-artifacts/outputs/66691ab2-b9b7-47cb-90ac-87abf84dd5ba/.scratch/pi-contract-probe-qjrms/subagent-summary.md`。

复核现有制品无需模型调用：

```bash
for file in .scratch/pi-contract-probe-qjrms/rpc-*-artifact.json; do
  kind=${file##*/rpc-}; kind=${kind%%-*}
  uv run --offline --locked python .scratch/pi-contract-probe-qjrms/probe.py \
    validate --kind "$kind" < "$file" > /dev/null || exit 1
done
```

未来显式复跑 live 实验时需新目录，不覆盖此次成功/失败材料（会消耗服务额度，本次恢复**未执行**下列命令）：

```bash
rerun=".scratch/pi-contract-probe-qjrms-rerun-$(date +%Y%m%d-%H%M%S)"
mkdir "$rerun"
cp .scratch/pi-contract-probe-qjrms/{probe.py,submit.ts} "$rerun/"
uv run --offline --locked python "$rerun/probe.py" prepare
for kind in boundary value_prediction reuse_assessment reading; do
  uv run --offline --locked python "$rerun/probe.py" run --mode rpc --kind "$kind" || exit 1
  uv run --offline --locked python "$rerun/probe.py" run --mode rpc --kind "$kind" --submit || exit 1
done
```

复跑依赖既有本地 PDF、独立解析结果/环境、项目 uv 环境与已配置模型认证，不是自包含发行包；若重新解析须用新的 unique_output_profile，并显式适配 scratch `PARSE`。`uv --offline` 与 Pi `--offline` 不禁止已授权的模型请求联网。没有把输入制品冒充日志或把本次结果发布为正式领域契约。
