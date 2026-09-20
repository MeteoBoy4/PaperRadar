# PaperRadar

PaperRadar 是面向单个研究者的论文发现与研读流水线。当前仓库交付了工程入口、
研究边界输出验证，以及 `BoundaryOutput` 的 `boundary/v1` 冻结契约安全导出；价值
预测、复用可行性升级、原因组合、只读契约检查、数据库、网络来源和论文处理命令
尚未实现。

## 环境与安装

项目支持 Python 3.12、3.13 和 3.14，并统一使用 `uv` 与已提交的
`uv.lock`。首次准备环境可以联网：

```bash
uv sync --locked
```

运行依赖为 Pydantic v2 与 Typer，开发工具为 pytest、Ruff 和 mypy。
精确解析版本以 `uv.lock` 为唯一权威，避免依赖升级后在说明文档中保留过期副本。

当前 CLI 尚未调用 Pydantic；Issue #2 AC1 明确要求先锁定阶段 A 使用的
Pydantic v2。Issue #3 已使用它交付 `BoundaryOutput` 和纯 Python 公共验证入口，
但这不表示其他 Screening 契约已经就绪。

没有引入数据库、网络、LLM 或文档解析依赖。

## 命令行帮助

依赖准备完成后，可从真实安装入口查看中文帮助：

```bash
uv run --offline --locked paper-radar --help
```

帮助命令只向标准输出写文本；它不读取配置或凭据，不访问网络或数据库，
不创建 `data/`、`reports/`、`logs/` 等业务目录，也不消耗自动处理配额。
当前只额外注册已实现的 `contracts export`，不注册尚未实现的业务命令。

## 研究边界输出验证

`paper_radar.screening.validate_output` 接受研究边界 JSON 或结构数据，成功时返回
严格的 `BoundaryOutput`，失败时抛出可操作且脱敏的受控错误。公共接口、错误类别、
占位文本规则和示例见
[Screening 输出验证接口](docs/contracts/screening-validation.md)。本接口不访问网络、
数据库、LLM 或 Docling。冻结 Schema 的格式与导出方式见
[冻结契约导出](docs/contracts/frozen-contracts.md)。

## 冻结契约导出

只支持当前已经实现的 `boundary/v1`：

```bash
uv run --offline --locked paper-radar contracts export \
  --contract boundary \
  --version v1 \
  --target contracts
```

快照写入 `contracts/screening/boundary/v1/`。同内容重跑不改写；损坏、版本不一致
或同版本内容冲突会明确拒绝覆盖。此命令不访问网络、数据库或模型，不消耗配额。

## 完整离线验证

```bash
./scripts/check-offline
```

该入口依次检查 lockfile 一致性、Ruff 格式、Ruff 静态规则、mypy 类型和
冻结契约专项测试及全部 pytest 测试。所有 `uv` 调用都带有 `--offline`；运行时使用
`--locked`，因此依赖声明与 lockfile 不一致会直接失败，而不会改写 lockfile。
若首次环境准备未完成或所需包不在本地，检查会返回非零，不会联网补装。
