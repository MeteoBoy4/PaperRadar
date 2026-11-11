# PaperRadar

PaperRadar 是面向单个研究者的论文发现与研读流水线。当前提供配置快照、不可变制品、
备份恢复、论文事实、Screening 任务与输出验证、Read 证据校验、Pi 固定供给与有界 RPC
组件，以及 JGR Feed／元数据取得服务、四刊摘要审计工具、只读 doctor、
安全运行日志与共享资格／校准可见性纯规则，以及不依赖 SDK 的规范正文生产与持久证据回查。

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
| 从 canonical 生产正文、恢复逐字证据 | [规范正文公共服务](docs/contracts/fulltext-extraction.md) |
| 检查、保存和比较配置 | [运行配置快照](#运行配置快照) |
| 只读诊断基础工程、显式配置与供给 | [只读诊断](#只读诊断) |
| 接入安全日志和共享纯规则 | [运行日志与共享规则](#运行日志与共享规则) |
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

可选的 CPU Docling 供给使用同一张产品锁。选择其他 minor 时先固定解释器和独立
磁盘环境,让安装、smoke、doctor 与后续命令共用；新终端须恢复这两个变量：

```bash
export UV_PYTHON=/absolute/path/to/python3.13
export UV_PROJECT_ENVIRONMENT="$PWD/.venv-docling-py313"
```

首次显式准备与缓存就绪后的离线安装分别为：

```bash
uv sync --locked --extra docling
uv sync --offline --locked --extra docling
uv run --offline --locked --extra docling python scripts/check_docling_imports.py
```

安装、模型供给与正文质量分别验证；支持限制、离线失败与模型冻结规则见
[CPU extra 安装](docs/contracts/extraction-config.md#cpu-extra-安装与支持面)，
实测范围见[安装证据](docs/verification/issue-152-docling-installation.md)，
进度与后续责任见[路线图](docs/roadmap.md#module-extra)。

长时间测试前可运行只读环境检查：

```bash
./scripts/dev-environment check
```

解释器、临时目录和容量检查的使用说明见 `./scripts/dev-environment --help`，
worktree、离线依赖准备与 pytest 临时材料保留规则见[测试约定](docs/agents/testing.md#开发环境)。

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

## 只读诊断

数据库先按[数据库升级](#数据库升级)显式准备，再选择诊断范围：

```bash
uv run --offline --locked paper-radar doctor --scope basic --database data/paperradar.sqlite3
uv run --offline --locked paper-radar doctor --scope config \
  --database data/paperradar.sqlite3 --settings examples/config/settings.yaml
# examples 是合成配置。退出 0 可以和 stage=... result=missing 并存。
uv run --offline --locked paper-radar doctor --scope config \
  --database data/paperradar.sqlite3 --snapshot <snapshot引用>
uv run --offline --locked paper-radar doctor --scope config \
  --database data/paperradar.sqlite3 --settings absent-settings.yaml
# 显式文件不可读：check=selection result=invalid reason=selected_file_unreadable，退出 2。
uv run --offline --locked paper-radar doctor --scope pi-supply \
  --database data/paperradar.sqlite3 --snapshot <snapshot引用>
```

四态结论区分缺失、非法、所检范围通过与未检查；退出 0 不代表任何阶段可运行。
`pi-exec` 需要显式选择，退出 2 会逐项解释执行阻断：

```bash
uv run --offline --locked paper-radar doctor --scope pi-exec \
  --database data/paperradar.sqlite3 --snapshot <id> \
  --credentials-dir /path/to/owner-provisioned-credentials
```

它只读核对 Screening 当前档位 boundary/value 两格的完整绑定与共享准入事实，
按必要项计算 executable 和退出码；披露型 unknown 保留原状态、原因与下一步，退出成功也逐项展示。
Read 此命令未选择、未诊断。它仅检查凭据元数据，不刷新、不解析 token。
共享结构化行与中文片段供 B/H 日报嵌入，不计入论文容量，见 [doctor Contract](docs/contracts/doctor.md#pi-执行诊断)。

`docling-runtime` 恰选 settings 或 snapshot，检查当前平台与所选依赖；模型、native ABI、
fixture/质量与资源仍为 not_assessed，详情见[公共探测契约](docs/contracts/docling-runtime.md)。

```bash
uv run --offline --locked paper-radar doctor --scope docling-runtime \
  --database data/paperradar.sqlite3 --settings examples/config/settings-extraction-v2.yaml
```

doctor/help 不建库或日志，不调用网络、模型或 Docling。选择规则、六阶段 readiness、
外发说明和证明边界见 [doctor Contract](docs/contracts/doctor.md)。

## 运行日志与共享规则

`audit run/resume` 向显式 `--data-root` 下的 `logs/` 写有限轮转安全事件。
库服务默认 `NullSink`；执行组合可以显式传入 `sink=FileSink(root)`。
只读查询、doctor、help 不建日志；写入故障不改变业务回执，成功制品仍由原接口回查。
格式、保留与隐私规则见[运行日志 Contract](docs/contracts/runtime-logging.md)。

`eligibility.evaluate_paper/evaluate_concept` 提供单篇与按概念批量资格投影。
`Concept.READ_PREREQUISITES` 表达无须人工请求的单篇 Read 前置；自动队列仍拒绝实验根，
人工请求可引用当前合法系统 accepted。前置通过不授予名额、任务领取或预算豁免。
`calibration.visibility.evaluate_visibility` 判定共享许可：论文事实和任务明细可见，
隐藏成员的 Agent 内容与普通动作受限。它们是库纯规则，尚不表示真实展示面或调度已接线。
支持范围与责任见[共享规则 Contract](docs/contracts/eligibility-visibility.md)，
独立工程覆盖见 [A 窄收口台账](docs/verification/a-narrow-delivery.md)，消费者见[路线图](docs/roadmap.md#模块承接索引)。

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
| [settings-extraction-v2.yaml](examples/config/settings-extraction-v2.yaml) | v2 工具链、pypdfium2 显式选择与合成模型身份 |
| [settings-extraction-v2-threaded.yaml](examples/config/settings-extraction-v2-threaded.yaml) | v2 工具链、threaded 显式选择与独立解析语义 |
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

`paper_radar.read_inputs.prepare_read_input` 从登记正文与历史配置准备完整单篇 Read，
在领取前检查含最坏修正槽的完整 RPC 帧预算；超额返回 `read_input_over_budget`。
接口和限制见 [Read 输入准备](docs/contracts/read-inputs.md)，覆盖见
[独立 D1 台账](docs/verification/issue-160-read-input-delivery.md)。

`paper_radar.stage_inputs` 提供 boundary/value/extraction/reuse/read 输入的构造、规范字节、
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

## PDF 与正文持久提取

`paper_radar.body.BodyService` 提供人工 PDF 附加、不可变根用途、直接人工决定、
冻结样本、持久提取预算及独立版式核查。
`paper_radar.docling_executor.DoclingParser` 通过显式模型根、超时和地址空间上限，
在离线受限子进程中执行所选工具链；[执行契约与调用方式](docs/contracts/docling-execution.md)
及[单样本真实 smoke 与隔离恢复记录](docs/verification/issue-164-docling-smoke.md)说明资源口径和能力上限。
外部 canonical parser 通过显式参数注入，
只读事实可在调用者事务内核验；备份会重验正文业务闭包。
接口、拒绝与限制见[正文持久化契约](docs/contracts/body-persistence.md)，
产品入口和真实核查责任见[路线图 B](docs/roadmap.md#module-b)。

## 显式 Read 任务与历史分析

`paper_radar.read_tasks.ReadTasks` 提供已 accepted 论文的显式登记、有限预算、租约、
受控修正、retry、v2 分析接收与证据回查。实际前置来自同库 Body 和元数据事实，
实验分析保留来源/质量/丢弃标记并被普通消费拒绝；备份在无 extra 环境重验完整业务闭包。
`paper_radar.read_queries.ReadQueries` 提供当前/历史分析、两轴状态、旧配置列表及保留证据回查；
仅使用明确历史快照，不自动重跑，展示 DTO 不携带原始候选或被丢弃内容。
`paper_radar.read_execution.ReadExecution.run_attempt` 组合单篇 Pi 执行、领取和权威接收；
在凭据刷新前、准备完成后和领取事务内复用 Screening 的分项证据权威；
各消费者格/档位不借证据，正文质量、根用途、输入预算及任务资格仍独立判断，
必需证据缺失或退化时在领取前拒绝。公共边界见[Read 任务](docs/contracts/read-tasks.md)及
[执行契约](docs/contracts/read-execution.md)，跨消费者组合与恢复候选见
[独立 D1 台账](docs/verification/issue-165-body-read-closure.md)。产品 CLI 与真实 Pi 接线
责任见[路线图 B](docs/roadmap.md#module-b)。

## Read 输出与证据校验

`paper_radar.reading.acceptance_v2.validate_read_output_v2` 接收完整 Read 候选与消费上下文，
首次坏指针要求修正，末次可丢弃无效证据列表项；合法受限源内容保留并附核对警告。
`paper_radar.reading.validate_read_output` 保留 v1 历史接收规则。两者都是纯输出接收接口。
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

`live-evidence/v1` 回执可通过 `--contract live-evidence` 单独导出或检查。
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
未绑定测试失败时额外显示安全模块路径与 setup/call/teardown/collection 阶段，
可单独重跑该模块；辅助诊断不含测试参数或原始错误，也不改变正式回执与退出判据。
检查计划、回执登记范围及各组证明边界见[离线验证证据](docs/verification/offline-evidence.md)，
输出说明见[状态查询契约](docs/contracts/verification-status.md)。
完整入口的执行、回执模块与本地帮助使用显式生产组登记；测试人工预期和历史读者格式表
分别独立维护。新增组机制保持当前 required 集合与完整 A 证明边界，扩展规则见状态查询契约。

固定验收材料变化时，可先运行只读登记审计：

```bash
./scripts/audit-verification-scope --json
# 比较稳定本地 main 与当前工作树；显式列出候选、来源、敏感变化及逐组确认缺口
./scripts/audit-verification-scope --base main --integration-target main --json
```

需要核对固定用例数时添加 `--collect`；收集不执行测试体，也不发布验收结论。
操作规则见[scope 审计契约](docs/contracts/verification-scope-audit.md)，
登记维护见[维护说明](docs/verification/offline-evidence.md#固定-scope-维护审计60)。
全部实际跨组共享材料采用单处中央哈希，各组保留显式成员、用途和固定计数；
scope 使用显式引用保留下游影响，不再要求下游 scope 机械更新哈希。
中央条目变化按实际消费组、材料用途与显式基线审阅，详见审计契约。
第二步的固定分母、新增独立覆盖及登记维护实测见
[集成台账](docs/verification/scope-registry-integration.md)；开发审计和组合回归不代替最终树的正式门禁。

规格、README、术语和现状 Contract 已与历史固定材料解绑；修改这些活文档无需重绑，
仍会改变历史 run 对当前工作树的适用性。冻结依据与本次迁移见
[第一步迁移台账](docs/verification/scope-document-migration.md)，
实施与收口遵循[项目集成规则](docs/agents/verification-scope.md)。

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

新的 Live 私有审阅包使用独立入口，派生当前策略/最新 activation 后冻结 strict β、七计划、
六格合成材料、user slice/静态 anchor、nft/resolver 和精确零参 wrappers：

```bash
uv run --offline --locked python scripts/seal_live_bundle.py --help
```

归档及每个成员均有精确 SHA；日期/网络 pending 时安装继续拒绝。新包不自动 receive 或激活，
升级/同 SHA 重跑/卸载/显式恢复保留历史与累计额度。流程与现场边界见
[Live 封印审阅包](docs/contracts/live-evidence.md#live-封印审阅包)。

旧 β 站点封印模式保留独立入口：

```bash
uv run --offline --locked python scripts/seal_site_evidence.py --help
```

入口输出冻结 Python/依赖/源码、零请求批准计划、部署/卸载脚本、SHA256 与私有审阅说明。
所有者审阅确切字节后从 root 冻结副本部署，默认卸载保留账本与回执；不自动证据激活。
采集只观察当前站点和认证/cache stat 元数据，不读秘密正文、不认证、不调用模型、不联网。
正常刷新取证采用 manifest v2 的三次外部执行批次：A 为 boundary-low，B 为 boundary-high，C 为 value-low 及剩余三格。批间返回并释放锁／进程；B 或 C 首格缺真实刷新提交证据时持久 unknown 停止，不自动补跑。供应商真实到期保持 unknown；既有六格和原七份 v2 计划各自保留来源，部署后72小时目标不延长共同授权窗口。详细边界见 [Live 契约](docs/contracts/live-evidence.md#正常认证刷新闭环)；离线工程覆盖见 [独立台账](docs/verification/issue-177-normal-auth-refresh.md)。新版封印字节仍须所有者审阅并部署，未执行现场不能判通过。

认证/cache 使用固定 v2 不变量基线，允许限定订阅刷新；封印产品认证入口经固定 1.4.0 公开 API 采样正常刷新／提交，正式与 collector 共用准备路径。helper 临时 HOME/TMPDIR 退出后删除并核验；root 只接固定元数据，token 仅产品内存。
首次基线与旧证据边界见[Live 证据契约](docs/contracts/live-evidence.md#当前观察与认证cache-基线)。
三项SHA OK后仍须核对部署/采集/接收终态；拒绝诊断给出受控原因与阶段。
所有者审阅新包后只运行REVIEW中的run-g2.sh，输入一次sudo密码，脚本从入口内嵌字节冻结部署材料，
不让root读取用户可换链来源，再自动预配固定空cwd并完成G2。
普通部署不接管用户目录。更新既有冻结runtime可明确提供旧payload与manifest SHA，
构建单入口升级包，核旧字节后原样归档，保留账本与历史；新字节须所有者重新审阅。
首次升级的cutover会永久撤销旧资格，再采集新计划；root只追加收紧日志在helper失败时仍阻断，缺失或不支持则拒绝。
`--owner-closure` 可冻结集成演练：三次本人手输实际短ID、产品uid权限负例、helper失败持久性和恢复后再活；
实际新root字节及所有操作仍须所有者审阅执行，详见上述契约。
该站点采集器不提供模型、RPC、IPv4 出站或 observer 的能力证明；规则见 [Live 证据契约](docs/contracts/live-evidence.md#β-站点采集与封印部署)。

单次收口审阅包可用 `uv run --offline --locked python scripts/issue176_closure.py --help` 显式构建。
它复用与当前准入策略身份匹配的已部署冻结 runtime，输出待审 owner 工作流；构建不执行 sudo 或操作账本。
真实恢复会失效全部旧激活，成功出口要求所有者重新手动激活非空最终分项，详见
[Live 证据契约](docs/contracts/live-evidence.md#所有者单次收口审阅包)。
正式消费者按分项证据决定资格，站点分项激活不能代替模型／RPC等必需证据。
正式 Pi 准入在调用前按需刷新受保护观察；临时不可用拒绝本次并保留原成功快照和证据时点，
真实漂移继续收紧。doctor 只读同一结果；固定零参数特权入口的实际安装与现场核验仍由封印部署承担。
详见 [Live 当前观察契约](docs/contracts/live-evidence.md#当前观察与认证cache-基线)。

当前边界见 [Live 证据契约](docs/contracts/live-evidence.md)，后继工作与承接见[路线图](docs/roadmap.md#module-live)。

## Pi RPC

`paper_radar.llm` 提供冻结调用描述，`paper_radar.llm.rpc.run_call` 提供显式注入会话的
有界单次协议组件；管道组件接管已启动的进程，不提供默认生产启动器。
接口与支持范围见[RPC 契约](docs/contracts/pi-rpc.md)，架构决策见
[ADR-0026](docs/adr/0026-control-pi-through-a-bounded-rpc-adapter.md)。
`paper_radar.pi_execution` 提供固定安装保护、宿主专用 OAuth 刷新、独立 attempt 资源与
Landlock 受控会话工厂；不提供执行 CLI，不保存准入 passed。接口与权限见
[Pi 执行资源契约](docs/contracts/pi-execution.md)；认证与模型共用锚定用户 scope 和专用封印放置入口，模型领取前只准备阻塞封装；引导阶段撤权后才进入动态代码，exec-stop 核身份后才释放认证或 prompt。入口、AppArmor 策略和 resolver 视图须审字节部署并核实际加载身份，真实部署适用性仍需独立验证。独立测试范围见
[#140 独立组合台账](docs/verification/issue-140-pi-delivery.md)。现场隔离与固定 Pi 的剩余验收由 Live 统一承担；
产品准入证据未被接收时继续阻断。
带版本的六格登记、共享分项投影，以及独立受保护账本的接收、证据激活、不可逆撤销与恢复见
[Live evidence](docs/contracts/live-evidence.md)。所有者入口为 `paper-radar live-evidence receive/activate/revoke`，
`show` 查询回执，`show --plan-id <ID>` 查询批准计划；v2 同时展示 root 累计额度、失败链、熔断与下一动作。
固定零参数模型采集入口执行封印六格与四个 IPv4 对照，只写受保护完成历史／inbox，owner 仍独立 receive／逐格激活。新 Live 封印模式安装这些固定入口，详见[固定模型采集闭环](docs/contracts/live-evidence.md#固定模型采集闭环)。
封印安装器显式核对 anchor 的空执行数组，并提供仅针对已核、未执行 `resources` 中断的
新包 `recover` 替换；完整已核 resources 谱系按原史恢复，固定 native nft 在独立网络
namespace 预检及宿主 dry-run 通过后才替换旧资源，实际 level 由代际一致的双视图核验。
已安装升版从受保护原始来源继承部署时点；AppArmor 内核字节与无秘密 scope／exec 预检同样受封印约束。
条件与拒绝边界见同一契约；升版字节须所有者重新审阅部署，不继承旧策略资格。
Live 采集使用跨计划固定域的 40 次联网／40 次 prompt 预占，不退款；普通失败按三次／六轮规则停止，
安全失败首次停止。规则与续跑来源见 [v2 契约](docs/contracts/live-evidence.md#v2-采集额度失败类与续跑)。帮助纯本地。
activate 展示完整脱敏回执并要求手输短 ID；确认后由固定封印采集器刷新观察，审核内容相同才激活。
阅读可超过60秒，执行前观察仍受60秒时效约束；事实改变或能力到期继续拒绝，原期限不延长。
Screening 正式入口在刷新前、准备后和领取事务内读取同一分项权威；普通资格缺口只拒绝当次调用，
已知漂移或明确失败按受影响范围持久收紧。
Read 执行边界见[Read 执行契约](docs/contracts/read-execution.md)；受保护部署与实际证据激活由所有者完成。有限合成实验的适用范围见
[EXP-2 证据与承接](docs/verification/exp-2-pi-live-probe.md)，不据此授予生产执行。
真实执行接线的承接入口见[路线图承接索引](docs/roadmap.md#模块承接索引)。

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
有限尝试、租约、`test | pi_rpc` 来源的成功接收、显式 retry 与历史查询。
`pi_rpc` 的供给/安装与回执审计随备份恢复核验；这只证明持久事实一致性，
真实执行和兼容仍需 Live 验收。这是 Python 服务，不是 screening CLI。
value 通过 `register` 登记时由调用方提供语言事实，`register_feed_value` 则从 Feed
发现归属派生该事实。
接口与任务语义见[Screening 任务契约](docs/contracts/screening-tasks.md)，
派生入口见[Feed 原题名语言来源](docs/contracts/screening-tasks.md#feed-原题名语言来源)，
来源政策见[ADR-0035](docs/adr/0035-feed-derived-original-title-language-fact.md)。

Pi 一次执行已支持 models-v2 采样声明、共享受保护账本的三检查点准入、完整当前绑定、
受保护隔离启动、pi_rpc 权威成功与 Feed value 登记/恢复。缺少有效且人工激活的必需证据时拒绝；
合成对端通过不代表真实认证、参数或 RPC 兼容。见 [执行契约](docs/contracts/pi-execution.md#一次任务执行组合)。
后续产品入口与实验用途由 [B](docs/roadmap.md#module-b) 承接。

## JGR Feed 与元数据

服务 API 可显式选择 Wiley 主摘要规则 v2；旧调用与历史回放保留 v1。
用法与字段缺项/冲突规则见[摘要审计契约](docs/contracts/fixture-audit.md#摘要矩阵与显式运行105)。

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
