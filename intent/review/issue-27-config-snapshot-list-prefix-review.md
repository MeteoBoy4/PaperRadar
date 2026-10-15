# Issue #27 代码审查：只读列出配置快照并支持唯一短 ID 比较

- 审查范围：`HEAD^..HEAD`（固定点 `9508740b323243af8e53eb04ea85ca9883637ad4`，已验证恰好一笔提交、diff 非空、993 行新增 / 20 行删除）：

  ```
  865845a feat(config): list saved snapshots and resolve unique references (#27)
  ```

- 规格来源：GitHub Issue #27 正文（What to build、13 条 Acceptance criteria、Blocked by #23）与全部 1 条 comment（前缀唯一性按解析时全库判定；前 63 位全相同时列表直接展示完整 64 位 ID，不得截断或报错；文档注明前缀仅反映查询时刻）。
- Standards 依据：AGENTS.md、CONTEXT.md、docs/agents/domain.md、docs/contracts/（config-snapshots.md、config-projections.md、runtime-config.md）、docs/adr/0023 与 Fowler smell 基线。
- 审查方式：只读双轴独立审查（Standards / Spec 两个并行子代理）；全部关键发现已由主代理逐一抽查复核（`config/snapshot_queries.py:23-24,27-64,102-149`、`storage/snapshot_queries.py:12-37`、`snapshot_cli.py:11-75`、`service.py:54-72,426-495`、`scripts/a2_scope.py` diff、README.md:112、config-snapshots.md:3、CONTEXT.md 无「档案库」词条，行号与内容均与报告一致）。未修改代码、未创建 commit、未触碰 Issue。
- 工具基线（主代理实际运行）：`uv run --offline --locked pytest tests/test_config_snapshot_queries.py tests/test_config_snapshot_cli.py tests/test_config_snapshot_architecture.py tests/test_config_diff_cli.py tests/test_config_diff_service.py tests/test_config_projections.py tests/test_config_projection_architecture.py -q` → 132 passed；`./scripts/check-offline` 全绿（lockfile/format/lint/types/tests/contracts 及 A1、A2-01 结论均 passed，run_id `87a2edf87aee4d199c43e09137c0e9c5`）。Spec 子代理另实测：`snapshots list --help`/`diff --help` 返回 0 且不产生文件，非法引用/缺库返回 2 且缺库路径未生成。

## Standards

### (a) 成文标准违反（硬违规）

**无。** 逐项核对通过：

- **核心不变量**：列表与引用解析全程 `DatabaseMode.READ_ONLY`（`config/snapshot_queries.py:79,122`），不建库、不迁移、不登记、不写缓存；测试断言数据库字节不变、重复运行输出一致；无静默合并、无单一 lifecycle/status 字段。
- **数据与版本控制**：无 migration、无新增持久化字段（复用 `runtime_config_snapshots`/`snapshot_version_refs`）；Frozen Contract、投影/基线指纹未触碰；公共 diff 服务仍只收完整 64 位 ID（`service.py` 的 `_SHA256` 校验未变）。
- **Calibration 安全**：摘要只含 ID/时间/声明版本，不暴露 Agent 结果、不分级、不启用精读；测试断言 Profile/Prompt 正文不外泄（ADR-0020、ADR-0023）。
- **LLM 与证据规则**：无模型路径；错误均为受控中文原因，不回显输入值、原始异常或 SQL 参数（`config/snapshot_queries.py:117-120,143-145,148`）。
- **依赖与外部服务**：无新依赖；测试走 `deny_network`/`deny_external_io` 哨兵与真实临时 SQLite。
- **面向用户的行为**：CLI 全中文；退出码 0/2 与契约一致；`--help` 路径只 import typer/errors，存储层均为函数内延迟导入，`test_new_help_is_safe_with_all_external_io_denied` 覆盖。
- **文档维护**：新增 `docs/contracts/config-snapshots.md`，同步 README、runtime-config、config-projections；`scripts/a2_scope.py` 三个被改文件哈希已更新（与 `git show` 核对一致），scope 不扩为文档明示的有意决定。
- **模块解耦/项目可读性**：依赖方向为 config→storage（与 `service.py` 既有方向一致），storage 不反向依赖；`snapshot_summary` 为纯类型；`test_config_snapshot_architecture.py` 固化 compile/projections/diff/summary 的无 I/O 约束。

### (b) 基线 smell（判断性发现）

**B1. Repeated Switches — kind→合法名称集合的封闭映射出现第二处**
- 位置：`src/paper_radar/config/snapshot_queries.py:48-64`（`_version`）；既有编码在 `src/paper_radar/config/service.py:54-72,426-495`（`_PROMPT_NAMES`/`ContractName` 映射/`ADAPTER_NAME` 分支）。
- 依据：Fowler Repeated Switches——同一封闭名称集合（ADAPTER→`ADAPTER_NAME`、PROMPT→`PromptName`+`SYSTEM_PROMPT_NAME`、CONTRACT_*→`ContractName`）按 kind 分派的逻辑形状在两处各自维护。
- 实际影响：未来新增材料种类或名称时需双处同步，漏改即静默分歧（列表摘要校验与 load/diff 校验可接受不同名称集）。
- 最小修复：抽一份共享的 kind→合法名称映射常量供两处调用；或接受现状（契约集合已封闭，严重度低），但应在注释中互相指引。

**B2. Data Clump — `versions` 位置三元组跨层传递**
- 位置：`src/paper_radar/storage/snapshot_queries.py:16`（`versions: tuple[tuple[str,str,str], ...]`），由 `config/snapshot_queries.py:96` 以 `_version(*version)` 位置解包。
- 依据：Fowler Data Clump——(kind, name, declared_version) 三字段恒定同行，却用裸三元组跨越 storage→config 边界。
- 实际影响：字段顺序错位只能靠 `_version` 内部的 `ValueError` 兜住，类型检查器无法发现 `(kind, name)` 颠倒；读者须对照两处才能确认语义。
- 最小修复：storage 侧定义 frozen `VersionRefRecord(kind, name, declared_version)` 小类型替代三元组。

**B3. 冗余显式事务 — `exec_driver_sql("BEGIN")`（轻微）**
- 位置：`src/paper_radar/storage/snapshot_queries.py:37`。
- 依据：SQLAlchemy 2.x 连接 autobegin 已使两条 SELECT 同处一个事务/读视图；与 `save_snapshot` 的 `BEGIN IMMEDIATE`（有写锁语义）不同，此处的显式 `BEGIN` 不提供增量保证，只提前了事务起点。
- 实际影响：无功能错误；但「BEGIN 才有同一读视图」的注释暗示了错误的并发语义，可能误导后续维护者照搬。
- 最小修复：删除该行并把注释改为「同一连接的 autobegin 事务保证两条 SELECT 共享读视图」；或保留并改写注释说明其为防御性显式化。

**B4. Mysterious Name — 「档案库」未入领域词汇表**
- 位置：`README.md:112`、`docs/contracts/config-snapshots.md:3,48`、`docs/contracts/runtime-config.md:14`、`src/paper_radar/config/cli.py:41`、`src/paper_radar/config/snapshot_cli.py:13,52`。
- 依据：docs/agents/domain.md 要求使用词汇表术语；CONTEXT.md 中无「档案库」词条（已 grep 确认）——它是有意引入的新领域说法（数据库选择档案库、快照引用选择历史配置），但未登记。
- 实际影响：术语与「数据库」混用，后续文档/CLI 文案可能漂移出第三种说法；Agent 仅凭 CONTEXT.md 无法对齐该概念。
- 最小修复：CONTEXT.md 增补「档案库」条目（界定其即指定 `--database` 的 SQLite 档案），或在全部文案中回退为「数据库」。

**B5. Duplicated Code — `SNAPSHOTS_HELP` 同文两任（轻微）**
- 位置：`src/paper_radar/config/snapshot_cli.py:23-24`（组 help）与 `:46`（list 命令 help = `SNAPSHOTS_HELP` + 增量段落）。
- 依据：Fowler Duplicated Code——组级与命令级 help 展示同一段全文，typer 的 help 展示场景不同（组列表摘要 vs 命令详情），同文复用使组列表输出冗长。
- 实际影响：仅展示层面；`config snapshots --help` 与 `config snapshots list --help` 几乎同样长，组层级失去摘要作用。
- 最小修复：组 help 保留一句话摘要，命令 help 保留全文 + 增量段落。

**抑制说明**：`config/__init__.py` 的延迟导入转发（模块 docstring 明示的既定模式，保障 `--help` 无 I/O）、engine 打开/异常包装块与 `service.py` 三处同款（既定事务边界写法）、`_SnapshotListCommand` 仿 `_ConfigDiffCommand`（A2 既定中文脱敏错误模式）、快照 ID 用 `str`（既有公共 API，issue 明示完整 ID 仍是权威身份）——均按「仓库标准优先于基线」抑制。

## Spec

### (a) 缺失 / 部分实现

**A1. 新模块未纳入 `a2_scope.py` 哈希绑定（观察级，非违规）**
- 位置：`scripts/a2_scope.py`（`REQUIRED_SOURCE_MODULES`/`REQUIRED_TEST_MODULES` 仅更新了 cli.py、config/__init__.py、config/cli.py 三个哈希，未追加 `config/snapshot_queries.py`、`config/snapshot_cli.py`、`config/snapshot_summary.py`、`storage/snapshot_queries.py` 与 4 个新测试模块）。
- 依据：#23 曾把 `projections.py`/`diff.py` 等新模块加入该清单（`HEAD~1:scripts/a2_scope.py:178,182`），本票未沿用此先例；AC12 原文只要求「新测试放入本票自有模块、保留 A1 固定测试哈希」，未强制绑定新模块，故属观察而非违规。
- 实际影响：后续这些新文件的字节漂移不会触发 `SCOPE_DRIFT`，A2 范围哨兵对本票交付物无感知。
- 最小修复：将 8 个新模块追加进对应清单并固定哈希；或在文件注释中显式说明不绑定的理由。

逐项核对：AC1–AC10、AC13 均有对应实现，无其他缺失。

### (b) 超范围实现

**无。** 逐项核对 issue 明确排除项：无人为名称/标签（`_version` 仅接受受控名称集合，`config/snapshot_queries.py:48-64`）、无 latest/current 别名（`:116-120` 拒绝非十六进制输入，测试含 `"latest"` 反例）、无跨数据库比较（单 `--database`）、无交互式选择（解析失败直接报错退出 2）、无激活入口与校准工作流（diff 输出沿用 #23 的「不判定变更等级或启用自动精读」）、无 `--json`、无 migration、无新持久化字段、不回改 #23 验收范围。`tests/config_snapshot_support.py` 的 `checkpoint` 等为纯测试工具。

### (c) 实现错误

**未发现。** 重点复核项均与规格一致：

- **前缀边界 8–63/64**：`_REFERENCE`/`_FULL_ID`（`config/snapshot_queries.py:23-24`）+ 64 位精确匹配（`:136-140`）正确；7/65 位、大写、非十六进制、空白均拒绝且错误文案不回显输入值。
- **comment 极端情况（前 63 位全同）**：`:33-44` `length` 升至 64 时 `snapshot_id[:64]` 即完整 ID，不截断不报错；`test_config_snapshot_queries.py:61-93` 用 `c*63+0/1` 固定碰撞验证，且展示值可经公共解析服务解析回原完整 ID。
- **排序**：`:102-110` 先按完整 ID 升序稳定排序，再按 `(有无时间, 时间)` 降序——同时间项保持 ID 升序、未记录项在最后且按 ID 升序；测试覆盖同一时刻两种时区写法（`+08:00` vs `Z`）的平局。
- **「未记录」**：`:67-73` NULL/空串 → `None`，CLI 显示「未记录」（`snapshot_cli.py:69`），不补写时间、不新增持久化字段。
- **零匹配/歧义**：`:142-145` 分别提示「未找到快照」/「补充字符」，均返回 2（子代理实测）。
- **同快照不同前缀仍走 #23 完整验证**：CLI 先 resolve 再调既有 `diff_config_snapshots`（`cli.py:207-213` 一带），不凭输入相同跳过验证；四种损坏形态（unknown_format/payload/material/reference）均穿透为受控失败 2。
- **退出码矩阵与只读语义**：实测 help=0、参数错/缺库/非法引用=2，缺库后目录为空；成功（含涉及校准的比较）=0 有测试断言；「是否涉及校准」不影响退出码。
- **测试覆盖（AC11/12）**：空列表、稳定排序、完整 ID、唯一前缀、混合输入、零匹配、歧义、非法格式、同快照不同前缀、损坏快照、缺库、只读副作用（字节级相等）、固定碰撞前缀歧义、列表前缀解析回原 ID、help 哨兵均在；#23 投影/基线回归保留且未重复实现算法测试；A1 固定测试哈希、外部 I/O 哨兵与四份冻结契约未触碰。
- **文档同步（AC13）**：README、config-snapshots.md（新）、runtime-config.md、config-projections.md 覆盖全部要求——「数据库选择档案库，快照引用选择其中的历史配置」、列表到比较完整示例、前缀仅反映查询时刻可能转为歧义、长期记录保留完整 ID、#23 原始接口与本票便捷层的区分、「不表示完整 A2 或阶段 A 已完成」。

**非违规观察**（规格未要求，不计 finding）：resolve 失败消息不指明是 before 还是 after 引用；WAL 库只读打开可能产生 `-shm/-wal` 边车文件，系 #23 既有 `open_database` 模式，非本票引入。

### 残留风险

- 本评审为静态核查加目标测试与 `./scripts/check-offline` 实际运行；live 行为（真实用户库上的长链路使用）未覆盖。
- 前缀歧义只能在新增快照后真实出现，测试以固定碰撞构造验证；真实库上前缀随时间失效的 UX 已被文档注明，但无运行时提醒机制（规格亦未要求）。
- 本票交付后，完整 A2 结论仍归 #25，校准变更工作流衔接属后续票。

## 总结

Standards 轴：0 项硬违规、5 项判断性 smell（最重：B1——kind→合法名称集合的封闭映射在 `snapshot_queries.py:48-64` 与 `service.py` 双处维护，新增材料种类时漏改即静默分歧）。Spec 轴：1 项观察级缺口、0 项范围蔓延、0 项实现错误（最重：A1——新模块未纳入 `a2_scope.py` 哈希绑定，范围哨兵对本票交付物无感知）。两轴无指向同一问题的发现，无需交叉说明。

## 实施方逐项核实与处理

本节针对实现提交 `865845a` 的上述报告追加核实结果，保留原始审查意见作为历史依据。
修正关联 Issue #27，不关闭 Issue，也不扩展后续 tickets。

| 建议 | 核实结论 | 本次处理 |
| --- | --- | --- |
| Standards B1：共享 kind → 合法名称集合 | 合理。历史加载有材料解码分派，列表只做摘要校验，两者职责不同，但合法名称集合应共享。 | 新建无 I/O 的 `config/material_names.py`，以不可变映射维护全部受控名称；load 和列表共用该映射。load 的解码分派保留，去除其中重复的名称集合判定，编译身份和合法输入不变。 |
| Standards B2：三元组改具名类型 | 合理。跨层三元组不便辨认字段含义，且均为 str 时类型检查不能识别换位。 | 存储层增加 frozen、slots、仅关键字构造的 `VersionRefRecord(kind, name, declared_version)`；列表通过具名字段读取，不再位置解包。没有新增持久化字段或 migration。 |
| Standards B3：删除显式 BEGIN | 拒绝删除。原报告把 SQLAlchemy 的逻辑 autobegin 与 sqlite3 驱动的实际事务混为一谈；当前连接默认使用 legacy transaction control，SELECT 不自动发出 BEGIN。 | 保留 BEGIN，并在代码、配置 Contract 中明确其用于固定两次查询的底层读视图，不称其为冗余或仅防御性写法。下文列出实测证据。 |
| Standards B4：登记“档案库” | 合理。该说法来自 #27 AC13 的明确要求，直接全部改回“数据库”会丢失规格要求的操作解释。 | 在 CONTEXT 的 Configuration 词汇组中定义为用户选择的一组历史快照和版本材料，注明选择不表示启用；不把 CLI 参数、路径或存储实现写入领域定义。 |
| Standards B5：拆分组与 list 的 help | 接受精简与分工，拒绝把组 help 缩成仅一句话。draft §8.1 要求每个命令组的帮助也包含参数、副作用、配额、常见失败、输出去向和示例。共享字符串本身不是逻辑复制，但原展示确实过长。 | 组帮助改为简短导航并保留全部必要说明；list 保留完整输出、前缀规则和比较示例。既有外部 I/O 哨兵继续验证所有 help。 |
| Spec A1：补充新文件哈希绑定 | 接受字节漂移哨兵的改进，不扩大 A2-01 的固定测试验收声明。原列表只更新三个入口，确实未单独绑定新增实现。 | 在 `REQUIRED_SOURCE_MODULES` 中绑定 #27 四个实现、四个测试/支撑文件及本次共享名称模块；按既有支撑文件模式，把新测试文件作为字节绑定输入。保留 `REQUIRED_TEST_MODULES` 五个固定模块、scope、Issue #16 及历史未覆盖声明，完整 A2 结论仍归 #25。 |

### B3 的依据与复现实验

SQLAlchemy 2.0 官方文档明确指出 sqlite3 legacy 模式不会为 SELECT 发出 BEGIN，
这会破坏重复读取的一致性保证；因此不能仅凭 SQLAlchemy 的 autobegin 状态判断
底层 SQLite 已开始事务。见 [SQLite legacy transaction control](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#legacy-transaction-mode-with-the-sqlite3-driver)。

本次使用项目 uv 锁定环境、真实 migration 创建的临时 WAL SQLite，以及既有
`open_database(..., mode=READ_ONLY)` 完成两个实验，没有修改用户数据库：

- 单独 SELECT 后，SQLAlchemy `in_transaction()` 为 True，底层 sqlite3
  `in_transaction` 为 False，`autocommit` 为 -1（LEGACY_TRANSACTION_CONTROL）；
  显式 BEGIN 后，底层 `in_transaction` 才为 True。
- 两个独立连接中，读连接第一次 SELECT 得到 `before`，写连接提交 `after` 后再次 SELECT：
  不显式 BEGIN 得到 `after`；显式 BEGIN 仍得到 `before`。两组均按预期断言通过。

因此保留该行是维护既有读视图保证，并非新增写事务或改变数据库连接策略。

### 其他观察与范围

resolve 错误未区分 before/after 是可选 UX，当前错误已有受控原因和操作指引，
不是 #27 缺陷，本次不新增输出行为。WAL sidecar 属于既有 SQLite 连接行为，
本次不修改它，也不引入会忽略 WAL 中已提交内容的 immutable 读取模式。
真实用户库与自动校准工作流未在本次验证范围内；前缀随新快照产生歧义的说明保留。

### 本次验证

实际运行结果：

- `uv run --offline --locked pytest tests/test_config_snapshot_queries.py tests/test_config_snapshot_cli.py tests/test_config_snapshot_architecture.py tests/test_config_diff_cli.py tests/test_config_diff_service.py tests/test_config_projections.py tests/test_config_projection_architecture.py tests/test_config_service.py -q`：145 passed。
- `uv run --offline --locked pytest tests/test_a2_acceptance.py -q`：3 passed。
- `uv run --offline --locked mypy`：126 个源文件通过；`ruff check` 通过；仓库规定的
  `ruff format --check src tests scripts` 通过；`git diff --check` 通过。
- `UV_CACHE_DIR=/tmp/paperradar-uv-cache ./scripts/check-offline`：退出 0，
  lockfile/format/lint/types/tests/contracts 全部 passed，独立 A1 和 A2-01 结论均 passed。
  本次 run_id 为 `44a7d3642f284f8798f4b1b355756d57`，证据保存在
  `verification-runs/44a7d3642f284f8798f4b1b355756d57{,.a1,.a2}.json`。
- B3 的两个独立连接实验通过，详见上节。

附加的无路径限制 `ruff format --check` 会检查 Markdown 内嵌代码，指出既有
`intent/draft.md` 若干 Python 代码块缺少空行；该文件本次未修改。
仓库完整离线入口的格式范围为 src/tests/scripts，该检查已通过；没有为本票顺手改写 draft。

上述完整证据对应本次代码修正完成后的提交前工作树；运行后只在本报告追加验证结果。
原报告开头的 `87a2edf87aee4d199c43e09137c0e9c5` 为另一 Agent 的历史审查运行，
不作为本次修正的验证结果。所有测试和实验均使用临时/合成材料，不依赖真实用户配置
或网络/模型调用，未运行真实用户库的 live 验收。
