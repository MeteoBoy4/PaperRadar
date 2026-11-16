# #207 / #208 版本消费者检查与轻量本地检查 — 两轴代码审查（r1）

- 日期：2026-11-16
- 固定点：`main` = `50485e2d9ad7d4b68780f24e79ebf9b9ac074202`
- 审查目标：`HEAD` = `37c7e65`（分支 `integration/207-208`）
- 比较命令：`git diff main...HEAD`（三点，对 merge-base）；改动 27 文件，+1614 / −11
- 提交范围：`git log main..HEAD --oneline`，5 个提交
  - `37c7e65 fix: preserve safe index symlinks and integrate local checks (#208)`
  - `608725f Merge branch 'integration/207-208' into implement/208`
  - `755322a fix: inspect raw index blobs and clarify local check errors (#208)`
  - `117504b feat: add staged local checks and live document link validation (#208)`
  - `c1ad601 feat: add explicit version consumer regression groups (#207)`
- 规格来源：GitHub issue #207、#208 的正文与所有者补充评论（评论优先）。交付台账
  `docs/verification/issue-207-*.md`、`issue-208-*.md` 与 `docs/contracts/check-{compatibility,local}.md`
  仅作被核对对象，不是规格。
- 标准来源：`AGENTS.md`、`docs/agents/{python-conventions,testing,cli-output,documentation,invariants,scope,refactor,verification-scope,domain}.md`、`GLOSSARY.md`、`docs/adr/`、`docs/contracts/`（仓库无 `CODING_STANDARDS.md`／`CONTRIBUTING.md`），叠加 Fowler smell 基线。
- 方法：Standards 与 Spec 各由一个独立 fresh-context 子代理只读审查，两者均持 bash（只读 Git/grep）；
  未修改代码、未创建 commit、未运行 pytest／门禁／live。两轴结论不合并、不跨轴排序。

---

## Standards

### 硬性违规（文档化标准被破坏）

1. **`scripts/check_local.py:251-257`**：把 `ValueError` 统一包成
   `launch_error：{error}；请检查 uv / Git 可用，…`。于是 `local_hooks.py:20,42` 的
   `hooks_path_conflict`／`hook_conflict`（以及 `intent_to_add`、`non_utf8_path`、
   `unsupported_index_entry`）都被覆写成 `launch_error：`，同时附上与冲突无关的 uv 准备下一步。
   违反 `docs/agents/cli-output.md:5`「错误信息写明具体原因和用户可采取的下一步」，
   并与 `docs/contracts/check-local.md` 自述的 `hook_conflict`／`hooks_path_conflict`／
   `launch_error` 分类不符。`tests/test_local_hooks.py:26,91,98` 只断言子串，掩盖了标签错位。
2. **`scripts/live_document_links.py:22`**：`LinkProblem.reason: str` 为裸字符串，全脚本又散落
   字符串常量。违反 `docs/agents/python-conventions.md:8`「用明确的领域类型和受控 enum / reason
   表达状态与原因」；同变更的 `scripts/check_compatibility.py:29` 已给出 `FailureReason(StrEnum)` 先例。
3. **`docs/verification/issue-208-local-checks-integration.md:1,8,11`**：把审阅结论（`Standards P3`、
   `Spec P2`）与修复过程写进长期证据台账。违反 `docs/agents/documentation.md:63`
   「票的实施过程、审阅发现留在 issue 评论、PR 与 `intent/review/`，不进入长期文档」。
4. **`docs/agents/testing.md:59-63`**：整段复述 `docs/contracts/check-compatibility.md:20-23` 的规则正文
   （负例字面量、mutation 前置、历史保护）。违反 `documentation.md:47`
   「每项行为的详细规则只在所属 Contract 定义；其他文档保留必要摘要与链接」。
5. **`scripts/check_local.py:48`**：文档检查结果打印 `docs：failed/passed`，状态词为英文。
   违反 `docs/agents/cli-output.md:3`「产品输出默认使用中文」（`format`/`lint` 是标识符，
   状态词不是）。

### 判断性 smell

6. **Duplicated Code** — `scripts/live_document_links.py:28-41` 的 `_positioned_link` 与
   `_positioned_image` 形状完全相同，只有被包装的 `link`／`image` 不同。
7. **Primitive Obsession／魔法下标** — `scripts/check_local.py:32,34` 两处 `check.command[4:]`
   假定 `offline_evidence.py:69` 的 `uv run --offline --locked` 前缀恰为 4 项且第 5 项是模块名；
   前缀一旦变化会静默执行另一条命令。
8. **Divergent Change** — `scripts/check_local.py` 同时承担 argparse 中文错误（`173-186`）、
   uv 编排、Git index→raw blob 导出（`55-152`）与文档编排，变化原因不止一个；
   `docs/agents/refactor.md` 要求模块职责单一，可抽出 index 快照模块。
9. **Duplicated Code** — `_Parser`（`check_local.py:173-186`）与
   `check_compatibility.py:368-383`、`dev_environment.py:270-280` 已是第三次复制。
10. **Primitive Obsession／Mysterious Name** — `local_hooks.py:12`
    `manage_hook(root, *, install: bool)` 用布尔区分安装/卸载，调用点需回读布尔含义。
11. **信息归属** — `README.md:378-390` 把轻量检查放在「完整离线验证」标题下，与契约
    「不替代完整门禁」的边界易混；`docs/contracts/check-compatibility.md:5` 新术语「版本消费者」
    未进 `GLOSSARY.md`（`documentation.md:3` 要求术语同步）。

**审查边界**：只读静态审查（`git diff/show`、`nl`、`rg`），未运行 pytest 或任何门禁，未验证运行期行为。
工具可强制的项（ruff/mypy）未列。

---

## Spec

### (a) 缺失或只做一半

1. **#208 评论 :66「staged 快照引用仅存在于工作区的 ignored 回执必须失败」无点名的
   ignored 用例**：`tests/test_check_local.py:99-106` 用未跟踪目标证明等价机制
   （`README.md:1 -> target.md: missing_target`），但 ignored 语义（`.gitignore` 命中）
   未被显式覆盖，代码路径亦未单独断言。
2. **旧缺陷重放的判别性证据不在仓库内**：台账 `docs/verification/issue-207-version-consumers.md`
   的重放记录只指向树外 `/tmp/…` 一次性材料，且自述为「对该组合中的具体失败节点作窄重放」；
   组合级「确实选到该节点」的证据无法从仓库复核。#207 评论 :62 允许一次性验收材料，
   故属**可复核性缺口**而非 AC3 未实现，详见 (d)。

### (b) 范围蔓延

1. **`scripts/check_local.py:97,120,135`** 额外加入 intent-to-add、非 UTF-8 路径、
   submodule/未合并条目、环链接拒绝。正文与评论只要求 index 快照、部分暂存、symlink 与
   冲突/卸载语义；这些扩展是 fail-closed 的收紧，不是错，但超出本票要求，应进 spec 或台账理由。

### (c) 实现/语义可疑

1. **`scripts/check_local.py:253`** 用 `launch_error：` 前缀覆盖
   `local_hooks.py:20,42` 的 `hooks_path_conflict`／`hook_conflict`，与
   `docs/contracts/check-local.md:73` 自述的错误分类不一致；`tests/test_local_hooks.py:31,90`
   只断言子串存在。（与 Standards 第 1 条同址，独立记为语义偏差。）
2. **staged 模式的 Ruff 配置来源**：`scripts/check_local.py:169-176` 以 `cwd=snapshot` 执行，
   Ruff 从快照内发现 `pyproject.toml`。若该文件在 index 中被删除或仅工作区存在修改，
   Ruff 会静默回落到默认规则集而不报错，检查口径与完整门禁不再同源
   （对照 #208 评论 :33-35「路径和参数与 `default_checks()` 同源」）。
3. **显式锚点识别偏窄**：`scripts/live_document_links.py:84-86` 的
   `<a\s+id=(["'])(.*?)\1\s*>` 要求 `id` 是唯一属性且 `>` 紧随，`<a id="x" name="y">`、
   `<a class="…" id="x">` 均不识别；仓库现有用法（如 `README.md:543`）都能匹配，
   `tests/test_local_document_links.py:34` 也只覆盖单一写法。自制 slug（`:66-74`）
   与 GitHub 实际渲染的一致性同样只有单侧断言。
4. **已核对为合规、不列为发现**：`all` 是五类有序去重（`check_compatibility.py:222-226`
   `_ordered_unique`）；当前版本负例确为人工字面量（`pi-admission-v29`、renderer `2`），
   未从生产常量推导；`acceptance`／`cli` 两组目录未扩张；`markdown-it-py` 已在
   `pyproject.toml:25` 的 `dev` 组显式声明。

### (d) 未验证（静态审查无法确认）

- 未执行任何入口/测试：三组实测节点数与耗时、`all` 的实际去重行为、hook 在子目录与
  真实仓库的调用、`TMPDIR` 树内拒绝、`RUFF_NO_CACHE` 与字节码树外效果均未实测。
- `scripts/live_document_links.py` 与既有 `tests/test_live_document_links.py` 两套链接实现并存，
  新活文档 `docs/contracts/check-local.md` 能否被两套检查同时通过未验证。
- #207 AC3 的三类旧缺陷重放结论仅存于树外材料（见 (a)2）。

**边界核对**：子代理另提两项经对照 spec 原文后调整，未列入上表——(i)「三组各自包含
`tests/test_version_consumer_checks.py` 属范围蔓延」与 #207 AC1「登记有理由的回归选择，
包含相关独立 D1 模块」冲突，撤回；(ii)「合成负例是否确已改变目标」已由代码核对
（`ADMISSION_POLICY_VERSION="pi-admission-v29"`、renderer `2`）确认，降级为 (d) 未实测项。

---

## 小结

- **Standards**：11 项 —— 5 项硬性违规、6 项判断性 smell；最重为 `check_local.py:251-257`
  用 `launch_error` 覆盖 hook 冲突原因码（原因与下一步双错），`live_document_links.py:22`
  的裸 `str` 原因码次之。
- **Spec**：6 项 —— 2 项部分实现/可复核性缺口、1 项范围蔓延、3 项语义可疑；
  最重为 staged 模式 Ruff 配置可能静默回落默认规则集，使「与门禁同源」失守。

---

## 逐项处置（保留以上审查原文）

处置依据为 #207/#208 正文与所有者补充评论；审查报告不构成新规格。
完整核对方法、旧重放摘要与安全边界理由见[处置依据](issue-207-208-review-fix-evidence.md)，
本轮命令和数量见[独立覆盖台账](../../docs/verification/issue-208-local-checks-followup.md)。

### Standards

| 编号 | 处置 | 理由、实现与证据 |
| --- | --- | --- |
| 1 | 采纳 | `check_local.main` 将受控 `ValueError` 单独输出；hook/index 冲突保留原因码与各自下一步，只有工具启动/调用失败使用 `launch_error`。hook 两种冲突、用户改过的 hook、五类 index 拒绝与 intent-to-add 均改为精确前缀断言；hook 前缀在修复前红、修复后绿。index 的异常路径/blob/symlink 拒绝也补具体修正动作。 |
| 2 | 采纳 | `LinkReason(StrEnum)` 收拢六种既有诊断；`LinkProblem.reason` 与局部变量使用枚举类型，输出拼写保持。链接七项及 mypy 通过。 |
| 3 | 部分采纳 | 认可过程归属原则；后续过程放 `intent/review/`。拒绝原地删除/改写旧 `docs/verification/issue-208-local-checks-integration.md`：`docs/agents/verification-scope.md` 要求已发布证据保留原字节，且本次无需改变其历史证明。新覆盖另建台账；旧证据字节保持，不将其待确认文字追改成现在状态。 |
| 4 | 采纳 | 测试导航删除当前负例、mutation 前置和历史保护的重复正文，直接链接 `check-compatibility` Contract；派生选择表和 Agent 触发条件保留。 |
| 5 | 采纳 | 文档状态改为 `docs：通过/失败`；成功状态在 CLI 的禁外部 I/O 用例断言，原 `passed/failed` 不再输出。 |
| 6 | 采纳 | 两个定位 wrapper 收为 `_positioned(rule)`，继续通过链接/reference/图片及多行诊断的公共合成树用例。 |
| 7 | 采纳 | 使用完整 `uv_prefix` 元组比对后按其长度取模块命令；前缀变化以 `invalid_check_plan` 失败并提示检查唯一计划，不再裸用 `[4:]`。同源计划/参数未复制或改动。 |
| 8 | 拒绝 | 本次是审查修复，非全模块重构；入口已有 `checked_tree`、`run_checks`、hook 适配分工。没有证据表明拆出新 index 模块能修复额外错误，先保留已验证快照 seam，避免扩大改动与导入链。后续若新增 index 消费者可重新评估。 |
| 9 | 拒绝 | 不跨三个入口提公共 Parser；各入口本地化分支与错误语义不同。当前中文段头在本入口修复并回归，跨入口共用会触及本轮未改的行为。 |
| 10 | 拒绝 | `install` 是 keyword-only，当前单一调用点显式写 `install=options.action == "install"`；没有易混的裸位置布尔或第二消费者，不为此引入 action 框架。 |
| 11 | 部分采纳 | README 分成轻量检查、开发期回归、完整离线验证三个入口，原完整门禁锚点保留。拒绝新增 GLOSSARY 术语：#207 评论已局部定义消费者，#208 评论明确无需改 GLOSSARY/ADR/模块路线图；这是开发检查目录，不引入产品领域概念。 |

### Spec

| 编号 | 处置 | 理由、实现与证据 |
| --- | --- | --- |
| (a)1 | 采纳 | 新增点名 ignored 回执 case：临时 `.gitignore` 命中 `verification-runs/local.json`，工作树通过而 staged 精确 `missing_target` 失败，回执和 index 字节不变；原未跟踪目标用例保留。 |
| (a)2 | 部分采纳 | 补仓库内三组的选择关系、精确节点/变异/边界、红绿结果与日志 SHA 摘要。已核对原日志及当前注册表，不夸称完整组合变异重跑；原规格允许一次性树外材料，不新增通用重放框架。 |
| (b)1 | 部分采纳 | 补足每种拒绝与封闭 index 快照的关系，见处置依据；不改产品规格、不撤回安全拒绝。空意图、非 UTF-8、submodule、未合并条目和成环/外向 symlink 均无法提供本入口承诺的可检查快照，属于必要失败边界。 |
| (c)1 | 采纳 | 与 Standards 1 同一根因，同一修复和精确前缀红绿证据；没有遗漏第二处 hook 分类。 |
| (c)2 | 采纳 | staged 导出后必须存在快照 `pyproject.toml`；缺失以 `missing_ruff_config` 失败，提示先暂存，不取工作树配置。仅工作树有配置、已从 index 删除配置两项均先红后绿；显式可执行模式及自定义 Ruff 配置原用例保留。Contract 同步。 |
| (c)3 | 部分采纳 | 核实已有单属性 `<a id="…"></a>`、中文/标点/重复后缀/inline code/碰撞用例通过。拒绝扩展多属性 HTML：#208 所有者明确“原始 HTML 的其他形式……不属于本票范围”。报告未给出现有范围内 slug 的具体失败反例，本轮不扩展或声称完整渲染等价。 |
| (c)4 | 无需改动 | 重新核对 `all` 有序去重、人工当前版本字面量、旧两组范围及直接 dev 依赖，保持；相应目录/兼容入口回归通过。 |
| (d) 第一项 | 部分采纳 | 本轮运行 63 项受影响子集和 cli 59 节点，补树内 TMPDIR 受控拒绝、子目录 Git 提交，已有 linked worktree、禁字节码/Ruff缓存与不写正式回执断言继续通过。三组节点/耗时仍为旧冻结测量，未改其选择或版本，未机械重跑三组长测；真实仓库不安装 hook。 |
| (d) 第二项 | 采纳 | 新合成链接七项、旧 `test_live_document_links.py` 四项、inventory 四项同一受影响子集通过；工作树轻量入口也实际检查当前活 Contract。旧测试字节保持。 |
| (d) 第三项 | 部分采纳 | 同 (a)2；核实旧三类 red/green 原日志，摘要现已入库，未把旧运行升级为本轮新树结论。 |
| 边界核对 (i)/(ii) | 无需改动 | 接受报告自行撤回的“D1 入组蔓延”和降级后的 mutation 疑点判断；独立 D1 保持，各有效 mutation 前置与受控边界继续由原测试保护。 |

本轮不重绑旧材料，不修改依赖、inventory 或 scope；最终提交身份由树外显式审计报告，
旧确认不复用。未运行完整离线门禁或任何 live；剩余限制见独立覆盖台账。
