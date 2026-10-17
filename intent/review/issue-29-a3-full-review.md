# Issue #29 阶段 A3 全量审查（Standards / Spec 双轴）

- 固定点：`main` = `91080ba9805da462c0b5a6213ab266b2971e1f98`
- Diff 命令：`git diff main...HEAD`（72 文件，+7716/−198）
- Commit 列表（`git log main..HEAD --oneline`）：
  - `a09c3cc` fix(backup): reject FIFO manifests and redact group options (#29 review fixes)
  - `c0ce26a` feat(verification): bind A3 acceptance to current offline run (#35)
  - `cb826b3` feat(restore): verify isolated copies without original roots (#34)
  - `bbb735a` Merge branch 'integration/issue-29-a3' into work/issue-33
  - `d2023dc` feat(backup): create and verify self-contained WAL backup batches (#33)
  - `dbe8819` feat(storage): publish complete extraction artifacts atomically (#32)
  - `660d553` test(storage): enforce immutable reuse and verify SQLite constraints (#31)
  - `a52b0c9` Merge branch 'integration/issue-29-a3' into work/issue-31
  - `bc7b843` feat(storage): safely upgrade and persist immutable single-file artifacts (#31)
  - `8d09251` refactor: share offline acceptance checks for #30
- 规格来源：GitHub Issues #29（父票正文 + 三条裁决评论 issuecomment-6212596698 / 6212865201 / 6213316174）与子票 #30–#35
- 标准来源：`AGENTS.md`、`CONTEXT.md`、`docs/agents/{python-conventions,testing,refactor,cli-output,invariants,scope,documentation}.md`、`docs/verification/offline-evidence.md`、`docs/adr/` + Fowler smell 基线
- 审查方式：Standards 与 Spec 两个 reviewer 子代理并行，仅聚合不混合排序；本次审查未修改代码、未创建 commit

### 子代理工具限制与补验说明（聚合者注）

两个子代理的运行环境均无 shell/git 工具：Standards 轴以 `scripts/a3_scope.py` 登记的哈希绑定清单定位改动并读取 HEAD 现状；Spec 轴依据 `.scratch/a3-tracer-bullets/issues/` 的本地 issue 镜像而非 GitHub 原文。聚合者随后用仓库 shell 逐项验证了 Standards 轴全部 5 项发现（均属实，见各条「已验证」注记），并针对 Spec 轴声明的两个缺口补做了父票级抽查：root help 无 `run-due`、六段锚点保留；`<backup-batch>` metavar；CONTEXT.md 术语词条；README「配置文件本身请用 git 保管」；restore help 写明写入完整副本与隐藏 staging；a302 migration 仅 CREATE TABLE/INDEX；A3 组 `required=True`；`stage_a_verified`/`live_verified` 恒 false——全部通过。以下两节为子代理报告原文（仅排版微调）。

## Standards

审查方法说明：本环境无 shell/git 工具，无法直接执行 `git diff main...HEAD`；以 `scripts/a3_scope.py` 显式登记的文件清单（本次 diff 的哈希绑定）定位改动并逐一读取 HEAD 现状，覆盖 storage/backup 全部生产源码、两份契约文档、ADR-0027、README 与 FIFO 回归测试。

- Correct:
  - 文档义务（`docs/agents/documentation.md`）满足：`docs/contracts/artifact-store.md`、`backup-restore.md`、`README.md:43-128`、ADR-0027、`docs/verification/offline-evidence.md` A3 节同步更新。
  - 领域不变量（`docs/agents/invariants.md`）：a302 经 Alembic（`storage/migrations/versions/a302_artifact_store.py`）、只追加、blob 在文件系统、登记在 SQLite；测试覆盖 a201→a302 与 base→head（testing.md 义务）。
  - FIFO 修复有回归测试（`tests/test_backup_integrity.py:185`，testing.md「先写失败测试」）。
  - 错误均为受控 enum + 中文下一步（`python-conventions.md`、`cli-output.md`）；`--help` 无 I/O 由延迟 import 保证。
  - 确定性与 I/O 分离良好：`artifact_contract.py`/`manifest.py`/`restore_contract.py` 纯格式，`files.py`/`blob_store.py` I/O。
  - `backup/__init__.py` 薄转发是契约明确要求的延迟加载，不算 Middle Man。

- Finding (P2, judgement call): Duplicated Code — `sync_directory` 与 `BlobStore._sync_directory`（`src/paper_radar/storage/blob_store.py`）逐字重复；最小修复：backup 复用 storage 侧或提取共享函数。
  〔聚合者已验证：`backup/files.py:111` 与 `blob_store.py:35` 均为 `os.open(O_DIRECTORY)` + `fsync` + `close` 的同形实现。〕
- Finding (P2, judgement call): 安全路径校验双实现 — `BlobStore._path`（`Path.parts`）与 `controlled_path`（`split("/")`，`backup/files.py`）各自实现「逐组件拒绝符号链接与 `..`」，安全关键逻辑重复且实现形状不同；宜共享一个约束函数。
  〔聚合者已验证：`blob_store.py:59` 用 `Path.parts` + `ArtifactReason.UNSAFE_PATH`，`backup/files.py:33` 用 `split("/")` + `BackupReason.UNSAFE_PATH`，均为本 diff 新增。〕
- Finding (P2, judgement call): CLI 层重复 — `_BackupGroup`/`_BackupCommand`（`backup/cli.py`）与 `_RestoreGroup`/`_RestoreCommand`（`restore_cli.py`）parse_args/get_command 逐字重复；`restore_verify` 成功输出重复 `_show_result` 三行格式（输出一致性是契约要求，但格式化形状可共享）。
  〔聚合者已验证：两对类仅中文消息文案（「备份」/「恢复」）不同，结构逐字相同。模块自包含属 refactor.md「单一职责」的合理解读，仍属 judgement call。〕
- Finding (P2, judgement call): 魔数 — `service.py` `_database_integrity` 的 `stream.read(20)[18:20] != b"\x01\x01"`（SQLite header write/read version）无命名常量无注释；同 diff 内 `publish_directory` 的 renameat2 魔数有注释，风格不一致。
  〔聚合者已验证：`service.py:92`。〕
- Finding (P2, judgement call): `storage/schema.py` docstring 仍是「配置事实的 SQLAlchemy Core 元数据」，已含制品三表，过时。
  〔聚合者已验证：`schema.py:1`。〕

无成文标准硬违规。

## Spec

### 审查范围与证据来源说明

我没有 shell 工具，无法执行 `git diff main...HEAD` 或 `gh issue view`。已用 `watchdog_diff` 确认工作区与 HEAD `a09c3cc` 一致，因此按 HEAD 最终状态审查；spec 依据 `.scratch/a3-tracer-bullets/issues/01–06`（#30–#35 正文的本地镜像，含三条裁决评论的效力说明）与 `docs/contracts/`、`docs/verification/offline-evidence.md` 交叉核对。**父票 #29 正文（User Stories 1–42、root help 禁止子串）本地不可得，未逐项核对**；逐 hunk 差异（如「旧 migration 保持原字节」）仅能经 `scripts/a3_scope.py` 固定哈希绑定间接确认。

### Review

- **Correct**（按子票验收判据抽查，均符合）：
  - #31：`artifact_contract.py` 冻结五 kind/角色、规范 JSON 身份、`blob_relative_path` 布局 v1；`blob_store.py` 分段写入→`0o400`→fsync→不覆盖 `os.link`；`database.py` 单事务 `BEGIN IMMEDIATE` DDL+stamp、WAL 仅 upgrade 入口、五类受控原因；migration 仅 CREATE TABLE/INDEX，无 kind/role DB CHECK。
  - #32：`publish_artifact` 全员发布后短事务登记；`tests/extraction_support.py` 管道握手无 sleep。
  - #33：`service.py` 在线 backup API、副本转 DELETE 后才哈希、`renameat2(RENAME_NOREPLACE)` 保护预占位；`files.py:read_manifest` 拒 FIFO（a09c3cc）；`test_backup_service.py:47` 含主文件负对照与未提交事实排除、快照后新提交属下批。
  - #34：`restore.py` 目标规则/隐藏同级 staging/发布前复查；`test_restore_service.py:51` 撤销原根后新进程查询、字节一致、DELETE 头 `0x01 0x01`、显式 `db upgrade` 回 WAL。
  - #35：`a2_full_acceptance.py:380` 追加 A3 `required=True, dependencies=("A1","完整 A2")`；A2-01 仍非必需；`stage_a_verified/live_verified` 恒 false；固定用例计数不动态生成。
  - 未发现按 extraction 物理目录/阶段指纹旁路、backup_runs、模型调用或导入 CLI 等 spec 外行为。

- **Fixed**：无（只读审查，未修改）。

- **Finding**：P2——镜像 spec 未经 GitHub 原文核对，若 `.scratch` 镜像与线上 issue 有出入，本结论需复核；建议 supervisor 用 `gh issue view 29 --comments` 抽验三裁决评论与 #29 正文。此外 P2：#29 正文级裁决（root help 禁止子串、Decision 14–21 全表）未独立核对。
  〔聚合者已补验：GitHub 原文取回 #29 全部评论；子票镜像与线上正文一致（#30–#35 正文经 `gh issue view` 比对无出入）；父票级高风险项——root help 无 `run-due`、`<backup-batch>` metavar、术语词条、README 提示、restore help 副作用说明、a302 纯 CREATE、A3 组 required、`stage_a_verified`/`live_verified` 恒 false——逐项通过。两条 P2 由聚合者验证关闭。〕

- **Merge verdict**: OK with notes。

## 汇总

- **Standards 轴**：5 项发现（全部 P2 judgement call，0 项成文标准硬违规）；轴内最重：安全路径校验双实现（`BlobStore._path` 与 `controlled_path` 形状不同的重复安全逻辑）。
- **Spec 轴**：0 项需求级偏差；2 项 P2 证据来源保留意见，均已被聚合者补验关闭；轴内无遗留最重问题。

两轴分开汇总，不做跨轴排序。

## 修复核实记录（2026-10-17，关联 #29、#31、#33、#34、#35）

以上审查原文保留。本轮逐项对照当前代码、ADR-0027、制品/备份恢复 Contract 与
父票裁决核实：Standards 的五条建议均合理，全部采纳；它们仍是可维护性判断
（judgement call），并非五项成文标准硬违规或已复现的功能 Bug。

| 原建议 | 采纳依据与具体处理 |
| --- | --- |
| 目录 fsync 重复 | 相同的打开目录、fsync、finally 关闭描述符应共用。提取到 `storage/filesystem.py::sync_directory`；BlobStore 与备份文件操作复用，原目录创建权限与持久化调用时序保留。 |
| 安全路径约束双实现 | 安全规则应集中维护，避免后续两边漂移。提取 `storage/filesystem.py::controlled_path`：逐组件拒绝链接及空、`.`、`..` 路径段；支持调用者逐级创建父目录。BlobStore 仍从哈希推导路径、仅解析一次数据根，备份保留自己的入口；两者分别映射回 `ArtifactReason.UNSAFE_PATH` 与 `BackupReason.UNSAFE_PATH`，storage 不反向依赖 backup/config。 |
| CLI 脱敏与成功摘要重复 | 提取仅供备份/恢复使用的 `backup/cli_support.py`，共用参数异常脱敏、未知命令处理与摘要输出；各命令仍提供原中文帮助和具体错误指引、延迟加载 I/O 服务，成功/失败退出码维持 0/2。没有引入通用 CLI 框架。 |
| SQLite 文件头魔数 | `backup/service.py` 用命名常量说明偏移 18/19 分别是写/读版本，20 字节为所需头部前缀；注释说明 1=rollback、2=WAL。仍只接受两个版本字节均为 1 的独立数据库副本，未修改校验行为。 |
| schema 模块说明过时 | `storage/schema.py` 的 docstring 改为「配置事实与不可变制品登记的 SQLAlchemy Core 元数据」，与现有表职责一致。未新增或修改 migration。 |

Spec 轴两条证据来源保留意见已被原审查聚合者补验关闭，本轮再次确认无需产品修复：
重新取得 GitHub #29 正文及三条裁决评论，与之前实现使用的父票正文/评论逐字比较一致；
核对原 a201 migration、旧 A2 support 和 A1 help 固定测试，相对 main 均无改动。
父票涉及的 root help 禁止子串、六段帮助、批次 metavar、领域词条、README 配置保管
提示、restore 写入副本/staging 说明、a302 仅追加建表/索引、A3 必需组和保守验收标记
仍符合要求。这是证据核实，不是新增 live 或 NAS 验收。

两份 Contract 追加共享模块职责说明。schema 的说明字节变化同步更新 A2-01、完整 A2
固定源码绑定；A3 逐项重绑本次受影响源码及完整 A2 scope，并显式登记两个新共享模块。
原固定测试、用例计数、冻结契约、制品/备份格式及身份算法、旧 migration 均未改动。
本轮是无公共行为变化的局部重构，沿用既有公共服务、真实 CLI/进程和 wheel 测试，
没有新增与内部函数形状绑定的镜像测试。

验证结果在下文追加；完整离线门槛另在提交后的干净提交上执行，以最终交付的同次
`verification-runs/<run_id>.a3.json` 为准。尚未执行真实 NAS、外部模型或来源 live 验收；
hard-link 与 Linux `renameat2(RENAME_NOREPLACE)` 的既有文件系统要求保持不变。

### 提交前实测

- 首轮公共存储/备份/恢复/帮助回归：201 passed。
- 下列扩展子集覆盖实际改动及 A2/A3 绑定判定：310 passed（45.65s）。
- `uv run --offline --locked ruff check src scripts`：通过。
- `uv run --offline --locked ruff format --check src scripts`：82 files already formatted。
- `uv run --offline --locked mypy`：Success，193 source files。
- `git diff --check`：通过；当前分支为 `integration/issue-29-a3`。

```bash
uv run --offline --locked pytest -q \
  tests/test_artifact_contract.py tests/test_artifact_store.py \
  tests/test_extraction_artifacts.py tests/test_storage_migrations.py \
  tests/test_backup_service.py tests/test_backup_integrity.py \
  tests/test_backup_failures.py tests/test_backup_cli.py \
  tests/test_backup_wheel.py tests/test_backup_architecture.py \
  tests/test_restore_service.py tests/test_restore_failures.py \
  tests/test_restore_cli.py tests/test_cli_help.py \
  tests/test_a3_acceptance.py tests/test_a3_combination.py \
  tests/test_a3_test_receipt.py tests/test_a3_entry.py \
  tests/test_a2_acceptance.py tests/test_a2_full_acceptance.py
```
