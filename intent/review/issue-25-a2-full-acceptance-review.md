# Issue #25（A2-10：完整 A2 离线验收结论）三笔提交代码审查

- 审查日期：2026-10-15
- 固定点：`HEAD~3` = `00bd798d0ab48cee5c3ca33b2b61216a7d2f3a62`（已用 `git rev-parse` 验证可解析）
- 范围验证：`git log HEAD~3..HEAD --oneline` 恰好包含目标三笔提交，无多无少：
  - `84bdd71` Implement complete A2 offline acceptance evidence (#25)
  - `0716461` Require actual fixed test execution for A2 evidence (#25)
  - `7d164ba` Hand off acceptance entry without a module cycle (#25)
- diff 命令：`git diff HEAD~3...HEAD`；17 files changed，+2256/−35。核心新文件：`scripts/a2_full_acceptance.py`、`scripts/a2_full_scope.py`、`scripts/a2_test_receipt.py`、`tests/a2_full_support.py` 及四个新测试模块；修改 `scripts/a1_acceptance.py`、`scripts/a2_scope.py`、`scripts/check-offline`、`scripts/offline_evidence.py` 与若干文档。
- 规格来源：GitHub Issue #25 正文与唯一 comment（2026-10-15），及其点名的父 spec #15（Decision 17、Testing Decisions、DoD）与三条评论（补充一 #20、补充二 #36–38/45–46、版本标签规则）。
- 审查方式：Standards 与 Spec 两轴由两个独立只读子代理并行审查后聚合，两轴不混合排序。全程只读：未修改代码、未创建 commit、未对 GitHub Issue 做任何写操作。

## Standards

依据：AGENTS.md、`docs/agents/python-conventions.md`、`docs/agents/testing.md`、`docs/agents/cli-output.md`、`docs/agents/documentation.md`、`docs/agents/invariants.md`、CONTEXT.md，外加 Fowler 气味基线（仓库文档标准优先；工具已强制项跳过）。

### (a) 文档化标准违规（硬）

**A1. 新验收模块用裸字符串表达 reason code 与 status，偏离受控 enum 约定**
- 位置：`scripts/a2_full_acceptance.py:33-52`（`_HELP` 字符串键 + `_reason(code: str, ...)`）、`scripts/a2_full_acceptance.py:375-378`（`"passed"/"failed"/"incomplete"` 字面量）；`scripts/a2_test_receipt.py:77-85`（outcome 字符串）。
- 依据：`docs/agents/python-conventions.md`「用明确的领域类型和受控 enum / reason 表达状态与原因」。同一离线验收链路上的三个既有模块全部以 StrEnum 落实该规则：`scripts/offline_evidence.py:25-44`（`CheckStatus/CheckReason/OverallStatus`）、`scripts/a1_acceptance.py:51-64`（`A1ReasonCode`）、`scripts/a2_acceptance.py:27-36`（`A2ReasonCode`）。本次新模块是该链路唯一例外。
- 实际影响：`_reason(code: str)` 使错误 code 字符串对 mypy 不可见，唯一防线是失败路径上的 `_HELP[code]` KeyError；后续新增 reason 没有类型级检查点，与同链路词汇管理方式不一致。
- 最小修复建议：新增 `A2FullReasonCode(StrEnum)`（成员值与现字符串逐字相同，JSON 契约不变），status 复用 `OverallStatus` 或新立 enum；序列化点取 `.value`。缓解因素：`_HELP` 键集合在运行时起封闭作用，序列化输出不受影响。

### (b) 基线气味（判断题）

**B1. possible Duplicated Code / Data Clump — 回执六项计数字段四处重复**
- 位置：`scripts/a2_test_receipt.py:22-33`（`dict.fromkeys` 初始化）、`scripts/a2_full_acceptance.py:180-190`（校验键元组）与 `:196-203`（期望字典字面量）、`tests/a2_full_support.py:24-34`（测试工厂）。`("collected","passed","failed","skipped","deselected","incomplete")` 同一字段簇在本 diff 内出现 4 次。
- 依据：Fowler Duplicated Code（相同逻辑形状跨 hunk/文件重复）与 Data Clump（六字段总结伴出现）。三个文件均已 import `scripts.a2_full_scope`，共享无障碍。
- 实际影响：回执自称格式版本 1，键集却没有单点定义；将来增删计数项需四处同步，漏改一处会使插件与验证器静默分歧——对 fail-closed 验收代码尤其敏感。
- 最小修复建议：在 `scripts/a2_full_scope.py` 定义 `RECEIPT_COUNTERS: tuple[str, ...]`，四处引用；期望值由该常量构造。

**B2. possible Duplicated Code — git fixture 提交块逐字重复**
- 位置：`tests/a2_full_support.py:51-66`（`repository_copy` 内 `git init -q` / `git add .` / `git -c user.name=Fixture … commit -qm fixture`）与 `tests/test_a2_full_acceptance.py:310-325`（同一序列，仅变量名 `target`→`root`）。
- 依据：Duplicated Code。后者因只需部分文件不能整体复用 `repository_copy`，但提交块完全相同。
- 实际影响：fixture 的 git 身份（user、email、message）双处维护；只改一处会让两类入口测试的 fixture 身份悄悄分叉，而该身份参与 worktree 哈希核对语义。
- 最小修复建议：在 `tests/a2_full_support.py` 提取 `_init_fixture_repo(path)` 辅助函数，两处调用。

**B3. possible Divergent Change（轻微观察，不建议返工）**
- 位置：`docs/contracts/runtime-config.md` 首 hunk（现 415-417 行，#27 短前缀文档补登）与新增「完整 A2 验收边界」章节（422-435 行）——同一文件因两个不相关 issue 被改。
- 依据：AGENTS.md「改动范围以任务所需为界」；Fowler Divergent Change。
- 实际影响：PR 评审面略增；但旧行「不接受短 ID」与已交付行为矛盾，`docs/agents/documentation.md` 又要求公共契约文档同步，顺手修正可辩护。
- 最小修复建议：如严格拆分可独立为 docs commit；接受现状亦可。

### 已核查并抑制（仓库标准覆盖基线）

- `a1_acceptance.main` 的 `os.execv` 移交：7d164ba 明确记录的破除模块循环决策，docstring 已说明，非 Middle Man。
- 同一逻辑变更同步 README/三份 docs/intent：`documentation.md` 强制同变更同步，抑制 Shotgun Surgery。
- `_files` 空清单保护、`pytest_deselected` 钩子：均被固定范围验证实际使用，非 Speculative Generality。
- JSON 结论用 dict：全链路既有契约形态（A1/A2-01 相同），抑制 Primitive Obsession。

### Standards 轴独立验证声明

已抽查 scope 清单哈希与实际文件一致（10/10）；常量集合内部一致（A1∪完整 A2 测试模块并集 == `REQUIRED_TEST_CASE_COUNTS` 键集 == 63，无重复、计数全正）；入口链路（check-offline → a1_acceptance → execv → a2_full_acceptance）与文档一致；新测试全部离线（fake uv、tmp 库、I/O 哨兵）。未实际运行 `./scripts/check-offline`（会写证据文件，超出只读约束）。

## Spec

依据：Issue #25 全部 11 条 Acceptance criteria、唯一 comment 的三点厘清，及父 spec #15 被点名引用部分。

**Spec 轴未发现违反规格的 (a) 遗漏/部分实现、(b) 范围蔓延、(c) 错误实现。** 逐条判定如下（均通过）：

- **AC1（同次运行、共享 run_id、绑定实际证据哈希、不拼运行不继承历史）— 通过。** `scripts/a2_full_acceptance.py:396-431` 只调一次 `run_a1_verification`；`:321-322,362-370` 发布前复核三份文件实际 SHA-256；`tests/test_a2_full_entry.py:21-84` 断言六项检查只执行一次、四份文件同 run_id、预置历史 `historical.a2-full.json` 不被读取或覆盖。
- **AC2（独立 scope、身份、migration revision、格式版本、材料身份、依赖版本、未实施项；不存正文/凭据；真实临时库）— 通过。** `scripts/a2_full_scope.py:3-105` 独立 scope；`_migrated_revision`（`a2_full_acceptance.py:120-146`）在 `TemporaryDirectory` 真实建库 base→head 后读 `alembic_version`，无用户库参数；`tests/test_a2_full_acceptance.py:243-263` 验证未登记新 head 显式失败且不在外部路径留 sqlite3。
- **AC3（A2-01–A2-09 全纳入；缺陷不静默通过）— 通过。** 磁盘 63 个 `test_*.py` 全部在固定范围且计数匹配（子代理用 `pytest --collect-only` 逐模块实测）；`_test_execution`（`a2_full_acceptance.py:149-215`）逐模块核对六项计数；`test_real_skipped_suite_cannot_pass_complete_entry_even_when_pytest_returns_zero` 证明 pytest 退出 0 但全 skip 仍失败。
- **AC4（A1+A2 均过才返回 0；中断 incomplete；stage A/live 未验收并列未覆盖能力）— 通过。** `a2_full_acceptance.py:442` 退出码仅看 `a2_verified` 且以 A1 通过为前提；SIGTERM→`run_incomplete`→`status="incomplete"`（371-378）；`NOT_ASSESSED`（`a2_full_scope.py:88-105`）含阶段输入指纹、全量业务事实、doctor、备份恢复等 16 项，`stage_a_verified`/`live_verified` 恒 False。
- **AC5（#12 格式、A1 固定哈希与历史 not_assessed 不变；新依赖只记 A2；新测试入新模块；不改弱哨兵）— 通过。** `offline_evidence.py` format_version 仍为 1、`_DEPENDENCY_NAMES` 未变；`scripts/a1_scope.py` 不在 diff 中；`tests/deny_external_io/`、`tests/deny_network/` 不在 diff 中且字节哈希被新范围原样固定。
- **AC6（help 准确说明临时数据库且无副作用；两类哨兵分工）— 通过。** `scripts/check-offline:12` 写明「使用临时数据库，不操作用户数据库」，help 分支是纯 bash `cat`；`tests/test_a2_full_entry.py:87-113` 在空目录 + `deny_external_io` 下验证 help 零副作用；真实命令测试用 `deny_network`、help 用 `deny_external_io`（`tests/config_test_support.py:80`、`tests/test_a2_full_examples.py:61-90`）。
- **AC7（父 spec 与全部评论覆盖核对；固定期望不来自被测函数；不冒充校准/阶段 B）— 通过。** `docs/verification/offline-evidence.md` 新增「父规格与评论覆盖」表逐段映射；所有期望值是 `a2_full_scope.py` 人工登记常量，运行时只比对不重算；点名的九项覆盖主题均对应固定清单内既有测试模块。
- **AC8（文档交叉核对与布局修正收口）— 通过。** README、`runtime-config.md`、`config-projections.md`、`offline-evidence.md`、`intent/draft.md` §6 均已同步；未新增领域决策或改写父 Issue。
- **AC9（真实临时 SQLite、附回归与 CLI 集成测试、无网络/付费模型依赖）— 通过。** 新测试全部 `tmp_path` 真实 SQLite + `run_cli` 真实入口；`verification-runs/` 存在格式 2 的真实 `passed` 完整 A2 结论（如 `681583b04bbb4542ba53e80ba7ec7c35.a2-full.json`）与一票 `failed` 中间运行，证明失败会拒而非静默通过。
- **AC10（中文 help/错误；help 零副作用；错误只暴露受控字段）— 通过。** check-offline help 与 `_HELP` 全中文；`test_failed_migration_does_not_reveal_original_exception` 等断言 `PRIVATE_SECRET_MARKER` 不进入结论文件。
- **AC11（新测试入 A2 自有模块；保留 A1 哈希、哨兵与四份 v1 契约；零反向依赖）— 通过。** 新测试全在 `test_a2_full_*`/`test_a2_test_receipt` 新模块；四份 v1 契约未动且其 examples 副本字节被固定范围锁定。
- **Comment 三点厘清 — 全部通过。** ① `.a2.json` 与 `.a2-full.json` 同次共存，A2-01 五个固定测试哈希/scope/历史 `null` 字段未变，`legacy_mismatch` 用例证明 A2-01 失败不再决定入口退出码；② migration revision 取真实临时库 head 且未登记显式失败，`format_versions` 含 snapshot、六阶段投影、calibration_baseline、adapter_semantics 九项独立键（`test_each_format_identity_is_independently_gated` 逐项验证漂移即 `config_format_drift`）；③ `REQUIRED_FIXTURE_FILES`（`a2_full_scope.py:536-669`）33 个 fixture 文件只存 SHA-256，子代理逐一比对与工作区一致。
- **范围蔓延核查 — 未发现。** 17 个文件全部围绕 #25 验收闭环；无新产品代码、无新 CLI 命令、无依赖变更（`pyproject.toml`/`uv.lock` 未动且被固定哈希钉住）。

### 留待裁决的判定点（子代理判断均合规，非违规）

**判定点 1：A2-01 的 check-offline 源码绑定哈希被更新。**
- 位置：`scripts/a2_scope.py:122-125`（diff 中 a2_scope 唯一改动行）；披露文字在 `docs/verification/offline-evidence.md`「完整 A2 独立结论」节。
- 依据：comment ①字面「A2-01 固定哈希不变」；但同票 AC6 要求入口 help 准确说明临时数据库，check-offline 内容被迫变化，其哈希钉在 A2-01 的 `REQUIRED_SOURCE_MODULES` 中，不改则 A2-01 永久 failed。
- 实际影响：A2-01 结论现在绑定新版 check-offline；其五个固定测试哈希、scope、历史 `null` 格式字段与语义均未变，属源码绑定层面的显式、已披露更新。
- 最小修复建议：无需修复；若从严，可在 issue 中补一句确认「固定哈希」仅指测试字节哈希。

**判定点 2：中断发生在 A2-01 结论写出期间时，重试写出的 `.a2.json` 可能记 `passed`。**
- 位置：`scripts/a2_full_acceptance.py:404-416`（重试 `write_a2_conclusion` 不传 interrupted；对照 A1 的 `a1_acceptance.py:422-435` 重试会传 `interrupted=True`）。
- 依据：AC4「中断明确 incomplete」——完整 A2 结论与入口退出码已正确做到（`test_interruption_while_generating_legacy_conclusion_keeps_four_files_incomplete` 验证）；A2-01 结论按其自身范围（检查已全部完成）记 passed 并非事实错误，但与 A1 处理不对称。
- 实际影响：极端中断时序下 `.a2.json` 显示 passed 而同次 `.a2-full.json` 显示 incomplete；因 A2-01 不再决定退出码（comment ①），不影响验收结论可信度。
- 最小修复建议：可不改；若求对称，重试时给 `write_a2_conclusion` 增加 interrupted 参数（会改变 A2-01 既有接口，需另行权衡）。

## 总结

Standards 轴 4 个 finding（1 个硬违规 + 2 个气味 + 1 个轻微观察），最严重为 A1（新验收模块的 reason code 裸字符串偏离同链路 StrEnum 约定）；Spec 轴 0 个违规（11 条 AC 与 comment 三点厘清全部通过，2 个判定点留待用户裁决，子代理均判断合规）。

## 逐项核实与处理（#25）

本节为实现方对上述原始报告的核实记录，原审查内容及其历史行号保留。核实基线为
`7d164ba52f09c2c3a7ebefc8b2f027bd80173dfb`；本轮仅修改已触及的 A2 验收与测试支撑，
不变更产品流程、依赖、数据库 migration、冻结契约、A1/A2-01 固定测试或历史格式。

| 条目 | 结论 | 核实依据与处理 |
| --- | --- | --- |
| Standards A1：原因与状态使用裸字符串 | 采纳 | 仓库约定明确要求受控类型，同链路也已有枚举。新增 `A2FullReasonCode`，将原因调用及帮助映射绑定枚举；结论/检查状态复用 `OverallStatus`、`CheckStatus`，回执累计结果使用 `ReceiptCounter`。序列化显式保留原字符串，原因值、中文指引、退出码和格式版本不变。 |
| Standards B1：六项计数字段重复 | 采纳 | 插件、校验器和合成回执工厂确有重复字段集合。由 `scripts/a2_full_scope.py` 的 `ReceiptCounter` / `RECEIPT_COUNTERS` 统一字段，三处复用；未增加通用证据框架。`test_a2_test_receipt` 对真实 pytest 子进程输出的六字段字面量断言保留，继续独立约束公开格式。 |
| Standards B2：Git fixture 初始化重复 | 采纳整理，修正影响描述 | 两处初始化/提交命令相同，提取 `init_fixture_repository(path)` 后复用，完整复制与部分文件复制逻辑保持分开。原报告称 Git user/email 参与工作树哈希不准确：提交元数据影响提交身份，工作树哈希仅覆盖文件路径、类型、权限和字节；这里是维护性改进，不是已证实的身份校验错误。 |
| Standards B3：短前缀文档补登应拆分 | 不采纳拆分建议 | #25 AC8 明确要求公共 Contract、CLI 与文档交叉核对并收口遗漏。修正已交付 #27 的过时文字正属于本票范围，未实现额外能力；原报告也认可现状可接受。本轮不改写或重排历史提交。 |
| Spec AC1–AC11 与唯一 comment 三点 | 维持原审查结论 | 本轮只约束实现类型与去重，不改变同次绑定、实际临时库迁移、固定范围、执行回执、失败/中断判据或历史兼容；继续使用原公共服务与真实子进程回归验证。 |
| 判定点 1：A2-01 wrapper 源码哈希 | 保留现状，无需额外裁决 | 更新 help 是 AC6 的明确要求，其源码哈希必须显式跟随字节变化。原五个固定测试哈希、scope 和历史 null 字段未变，既有证据文档也已披露。本轮不再更改 wrapper 或 A2-01 源码绑定，不向 Issue 追加评论或修改其正文。 |
| 判定点 2：A2-01 补写可能 passed | 保留现状，不扩展旧接口 | 中断前已完成检查的旧切片可按自身 scope 通过；本轮核对现有回归明确要求同次完整 A2 为 incomplete、不得通过。A2-01 不再决定整体验收退出码，无须为了对称新增 interrupted 参数；证据文档补充说明此时两份结论的含义。 |

上述整理没有改变外部 JSON 契约，因此完整 A2 格式仍为 2、回执格式仍为 1。
只对本轮实际改动的源码与 A2 自有测试更新固定字节绑定；固定用例数量仍为
63 个模块、1209 个用例，不自动生成新期望。所有验证完全离线，不访问用户数据库、
真实来源或付费模型。

### 本轮验证

- `uv run --offline --locked pytest -q tests/test_a2_full_acceptance.py tests/test_a2_full_entry.py tests/test_a2_full_examples.py tests/test_a2_test_receipt.py tests/test_a2_acceptance.py`：57 passed。
- `uv run --offline --locked mypy`：138 个源码文件通过。
- 本轮触及模块的 Ruff format/check 与 `git diff --check`：通过。
- `./scripts/check-offline`：返回 0；lockfile、Ruff format/check、mypy、全部 pytest 与四份冻结契约均通过。A1、A2-01、完整 A2 同次全部 passed；63 个固定模块的 1209 个用例全部执行通过，失败/跳过为 0。
- 本次完整验证 `run_id`：`8a551651994844ab9d48293573cda64d`，完整结论位于 `verification-runs/8a551651994844ab9d48293573cda64d.a2-full.json`。验证在提交前的修复工作树运行，证据保留当时身份；验证后只补写本节记录，代码与固定字节清单未再修改。
- 未运行 live；不声明正式校准、阶段 A/B 或真实来源验收通过。原报告和本节处理记录随修复代码一并提交，commit 引用 #25；Issue 保持开放。
