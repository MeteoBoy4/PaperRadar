# PaperRadar

PaperRadar 是面向单个研究者的论文发现与研读流水线。当前仓库交付了工程入口、
研究边界、摘要层价值预测、复用可行性升级和筛选原因组合的公共验证，以及
`BoundaryOutput` 的 `boundary/v1` 冻结契约安全导出与只读漂移检查；原因契约及其他
输出的磁盘冻结快照、数据库、网络来源和论文处理命令尚未实现。

## 环境与安装

项目支持 Python 3.12、3.13 和 3.14，并统一使用 `uv` 与已提交的
`uv.lock`。首次准备环境可以联网：

```bash
uv sync --locked
```

运行依赖为 Pydantic v2 与 Typer，开发工具为 pytest、Ruff 和 mypy。
精确解析版本以 `uv.lock` 为唯一权威，避免依赖升级后在说明文档中保留过期副本。

当前 CLI 尚未调用 Pydantic；纯 Python 公共验证入口使用锁定的 Pydantic v2
校验已实现的三种 Screening 输出及原因组合，但这不表示其冻结契约或后续业务流程
已经就绪。

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

只支持当前已经实现的 `boundary/v1`：

```bash
uv run --offline --locked paper-radar contracts export \
  --contract boundary \
  --version v1 \
  --target contracts
```

快照写入 `contracts/screening/boundary/v1/`。同内容重跑不改写；损坏、版本不一致
或同版本内容冲突会明确拒绝覆盖。此命令不访问网络、数据库或模型，不消耗配额。

只读确认这份快照仍与当前权威定义一致：

```bash
uv run --offline --locked paper-radar contracts check \
  --contract boundary \
  --version v1 \
  --target contracts
```

一致返回 0；缺失、不可读取、损坏、版本不一致或内容漂移返回非零并给出受控
中文类别。检查不修复、不刷新、不创建任何文件，也不访问网络、数据库或模型。

## 完整离线验证

```bash
./scripts/check-offline
```

该入口依次检查 lockfile 一致性、Ruff 格式、Ruff 静态规则、mypy 类型、全部
pytest 测试（包括冻结契约导出与只读检查测试），最后实际运行
`contracts check` 确认已提交快照与当前权威定义一致。所有 `uv` 调用都带有
`--offline`；运行时使用 `--locked`，因此依赖声明与 lockfile 不一致会直接失败，
而不会改写 lockfile。若首次环境准备未完成或所需包不在本地，检查会返回非零，
不会联网补装。
