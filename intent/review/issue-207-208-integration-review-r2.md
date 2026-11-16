# 双轴代码审查：`main...HEAD`（#207 / #208 集成分支）

- 审查对象：`git diff main...HEAD`（fixed point `main` = `50485e2`，27 个文件，+1614/-11）
- Commit 列表（`main..HEAD`）：
  - `37c7e65` fix: preserve safe index symlinks and integrate local checks (#208)
  - `608725f` Merge branch 'integration/207-208' into implement/208
  - `755322a` fix: inspect raw index blobs and clarify local check errors (#208)
  - `117504b` feat: add staged local checks and live document link validation (#208)
  - `c1ad601` feat: add explicit version consumer regression groups (#207)
- Spec 来源：GitHub Issues #207《补齐版本变更的消费者回归检查》、#208《接入轻量本地自动检查并补强活文档链接校验》（正文 + 评论，按 tracker 规则评论优先）
- Standards 来源：`AGENTS.md`、`docs/agents/python-conventions.md`、`docs/agents/testing.md`、`docs/agents/cli-output.md`、`docs/agents/documentation.md`、`docs/agents/verification-scope.md`、`docs/agents/refactor.md`、`docs/agents/invariants.md` + Fowler smell baseline
- 审查方式：Standards / Spec 两个只读 sub-agent（均带 bash）并行独立审查，本文件仅聚合、不跨轴重排。

## Standards

### 【硬违规】

**1. CLI help 未達「默认中文」**
- 依据 `docs/agents/cli-output.md`：「产品输出（CLI help、错误信息……）默认使用中文」。
- `scripts/check_local.py:191-213`：`_Parser` 只做了 `super().format_help().replace("usage: ", "用法：", 1)`，实测 `./scripts/check-local --help` 仍输出英文段头 `positional arguments:` 与 `options:`。同仓姊妹入口 `scripts/check_compatibility.py:409` 用 `add_argument_group("参数与选项")` 达标，证明这是本仓库既有标准而非偏好。`tests/test_check_local.py` 仅断言 `"用法："`，未拦住。
- 最小修复：给 parser 加同名 `add_argument_group("参数与选项")`，并补断言 `"options:" not in result.stdout`。

### 【判断性提示】（baseline smell）

**2. Duplicated Code**：`scripts/live_document_links.py:28-42`，`_positioned_link` 与 `_positioned_image` 除调用 `link`/`image` 外逐行相同（`start, count = state.pos, len(state.tokens) + bool(state.pending)` …）。可提取一个以规则函数为参数的 `_positioned(rule)`。

**3. Duplicated Code（跨入口 bootstrap）**：`scripts/check-local:8-19` 的「`${UV_PROJECT_ENVIRONMENT-.venv}/bin/python` → 宿主 `python3`（≥3.12 检查）」与 `scripts/dev-environment:8-18` 及 `check_compatibility.py` 的 Python 侧同形；同一形状已第三处。可共享或委托 `dev-environment`。

**4. Duplicated Code / Data Clumps**：`tests/test_check_local.py:87,101,205,252,264` 五处重复 `git(git_root, "add", "README.md", "src", "tests", "scripts", "docs")`。可提取 `stage_default(root)` helper。

**5. Feature Envy + 魔法偏移**：`scripts/check_local.py:32,34` 用 `check.command[4:]` 切片，越权知晓 `offline_evidence.default_checks()` 内部 `uv` 前缀的长度；前缀形状变化会静默错切。最小修复：在 `offline_evidence` 暴露去 uv 前缀的模块命令，或按字面量前缀比对剥离。

**6. Primitive Obsession**：`scripts/check_local.py:83,113` 用 `list[tuple[Path, bytes, int]]`、`list[tuple[Path, str]]` 表达 index 条目/符号链接；可改小 dataclass 让字段自名。

### 已核实合规（未发现违规）
D1 独立模块＋`docs/verification/` 逐模块台账；`check-local.md` 符合 documentation.md 固定骨架；README/testing.md 同步更新；`markdown-it-py` 新依赖同步 `uv.lock` 并给出理由；新增测试全离线、负例断言受控 reason 字符串；错误信息均含原因与下一步。`tests/test_local_hooks.py` 跨测试模块导入 fixture 与仓库既有惯例一致，不作 finding。

（Standards sub-agent 验证方式：仅 `--help`（两入口，纯本地只读）；pytest 未运行。）

## Spec

**结论：未发现 missing、partial、scope creep 或 implemented-but-wrong 的实质偏差。** 17 条验收逐条核对通过，两票评论（优先于正文）均落实。

**(a) 缺失/部分**
- 无实质项。#207 评论「在隔离副本做一次窄范围的旧缺陷重放……该验证可以是一次性验收材料……也不把变异后的生产代码或测试入库」：重放不入库是规格允许；其树外证据 `/tmp/paperradar-207-208/207-replay-results.json` 三组 red_exit=1/green_exit=0、边界（`altered != original`／`pi-admission-v28`／`renderer_v2_history_present`）与台账及 red 日志 FAILED 节点一致。仓库内不可复现，列为证据性依赖（非缺陷）。
- 台账自述「分类、依赖身份及 A10 登记的 22 条逐组敏感确认由所有者在最终 HEAD/target 身份上另行生成」：固定范围收口确认未完成，但有明确触发条件，属后续项而非缺失交付，是剩余风险。

**(b) 超范围**：未发现。README 仅入口导航（符合评论「README 只保留入口导航，不复制测试清单」）；inventory 仅 +1 活文档；`a10_scope.py`/`verification_scope_materials.py` 哈希替换与实际文件 sha256 一致（`634b507d…`/`b398adef…`），系「若直接导入就应显式声明适用的 dev 依赖」的机械重绑。

**(c) 实现疑点**：无实质项。备注（不立案，无现实影响）：
- `live_document_links.py` 用 `urlsplit` 判外部链接，形如 `a:b.md` 的本地目标会被跳过；实测当前 36 份活文档无此类链接。
- staged 模式 `uv run` cwd 为真实仓库根（`check_local.py` main），与契约「Ruff 配置取所选树」一致，未违反「说明检查针对工作树还是暂存内容」。

**关键符合点（spec 原文 → 证据）**
- 「`all` 应成为现有 `acceptance`、`cli` 与新增三组的有序去重并集」：`ALL_GROUP`/`select_tests` ✓，tests/test_check_compatibility.py 与 test_version_consumer_checks.py 断言。
- 评论表格 10 个必备消费者模块全部登记于 `CHECK_GROUPS`（check_compatibility.py:122-219）。
- 「负例确认目标确实被改变」：4 个既有测试新增 setup 断言（如 test_live_epoch_upgrade.py:402 `pi-admission-v29`；test_experiment_exposure_migrations.py:41 `b008_body_selection`）。
- #208「pre-commit 调用同一入口的 staged 模式」及四个双向差异场景：test_check_local.py（含 smudge 原始 blob、intent-to-add）、test_local_hooks.py（幂等/冲突/linked worktree/真实提交阻止）全覆盖。
- 两票边界「#208 的 pre-commit……不调用本票三组」：`HOOK_CONTENT` 仅 `exec ./scripts/check-local --staged`，不触 pytest/check-compatibility。

（Spec sub-agent 验证方式：`uv run --offline --locked pytest tests/test_check_compatibility.py tests/test_local_document_links.py -q` → 19 passed, 1.55s；`./scripts/check-compatibility --help` 含三组派生清单。完整门禁未运行。）

## 汇总（不跨轴排序）

- **Standards**：6 项发现（1 硬违规 + 5 判断性 smell）；轴内最重：`scripts/check_local.py` 的 `--help` 段头未中文化，违反 `docs/agents/cli-output.md`「CLI help 默认使用中文」。
- **Spec**：0 项实质发现（2 项证据性备注/剩余风险）；轴内最重：固定范围收口的逐组敏感确认待所有者在最终 HEAD 上另行生成（后续项，非缺失）。

---

## 逐项处置（保留以上审查原文）

按原规格及补充评论核实，r1 同址发现的实现修复一并纳入。
共同依据与旧重放摘要见[处置依据](issue-207-208-review-fix-evidence.md)，
验证数量与限制见[独立覆盖台账](../../docs/verification/issue-208-local-checks-followup.md)。

### Standards

| 编号 | 处置 | 理由、实现与证据 |
| --- | --- | --- |
| 1 | 采纳 | `check-local` 参数加入中文“参数与选项”组，`--help` 不再含 `options:` 或 `positional arguments:`。公共 CLI 回归先红后绿，保留不启动 uv/外部 I/O 的帮助边界。 |
| 2 | 采纳 | 与 r1 Standards 6 同一重复；提取 `_positioned(rule)`，链接、图片、reference、多行诊断七项通过。 |
| 3 | 拒绝 | 不跨 shell/Python 三入口统一 bootstrap：宿主 fallback 与项目环境路径是现有安全引导，报告没有运行错误证据；委托 `dev-environment` 将增加本入口依赖，超出本轮局部修复。缺 uv/帮助 fallback 原回归及 CLI 组合保持。 |
| 4 | 采纳 | 在同一测试模块提取 `stage_default(root)`，常规暂存清单包括显式测试配置；缺配置负例故意不调用该 helper。 |
| 5 | 采纳 | 同 r1 Standards 7：先核对完整 `uv run --offline --locked` 前缀，再按元组长度剥离，形状变化以 `invalid_check_plan` 非零，给出检查唯一计划的下一步。 |
| 6 | 拒绝 | 两类短生命周期私有 tuple 仅在 index 导出内构造/解构，字段名已在循环中表达，没有跨消费者传递。新增 dataclass 不改变当前 seam 或错误，先保留局部实现，避免为 smell 增加类型层。 |
| 已核实合规段 | 无需改动 | 保留独立 D1、Contract 骨架、直接 dev 依赖/lock、离线材料和跨模块 fixture 惯例。r1 另发现的受控错误/下一步问题已修，不能把原笼统“错误均合规”当作忽略它们的依据。 |

### Spec 与证据备注

| 项目 | 处置 | 理由、实现与证据 |
| --- | --- | --- |
| 总体“无实质偏差” | 部分采纳 | 原目录、hook范围和冻结边界核对维持；r1 的 staged 缺配置是实际误通过，已用两项先红后绿用例修复，不能沿用本报告的整体判断略过。 |
| (a) 树外三类重放 | 部分采纳 | 原规格允许一次性材料。核对三组原 red/green 与选择目录后将节点、变异、边界、结果及日志 SHA 摘要留入仓库；未将变异代码或通用框架入库。原始完整日志仍是树外证据依赖。 |
| (a) 22 条敏感确认待完成 | 无需改动（旧信息更正） | 旧 `208-final-scope-confirmed.json` 对 HEAD `37c7e65` 已确认四类变化的全部 22 条组记录，`issues=[]`，结构报告也无问题。该备注对旧树已过时；本轮重新绑定 `37c7e65` 稳定基线做显式审计，不复用旧确认或称旧台账为当前状态。 |
| (b) 依赖、inventory 与机械重绑 | 无需改动 | 旧变更已在基线中，本轮不再修改任何依赖、inventory、中央哈希或 A10 登记，不扩大原消费者目录。 |
| (c) `a:b.md` 被当作 scheme | 拒绝扩展 | CommonMark destination `a:b.md` 具有 URL scheme，本票不扩展为冒号文件名猜测器；仓库现有活文档无这种本地目标。字面冒号路径可用明确相对 `./a:b.md` 表达，不引入新白名单。 |
| (c) staged 的 cwd/配置 | 部分采纳 | 外层 uv 在真实项目根准备环境，worker 的 Ruff subprocess 在所选树运行。原报告未覆盖快照缺 `pyproject.toml` 时的默认回落；现在明确拒绝，且不使用工作树配置。 |
| `all` 与10个必备消费者 | 无需改动 | 注册表未改，`all` 和目录完整性用例继续通过；旧重放 `selected_by` 与当前三组逐项相同，必备模块仍可达。 |
| 当前负例的 mutation 前置 | 无需改动 | 不换版本字面量或旧 migration；renderer 公共负例复验通过，原三类精确边界摘要补入处置依据。 |
| staged四类双向差异与临时hook | 采纳（补证据） | 原场景保留；新增 ignored 回执明确命中、缺配置两例、树内 TMPDIR，临时 hook 成功提交改从 `src/` 子目录调用，linked worktree 仍通过。 |
| #208不自动调用#207组 | 无需改动 | `HOOK_CONTENT` 不变，仍只执行 `check-local --staged`，不触发 pytest/兼容组/正式门禁。 |

所有原发现和备注均有上述处置；本轮没有引入新产品术语、ADR 或路线图状态变化。
完整离线门禁、真实 hook 安装与 live 均未执行，开发检查不替代正式验收。
