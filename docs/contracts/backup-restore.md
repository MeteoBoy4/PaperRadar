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
| database_revision | 显式支持 a403_pi_activation，且须等于随包唯一 head；不动态接受未来 head |
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
时间、六投影和校准基线保持不变。要把副本作为工作库，另显式运行：

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

## Pi 供给事实与 a302 旧批次

当前 head `a403_pi_activation` 将供给清单、官方/派生/补充校验材料、D5 证据与引用、
安装根归属、安装实例、scope 为 install_check 的历史事实、重建失败、
激活事件及单库唯一当前选择一并存入数据库。
备份 format 仍为 1，不增清单字段、blob kind 或安装树副本。
create/verify/restore 均经供给公共查询完整语义回放，材料摘要、供给身份、派生规则与 D5
闭包（含事件对供给/实例/完整快照/根的交叉引用与唯一选择）损坏返回 `supply_invalid`；
若先违反 SQLite 外键完整性则返回 `database_invalid`；不读取现场树，不启动 Node/Pi，不联网，不激活。

版本门槛不接受已知祖先：a302 批次以当前程序 verify/restore 返回 unsupported_revision。
保留该批次，checkout 匹配 A3 程序先 verify/restore，切回当前程序后显式 db upgrade，
随后新做当前版本备份。原始配置/制品身份与原字节保持不变。
供给历史路径只是本机审计事实；恢复副本可以离线查询，不表示原安装仍存在。
同机原实例完好且 doctor 现场核验通过可继续使用，不增加恢复标记；
原根缺失时 doctor 指向 rebuild 后显式 activate，且旧根历史无需修回才能匹配新当前选择。
如恢复活动副本继续共用原安装根，旧副本退役前不得执行后续 gc execute；
flock 不能区分两个空闲活动副本。详见 [供给 Contract](pi-supply.md)。
