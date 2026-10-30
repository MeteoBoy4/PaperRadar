# PaperRadar

PaperRadar 是面向单个研究者的论文发现与研读流水线。当前提供配置快照、不可变制品、
备份恢复、论文事实、Screening 任务与输出验证、Read 证据校验、Pi 固定供给与有界 RPC
组件，以及 JGR Feed／元数据取得服务和四刊摘要审计工具。

这些工程入口不等于完整论文处理流水线或生产运行许可。目标与判据见
[V1 规格](intent/draft.md)，当前前沿、未验范围与后续责任见[路线图](docs/roadmap.md)，
已发布的工程证明见[文档与证据入口](#文档与证据入口)。

## 能力导航

| 我想做什么 | 入口 |
| --- | --- |
| 准备环境、查看命令 | [环境与安装](#环境与安装)、[命令行帮助](#命令行帮助) |
| 初始化或升级数据库 | [数据库升级](#数据库升级) |
| 保存、校验或恢复档案库 | [备份批次与校验](#备份批次与校验)、[隔离恢复](#隔离恢复) |
| 保存和读取原始材料 | [不可变制品存储](#不可变制品存储) |
| 检查、保存和比较配置 | [运行配置快照](#运行配置快照) |
| 构造阶段输入、验证模型输出 | [阶段输入](#阶段输入)、[Screening 输出验证](#screening-输出验证)、[Read 输出与证据校验](#read-输出与证据校验) |
| 导出或检查冻结 Schema | [冻结契约导出与检查](#冻结契约导出与检查) |
| 运行开发检查、查询离线验证结果 | [完整离线验证](#完整离线验证) |
| 准备、核验和清理项目独立 Pi | [Pi 固定供给](#pi-固定供给) |
| 接入单次 RPC 组件 | [Pi RPC](#pi-rpc) |
| 查询论文、发现与来源 | [论文事实与 Feed 发现的本地查询](#论文事实与-feed-发现的本地查询) |
| 登记和查询 Screening 任务 | [Screening 任务](#screening-任务) |
| 调用 JGR 取得与登记服务 | [JGR Feed 与元数据](#jgr-feed-与元数据) |
| 登记 fixture、执行或回放摘要审计 | [Fixture 与摘要审计](#fixture-与摘要审计) |

## 环境与安装

项目支持 Python 3.12–3.14，开发解释器由 `.python-version` 选择，依赖由 `uv.lock`
锁定。首次准备环境可以联网：

```bash
uv sync --locked
```

准备后统一使用 `uv run --offline --locked …`。其中 `--offline` 限制 uv 获取依赖，
**不阻止业务命令联网**；Pi 准备／重建、摘要审计和 Feed 取得的副作用见相应章节。

长时间测试前可运行只读环境检查：

```bash
./scripts/dev-environment check
```

解释器、临时目录和容量检查的使用说明见 `./scripts/dev-environment --help`，
worktree 与离线依赖准备见[测试约定](docs/agents/testing.md#开发环境)。

## 命令行帮助

从安装入口查看中文帮助，再在所需命令或命令组后添加 `--help` 查看参数：

```bash
uv run --offline --locked paper-radar --help
uv run --offline --locked paper-radar config --help
uv run --offline --locked paper-radar audit run --help
```

帮助只输出文本，不读取配置或凭据、不访问网络或数据库、不创建业务目录。
下列示例中的尖括号表示须替换的参数；请求 JSON、PDF 和联系邮箱也须使用实际材料。
Python 服务与 CLI 的边界分别见各节所链 Contract，不将服务 API 视为已有业务命令。

## 数据库升级

显式初始化或升级工作库：

```bash
mkdir -p data
uv run --offline --locked paper-radar db upgrade --database data/paperradar.sqlite3
```

既有库升级前如需手工保护数据库副本，使用 SQLite backup API，不能只复制活动主文件
而遗漏 WAL。目标文件须尚不存在；以下示例**只保护数据库，不包含制品**：

```bash
uv run --offline --locked python - <<'PYTHON'
import sqlite3
from pathlib import Path
from urllib.parse import quote

source = Path("data/paperradar.sqlite3").resolve()
target = Path("data/pre-upgrade.sqlite3")
with target.open("xb"):
    pass
with sqlite3.connect(f"file:{quote(str(source))}?mode=ro", uri=True) as src:
    with sqlite3.connect(target) as dst:
        src.backup(dst)
PYTHON
uv run --offline --locked paper-radar db upgrade --database data/paperradar.sqlite3
```

升级与 revision 拒绝规则见[迁移契约](docs/contracts/artifact-store.md#revision-与原因码)；
备份所支持的数据库版本与旧批次操作见[备份契约](docs/contracts/backup-restore.md)。
配置命令不隐式初始化或升级数据库。

## 备份批次与校验

```bash
uv run --offline --locked paper-radar backup create \
  --database data/paperradar.sqlite3 --data-root data --output backups
uv run --offline --locked paper-radar backup verify backups/<backup-batch>
```

`create` 发布包含数据库及已登记制品的自包含批次；`verify` 只读核验该批次。
`<backup-batch>` 是实际发布的批次目录名，不是配置快照 ID。

备份不代替配置源文件、凭据和安装环境的保管；配置源文件请另用 Git 等方式保存，
凭据单独保护。批次内容、路径限制、版本支持与失败处理统一见
[备份与隔离恢复 Contract](docs/contracts/backup-restore.md)。

## 隔离恢复

`restore verify` **向目标写入完整副本**；仅检查批次时使用上节的 `backup verify`。
准备好目标父目录，使用不存在或为空的目标：

```bash
uv run --offline --locked paper-radar restore verify \
  backups/<backup-batch> --target restored
uv run --offline --locked paper-radar config snapshots list \
  --database restored/database.sqlite3
```

要将恢复副本作为工作库，再显式运行：

```bash
uv run --offline --locked paper-radar db upgrade --database restored/database.sqlite3
```

恢复不会自动启动任务、安装 Pi 或启用自动精读。目标保护、旧批次恢复、失败重试及
可恢复范围见[隔离恢复契约](docs/contracts/backup-restore.md#隔离恢复)。

## 不可变制品存储

公共 Python 服务 `paper_radar.storage.artifacts.ArtifactStore` 提供来源快照、原始 PDF、
模型成功响应、参考文献 TEI 和 extraction 集合的发布、查询与校验回读。
它保存材料，不执行 PDF 解析或模型调用，也没有通用制品人工导入 CLI。

接口、制品种类与角色、内容身份和错误处理见
[制品存储 Contract](docs/contracts/artifact-store.md)。

## 运行配置快照

初始化数据库后检查并保存配置：

```bash
uv run --offline --locked paper-radar config check \
  --settings examples/config/settings-value.yaml --database data/paperradar.sqlite3
uv run --offline --locked paper-radar config compile \
  --settings examples/config/settings-value.yaml --database data/paperradar.sqlite3
```

`check` 只读校验，`compile` 登记不可变历史快照。配置就绪不代表模型、正文解析或
校准已就绪。示例均为**工程合成材料，不是正式 Profile 或校准资料**：

| 示例 | 用途 |
| --- | --- |
| [settings.yaml](examples/config/settings.yaml) | 查看占位配置的未就绪提示 |
| [settings-boundary.yaml](examples/config/settings-boundary.yaml) | 研究边界配置 |
| [settings-value.yaml](examples/config/settings-value.yaml) | 两阶段 Screening 配置 |
| [settings-reuse.yaml](examples/config/settings-reuse.yaml) | 复用升级与建议配置 |
| [settings-extraction.yaml](examples/config/settings-extraction.yaml) | 正文提取工具链与模型配置，不运行 Docling |
| [settings-pi.yaml](examples/config/settings-pi.yaml) | Pi adapter 槽与系统指令配置，不启动 Pi |
| [settings-journals.yaml](examples/config/settings-journals.yaml) | 期刊身份与信誉登记 |
| [settings-read.yaml](examples/config/settings-read.yaml) | Read 缺少契约选择的配置示例 |
| [settings-read-ready.yaml](examples/config/settings-read-ready.yaml) | Read 配置完整示例，不执行 Read |

从列表复制两份快照的完整 ID 或便捷引用后，可只读比较：

```bash
uv run --offline --locked paper-radar config snapshots list \
  --database data/paperradar.sqlite3
uv run --offline --locked paper-radar config diff <before-reference> <after-reference> \
  --database data/paperradar.sqlite3
```

- 配置字段、版本登记、就绪判断和失败恢复：[运行配置契约](docs/contracts/runtime-config.md)。
- 历史查询与引用：[配置快照发现](docs/contracts/config-snapshots.md)。
- 阶段依赖、校准基线与比较：[配置投影](docs/contracts/config-projections.md)。
- 专题配置：[正文提取](docs/contracts/extraction-config.md)、[Pi adapter](docs/contracts/adapter-config.md)。

## 阶段输入

`paper_radar.stage_inputs` 提供 boundary/value/extraction/reuse 输入的构造、规范字节、
指纹、严格回放与比较，不执行模型或正文解析。

论文事实到 boundary/value 输入的映射由 `PaperFacts.map_screening_inputs` 提供，
支持明确历史配置与版本修订。接口、事实要求与身份规则分别见
[阶段输入契约](docs/contracts/stage-inputs.md)和
[论文输入映射](docs/contracts/paper-facts.md#8-当前查询历史重建与只读-cli)。

## Screening 输出验证

`paper_radar.screening.validate_output` 验证研究边界、摘要层价值预测和复用升级输出；
`validate_screening_reason` 验证筛选结果、来源与原因组合。
接口与上下文、受控错误、词汇及示例见
[Screening 输出验证契约](docs/contracts/screening-validation.md)。

## Read 输出与证据校验

`paper_radar.reading.validate_read_output` 验证 Read 候选原始字节与消费上下文，提供
证据引用核验、受限内容检查、数值诊断与警告视图。它是输出校验接口，不是 Read 执行器。
结构、上下文和配置接入见[Read 契约](docs/contracts/read-validation.md)，
恢复边界见[Read 恢复说明](docs/contracts/read-validation.md#恢复范围98)。

## 冻结契约导出与检查

用重复的 `--contract` 选择需要的契约，例如：

```bash
uv run --offline --locked paper-radar contracts export \
  --contract boundary --contract value-prediction --contract reuse-assessment \
  --contract decision-reasons --contract read --version v1 --target contracts
uv run --offline --locked paper-radar contracts check \
  --contract boundary --contract value-prediction --contract reuse-assessment \
  --contract decision-reasons --contract read --version v1 --target contracts
```

`export` 安全发布快照，`check` 只读检查漂移。契约选择、目录布局、不可覆盖规则与
部分失败后的重试见[冻结契约 Contract](docs/contracts/frozen-contracts.md)。

## 完整离线验证

开发中先运行相关功能测试，再按变更类型选择入口兼容组合；例如：

```bash
uv run --offline --locked pytest tests/test_feed_pipeline.py
./scripts/check-compatibility acceptance
./scripts/check-compatibility cli
```

`all` 可替代两个组合，运行去重并集。选择依据与使用边界见
[开发入口契约](docs/contracts/check-compatibility.md)和[测试导航](docs/agents/testing.md)。

完整离线门禁及历史结果查询：

```bash
./scripts/check-offline
./scripts/verification-status <run_id> --json
```

门禁执行锁文件、格式、静态规则、类型、全部 pytest 与冻结契约检查；运行证据保存在
`verification-runs/`。正式结论与当前工作树适用性分开查询，不用历史 passed 代替当前验证。
检查计划、回执登记范围及各组证明边界见[离线验证证据](docs/verification/offline-evidence.md)，
输出说明见[状态查询契约](docs/contracts/verification-status.md)。

固定验收材料变化时，可先运行只读登记审计：

```bash
./scripts/audit-verification-scope --json
```

需要核对固定用例数时添加 `--collect`；收集不执行测试体，也不发布验收结论。
操作规则见[scope 审计契约](docs/contracts/verification-scope-audit.md)，
登记维护见[维护说明](docs/verification/offline-evidence.md#固定-scope-维护审计60)。

## Pi 固定供给

项目独立管理 Pi／Node 安装，不依赖个人 Pi。`prepare` 与 `rebuild` 会**联网下载并安装**，
`verify` 执行无模型检查；这些命令不调用模型、不自动激活供给。
先按[供给请求格式](docs/contracts/pi-supply.md#显式输入与请求)准备 `supply.json`：

```bash
uv run --offline --locked paper-radar pi supply prepare \
  --database data/paperradar.sqlite3 --snapshot <snapshot-reference> --adapter-slot screening \
  --request supply.json --install-root .tools/pi --data-root data \
  --config-root config --material-root tools/pi
uv run --offline --locked paper-radar pi supply list --database data/paperradar.sqlite3
uv run --offline --locked paper-radar pi supply show <supply_id> --database data/paperradar.sqlite3
uv run --offline --locked paper-radar pi supply verify <supply_id> --database data/paperradar.sqlite3
uv run --offline --locked paper-radar pi supply rebuild <supply_id> \
  --database data/paperradar.sqlite3 --install-root .tools/pi --data-root data \
  --config-root config --material-root tools/pi
uv run --offline --locked paper-radar pi supply export <supply_id> \
  --database data/paperradar.sqlite3 --target tools/pi
```

执行选择与供给范围诊断：

```bash
uv run --offline --locked paper-radar pi supply activate <supply_id> \
  --database data/paperradar.sqlite3 --snapshot <snapshot-reference>
uv run --offline --locked paper-radar doctor --scope pi-supply \
  --database data/paperradar.sqlite3 --snapshot <snapshot-reference>
```

清理先保存并审阅计划，再显式执行。**`--dry-run` 会保存计划，但不删除安装**：

```bash
uv run --offline --locked paper-radar pi supply gc --dry-run \
  --database data/paperradar.sqlite3 --data-root data \
  --config-root config --material-root tools/pi
uv run --offline --locked paper-radar pi supply show-plan <plan_id> \
  --database data/paperradar.sqlite3
uv run --offline --locked paper-radar pi supply gc --execute <plan_id> \
  --database data/paperradar.sqlite3
```

`tools/pi/` 是可提交的导出材料，`.tools/pi/` 是不提交的安装树。
平台、根目录、安装保护、恢复后使用和故障处理见
[Pi 供给 Contract](docs/contracts/pi-supply.md)，清理操作见
[安装清理计划](docs/contracts/pi-supply.md#不可变安装清理计划)。
供给检查和激活不代表 RPC、模型或校准就绪。

## Pi RPC

`paper_radar.llm` 提供冻结调用描述，`paper_radar.llm.rpc.run_call` 提供显式注入会话的
有界单次协议组件；管道组件接管已启动的进程，不提供默认生产启动器。
接口与支持范围见[RPC 契约](docs/contracts/pi-rpc.md)，架构决策见
[ADR-0026](docs/adr/0026-control-pi-through-a-bounded-rpc-adapter.md)。
真实执行与隔离接线的承接入口见[路线图承接索引](docs/roadmap.md#模块承接索引)。

## 论文事实与 Feed 发现的本地查询

```bash
uv run --offline --locked paper-radar paper show PAPER_ID --database data/paperradar.sqlite3
uv run --offline --locked paper-radar paper trace PAPER_ID --database data/paperradar.sqlite3 \
  --data-root data --verify-source-bytes --json
```

`paper show/trace` 只读查询论文身份、版本、字段来源与发现历史。摘要需显式
`--show-abstract` 展开；来源字节核验不会转储原始响应。

Python 服务 `PaperFacts` 提供来源提交、Feed 登记、人工字段修正、历史修订与版本关系，
以及强身份冲突的查询、原断言与原字节回查。身份、
[文本输入](docs/contracts/paper-facts.md#51-文本规范形式-v1n1)、仲裁、查询和错误规则见
[论文事实 Contract](docs/contracts/paper-facts.md)。该 CLI 不提供生产导入或完整任务资格查询。

<a id="screening-任务登记有限尝试与两阶段成功a7-02-至-a7-08"></a>

## Screening 任务

`paper_radar.screening_tasks.ScreeningTasks` 提供 boundary/value 请求登记、冻结回放、
有限尝试、租约、成功接收、显式 retry 与历史查询；这是 Python 服务，不是 screening CLI。
value 通过 `register` 登记时由调用方提供语言事实，`register_feed_value` 则从 Feed
发现归属派生该事实。
接口与任务语义见[Screening 任务契约](docs/contracts/screening-tasks.md)，
派生入口见[Feed 原题名语言来源](docs/contracts/screening-tasks.md#feed-原题名语言来源)，
来源政策见[ADR-0035](docs/adr/0035-feed-derived-original-title-language-fact.md)。

当前执行边界仅提供 test 来源，不提供真实模型执行。产品接线与后续责任见
[路线图 B](docs/roadmap.md#module-b)。

## JGR Feed 与元数据

JGR 的网络取得服务已可显式调用；这些 Python API 不提供真实导入 CLI、调度或模型调用。

| 能力 | 公共服务与文档 |
| --- | --- |
| Feed 检查、发现登记、故障继续与原 item 回查 | `JGRFeed`：[取得契约](docs/contracts/feed-ingestion.md) |
| 补充适用注册机构与出版者元数据、查询缺项与来源 | `JGRMetadata`：[元数据契约](docs/contracts/feed-metadata.md) |
| 串联取得、最低元数据、语言依据和 value 登记，组合 trace | `FeedPipeline`：[组合契约](docs/contracts/feed-pipeline.md) |

组合服务提供生产登记与明确的 test 工程路径，但不生成 boundary 成功，也不授予 B
实验或自动精读资格。登记前置及拒绝规则统一见组合契约。
真实来源核实与纵向接线见[路线图承接索引](docs/roadmap.md#模块承接索引)。

## Fixture 与摘要审计

声明登记与只读查询：

```bash
uv run --offline --locked paper-radar fixture register fixtures/a10/historical-v1.json \
  --database data/paperradar.sqlite3 --data-root data
uv run --offline --locked paper-radar fixture check fixtures/a10/historical-v1.json \
  --database data/paperradar.sqlite3
uv run --offline --locked paper-radar fixture list --database data/paperradar.sqlite3 --history --json
uv run --offline --locked paper-radar fixture show RECORD_ID --database data/paperradar.sqlite3 --json
```

本机 PDF 和 backend 期望分别登记；请求格式见
[PDF 字节与期望契约](docs/contracts/fixture-audit.md#pdf-字节事实与-backend-期望102)：

```bash
uv run --offline --locked paper-radar fixture register pdf-request.json --pdf-file sample.pdf \
  --database data/paperradar.sqlite3 --data-root data
uv run --offline --locked paper-radar fixture register backend-request.json --backend \
  --database data/paperradar.sqlite3 --data-root data
uv run --offline --locked paper-radar fixture check RECORD_ID --pdf \
  --database data/paperradar.sqlite3 --data-root data --json
```

`audit run` 和 `resume` 会**联网并保存取得事实**，每次显式提供联系邮箱；
`list/show/replay` 只读，不联网。以下命令不调用模型：

```bash
uv run --offline --locked paper-radar audit run \
  --database data/paperradar.sqlite3 --data-root data --contact-email <email> --count 5 --json
uv run --offline --locked paper-radar audit list --database data/paperradar.sqlite3 --json
uv run --offline --locked paper-radar audit show PLAN_ID --database data/paperradar.sqlite3 --json
uv run --offline --locked paper-radar audit resume PLAN_ID \
  --database data/paperradar.sqlite3 --data-root data --contact-email <email>
uv run --offline --locked paper-radar audit replay PLAN_ID \
  --database data/paperradar.sqlite3 --data-root data --json
```

历史完整汇总可通过 `replay --summary-sha256 <sha256>` 选择；原摘要通过公共服务
`read_audit_text` 显式读取。类别、选样、主摘要、HTTP 通道、恢复与完成审计引用的规则见
[Fixture 与摘要审计 Contract](docs/contracts/fixture-audit.md)。声明登记、字节完整或
计划完成都不等于真实来源达标或 Docling 质量通过。

## 文档与证据入口

- 目标与验收：[V1 规格及任务阅读导航](intent/draft.md#任务阅读导航)。
- 领域术语与决策：[GLOSSARY](GLOSSARY.md)、[ADR](docs/adr/)。
- 当前前沿、阶段状态与后续责任：[路线图](docs/roadmap.md)。
- 离线检查与工程证明：[离线验证证据](docs/verification/offline-evidence.md)、
  [阶段 A 收口与证据索引](docs/verification/stage-a-closure.md#证据索引与范围)。
- 专项覆盖：[Pi 供给](docs/verification/a4-requirements.md)、
  [阶段输入](docs/verification/offline-evidence.md#a5-独立结论4754)、
  [论文事实](docs/verification/a6-requirements.md)、
  [Screening 任务](docs/verification/a7-requirements.md)、
  [RPC](docs/verification/a8-requirements.md)、
  [Read](docs/verification/contracts-read-validation-history.md#92-覆盖台账)、
  [Fixture／摘要审计](docs/verification/a10-requirements.md)。
- Feed 工程与解析边界：[交付证据](docs/verification/issue-114-feed-delivery.md)、
  [parser 固定回归](docs/verification/feed-parser-v1.md)。
- 历史研究：[Pi 供给 spike](docs/research/pi-1.3.0-supply-spike.md)，不作为 live 验收结论。
