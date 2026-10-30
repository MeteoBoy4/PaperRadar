# 自包含备份批次 Contract v1

`backup create` 创建自包含批次，`backup verify` 只读校验已发布批次，
`restore verify` 向隔离目标写入并校验完整副本。范围包括已登记配置、全部制品及
[已实现组件的事实闭包](#组件事实闭包)，不是 NAS 或业务执行恢复。
备份服务组合 storage/config 及业务公共服务，不增加 `backup_runs`，不写源执行记录。

## 公开边界与使用

```bash
uv run --offline --locked paper-radar backup create \
  --database data/paperradar.sqlite3 --data-root data --output backups
uv run --offline --locked paper-radar backup verify backups/<backup-batch>
uv run --offline --locked paper-radar restore verify backups/<backup-batch> --target restored
```

`<backup-batch>` 是已发布批次目录，不是运行配置快照 ID。公共 Python 服务为
`paper_radar.backup.create_backup(database, data_root, output)` 与
`verify_backup(batch_dir)`，均返回不可变 `BackupResult(batch_dir, manifest_sha256, manifest)`。
路径不是身份，结果的 batch_dir 为绝对路径；清单不保存绝对源位置。
`verify_contents(root, manifest)` 只负责同一套完整内容解释，不判定根 basename；
`copy_verified_contents(result, destination)` 重新校验来源后向既有空私有 staging
分段复制独立字节并重新校验，不发布目标。它们供恢复服务组合，不是额外产品命令。

create 只接受当前 head；已知祖先指向显式 `db upgrade`，未知/未来或安装包迁移图异常拒绝。
源库通过 SQLite `mode=ro` 读取，不 checkpoint 或升级源库。活动 WAL 的临时协调文件
由 SQLite 管理；不把源侧 WAL/SHM 的存在作为备份成员或业务事实变化。
数据库与数据根不必互相包含。output 不存在时按 0700 递归创建所需目录，存在时必须
为可用目录；数据根与 output 根本身可为符号链接，先各解析一次。
只拒绝 output 位于本根 `blobs`/`tmp` 受控子树，允许数据根内其他安全位置。

## 固定布局、身份与清单

批次 ID 固定为 `YYYYMMDDTHHMMSSZ-<8位密码学随机小写hex>`，例如
`20261017T000000Z-1234abcd`。审计时间固定 UTC ISO 8601 秒精度
`2026-10-17T00:00:00Z`；ID 的时间部分只用于排序，不与审计时间作相等核对，时间不参与完整性信任。
同秒碰撞按位置占用失败，不覆盖任何既有条目，包括空目录和别人的 staging。

```text
<output>/
  .staging-<batch-id>/             # 仅本次创建的未发布目录
  <batch-id>/
    manifest.json
    database.sqlite3
    blobs/sha256/<前2>/<64位SHA-256>
```

目录只有清单、列出的成员及其必要父目录；空多余目录、杂散文件、符号链接、特殊文件、
WAL/SHM/journal、嵌套 staging 一律拒绝。批次根及根内任何路径组件符号链接均拒绝。
所有新建目录 0700；数据库和清单 0600，副本 blob 0400。verify 要求根与内部目录没有
组／其他用户权限，blob 恰为 0400；不把数据库／清单的 0600 创建权限作为精确模式校验项。
源 blob 沿用 [ArtifactStore 的只读约束](artifact-store.md#路径权限与发布)，
允许 0444 等无写位权限，复制时规范化为 0400。
复制不用硬链接，恢复／备份不与来源共享文件 inode。防护范围是误配置、登记损坏与普通并发碰撞，
不包括同机恶意并发替换的 openat 级防护。

清单版本为整数 1，布尔不是整数。UTF-8 JSON、键排序、紧凑 `,`/`:`、
`ensure_ascii=False`、恰有一个结尾换行；拒绝未知字段、重复 JSON 键与非规范字节。
哈希使用完整 64 位小写 SHA-256。清单不自哈希，对外 SHA-256 是最终完整清单字节的哈希。
字段固定如下：

| 字段 | 格式与责任 |
| --- | --- |
| format_version | 1 |
| batch_id / created_at | 上述 ID 与 UTC 审计时间，目录名须等于 batch_id |
| database_revision | 显式支持 `feed06_language_provenance`，且须等于随包唯一 head；不动态接受未来 head |
| artifact_format_version / blob_layout_version | 各为整数 1 |
| database | 恰有 path=`database.sqlite3`、sha256、非负整数 size_bytes |
| blobs | 全部且去重的 FileEntry(path,sha256,size_bytes)，按 SHA-256 升序；path 必须等于 blobs/sha256/<前2>/<哈希> |
| artifacts | 全部制品，按 artifact_id 升序；恰有 artifact_id、kind、format_version、members、created_at；成员、种类和身份按[制品 Contract](artifact-store.md#身份字段与固定词表)校验，成员按 Unicode role 升序；created_at 须为带时区时间 |
| snapshot_ids | 全部运行配置快照 ID，唯一且升序；逐个由公共 load 完整回放 |
| counts | blobs、artifacts、config_snapshots、blob_bytes、by_kind；均与实际登记重算匹配 |
| counts.by_kind | 每种实际 kind 的 artifacts、members、size_bytes；字节按每个角色引用计数，允许共享对象重复计入不同用途；blob_bytes 是去重后的物理内容字节 |
| code | package_version、migration_revision、backup_format_version、artifact_format_version、blob_layout_version、sqlite_version、git_commit；格式/revision 与清单一致，git_commit 固定 null |

清单不保存源路径、主机名、用户名、配置正文、Profile、Prompt、模型响应或凭据。
这不表示整个批次没有敏感内容：数据库保留已登记配置原字节与历史审计位置，blob 包含已登记业务原文；
批次不提供加密或签名，清单哈希不是来源认证。
包版本通过已安装 distribution 元数据读取，revision 通过随包迁移图读取，不依赖 Git
或仓库。wheel 安装环境与 editable 环境遵守相同规则。

## 一致性与发布

先调用 SQLite 在线 backup 固定独立副本，再从副本公共登记接口推导全部制品、成员与
内容对象闭包，不从活动库另读清单、不递归扫描数据根猜测事实。副本切换
`journal_mode=DELETE` 并关闭、fsync 后才计算数据库哈希；这表示独立单文件，避免 WAL
头副本被只读公共 API 打开时创建 -wal/-shm。大文件全量哈希与复制均按 1 MiB 分段。
先 `verified_blob_path` 完整核验源对象，复制时再次哈希，再独立校验整个 staging。
业务来源字节的语义解析只在全部成员已复制的 staging 上进行，不从活动源 blob 解析业务事实。

创建和 verify 使用同一规则：精确目录集合、每个文件存在／长度／完整 SHA-256、数据库
integrity_check 与 foreign_key_check、DELETE 文件头、支持格式/head、清单和登记双向一致、
所有配置快照经公共 load 语义回放及下述组件闭包校验。list 发现本身不代替完整回放。
任何缺失、损坏或漏列不补写。只接受已发布名字，完整但未发布的 staging 也拒绝；
移动批次须保留自己的 basename。verify 成功和失败都不写批次、不迁移、不读取原数据
或配置树，批次字节与目录条目不变化。

全部通过后，同文件系统原子不覆盖目录发布；当前使用 Linux
`renameat2(RENAME_NOREPLACE)`，文件系统／系统不支持时明确失败，不降级为可覆盖 rename。
数据库、文件与目录发布前持久化，发布后同步 output 目录。可捕获失败只尽力清理本次
独占创建的 staging；强杀残留由人工处理，不扫描清理其他目录。原子提交点前失败不产生
完成批次；原子发布已经发生后的中断或目录 fsync 失败可能留下完整批次，须重新 verify，
不能从缺少终端成功输出推断提交是否发生。

无需锁整个存储根的依据是：文件先发布、登记后提交、blob 不可变且当前无制品删除。
固定副本已经登记的文件在提交前已存在；固定之后的新提交属于以后批次。
该论证不覆盖 GC／并发删除，不把未来删除能力纳入当前并发安全保证；
存储前置见[制品存储契约](artifact-store.md#路径权限与发布)。

批次包含数据库随历史保留的已登记配置原字节；不包含 config/ 树、settings.yaml 与
selector、未登记草稿、contracts/ 导出目录、reports、logs、缓存、认证和孤立文件。
**配置文件本身请用 git 保管**。完整已登记但未被业务引用的制品仍纳入批次，
不因没有业务引用判坏，不凭其存在补出成功事实，也不自动清理。

## 结果与受控原因

成功退出 0，只输出批次 ID、清单 SHA-256、按 kind 的数量与字节汇总，不逐条列 artifact ID。
参数／业务错误退出 2，中断非零；不联网、不调用模型、不消耗自动配额。
CLI 参数脱敏，帮助和错误指引为中文，I/O 服务延迟加载；帮助不读配置、凭据或数据库。
错误不回显输入、原始异常或内容，`BackupError.reason` 固定如下，各有中文下一步指引：

| reason | 原因与下一步 |
| --- | --- |
| batch_unavailable | 批次不可用，检查位置／权限 |
| not_published | 非完成批次或目录 ID 不符，选择已发布目录 |
| invalid_manifest | 清单无效／与登记不符，保留原批次检查 |
| unsupported_format | 格式不支持，使用匹配程序 |
| unsupported_revision | revision 不支持，使用匹配程序；不原地升级备份 |
| upgrade_required | 创建源为已知旧库，先显式 db upgrade |
| unsafe_path | 符号链接／路径／权限不安全，检查受控目录 |
| unexpected_entry | 出现清单外文件或目录，保留批次检查 |
| file_missing | 成员缺失，检查完整批次，不补写 |
| file_corrupt | 字节／长度／blob 权限不符，检查保护副本 |
| database_invalid | SQLite 完整性／外键／单文件模式等校验失败，检查数据库 |
| registration_invalid | 制品登记或业务事实闭包损坏，检查来源或保护副本 |
| config_invalid | 历史配置无法完整回放，检查配置登记 |
| supply_invalid | 固定供给事实无法完整回放，检查材料及 D5 引用；不安装或联网补齐 |
| output_invalid | output 不可用或位于受控子树，选择可写安全目录 |
| batch_exists | 位置冲突，包括既有空目录；重新创建新批次 |
| copy_failed | I/O／空间等复制失败，排除故障重试 |
| publication_failed | 原子发布不可用，检查同文件系统和系统支持 |
| interrupted | 操作中断，重新创建／校验，不继承旧成功 |

## 隔离恢复

`paper_radar.backup.restore_backup(batch_dir, target)` 只消费已发布批次，返回不可变
`RestoreResult(target_dir, manifest_sha256, manifest)`；target_dir 是绝对位置，不是身份。
目标根可以整体移动，成员仍按新根解析；恢复目标无需沿用批次名。
`RestoreError.reason` 复用下表与原 BackupReason，CLI 错误统一为中文脱敏原因，不回显
路径、原始异常、配置、Prompt、正文、模型结果或凭据。

源批次先经 `verify_backup` 严格验证，再由 `copy_verified_contents` 重新核对源并复制
数据库、全部登记 blob 和原清单，使用同一 `verify_contents` 规则完整校验副本；不维护
第二套清单／配置／制品解释器，不读取原数据或配置根，不补写缺项。完整但未发布的 staging、
改名批次、损坏和任何清单外条目都拒绝。复制使用独立 inode，不以硬链接依赖源字节。

目标可以不存在，或为非符号链接的空目录；拒绝普通文件、非空目录、目标自身符号链接
（含断链）、与批次相同或位于批次内部的位置。重叠检查仅针对批次，清单不加绝对源
位置，也不探测活动数据目录。目标父路径解析一次，**父目录必须预先存在**，不存在时
报 parent_unavailable，不创建任何层级。父目录已有权限不改写；所有本次新目录 0700，
数据库／清单 0600、blob 0400。

在目标父目录创建唯一 `.restore-staging-<随机名>` 同级目录，完整复制并验证后用 POSIX
`rename` 原子发布。允许原子替换空目标目录；发布前重新检查目标，且最终 rename 本身
拒绝被并发写成非空的目录，因此不会递归清空或覆盖用户数据。须支持的是 staging 与目标
之间的同文件系统重命名；源批次可在另一文件系统，来源字节经复制进入 staging。
发布失败受控，不降级为逐文件发布；发布后 fsync 父目录。

失败或中断不生成成功恢复结论；只尽力清理本次独占创建的 staging，不清理别人的
staging，也不扫描 GC。强杀在发布前发生时残留由人工处理；若与原子提交同时或之后
发生（包括发布后父目录 fsync 失败），可能已有完整已验证的目标，不能从缺少终端成功输出
推断发布未发生。目标已有内容时请保留检查，向合适的新空目标重试，不通过清空目录绕过保护。

恢复库与批次库原字节完全一致，保持 `journal_mode=DELETE`；list/diff/完整 ID load
及制品读取不会自动迁移、重编译、激活快照或启动任务。历史 ID、配置原字节、创建
时间、六投影和校准基线保持不变。阶段输入的历史重建由
[阶段输入契约](stage-inputs.md#隔离恢复跨进程与后续消费者义务)定义，不把内存旧成员哈希
或测试消费上下文当作备份成员。要把副本作为工作库，另显式运行：

```bash
uv run --offline --locked paper-radar db upgrade --database restored/database.sqlite3
```

此操作在当前 head 上不改 revision，恢复 WAL；事实与身份不变，数据库物理字节可能变化。
原备份批次始终独立保留 DELETE 模式。恢复不安装 Pi、不续跑或回收任务、不修改校准或自动精读门禁。

| RestoreReason | 原因与下一步 |
| --- | --- |
| target_unavailable | 目标不可用、为文件或链接；选择不存在位置或普通空目录 |
| target_not_empty | 目标非空或发布时被占用；保留已有内容，选择新目标 |
| target_overlap | 目标与批次相同或位于其内部；选择批次以外的位置 |
| parent_unavailable | 父目录不存在或不可用；先创建可写父目录 |
| restore_copy_failed | 复制／空间／权限失败；排除原因后向合适空目标重试 |
| restore_publication_failed | 原子目录发布失败；检查文件系统和目标状态 |
| restore_interrupted | 操作中断；检查目标与本次残留，不能继承旧成功 |

批次错误保留原 BackupReason（如 file_missing、file_corrupt、unexpected_entry），不以
一个通用恢复错误抹掉原因。成功退出 0；参数／业务失败退出 2，中断非零。成功输出与
backup verify 一样只给批次 ID、清单 SHA-256 及按 kind 汇总，不逐条输出制品或研究内容。
帮助直接说明“写入完整副本”和父目录 staging；帮助无外部 I/O，不依赖配置、凭据或数据库。

<a id="pi-供给事实与旧-revision-批次"></a>

## 版本准入与旧批次

`BACKUP_DATABASE_REVISION` 固定支持 `feed06_language_provenance`，且要求与随包唯一 head
一致。format 1 不表示任意 revision 兼容：verify／restore 对所有旧 revision（包括 a302、
a405、a704、a1001 及 feed01–feed05）返回 `unsupported_revision`，不在批次内部迁移。
保留原批次，用匹配该 revision 的旧程序先 verify／restore，再切回当前程序，对恢复的
活动副本显式 `db upgrade`，随后创建新批次；不得修改原清单 revision 绕过准入。
即使 revision 相同，当前程序也按当前配置、阶段输入和输出权威规则重验历史事实；
规则收紧可能让旧程序曾通过的批次失败，不承诺无限跨版本验证。

<a id="组合论文事实的语义闭包"></a>
<a id="a7-02-登记事实闭包"></a>
<a id="a7-03-尝试租约与失败闭包"></a>
<a id="a7-06-retry-链闭包"></a>
<a id="a7-07-隔离组合恢复与版本边界"></a>

## 组件事实闭包

备份固定副本的公共登记回放之后、manifest 反查之前，`verify_contents` 调用
`FixtureAudit.validate_all()` 和 `FeedPipeline.validate_all()`；后者组合 PaperFacts、
ScreeningTasks、JGRFeed、JGRMetadata 及组合登记依据的校验。所有来源语义在副本上校验，
外层数据库／清单重哈希不能绕过这些检查；拒绝不回写源库、不修复批次、不发布错误恢复目标。
组件详细格式与规则由下列 Contract 唯一定义：

| 组件 | 备份／恢复的组合保证 | 详细规则 |
| --- | --- | --- |
| 配置 | 全部历史快照经公共 load 完整回放，不依赖当前配置树 | [运行配置](runtime-config.md)、[投影与基线](config-projections.md) |
| 供给 | 数据库内材料、D5、实例／检查／失败、激活／选择、清理计划／退役／执行历史完整回放；不读取现场树 | [Pi 供给](pi-supply.md) |
| 论文 | 身份、发现、来源／人工修正、候选／修订、选择／关系及强身份冲突原材料随历史保留并校验；合法未齐端点或待合并关系不因恢复被改写 | [论文事实](paper-facts.md) |
| Screening | 冻结输入、历史配置／语言依据、登记／请求、attempt／租约／失败／成功响应与 retry 父链完整校验；恢复不执行、不回收、不退预算 | [Screening 任务](screening-tasks.md) |
| Feed 与组合登记 | 检查／条件引用、原材料／解析／论文与冲突引用、元数据请求／路线及语言／预算／组合前置依据一并校验；恢复不重新取得 | [Feed 取得](feed-ingestion.md)、[元数据](feed-metadata.md)、[组合](feed-pipeline.md) |
| Fixture 与审计 | 声明、PDF／backend 期望、取得／选样／矩阵／解释与完整汇总引用闭包校验；未实际取得 PDF 不伪报缺件 | [Fixture 审计](fixture-audit.md) |

SQLite integrity／FK 失败为 `database_invalid`；配置回放失败为 `config_invalid`，供给公共回放
失败为 `supply_invalid`；制品登记及上述业务引用语义损坏为 `registration_invalid`。
来源成员缺失／坏字节为 `file_missing`／`file_corrupt`，清单与合法登记不一致为 `invalid_manifest`。

恢复保留已经占用的 attempt 和未结算租约，只读状态不顺手回收。租约按绝对 UTC 保存，
副本时钟偏差可能使其立即过期或长期有效；到期派生、回收 `outcome_unknown` 和剩余预算规则
仍由任务 Contract 定义。**两次预算上限仅针对每个档案库各自连续历史**：旧备份不含其后
attempt，源库与副本独立继续时，不承诺追回丢失次数、跨恢复 exactly-once 或全局真实调用上限。

<a id="供给隔离恢复操作"></a>

### 供给恢复边界

供给材料与历史事实随数据库保留，format 1 不增加安装树副本、blob kind 或清单字段。
安装树、导出目录、Node/npm 大包及认证不进入批次；历史绝对安装路径只是审计事实，
恢复保留退役与清理历史，不恢复已退役实例可用性。原根不可访问时仍可回查库内材料，
恢复／历史查询不启动 Node/Pi、不安装、不自动激活、不追加恢复标记。
现场核验、缺根后的显式 rebuild／activate 及新独立安全根要求见
[供给诊断与恢复](pi-supply.md#原子激活与只读诊断)和[固定材料重建](pi-supply.md#完整核验与固定材料重建)。
恢复活动副本若继续共用原安装根，**旧活动副本退役前不得 `gc execute`**；flock 只保护
在途使用，不能识别另一个空闲副本的 current。恢复本身不执行清理计划。

<a id="a10-fixture-登记闭包"></a>
<a id="a10-pdf-登记闭包"></a>
<a id="a10-完整混合历史与引用边界107"></a>

### Fixture 回放的证明边界

恢复后的 list/show/replay 只依赖恢复 SQLite 与制品；check 额外检查工作树时，源声明缺失
独立为 `source_missing`，不是 drift 或批次损坏。恢复不下载／解析 PDF、不自动继续审计，
不创建审计执行锁。冻结 v1 保留材料按组件规则回放；新 parser 的默认校验只证明声明、
引用与差异闭包，不声称缺失运行时已经重解析。显式匹配 parser 的重解析规则见
[审计历史回放](fixture-audit.md#显式恢复历史回放与追加解释106)。
共享 source_snapshot 允许论文与审计去重，不使未引用完整制品变成业务成功；
当前备份不承担制品清理，共享引用规则见[Fixture 审计](fixture-audit.md#完成审计引用与完整恢复107)。

## 不提供／不证明

- 不提供 NAS 增量备份、保留策略或无人值守 timer；本机隔离恢复不证明 NAS 恢复。
  承接：[路线图 I](../roadmap.md#module-i)。
- 不提供业务任务自动续跑、完整报告重建或校准／自动精读资格；恢复不扩大已保存制品的使用权限。
  报告由[路线图 H](../roadmap.md#module-h)承接，最终执行恢复由[I](../roadmap.md#module-i)承接。
- 不提供 Pi 执行环境脱网重建（[V1 排除项](../../intent/draft.md#13-明确不进入第一版)）；
  固定供给与实际 RPC 的后续验证范围见[Pi](../roadmap.md#module-pi)／[Live](../roadmap.md#module-live)。
- 不证明真实来源、Docling／正文质量、B 实验入口隔离或模型质量／live 就绪；相应责任见
  [Audit](../roadmap.md#module-audit)、[Body](../roadmap.md#module-body)、
  [B](../roadmap.md#module-b)、[F](../roadmap.md#module-f)、[D](../roadmap.md#module-d)。

<a id="a7-08-独立验收绑定"></a>
<a id="read-配置与候选恢复98"></a>

## 相关

- [既有 A3/A4/A6/A7/Read/A10 覆盖与证明范围](../verification/contracts-backup-restore-history.md)。
  这些是固定历史证据，不替代当前程序校验、完整阶段 A 或 live 验收。
- 实现依据：[备份与校验](../../src/paper_radar/backup/service.py)、
  [清单与原因](../../src/paper_radar/backup/manifest.py)、[恢复](../../src/paper_radar/backup/restore.py)、
  [当前迁移](../../src/paper_radar/storage/migrations/versions/feed06_language_provenance.py)。
- 规格与决策依据：[§9.1](../../intent/draft.md#91-本机一致性快照)、
  [ADR-0027](../adr/0027-address-artifacts-by-content.md)、
  [ADR-0031](../adr/0031-screening-budget-and-derived-applicability.md)、
  [ADR-0034](../adr/0034-separate-fixture-declarations-and-acquisition-audits.md)。
- 原组件扩展依据：[#98](https://github.com/MeteoBoy4/PaperRadar/issues/98)、
  [#101](https://github.com/MeteoBoy4/PaperRadar/issues/101)、[#103](https://github.com/MeteoBoy4/PaperRadar/issues/103)、
  [#104](https://github.com/MeteoBoy4/PaperRadar/issues/104)、[#105](https://github.com/MeteoBoy4/PaperRadar/issues/105)、
  [#106](https://github.com/MeteoBoy4/PaperRadar/issues/106)、[#107](https://github.com/MeteoBoy4/PaperRadar/issues/107)、
  [#114](https://github.com/MeteoBoy4/PaperRadar/issues/114)。
