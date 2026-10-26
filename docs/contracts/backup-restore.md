# 自包含备份批次 Contract v1

现已开放 `backup create`、只读 `backup verify` 和会写入完整副本的 `restore verify`。
隔离恢复只证明本 Contract 的配置/制品范围，不代表 NAS、完整阶段 A、业务任务续跑
或自动精读已验收。
备份服务组合 storage/config 公共服务，不增加 `backup_runs`，不写源执行记录。
受控路径与目录 fsync 复用存储底层约束；备份与恢复的 CLI 复用参数脱敏、批次摘要与受控失败输出，
各自保留中文帮助、错误指引与服务的延迟加载。

## 公开边界与使用

```bash
uv run --offline --locked paper-radar backup create \
  --database data/paperradar.sqlite3 --data-root data --output backups
uv run --offline --locked paper-radar backup verify backups/<backup-batch>
uv run --offline --locked paper-radar restore verify backups/<backup-batch> --target restored
```

`<backup-batch>` 是已发布批次目录，不是运行配置快照 ID。公共 Python 服务为
`paper_radar.backup.create_backup(database, data_root, output)` 与
`verify_backup(batch_dir)`，均返回 `BackupResult(batch_dir, manifest_sha256, manifest)`。
路径不是身份，结果的 batch_dir 为绝对路径；清单不保存绝对源位置。
`verify_contents(root, manifest)` 只负责同一套完整内容解释，不判定根 basename；
`copy_verified_contents(result, destination)` 重新校验来源后向既有空私有 staging
分段复制独立字节并重新校验，不发布目标。它们供恢复服务组合，不是额外产品命令。

create 只接受当前 head；已知祖先指向显式 `db upgrade`，未知/未来或安装包异常拒绝。
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
WAL/SHM/journal、嵌套 staging 一律拒绝。根内任何路径组件符号链接均拒绝。所有新建
目录 0700；数据库和清单 0600，副本 blob 0400。源 blob 沿用 ArtifactStore 的只读约束，
允许 0444 等无写位权限；复制时规范化为 0400，外部 verify 要求批次 blob 恰为 0400。
复制不用硬链接，恢复/备份不会共享源可写 inode。只防误配置、登记损坏与普通并发碰撞；
不要求对抗同机恶意并发替换的 openat 级防护。

清单版本为整数 1，布尔不是整数。UTF-8 JSON、键排序、紧凑 `,`/`:`、
`ensure_ascii=False`、恰有一个结尾换行；拒绝重复 JSON 键与非规范字节。
清单不自哈希，对外 SHA-256 是最终完整清单字节的哈希。字段固定如下：

| 字段 | 格式与责任 |
| --- | --- |
| format_version | 1 |
| batch_id / created_at | 上述 ID 与 UTC 审计时间，目录名须等于 batch_id |
| database_revision | 显式支持 a704_screening_retry，且须等于随包唯一 head；不动态接受未来 head |
| artifact_format_version / blob_layout_version | 各为整数 1 |
| database | 恰有 path=`database.sqlite3`、sha256、非负整数 size_bytes |
| blobs | 全部且去重的 FileEntry(path,sha256,size_bytes)，按 SHA-256 升序；path 必须等于 blobs/sha256/<前2>/<哈希> |
| artifacts | 全部制品，按 artifact_id 升序；恰有 artifact_id、kind、format_version、members、created_at；角色成员按 Unicode role 升序，身份按制品 Contract 重算 |
| snapshot_ids | 全部运行配置快照 ID，唯一且升序；逐个由公共 load 完整回放 |
| counts | blobs、artifacts、config_snapshots、blob_bytes、by_kind；均与实际登记重算匹配 |
| counts.by_kind | 每种实际 kind 的 artifacts、members、size_bytes；字节按每个角色引用计数，允许共享对象重复计入不同用途；blob_bytes 是去重后的物理内容字节 |
| code | package_version、migration_revision、backup_format_version、artifact_format_version、blob_layout_version、sqlite_version、git_commit；格式/revision 与清单一致，git_commit 固定 null |

清单不保存源路径、主机名、用户名、配置正文、Profile、Prompt、模型响应或凭据。
包版本通过已安装 distribution 元数据读取，revision 通过随包迁移图读取，不依赖 Git
或仓库。wheel 安装环境与 editable 环境遵守相同规则。

## 一致性与发布

先调用 SQLite 在线 backup 固定独立副本，再从副本公共登记接口推导全部制品、成员与
内容对象闭包，不从活动库另读清单、不递归扫描数据根猜测事实。副本切换
`journal_mode=DELETE` 并关闭、fsync 后才计算数据库哈希；这表示独立单文件，避免 WAL
头副本被只读公共 API 打开时创建 -wal/-shm。大文件全量哈希与复制均按 1 MiB 分段。
先 `verified_blob_path` 完整核验源对象，复制时再次哈希，再独立校验整个 staging。

创建和 verify 使用同一规则：精确目录集合、每个文件存在/长度/完整 SHA-256、数据库
integrity_check 与 foreign_key_check、支持格式/head、清单和登记双向一致、所有配置
快照经公共 load 语义回放。list 发现本身不代替完整回放。任何缺失、损坏或漏列不补写。
只接受已发布名字，完整但未发布的 staging 也拒绝；移动批次须保留自己的 basename。
verify 成功和失败都不写批次、不迁移、不读取原数据或配置树，目录条目也不变化。

全部通过后，同文件系统原子不覆盖目录发布；当前 Linux 使用
`renameat2(RENAME_NOREPLACE)`，文件系统/系统不支持时明确失败，不降级为可覆盖 rename。
数据库、文件与目录发布前持久化，发布后同步 output 目录。可捕获失败只尽力清理本次
独占创建的 staging；强杀残留由人工处理，不扫描清理其他目录。原子提交点前失败不产生
完成批次；强杀与原子提交同时发生时，可能留下完整已验证批次，须重新 verify，不能从
缺少终端成功输出推断提交是否发生。

无需锁整个存储根的依据是：文件先发布、登记后提交、blob 不可变且本轮无删除。固定
副本已经登记的文件必然存在且不会被删除；固定之后的新提交属于以后批次。未来引入
GC/删除必须重新审查这个并发论证，不可沿用本轮前提。

批次包含数据库随历史保留的已登记配置原字节；不包含 config/ 树、settings.yaml 与
selector、未登记草稿、contracts/ 导出目录、reports、logs、缓存、认证和孤立文件。
**配置文件本身请用 git 保管**。不建报告/任务表，也不伪造其恢复验收。

## 结果与受控原因

成功退出 0，只输出批次 ID、清单 SHA-256、按 kind 的数量与字节汇总，不逐条列 artifact ID。
参数/业务错误退出 2，中断非零；不联网、不调用模型、不消耗自动配额。错误不回显输入、
原始异常或内容，`BackupError.reason` 固定如下，各有中文下一步指引：

| reason | 原因与下一步 |
| --- | --- |
| batch_unavailable | 批次不可用，检查位置/权限 |
| not_published | 非完成批次或目录 ID 不符，选择已发布目录 |
| invalid_manifest | 清单无效/与登记不符，保留原批次检查 |
| unsupported_format | 格式不支持，使用匹配程序 |
| unsupported_revision | revision 不支持，使用匹配程序；不原地升级备份 |
| upgrade_required | 创建源为已知旧库，先显式 db upgrade |
| unsafe_path | 符号链接/路径/权限不安全，检查受控目录 |
| unexpected_entry | 出现清单外文件或目录，保留批次检查 |
| file_missing | 成员缺失，检查完整批次，不补写 |
| file_corrupt | 字节/长度/权限不符，检查保护副本 |
| database_invalid | SQLite 完整性/外键失败，检查数据库 |
| registration_invalid | 制品登记闭包损坏，检查来源或保护副本 |
| config_invalid | 历史配置无法完整回放，检查配置登记 |
| output_invalid | output 不可用或位于受控子树，选择可写安全目录 |
| batch_exists | 位置冲突，包括既有空目录；重新创建新批次 |
| copy_failed | I/O/空间等复制失败，排除故障重试 |
| publication_failed | 原子发布不可用，检查同文件系统和系统支持 |
| interrupted | 操作中断，重新创建/校验，不继承旧成功 |

## 隔离恢复

`paper_radar.backup.restore_backup(batch_dir, target)` 只消费已发布批次，返回不可变
`RestoreResult(target_dir, manifest_sha256, manifest)`；target_dir 是绝对位置，不是身份。
目标根可以整体移动，成员仍按新根解析；恢复目标无需沿用批次名。
`RestoreError.reason` 复用下表与原 BackupReason，CLI 错误统一为中文脱敏原因，不回显
路径、原始异常、配置、Prompt、正文、模型结果或凭据。

源批次先经 `verify_backup` 严格验证，再由 `copy_verified_contents` 重新核对源并复制
数据库、全部登记 blob 和原清单，使用同一 `verify_contents` 规则完整校验副本；不维护
第二套清单/配置/制品解释器，不读取原数据或配置根，不补写缺项。完整但未发布的 staging、
改名批次、损坏和任何清单外条目都拒绝。复制使用独立 inode，不以硬链接依赖源字节。

目标可以不存在，或为非符号链接的空目录；拒绝普通文件、非空目录、目标自身符号链接
（含断链）、与批次相同或位于批次内部的位置。重叠检查仅针对批次，清单不加绝对源
位置，也不探测活动数据目录。目标父路径解析一次，**父目录必须预先存在**，不存在时
报 parent_unavailable，不创建任何层级。父目录已有权限不改写；所有本次新目录 0700，
数据库/清单 0600、blob 0400。

在目标父目录创建唯一 `.restore-staging-<随机名>` 同级目录，完整复制并验证后用 POSIX
`rename` 原子发布。允许原子替换空目标目录；发布前重新检查目标，且最终 rename 本身
拒绝被并发写成非空的目录，因此不会递归清空或覆盖用户数据。源/目标必须适用同文件系统
重命名，失败受控，不降级为逐文件发布。发布后 fsync 父目录。

失败或中断不生成成功恢复结论；只尽力清理本次独占创建的 staging，不清理别人的
staging，也不扫描 GC。强杀在发布前发生时残留由人工处理；若与原子提交同时或之后
发生，可能已有完整已验证的目标，不能从缺少终端成功输出推断发布未发生。目标已有
内容时请保留检查，向合适的新空目标重试，不通过清空目录绕过保护。

恢复库与批次库原字节完全一致，保持 `journal_mode=DELETE`；list/diff/完整 ID load
及制品读取不会自动迁移、重编译、激活快照或启动任务。历史 ID、配置原字节、创建
时间、六投影和校准基线保持不变。[阶段输入消费者](stage-inputs.md#隔离恢复跨进程与后续消费者义务)
在原根不可访问时，从恢复库明确历史快照与重新 get_artifact 的成员重建四阶段身份；
该验证只使用公共恢复服务，不改变备份算法，也不从内存旧成员哈希补项。
要把副本作为工作库，另显式运行：

```bash
uv run --offline --locked paper-radar db upgrade --database restored/database.sqlite3
```

此操作 head 不变，恢复 WAL；事实与身份不变，数据库物理字节可能变化。原备份批次
始终独立保留 DELETE 模式。恢复不安装 Pi、不续跑任务、不修改校准或自动精读门禁，
不声称能重建尚未实现的业务报告。配置文件本身仍请用 git 保管。

| RestoreReason | 原因与下一步 |
| --- | --- |
| target_unavailable | 目标不可用、为文件或链接；选择不存在位置或普通空目录 |
| target_not_empty | 目标非空或发布时被占用；保留已有内容，选择新目标 |
| target_overlap | 目标与批次相同或位于其内部；选择批次以外的位置 |
| parent_unavailable | 父目录不存在或不可用；先创建可写父目录 |
| restore_copy_failed | 复制/空间/权限失败；排除原因后向合适空目标重试 |
| restore_publication_failed | 原子目录发布失败；检查文件系统和目标状态 |
| restore_interrupted | 操作中断；检查目标与本次残留，不能继承旧成功 |

批次错误保留原 BackupReason（如 file_missing、file_corrupt、unexpected_entry），不以
一个通用恢复错误抹掉原因。成功退出 0；参数/业务失败退出 2，中断非零。成功输出与
backup verify 一样只给批次 ID、清单 SHA-256 及按 kind 汇总，不逐条输出制品或研究内容。
帮助直接说明“写入完整副本”和父目录 staging；帮助无外部 I/O，不依赖配置、凭据或数据库。


同次离线存储/恢复范围由 [A3 独立结论](../verification/offline-evidence.md#a3-独立结论)
记录；它绑定实际运行和固定回执，不替代 NAS 验收，也不开放业务任务或自动精读门禁。

## Pi 供给事实与旧 revision 批次

供给路径已在 `a405_pi_cleanup_execution` 将供给清单、官方/派生/补充校验材料、D5 证据与引用、
安装根归属、安装实例、scope 为 install_check 的历史事实、重建失败、
激活事件及单库唯一当前选择、不可变清理计划与追加的清理执行进展一并存入数据库。
备份 format 仍为 1，不增清单字段、blob kind 或安装树副本。
create/verify/restore 均经供给公共查询完整语义回放，材料摘要、供给身份、派生规则与 D5
闭包（含事件对供给/实例/完整快照/根的交叉引用与唯一选择）损坏返回 `supply_invalid`；
若先违反 SQLite 外键完整性则返回 `database_invalid`；不读取现场树，不启动 Node/Pi，不联网，不激活。

版本门槛不接受已知祖先：a302 或 `a404_pi_cleanup_plans` 批次以当前程序 verify/restore
返回 unsupported_revision。保留原批次，checkout 匹配该 revision 的程序先 verify/restore
（a302 对应匹配 A3 程序），切回当前程序后对恢复库显式 db upgrade，
随后新做当前版本备份。原始配置/制品身份与原字节保持不变。
供给历史路径只是本机审计事实；恢复副本可以离线查询，不表示原安装仍存在。
同机原实例完好且 doctor 现场核验通过可继续使用，不增加恢复标记；
原根缺失时 doctor 指向 rebuild 后显式 activate，且旧根历史无需修回才能匹配新当前选择。
如恢复活动副本继续共用原安装根，旧副本退役前不得执行后续 gc execute；
flock 不能区分两个空闲活动副本。详见 [供给 Contract](pi-supply.md)。

`a404_pi_cleanup_plans` 的不可变安装清理计划和最小退役识别事实也随数据库完整保留。
计划规范字节/ID/严格格式、事实引用闭包、受控实例位置、选择与保护理由均在公共供给历史回放中校验。
后来的激活/检查/退役不改写旧计划，事实版本不同只影响执行适用性，不否决合法历史备份。
恢复不读取现场树，也不执行计划；原根失去访问后仍可按完整 plan_id 回查原规范字节。
计划损坏属于 supply_invalid，悬空外键优先属于 database_invalid；备份 format 继续为 1。
### 供给隔离恢复操作

1. 在原库创建并 verify 批次；供给、D5、实例、检查、失败与激活事实均在 SQLite，
   安装树、导出目录、Node/npm 大包和认证不进入 format 1。原库有未 checkpoint 的 WAL 时，
   备份仍通过 SQLite 在线备份取得包含已提交事实的一致副本。
2. 原数据库、配置、request/evidence、导出材料及安装根均可撤销访问，再对批次运行
   `restore verify <batch> --target <新空目标>`。恢复及随后 list/show/export 不联网、不探测
   Node/Pi、不安装、不自动激活，不追加恢复标记。可立即在不支持部署的平台回查原身份、
   材料字节、三种 D5 引用、旧配置/六投影/基线及制品；export 可另选新材料根。
3. 只有准备恢复执行时，在支持的平台对恢复库显式运行
   `doctor --scope pi-supply --database <恢复库> --snapshot <已有快照>`。
   原安装缺失会给 `install_unavailable` 并指向 rebuild 后 activate；历史缺根保留。
4. 向新的本库独立安全根显式 `pi supply rebuild <supply_id>`，提供分离的
   `--data-root <恢复根>`、`--config-root <新配置根>`、`--material-root <新材料根>`。
   该步按冻结哈希重新联网下载大包，不读取旧 request，也不重新取 release/SHASUMS；
   不承诺上游永久可用或脱网重建。新实例成功后仍须显式 `pi supply activate`，
   用所需匹配快照切换当前选择，再运行 doctor。旧实例/激活与全部供给材料保持。

一根仅服务一库，归属他库拒绝。恢复副本继续用原根时，先退役旧活动副本再允许清理；
flock 保护在途进程，无法保护另一个空闲副本的 current。恢复到新根可避开这一共享纪律。
任何材料摘要、supply_id、D5 基线/证据或激活闭包损坏，即使 SQLite integrity 为 ok 也拒绝；
不联网补齐，不读导出文件修复。a302 旧批次仍须由匹配 A3 程序先 verify/restore，
再切换新程序显式 db upgrade 并重做备份；新程序的 unsupported_revision 是预期，
不得改写原批次清单 revision 或放宽 head gate。


A4 同次完整离线组合还覆盖：非空供给准备/核验/重建与激活后，真实保护阻止候选，
释放后显式计划清理，再导出固定原材料；备份隔离恢复仍保留供给检查、激活、原计划和
逐项执行审计、D5 原字节与既有配置/制品，退役安装不恢复可用性。该组合不访问原根、
不安装 Pi/Node、不启用模型，不替代 NAS/live 验收；见 [A4 证据](../verification/offline-evidence.md)。

以下 A6 组合交付时的历史 head 为 `a604_version_relations`；当时 backup format 继续为 1，
该组合未新增 migration 或清单字段。当前支持的 head 见上表及 A7-03 小节。
当前程序对 a405/a601–a701 等旧 revision 批次返回 `unsupported_revision`，须用匹配旧程序恢复后对恢复活动副本显式升级；
不得在备份批次内部迁移。

### 组合论文事实的语义闭包

create 先在线固定数据库、枚举该副本登记，再核验与复制源 blob。源字节只供完整性哈希与复制；
论文业务语义解析（包括人工请求正文核对）只在全部成员已复制的 staging 上执行。
create、只读 verify 与 restore verify 共用 `verify_contents` 的 `PaperFacts.validate_all` 入口。
源文件缺失/坏字节按 `file_missing/file_corrupt` 拒绝；引用语义矛盾按 `registration_invalid` 拒绝。
成功与失败均不回写源库，不修复批次、旧修订或选择；失败不发布目标，只清本次独占 staging。

核对 DOI/版本/Paper 归属、Feed 原文指纹与 payload/发现键、候选所属观察/版本、完整修订获选引用、
来源取得/轻量重复/完整重解析、人工请求、选择事件顺序与关系原始断言/端点类别/locator。
合法无 DOI 版本、尚缺一端或两端的关系、两端分属不同 Paper 的 requires_merge 都是可恢复事实。
正式版无摘要仍升级当前，映射缺摘要；旧预印本和从未获选同级版本可明确按历史修订重建。
外键合法且外层数据库/清单重哈希不能掩盖 item/payload、provenance、DOI 归属、错候选或选择/关系矛盾。

`test_paper_recovery_combined` 从公共服务组合四来源、跨 Feed/无 DOI 后补、人工修订、关系三态和零端点、
旧/新快照及完整重解析。真实 WAL 非空时备份，复制便携批次后以进程 audit 拒绝原数据/配置/备份源及
改名位置的 open/SQLite URI/listdir/scandir；另进程恢复并搬迁，再在不同 cwd/hashseed 新进程读取。
请求只含受控 ID/revision/snapshot 与原记录的 fingerprint、payload SHA/长度、业务依据哈希；
论文题名摘要由恢复库候选引用取得，不从请求/环境或原配置材料补入。普通查询和映射另拒绝 blob I/O。
CLI show/trace 与公共服务一致，默认不展开摘要；显式 trace 字节核验包含仅关系材料且不转储原文。

这些是离线组合恢复证据，不能替代完整阶段 A、真实来源/解析器、live/RPC、Docling/NAS 或任务续跑。
parser 升级固定样本与强身份冲突材料持久化仍是阶段 C 门禁。

## A7-02 登记事实闭包

A7-02 历史批次数据库 revision 为 `a701_screening_registration`，备份格式仍为 1。
配置、论文事实之后增加任务登记语义重验，覆盖冻结 BLOB/指纹/投影、历史 snapshot、
Paper/版本修订/选择归属、请求身份及第 0 代唯一关系；失败稳定为 registration_invalid。
manifest 形状、制品种类与计数不扩展。a604 批次须使用匹配旧程序恢复后显式 upgrade；
verify 本身不会升级旧批次。非空双阶段登记可在原目录不可用的新进程中从移动后的
副本独立回放；恢复/查询不执行任务。

## A7-03 尝试、租约与失败闭包

A7-03 历史批次数据库 revision 为 `a702_screening_attempts`，备份格式、manifest 字段、
artifact kind 与 counts 均保持原值。任务语义钩子继续位于 PaperFacts 后、manifest
反查前，不重复注册第二条 hook。除登记闭包外，核对 attempt 序号连续且每代最多两次、
请求与任务归属、请求 snapshot 下领取时历史输入同指纹、凭据/租约归属、UTC 时间和
追加失败结算的一致性。外键合法或重新计算外层数据库/manifest 哈希不能掩盖语义损坏；
失败沿用 registration_invalid，不回写源库或修复批次。

恢复保留已占次数、未结算租约与已结算失败；只读状态不会顺手回收。租约固定 600 秒，
恰好到期派生 lease_expired，直到显式回收或后续领取事务结算 outcome_unknown。
第二次到期未结算仍为 lease_expired/剩余 0，回收后才为失败终态。没有自动回收守护进程，
恢复也不调用执行者。已到期但未被结算的原持有者仍可续租/提交，回收后旧凭据失权。

**两次预算保证仅针对每个档案库各自连续历史。** 从较早批次恢复会丢失备份之后的
attempt；源库和副本之后各自继续，不能承诺跨回退追回丢失次数或限制全局真实调用数。
新程序对 a701 批次返回 unsupported_revision，须由匹配旧程序恢复后显式升级活动副本。
完整成功/retry 跨域隔离恢复见 A7-07；真实模型、RPC、NAS 与 live 行为仍待后续验收。


## A7-06 retry 链闭包

当前 head 为 a704_screening_retry；备份格式 1、manifest 与 counts 不变。任务完整性钩子
追加连续代际、唯一同预算父链、父真实失败终态与 retry 请求摘要校验。恢复保留每代
两次预算、原回执、后继与未结算租约，查询只派生 lease_expired，不自动回收或执行。
外键合法且外层重新哈希的代际跳号、环、父链缺失、retry 摘要损坏或未失败父任务仍报
registration_invalid；拒绝不修复批次，也不发布恢复目标。

## A7-07 隔离组合恢复与版本边界

两篇 Paper、双阶段、当前/历史成功、耗尽失败、retry 后继与过期 attempt 在同一活动
WAL 档案库备份，并在真正的新进程执行恢复。阻断原数据/配置及改名路径后，恢复
副本再次搬迁并阻断批次访问；公共查询/完整性重验只读重建全部任务历史和原始响应。
显式 upgrade 后才继续测试任务；恢复不自动激活配置或执行/回收任务。

租约记录的是绝对 UTC，副本时钟与原机器偏差可能使它立即过期或长期有效；默认
接受偏差，只改变结算时机。回收始终 outcome_unknown，不退预算，也不额外购买次数。
每代两次上限只对单一档案库连续历史成立；旧备份遗失后续 attempt 时副本可能再次
调用，不能承诺跨恢复 exactly-once 或全局真实调用上限。

`BACKUP_DATABASE_REVISION` 固定批次支持的 revision；旧 revision 必须由匹配旧程序
恢复，再显式 upgrade 副本。当前任务语义钩子位于 `_registered_contents` 和 PaperFacts 校验之后、manifest
反查之前，并按当前 A1/A5 规则重验成功响应；即使 revision 相同，校验规则收紧也
可能让旧程序曾验证通过的批次在当前程序失败。这不是无限跨版本的验证承诺。


## A7-08 独立验收绑定

A7 将上述登记、尝试、双阶段成功、retry 与完整隔离恢复逐项纳入固定能力材料，
绑定生产 backup 格式 1、真实临时升级 head a704_screening_retry、同次 A3/A6 结论及
实际 pytest 回执。语义损坏反例必须在 FK/SQLite 合法、外层重新哈希后仍受控拒绝，
不修改批次、不发布目标；详见[A7 验收矩阵](../verification/a7-requirements.md#a7-08--84-独立验收与可信终态)。
备份格式、manifest 字段、计数、artifact kind 与旧 revision 策略不因此改变。
当前正常离线入口为九份主要文件、共十一份 JSON；这不证明 NAS、真实模型或 live 恢复。

## Read 配置与候选恢复（#98）

新增组合沿用本 Contract 的格式、revision 准入与独立副本算法。
双历史配置、四份合法 `model_success_response` 的隔离恢复和明确未验证项统一见
[Read 恢复范围](read-validation.md#恢复范围98)；消费上下文来自测试常量，不是备份产物。

## A10 fixture 登记闭包

备份固定副本只读调用 FixtureAudit.validate_all，校验不可变声明原字节、解释与显式替换历史；恢复不读原声明或远端 URL。取得字节继续使用 ArtifactStore，当前 #101–#103 已接入声明、PDF 与来源取得闭包，后续票继续扩展成员、矩阵与恢复继续历史。共享 source_snapshot 的清理必须同时纳入论文与审计引用。

A10 #103 的计划、started/结算与条件材料复用也由 FixtureAudit.validate_all 进入固定副本语义闭包；核对规范请求身份、策略/通道、真实 HTTP 计数及 retained source_snapshot 的种类/字节/身份。失败只保存结构化事实，不要求缺失错误页正文；恢复和只读查询不访问来源或创建审计锁。


### A10 PDF 登记闭包

本机 PDF 取得引用既有 `original_pdf`，声明只保留要求时不产生虚假的缺件。
取得历史、当前选择的显式替换链及每份 PDF 独立的 backend 期望随 SQLite 保存，
制品字节随既有闭包复制。恢复不依赖原 PDF 路径、声明源文件或来源 URL，不自动
解析、下载或替换当前样本。语义校验核对 PDF 种类、真实长度/SHA、backend 的准确
内容绑定与三态章节检查依据；期望登记仍只表示形状与引用一致，不代表提取质量通过。

A10 #104 将唯一冻结 Feed、固定成员、原位次排除/暂停台账与继续历史纳入同一语义闭包。核验会重读批次内 Feed 和来源材料重放旧选择，检查真实身份/类别依据与成员；完整重哈希不能将别的 DOI 替换入成员。恢复无网络、无选样执行锁，完整跨阶段混合历史隔离演练由 #107 收口。


A10 #105 将成员适用摘要路线的取得引用、安全候选解释、区块定位和原取得时间纳入同一闭包。
备份固定副本调用 validate_all 从原保留材料重解析主区块、长度、截断信号并复算来源仲裁；
重哈希不能篡改候选解释。原文本仅保留在受控制品，联系人不保存；恢复可显式读取原摘要，
普通 list/show 只投影安全元数据，不联网、不获取执行锁。基本恢复子集不代替 #107 全历史混合演练。
