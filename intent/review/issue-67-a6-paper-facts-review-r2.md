# Code review：issue-67 A6 论文事实底座（r2）

- 分支：`integration/67-paper-facts`（HEAD = `706ecb1`，工作树 = HEAD，仅 untracked 的 r1 审查文件）
- Fixed point：`main` = `bd6afba80d0c9b1fa8b455c332be3329b97d513d`
- Diff：`git diff main...HEAD`（三点，129 文件，+15743/−132，15 个 commit；映射 #68 文档冻结 → #69 DOI 事实 → #70 Feed 发现 → #71 仲裁/人工修正 → #72 版本关系 → #73 输入映射 → #74 隔离恢复 → #75 A6 验收 → `706ecb1` 验收后修复）
- Spec 来源：#67 正文 + 5 条评论裁决（实施前补充 T/B、D1–D4、补充澄清、N1–N11、N1/N2）；#68–#75 正文验收标准与各 2 条评论；`docs/contracts/paper-facts.md`、`docs/adr/0030`、`docs/verification/a6-requirements.md`（#68 冻结产物，同为后续票 spec）。权威顺序：最新用户裁决 > 不冲突澄清 > 实施前默认 > 原正文；实现者完成报告不作 spec。
- 标准来源：`AGENTS.md`、`GLOSSARY.md`、`docs/agents/{python-conventions,testing,cli-output,invariants,documentation,refactor,calibration,llm-evidence,scope,domain}.md`、`docs/adr/`、`docs/contracts/`、`pyproject.toml` + Fowler smell 基线（仓库无 `CODING_STANDARDS.md` / `CONTRIBUTING.md`）
- 方式：Standards、Spec 两轴由两个并行只读 reviewer subagent 独立审查后聚合；两轴分列，未混合排序；未修改代码、未创建 commit、未写 Issue。

### 口径限制（两子代理披露，聚合者整理）

- 两子代理均为无 shell 只读环境（read/grep/find/ls/watchdog_diff）：`git diff` 逐 hunk 未做，以「工作树=HEAD 现状」审查；**全部 pytest 未运行**；功能性行为差异均为静态推断（各条已标「未复现」）。
- Issue 评论原文：Spec 轴取自 `/tmp/paperradar-a6-tickets/`、`/tmp/paperradar-67/` 快照（与 GitHub 线上当前一致性未核实，若线上有更新评论需补充）；Standards 轴以 ADR/Contract 内嵌转述为准（评论原文未核实）。聚合者会话内 gh 可用并直接核对了 #67 首条评论、#68/#69/#72 评论全文与各票正文，未见与子代理引用相悖内容。
- 聚合者抽查（静态复核属实）：H1/A1——`docs/contracts/paper-facts.md:114` 明文「双包装…为 `unsupported_form`」，`src/paper_radar/papers/doi.py` URL 分支无双包装检测、`tests/fixtures/paper_facts_v1.json:50,110,114` 三条双包装向量期望 `invalid_doi`；H6——`README.md:282`、`docs/contracts/stage-inputs.md:372`「七份」字样存在；C2——`tests/test_version_relations.py` 确以 `test_requires_merge_stays_successful_when_candidate_material_is_reused` 钉死该行为。

---

## Standards

# PaperRadar A6 r2 · Standards 轴审查报告

- 固定点 `main=bd6afba`，被审 HEAD=`706ecb1`（`integration/67-paper-facts`）。`watchdog_diff` 确认工作树无已跟踪改动（仅 untracked 的 r1 审查文件），所读即 HEAD 状态。
- **口径限制（重要）**：本环境实际只读工具为 `read/grep/find/ls/watchdog_diff`，**无 shell/git/gh/pytest**。故 `git diff main...HEAD` 的 15 个提交无法逐 hunk 读取（`watchdog_diff` 不覆盖已提交区间），Issue #68–#75 评论与 #67 两条裁决评论原文（ADR-0030 内链接）无法直接访问，裁决以 ADR/Contract 内嵌转述为准（未核实原文）；所有 pytest **未运行**。本报告按「当前 HEAD 实现状态 vs 文档化标准」完成；按「逐 hunk diff」口径**审阅未完成**，不以「通过/零问题」代替。已跳过 Ruff/mypy 强制项。

## (a) 硬违规（文档化标准违反）

**H1 [P1] 契约 §2.1「双包装→unsupported_form」与实现/固定向量不一致**（聚合者已静态复核属实）
- 位置：`src/paper_radar/papers/doi.py:39-58`（URL path 与 `doi:` 前缀双包装最终落入结构检查）；`tests/fixtures/paper_facts_v1.json`（`doi:doi:10.1/a`、`https://doi.org/https://doi.org/10.1/a`、`https://doi.org/doi:10.1/a` 均固定 `invalid_doi`）。
- 引用：`docs/contracts/paper-facts.md` §2.1「拒绝 userinfo、非默认端口、www 子域、尾点主机、**双包装**与任何 query/fragment…为 `unsupported_form`」；任务书规定「契约文档自身与实现不一致即违规」。
- 影响：reason 语义与下一步指引错位（「请核对 DOI 字面值」vs「改用裸 DOI/规范 URL」）；契约与向量二者必有一错。
- 测试核查：固定向量即测试期望（`test_paper_inputs.py` DOI 向量参数化），向量与契约文本互相矛盾。
- 复现/限制：静态核对（未运行）。
- 最小建议：改契约一句（明确 path 级双包装判 `invalid_doi`）或改 doi.py 归因+向量；二者取一，同步 a6 固定材料。

**H2 [P2] `corrupt_reference` 被挪用于非损坏类存储失败（§9 词表失真）**
- 位置：`src/paper_radar/papers/service.py:170-172,179-181,190,213,238,262`（缺库/未初始化/旧 revision/verify 缺 `--data-root` 一律 `CORRUPT_REFERENCE`）；`storage/database.py:54-58` 的准确原因与指引被丢弃。
- 引用：契约 §9 `corrupt_reference` 定义「业务引用链、归属、制品 kind 或显式核验字节损坏」；`docs/agents/cli-output.md`「错误信息写明具体原因和用户可采取的下一步」。
- 测试核查：`tests/test_paper_cli.py::test_paper_missing_database_does_not_create_it`（107-113 行）只断言退出 1 与不建库，不断言 reason；无「缺库应提示 db upgrade」用例（覆盖不足）。
- 复现/限制：静态路径核对；未复现。
- 最小建议：让 `StorageError` 原样穿透（CLI 已处理其 reason/中文指引），或按 storage reason 细分受控输出。

**H3 [P2] 受控字段路径失真：统一误报 `source_url`**
- 位置：`src/paper_radar/papers/text.py:37,54`（`require_public_url` 固定 `path="source_url"`）；调用点 `text.py:66`（关系 locator）、`text.py:130`（候选 locator）、`text.py:135-137`（provider/query_key）。
- 引用：契约 §9「原因可带受控字段路径/ID」（含义为准确路径）；cli-output.md 同上。影响：provider 输入错被显示为 `invalid_observation（source_url）`，误导排障。
- 测试核查：`tests/test_paper_inputs.py::test_authenticated_or_parameterized_urls_cannot_enter_query_output`（约 238-263 行）覆盖四位置但只断言 reason，不断言 path。
- 复现/限制：静态；未复现。最小建议：`path` 作为参数传入。

**H4 [P2] 公共边界类型未落成契约领域类型**
- 位置：`src/paper_radar/papers/models.py:159`（`relations: tuple[object, ...]` vs 契约 §6 `tuple[RelationInput, ...]`）、`:146`（`source_kind: str`）、`:343`（`RelationInput.kind: str`）。
- 引用：`docs/agents/python-conventions.md`「用明确的领域类型和受控 enum / reason 表达状态与原因」。影响：静态约束缺失，导致 `relations.py:27-31`、`rules.py:100-121` 等处反复 `model_validate` 防御回转。
- 测试核查：`test_paper_inputs.py`、`test_version_relations.py` 只断言运行期受控拒绝，无类型断言；mypy 因 `object` 不报。
- 复现/限制：静态（已核行号）。最小建议：改 `tuple[RelationInput, ...]` + `Literal` 化 `source_kind/kind`，校验逻辑前移。

**H5 [P2] `paper show` 文本输出未显示「当前选择依据」**
- 位置：`src/paper_radar/papers/cli.py:80-127`（selection 仅在 trace 分支打印，:122）；JSON 输出含 `selection`。
- 引用：契约 §8「show 显示 …、摘要是否存在与截断状态、**当前选择依据**；trace 显示全部版本/修订/选择…」。测试核查：`tests/test_paper_cli.py` 只断言摘要脱敏/退出码，无 show 文本 selection 断言。复现/限制：静态。最小建议：show 文本补一行当前 selection（reason/selected_at）。

**H6 [P2] 文档计数漂移：「七份主要文件」残留**（聚合者已核对该字样存在）
- 位置：`README.md:282`、`docs/contracts/stage-inputs.md:372-373` vs `README.md:370`、`scripts/check-offline` help 与 `docs/verification/offline-evidence.md`（八份主要文件/十份 JSON）。
- 引用：`docs/agents/documentation.md` 同步要求。测试核查：无文档断言。最小建议：两处补「A5 当时」限定或改八份。

## (b) 基线 smell（判断题，附成本/风险）

- **S1 Duplicated Code**：`save_observation` 对同一 retry 查询执行两次并拆开 digest 分支（`repository.py:208-209`、`:260-261`）；合并为一查一分支。成本小、风险低。
- **S2 Duplicated Code**：`rules.py:42-51`（`choose_fields`）与 `:133-139`（`explain_fields`）各自重建 `highest` 映射，与 §1.3「说明复用纯仲裁权威」精神相悖；抽共享 helper。成本小。
- **S3 Duplicated Code**：三写路径各自记账 acquisition/event_no/修订（`repository.py:337-391`、`feed_repository.py:274-322`、`manual.py:150-194`），字段默认已分叉（feed 用 first_seen、manual 固定 parser 1、raw_doi 写法不一）；抽 `record_acquisition`。成本中、风险中，需三来源回归。
- **S4 冗余写**：`relation_repository.py:423-425` 先写 `response_bytes_retained`，`:444-448` 再整体覆盖；删首写。成本极小。
- **S5 私有名跨模块**：`_utc/_uuid/_candidate/_conflict/_insert_candidates/_saved_result` 被 5+ 模块导入（`feed_queries.py:10`、`relation_repository.py:19`、`fact_reads.py:12`、`queries.py:12,32`、`feed_repository.py:18-20`、`manual.py:24-28`），与 `refactor.md` 单一职责/单模块可读相悖；公开化改名。成本低（含 a6_scope 哈希重绑）。
- **S6 Mysterious Name**：`manual.py:139-151` 合成 `ObservationInput` 命名 `material` 仅为算 `interpretation_digest`；改名或抽摘要函数。成本极小。
- **S7 Divergent Change**：`queries.py`（~614 行，读模型+历史校验+选择语义混载）、`relation_repository.py`（~560 行，写/读/校验 17 函数）、`load_trace` 8 层嵌套；拆 writes/reads 为后续扩展减压。成本中（须 scope 重绑），纯移动风险低。

## (c) 被仓库标准抑制的候选 smell

- 封闭 `StrEnum` reason + `GUIDANCE` 表（`errors.py`）→ 契约 §9/reason_catalog 抑制 Repeated Switches。
- `papers/__init__.py` `__getattr__` 薄转发 → 契约 §1.1 公共边界与 A1–A5 既有模式抑制 Middle Man。
- 读面 fail-closed 广 `except`（`queries.py:511-512` 等）→ §10「外键合法也不能通过」的闭包要求抑制；其 reason 混同问题已并入 H2，不另计。
- a602/a603 temp-table 重建同形异构、a604 位置耦合重插 → migration 字节冻结（invariants「只追加」）抑制 Duplicated Code 主张。
- `validate_feed_item` 函数内延迟 import、CLI 延迟加载服务 → 与备份 CLI 延迟加载一致的仓库模式，不列为 Middle Man。

## (d) 文档/契约同步情况

GLOSSARY 新术语齐备（来源观察/字段候选/版本修订/取得事实/人工字段修正/Feed 发现记录/一致读视图/历史重建）；ADR-0030 含各切片落点与 #67 两条用户裁决链接；backup-restore（a604 head、`validate_all` 闭包、组合恢复段）、artifact-store、stage-inputs（#73 映射）、verification-status（`.a6.json` 组绑定）、README（paper show/trace、a604）均已同步；reason_catalog 与文档一致性由 `tests/test_paper_inputs.py::test_reason_catalog_and_guidance_are_complete_and_private`（117-124 行）固定。不符点即 H1/H5/H6。依赖方向核查：`config/screening/stage_inputs` 无反向导入 `papers`（grep 全量核过），符合契约 §1。

## (e) 抽查文件与测试

源码：`papers/` 全部 23 个文件逐一读毕；`storage/migrations/versions/a601–a604`；`backup/service.py`（verify_contents 段）、`backup/manifest.py`；根 `cli.py` 注册段；`pyproject.toml`、`scripts/check-offline`、`docs/agents/*` 全部、`docs/adr/0030`、五份契约与 offline-evidence/a6-requirements 相关段。测试（读）：`test_paper_inputs.py`、`test_paper_cli.py`、`test_pending_relation_roles.py`、`test_paper_model_validation.py` 全文；`test_paper_service.py`、`test_source_arbitration.py` 用例名与关键断言；`tests/fixtures/paper_facts_v1.json` 全文。断言核查示例：`test_cross_request_role_conflict_is_atomic_and_original_role_can_register`（整笔拒绝+原角色可登记+validate_all）确证 HEAD 提交语义；`test_paper_show_and_trace_default_hide_every_abstract` 确证摘要脱敏与 `--verify-source-bytes` 退出 0。**全部 pytest 未运行**（无 shell）；H1/H2/H3 行为差异未复现（静态推断，路径已核对）。

**完成状态**：按「当前实现 vs 文档标准」的 Standards 审查完成，共 6 项硬违规 + 7 项判断题 smell；按「逐 hunk diff」与「Issue 评论原文/裁决核实」口径未完成，相关结论均已标注静态/未核实。

---

## Spec

# PaperRadar A6 r2 · Spec 轴审查报告（#67/#68–#75）

- 审查对象：`integration/67-paper-facts` HEAD=706ecb1（工作树=HEAD，仅 untracked 的 r1 审查文件）；按任务书 commit→票映射核对 A6 模块/docs/tests 现状。
- 权威顺序：#67 最新用户裁决（D1–D4、N1/N2、轻量重复取得、完整新解释）> 不冲突澄清 > 实施前默认 > 原正文；`docs/contracts/paper-facts.md`、ADR-0030、a6-requirements.md 为冻结 spec 产物。

## (a) 缺失 / 不完整

**A1 双包装 DOI 的拒绝类别与冻结 Contract 相反（文档化硬要求 / 文档-实现不一致，P2；聚合者已静态复核属实）**
- 位置：`src/paper_radar/papers/doi.py:27-58`（URL 分支无双包装检测，`https://doi.org/doi:10.1/a` 落入结构正则）；`tests/fixtures/paper_facts_v1.json:50,110-111`（期望 `invalid_doi`）。
- 需求引用：`docs/contracts/paper-facts.md:114`「拒绝 userinfo、非默认端口、www 子域、尾点主机、双包装与任何 query/fragment…为 `unsupported_form`」；D2 裁决要求两类别可区分且 D2-1「拒绝表达的是输入能力边界」落在 reason 含义。#67 评论 DOI 向量仅要求「明确结论」；矛盾出自 #68 冻结文本与实现/向量之间。
- 测试核查：`test_paper_inputs.py` fixture 参数化断言即 `invalid_doi`；无「双包装→unsupported_form」用例（覆盖缺口而非测试失真）。
- 复现/限制：静态核对（无 shell，未运行）；路径已逐行核对。
- 影响：不影响规范值与接受集合，仅冻结词表 v1 的类别语义自相矛盾，阶段 C 分支会拿到与 Contract 相反的类别。
- 最小建议：二选一对齐——URL path 检出 `doi:`/二次 URL 前缀时返回 `unsupported_form`，或修订 Contract 该句与向量为 `invalid_doi`（后者需按 N4 视作词表文档修订）。

**A2 `mapping_result` 未进入 A6 验收格式核对（测试缺口，P2）**
- 位置：`scripts/a6_scope.py:12-21`（FORMAT_VERSIONS 七项）、`scripts/a6_acceptance.py:112-131`（`_formats()` 同样七项）。
- 需求引用：Contract §1 将 `mapping_result=1` 列入「格式权威一次固定…验收独立固定期望」；#75 正文仅点名五项+stage_inputs+backup，故按子票不算缺失，但对 Contract §1 是验收矩阵缺口。
- 测试核查：`tests/test_a6_formats.py` 仅核对 fingerprint 常量与纯模块隔离；全仓无 `mapping_result` 格式断言（已 grep）。生产侧 `mapping_models.py` 有 `format_version: Literal[1]`，可读。
- 复现/限制：静态（未运行）。
- 最小建议：`FORMAT_VERSIONS`/`_formats()` 增加 `mapping_result: 1` 并从生产常量读取。

## (b) 越界（scope creep）

未发现。S2/S3/S4 收缩均已落实：`tables.py` 的 feeds 仅 UUID+URL（无 ETag/健康列）、无 duplicate_candidates/merge_events/manual_intakes/任务表；CLI 仅 show/trace（`papers/cli.py`，无写入/映射/指纹命令）；migration 仅 a601–a604 顺序追加；阶段 C 暂缓项（强冲突持久化、parser 固定样本回归、未验证来源假设）均以硬门禁/NOT_ASSESSED 保留（Contract §7/§10、a6_scope.NOT_ASSESSED），未计为缺失。

## (c) 实现有疑

**C1 标签形状近似实现仍拒绝非 HTML 泛型写法（功能限制+文档张力，P2；r1-F1 至 706ecb1 未处理）**
- 位置：`src/paper_radar/papers/text_rules.py:7-10` `_MARKUP`；`<String>` 匹配 `</?[A-Za-z][A-Za-z0-9:_-]*…>` 被拒。
- 需求引用：N1 用户裁决「只做 LF 化+去首尾空白，其余原样保留」；Contract §5.1（paper-facts.md:167）「数学比较…须接受…不能用『含尖括号就拒绝』的近似实现」，且仅「真正标签、注释」应拒；`<String>` 非真实标签。
- 测试核查：fixture `text` 向量含数学比较/`<p>`/`<!-- -->`/`<b title>`/孤立代理（`test_paper_inputs.py` 参数化）；无泛型向量——覆盖不足。
- 复现/限制：正则静态判定（无 shell 未复现；r1 已实跑 `List<String>`→`invalid_text`，本轴未重跑）。
- 影响：A6 无适配器当前成本为零；阶段 C 含 `List<String>` 类题名将被整笔拒。
- 最小建议：按「已知 HTML 标签闭集/标签+属性语法」判定并补固定向量（`List<String>` 接受、`<script>` 拒绝）。

**C2 `requires_merge` 按论文级状态污染无关写入结果（语义判断，P2；r1-F2 未处理且已被测试钉死；聚合者已核对该测试存在）**
- 位置：`src/paper_radar/papers/relation_repository.py:418-441` `save_acquisition_result` 全库扫描 DOI 命中即置 `requires_merge`。
- 需求引用：#72 评论点2「`requires_merge` 是『观察与关系已保留、需人工动作』的成功结果」；Contract §7「`not_retained` 是有效且未新增来源材料/候选正文的独立结果」、§9 两词条词义。
- 测试核查：`tests/test_version_relations.py:258-287` 断言不含关系、仅复用候选的重复取得（正常应 not_retained）返回 `retained/requires_merge`——测试钉死了与 Contract §7 张力并存的行为（覆盖存在、语义与词表冲突）。
- 复现/限制：静态；r1 曾实跑同场景，本轴未重跑。
- 影响：调用方按 reason 分支会把普通元数据更新当待人工动作；`not_retained` 语义被掩盖。
- 最小建议：reason 仅在本次取得新增/复用关系时置 `requires_merge`，论文级状态由 `trace.relations[].state` 暴露；或补 Contract 明文定义该行为后保留现实现。

**C3 `trace --verify-source-bytes` 缺 `--data-root` 报 `corrupt_reference`（CLI 原因选择，P2；r1-F3 未处理）**
- 位置：`src/paper_radar/papers/service.py:179-181`（`data_root is None → CORRUPT_REFERENCE(path="data_root")`）；errors.py 文案「请停止使用该批次并检查备份」。
- 需求引用：#74 评论点3「一次定名…默认关闭、额外只读 I/O、只报原因与位置」；Contract §8「data-root 在来源字节核验时指向既有制品根」。
- 测试核查：`tests/test_paper_cli.py:60-96` 核验用例始终同传两参数；无缺参组合（覆盖不足）。
- 复现/限制：静态路径确认；未构造临时库复现（无 shell）。
- 最小建议：CLI 参数层校验两选项同现（退出 2）或引入独立受控原因。

## 披露：工具、来源与完成状态

- 实际可用工具：read/grep/find/ls/watchdog_diff。**无 shell**：gh、git diff/show、pytest 均不可运行；本轴全部结论为静态核对（各发现已标「未复现/未运行」）；r1 实跑结果仅作历史引用。
- Issue 来源：本会话 gh 不可用，#67 最终正文+5 条评论、#68–#75 正文/评论/完成报告、两项追加裁决取自 /tmp 缓存快照（`/tmp/paperradar-a6-tickets/`、`/tmp/paperradar-67/`）；快照与 GitHub 线上当前一致性未核实（若线上有更新评论则本报告需补充）。
- diff 界定：无法运行 `git diff main...HEAD`；以工作树（=HEAD 706ecb1）现状审查，129 文件逐文件 diff 未枚举，a1–a5 旧 scope 重绑定文件仅抽查相关 seam；`verification-runs/912c5913…` 等运行证据未直接读取（引完成报告与 r1 只读核对记录）。
- 静态核对未见偏差的高风险面（抽样依据：代码+测试名+断言语义）：D1 DOI↔版本一对一（tables.py identifiers 约束）、D3 回摆不回退且 last_seen 不参与仲裁（feed_repository 以 first_seen 记 observed_at；test_feed_discovery.py:42-76）、四源优先级与稳定 tie-break（rules.py；test_source_arbitration.py）、完整新解释四测试（test_paper_reparse.py）、映射指纹不变量矩阵（test_paper_mapping.py）、并发/强杀/一致读（test_paper_process.py）、a405 非空迁移与依赖 AST 守卫（test_paper_migrations.py）、隔离恢复端到端（test_paper_recovery_combined.py）、706ecb1 修复（test_pending_relation_roles.py 5 例）。
- 完成状态：审阅完成（受上述来源/工具限制），非「零问题」；发现 5 条（A1/A2/C1/C2/C3），无 P0/P1。

---

## 总结（按轴一行，不跨轴排名）

- **Standards**：13 项发现（6 硬违规 H1–H6 + 7 smell 判断题 S1–S7）；轴内最重 **H1**——契约 §2.1「双包装→`unsupported_form`」与实现/固定向量 `invalid_doi` 相反（P1，聚合者已复核属实）。
- **Spec**：5 项发现（A1/A2/C1/C2/C3），无 P0/P1；轴内最重 **A1**（与 Standards-H1 同源的契约-实现类别矛盾，两轴独立收敛），其次 C2（`requires_merge` 覆盖 `not_retained` 语义、已被测试钉死，属待用户裁决的语义取舍）。


## 2026-10-22 审查后处置索引

以上正文描述原基线 706ecb1 的历史审查，不代表修复后工作树或新的全量门禁状态。
逐条裁决、证据、未采纳理由与验证边界见[统一处置表](issue-67-a6-paper-facts-review-resolution.md)。
本报告全部编号均已登记：Standards H1、Standards H2、Standards H3、Standards H4、Standards H5、Standards H6、Standards S1、Standards S2、Standards S3、Standards S4、Standards S5、Standards S6、Standards S7、Spec A1、Spec A2、Spec C1、Spec C2、Spec C3。
原文“15 commits”经 git log main..706ecb1 --oneline 核对为 14 条（含 merge），在统一处置表更正，保留原文快照。
