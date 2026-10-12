# PaperRadar

PaperRadar 是面向单个研究者的论文发现与研读流水线。当前仓库交付了工程入口、
研究边界、摘要层价值预测、复用可行性升级和筛选原因组合的公共验证，以及
四种公共契约各自的 `v1` 冻结快照、带全量预检的批量安全导出，以及逐份或整组
只读漂移检查；另已交付 Profile、模型、主题、三阶段提示词/契约、复用升级参数、正文提取和 Read 配置快照的显式迁移、检查、编译与历史加载。
网络来源和论文处理命令尚未实现。
另可登记 Pi adapter 的三个独立选择、完整有效系统指令、资源哈希、推理档位与
固定调用策略；其只读语义供后续统一投影消费。

## 环境与安装

项目支持 Python 3.12、3.13 和 3.14，并统一使用 `uv` 与已提交的
`uv.lock`。首次准备环境可以联网：

```bash
uv sync --locked
```

运行依赖为 Pydantic v2、Typer、PyYAML、SQLAlchemy 和 Alembic；开发工具为
pytest、Ruff、mypy 和 PyYAML 类型声明。
精确解析版本以 `uv.lock` 为唯一权威，避免依赖升级后在说明文档中保留过期副本。

CLI 的契约命令从权威 Pydantic 定义生成 Schema；纯 Python 公共验证入口使用锁定的
Pydantic v2 校验已实现的三种 Screening 输出及原因组合。冻结结构契约就绪不表示
后续业务流程已经就绪。

当前无网络、LLM 或文档解析依赖。

## 命令行帮助

依赖准备完成后，可从真实安装入口查看中文帮助：

```bash
uv run --offline --locked paper-radar --help
```

帮助命令只向标准输出写文本；它不读取配置或凭据，不访问网络或数据库，
不创建 `data/`、`reports/`、`logs/` 等业务目录，也不消耗自动处理配额。
当前注册 `contracts export/check`、`db upgrade` 与 `config check/compile`。
不注册尚未实现的业务命令。

## 运行配置快照

`db upgrade` 是唯一可创建数据库的命令；`config check` 只读，`config compile`
只打开已迁移的既有库。三个命令均要求明确路径：

```bash
uv run --offline --locked paper-radar db upgrade --database data/paperradar.sqlite3
uv run --offline --locked paper-radar config check \
  --settings examples/config/settings.yaml --database data/paperradar.sqlite3
uv run --offline --locked paper-radar config compile \
  --settings examples/config/settings.yaml --database data/paperradar.sqlite3
```

先创建数据库父目录，例如 `mkdir -p data`。示例是工程验收合成材料，不是正式
校准资料。当前可选六段式 Profile、单份三槽 models 文件、主题集合、boundary/value/reuse 提示词、四份 A1 冻结契约与复用升级参数。boundary、value、reuse 和 suggestion 各自报告配置就绪；value 需要已配置的主题集合，空集合和全部停用均合法。`examples/config/settings-value.yaml` 使用完整合成 Profile，演示两阶段均就绪；`settings-boundary.yaml` 演示仅 boundary 就绪；`settings-reuse.yaml` 演示缺 value/PDF/extraction 时 reuse 和 suggestion 配置就绪，触发集合默认仅 `{3}`、摘录顺序固定为 availability 优先；算法身份只接受受控 v1，不执行摘录选择或建议规则。原 `settings.yaml` 保留占位 Profile，展示未就绪原因。公共 Python 服务可从数据库加载旧快照；完整字段、声明版本规则、
身份格式、未就绪范围和迁移行为见
[运行配置快照契约](docs/contracts/runtime-config.md)。

`settings-read.yaml` 使用新增的 `models-read-v1`、独立 `config/read/read-v1.yaml`
和 `prompts/reading/v1.md`，演示 Read 模型、业务提示词和受控 chunking v1 的
版本登记与历史回放。`settings.read` 选择分块配置，`prompts.reading` 选择提示词；
Read 始终 `not_ready`，该合成示例仅缺 `read_contract`，boundary 仍配置就绪。
当前不执行分块或 Read，不接受手写 Read Schema，也不构成阶段 B 验收：

```bash
uv run --offline --locked paper-radar config compile \
  --settings examples/config/settings-read.yaml --database data/paperradar.sqlite3
```

`settings-extraction.yaml` 独立演示正文提取配置就绪：受控工具链、pypdfium2、
Egret medium、TableFormer accurate 和默认开启的 CodeFormulaV2 局部公式候选，
模型按阶段登记 commit 与文件哈希。此票不安装 Docling、下载模型、检查模型文件
或解析 PDF；配置就绪不代表四刊 fixture gate 或资源检查通过。模型哈希为合成示例，
不用于正式解析。源文本/生成文本分离与裁切核查由后续解析实现；公开字段与边界见
[正文提取配置契约](docs/contracts/extraction-config.md)。

`settings-pi.yaml` 使用新增的不可变 `models-pi-v1`，演示 Screening 与复用升级
使用 V1 选定的 `prompt_only` 协议，四份业务冻结契约继续使用原 `v1`。例如：

```bash
uv run --offline --locked paper-radar config check \
  --settings examples/config/settings-pi.yaml --database data/paperradar.sqlite3
uv run --offline --locked paper-radar config compile \
  --settings examples/config/settings-pi.yaml --database data/paperradar.sqlite3
```

该示例只证明 boundary、value、reuse 与 suggestion 配置完整；模型、Profile 和
提示词仍为合成材料，Read 未就绪。当前没有 Pi RPC 执行器，也不检查 Pi/Node、
认证、实际参数能力或运行隔离。旧 models 与示例选择保留，以维持历史版本和快照
回放；配置层继续接受既有协议，不代表 Pi 会支持或自动切换这些协议。
接入目标与边界见 [ADR-0026](docs/adr/0026-control-pi-through-a-bounded-rpc-adapter.md)。
示例独立选择三个 adapter 槽，使用一份 `adapters/pi-v1.yaml` 与它引用的
`config/prompts/pi-system-v1.md`。未选择 adapter 时明确显示 unconfigured；旧快照
身份和回放保持不变。完整字段、固定策略及阶段/校准消费者依赖见
[Pi adapter 配置契约](docs/contracts/adapter-config.md)。配置事实不证明执行隔离、
实际有效输入或校准通过；统一阶段投影、校准基线和 diff 联动仍待 #23。

## Screening 输出验证

`paper_radar.screening.validate_output` 接受研究边界、摘要层价值预测或复用可行性
升级的 JSON/结构数据及适用只读上下文，成功时返回对应权威类型，失败时抛出可操作
且脱敏的受控错误。`validate_screening_reason` 严格验证结果、来源与原因三元组，返回
保留建议、人工决定或只读失败投影身份的类型；`screening_reason_json_schema` 从同一
组合权威生成内存 JSON Schema。公共接口、错误类别、组合表和示例见
[Screening 输出验证接口](docs/contracts/screening-validation.md)。本接口不访问网络、
数据库、LLM 或 Docling。冻结 Schema 的格式、导出与只读检查见
[冻结契约导出](docs/contracts/frozen-contracts.md)。

## 冻结契约导出与检查

当前可一次选择一份或多份以下固定契约，声明版本均为 `v1`：

- `boundary`
- `value-prediction`
- `reuse-assessment`
- `decision-reasons`

例如一次导出全部四份契约：

```bash
uv run --offline --locked paper-radar contracts export \
  --contract boundary \
  --contract value-prediction \
  --contract reuse-assessment \
  --contract decision-reasons \
  --version v1 \
  --target contracts
```

`--contract` 可重复，每份至多一次；命令按上述声明顺序处理。快照写入
`contracts/screening/<契约名>/v1/`。写入前会预检全部既有目标；损坏、版本不一致
或同版本内容冲突不会产生任何新快照。发布阶段逐份安全落盘，不承诺跨快照事务：
若中途失败，预检时已经一致的项目标为“未改写”，故障前完整写入的项目标为
“已创建”，只有失败项和仍缺失的未处理项标为“未完成”；修复后用原命令重跑会
保持完整项不变并补齐缺失项。此命令不访问网络、数据库或模型，不消耗配额。

只读确认整组快照仍与当前权威定义一致：

```bash
uv run --offline --locked paper-radar contracts check \
  --contract boundary \
  --contract value-prediction \
  --contract reuse-assessment \
  --contract decision-reasons \
  --version v1 \
  --target contracts
```

单份或整组均通过重复 `--contract` 显式选择，按固定声明顺序逐项输出契约、版本、
结果、错误类别和中文处理说明。全部一致返回 0；任一项缺失、不可读取、损坏、版本
不一致或内容漂移时，其他项仍会完成检查，报告全部结果后返回 2。检查不修复、不
刷新、不创建任何文件，也不访问网络、数据库或模型。

## 完整离线验证

```bash
./scripts/check-offline
```

该入口依次检查 lockfile 一致性、Ruff 格式、Ruff 静态规则、mypy 类型、全部
pytest 测试（包括冻结契约导出与只读检查测试），最后用一次显式整组
`contracts check` 确认四份已提交快照分别与当前权威定义一致。所有 `uv` 调用都带有
`--offline`；运行时使用 `--locked`，因此依赖声明与 lockfile 不一致会直接失败，
而不会改写 lockfile。若首次环境准备未完成或所需包不在本地，检查会返回非零，
不会联网补装。

每次运行在 `verification-runs/` 下生成新的 `<run_id>.json` 离线证据、
`<run_id>.a1.json` 独立 A1 结论与 `<run_id>.a2.json` A2-01 结论。入口仅在
两份结论都通过时返回 0；阶段 A 剩余能力、真实来源和自动精读仍未验收。
该目录不进入版本控制；格式、失败表示与使用方法见
[离线验证证据](docs/verification/offline-evidence.md)。
