# PaperRadar

PaperRadar 是面向单个研究者的论文发现与研读流水线。当前仓库交付了工程入口、
研究边界、摘要层价值预测、复用可行性升级和筛选原因组合的公共验证，以及
四种公共契约各自的 `v1` 冻结快照、带全量预检的批量安全导出，以及逐份或整组
只读漂移检查；另已交付 Profile、模型、主题、三阶段提示词/契约、复用升级参数、正文提取和 Read 配置快照的显式迁移、检查、编译与历史加载。
现已开放四种单文件制品与完整 extraction 集合的不可变内容寻址存储和完整校验回读。
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

Pi 供给的官方下载使用 httpx；普通离线测试替换网络与外部程序，不依赖个人 Pi、Node、LLM 或文档解析器。

## 命令行帮助

依赖准备完成后，可从真实安装入口查看中文帮助：

```bash
uv run --offline --locked paper-radar --help
```

帮助命令只向标准输出写文本；它不读取配置或凭据，不访问网络或数据库，
不创建 `data/`、`reports/`、`logs/` 等业务目录，也不消耗自动处理配额。
当前注册 `contracts export/check`、`db upgrade`、`config check/compile/diff/snapshots list`
与 `backup create/verify`、会写入副本的 `restore verify`。
`pi supply prepare/verify/rebuild/list/show/export` 可准备、核验、联网重建、查询并导出项目独立 Pi 供给，
`activate` 显式切换每库唯一执行选择，`doctor --scope pi-supply` 只读核对显式快照与现场。
不注册尚未实现的业务命令。

## 数据库升级

A2 的 `a201_profile_snapshot`、A3 的 `a302_artifact_store` 可显式升级至当前
`a405_pi_cleanup_execution`。升级只追加内容对象/制品及供给材料、安装根、实例、检查、重建失败、激活、不可变清理计划、退役与逐项清理进展事实，
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
提示词仍为合成材料，Read 未就绪。当前没有 Pi RPC 执行器，配置层也不检查 Pi/Node、
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
提供规范字节、SHA-256 指纹、严格回放及安全比较。当前交付 boundary/value/extraction
与结构化 reuse 各自独立格式 1。boundary/value 使用精确题名、非空论文摘要、严格
布尔截断标记与各自配置投影引用；extraction 仅组合上游计算的原始 PDF 完整 SHA-256
与 extraction 投影，不读取 PDF 或运行 Docling，不接收论文元数据。配置缺项或占位
保持拒绝；无 adapter 的历史快照按已有配置完整性判断，指纹不证明 RPC 可执行。
value 输入可从明确匹配的历史快照派生同源 `ValuePredictionContext`，原题名语言由调用方
显式提供。结构化 reuse 消费冻结的有序摘录、source_snapshot 的 payload 成员内容哈希
与来源定位，不依赖 PDF 或 extraction 配置；从相同摘录派生 `ReuseAssessmentContext`。
载荷含敏感论文文本，不写终端或日志。接口、固定向量和证明边界见
[阶段输入契约](docs/contracts/stage-inputs.md)。PDF 来源 reuse 及独立 A5 验收
由后续工作包接入；本服务不调度任务或改写人工决定。

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
`<run_id>.a2-full.json` 完整 A2、`<run_id>.a3.json` 存储/恢复 A3 与
`<run_id>.a4.json` Pi 供给生命周期 A4 独立结论。六份主要文件共用本次 `run_id`，
不重复执行整套检查。只有本次 A1、完整 A2、A3 与 A4 都通过时返回 0；A2-01 独立保留，仍不决定整体通过。
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
仅依赖登记顺序或总测试退出码不能通过。阶段输入指纹、论文业务事实、attempt/lease、
共享资格/可见性、报告重建与任务续跑、doctor、Pi/Docling/Read 执行、真实来源与 NAS、
正式校准和自动精读仍未验收；A3 passed 不等于完整阶段 A 或阶段 B 通过。
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
等安全文件能力边界，能力不足继续安全拒绝。Windows 安全导出由
[#46](https://github.com/MeteoBoy4/PaperRadar/issues/46) 后续交付，本次未实现/未验证；
#46 不阻塞已裁定的本次平台范围，#36 保持 OPEN。
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
