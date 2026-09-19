# PaperRadar

PaperRadar 是面向单个研究者的论文发现与研读流水线。当前仓库只交付了
Issue #2 的工程入口；Screening 契约、数据库、网络来源和论文处理命令尚未实现。

## 环境与安装

项目支持 Python 3.12、3.13 和 3.14，并统一使用 `uv` 与已提交的
`uv.lock`。首次准备环境可以联网：

```bash
uv sync --locked
```

运行依赖为 Pydantic v2 与 Typer，开发工具为 pytest、Ruff 和 mypy。
精确解析版本以 `uv.lock` 为唯一权威，避免依赖升级后在说明文档中保留过期副本。

当前 CLI 尚未调用 Pydantic；Issue #2 AC1 明确要求先锁定阶段 A 使用的
Pydantic v2，具体 Screening 契约仍由后续 ticket 交付。这项锁定不表示契约能力
已经就绪。

没有引入数据库、网络、LLM 或文档解析依赖。

## 命令行帮助

依赖准备完成后，可从真实安装入口查看中文帮助：

```bash
uv run --offline --locked paper-radar --help
```

帮助命令只向标准输出写文本；它不读取配置或凭据，不访问网络或数据库，
不创建 `data/`、`reports/`、`logs/` 等业务目录，也不消耗自动处理配额。
当前不注册尚未实现的业务命令。

## 完整离线验证

```bash
./scripts/check-offline
```

该入口依次检查 lockfile 一致性、Ruff 格式、Ruff 静态规则、mypy 类型和
全部 pytest 测试。所有 `uv` 调用都带有 `--offline`；运行时使用
`--locked`，因此依赖声明与 lockfile 不一致会直接失败，而不会改写 lockfile。
若首次环境准备未完成或所需包不在本地，检查会返回非零，不会联网补装。
