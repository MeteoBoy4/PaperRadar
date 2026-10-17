# 不可变制品存储 Contract v1

本 Contract 固定内容对象身份、制品清单格式、纯内容布局及公共发布/读取边界。
现已完成四种单文件制品与完整 extraction 多文件发布；自包含备份与隔离恢复也已交付，
公开边界见[备份与恢复 Contract](backup-restore.md)。
存储成功表示原字节完整保存，业务接收不在这个边界：不判断来源是否贡献事实、PDF
是否合法取得或模型输出是否通过权威接收。上游必须先完成相应验证；不提供通用人工导入 CLI。

## 身份、字段与固定词表

blob 身份是原始字节 SHA-256，无域前缀，64 位小写十六进制；允许 0 字节。
artifact 身份是规范清单 UTF-8 字节的 SHA-256，不包含时间、路径、数据库行号或阶段指纹。
固定域标识 `paper-radar.artifact`，独立 `format_version=1`；清单必须恰有
`domain`、`format_version`、`kind`、`members`。每个成员恰有 `role`、`sha256`、
`size_bytes`；大小为非负整数，布尔不是整数。未知字段、重复/缺失/额外角色、非法哈希、
其他域或格式版本拒绝。成员按 role 的 Unicode 码点升序，JSON 键排序、紧凑分隔符
`,`/`:`，非 ASCII 直接编码 UTF-8，无 BOM、末尾换行或无意义空格。

| kind | 恰有的角色 | 当前发布状态 |
| --- | --- | --- |
| source_snapshot | payload | 已开放 |
| original_pdf | payload | 已开放 |
| model_success_response | payload | 已开放 |
| reference_tei | payload | 已开放 |
| extraction | document、evidence_map、manifest、reading | 已开放完整集合 |

extraction 的 manifest 是上游正文材料成员，与这里的制品清单不同，不能循环包含自身哈希。
同一 artifact 内不同角色允许引用同一个 blob。媒体类型由 kind/role 推导，不由调用方传入，
不进入身份：original_pdf 为 application/pdf，reference_tei 为 application/tei+xml，
extraction/reading 为 text/markdown，其余 extraction 角色为 application/json；
来源与模型响应默认 application/octet-stream，以保持原始字节语义。

SQLite 是登记事实源：`content_objects` 记录 blob 身份、长度、布局版本、相对位置和时间；
`artifacts` 记录身份、kind、格式与时间；`artifact_members` 记录 artifact/role 到 blob 和
成员长度。artifact 清单正文既不存磁盘也不存数据库；每次读取从关系重算身份。
PK、UNIQUE、FK、hex 和非负整数约束在 SQLite 生效；kind/role 枚举由 Python Contract
强制，不使用需要重建表才能演进的 DB CHECK 枚举。不建立论文表、backup_runs 或自由业务 JSON 桶。

## 独立固定向量

FIPS 180-4 标准原始字节向量：空串为
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`，
`abc` 为 `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`。
下列完整 JSON 是固定字面量；代码围栏的换行不属于字节。

```json
{"domain":"paper-radar.artifact","format_version":1,"kind":"source_snapshot","members":[{"role":"payload","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","size_bytes":0}]}
```

artifact ID：`accf50f8375b85b3f2105c3904cf05db0d56922a0bffe9cafb0f1e8bf6e57afa`。

```json
{"domain":"paper-radar.artifact","format_version":1,"kind":"extraction","members":[{"role":"document","sha256":"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad","size_bytes":3},{"role":"evidence_map","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","size_bytes":0},{"role":"manifest","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","size_bytes":0},{"role":"reading","sha256":"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad","size_bytes":3}]}
```

artifact ID：`b461c859afffb63c837b556746fd0ab9cfe892bcd1a58a912da46799b1738d87`。
这个向量冻结共享 blob 和角色排序。成员字节或角色分配变化的六组完整规范清单与身份
另外固定在 `tests/fixtures/extraction_artifact_vectors.json`；期望不从被测服务生成。

## 路径、权限与发布

布局版本 1：`<data-root>/blobs/sha256/<前2位>/<64位哈希>`。登记相对位置必须逐字等于
布局/哈希推导值；读取不能信任任意登记路径。根本身可以是符号链接，构造时解析一次；
根内每个组件（含 tmp、前缀目录和文件）一律拒绝符号链接。数据库可以位于数据根以外。
这是误配置、损坏与路径穿越的防护，不扩展至同机恶意替换的 TOCTOU/openat 威胁模型。

存储与备份共用 `storage/filesystem.py` 的逐组件路径约束与目录 fsync；各自入口
保留领域错误映射，根解析与目录创建策略仍由调用者负责。

分段写入本根 `tmp/` 的进程独有临时文件，同时计算实际哈希和长度；若给定预期哈希必须一致。
文件 flush、改为只读 0400 并 fsync 后，以不覆盖 hard-link 发布；每级新建目录 0700，
目录项同步至父目录。既有同名文件必须完整核验长度/哈希且没有写权限，损坏或可写对象拒绝接收、不覆盖；已登记文件缺失不能
用重试重建。不支持 hard-link 时受控失败，不能退化到覆盖式 rename。
受控失败只尽力删除本进程独有临时文件；被强杀的残留由人工处理，不扫描清理其他文件。

文件完整发布并持久化后，才在同一短 `BEGIN IMMEDIATE` 事务中登记 blob、artifact 及
所有成员。外键开启，锁等待固定 5 秒，失败原子回滚。重复或并发发布返回同一完整事实，
不刷新创建时间。提交前故障或强杀最多留下未登记文件；它们不可查询，重试核验后可复用。
已有损坏登记不补齐、不从来源自动修复。

## 公共服务

`paper_radar.storage.artifacts.ArtifactStore(database: Path, data_root: Path)` 的构造不建库、不
创建目录；仅解析根。公共发布入口 `publish_single(kind, chunks, expected_sha256=None)` 与
`publish_artifact(kind, members, expected_sha256=None)` 分别接收单文件 kind 与全部五种已开放 kind。
chunks 为 bytes 分段 iterable；members 为角色到分段 iterable 的映射。
`publish_single` 只接受单 payload 集合；`publish_artifact` 对 extraction 恰要求四角色，
拒绝缺项、未知/额外角色或重复枚举的角色。成员枚举顺序不改变身份。

返回不可变 `ArtifactRecord(artifact_id, kind, format_version, members, created_at)`，其中
members 是 `ArtifactMember(role, sha256, size_bytes)` 集合。
`get_artifact(id)` / `artifact_blobs(id)` 校验完整登记身份、角色闭包与派生位置，后者也返回
`BlobRecord(sha256,size_bytes,relative_path,layout_version)`。`list_artifacts()` 在同一
数据库读取视图中校验全部登记闭包，拒绝孤立对象/引用，不扫描文件系统猜测事实。

`read_artifact(id)` 返回角色到 bytes 的映射；在全部成员登记身份、位置、长度、哈希完整
验证前不向调用方交出内容。本轮不提供流式读取 API。
`verified_blob_path(blob)` 完整校验文件后返回受控推导路径，供备份自行分段复制并再次
核验哈希；这是完整性检查边界，不是将未校验字节交给业务的流式读取入口。

文件先发布、登记后提交，且 A3 无删除：固定备份数据库已引用的内容文件在其提交前就存在，
之后不会被删除；备份复制期间新增 blob 不在固定清单中。因此备份按副本登记复制无需锁
存储根。未来引入 GC/删除前必须重新建立并发安全论证。

## Revision 与原因码

head 固定为 `a302_artifact_store`，祖先 `a201_profile_snapshot`。只追加 CREATE TABLE/INDEX，
旧 migration 字节不变，不 batch 重建三张配置表。显式升级在一个 SQLite 事务内完成全部
DDL 和 version stamp；仅迁移连接关闭 legacy 事务模式并显式 BEGIN IMMEDIATE，普通配置
save_snapshot 的事务语义不变。空库初始化和重复升级可用；升级结束启用 WAL。

`StorageError.reason` 的数据库分类如下；reason 不包含路径、revision 原文或配置正文。

| reason | 原因与下一步 |
| --- | --- |
| database_missing | 缺库；显式 db upgrade |
| database_uninitialized | 未初始化；显式 db upgrade |
| upgrade_required | 随包图中的已知祖先；先显式 db upgrade |
| unknown_revision | 不在图中；使用匹配程序检查，不从名字推断“未来” |
| package_migrations_invalid | 安装包迁移脚本多 head、无 head 或不可读；检查安装 |
| database_revision_corrupt | 库内 version 行为空或多行；检查数据库 |
| database_unreadable | 库不可读；检查路径/权限 |
| upgrade_failed | DDL/stamp 失败已回滚；排除故障后重试 |
| wal_unavailable | 无法启用 WAL；检查存储介质 |
| storage_failed | 其他既有存储失败；按中文指引检查 |

配置 check/compile/diff/list 在已知旧库上明确要求先 upgrade，不自动建库或迁移。
升级前保护副本须使用 SQLite backup API（README 有离线示例），不能只复制活动主文件。

`ArtifactError` 继承 StorageError，具有以下固定 reason；错误文本为中文、脱敏并提供下一步。

| reason | 原因与下一步 |
| --- | --- |
| invalid_manifest | 未开放种类、角色或字段无效；按 Contract 提交 |
| invalid_hash | 非完整小写 SHA-256；检查输入身份 |
| unsafe_path | 根内链接或受控位置异常；检查数据根 |
| blob_missing | 已登记文件缺失；检查数据根或保护副本 |
| blob_corrupt | 长度/哈希损坏或不可读；检查保护副本，不自动修复 |
| hash_mismatch | 实际字节与预期哈希不同；检查上游输入 |
| publication_failed | 文件持久化或 hard-link 失败；检查权限与文件系统 |
| artifact_missing | 制品身份未登记；检查完整身份 |
| registration_corrupt | 清单身份/成员/位置登记损坏；检查数据库，不修补历史 |
| database_busy | 5 秒锁等待超时；稍后重试 |
| database_failed | 登记读取/提交失败；事实回滚后排除故障重试 |

## 多文件集合原子性与失败恢复

extraction 的 `manifest` 成员是上游正文制品原字节，与进入制品身份的 `ArtifactManifest`
规范清单、备份清单是三个不同对象；它不能循环包含当前制品自身的哈希。存储层只验证
完整集合和字节，不运行 Docling，也不验证正文或 evidence 的业务语义。

成员按固定角色顺序逐个分段发布，document 与 reading 可以共享同一 blob，仍保留
两条独立角色引用；跨 extraction 和单文件种类也共享相同内容。全部文件完整发布并验证
后才开始一次登记事务，写入完整 artifact 与全部成员。公开枚举仍按数据库成员引用闭包
工作，没有 extraction 专属目录、自由角色或阶段指纹查找旁路。

临时写入、部分成员已发布、全部文件已发布但登记前、成员行写入中途和 commit 前的
异常或强杀，都不产生可查询的半集合，旧制品保持可读。未登记的已发布文件允许保留，
重试逐个验证后复用；本轮不做 GC。读取先验证登记身份并完整读取全部成员，任一成员
缺失、同长度损坏、路径链接或成员行篡改都会拒绝整个集合，不向调用方交出部分结果，
也不能用重新发布输入补写历史。进程竞争用管道屏障固定到真实发布/SQL 边界，无 sleep
排序；输入测试用拒绝无界读取的流包装为 bounded 分段生成器。
