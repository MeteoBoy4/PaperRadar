# Issue #126 相对 main 的双轴代码审查 R4

- 固定点：`main`（merge-base：`e6c1ec74c9fc8d15fc8f76d2c8a7b29fcdda9438`）
- 审查 HEAD：`bfc71177d38eb0355a7760f22a3554ba31834e42`（`integration/126-scope-registry`）
- 差异命令：`git diff main...HEAD`（70 文件，+37986/−1607）；提交列表见 `git log main..HEAD --oneline`（18 个提交，含 6 个 merge commit）
- 规格来源：GitHub Issue #126 正文与全部评论（含用户 S1–S8 最终裁决），原生子票 #127–#137 正文与评论；实现者收口评论只作线索，不作为需求或验收证据。
- 审查方式：两个 fresh-context subagent（`oracle`，工具 `read/grep/find/ls/bash`，只读、具备 `bash` 权限）并行前台执行；只读审查，未修改代码、未创建 commit。
- 说明：完整离线门禁未由本次审查启动；实现者声明的门禁 exit 0、`run_id` 与树外 red/green 输出均标为「未核实」。

## Standards

### 完成状态 / 可用来源 / 未验证范围

- 完成状态：Standards 轴审查完成（只读）。已核对 `git diff main...HEAD` 全量文件清单、9 份 `docs/agents/` 标准、2 份 Contract、README/GLOSSARY/roadmap、`gh issue view 126/132–138`，并运行定向 pytest 与只读脚本；未修改任何文件。
- 可用来源：仓库文档与代码、本地 Git 对象、`gh`（可用）、`verification-runs/` 正式证据（`./scripts/verification-status d8e684…` 返回 passed/verified/same）、定向 `pytest`/`--collect-only`（可用）。已实测一致：中央登记 255 = 实际跨组路径 255（无缺漏/多余）、显式 refs 41、scope 哈希边 0、活文档绑定 0、285 模块/1203 登记/695 路径、14 份 JSON；新增 D1 模块收集数 24/34/17/22/7/16/1 与台账逐项一致且均未绑定。
- 未验证范围：未运行 `./scripts/check-offline` 全量门禁、未跑 live；31k 行证据 JSON 仅抽样；`test_scope_*` 仅收集计数并抽跑 7 例；实现者收口评论中树外 red/green 原始输出「未核实」。

### 发现

**1）类别：文档化硬要求（路线图维护）/ 影响中**
- 文件：`docs/roadmap.md:148`（未成形板块）
- 标准引用：`docs/agents/roadmap.md`「粒度：票级任务图、领取与进行中状态只在 GitHub 原生关系中维护；路线图只链接 spec issue」「不写票号或票范围的时点快照」。用户 S7(c) 仅裁决「把未成形中的 #112 换成本票链接」。
- 内容：新增句子写入「第一步已…合入 main；第二步基于该稳定提交…已实现…仍须独立审阅…取得授权完整门禁结论」，是票级交付状态快照。
- 测试核查：文档规则，无对应测试（不适用）。
- 限制：未核实是否存在未公开的口头授权。
- 最小建议：收缩为「#126 承接…，规则见唯一集成规则/集成台账」一行，状态留在 issue 与台账。

**2）类别：功能/文档化标准（CLI 错误信息）/ 影响中**
- 文件：`scripts/check-offline:8-12`；`docs/contracts/verification-status.md:146-148`
- 标准引用：`docs/agents/cli-output.md`（错误信息须写明原因与下一步）；`docs/agents/testing.md` 对同类入口 `check-compatibility --help` 规定「两者均不可用时退出 1 并提示准备环境」。
- 复现（已运行）：在 `/tmp` 副本、`PATH` 仅含 `bash`/`dirname` 时执行 `--help` → `exec: python3: 未找到`，`exit=127`（C locale 为英文），无中文准备指引；旧实现为纯 heredoc，不依赖解释器。
- 测试核查：`tests/test_a1_acceptance.py::test_shell_help_does_not_create_evidence`（已跑通过）只覆盖解释器存在的 PATH；无缺解释器/低版本分支用例。
- 最小建议：`command -v` + 版本校验 + 中文提示 `exit 1`，并在 Contract 补失败行为、加一条负例。

**3）类别：可能 Duplicated Code / Data Clumps（判断题）/ 影响低中**
- 文件：`scripts/verification_groups.py:159-170`（`replace()` 覆盖）vs `scripts/a1_acceptance.py:374`、`scripts/a2_acceptance.py:254`；`scripts/verification_scope_baseline.py:206-236`（敏感词表不含 `GROUP/SUFFIX/REQUIRED`）
- 内容：A1/A2-01 的 name/suffix/required/dependencies 有两处声明，registry 静默覆盖；单独入口 `run_a1_verification` 仍用 writer 声明。改 writer 字段对完整入口无效（`GROUPS` 之外的声明又按 mechanical source 分类），形成隐性分叉。
- 测试核查：`tests/test_extensible_acceptance.py::test_production_registry_expectation_and_reader_are_independent`（已跑通过）只比对 registry 与独立 fixture，未覆盖 writer 侧冗余字段。
- 最小建议：A1/A2-01 与其它组一样由 registry 构造（writer 只留 `write/recover`），或加一致性测试并把 `*_GROUP` 纳入敏感摘要。

**4）类别：文档归属/重复（判断题）/ 影响低**
- 文件：`docs/contracts/verification-status.md:149-157`
- 标准引用：`docs/agents/documentation.md` Contract 规则「只用现在时描述已实现的公共边界」「每项行为的详细规则只在所属 Contract 定义」+ 信息归属表（测试规则归 `docs/agents/testing.md`、证据归 `docs/verification/`）。
- 内容：把 fixture 路径、「旧 entry 单测的模拟执行器」等测试维护细节写进状态查询 Contract，并与 `docs/agents/testing.md`「不从生产输出机械推导预期」重复。
- 测试核查：不适用（文档）。
- 最小建议：Contract 只保留可观察保证（「生产新增组不更新人工预期则检查失败」），细节移入 testing.md 或 D1 台账并链接。

**5）类别：可能 Feature Envy + 测试覆盖不足（判断题）/ 影响低中**
- 文件：`scripts/a8_acceptance.py:168-196`、`:482`
- 内容：A8 writer 在产出验收结论时导入并重跑审计核心（`load_scopes`+`audit_scopes`）推导冻结指针；审计出现任何 issue 时静默返回空集，原因只剩 `scope_drift`，诊断性差。
- 测试核查：仅 `tests/test_a8_a9_document_scope.py:116` 间接验证成功路径；`issues → set()` 失败分支（已搜索）无用例。
- 最小建议：把「经审计的引用集」下沉为 registry/audit 的共享函数，失败时返回受控 reason；补一条负例。

补充：未发现未裁决的通用框架或为未来预留的抽象——`GROUPS`/`Group` 字段、`receipt_scope`、`dependencies` 均与 S4(b) 裁决一致；封闭登记与显式分派成立。

**本轴发现总数：5**

## Spec

### 完成状态 / 可用来源 / 未验证范围

- **完成状态**：Spec 轴审查完成（读 diff、Issue #126 正文+全部评论与 S1–S8 裁决、#137 正文、7 份 `docs/verification/` 台账、只读运行审计与定向 pytest）；未发现缺失的硬要求，3 条低优先级发现。
- **可用来源**：`git diff main...HEAD`；`gh issue view 126/137`；`gh api .../126/comments`；`./scripts/audit-verification-scope --json`；`./scripts/verification-status`；本地 `verification-runs/`；定向 pytest（`uv run --offline --locked`）。
- **未验证范围**：可信 terminal 的原始输出（仅有 run 记录）、台账中「维护行数」逐项实测、历史 49 份 JSON 迁移前后字节比对（`verification-runs/` 未被 git 跟踪，无 main 侧基线）、`--collect` 5281 未由我重跑。

### 发现

**1｜类别 b（边界性范围外行为）+ 留痕不足｜低**

`pyproject.toml:37` 新增全局 `tmp_path_retention_policy = "failed"`，并连带改 `tests/test_tmp_path_cleanup.py:40-43`（补 `-o tmp_path_retention_policy=all`）。
- 需求引用：#126「Out of Scope/不改业务语义」未要求此项；动机来自门禁失败修复（`docs/verification/gate-failure-repair.md:11-16`），属验收基础设施。
- 已有测试核查：该模块未绑定任何 scope（`docs/verification/scope-material-inventory.json` 与 `scripts/verification_scope_materials.py` 均无该路径），故不属「冻结测试」；台账只以「原临时目录权限测试」散文提及，未给路径与旧/新 SHA，弱于 `scope-registry-integration.md:33`「未绑定兼容测试…另表记录旧新 SHA 和理由」的自定标准。
- 复现/限制：静态核对；未运行该模块（8 例）。
- 最小建议：在 `gate-failure-repair.md` 补一行（路径、旧/新 SHA、理由），或明示「未绑定模块不做 SHA 台账」。

**2｜类别 a（口径需显式说明）｜低**

验收标准「改 `cli.py` 只改 1 处中央登记，审计列出 7 个受影响组」与实现字段不一致：`tests/test_scope_shared_dag.py:300-315` 断言 `change["groups"]==7` 但 `affected_groups==10`（A10、A2-01、A3、A4、A5、A6、A7、A8、A9、完整 A2）。
- 需求引用：#126 正文表格同处写「cli.py｜7 直接｜33 级联｜10 受影响 scope」，故实现与正文表一致，属验收标准措辞与正文自相矛盾。
- 已有测试核查：`test_material_or_scope_change_never_rewrites_other_scopes`（已运行通过）；`scope-registry-integration.md:79` 记「7/3」。
- 最小建议：最终回复明确「7 直接组 + 3 额外下游 = 10 受影响组，中央只改 1 行」，避免被读成缺失。

**3｜类别 a（数字口径已披露）｜低**

验收标准写 scope→scope 绑定「42 降为 0」，实际 41→0：`scope-shared-dag-delivery.json.scope_hash_edges` 恰 41 行（已统计确认），`scope-shared-dag-delivery.md:12-15`、`scope-registry-integration.md:15-16`、`docs/contracts/verification-scope-audit.md:41-44` 均披露「42 无第 42 条实际边」，且未改写冻结描述（符合「不重写历史」）。
- 结论：不需要新裁决，只建议在收口回复沿用「41→0，42 为旧账口径」表述。

### 已核实通过（要点）

- 审计 `exit 0`、`issues=[]`、`affected_groups=[]`、1203 条登记；`SHARED_MATERIALS` 255 条 == 多组共享路径集合（已复核，且由 `test_production_migration_keeps_exact_materials_counts_and_graph` 守住）；scope 自身文件与中央登记均不在逐文件哈希闭包。
- 门禁声明部分佐证：`verification-status d8e68439…` = `passed/verified/same`、14 份 JSON、`terminal.materials_consistent=true`、5281/5281、skip0/deselect0、checks 6/6；失败 run `dae8081b…` 仍为 `failed/exit_nonzero`（53 failed）未追认；第一步 `3e72e79…` = `passed`。
- S3(b)/§9：`--base/--integration-target/--confirmations` 受控（非祖先、目标移动、旧 merge-base、身份变更、缺逐组确认、确认不可清除真实 `hash_drift`）均有测试；候选分析不写登记/回执/Git 索引（快照含 `.git/index`）。
- S4(b)：11 组/10 required，#114/#120 未登记；独立预期 `tests/fixtures/verification_group_expectations.json` + 读取支撑均走中央 SHA，帮助断言按该清单独立计算；D1 模块 104 例不在回执（回执 285 模块，无 D1 路径）。
- S7(c)：`docs/agents/verification-scope.md` 已成唯一权威（材料边界、中央登记、S3 分级确认、单/跨 spec、串行点），路线图未增模块、未阻塞 B；ADR-0038 已覆盖分类/中央/确认三项且正文未改。
- 实际运行：`pytest tests/test_scope_{baseline_audit,central_registration,shared_dag,parallel_integration}.py tests/test_tmp_path_peak_usage.py` → 83 passed；`pytest tests/test_extensible_acceptance.py tests/test_a2_full_entry.py tests/test_verification_status.py` → 64 passed。

**需主 agent 决策：无阻塞项。** 建议聚合时把发现 1 归为「可选留痕改进」，2、3 归为「最终回复措辞校准」，不并入功能缺陷。

**本轴发现总数：3（均低优先级）**

---

汇总：Standards 共 5 项（2 项文档化硬违规 + 3 项判断题/可能 smell），轴内最严重为 `docs/roadmap.md:148` 写入票级交付状态快照与 `scripts/check-offline --help` 在缺宿主 Python 时 `exit 127` 且无中文指引；Spec 共 3 项（均低优先级，无缺失硬要求），轴内最严重为未绑定模块 `tmp_path_retention_policy` 变更在台账中只留散文、缺路径与旧/新 SHA。两轴合计 8 项，未发现跨轴均可归一的阻塞缺陷。


## 本批逐项核实与处置（#126，base `bfc7117`）

### Standards

1. **采纳。** 路线图中的票级阶段/候选快照确实违反 `docs/agents/roadmap.md`，且会过时。`docs/roadmap.md` 收缩为 #126 承接描述和唯一集成规则/台账链接，模块、前沿和 B 依赖不变。
2. **采纳。** 缺解释器时原入口确实 exit127、无中文恢复指引。`scripts/check-offline --help` 现在优先解析项目环境（相对路径以仓库为准），不可执行时查找宿主 `python3`；所选解释器缺失、无法运行或版本低于 3.12 时给出中文原因与 `uv run --offline --locked` 准备指引，exit1。版本探测隔离执行，真正帮助保留正常 sitecustomize 守卫；帮助不运行 uv/writer/检查、不写字节码/证据。`verification-status` Contract 同步。补充：旧 heredoc 也依赖 `cat`，不能精确描述为只需 bash/dirname；这不影响当前错误分支缺陷的成立。
3. **部分采纳，采用原建议的最小替代。** 保留历史 `A1_GROUP`/`A2_01_GROUP` 公共对象及独立 A1 入口，不在本轮删除对象或改变运行接口。新增独立一致性回归核对 name/suffix/required/dependencies；两条精确源路径的显式 legacy 声明按有序 AST 纳入敏感摘要。改声明并重绑 SHA 后仍须 S3 确认。未全局扩大 `GROUP/SUFFIX/REQUIRED` 模糊匹配，也未在生产 registry 强制不一致拒绝；保留原 `GROUPS` 策略变化的分析行为。
4. **采纳。** `verification-status` Contract 保留帮助、回执、独立人工预期不会自动跟随生产、reader 支持格式等可观察保证，删除 fixture 路径和模拟 executor 等维护细节，链接测试规则与本轮新覆盖台账。详细证明边界收于新台账。
5. **部分采纳并纠正覆盖事实。** 原有 `tests/test_scope_shared_dag.py::test_writer_rejects_unverified_scope_metadata_pointer` 已有 `unlisted_scope`、`non_scope_reference`、`invalid_graph` 三类负例，`invalid_graph` 覆盖审计 issues→空引用集，因此不采纳「无失败分支用例」的判断。A8 编排使用公开 `load_scopes`/`audit_scopes` 校验自己的冻结指针职责合理，未为单一调用者新增服务层或让 registry 反向依赖 audit。采纳诊断改进：审计失败在既有 `scope_drift` 下附 `item=scope_references.<受控AuditReason>`，不回显异常/非法内容；新增公共 writer 负例断言具体 item。没有新增 reason、字段或格式版本。

### Spec

1. **采纳补充留痕，拒绝追改旧冻结台账。** 在新 `docs/verification/issue-126-review-followup.json` 补充 `tests/test_tmp_path_cleanup.py` 于 `622d3ab`→`bfc7117` 的旧/新 SHA、精确变化与理由；四次子会话显式 `all` 保留原三个成功会话的上限场景及权限/软链断言，模块仍 8 例。本轮不修改该测试或 `gate-failure-repair.md`/历史 JSON。
2. **采纳口径说明，无代码缺陷。** `cli.py` 场景只改一行中央 SHA；7 个直接组 + 3 个额外下游 = 10 个受影响组，`groups` 与 `affected_groups` 各自表示这些口径。
3. **采纳口径说明，无代码缺陷。** 实际 scope 哈希边为 41→0；42 为旧描述口径，既有台账已披露。不改冻结历史凑数。

独立新增 `tests/test_scope_review_r4.py` 共 15 例：帮助 5、legacy 一致性 1、两路径四字段敏感声明 8、A8 受控诊断 1。有效 red 为 12 failed / 3 passed（CLI 3、分类 8、诊断 1 命中），green 为 15 passed。原六冻结测试、原 78 例准备测试、285 固定模块/5281 例和实际 required/reader/Schema/migration 保持。合批后的完整开发验证和精确重绑见本轮新台账；未运行本次完整 `check-offline` 或 live，历史门禁不能充当新树结论。


### 合批最终开发验证

与 r4 合批后：相关 pytest **237 passed / 206.59s**；`check-compatibility all` **176 passed / 325.79s**（入口总 326.39s，exit0）。低版本 shim 加强后 R4 模块再次 **15 passed / 3.96s**，实际模拟 3.11 执行探测，并拒绝树外将门槛误放宽至 3.10 的变异。全项目 Ruff check、format（988 文件）、mypy（710 source files）通过。默认及显式基线 collect 审计均 exit0，无既有漂移、固定 285 模块/5281 例、skip0/deselect0。本批共重绑四个中央 SHA（原三份 source 加 r4 的 `check-offline`），展开 18 条原成员资格；四个候选均为 mechanical source/support。旧成员、用途、分母、41 refs/0 scope hash 保持，原六冻结测试及旧证据不改。精确旧新 file/entry SHA、消费闭包与历史留痕见 `docs/verification/issue-126-review-followup.json`。本次未运行完整 `check-offline` 或 live。
