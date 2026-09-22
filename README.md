# PaperRadar

PaperRadar 是面向单个研究者的论文发现与研读流水线。当前仓库交付了工程入口、
研究边界、摘要层价值预测、复用可行性升级和筛选原因组合的公共验证，以及
四种公共契约各自的 `v1` 冻结快照、带全量预检的批量安全导出，以及逐份或整组
只读漂移检查；数据库、网络来源和论文处理命令尚未实现。

## 环境与安装

项目支持 Python 3.12、3.13 和 3.14，并统一使用 `uv` 与已提交的
`uv.lock`。首次准备环境可以联网：

```bash
uv sync --locked
```

运行依赖为 Pydantic v2 与 Typer，开发工具为 pytest、Ruff 和 mypy。
精确解析版本以 `uv.lock` 为唯一权威，避免依赖升级后在说明文档中保留过期副本。

CLI 的契约命令从权威 Pydantic 定义生成 Schema；纯 Python 公共验证入口使用锁定的
Pydantic v2 校验已实现的三种 Screening 输出及原因组合。冻结结构契约就绪不表示
后续业务流程已经就绪。

没有引入数据库、网络、LLM 或文档解析依赖。

## 命令行帮助

依赖准备完成后，可从真实安装入口查看中文帮助：

```bash
uv run --offline --locked paper-radar --help
```

帮助命令只向标准输出写文本；它不读取配置或凭据，不访问网络或数据库，
不创建 `data/`、`reports/`、`logs/` 等业务目录，也不消耗自动处理配额。
当前只额外注册已实现的 `contracts export` 和 `contracts check`，不注册尚未
实现的业务命令。

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

每次运行另在 `verification-runs/` 下生成新的机器可读证据，记录实际执行的检查、
未运行项、代码与依赖身份以及所验契约哈希。该目录不进入版本控制；格式、失败
表示与使用方法见[离线验证证据](docs/verification/offline-evidence.md)。局部通过
不表示完整 A1 或阶段 A 验收通过。
