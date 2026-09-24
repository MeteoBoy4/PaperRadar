# Issue #16 代码审查：A2-01 从 Profile 配置生成可跨进程读取的不可变快照

> 以下 Standards / Spec 为原审查时的发现；逐条复核与后续处理记录见文末的
> “复核与处理记录”。

- 审查范围：`HEAD~3..HEAD`（已验证恰好三笔提交，固定点 `c531017`）：

  ```
  060e2ba fix(config): parse common YAML numeric scalars strictly
  ae47918 fix(config): address Issue #16 review findings
  6529b74 feat(config): add immutable Profile snapshots and migration (#16)
  ```

- 规格来源：GitHub Issue #16 正文（13 条 Acceptance criteria）与全部 comments；父票 #15 Decisions 2–9、15–17、补充一、补充二、已确认的版本标签规则。
- Standards 依据：AGENTS.md、CONTEXT.md、docs/agents/domain.md、相关 ADR（0006/0008/0018/0023 等）、docs/contracts/ 与 Fowler smell 基线。
- 审查方式：只读双轴独立审查（Standards / Spec 两个并行子代理），关键发现已经主代理抽查复核（`scripts/check-offline`、`storage/database.py:21`、`config/__init__.py` 均与报告一致）。未修改代码、未创建 commit、未触碰 Issue。

## Standards

**工具基线**：ruff、mypy strict、pytest 全部通过（420 passed）；wheel 已含 migrations；两个 fix 提交均带回归测试。**未发现硬性违规**：SQLite 唯一事实源、版本字节不可变、同输入幂等（重编译不刷新 `created_at`）、`BEGIN IMMEDIATE` 原子提交与回滚、中文 CLI、help 无副作用、错误脱敏不回显输入、离线测试（deny_network）、lockfile 同步、文档同步（CONTEXT.md/README/intent/契约文档）均已落实并有测试。以下为判断性发现。

**(b) 基准 smell 与偏好级标准偏离**

1. **Magic string 作打开模式** — `storage/database.py:21` `open_database(path, *, mode: str)`，调用点散布 `"ro"/"rw"/"rwc"` 字面量（`config/service.py:68,84,108`、`tests/test_config_service.py:135`）。依据 AGENTS.md 编码流程「优先使用明确的领域类型和受控 enum / reason，避免 magic string」（偏好级）；既有模块（ContractName、OutputKind）全部用 StrEnum。影响：拼错模式要到运行时才暴露。最小修复：改为 `Literal["ro","rw","rwc"]` 或小 StrEnum。

2. **阶段名未受控** — `config/compile.py:108` 起 `stages` 以六个裸字符串（`"boundary"`…）为键，`config/cli.py:36` 与测试按下标消费。`MissingReason` 已用 StrEnum，阶段名同样是领域受控词汇却未给类型。Primitive Obsession（判断性）。修复：加 `StageName` StrEnum。

3. **重复记录类型** — `config/compile.py:50` `Material` 与 `storage/records.py:9` `VersionRecord` 字段及 `raw_sha256` 完全相同；`sha256` 在 `identity.py:21`、`records.py:17`、`repository.py:169` 三处重复。records.py docstring 说明是有意保持 storage 不依赖 config（架构测试强制），属有依据的重复，仅提示后续新增材料种类时两处需同步。判断性。

4. **Middle Man** — `config/__init__.py:10-28` 四个一行转发函数用函数内 import 包装 service；既有 `contracts/__init__.py`、`screening/__init__.py` 均为顶层直接再导出。若延迟加载是为避免 CLI help 引入 SQLAlchemy，应写进 docstring，否则改回急切导出与仓库惯例一致。判断性。

5. **死防御与冗余** — `config/service.py:144` `isinstance(profile, Profile)` 永真（`validate_yaml_bytes[T]` 必返回 T）；`:152` `json.JSONDecodeError` 是 `ValueError` 子类，元组中冗余；`:57` 与 `:136` 重复出现 `("profile","profile")` 键对，宜提取常量。琐碎清理。

6. **兜底 `except Exception`** — `storage/database.py:89` 把任何异常（含迁移脚本 bug）统一报成「请检查路径和权限」，与「错误信息应说明可操作的具体原因」有张力。判断性：边界翻译可保留，但消息不应预设原因。

7. **REVISION 双写** — `storage/database.py:17` 硬编码 `a201_profile_snapshot`，与迁移文件内 `revision` 重复；未来每次 migration 需同步两处（mini Shotgun Surgery）。可从 Alembic `ScriptDirectory` 取 head。判断性。

8. **占位词汇分歧（仅提示）** — `config/schema.py:97` 仅认精确 ASCII `"..."` 为 placeholder，而 `screening/text.py:5` `EXPLICIT_PLACEHOLDER_TEXTS` 含 `…`、`-`、`占位` 等。新契约文档已明确声明此差异（`…` 算 configured），属有意且已记录，不建议本票改动。

另注：`runtime_config_snapshots.created_at` 与 CONTEXT.md「快照记录版本引用、原始哈希和编译值」的枚举略有出入，但属持久化审计元数据且契约文档已说明，视为可接受。

## Spec

### (a) 缺失 / 部分实现

**1. 补充二 #38（A2 证据与 check-offline 组合）完全缺失 — 中优先级。**
Issue 范围行：「补充二 23、28、31–38、40–46」；#38 要求「A2 结论写到 `verification-runs/<run_id>.a2.json`，固定范围放在 `scripts/a2_scope.py`…`check-offline` 只在 A1 与 A2 结论都通过时返回 0；它的 `--help` 和 `docs/verification/offline-evidence.md` 同步说明」。实际：`scripts/check-offline:27` 仍只执行 `scripts.a1_acceptance`，`:12` help 仍称只产出「独立 A1 验收结论」；`scripts/a2_scope.py` 不存在；`verification-runs/` 无任何 `.a2.json`；`docs/verification/offline-evidence.md` 未更新（含「RuntimePlan 现对应 RuntimeConfigSnapshot」的注明也缺）。影响：仓库「完整离线验证」通过不代表 A2-01 行为通过，A2 新依赖版本也无证据落点。最小修复：新增 `scripts/a2_scope.py`（覆盖 5 个新测试模块与 config/storage 源文件哈希），产出 `.a2.json`，改 `check-offline` 为双结论并同步 help 与文档。

**2. 补充一 #20 要求的投影依赖矩阵未写入契约 — 低优先级（部分）。**
原文：「配置 Contract 文档：……**投影依赖矩阵**（每类配置 → 进入哪些阶段投影 / 基线 / 都不进），它同时是 diff 隔离测试的对照权威」。`docs/contracts/runtime-config.md:71-77` 只说投影「由后续 A2 票实现」，无逐类矩阵；`compile.py:28-42` 的 `MissingReason` 只在代码里隐含阶段→槽对应。最小修复：在契约文档补一张逐类矩阵（本票可只列 profile → boundary/value/reuse/read，其余类标「都不进」）。

**3. 测试小缺口 — 低优先级。**
补充二 #28「每种情况各配一个失败用例」：`yes`/`on` 保持文本的行为无用例（`tests/test_config_validation.py:35-53` 覆盖重复键/别名/合并键/tag/多文档/数值版本/非有限浮点，独缺此项）。AC1「未初始化…返回中文原因和退出码 2」：库文件存在但无 `alembic_version` 表的路径（`database.py:61-62`）无用例。最小修复：各加一条用例。

三点评论确认：① 包络规则（`runtime-config.md:29-31`、`compile.py:75`）✅；② selector 缺失/null → unconfigured、可存 not_ready 且已写入契约（`service.py:50-51`、`runtime-config.md:23`、`test_config_service.py:93`）✅；③ 精确 ASCII `...`、文档写明「占位只能为空或精确的 ...」、U+2026 视为已填写（`schema.py:99`、`runtime-config.md:37-38`、`test_config_validation.py:95-109`）✅；唯模型槽固定词（补充二 #31 的三个 REQUIRED token）未在契约中预留词表，后续模型票需补。

### (b) 超范围实现

无发现。`config diff`（#39）正确未实现；CONTEXT/README/draft 改动均对应 #45/#46/补充一 #2；无 V2 能力混入。

### (c) 实现错误

无发现。已重点核查：CLI 三入口显式参数 + 退出码 2 + 中文原因（`config/cli.py`）、ro/rw/rwc 打开模式（`database.py:21-32`）、`BEGIN IMMEDIATE` 单事务与回滚（`repository.py:62-129`，触发器注入失败测试证明）、FK/compare_metadata/WAL 仅 upgrade、严格 YAML（别名/合并键/重复键/多文档/非有限浮点/未知字段/凭据不回显）、规范 JSON 身份（`identity.py`，独立 A1 排版，NaN 拒绝，created_at 不入身份且重复保存不刷新）、历史 load 从库内原材料重校验并拒绝未知格式（`service.py:104-153`）、就绪词汇受控、纯编译层无 I/O 依赖、A1 固定哈希模块与哨兵零改动。新增 49 个测试（service/validation/architecture/cli）全部通过。

### 残留风险

WAL 库以 `mode=ro` 打开且存在未恢复 `-wal` 时的边缘行为未测；并发竞争的完整验收由 A2-09 承接（约定范围内），本票已提供原子性与唯一约束。

## 总结

Standards 轴：0 项硬性违规、8 项判断性发现（最重：`open_database` 打开模式用裸字符串，偏离 AGENTS.md 受控 enum 偏好，错误仅运行时可发现）。Spec 轴：3 项缺失/部分实现、0 项超范围、0 项错误实现（最重：补充二 #38 的 A2 证据/check-offline 组合完全缺失，仓库离线验证尚不代表 A2-01 通过）。

## 复核与处理记录

本节记录对上述建议的核实结果。原审查内容保留，便于追踪问题与修复依据。

| 原发现 | 结论与处理 |
| --- | --- |
| Standards 1：打开模式 magic string | 合理。改用 `DatabaseMode` 受控枚举，调用方不能再传任意字符串。 |
| Standards 2：阶段名未受控 | 合理。增加 `StageName`，快照阶段映射与 CLI 使用受控名称。 |
| Standards 3：重复记录类型与 SHA-256 | 保留。`Material` 属于纯编译层，`VersionRecord` 属于存储层；合并会重新引入 config/storage 双向依赖。两个边界各自用原始字节计算 SHA-256，现有架构测试守护依赖方向。 |
| Standards 4：Middle Man | 部分合理。`config/__init__.py` 已说明延迟导入目的：`--help` 不能加载可能触及数据库/网络标准库的存储实现。保留公共服务入口的轻包装。 |
| Standards 5：死防御与冗余 | 合理。删除永真的类型判断和重复异常类别，集中 Profile 登记键。 |
| Standards 6：兜底异常 | 部分合理。迁移入口仍把意外异常转为受控错误，避免 CLI 泄漏原始异常；提示改为检查数据库状态与迁移脚本，不再预断为路径权限错误。 |
| Standards 7：revision 双写 | 合理。运行时从 Alembic 包内脚本读取唯一 head；A2 固定验收范围另记录预期 revision，以便有意迁移后更新验收。 |
| Standards 8：占位词汇差异 | 不采纳修改。Issue #16 的确认评论明确 Profile 仅认精确 ASCII `...`；Screening 的宽词表用途不同。 |
| Standards 附注：`created_at` | 保留。它是与语义身份分离的审计时间，不进入快照哈希，重复保存不刷新。 |
| Spec 1：缺少 A2 结论 | 合理。新增固定 A2 范围和 `.a2.json`，绑定同次证据与 A1 结论；`check-offline` 只在两份结论均通过时返回 0。同步帮助和证据文档，A1 既有格式与固定测试哈希不改。 |
| Spec 2：缺少投影依赖矩阵 | 合理。契约文档补充后续投影依赖矩阵，明确本票尚不生成投影。拒绝“其余类都不进投影”的简化写法，因为父规格要求主题、模型、提示词等在后续进入相应投影。 |
| Spec 3：测试缺口 | 合理。新增 `yes`/`on` 保留文本及既有未迁移数据库返回中文退出码 2 的回归测试。 |
| 模型槽占位固定词提示 | 文档预留三个受控 token；本票的非空模型选择仍明确拒绝。 |
| WAL 只读边缘与并发风险 | 作为范围限制记录。并发完整验收由 A2-09 承接；本票维持只读连接、原子写事务及离线 SQLite 验证，不扩展后续流程。 |

处理后的 A2-01 独立结论只证明本票固定范围。完整 A2、阶段 A、真实来源与自动
全文精读仍未验收。以下人工检查入口未作为本次处理依据，也未执行。

## 人工针对性检查入口

以下入口可在不改动代码的前提下，对本 diff 的变更范围和 Issue #16 各条 AC 做人工抽查。通用入口：

- **变更范围**：`git log HEAD~3..HEAD --oneline`（应恰好三笔）、`git diff HEAD~3...HEAD --stat`、逐文件 `git diff HEAD~3...HEAD -- <path>`；A1 零改动可用 `git diff HEAD~3...HEAD -- tests/test_a1_acceptance.py contracts/ scripts/a1_scope.py`（应为空）确认。
- **整体回归**：`uv run pytest tests/test_config_service.py tests/test_config_validation.py tests/test_config_cli.py tests/test_config_architecture.py -v`（本票新增 49 例）；`./scripts/check-offline` 跑完整离线验证——但注意它当前只产出 A1 结论（见 Spec 发现 1），通过 ≠ A2-01 验收通过。

按 AC 的针对性入口（在临时目录操作，避免污染仓库）：

- **AC1（CLI 入口 / 退出码 2 / 只有 upgrade 建库）**：空目录下 `uv run paper-radar config check --settings 不存在.yaml --database /tmp/x.db; echo $?` → 应为中文原因 + 退出码 2 且 `/tmp/x.db` 未创建；`uv run paper-radar db upgrade --database /tmp/x.db` 连跑两次验幂等；`uv run paper-radar config compile --settings examples/config/settings.yaml --database /tmp/x.db` 成功；手工 `sqlite3 /tmp/x.db "UPDATE alembic_version SET version_num='zzz_future'"` 后再 check → 应拒绝（未知/未来 revision）。脱离仓库执行：`uv build` 后将 `dist/*.whl` 装入临时 venv，在任意 cwd 运行上述命令。
- **AC2（约束真实生效）**：`sqlite3 /tmp/x.db ".schema"` 与 `PRAGMA foreign_key_list(...)` / `PRAGMA index_list(...)` 查外键与唯一约束；`PRAGMA journal_mode;` 确认 WAL 只在 upgrade 后设置。
- **AC3/AC4（selector、未配置表示、占位判定）**：复制 `examples/config/`，分别构造：settings 缺 `profile` 键、显式 `profile: null` → check 应报 unconfigured 且 compile 可存 not_ready 快照（评论确认②）；Profile 某段改为纯空白或精确 `...` → 对应槽 placeholder；改为 `…`（U+2026）→ 应算 configured（评论确认③）；改 Profile 内嵌 `version` 与 selector 不一致 → 失败。
- **AC5（严格 YAML）**：手工构造含重复键、别名/锚点、`<<:` 合并键、`!tag`、多文档（`---`）、`yes/on`、日期样文本、`.nan/.inf`、未知字段、内联 `api_key` 的 settings/profile 逐个喂给 check → 应各自以中文受控原因失败，且错误中不含有输入值；合法 Profile 中的日期文本（如「2024 年起」）不应被误禁。
- **AC6/AC7（版本不可变、快照身份）**：compile 后仅改 Profile 注释/空白再 compile 同版本 → 拒绝；同字节重复 compile → 同一快照 ID；把同一输入复制到另一目录、换新数据库各 compile 一次 → 身份相同；`sqlite3 ... "SELECT snapshot_id, created_at FROM runtime_config_snapshots"` 在重复 compile 前后对比 → 旧记录 `created_at` 不刷新。
- **AC8（跨进程 load）**：一个进程 compile，另一个进程 `uv run python -c "from paper_radar.config import load_config_snapshot; ..."` 读旧快照；手工 `UPDATE` 库中保存的原材料字节 → load 应受控报错而非静默重哈希；改坏/删除磁盘原文件 → 旧快照 load 不受影响，新 compile 失败。
- **AC9（就绪词汇）**：check 输出只出现 configured/unconfigured/placeholder 与 ready/not_ready 及受控缺项原因，无「校准就绪」类表述。
- **AC12（help 无副作用）**：在空 HOME/临时 cwd 下 `uv run paper-radar --help`、`db --help`、`config --help`、`config check --help` → 退出码 0、全中文，且目录中不产生任何文件。
- **AC13（边界）**：`uv run pytest tests/test_config_architecture.py`（纯编译层不依赖 YAML/DB/CLI、storage 不反向依赖 config 由该模块强制）。

**无法直接验证 / 需说明的项**：

- 补充二 #38 的 `.a2.json` 证据与 `check-offline` 双结论：实现缺失（Spec 发现 1），暂无入口，A2-01 的机器可读验收结论目前不存在。
- 并发 compile 的原子性：约定由 A2-09 验收，本票仅有唯一约束与 `BEGIN IMMEDIATE` 兜底，无并发验收入口。
- WAL 库 `mode=ro` 打开且存在未恢复 `-wal` 的边缘行为：无测试覆盖，只能手工构造（upgrade 后杀掉进程保留 `-wal`，再 check）观察。
- 错误信息「不回显输入值」：测试覆盖了受控错误类型，但要穷举所有失败路径仍需人工抽查若干畸形输入的实际 stderr。
