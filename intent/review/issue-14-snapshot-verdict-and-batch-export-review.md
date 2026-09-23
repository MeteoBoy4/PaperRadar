# Issue #14 snapshot 判决 seam 与 export 批量结果重构审查（Standards / Spec 双轴）

- 固定点：`HEAD~2`（= `7cef100b4e023056a7367b7bd3995b73e11d5a1a`）；`HEAD` = `74d044c`
- 范围验证：`git log HEAD~2..HEAD --oneline` 恰为两笔目标提交——`f1628ee refactor(contracts): centralize snapshot verdicts (#14)`（规格的 commit 1）、`74d044c refactor(contracts): return per-item batch export outcomes (#14)`（规格的 commit 2）；`git diff HEAD~2...HEAD --stat` 为 9 文件、+581/-381
- Diff 命令：`git diff HEAD~2...HEAD`（三点，相对 merge-base；固定点是直接祖先，等价两点）
- 规格来源：GitHub Issue #14 正文（已完整读取；该 issue 无 comments），及 `intent/discussions/ica-advise-*.md` 十份决策记录
- 标准来源：`AGENTS.md`、`CONTEXT.md`、`docs/agents/domain.md`、`docs/adr/`（0006/0008/0018/0023 浏览后判不相关）、`docs/contracts/frozen-contracts.md`、`pyproject.toml`，外加 Fowler smell 基线
- 审查方式：Standards 与 Spec 两个独立子代理（explore，只读约束）并行、各自 fresh 上下文；子代理只运行 git 只读命令与 read/grep，未修改文件、未创建 commit、未运行 pytest/check-offline、未触碰 GitHub Issue；聚合者只按 skill 要求分轴呈现，不混合排序
- 聚合者只读抽查（未运行测试、未复跑审查）：对 finding 行号逐条核对——Standards 1 原文 `export.py:236-242` 实为 `:237-242`（:236 是 docstring）；Standards 2（snapshot.py:213-225、:325、:352）、Standards 3（snapshot.py:310-315；HEAD~2 旧 check.py `_snapshot_failure` 末位确为 `raise ValueError("一致状态不是失败：…")`）、Standards 4（cli.py:178-180 与 :192-194）、Spec c1（cli.py:178-180）、Spec c3（test_contract_export.py:98-153、:141-153、:41-46、:84-89）、Spec c4（export.py:76、check.py:65）均核对一致
- 聚合者独立复核：`sha256sum tests/test_contract_export.py` = `62e522d9…` 与 `scripts/a1_scope.py:30` 一致；`git diff HEAD~2...HEAD -- tests/test_contract_cli.py contracts/` 为空（CLI 测试与四份冻结快照零改动）；`git show HEAD~2` 确认旧 `export_frozen_contract` 委托批量入口；审查全程 `git status --porcelain` 为空
- 未运行验证的声明：两轴及聚合者均未运行 `uv run pytest` / `./scripts/check-offline`（会产生缓存与 verification-runs 写入，超出只读约束）；「CLI 输出逐字节不变」「离线检查全部通过」等验收项仅为静态推断
- 跨轴重叠提示：Standards 3 与 Spec (c)-2 指向同一位置（snapshot.py:310-315）但结论相反；决策记录 `ica-advise-single-entry-composition.md` 明确把旧 `raise ValueError` 防御列为正在消除的症状（选定方案 (a) 的理由之一），实施复核时需带着该记录裁决

## Standards

### 硬性违规（仓库明文标准）

未发现。子代理逐项核查：不可覆盖/冻结语义、幂等重跑、文档同步（frozen-contracts.md:150-173 与实现逐条吻合）、新增用户可见文本全中文、异常文本脱敏（"synthetic-secret" 不进消息）、ADR 0006/0008/0018/0023 无冲突、被删/私有化符号在 `.py` 代码中无残留引用，均无违反。

### 判断性（基线 smell）

**1. `src/paper_radar/contracts/export.py:237-242` — 可能的 Duplicated Code：选择错误转译样板出现第 4 份拷贝（本 diff 新增）**

- 依据：commit 2 在 `export_frozen_contract` 中新写 `try: build_selected_contract … except ContractSelectionError → raise ContractExportError(INVALID_SELECTION, str(error))`；同形代码已存在于 `export.py:160-169`（`_select_contracts`）、`check.py:76-81`、`check.py:98-107`。commit 1 之前单份入口委托批量入口（旧 docstring「通过批量边界…」，已经聚合者用 `git show HEAD~2` 证实），不持有此逻辑。旁证：commit 2 不得不新增「单份 ≡ 单元素批量」等价性测试专门锁住两条路径的消息一致——两条独立路径需要等价性测试，正是复制粘贴的信号。
- 实际影响：未来调整选择失败的措辞或类别时需同步 4 处，漏改即造成单份入口与批量入口可观察行为分叉，而测试只能覆盖已被想到的断言。
- 最小修复：让 `export_frozen_contract` 重新委托 `export_frozen_contracts((name,), version, target)`，把唯一 item 还原为返回或按 `item.error_category`/`item.message_zh` 抛 `ContractExportError`。
- 聚合者注：该修复方向与 `intent/discussions/ica-advise-single-entry-composition.md` 的已记录决策冲突——Q9 选定方案 (a)（平级入口共享私有 helper）并明确把委托方向倒转列为待消除症状；实施复核时大概率不采纳，finding 保留以供裁决。

**2. `src/paper_radar/contracts/snapshot.py:213-225`（调用点 :325、:352）— 可能的 Primitive Obsession：`_PATH_FAILURE_CATEGORIES` 用 `[0]`/`[1]` 位置区分导出与检查**

- 依据：值类型为 `tuple[ContractExportErrorCategory, ContractCheckErrorCategory]`，调用点 `:325` 取 `[0]`、`:352` 取 `[1]`，元组位置没有自解释性，读者须记住「0=导出、1=检查」。
- 实际影响：新增第三类调用方或有人调整元组元素顺序时，错误类别会静默错配（两个枚举成员字符串完全相同，错了也不会在值层面暴露）。
- 最小修复：两个枚举的成员名与值一一对应（`"invalid_target"`/`"path_escape"`），直接在两个 verdict 函数里写 `ContractExportErrorCategory(error.problem.value)` / `ContractCheckErrorCategory(error.problem.value)` 并删掉映射表；或把元组换成带 `export_category`/`check_category` 命名字段的小 dataclass。

**3. `src/paper_radar/contracts/snapshot.py:310-315` — 判断性：` _check_snapshot_failure` 防御性兜底丢失，对 `MATCHED` 不再拒绝**

- 依据：改前 check.py 旧 `_snapshot_failure` 末位是 `raise ValueError(f"一致状态不是失败：…")`（聚合者已用 `git show HEAD~2` 证实）；改后末位 `return` 默认给出 `CONTENT_DRIFT` 判决。当前两个调用点都先拦截 `MATCHED`（`verdict_for_check` 于 :357），行为无回归；但这属于把「不可能输入会炸」改成「不可能输入得到错误但合法的答案」。
- 实际影响：未来新增调用点若误传 `MATCHED`，会把一致快照静默报告为内容漂移，且带完整中文指引，极难排查。
- 最小修复：函数开头加 `if inspection is _SnapshotInspection.MATCHED: raise ValueError(...)`；或把 if 链改为以枚举为键的 dict 映射，让非法键自然 `KeyError`。
- 聚合者注：与 Spec (c)-2 同位；决策记录把旧防御列为正在消除的症状，恢复防御的建议大概率不被采纳。

**4. `src/paper_radar/cli.py:178-180`（本 diff 新增）与 `cli.py:192-194`（既有）— 可能的 Duplicated Code（轻微）：`error_category` 渲染片段复制**

- 依据：两处同为 `category.value if category is not None else "none"`。
- 实际影响：很小；两处展示逻辑将来要同步改。
- 最小修复：抽一个 `_category_value(category) -> str` 供两处调用。

未报告项说明（子代理）：`snapshot.py` 同时容纳 export 与 check 两套判决词汇看似 Divergent Change，但两轴共享「快照只读判决」这一变化原因，且这正是 commit 1 的既定目标，故不判为 smell；指引文本引用 `--target` 等 CLI 旗标系从 check.py 原样搬移、非本 diff 新增，仅备注。

## Spec

### (a) 规格要求但缺失/部分实现

未发现。逐条核对（节选关键证据）：commit 1 切分约束满足（`git show f1628ee --stat` 无测试、无 `a1_scope.py`；frozen-contracts.md 调用方向句已同步）；设计 A 全部落实（双具名入口 snapshot.py:318-360；四个名字全私有且 export/check 不再 import；`_PATH_FAILURE_CATEGORIES` 全仓一份；判决 union 未进 `__all__`；errors.py 为叶模块只载四个失败词汇；`_write_error` 未触碰；单份/批量平级共享 helper；无 cast/assert/不可达分支）；设计 B 全部落实（逐份失败不抛异常 export.py:249-292；invalid_selection 在生成 item 前抛出 :160-169；`ExportOutcome` 四成员唯一一份；`ContractExportResult.outcome` 为 `Literal[CREATED, UNCHANGED]` :50；item 字段与 `ContractCheckItemResult` 一一对应；`.passed` 语义 :74-79；not_attempted 口径由「matched 预检即定局、prepared 仅装 ABSENT、`publish_stopped` 置位后全 not_attempted」结构性保证 :260-291；四句中文文本由 export.py 写入 `message_zh`；`ContractBatchExportError`/`Failure` 全仓零残留）；commit 2 验收逐项满足（旧构造异常测试已删；等价性测试 test_contract_export.py:98-153；a1_scope.py 哈希实测一致且 commit message 说明语义变化；test_contract_cli.py 零改动；not_attempted 口径测试存在）；文档同步六项全部落实（frozen-contracts.md:150-173；:142-146 恢复说明与 7/8 行类别表未出现在 diff 中）；不变承诺静态比对成立（行模板逐字不变、输出流按单项分流、`content_conflict`/`content_drift` 未合并、contracts/screening/ 零 diff）；范围外项均未越界（scripts/ 仅哈希行、ADR/CONTEXT.md 未动、无新 CLI 选项与公共 API）。

### (b) 范围蔓延

未发现实质性蔓延。唯一可提的新增代码是 `cli.py:178-180` 的 `"none"` 兜底，但它是对同文件 check 侧既有惯例（:192-194，本次未改）的平移，不构成新能力。

### (c) 看似实现但可疑/错误的实现

**1. `src/paper_radar/cli.py:178-180` — FAILED 分支的 `else "none"` 兜底是不可达分支（观察项）**

- 依据：规格 :45 要求「判别字段是 `outcome`」且模块保证 `failed` 项必带 category（export.py:203-216 `_failed_item` 必传 category）；规格 :35 要求「没有不可达分支」（该条在设计 A 语境，但精神适用）。
- 实际影响：运行时无影响；若模块不变量未来被破坏，CLI 会打印 `未完成 [none]：` 掩盖缺陷而非暴露。
- 最小修复建议：可保留（与 check 侧惯例一致，且规格禁止 cast/assert，现状是可接受的折衷）；若要严格化，由模块类型层面保证后 CLI 直接取 `.value`。建议仅留意。

**2. `src/paper_radar/contracts/snapshot.py:310-315` — `_check_snapshot_failure` 以 CONTENT_DRIFT 作为兜底返回（观察项，判定为有意为之）**

- 依据：旧 check.py 末位 `raise ValueError("一致状态不是失败")` 防御已移除；若未来以 `MATCHED` 调用会捏造 content_drift 失败。
- 实际影响：无——`verdict_for_check` 在 :357 已拦截 MATCHED，且决策记录 `ica-advise-single-entry-composition.md` 明确把该旧模式列为正在消除的症状，属有意为之。
- 最小修复建议：无需修复。

**3. `tests/test_contract_export.py` — 测试覆盖的两处小缺口（不违反验收条文，但弱于条文意图）**

- 依据：规格 :57 要求等价性测试「比对选择文案、类别、指引和结果字段」；规格 :68 要求覆盖「位于失败项之后的 `matched` 项仍报 `unchanged`」。
- 实际影响：
  - 等价性测试（:141-153）对单份 invalid_selection 只比对了消息文案（:153 `str ==`），未直接断言单份侧的 `category is INVALID_SELECTION`（类别断言 :149 只覆盖批量侧）；路径失败类（`invalid_target`/`path_escape`）的单份 ≡ 单元素批量等价性未覆盖。
  - 预检失败场景的 matched 项位于失败项**之前**（:41-46）；「matched 位于失败项之后」仅由发布失败场景覆盖（:84-89，满足 :68 字面要求）。
- 最小修复：在 :150-153 的循环中加一行 `assert single_error.value.category is captured.value.category`；可选增补 symlink-escape 场景的等价断言与预检场景 matched 在后的用例（非必须，实现上 matched 在预检循环即定局，行为与位置无关，风险极低）。

**4. `src/paper_radar/contracts/export.py:76` — `.passed` 多了 `bool(self.items)` 守卫（观察项）**

- 依据：规格 :46 字面「`.passed` 只在全部 item 为 `created`/`unchanged` 时为真」，对空集为 vacuously true；现实现 `bool(self.items) and all(...)` 使空 items 返回 False。
- 实际影响：公共路径不可达（空选择先抛 invalid_selection），且与 check.py:65 既有写法对齐。
- 最小修复建议：观察项，无需修复。

### 只能静态推断、未实际运行的验收项（Spec 轴声明，聚合者确认）

- 「CLI stdout/stderr 逐字节不变」（规格 :14、:67）：通过新旧 cli.py 行模板逐字比对 + `test_contract_cli.py` 零改动推断；未运行 pytest 验证。
- 「`uv run pytest` 与 `./scripts/check-offline` 全部通过」（规格 :64、:70，含 `ruff format --check`、`ruff check`、`mypy --strict`）：未运行；静态未见明显违例。
- 运行时行为等价（预检顺序、发布中断点、os.replace 调用次数）：通过新旧调用链逐步对照推断。

## 汇总

- Standards：4 条，均为判断性 smell，无硬性违规；本轴最严重为第 1 条：`export.py:237-242` 把选择错误转译样板复制到第 4 处，单份与批量入口的措辞/类别存在未来分叉风险（但其修复方向与已记录决策冲突，需复核裁决）。
- Spec：4 条均为 (c) 类观察项/小缺口，(a) 缺失与 (b) 蔓延均未发现；本轴最值得注意的是第 3 条：等价性测试未按规格 :57 字面比对单份侧 `category`（仅比对消息文案），路径失败类等价性未覆盖——一行断言即可补齐。
- 总体：两笔提交忠实实现 Issue #14，commit 切分、验收条目、文档同步与不变承诺在静态层面全部成立；离线测试与 CLI 逐字节等价未实际运行，建议合并前补跑 `uv run pytest` 与 `./scripts/check-offline`。

## 实施者逐条复核与处理（2026-09-23）

以上审查正文保留其针对 `74d044c` 的原始结论；以下记录后续修订，不改变审查当时「未运行测试」的事实。

| 建议 | 裁决与依据 | 处理 |
| --- | --- | --- |
| Standards 1：单份 export 的选择错误转译重复，建议重新委托批量入口 | 不采纳所提修复。`ica-advise-single-entry-composition.md` 已明确选择平级入口共享判决与发布 helper；单元素批量 item 的四态类型若转回单份成功结果，需要引入不可达分支、断言或伪造类别。这里的短小选择边界转译不值得推翻该决策。 | 保留平级入口；补强选择错误的单份/批量等价断言，防止文案和类别分叉。 |
| Standards 2：路径类别表用 `[0]`/`[1]` | 采纳。位置语义不清晰，且两个 category 枚举有相同字符串值，错配可能不易察觉。 | 将单一 `_PATH_FAILURE_CATEGORIES` 的值改为带 `export`、`check` 具名字段的私有类型，调用点按名称读取；公开类别和值不变。 |
| Standards 3：恢复 `_check_snapshot_failure(MATCHED)` 的防御异常 | 不采纳。该私有 helper 仅由先处理 `MATCHED` 的 `verdict_for_check` 调用；恢复不可达异常与 Issue #14 设计 A 的「没有不可达分支」及 `ica-advise-single-entry-composition.md` 的已决方向冲突。 | 保留当前判决入口约束，不增加伪造的失败或不可达异常。 |
| Standards 4：抽取 CLI 两处 `error_category` 渲染片段 | 不采纳。两处各只有一个表达式，export 的 `None` 还可能表示 `not_attempted`，check 的 `None` 表示通过；共享 helper 会隐藏这个领域差异，收益很小。 | 保留各自渲染。 |
| Spec (c)-1：FAILED 类别的 `else "none"` 兜底 | 不采纳。生产构造器 `_failed_item` 总是传入类别；但公开 item dataclass 的字段类型允许调用方自行构造 `None`，因此 CLI 的兜底并非类型上不可达。改成新的判别 union 超出本次范围。 | 保留既有的安全展示兜底；生产路径仍输出受控类别。 |
| Spec (c)-2：`CONTENT_DRIFT` 末位返回可能误报 `MATCHED` | 不采纳。与 Standards 3 同一问题；当前唯一调用点已先返回 `CheckReady`。恢复旧防御分支违背已记录设计。 | 保留当前结构。 |
| Spec (c)-3：等价性与 matched 顺序测试缺口 | 采纳。原测试未直接断言单份 `invalid_selection` 类别，且未检查路径逃逸的两种入口；预检失败后还有 matched 项值得显式锁定。 | 增加类别断言、单份/单元素批量 `path_escape` 对照，以及预检失败项之后的 matched 仍为 `unchanged` 的测试；同步更新 `a1_scope.py` 哈希。 |
| Spec (c)-4：空 items 的 `.passed` 为 False | 不采纳。公共入口对空选择先抛 `invalid_selection`；若直接构造空结果，False 与现有 `ContractBatchCheckResult.passed` 一致，也符合「确有全部所选项成功」的实际含义。 | 保留 `bool(self.items)` 守卫。 |

原审查提出的测试建议已纳入本次复核的验证流程；原文的静态审查范围说明继续有效。
