# Issue #150 Docling Extra 双轴审查（r2）

- 固定点：`main` = `542265c0971fb0e8bcee4c2a7019295fc9686ac7`（`git rev-parse main` 已确认）
- 被审：HEAD = `bc8ab83f2a78510129d55a11b37cc8d6120103d0`；审阅开始时工作树无未暂存修改
- diff：`git diff main...HEAD`（三点，对 merge-base）＝ 45 files, +5215/−78
- 提交（`git log main..HEAD --oneline`）：`f6736d2`(v2 工具链与历史回放) → `34beefe`(CPU extra 供给与安装证据) → `ac584cb`(runtime 依赖诊断) → `d7172ae`(集成证据与冻结准备) → `6c660c2`(审阅修复) → `bc8ab83`(A10 依赖守卫对齐)
- 两轴由独立只读子 agent（`worker`，**两轴均被明确授予并实际使用 `bash`**）并行执行，互不共享上下文；本报告按轴分列，**未跨轴合并或重排**
- 本任务约束：不修改代码、不创建 commit、不 push、不改 Issue 状态、不运行 live。本文件是唯一写入产物。
- 目录内已存在 `issue-150-docling-extra-review-r1.md`；本条为**第二次独立双轴审阅（r2）**，两轴子 agent 未读取该文件，聚合者仅读取其抬头以对齐格式，不继承其结论。

## 工具、来源与完成状态（两轴共同）

- **规格来源**（按 `docs/agents/issue-tracker.md`，`gh` 2.101.0 可用）：`gh issue view {150,151,152,153,154} --comments` 与 `--json subIssues,subIssuesSummary,blockedBy,parent,assignees,state`；#150 正文含 Problem Statement / Solution / 20 条 User Stories / 13 条 Implementation Decisions / Testing Decisions / Out of Scope。优先级：评论中的后续用户裁决 > 正文；实现者完成报告仅作线索。#150–#154 均为 `CLOSED`，`CLOSED` 不等于已验证。随 diff 交付的台账（`docs/verification/issue-150-*`、`issue-152-*`、`issue-153-*`）按实现者自述处理，与代码/测试/契约交叉核对。
- **标准来源**（仓库无 `CODING_STANDARDS.md` / `CONTRIBUTING.md`）：`AGENTS.md`、`docs/agents/{python-conventions,testing,invariants,documentation,cli-output,verification-scope,llm-evidence,scope,refactor,roadmap}.md`、`GLOSSARY.md`、`docs/adr/`（含 0008、0010 与供给/固定范围相关条目），另加 skill 指定的 Fowler smell 基线（已在两轴提示词中全文粘贴）。
- **两轴子 agent 实际工具**：`read`/`grep`/`find`/`ls`/`bash`（只读 `git`、`gh`、`rg`、`sed`、`pytest`、`uv run --offline --locked`），未获得/未使用写入意图；未改仓库、未建 commit、未改 Issue。
- **实跑（子 agent 各自执行）**：Standards 轴 `uv run --offline --locked python -m pytest -q -p no:cacheprovider tests/test_docling_runtime.py tests/test_doctor_docling_runtime.py tests/test_docling_extra_supply.py tests/test_docling_import_smoke.py tests/test_docling_toolchain_v2.py` → **69 passed / 4.21s**；Spec 轴六个新 D1 模块 → **95 passed**，`test_a10_isolation`/`test_scope_shared_dag`/`test_config_extraction`/`test_doctor_process` → **82 passed**，stage_inputs 系 → **116+101 passed**，`./scripts/check-compatibility all` → **176 passed 退出 0**，`uv lock --offline --check` → 0，`--collect-only` → 6518 节点，`scripts/audit_verification_scope.py --base 542265c --json` → 1214 成员 / 289 计数 / 41 refs、`baseline_issues=[]`、无 hash_drift、12 条 `confirmation_required`。
- **聚合者独立复核（只读、静态或实跑）**：`tests/docling_runtime_support.py:21` 为 `4.13.0.92`，而 `scripts/check_docling_imports.py:32`、`pyproject.toml`、`uv.lock:757` 为 `4.14.0.94`（见 S5/Spec-3，已复现为静态事实）；`src/paper_radar/docling_runtime.py:271-290` 在 `PLATFORM_SUPPORTED` 之后必以依赖聚合覆盖 `reason`，probe 级不会返回 `platform_supported`（见 S2）；`tests/test_docling_runtime_process.py:41-52` 的 help 参数化未设置 `DOCLING_FORBID_PROBE`（见 Spec-2）；`docs/roadmap.md:61` 的「已完成」与 `docs/verification/issue-150-extra-delivery.md:7-8` 的「不宣称完整门禁已 passed」并列存在（S1/Spec-1）。
- **未运行**：完整 `./scripts/check-offline`（约 40 分钟且需本机 socket 权限，超出只读授权，**未运行**）；真实 3.14t / 非 x86_64 平台；模型加载、解析、正文质量；全部 live。
- **缺失来源**：树外正式门禁回执与 `run_id`（#154 裁决要求留树外）、树外三解释器/无 extra 环境原始库存日志、12 条 S3 确认输入。两轴均声明「本轴完成」，但覆盖面有下文各自明示的收缩。

## Standards

### 发现

**S1｜硬违规（状态与证据一致性）— 对外宣称已完成但树内证据自述未完成**
- **影响**：`docs/roadmap.md:61` 将 Extra 标为「已完成」；`docs/roadmap.md:101` 与 `docs/verification/issue-150-extra-delivery.md:7-8`（「完整验收结论待…本文不宣称完整门禁已 passed」）、`issue-150-gate-fixes.md`（修复后「未重跑完整门禁」）、`issue-150-review-fixes.md`（「本次未运行完整门禁」）并列存在。
- **标准引用**：`docs/agents/roadmap.md`「implement-spec 收尾时…标记完成」＋`docs/agents/verification-scope.md`「单个 spec 的实施与收口」第 5–6 步（先完整门禁退出 0 / passed-verified-same，再收尾）。`docs/agents/documentation.md`「只用现在时描述已实现的公共边界」。
- **已有测试核查**：文档状态无测试可覆盖（不适用）；门禁结论本身在仓库内不可复现（回执留树外），仅台账自述。
- **复现/限制**：静态对照四份文档，无运行命令。**未核实** #150 收口评论所述 `run_id 88b314b3…` 与最终树身份是否对应本次 HEAD（回执不可访问）。
- **最小建议**：由用户裁决保留哪种状态；若保留「已完成」，把台账 `:7-8` 改为指向 #150 收口回帖并删除「不宣称 passed」的现行时表述。

**S2｜硬违规（Contract 现状描述）— 契约列出实现无法在 probe 级返回的取值**
- **影响**：`docs/contracts/docling-runtime.md:37` 把 `platform_supported` 与其它 9 个 reason 同列于 `RuntimeProbe.reason` 表；`src/paper_radar/docling_runtime.py:273-290` 在平台支持后必以依赖聚合覆盖 `reason`，probe 级恒不返回该值（只有 `PlatformFacts.reason` 使用它）。
- **标准引用**：`docs/agents/documentation.md` Contract 规则「只用现在时描述已实现的公共边界」。仓库许可的封闭分派（`RuntimeReason` 单枚举同时服务两级）本身不违规，问题是表格未标注作用域。
- **已有测试核查**：`tests/test_docling_runtime.py:43` 只断言 `result.platform.reason`；`tests/test_doctor_docling_runtime.py:81` 断言的也是平台子项——无任何用例断言 `probe.reason == "platform_supported"`，属「覆盖不足＋表格作用域歧义」。69 节点全绿说明该取值不可由测试观测。
- **复现/限制**：静态读码确认；建议的最小反例是一个断言 `probe.reason == "platform_supported"` 的用例，它必然失败。
- **最小建议**：表格拆成 probe 级 / 平台级两列，或在该行注明「仅 `PlatformFacts.reason`」。

**S3｜判断题（possible Duplicated Code，已发散）— GIL/ABI 分类两处结论可能相反**
- **影响**：`src/paper_radar/docling_runtime.py:135,175`（`Py_GIL_DISABLED` **或** `sys.abiflags` 含 `t` 即拒绝）vs `scripts/check_docling_imports.py:122-125`（只看 `Py_GIL_DISABLED`）。在 3.14t 且带 GIL 启用的组合下，smoke 会输出 `gil_enabled=true` 并退出 0，而 probe 判 `platform_unsupported`；`docs/contracts/extraction-config.md:69` 明确 free-threaded 不支持。
- **标准引用**：`docs/agents/python-conventions.md`「用明确的领域类型和受控 enum / reason 表达状态与原因」＋单一权威；smell 基线 Duplicated Code。
- **已有测试核查**：`tests/test_docling_runtime.py:283+` 覆盖 probe 侧；`tests/test_docling_import_smoke.py` 无 `abiflags` 用例（覆盖不足）。
- **复现/限制**：**未复现**（无 3.14t 解释器），静态推断。
- **最小建议**：smoke 复用同一分类函数，或补 `abiflags` 判断与负例。

**S4｜判断题（possible Shotgun Surgery / 版本权威重复）**
- **影响**：`scripts/check_docling_imports.py:22-33` 硬编码 9 个精确版本＋opencv，与 `src/paper_radar/docling_toolchain.py` 权威清单并行；与 `docs/contracts/extraction-config.md:33`「唯一权威」、`docs/contracts/docling-runtime.md:52`「不维护第二份版本清单」冲突。
- **已有测试核查**：无一致性用例（无覆盖）。测试内字面量属 D1「人工预期」许可，已抑制、不报。
- **复现/限制**：静态对照 `pyproject.toml` / `uv.lock` / 权威清单；未运行。
- **成本与风险**：改一次版本需同步 6+ 处；改成从 `toolchain_supply("docling-2.135.0-cpu-v2")` 派生成本约半小时，风险低，但会动 `scripts/check_docling_imports.py` 的 D1 账（需重登记）。
- **最小建议**：派生 9 项，opencv 单列常量；或在契约中显式声明 smoke 为第二来源。

**S5｜判断题（人工数据漂移）— 测试库存与产品锁不一致，且因 `expected_version=None` 永不被发现**
- **影响**：`tests/docling_runtime_support.py:21` `opencv-python-headless: "4.13.0.92"`；`uv.lock:757`、`pyproject.toml`、`tests/test_docling_extra_supply.py`、`scripts/check_docling_imports.py:32` 均为 `4.14.0.94`。`src/paper_radar/docling_runtime.py:269` 对该包 `expected_version=None`，任何版本都 passed。
- **已有测试核查**：`test_only_explicit_selected_backend_is_required` 等只覆盖发现/缺失，属「仅缺某种实现方式」。
- **复现/限制**：聚合者已核对 `uv.lock:757` 与两处字面量；未运行变异验证。
- **最小建议**：改为 `4.14.0.94`（一处字面量，成本 <5 分钟）。

**S6｜判断题（possible Shotgun Surgery / Divergent Change）— 新增一个 doctor scope 落在 14 处字面量**
- **影响**：`src/paper_radar/pi_supply/cli.py:56,403,406,416,432,456,459,466,477,493`；`src/paper_radar/cli.py:69`；`src/paper_radar/doctor/cli.py:78,117,198`。
- **标准引用**：`docs/agents/refactor.md`「每个模块职责单一…目录结构反映功能分布」。另注：docling runtime 的 CLI 分派落在 `pi_supply/cli.py` 属 Divergent Change。
- **已有测试核查**：`tests/test_doctor_docling_runtime.py`、`tests/test_cli_import_compatibility.py` 覆盖行为；重复字面量无检查。
- **复现/限制**：`grep -rn docling-runtime src/` 共 14 处（静态）。
- **最小建议**：单一 `DOCTOR_SCOPES` 常量供 help/校验/分派共用；成本中等，风险低。

**S7｜判断题（possible Feature Envy＋重复形状）**
- **影响**：`src/paper_radar/doctor/docling_runtime.py:53-67` 用 `json.loads(material.config_json)["toolchain"]`（`Any` 流入 `ToolchainId`），与 `src/paper_radar/config/projections.py:56-64` 同形重复，而冻结 Schema `config/extraction.py:81-84` 已有 `toolchain`/`pdf_backend` 类型字段。
- **已有测试核查**：行为路径由 `test_required_checks_can_pass_while_fixture_and_runtime_remain_unassessed` 覆盖；类型安全无覆盖。
- **复现/限制**：静态；未运行。
- **最小建议**：在 `RuntimeConfigSnapshot` 上补返回 `Extraction`（或 `(ToolchainId, PDFBackend)`）的访问器，两处共用。

**合并的低优先项（因篇幅未展开）**：`src/paper_radar/docling_runtime.py:275-290` 的 `next(...)` 嵌套条件聚合与本模块 `_classify_*` 纯函数风格不一致，宜抽 `_dependency_reason(deps)`；`README.md:61-62` 复制了 `docs/contracts/extraction-config.md:69-71` 的支持面与安装点（`README.md` 不另维护事实副本边缘）；`tests/docling_runtime_guard/sitecustomize.py:74-80` 对 `-wal/-shm/-journal` 写入一律放行，弱化「禁业务写入」（有 `logical(database)` 兜底）。

### 已核对合规（无发现）
`docling-runtime.md` 采用固定骨架；D1 计数与实测一致（36/5/26/15/3/10，合计 85＋10）；`test_docling_import_smoke.py` 已在 `issue-150-review-fixes.md` 登记；`test_scope_shared_dag.py` 的 #146 期望补充在 `issue-150-extra-delivery.md` 有原失败与授权说明；工具已强制项（Ruff/mypy/format）跳过。

### 本轴状态
**完成**（仅 Standards 轴）。缺失来源：树外 `check-offline` 回执与正式 `verification-runs/`、树外 `.scratch` 库存日志。未验证范围：Issue 正文/评论裁决的完整一致性（Standards 轴未读 Issue，S1 仅按仓库文档判「状态与证据矛盾」，**未核实**是否有用户裁决支持提前标完成）、真实 3.14t / 非 x86_64 / 非 glibc 平台、完整离线门禁。

## Spec

### 发现

**1｜类别：文档化硬要求（验收证据缺口，未核实）**
- **需求**：#150 Testing Decisions「完整硬门禁」与 #154「在装好 extra 的支持环境运行一次 `./scripts/check-offline`…实际退出 0…同 run `passed/verified/same`」。
- **现状**：树内唯一索引 `docs/verification/issue-150-extra-delivery.md:7-8` 仍写「完整验收结论待…本文不宣称完整门禁已 passed」，而 `docs/roadmap.md:11,61` 已把 Extra 标「已完成」；`run_id 88b314b3…` 按 #154 裁决留树外。
- **已有测试核查**：无覆盖（不是 pytest 断言）；`scripts/check-offline` 本次 diff 为空，仍 `exec uv run --offline --locked python -m scripts.a1_acceptance`。
- **复现/限制**：**未运行**完整门禁（约 40 分钟、需本机 socket 权限，超出只读授权）；不据此声称门禁未通过，仅声称树内无法验证。
- **最小建议**：在台账「最终冻结与同次门禁」节补一句「最终结论以 #150 收口回帖为准（`run_id` 留树外）」，消除「已完成」与「不宣称 passed」并列；不要为改文档重跑或伪造门禁。

**2｜类别：测试缺口（覆盖不足，当前无功能缺陷）**
- **需求**：#150 decision 10「帮助不探测」/ US7。
- **现状**：`tests/test_docling_runtime_process.py:41-52` 只断言 help 退出 0、无文件产出，且哨兵的 socket/subprocess/SDK import 生效；但 `DOCLING_FORBID_PROBE`（`tests/docling_runtime_guard/sitecustomize.py:100-106`）只用于 basic/config/diff（同文件 151-196），未用于 `--help`。若将来 help 动态读取 metadata，不会被发现。
- **已有测试核查**：`test_help_cannot_probe_or_load_sdk` 的 4 个参数均属「覆盖不足」。
- **复现/限制**：聚合者已实跑确认路径——为 help 加 `DOCLING_FORBID_PROBE=1` 后 `doctor --help` / 根 `--help` / `config check --help` 均退出 0，可直接加断言（该手动验证属只读）。
- **最小建议**：help 参数化中同时设置该环境变量（一行）。

**3｜类别：可选建议（D1 人工库存陈旧）**
- **现状**：`tests/docling_runtime_support.py:21` 写 `opencv-python-headless 4.13.0.92`，锁与 `scripts/check_docling_imports.py:32` 为 `4.14.0.94`。probe 对 cv2 用 `expected=None`（契约明示由锁约束），故不假通过，但也不暴露 cv2 版本漂移。
- **已有测试核查**：`test_current_inventory_failures_are_structured_and_never_fallback` 仅测 cv2 缺失分支。
- **复现/限制**：静态核对 `uv.lock:757`（聚合者已复核）。
- **最小建议**：改字面量，或注明「不参与断言」。

**4｜类别：可选建议（规格未要求的输出）**
- **现状**：`doctor --scope docling-runtime` 复用 config 范围整段展示（`src/paper_radar/doctor/cli.py:118-177`：业务配置缺项、Profile、六阶段 readiness、外发类别）。#150 decision 10 只说汇总「仅表示基础、选择、平台和选定工具链依赖检查」；实跑可见 `stage=extraction result=passed`，有被误读为可运行的风险（`SUCCESS_NOTICE` 与 `not_assessed` 行已缓解，退出码不受影响）。
- **已有测试核查**：测试未断言其有无（无覆盖，但属展示层）。
- **复现/限制**：实跑于真实 extra 环境（`doctor --scope docling-runtime`，v2 配置）→ 退出 0，可见上述输出；v1 配置 → `docling-core invalid / dependency_version_mismatch` 退出 2。
- **最小建议**：不阻塞；若收窄，在 docling-runtime 范围隐藏决策/Profile/readiness 段，只保留基础、选择、平台、依赖四项。

### 已核对无问题
- v1 字节不变：`tests/fixtures/stage_inputs/extraction-v1.json` 的 `b22ab98c…`/`6ca4e413…` 与 `test_config_extraction.py:62` 的 `ba91a2df…` 均未改且通过。
- Typer 只进 `cli_constraints`，不进 backend identity/投影/StageInput（`tests/fixtures/docling_v2/*/projection.json` 无 typer、无 pypdfium2 下的 parse）。
- marker / 官方 CPU 索引 / `required-environments` 与 9 项精确版本与 `pyproject.toml`、`test_docling_extra_supply.py` 一致。
- 基础六包完整记录逐字不变：用 compact 与默认分隔符两种规范化分别复算，与 `test_a10_isolation.py` 及 `issue-152-docling-installation.json` 两套 SHA 均吻合（方法不同、结论一致），符合 #150 decision 7「不以全锁文本相等为判据」。
- stdlib-only 边界（import 期不探测、只用顶层 `find_spec`）；doctor 四态与退出码语义（必要项通过才 passed，不授予 Read/reuse）。
- 示例配置 check/compile/load；固定范围（D1 未进 A1–A10、`stage_a_verified=False` 未动）；`uv run --offline --locked` 多次调用前后 extra 仍在，与门禁环境真实性主张一致。
- #150 decision 9 正文的「中文下一步」与 #153 用户裁决「结构化事实与中文展示分开」冲突时，实现按裁决执行，不记为缺失。

### 本轴状态
**完成**（Spec 轴），无功能错误级发现。缺失来源：正式 `check-offline` 回执与 `run_id`（树外）、12 条 S3 确认输入（树外）、#152/#153 三解释器与无 extra 环境原始日志/库存（树外）。未验证范围：完整离线门禁、三解释器实装矩阵、真实无 extra 环境、模型加载/解析/正文质量、四刊 fixture、Read/reuse。

## 汇总

- Standards：7 项发现（其中 2 项文档化硬违规、5 项判断题）；轴内最重项为 **S1（路线图「已完成」与台账「不宣称 passed」并列）**。
- Spec：4 项发现（其中 1 项验收证据缺口、1 项测试覆盖不足、2 项可选建议，无功能错误）；轴内最重项为 **Spec-1（#150 完整门禁证据在树内无法验证，未核实）**。

## 本轮逐项核实与处置

以下记录逐项实现核实与取舍，不改写上文原审阅正文。实施基线是当前分支
`integration/issue-150-docling-extra` 的 `bc8ab83f2a78510129d55a11b37cc8d6120103d0`。
原报告完整字节先保存在树外 `/tmp/paperradar-review-original/issue-150-docling-extra-review-r2.md`，
SHA-256 为 `61896e678d8189822c43c4d940d056f61ddc00e635ac30a349141936fe1b7472`。
最初两份未跟踪报告是用户输入；实施前显式 base/target 审计 exit 0、无既有漂移。

### 编号处理表

| 编号 | 结论 | 核实、处理或拒绝原因 |
| --- | --- | --- |
| R2-S1 | 部分采纳 | 接受历史收口索引不足的可读性问题，在路线图 Extra 模块行补官方收口回帖；拒绝把“审阅者未访问树外证据”推导为实际门禁未完成，也不要求用户重新裁决既有完成状态或改写按次冻结台账。实际历史证据核验见下。 |
| R2-S2 | 采纳 | reason 表明确 `platform_supported` 仅为 `PlatformFacts.reason`，不是 probe 总 reason；其 next_step 标为无，因为平台子项没有该属性。实现原有分类不变。 |
| R2-S3 | 部分采纳 | 同意平台分类一致性改进。原报告“3.14t 且运行时启用 GIL 时 smoke 会输出 gil_enabled=true”的具体推断未实测；若构建标志仍为 1，旧 helper 实际输出 false，不能将该推断当作已复现事实。但受控公共回归确实证明旧 smoke 对含 t ABI、禁用 GIL 构建和未知 ABI 未作拒绝而返回成功。将既有读取入口提升为 stdlib `docling_platform_facts()`，由 probe/smoke 两个消费者复用；smoke 在 SDK import 前拒绝 unsupported/unknown，JSON 的 gil_enabled 也取同一事实，不增加第二套平台表。 |
| R2-S4 | 采纳 | 同 R1-Standards-3。smoke 从权威 supply 的解析组件及 CLI 约束派生，仅单列 cv2 锁值；不是新增第二来源。独立人工版本预期不变。实际审计证明该 smoke 是未绑定材料，本轮不需要刷新旧 D1 台账或历史哈希。 |
| R2-S5 | 采纳库存修正；拒绝扩张 probe 语义 | 人工 cv2 库存已改为 `4.14.0.94`。`expected_version=None` 是 Contract 明确的浅发现设计，具体 pin 由产品锁和显式安装 smoke 检查，不是 probe 漏验的精确版本承诺；不新增 cv2 语义版本或准入条件。 |
| R2-S6 | 不采纳本轮重构 | 14 个字面量承担根帮助、参数校验、选择限制、scope 路由和诊断投影等不同职责，不能单凭出现次数认定 14 份同义分派。现有注册保留于兼容的 CLI 装配入口；新建跨 Pi/CLI registry 并不能消除各范围不同必填参数/拒绝语义，却会扩大本轮范围和固定源码漂移。公共兼容组合 59 项及相关 CLI 回归通过，未确认行为缺陷。 |
| R2-S7 | 不采纳本轮接口扩张 | `runtime_checks` 只消费 check/load 验证后的快照；`config_json` 是已验证材料，不是未经信任的任意 JSON。投影同时消费原已验证材料，不重新套用当前 Schema 是其历史边界的一部分。未发现功能或类型流导致的错误；为此给 RuntimeConfigSnapshot 扩张 typed accessor 会涉及公共模型和回放边界，超出本次局部修复。 |
| R2-L1（低优先：依赖聚合） | 采纳 | 将嵌套 `next` 的 reason 优先级聚合提取成私有纯 helper，保持首个 inconsistent/mismatch 优先、再 missing、最后 passed 的既有行为。通过公共 probe 回归，不新增私有测试或镜像实现的断言。 |
| R2-L2（低优先：README） | 采纳 | 同 R1-Standards-2：删除支持矩阵、实测 patch 和审阅进度副本，保留命令与权威导航。 |
| R2-L3（低优先：sidecar） | 采纳 | 哨兵只允许本次显式数据库路径对应的 -wal/-shm/-journal；取消全路径后缀放行。新增真实冷进程负例逐个拒绝无关 sidecar 写入（退出 97、无产物），并以真实 WAL 库只读查询及显式 WAL 可写打开验证合法例外仍允许且原字节不变。原 CLI 树/逻辑库不变断言保留，不修改生产 SQLite 只读规则。 |
| R2-Spec-1 | 部分采纳 | 与 R2-S1 相同：采纳活导航与报告补历史回帖索引，拒绝修改历史冻结台账、重写旧 passed 或用旧 run 为新树背书。本轮按相关子集、CLI 及静态检查验证，未重跑完整门禁；旧 run 仅证明旧冻结树。 |
| R2-Spec-2 | 采纳 | 帮助 invoke 显式设置 `DOCLING_FORBID_PROBE=1`；四个帮助冷进程均通过。新增两类受控负例分别尝试 metadata.version、顶层 find_spec，均被哨兵以 97 拒绝；SDK、网络、子进程、业务 I/O 守卫继续启用。 |
| R2-Spec-3 | 采纳 | 与 R2-S5 相同：修正独立人工 cv2 库存，保留 probe 的发现检查契约，实际精确 pin 继续由锁与 smoke 负责。 |
| R2-Spec-4 | 采纳 | runtime 范围只显示基础、选择、平台、依赖和 Docling not_assessed；隐藏 Profile、六阶段 readiness、外发说明和其他能力类别。成功提示限定这些必要检查，不再引用未展示的 readiness。settings/snapshot 两个公共 CLI 例子仍 scope passed，fixture/native ABI 仍 not_assessed，且不含 stage=extraction passed 等误导行。basic/config 的输出、退出码和只读行为保持，并由原回归验证。 |

### 历史证据与当前适用性

重新读取 #150/#153/#154 正文与后续裁决，原要求未改变。#150 的
[历史收口回帖](https://github.com/MeteoBoy4/PaperRadar/issues/150#issuecomment-6611646055)及
[#154 收口回帖](https://github.com/MeteoBoy4/PaperRadar/issues/154#issuecomment-6611644710)
记载旧冻结树真实门禁。已访问本地树外 `.scratch/issue-150/final-gate-rerun/summary.json`
及对应 `verification-runs/`：

- 旧命令实际 exit 0，六项检查与十一组结论均 passed，同次历史查询为 `passed/verified/same`。
- 原 HEAD 为 `bc8ab83f2a78510129d55a11b37cc8d6120103d0`、clean；原树 SHA 为 `66499e1cea60bae7e1378bd84b3d64198abf93f20c6fdea5dd836406c22943b4`，锁 SHA 为 `fcd6149e80b961d9bfa3c9b0015f3ddf2835c830f03b956506f300353c0f0905`。
- 实际重算 14 份正式文件和 52 条同 run 链接的哈希，全部匹配；原前后环境均 85 包，解释器、平台/GIL、库存及身份比较全部相同。
- 两份新报告出现时当前树已经不同，旧 run 的当前查询为 `passed/verified/different`；本轮代码与文档继续改变新树。`passed/verified` 是历史事实，`different` 表示当前不适用，二者不矛盾。

因此不改写“当次未运行完整门禁”的旧过程台账，不降低已完成模块状态，也不把上述旧通过提升为本轮新提交的正式结论。
本轮只运行下列开发检查；最终新树需要完整门禁时，仍须按用户明确指令在冻结身份上执行。

### 本轮验证、范围与限制

按 TDD 在已确认公共 seams 实施：ABI 四例、无关 sidecar 三例、CLI 输出两例先 red
再 green；新增 15 项 D1（其余为三个普通 GIL 成功、两个帮助探测拒绝、一个所选 WAL 正例）。
测试不调用私有 helper，不从生产清单构造预期。新增覆盖另记
[独立台账](../../docs/verification/issue-150-external-review-regressions.md)，不扩张旧登记。

| 实际验证 | 结果 |
| --- | --- |
| 七个 Docling D1 + doctor 冷进程 + extraction check/CLI/持久化/字段验证 | 263 passed；无 skip/deselect/incomplete |
| `uv run --offline --locked ./scripts/check-compatibility cli` | 59 passed；退出 0 |
| 触及的 8 个 Python 文件 Ruff check / format / 严格 mypy | 通过 |
| CPython 3.14.4 + extra + dev 的显式真实 SDK import smoke | 退出 0，85 包，gil_enabled=true；模型/PDF not_assessed |
| 显式 bc8ab83 base / 本地 integration target 的只读 scope 审计 | 退出 0；issues/baseline_issues 为空，无 hash drift、无本轮敏感确认或重绑 |
| `--collect` 固定分母审计 | 退出 0；1214 成员、289 计数记录、285 固定模块保持，无 collection skip/deselect |

使用 `uv run --offline --locked`，显式固定项目 `.venv`、`/usr/bin/python3.14` 和既有离线缓存。
本轮命令与 red/green 输出保存在树外 `/tmp/paperradar-review-original/`。
本轮触及的源码和 D1 未绑定旧组，活文档按既有分类维护；不改中央登记、固定成员、旧计数、
旧 fixture、冻结证据或历史台账。原报告包含的历史引用保持原文。

未运行完整 `check-offline` 或全量 pytest，也未重跑三解释器实装矩阵；三 minor 的新 ABI
行为使用受控事实验证。未实跑真实 3.14t、其他 patch/平台、模型加载、PDF 转换、正文质量、
四刊/中文 fixture、资源、Read/reuse、Pi live、正式校准或 NAS。真实导入成功不证明这些能力。
