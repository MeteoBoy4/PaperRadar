# PaperRadar

PaperRadar 是面向单个研究者的论文发现与研读流水线。当前仓库交付了工程入口、
研究边界、摘要层价值预测、复用可行性升级和筛选原因组合的公共验证，以及
四种公共契约各自的 `v1` 冻结快照、带全量预检的批量安全导出，以及逐份或整组
只读漂移检查；另已交付 Profile、模型、主题、三阶段提示词/契约、复用升级参数、正文提取和 Read 配置快照的显式迁移、检查、编译与历史加载。
网络来源和论文处理命令尚未实现。
期刊身份与信誉集合也可版本化登记，校验 ISSN 与冲突，并从 SQLite 回放历史。
另可登记 Pi adapter 的三个独立选择、完整有效系统指令、资源哈希、推理档位与
固定调用策略；单快照可重建六阶段配置投影和校准基线，并只读比较已保存快照。

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
当前注册 `contracts export/check`、`db upgrade` 与 `config check/compile/diff`。
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

并发编译相同材料会等待并复用同一已提交快照，成功输出与首次一致（退出 0）；
同声明身份不同字节返回版本冲突（退出 2），须新建版本。写锁等待固定为 5 秒，
超时提示“数据库忙”，请稍后显式重试。提交前失败或进程中断不会留下部分配置
事实；排除故障后用原输入重跑即可。编译只保存已读取并校验的材料，不写回来源
文件；完整结果与恢复约定见契约中的“并发、失败与恢复”。

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
实际有效输入或校准通过；统一阶段投影与 diff 已按槽消费 adapter 语义。

`settings-journals.yaml` 单独演示期刊身份、名称与信誉配置。ISSN 支持带或不带
连字符、末位大小写 X，并先验证校验位再规范化判重。空集合合法；期刊不影响
任何阶段就绪，也不进入六个阶段投影或校准基线。当前只登记事实，不执行评分、
排序或论文匹配。完整字段与公开只读类型见
[运行配置快照契约](docs/contracts/runtime-config.md)：

```bash
uv run --offline --locked paper-radar config compile \
  --settings examples/config/settings-journals.yaml --database data/paperradar.sqlite3
```

数据库选择档案库，快照引用选择其中的历史配置。先只读查看已保存的快照：

```bash
uv run --offline --locked paper-radar config snapshots list \
  --database data/paperradar.sqlite3
```

列表展示完整 ID、查询时唯一的便捷引用、创建时间（缺失显示“未记录”）与声明版本摘要，
不验证快照完整性或表示已启用。空库显示“暂无已保存快照”。从列表复制两个完整 ID
或便捷引用替换占位参数，可混用并只读比较：

```bash
uv run --offline --locked paper-radar config diff <before-reference> <after-reference> \
  --database data/paperradar.sqlite3
```

输出配置类别、版本/哈希、受影响投影与前后校准基线；比较成功均返回 0，错误返回 2。
引用接受完整 64 位小写十六进制 ID 或唯一的 8–63 位小写十六进制前缀；拒绝大写与别名。
歧义时要求补充字符。列表前缀从 8 位按需延长，63 位内无法唯一时展示完整 ID。
新增快照可能使旧前缀不再唯一，使用时重新验证；长期记录、脚本和审计保留完整 ID。
公共 diff 服务仍只接收完整 ID。列表到比较的完整示例与查询接口见
[历史快照发现与引用](docs/contracts/config-snapshots.md)。
仅改 Read 语义只影响 read 投影；期刊信誉或普通版本标签变化只影响完整快照。
历史比较只读取 SQLite 保存材料，不要求原配置文件仍存在，不输出 Profile/Prompt 正文。
公共 `project_config(snapshot)` 对一个已验证快照纯计算六投影及基线，与数据库和 CLI
解耦，供后续校准或诊断复用；没有单快照 CLI。接口与依赖矩阵见
[阶段配置投影与比较](docs/contracts/config-projections.md)。保存和比较均不启用精读，
自动运行前仍需接入完整校准变更工作流；完整 A2 通过由独立的离线结论记录。

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
`<run_id>.a1.json` 独立 A1 结论、`<run_id>.a2.json` 历史范围的 A2-01 结论，
以及 `<run_id>.a2-full.json` 完整 A2 结论。四份文件共用本次 `run_id`，不重复
执行整套检查。入口仅在本次 A1 与完整 A2 都通过时返回 0；A2-01 独立保留。
`<run_id>.pytest.json` 另行记录脱敏测试执行回执；固定范围的收集和完整通过数量
必须与已审查清单一致，跳过、取消选择、未完成或缺回执均不能通过。
一次运行由 `scripts/verification_run.py` 统一组织，验收组在
`scripts/a2_full_acceptance.py` 的 `acceptance_groups()` 显式登记；各组维护自己的
判据与中断恢复，共用不可覆盖的最终结论发布。新增组若需要扩大逐模块执行证明，
仍须显式扩展固定回执范围；登记本身不提供任意测试范围的执行证明。
测试与迁移验收使用临时 SQLite，不操作用户数据库。完整 A2 固定覆盖版本登记、
配置快照、六阶段投影、校准语义基线、只读查询、CLI 与并发中断恢复；只保存
固定测试/源码/合成材料的哈希及实际迁移与格式版本，不保存配置正文或凭据。
配置材料重构另以重构前固定的 16 种配置组合身份和 126 条中文错误文本逐字节核对，
并验证多个错误同时存在时的首条错误；检查、编译与历史回放共用材料验证和组装。
阶段输入指纹、全量业务事实、任务与共享接口、doctor、备份恢复、真实来源、
模型执行、正式校准和自动精读仍未验收；完整 A2 不等于阶段 A 或阶段 B 通过。
该目录不进入版本控制；格式、失败表示与使用方法见
[离线验证证据](docs/verification/offline-evidence.md)。
