# PaperRadar

PaperRadar 是面向单个研究者的论文发现与研读流水线。当前仓库交付了工程入口、
研究边界、摘要层价值预测、复用可行性升级和筛选原因组合的公共验证，以及
原四种公共契约和 Read 结构契约各自的 `v1` 冻结快照、带全量预检的批量安全导出，以及逐份或整组
只读漂移检查；另已交付 Profile、模型、主题、三阶段提示词/契约、复用升级参数、正文提取和 Read 配置快照的显式迁移、检查、编译与历史加载。
现已开放四种单文件制品与完整 extraction 集合的不可变内容寻址存储和完整校验回读。
已提供四类来源仲裁、人工字段修正、Feed 登记与发现的本地事实服务和只读 `paper show/trace`；
另已交付 boundary/value 的冻结任务、有限尝试、租约、成功接收、retry 与独立离线验收。
真实网络来源、模型执行和完整论文处理流水线尚未实现。

#93 已冻结 [Read 权威结构](docs/contracts/read-validation.md)，包含全部 18 个必填字段、
严格独立评分与 Read 自有价值词汇。#94 已交付原始 bytes 与只读可靠文本上下文的
公共校验、逐条数值诊断和带来源的警告视图；#95 已按字段接通受限证据矩阵，
#96 已交付同正文 reduce 允许集合，#97 已交付显式配置准入。
#98 已验证两份历史配置与四份候选原始字节的非空隔离恢复；固定消费上下文由测试
常量重建，范围见 [Read 恢复说明](docs/contracts/read-validation.md#恢复范围98)。
独立 A9 由 #99 推进，离线校验不授予生产 Read 或校准资格。

期刊身份与信誉集合也可版本化登记，校验 ISSN 与冲突，并从 SQLite 回放历史。
另可登记 Pi adapter 的三个独立选择、声明系统指令、资源哈希、推理档位与
固定调用策略；单快照可重建六阶段配置投影和校准基线，并只读比较已保存快照。

A8 已提供 [冻结调用描述与单次 RPC 协议](docs/contracts/pi-rpc.md)：从预算首次历史
语义与本次回执执行审计构造，仅支持 1.4.0 离线协议档案，系统指令与 user 消息分离。
boundary/value 完整候选经既有 A1/A7 同源接收，事件、消息副本、模型和用量有离线
边界证明。生产管道组件只包装已启动的独立进程组；Python 夹具已验证双管道背压、
超时、取消与整组回收。独立字节向量与合成协议测试不运行真实 Pi/模型；非空恢复与
独立 A8 验收仍按[逐项台账](docs/verification/a8-requirements.md)继续。Pi 强制追加的常量 cwd 例外
须在真实调用前由生产启动器票确认；当前不授予生产执行或校准资格。

## 环境与安装

项目支持 Python 3.12、3.13 和 3.14，开发环境由 `.python-version` 固定为 3.14，
并统一使用 `uv` 与已提交的 `uv.lock`。首次准备环境可以联网：

```bash
uv sync --locked
```

长时间测试前运行 `./scripts/dev-environment check`（可加 `--json`），只读检查解释器、
临时根隔离、有效容量、inode 与 pytest 残留；使用与退出码见 `--help`，
worktree 环境说明见[测试约定](docs/agents/testing.md#开发环境)。

离线验证运行可用 `./scripts/verification-status <run_id> [--runs-dir <目录>] [--json]`
只读查询；缺少控制方终态时不显示通过，历史结果与当前工作树适用性分别展示。
历史检查按已发布的记录格式解释，不随当前执行计划改变。
状态词表与终态记录格式见[状态查询契约](docs/contracts/verification-status.md)。

运行依赖为 Pydantic v2、Typer、PyYAML、SQLAlchemy 和 Alembic；开发工具为
pytest、Ruff、mypy 和 PyYAML 类型声明。
精确解析版本以 `uv.lock` 为唯一权威，避免依赖升级后在说明文档中保留过期副本。

CLI 的契约命令从权威 Pydantic 定义生成 Schema；纯 Python 公共验证入口使用锁定的
Pydantic v2 校验已实现的三种 Screening 输出及原因组合。冻结结构契约就绪不表示
后续业务流程已经就绪。

Pi 供给的官方下载使用 httpx；普通离线测试替换网络与外部程序，不依赖个人 Pi、Node、LLM 或文档解析器。

## 命令行帮助

依赖准备完成后，可从真实安装入口查看中文帮助：

```bash
uv run --offline --locked paper-radar --help
```

帮助命令只向标准输出写文本；它不读取配置或凭据，不访问网络或数据库，
不创建 `data/`、`reports/`、`logs/` 等业务目录，也不消耗自动处理配额。
当前注册 `contracts export/check`、`db upgrade`、`config check/compile/diff/snapshots list`
与 `backup create/verify`、会写入副本的 `restore verify`、只读 `paper show/trace`。
`pi supply prepare/verify/rebuild/list/show/export` 可准备、核验、联网重建、查询并导出项目独立 Pi 供给，
`activate` 显式切换每库唯一执行选择，`doctor --scope pi-supply` 只读核对显式快照与现场。
不注册尚未实现的业务命令。

## 数据库升级

A2 的 `a201_profile_snapshot`、A3 的 `a302_artifact_store` 可显式升级至当前
`a704_screening_retry`。论文切片追加 DOI 论文身份、四类来源观察、人工事件、发现历史、候选引用式修订与初始选择；Screening 切片追加冻结输入、预算、请求、领取尝试、租约、失败结算、boundary/value 成功制品及 retry 父链。既有升级只追加内容对象/制品及供给材料、安装根、实例、检查、重建失败、激活、不可变清理计划、退役与逐项清理进展事实，
全部 DDL 与 revision stamp 在一个 SQLite 事务内提交；
失败或进程中断完整回滚后可以重试。配置历史的 ID、原字节、创建时间、六投影和基线不变。
已知旧库上的 `config check/compile/diff/snapshots list` 会提示先执行升级，不自动修改库。
不在随包迁移图中的 revision 无法判断是较新版本还是损坏，须使用匹配程序检查。

升级前需要手工保护副本时，使用 SQLite backup API，确保目标文件尚不存在；不能只复制
活动主文件，因为已提交的事实可能仍在 WAL 中。以下命令完全离线，不打印配置正文：

```bash
uv run --offline --locked python - <<'PYTHON'
import sqlite3
from pathlib import Path
from urllib.parse import quote
source = Path("data/paperradar.sqlite3").resolve()
target = Path("data/pre-a3.sqlite3")
with target.open("xb"):
    pass
with sqlite3.connect(f"file:{quote(str(source))}?mode=ro", uri=True) as src:
    with sqlite3.connect(target) as dst:
        src.backup(dst)
PYTHON
uv run --offline --locked paper-radar db upgrade --database data/paperradar.sqlite3
```

重复 `db upgrade` 保持事实和身份不变，并将工作库设为 WAL。数据库路径与制品数据根
无需互相包含。下列备份命令创建含制品的完整批次；上述手工命令只保护数据库。

## 备份批次与校验

```bash
uv run --offline --locked paper-radar backup create \
  --database data/paperradar.sqlite3 --data-root data --output backups
uv run --offline --locked paper-radar backup verify backups/<backup-batch>
```

`<backup-batch>` 是已发布批次目录，不是运行配置快照 ID。创建要求源库已升级到当前
head；只读固定 SQLite 在线副本，再按其全部登记闭包复制不可变制品。固定之后的新提交
留给下一批，不扫描数据根复制孤立文件。output 不存在时按属主权限创建，staging 在
output 内；全部验证后原子不覆盖发布，包括空目录碰撞也拒绝。系统须支持 Linux
renameat2(RENAME_NOREPLACE)，不支持时受控失败。

批次包含数据库中已登记的配置原字节和全部登记制品；不包含 `config/` 树、
`settings.yaml`/selector、未登记草稿、`contracts/` 导出目录、reports/logs、认证或缓存。
**配置文件本身请用 git 保管**。终端只显示批次 ID、清单 SHA-256 和按种类汇总，
不输出配置、正文或模型响应。

批次数据库为 `journal_mode=DELETE` 的独立单文件，不依赖原 WAL/SHM；这使 verify
在成功和失败时都不改字节或目录条目。verify 全量核对 SHA-256、数据库 integrity/FK、
登记双向闭包及每份历史配置回放，不补文件、不迁移，原数据和配置根不可访问时仍可用。
批次移动时保留自身目录名。详见
[备份与隔离恢复 Contract](docs/contracts/backup-restore.md)。未验证 NAS 或全阶段 A。

## 隔离恢复

`restore verify` 会向 `--target` **写入完整副本**；只读检查请使用 `backup verify`。
目标父目录须预先存在，目标可以不存在或为非符号链接的空目录。命令在父目录临时创建
唯一隐藏 staging，复制全部登记闭包并完整验证后原子发布；拒绝非空目标、目标符号链接
及批次内部位置，不清空目录，也不读取原数据库、制品根或配置文件。
以下示例的批次名请替换为实际已发布目录名：

```bash
uv run --offline --locked paper-radar restore verify \
  backups/20261017T000000Z-1234abcd --target restored
uv run --offline --locked paper-radar config snapshots list \
  --database restored/database.sqlite3
```

恢复库保持与批次相同的 DELETE 单文件字节；历史配置 ID、原字节、创建时间、六投影与
校准基线不变，制品随新根解析。原配置/数据不可访问及移动恢复根后仍可查询和读取。
复制使用独立 inode，修改副本不会修改原批次。失败只尽力清理自己创建的 staging；
强杀残留由人工处理。原子发布附近中断可能已留下完整目标，请检查已有内容，向新的
空目标重试。成功只输出批次 ID、清单 SHA-256 与按 kind 汇总。

要把恢复副本作为工作库，另显式运行下面的命令使其恢复 WAL；head、历史身份和事实不变：

```bash
uv run --offline --locked paper-radar db upgrade --database restored/database.sqlite3
```

恢复不会自动升级、激活配置、启动任务、安装 Pi 或修改校准/自动精读门禁；当前也不
声称恢复尚未实现的报告。**配置文件本身请用 git 保管**，本轮不验证 NAS。

## 不可变制品存储

公共 `paper_radar.storage.artifacts.ArtifactStore` 可发布 `source_snapshot`、
`original_pdf`、`model_success_response`、`reference_tei` 四种单文件制品，每种恰含
`payload`。输入可分段；读取先完整校验登记身份与全部文件，再返回角色到原字节的映射。
相同内容重复发布保持原创建时间；跨种类共享内容对象。已登记内容缺失、损坏或位置不符
会受控失败，不从当前来源重建历史；根内符号链接一律拒绝。新建目录仅属主访问，文件只读。

存储成功只表示完整保存；来源接收、PDF 合法性与模型权威输出验证仍由上游负责。
当前不注册通用制品人工导入 CLI，不执行模型或 PDF 检查。`extraction` 通过
`publish_artifact` 一次提交 `manifest`、`document`、`reading`、`evidence_map` 四角色；
完整集合才登记，多个角色可共享字节。失败或中断后重试复用未登记文件；任一成员损坏
都会拒绝整个读取结果，不补写历史。存储不运行 Docling 或验证正文/evidence 业务语义。
身份向量、公共 API、错误码与迁移边界见
[制品存储 Contract](docs/contracts/artifact-store.md)。

## 运行配置快照

`db upgrade` 是唯一可初始化/升级工作数据库的命令（backup 只创建独立副本）；`config check` 只读，`config compile`
只打开已迁移的既有库。三个命令均要求明确路径：

```bash
uv run --offline --locked paper-radar db upgrade --database data/paperradar.sqlite3
uv run --offline --locked paper-radar config check \
  --settings examples/config/settings.yaml --database data/paperradar.sqlite3
uv run --offline --locked paper-radar config compile \
  --settings examples/config/settings.yaml --database data/paperradar.sqlite3
```

先创建数据库父目录，例如 `mkdir -p data`。示例是工程验收合成材料，不是正式
校准资料。当前可选六段式 Profile、单份三槽 models 文件、主题集合、boundary/value/reuse/reading 提示词、四份 A1 冻结契约及独立 Read v1 与复用升级参数。boundary、value、reuse、read 和 suggestion 各自报告配置就绪；value 需要已配置的主题集合，空集合和全部停用均合法。`examples/config/settings-value.yaml` 使用完整合成 Profile，演示两阶段均就绪；`settings-boundary.yaml` 演示仅 boundary 就绪；`settings-reuse.yaml` 演示缺 value/PDF/extraction 时 reuse 和 suggestion 配置就绪，触发集合默认仅 `{3}`、摘录顺序固定为 availability 优先；算法身份只接受受控 v1，不执行摘录选择或建议规则。原 `settings.yaml` 保留占位 Profile，展示未就绪原因。公共 Python 服务可从数据库加载旧快照；完整字段、声明版本规则、
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
旧示例未选择 `contracts.read`，因此保持 `not_ready` / `read_contract`；boundary 配置就绪。
新 `settings-read-ready.yaml` 显式选择 `contracts.read: v1`，配齐 Profile、reading 模型、
reading Prompt、reading adapter 和 chunking v1 后报告 Read 配置 `ready`。
两者都不执行分块或 Read，不接受手写替代 Schema，也不构成阶段 B 验收：

```bash
uv run --offline --locked paper-radar config compile \
  --settings examples/config/settings-read.yaml --database data/paperradar.sqlite3
uv run --offline --locked paper-radar config compile \
  --settings examples/config/settings-read-ready.yaml --database data/paperradar.sqlite3
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
提示词仍为合成材料，该示例未选择 Read 契约，Read 配置未就绪。配置层不检查 Pi/Node、
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

## 阶段输入

`paper_radar.stage_inputs` 从已验证运行配置快照与严格阶段事实构造不可变的阶段输入载荷，
提供规范字节、SHA-256 指纹、严格回放及安全比较。当前交付 boundary/value/extraction/reuse
各自独立格式 1，reuse 包含结构化、正文及其显式混合来源。boundary/value 使用精确题名、
非空论文摘要、严格
布尔截断标记与各自配置投影引用；extraction 仅组合上游计算的原始 PDF 完整 SHA-256
与 extraction 投影，不读取 PDF 或运行 Docling，不接收论文元数据。配置缺项或占位
保持拒绝；无 adapter 的历史快照按已有配置完整性判断，指纹不证明 RPC 可执行。
value 输入可从明确匹配的历史快照派生同源 `ValuePredictionContext`，原题名语言由调用方
显式提供；派生失败使用 `BuildReason`，载荷回放失败使用 `ReplayReason`。
reuse 消费冻结的有序摘录与来源定位：结构化来源绑定 source_snapshot 的 payload
成员内容哈希；正文来源从明确 extraction 输入绑定 reading/evidence_map 成员哈希，排除
manifest 审计变化，同次调用只允许一份一致正文。从相同摘录派生 `ReuseAssessmentContext`，
不读取当前 extraction 就绪状态或静默更换引用。
载荷含敏感论文文本，不写终端或日志。接口、固定向量和证明边界见
[阶段输入契约](docs/contracts/stage-inputs.md)。#53 已用真实非空备份、恢复历史快照与
重新取得的制品成员验证四阶段重建；不同 hashseed、cwd 和无序集合构造顺序保持身份，
纯构造、回放与比较不执行 I/O。独立复现命令见[离线证据说明](docs/verification/offline-evidence.md)。
独立 A5 验收由 #54 接入，固定绑定四阶段、回放、比较与隔离恢复能力。
A5 当时的 check-offline 输出七份主要文件，A6 注册时为八份主要文件、总十份 JSON；A7 注册时为九份主要文件、总十一份 JSON；A8 注册时为十份主要文件、总十二份 JSON；当前 A9 为十一份主要文件、总十三份 JSON，见[当前离线证据](docs/verification/offline-evidence.md)。另有实际 pytest 执行回执与控制方终态记录；
本服务不调度任务或改写人工决定，也不证明 PDF/正文的真实质量。

论文事实可通过 `PaperFacts(database).map_screening_inputs(snapshot_id=..., paper_id=...)`
直接映射 boundary/value 输入；历史重建改用 `version_id=..., revision_no=...`，并明确旧
`snapshot_id`。返回 `mapping_result` v1 的逐阶段输入、受控原因和完整 provenance；两阶段
配置就绪分别判断。查询只读、不读来源 blob、不生成任务或推导资格，不新增指纹 CLI。
普通映射不证明来源字节完整性，需由备份 verify 或显式 trace 核验；完整字段形状见
[论文事实 Contract](docs/contracts/paper-facts.md#8-当前查询历史重建与只读-cli)。

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
- `read`

例如一次导出历史 A1 的四份契约：

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
`contracts/screening/<契约名>/v1/`；Read 单独使用 `contracts/read/read/v1/`。
可用 `--contract read` 单选或加入混选，两处 area 均来自受控注册表。
写入前会预检全部既有目标；损坏、版本不一致
或同版本内容冲突不会产生任何新快照。发布阶段逐份安全落盘，不承诺跨快照事务：
若中途失败，预检时已经一致的项目标为“未改写”，故障前完整写入的项目标为
“已创建”，只有失败项和仍缺失的未处理项标为“未完成”；修复后用原命令重跑会
保持完整项不变并补齐缺失项。此命令不访问网络、数据库或模型，不消耗配额。

只读确认历史 A1 四份快照仍与当前权威定义一致：

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

Read 的单独只读检查为
`uv run --offline --locked paper-radar contracts check --contract read --version v1 --target contracts`。
完整离线计划仍只显式选择原四份；Read 由 A9 的独立结论内部显式检查，不静默扩大
A1 的历史证明范围。

## 完整离线验证

修改固定验收材料时，可先运行 `./scripts/audit-verification-scope`（支持 `--json`、
`--collect`），只读核对登记哈希、固定用例数及 scope 引用链，按报告顺序人工审查和
重绑。收集仅核对分母，不执行测试或写正式回执，不代表验收通过；详见
[维护入口](docs/verification/offline-evidence.md#固定-scope-维护审计60)。

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
`<run_id>.a2-full.json` 完整 A2、`<run_id>.a3.json` 存储/恢复 A3 与
`<run_id>.a4.json` Pi 供给生命周期 A4、`<run_id>.a5.json` 四阶段输入 A5 与
`<run_id>.a6.json` 论文事实 A6 与 `<run_id>.a7.json` Screening 任务 A7 与 `<run_id>.a8.json` RPC 离线协议/任务接线 A8、`<run_id>.a9.json` Read 离线校验/配置/恢复 A9 独立结论。
十一份主要文件共用本次 `run_id`，不重复执行整套检查。只有本次 A1、完整 A2、A3、A4、
A5、A6、A7、A8 与 A9 都通过时返回 0；A2-01 独立保留，仍不决定整体通过。
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
A3 另外固定覆盖单/多文件制品、真实迁移、WAL 备份、全量只读校验和隔离恢复；
它独立核对本次 A1/完整 A2 前置、回执整数计数、源码/材料哈希、运行身份和发布前绑定。
A4 另外绑定三份前置、真实生产格式、供给全生命周期、清理后导出与非空隔离恢复；
十项 capabilities 全部通过才声明完整 A4，live_install_verified/rpc_verified 恒 false。
要求归属见 [A4 规格对照](docs/verification/a4-requirements.md)。
A5 独立绑定 A1、完整 A2、A3，核对生产输入/投影格式、固定源码/向量与严格整数回执；
A4 仍决定整体通过，但不作为 A5 前置。七项 capabilities 共用整组状态，
stage_a_verified/live_verified/rpc_verified 恒 false，范围映射见
[独立 A5 结论](docs/verification/offline-evidence.md#a5-独立结论4754)。
A6 独立绑定同次 A1、完整 A2、A3、A5，A4 继续决定整体门禁。12 项能力逐项映射固定业务
用例和 #74 组合材料，核对真实临时迁移至随包 head、生产格式、固定源码及全量实际执行回执。
A5 历史 `paper_fact_mapping` 未覆盖项保留，新增映射证明属于 A6。A6 注册时正常运行另含
回执和终态，共十份 JSON；要求与未验证来源假设见[A6 规格对照](docs/verification/a6-requirements.md)。
A7 独立绑定同次 A1、完整 A2、A3、A5、A6，固定 boundary/value 任务、原权威严格 JSON、
真实 a704 migration、生产格式、源码/材料、用例分母与实际 pytest 回执；A4 仍为整体必需。
当前正常运行共十三份 JSON；缺失或篡改 terminal、少执行、跳过、身份漂移和中断均不能通过。
15 项能力与排除项见[A7 规格对照](docs/verification/a7-requirements.md)。
A8 另以 `.a8.json` 格式 1 直接核对同次 A1、完整 A2、A3、A5、A6、A7、实际原始字节和
固定用例回执；13 项离线能力、40 条故事及全部子票/裁决落点见
[A8 需求与绑定台账](docs/verification/a8-requirements.md)。A4 仍决定总门禁；
`rpc_verified/live_verified/stage_a_verified` 恒为 false，真实 Pi 与生产准入仍未验收。
A9 以 `.a9.json` 格式 1 直接核对同次 A1、完整 A2、A3、Read v1 磁盘检查、
实际规则身份、固定分母与真实回执；42 条故事、21 项决策、20 个测试面及四条评论
记录在[Read 覆盖台账](docs/contracts/read-validation.md#92-覆盖台账)，结论包含对应结构化指针。
A4–A8 仍 required，A9 不继承其通过状态。scope 不自哈希，但完整工作树身份和
登记审计仍保护其字节，自引用/循环持续拒绝。
仅依赖登记顺序或总测试退出码不能通过。Screening 的有限尝试、租约、显式 retry 与恢复
仅以离线 test 执行边界验收。Read/suggestion/report 指纹、完整资格/可见性、报告重建、
其他任务续跑、doctor、Pi/Docling/Read 执行、真实来源与 NAS、正式校准和自动精读仍未验收；
A3 或 A7 passed 均不等于完整阶段 A 或阶段 B 通过。
该目录不进入版本控制；格式、失败表示与使用方法见
[离线验证证据](docs/verification/offline-evidence.md)。

## Pi 固定供给

`pi supply prepare` 显式选择历史快照、adapter 槽与严格请求，固定官方材料、独立 Node
及其 bundled npm，在私有 staging 安装并执行无模型检查，完整树只读发布后原子登记。
`list/show` 只读回查材料、D5 与历史 install_check，不依赖本机 Pi、Node、平台或网络；
历史检查不等于现场仍可用。prepare 无需真实 Profile/模型，不激活、不调用模型、不替代 RPC/校准。
list 明示实例计数为历史登记、未核验现场；verify、doctor、activate 与使用句柄会核验当前现场。
`export` 同样只取已核验库材料，向 `tools/pi/<supply_id>/` 输出六个顶层文件与去重 D5 证据，
整组预检后不覆盖发布，同字节重试无操作；不导出内部派生锁或安装归档。
2026-10-18 用户裁决：本次 A4 接受导出所需的目录句柄、nofollow、硬链接不覆盖发布与 fsync
等安全文件能力边界，能力不足继续安全拒绝。#36 已关闭；
[#46](https://github.com/MeteoBoy4/PaperRadar/issues/46) 已以 NOT_PLANNED 关闭，
Windows 安全导出当前无交付计划，未实现/未验证 Windows 后端。
`tools/pi/` 可提交版本控制，`.tools/pi/` 是被 Git 忽略的安装树，两者分开。
`verify` 逐实例全树检查并探测 Node/npm/Pi，只追加检查事实；任一失败返回 2。
`rebuild` 从库内冻结材料重新联网取得固定大包，要求原预期树、工具链与 libc 完全一致，
成功新增随机实例和检查，失败另记供给级审计，旧坏实例保持不变；不重取小材料，不支持脱网恢复。
`activate` 要求所给快照全部已选槽 Pi 版本一致且匹配，选最近通过并现场完好的实例；
只做全树哈希，不启动程序，不更改配置、预算或校准门禁。
执行器通过 `use_install(database, snapshot_reference)` 领取固定入口及共享 flock 句柄，
verify 子进程经 pass_fds 继承保护；父退出而子仍持 fd 时仍不能清理。
`doctor --scope pi-supply` 必须显式选择快照，只读显示当前匹配、D5 原文、历史现场、在途保护与保留计数；
缺少或无法安全读取锁时如实显示 unknown 并保守保护，不创建锁或使用记录。
当前实例保护 unknown、供给缺项/损坏/超过四棵时返回2，0仅代表此scope通过；
历史实例 unknown 独立披露，不否决已显式激活的新当前实例。Profile/模型/Read缺项、
RPC/真实模型/生产隔离/校准/自动精读未验证分别披露，不因此伪称全项目就绪。

```bash
uv run --offline --locked paper-radar pi supply prepare \
  --database data/paperradar.sqlite3 --snapshot <id> --adapter-slot screening \
  --request supply.json --install-root .tools/pi --data-root data \
  --config-root config --material-root tools/pi
uv run --offline --locked paper-radar pi supply list --database data/paperradar.sqlite3
uv run --offline --locked paper-radar pi supply export <supply_id> \
  --database data/paperradar.sqlite3 --target tools/pi
uv run --offline --locked paper-radar pi supply verify <supply_id> --database data/paperradar.sqlite3
uv run --offline --locked paper-radar pi supply rebuild <supply_id> \
  --database data/paperradar.sqlite3 --install-root .tools/pi --data-root data \
  --config-root config --material-root tools/pi
```

执行选择和诊断：

```bash
uv run --offline --locked paper-radar pi supply activate <supply_id> \
  --database data/paperradar.sqlite3 --snapshot <id>
uv run --offline --locked paper-radar doctor --scope pi-supply \
  --database data/paperradar.sqlite3 --snapshot <id>
```

请求必须填写精确 Node/npm、Node 官方摘要、Linux x86_64/glibc 及 D5 三态/依据/证据。
证据路径相对请求所在目录，拒绝绝对路径、`..` 或链接解析越界；show/doctor 对
may_change/unknown 明示需要后续相关语义评估，安装检查不代表校准兼容。
安装根与 data/config/materials 根互不包含；首次空根绑定本库，不支持网络文件系统。
发布协调使用数据库旁 `<database>.pi-supply.lock` 及安装根内 `.root.lock`、
`.prepare-<material_key>.lock`；它们不是事实源、备份或清理对象，关闭释放、不删除锁文件。
普通重复材料要求 rebuild，改变 D5 也不能重冻；同时开始的同请求只登记一个实例。
实际下载/进程实现已存在，普通测试仅用网络/程序 fake，真实 Pi 机制记录见
[1.3.0 spike](docs/research/pi-1.3.0-supply-spike.md)，它不是项目 live 供给验收。
完整字段、固定来源、逐包完整性边界、树身份及故障恢复见
[Pi 供给 Contract](docs/contracts/pi-supply.md)。安装树 `.tools/` 不提交 Git。

供给小材料随数据库备份，backup format 仍为 1，verify/restore 重验供给与 D5 引用闭包。
head gate 继续严格匹配：旧 a302 批次先 checkout 匹配的 A3 程序 verify/restore，
再切回新程序执行 `db upgrade`，随后用新程序重做备份。恢复不会安装或新增激活；原实例完好时可现场核验后继续使用，
原根缺失时请 rebuild 到新根后显式 activate。活动恢复副本共用原根时，旧副本退役前不得清理。

安装清理先保存可审阅计划，再用完整计划 ID 显式执行：

```bash
uv run --offline --locked paper-radar pi supply gc --dry-run \
  --database data/paperradar.sqlite3 --data-root data \
  --config-root config --material-root tools/pi
uv run --offline --locked paper-radar pi supply show-plan <完整plan_id> \
  --database data/paperradar.sqlite3
```

`--dry-run` **保存计划但不删除**；窗口全库跨供给按实例去重，当前、在途、未知保护和各范围最近通过均保留。
计划输出实际身份、保护理由和真实占用/回收估算，未知残留需人工处理，超限不自动删树。
执行只接受保存的计划 ID，不接受路径、glob 或 force：

```bash
uv run --offline --locked paper-radar pi supply gc --execute <完整plan_id> \
  --database data/paperradar.sqlite3
```

安全事实、根归属、保护或实际树变化必须重新生成计划。执行在非阻塞排他锁下先永久退役，
再不覆盖移入 `.trash/<install_id>` 后删除；`show-plan` 同时回查 run_id 与逐项结果。
失败或强杀不恢复可用性；重新 `gc --dry-run` 单列已退役待删，再显式执行新计划。
已完成身份的重现路径、未知 staging/树/trash 均需人工处理。恢复活动副本共用原根时，旧副本退役前不得执行清理。
安装锁缺失不补建，请 rebuild 新实例；只恢复删除所需目录权限，不改变普通文件或树外硬链接权限。
供给、D5、检查、激活与清理历史随数据库备份；不删除业务制品、blob、材料或其他安装。
清理单项核验错误归因于实际候选；库级前置阻断整组保留 not_run 并原子追加原因，
退役提交后中断依据实际进展记录，已完成项不回退为失败。旧计划与执行历史仍可回放。
计划原字节随备份恢复，后来的选择变化不改写历史。详见 [清理计划 Contract](docs/contracts/pi-supply.md#不可变安装清理计划)。

## 论文事实与 Feed 发现的本地查询

```bash
uv run --offline --locked paper-radar paper show PAPER_ID --database data/paperradar.sqlite3
uv run --offline --locked paper-radar paper trace PAPER_ID --database data/paperradar.sqlite3 \
  --data-root data --verify-source-bytes --json
```

`paper` 只读既有库，不创建目录、不调用模型，仅覆盖论文事实，尚未计算完整任务资格。
默认中文文本显示原题名、身份、当前版本选择事件/原因/时间及来源摘要；`--json` 提供受控历史结构。
摘要默认隐藏，`--show-abstract` 才展开；来源字节核验不转储原始响应或 item。
Python 公共写边界是 `paper_radar.papers.PaperFacts.submit`，只接有界原始 bytes、严格字段与
必填 `interpretation="complete"` 声明。题名/摘要必须为已解析文本；数学比较可接受，`List<String>`、`Array<int>` 等歧义标签形状受控拒绝，详见[文本输入边界](docs/contracts/paper-facts.md#51-文本规范形式-v1n1)。`register_feed(url)` 按数据库唯一规范 URL 登记 Feed；
Feed 输入要求真实 `feed_id/entry_id`、`payload_scope="single_item"`，允许 `doi=None`。
同 Feed 条目内容变化保持版本关联；同 DOI 跨 Feed 复用版本；逐字段按人工修正 > 出版者 > 对应 DOI 注册机构 > Feed 仲裁。
注册机构查询 DOI 必须一致；普通字段入口明确既有版本，权威关系路径可先保留尚无端点的依据；不联网推断真实注册机构。
`correct({version_id, request_id, actor, reason, fields})` 追加版本内幂等人工修正，只覆盖提供的非空字段，
按原子事件次序选择最新人工值；没有撤销或清空入口。修正不随当前版本升级迁移。
`revision(version_id, revision_no)` 读取完整历史状态及来源依据，trace 展示获选与未选候选和全部修订。
`relations=({kind, source_doi, target_doi, locator}, ...)` 仅接受出版者/注册机构的预印本→正式版关系；
双向别名归一同一事实，原始书写和来源断言保留；未登记 DOI 也必须在全部关系中保持同一端点类别，矛盾输入或历史受控拒绝。关系本身不创建版本；真实正式版到达时原子升级当前，
缺摘要不从预印本补入。同级保持既有选择，本次 DOI 涉及既有跨 Paper 关系时返回 retained/requires_merge 成功提示，优先于 not_retained；它不表示新增材料，材料保留另由 response_bytes_retained 表达，不自动合并。
trace 展示端点尚未出现、等待合并、已生效三态及真实选择历史。
当前不开放生产写入 CLI、抓取适配器或 Feed 配置；只读阶段输入映射见前述公共服务。
本机备份在完整副本上统一校验四类来源、人工请求、版本选择与关系证据。活跃 WAL 的组合库
在禁止访问原数据/配置/备份源后独立恢复、再次搬迁；新进程仅凭 ID、修订、快照引用和预期哈希，
从恢复库候选重建历史 boundary/value 输入。有/无摘要的正式升级、旧预印本及从未获选版本均保留。
`--verify-source-bytes` 默认关闭，显式开启须同时提供 `--data-root`；遗漏按参数错误退出 2。开启增加只读 blob I/O，包含仅关系材料，失败不输出原响应；缺库、未初始化或旧 revision 保留存储原因与迁移指引。
A6 独立结论覆盖本地论文事实及隔离历史重建，仍不表示阶段 A、live、RPC、Docling/NAS 或任务续跑已验收。
**阶段 C 真实 Feed 接入前必须补齐强冲突观察持久化和 parser 升级固定样本回归，
此前不得将本地拒绝路径直接作为生产写入。**详见[论文事实 Contract](docs/contracts/paper-facts.md)。

A7 的 D1–D4 裁决和公共任务目标见[Screening 任务 Contract](docs/contracts/screening-tasks.md)
及[A7 规格对照与绑定台账](docs/verification/a7-requirements.md)。#77 已在原权威验证器
收紧重复 JSON 键和非有限常量；#78–#79 已交付任务登记、冻结回放、两次预算和租约，
boundary/value 筛选制品接收与三值适用性由 #80/#81 交付，#82 交付显式 retry、共享版本化查询与父链恢复；#83 补齐新进程隔离完整历史恢复，
#84 将这些能力注册为独立必需 A7 验收组。A7 暂不提供 screening CLI 或 paper trace 组合；真实 value 任务前
必须先裁决原题名语言事实的生产来源。

### Screening 任务登记、有限尝试与两阶段成功（A7-02 至 A7-08）

公共 `paper_radar.screening_tasks.ScreeningTasks` 已支持用现有论文和明确历史配置快照
登记 boundary/value 请求，保存规范输入、独立预算范围和精确回执，并在备份恢复后回放。
value 的原题名语言事实必须显式提供；登记不会调用模型。以请求回执领取时按同一
历史配置快照复核当前指纹，原子占用每代至多两次预算并建立 600 秒租约；时间统一注入。
可显式续租、提交封闭失败和回收过期尝试，安全只读状态区分 lease_expired 与失败终态。
到期但未结算的持有者仍可续租或提交，回收后旧凭据失权；没有后台自动回收。
一次尝试驱动仅有可替换 test 执行边界，接收封闭失败或 boundary/value 原始成功候选；没有默认执行者或产品 CLI。
当前数据库 head 为 a704_screening_retry，备份恢复保存已占次数和租约且不自动执行。
两次预算只保证各库连续历史，回退旧备份不能追回其后丢失的尝试。
副本按注入时钟解释绝对 UTC 租约；时钟偏差只改变结算时机，回收不退预算。
旧 revision 批次须由匹配旧程序恢复再显式升级；当前 A1/A5 规则收紧也可能使旧备份验证失败。
boundary/value 原始成功候选经唯一权威校验，原字节由 A3 保留；成功制品和登记时缓存命中回执不可变。
显式 snapshot 的查询派生 current/historical/undeterminable，映射失败保留 PaperReason；
同文本跨版本仍适用。显式内部消费才返回输出与审计，test 来源不能进入生产建议或校准。
value 从预算首次冻结的历史 snapshot、A5 严格回放和语言事实重建 A1 上下文，
当前主题/模型文件变化或原目录不可访问均不替代历史接收依据；两阶段成功互不依赖。
显式 `retry` 仅追加唯一后继，`query` 返回 task_query_result v1 的安全历史与当前失败集合；
旧回执精确重放不随最新代际改变。独立 A7 结论只证明这些离线任务能力；真实模型执行仍待后续切片。
API、隐私与语义闭包见[Screening 任务 Contract](docs/contracts/screening-tasks.md)，
规格对照与重绑责任见[A7 requirements](docs/verification/a7-requirements.md)。

Fixture 注册：`paper-radar fixture register fixtures/a10/historical-v1.json --database data/paper-radar.sqlite3 --data-root data` 显式登记历史声明；`fixture check/list/show` 只读核查原字节与历史。另支持 `fixture register pdf-request.json --pdf-file sample.pdf` 登记本机字节、`--backend` 单独追加绑定该 PDF 的期望、`fixture check RECORD_ID --pdf --data-root data` 核查证据。替换保留旧字节和期望，新 PDF 不继承旧 backend 结果。只证明声明/字节登记与恢复，不代表真实四刊审计或 Docling 通过。详见 [fixture 与摘要审计 Contract](docs/contracts/fixture-audit.md)。

来源取得（#103）：公共服务先冻结计划，再以有界 HTTP/通道接口取得并保存安全执行事实；`paper-radar audit list/show --database ... --json` 只读查询。默认只交付 http，其他通道显示未安装；显式 run 已由 #105 接通，resume/replay 待 #106；不代表真实来源审计已执行。

固定选样（#104）：公共服务按四刊原位次冻结前 N 个显式 journal-article 候选，保留未知/冲突/重复/不足和暂停历史；`audit show` 可只读查看成员依据。显式继续保持原 Feed/位次，摘要成败不影响成员。当前仍未执行四刊 live；摘要矩阵由 #105 交付，完整恢复继续由后续票收口。

摘要矩阵（#105）：`paper-radar audit run --database DB --data-root ROOT --contact-email EMAIL --count 5 --json` 显式固定选样并执行适用路线；联系邮箱只用于请求标识，不保存。复用选样响应及原取得时间，题名/摘要分别调用 A6 仲裁；普通 show 只输出哈希、定位、截断信号及真实分母。原摘要通过显式服务 `read_audit_text` 读取。http 与未安装的适用渲染通道分列，official_api/repository 无适用目标；doiRA 不进入摘要命中分母。complete 只表示终态齐备，即使不足样本也不表示长期稳定或生产就绪。本票验证离线子集和基本恢复；完整门禁留 #108，不执行 live。
