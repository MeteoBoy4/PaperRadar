# Issue #139 双轴代码审阅（r1）

- **Fixed point**: `main` = `5a3a543fcd5d57e445f28451830ae03b48624590`
- **HEAD**: `8852cc8` — `test: finalize migration expectation guard and verification evidence (#139)`
- **Diff 命令**: `git diff main...HEAD`（49 files, +313 / −79）
- **提交列表**:
  - `8852cc8` test: finalize migration expectation guard and verification evidence (#139)
  - `69aaa69` refactor(tests): centralize manual migration expectations (#139)
- **Spec 来源**: GitHub issue #139（body + 1 comment）
- **Standards 来源**: `AGENTS.md`、`docs/agents/{python-conventions,testing,verification-scope,documentation,refactor,invariants,llm-evidence}.md`、`GLOSSARY.md`、`docs/adr/`、`pyproject.toml`（ruff/mypy，工具强制项已跳过），另加 Fowler ch.3 smell baseline。

两个维度由独立 sub-agent 并行审查，**各自独立报告，未跨轴合并排序**。

---

## Standards

**硬违规：0 项。** 下述均为判断题，按文件/hunk 列出。

### 1. `tests/test_migration_expectations.py:8-16`（判断题：Primitive Obsession）
`EXPECTED_MIGRATION_REVISION in path.read_text(encoding="utf-8")` 把「单点所有者」这一不变量交给裸字符串子串判断：下一个 head 若以现值为前缀（`feed06_language_provenance_v2`）或同串出现在注释里都会误报，而拼写变体/相邻字面量又不在扫描范围。若要表达「当前 head 文本只有一个所有者」，按 AST 常量节点或精确 token 比较更贴合语义。注意 `testing.md` 已把「扫描 tests 下除 fixtures 外的 Python 文件」写成规则，所以写法本身合规，只是强度偏弱。

### 2. 同文件 `parts[0] != "fixtures"`（判断题：Speculative Generality，轻）
`find tests/fixtures -name '*.py'` 当前为 0，排除分支尚不生效；`testing.md` 已先写下该例外，故属标准先行，仅提示长期无 Python fixture 时它是近似死代码。

### 3. 七个 hunk 的双行同形断言（判断题：Duplicated Code）
`a10_recovery_support.py:189-190`、`test_a7_attempt_migrations.py:117-118`、`test_a7_registration_migrations.py:119-120`、`test_a7_retry_migrations.py:166-167`、`test_a7_success_migrations.py:122-123`、`test_fixture_recovery.py:155-156`、`test_storage_migrations.py:141/151` 都是 `assert upgrade_database(x) == EXPECTED_MIGRATION_REVISION` 连写两次，可提 `assert_upgrade_head()`；但 `docs/agents/testing.md`「冻结测试修改须先有裁决并逐项登记」加 scope 哈希重算成本压制该重构，记录不要求改。

### 4. `docs/verification/issue-139-migration-expectations.md`「## 开发验证实测」（判断题，偏硬：文档标准）
`docs/agents/documentation.md` 明写「票的实施过程、审阅发现留在 issue 评论、PR 与 `intent/review/`，不进入长期文档」。该节写入中间失败（「1011 passed、1 failed」「补写本台账期间触发…identity_changed 保护」）、临时改常量的探针过程、`/tmp/issue139-constant-only.json` 与「Standards 0 项、Spec 0 项」审阅结论；`testing.md` 的 #109 先例是原始复现/计时进被忽略的 `.scratch/`，仓库只留摘要。建议压缩为结论性数字，过程叙述外移。哈希表与命令结果本身属 `docs/verification/` 证据范围，不需删。

### 5. `docs/roadmap.md:103`（判断题，轻）
新增「以原生 blocked-by 依赖本票」把票级任务图写进模块表行，而 `docs/agents/roadmap.md` 规定「票级任务图…只在 GitHub 原生关系中维护」。串行权威在 `verification-scope.md` 且此处已有链接，属「摘要+链接」边缘合规；可只保留「核实 #139 完成」与链接。

### 已压制、不报告
10 个 scope 的 `MIGRATION_REVISION`、A3 `FORMAT_VERSIONS` 与生产/Contract 字面量仍重复，但 `verification-scope.md`「各组显式保留成员、用途和固定计数」与 `testing.md` 的人工更新清单明确要求；台账重复 32 组旧/新 SHA 亦由 verification-scope S3 登记规则要求。

---

## Spec

### (a) 规格要求但缺失/半做
无。逐条核对全部 acceptance criteria 均有可复现证据：

- "32 个测试/支撑文件里的当前 head 预期（34 处 E）和 future 探针的 `down_revision`（10 处 F）"：diff 实测 32 文件、E=34、F=10；台账逐行 E/F 与代码逐处分类一一吻合，旧 SHA 全部等于 `main:<path>` 字节、新 SHA 全部等于工作树字节。
- "只改中央预期时，A2-01 及其余 9 组都落入敏感分类"：`/tmp/issue139-constant-only.json` 的 `affected_groups` = 全十组，均为 `hash_drift`。
- 登记 kind：审计 JSON 中 `tests/migration_expectations.py` 在 A2-01 为 `source`、完整 A2 与 A3–A10 为 `fixture`，符合"评估只写了'共享 fixture'……A2-01 例外……用 `REQUIRED_SOURCE_MODULES` 登记"。
- "不增减测试函数、参数化分支或 `REQUIRED_TEST_CASE_COUNTS`"：新增 def 仅 D1 一条；`parametrize` 零增删；计数表零改动；`--collect` 285 模块 / 5281 用例、`collection_skipped=0`、`deselected=0`。
- "守卫不扫描 `scripts/`、`src/`、`docs/`"：D1 用 `rglob("*.py")` + `parts[0] != "fixtures"`，精确匹配；`tests/` 内字面量仅剩 `migration_expectations.py`。
- "登记：新文件加入 `SHARED_MATERIALS`"、"只重算实际改动文件的哈希"：1139 条登记对全部当前字节校验 0 漂移；`src/`、migration 节点、Frozen Contract、历史 `docs/verification/` 零改动。
- 审计与验收可复现：默认与 `--json --collect` 均 `issues=[]` 退出 0；`./scripts/check-compatibility acceptance` 117 passed 退出 0。

### (b) scope creep
无。49 个改动 = 32 tests + 2 新 tests + 10 scope + `verification_scope_materials.py` + 3 docs + 1 台账，与规格逐项对应；文档仅按调整 3 修改迁移条目、串行段与 roadmap 承接条目。

### (c) 看着做了但方式可疑
- 台账 "32 个既有文件仅内联新常量后 AST 与旧版完全等价" 措辞不准（新增 import，`Constant`→`Name` 节点），应为语义等价的断言不变；不影响行为。
- 报告正文 checkbox 仍为未勾选状态（`- [ ]`），完成结论在票评论中；无实质影响，但收口时应收敛。

残余风险：1012 用例组合运行、ruff/mypy、临时反向验证仅有台账自述，本次未复跑（除 acceptance 117 例与两种审计）。

---

## 汇总

- **Standards**：5 项，全部为判断题（0 硬违规）。本轴最重的是第 4 项——`docs/verification/issue-139-migration-expectations.md`「开发验证实测」把实施过程叙述写进长期文档，与 `docs/agents/documentation.md` 的分工相悖。
- **Spec**：0 项缺失、0 项 scope creep、2 项实现方式可疑（均已判定不影响行为）。本轴最重的是台账中「AST 与旧版完全等价」的措辞不准确。


## 逐条核实与处置

本节是对以上原始审查意见的逐条回复；原报告保留，以便回查。关联 #139，
核实基线为 `8852cc870342e8a4a6f7d3eb02e25cc4f3af57d0`；开始时仅本报告未跟踪，
专用分支仍为 `implement/issue-139`，本地 main 为 `5a3a543fcd5d57e445f28451830ae03b48624590`。

| 项目 | 判断与处置 |
| --- | --- |
| Standards 1：用 AST/token 替代文本扫描 | 不采纳行为修改。#139 要求仅常量文件“出现 EXPECTED_MIGRATION_REVISION 的字面值”，现有规则有意约束源文本，包含注释和更长字符串中的重复值；token/AST 精确匹配会允许这些文本回流。相邻字符串或转义拼接不在本票文本守卫的承诺范围。推进到更长新 head 时，旧 head 本身也不包含完整新值，不能据此前缀关系推定必有误报。给守卫补充注释说明检查意图，保持 1 个 D1 用例及行为不变。 |
| Standards 2：删除 fixtures 排除分支 | 不采纳。#139 调整 2 明确排除 tests/fixtures/，当前没有 Python fixture 不影响该边界的必要性；删除会直接违反规格。保持只排除顶层 tests/fixtures/。 |
| Standards 3：提取 assert_upgrade_head | 不采纳，原报告也明确不要求改。两次 upgrade_database 调用验证第一次真实升级和第二次幂等升级；它们不是对同一无副作用值的重复比较。保持断言显式可读，避免给冻结测试增加本票之外的抽象和重绑面。test_storage_migrations.py 两次调用之间还校验旧事实和配置投影。 |
| Standards 4：台账包含过程叙述 | 采纳。台账压缩为命令、数量、结论及证明边界；中间失败、运行过程、临时诊断路径及原双轴审阅结论归入本节。保留票要求的逐文件 SHA、E/F、成员 kind、D1 数量及结论性反向验证摘要。 |
| Standards 5：路线图重复票级串行要求 | 采纳精简建议，但不认定原文构成硬违规。实际第 103 行没有原报告所引“以原生 blocked-by 依赖本票”，这句话在唯一集成规则中；路线图原文是承接摘要。现仅保留核实 #139 完成及交付结论，人工更新/串行/S3 细则通过已有规则链接承接。 |
| Spec (c) 1：AST 等价措辞 | 部分采纳。实测脚本确实做了移除新增导入、Name 还原 Constant、折叠相应 JoinedStr 的限定归一化，并逐文件比较 ast.dump，不能说比较结果虚假；但原台账“仅内联”未完整列明变换。已明确这些条件和“原始 AST 并不相同”，避免把语义校验误读为原始语法树相同。 |
| Spec (c) 2：Issue checkbox 未勾选 | 核实属实，但不作为代码缺陷处理。#139 未规定实施者须勾选或关闭 Issue；已发布收尾评论逐项给出结果，checkbox 未勾选不改变本地实现或验证事实。本次按用户要求提交代码说明、文档修正与本报告，通过 commit 中的 #139 关联，不改远程验收状态。 |

### 移入的实施过程与诊断说明

- 原 D1 在集中化前检出 32 个分散文件并失败，替换后通过。
- 首次 34 模块组合运行是 1011 passed、1 failed（505.54s），失败为
  `test_every_predecessor_must_independently_bind_and_pass[status-full]` 的
  `identity_changed`：运行期间补写台账改变了受检查树。材料稳定后该具体用例通过，
  A4 独立复跑另为 84 passed。不能将首次组合表述为退出 0。
- 临时错误常量使 E 的 success/failure/kill 三分支及 F 探针均失败，
  临时重新写入 head 文本使 D1 失败；恢复后 E/F/D1 五例通过，临时改动未提交。
- 仅改常量的分类诊断在 `/tmp/issue139-constant-only.json`；旧树 S3 确认在
  `/tmp/issue139-confirmations.json`。这些是原实现的树外本地材料，路径不保证长期可用，
  也不能用作本次新提交的确认；本轮最终确认另以新身份生成。
- 原实现独立双轴审阅结论为 Standards 0、Spec 0；该结论是先前审阅记录，
  不否定本份 r1 新提出且已采纳的文档建议。

### 本轮验证边界

本轮守卫仅补说明注释，既有 32 文件、scope 登记、固定分母和生产行为均未改。
运行 D1、既有测试 AST 归一化校验、Ruff 与 mypy；对注释/更长字符串回流及
fixtures 排除边界作不提交的临时验证。另在最终提交上重新执行默认审计和显式
main 基线审计（含 collect），为本票原有敏感变化重新绑定全部影响组的 S3 确认。
不将原实现的 1012 例或 acceptance 117 例称为本轮重跑；本轮不触发入口兼容组合，
不运行完整离线门禁或 live。

本轮已取得结果：D1 `1 passed`；四个临时边界探针通过（注释与更长字符串回流拒绝、
顶层 fixtures 放行、嵌套同名 fixtures 仍拒绝）；既有 32 文件受限 AST 归一化比较通过；
Ruff、格式检查、mypy（712 文件）通过；提交前默认 scope 审计退出 0。
本轮最终身份审计和确认材料使用树外 `/tmp/issue139-r1-*` 路径，避免混用原实现的确认。
