# 阶段 A10 双轴审查 r1（#100 / #101–#108）

- 固定点：`main` = `4ec450fc43950ae96b8a8ed8acb29b641af5a7b3`
- 被审：HEAD = `8f65371`（分支 `integration/a10-fixture-audit`）；审阅开始与结束时工作树均干净（`git status --porcelain` 为空）
- diff：`git diff main...HEAD`（三点，对 merge-base）＝ 169 files, +89882/−211；`git log main..HEAD --oneline` 共 38 个提交（含 19 个 merge）
- 提交列表（压缩，功能提交按序引用）：`de1efb7`(#101) → `c08c385`(#102) → `c501dd3`/`a0ce648`/`c193125`/`e67120d`(#103) → `052f79f`/`6043913`/`1b3e2ea`(#104) → `34bc2ec`/`a935a55`(#105) → `6ddd426`/`718407c`(#106) → `2a7bb75`(#107) → `ce10659`/`814ad37`(#108) → `97db787`/`3a38392`（审阅清理）→ `8f65371`（merge），间以 19 个 merge 提交
- 两轴分别由独立只读子 agent（`oracle`，**均具备 `bash`**）执行，互不共享上下文；本文按轴分列，**未跨轴合并或重排**
- 执行说明：首次尝试用 `reviewer` 角色，其工具集**无 `bash`**（与用户「确保两个 subagent 均被赋予 bash 权限」的要求不符，且无法运行 diff/pytest/gh），该次降级报告**作废未采用**；按 A9 r2 先例改用 `oracle` 角色同协议重试，两轴均通过第 0 步 bash 门禁（`git rev-parse HEAD` = `8f65371…`）
- 聚合者独立验证：`main` 可解析、diff 非空、`gh` 可用、父票 #100（OPEN）与 8 张子票 #101–#108（全 CLOSED，`subIssuesSummary completed=8/8`）状态核对；两轴报告内的实跑命令与结果**未由聚合者重跑**，均为各轴自报并披露

## 工具与来源（两轴共同）

- **规格来源**（Spec 轴 gh 直读，2026-11-03，按 `docs/agents/issue-tracker.md`）：#100 正文＋6 条评论（四项裁决、获取边界更正、接线补充、通道枚举裁决）＋ #101–#108 正文与全部评论（含 #103 两轮上限 Owner 裁决、各票补充澄清与集成修复记录）；关系计数核对一致（#100 `blockedBy` 4/4 全 CLOSED、`subIssues` 8/8；子票 sub/blocked 计数与 nodes 全一致，parent 均 #100）；**评论优先于正文、后续用户裁决优先**，已按时间序取最新裁决
- **标准来源**（仓库无 `CODING_STANDARDS.md` / `CONTRIBUTING.md`）：`AGENTS.md`、`CLAUDE.md`、`docs/agents/{python-conventions,testing,invariants,llm-evidence,documentation,cli-output,scope,refactor,calibration,domain}.md`、`GLOSSARY.md`、`README.md`、`docs/adr/`（重点 0032/0033/0034）、`docs/contracts/`（重点 `fixture-audit.md`）、`docs/verification/`、`intent/draft.md`；另加 skill 指定 smell baseline（已在两轴提示词 `/tmp/a10_review_common.md`、`/tmp/a10_standards_axis.md`、`/tmp/a10_spec_axis.md` 全文粘贴，含用户增强要求与 800 词上限）
- **两轴实跑**（全部离线、只读）：Standards 轴 `ruff check`（All checks passed）、`mypy src/paper_radar/fixture_audit`（Success, 41 files）、pytest 两批 **282 passed**（225＋57）；Spec 轴 pytest 两批 **338 passed**（194＋144）、只读 `./scripts/verification-status aec731e203e54e11b712da6d65dabf96` → **passed / verified / applicability=same**、6/6 检查、5251/5251 passed、0 skipped/deselected、exit 0、14 份 JSON 齐备（含 `.a10.json`，`stage_a/live/rpc_verified` 均 False）——#108 完成评论的终态声明已由 Spec 轴独立复现，非转述
- **两轴均未运行**：完整 `./scripts/check-offline`（约 20–27 分钟，属门禁职责）；全部 live（真实网络/模型/PDF 解析/凭据/NAS）；未建 commit、未改任何仓库文件与 Issue 状态
- **缺失来源**：Standards 轴无 `gh`（Issue 裁决原文未核实，以 ADR/契约内嵌引用为准）；`tests/fixtures/a10_coverage.json`（69,393 行冻结台账）两轴均按冻结材料抽样核对，未逐行验证

## Standards

### 工具与来源

- **实际工具**：`bash`（只读 `git`/`rg`/`sed`）＋`read`/`grep`/`find`/`ls`；实跑 `uv run --offline --locked` 下的 ruff / mypy / pytest（无 gh、无网络写、未改任何文件；结束时 `git status --porcelain` 为空）。
- **实读标准**：`AGENTS.md`、`docs/agents/{python-conventions,testing,invariants,documentation,cli-output,refactor,llm-evidence}.md`、ADR-0032/0033/0034、`docs/contracts/fixture-audit.md`（120 行已读，余下抽样）。
- **实读代码**：`fixture_audit/` 全部核心模块（service/acquisition/sampling/abstract/interpretation/pdf 的 service+rules、source_http、errors、两个 cli、history_rules、resume_rules、models 抽样）、`backup/{service,manifest}.py`、`cli.py`、`verification_status.py`、`check-offline` 的 diff hunk、`a2_scope.py`/`a9_scope.py` 代表性 hunk（其余 `a*_scope.py` 为同模式哈希重绑）、GLOSSARY/.gitignore hunk、`tests/fixtures/a10_coverage.json` 仅头 60 行抽样。
- **实跑验证**：`ruff check src/paper_radar/fixture_audit scripts/a10_*.py tests/test_{audit,fixture,a10}_*.py` → **All checks passed**；`mypy src/paper_radar/fixture_audit` → **Success, 41 files**；`pytest -q tests/test_audit_acquisition.py …test_backup_failures.py -p no:randomly` → **225 passed**；补跑 migrations/restore/CLI 子集 → **57 passed**（两批合计 282）。
- **缺失来源**：GitHub Issues #100–#108 裁决原文（Standards 轴无 gh），以 ADR/契约内嵌引用为准，Issue 级差异未核实。

### 符合项（抽查证据）

- 网络边界（python-conventions.md）：`source_http.py:167-169` `trust_env=False, follow_redirects=False, proxy` 显式；8 MiB/30s/逐跳白名单；`SourceExecutor` 为 Protocol，测试用 `httpx.MockTransport` 全离线（tests/test_audit_http.py:14-35），符合 testing.md「不联网」。
- 确定性/I-O 分离与短事务：`acquisition_service.py:284-336` started 短事务→事务外 fetch→结算短事务，符合 ADR-0034「写锁外核验材料」。
- 受控 enum/reason＋中文 guidance（cli-output.md）：`errors.py:37-63` 每条 reason 含原因与下一步；fixture/audit CLI 帮助中文、`--help` 纯本地有测试（tests/test_audit_cli.py）。
- 文档同步（documentation.md）：GLOSSARY 词条修订、ADR-0033/0034、`contracts/fixture-audit.md`、`docs/verification/a10-*`、README、`intent/draft.md` 同批更新；`check-offline` 帮助文案同步十二/十四份。
- 既有文件修改（backup 接入第三个 `validate_all`、`cli.py` 挂两个子应用、`a*_scope.py` 哈希重绑）均为最小增量，符合各阶段冻结验收模式。

### 发现（均经本轴实读核实，全部为判断线索级，无硬违规）

- **F1｜Duplicated Code｜P2**：连接模板 `open_database→require_current_revision→BEGIN( IMMEDIATE)→…→finally dispose` 在 6 个 service 约 20 处重复（`rg` 计数：acquisition 16 行、service 13、sampling 10、abstract 9、pdf 8、interpretation 7）。影响：一致性意图散落，快照加载链 `load_sampling(connection, load_audits(connection))` 同步重复。已有测试核查：行为有 282 例覆盖，无语义错误；这是维护性建议非缺陷。最小建议：抽一个连接上下文管理器＋`full_views(connection)` 帮助函数；机械改动、风险低。
- **F2｜Duplicated Code（值漂移风险）｜P2**：`resume_rules.py:46-57` 内联 `versions` 字典与 `history_rules.py:9-21` `HISTORICAL_V1` 十个字段→版本值逐项相同但未互相引用（前者取当前代码常量，后者硬编码历史值，语义不同、值恰好一致）。影响：未来新增任一 `*_rules_version` 需双处同步，漂移会造成 resume 与 replay 判定不一致且无测试能捕捉语义差。已有测试核查：`test_audit_replay.py`/`test_audit_resume.py` 覆盖各自路径，未断言两表恒等。最小建议：加一条断言当前常量组 == `HISTORICAL_V1` 的回归测试（机械、可执行），或在 resume_rules 注释交叉引用。
- **F3｜Duplicated Code｜P2**：`_raw()`（`sampling_service.py:87` vs `abstract_service.py:87`，仅 path 字符串不同）、`show_audit()` 线性查找三份（acquisition/sampling/abstract）、`list_audits()` 同形三份。分层拆分是 ADR-0034 的有意设计，故仅建议提取共享只读助手，不改变分层。
- **F4｜冗余重复执行｜P2**：`service.py:825-846` `validate_all()` 末尾逐一执行的四次调用与 `_validate_audit_materials()`（:529-534）完全相同；且 `validate_all()` 首行 `self.list(history=True)` 在有 data_root 且含 audit_reference 时已触发一次 `_validate_audit_materials()`（:401）→ 同一次 `validate_all` 全部材料被校验两遍。只读幂等、无正确性影响（`test_fixture_audit_references.py:82` 通过），纯性能/重复。最小建议：`validate_all` 末尾改调 `self._validate_audit_materials()` 并让 `list()` 跳过或复用结果。
- **F5｜Duplicated Code｜P3**：token→kind 四元映射两份：`abstract_parser.py:131-135`（dict）与 `:317-321`（publisher 分支内联元组）。新增 token 须改两处。最小建议：模块级常量。
- **F6｜Primitive/magic number｜P3**：`acquisition_service.py:312` 重写 `8 * 1024 * 1024` 而不复用 `source_http.py:33` `SOURCE_BYTE_LIMIT`；限额调整时易漂移。最小建议：导入常量。

**放行的基线条目**（仓库文档优先）：Repeated Switches——类别/路线分派是 ADR-0033 封闭表设计；Speculative Generality——四通道枚举仅注册 http 是 ADR-0034 明文要求；Middle Man——`FixtureAudit` 门面 1:1 转发是 `contracts/fixture-audit.md` 点名的公共 API 边界；Data Clumps——`(database, data_root)` 对是仓库既有 ArtifactStore 模式。Mysterious Name/Feature Envy/Message Chains/Refused Bequest 未发现。

### 完成状态与未验证范围

- 本轴**完成**（新增代码全部通读＋既有文件 hunk 逐个核对＋离线验证实跑全绿）。
- 未运行：完整 `./scripts/check-offline`（约 20 分钟，属聚合者/门禁职责）；`tests/fixtures/a10_coverage.json` 69,393 行仅抽样；`interpretation_service.py` 后段与部分 records/tables 为通读抽样非逐行；Issue 裁决原文未核实（无 gh）。

## Spec

### 工具与来源

- **实际工具**：`bash`（只读 `git`/`rg`/`sed`/`python3`/`ls`、离线 `uv run --offline --locked pytest`、只读 `gh issue view`）＋`read`/`grep`/`find`/`ls`。无写操作；工作树始末均干净。
- **规格源（gh 直读，2026-11-03）**：#100 正文＋6 条评论（四项裁决、获取边界更正、接线补充、通道枚举裁决）、#101–#108 正文与全部评论（含 #103 两轮上限 Owner 裁决、各票补充澄清与集成修复记录）。关系计数核对一致：#100 blockedBy 4/4 全 CLOSED、subIssues 8/8 全 CLOSED；#101–#108 sub 0/0、blocked 计数与 nodes 全一致，parent 均 #100。评论优先于正文，已按时间序取最新裁决。
- **实读实现**：`src/paper_radar/fixture_audit/` 45 个文件全部结构核对＋关键模块精读（source_http、acquisition_*、sampling_*、abstract_*、interpretation_*、service、models）、`a1001_fixture_audit` migration、`backup/service.py`/`cli.py` diff、`scripts/{a10_scope,a10_acceptance,a10_coverage,a2_full_acceptance,verification_status,check-offline}` diff、`fixtures/a10/historical-v1.json`、ADR-0033/0034、`docs/contracts/fixture-audit.md`、`docs/verification/a10-requirements.md`、draft §4.3/§13.1/§2341、GLOSSARY diff。
- **实跑**：`pytest -q tests/test_audit_{acquisition,http,sampling,sampling_categories,matrix,matrix_boundaries,resume,replay,reinterpret}.py tests/test_fixture_{registry,pdf}.py tests/test_a10_{entry,status,acceptance,isolation,behavior_coverage}.py -p no:randomly` → **194 passed**（124s）；恢复子集 `tests/test_audit_{acquisition,resume,matrix}_recovery.py tests/test_a10_{complete,reference}_recovery.py tests/test_a10_integrity.py` → **144 passed**（127s）。只读复核 `./scripts/verification-status aec731e203e54e11b712da6d65dabf96` → **passed / verified / applicability=same**、6/6 检查、5251/5251 passed、0 skipped/deselected、exit=0；14 份 JSON（含 `.a10.json`，`stage_a_verified/live_verified/rpc_verified` 均 False）实际存在——#108 完成评论的终态声明**已独立复现，非转述**。

### 逐票正确（证据压缩）

- **#101**：Pydantic 注册 v1 四用途三依据（`models.py`）；同键同字节幂等/异字节拒绝、显式替换链（`test_fixture_registry.py:134,153`）；`fixtures/a10/historical-v1.json` 含六 DOI/JGR `10.1029/2025JD043927`/`11094/103589`；a704→a1001 单一 revision；五份 Frozen Contract 未动（contracts 检查仍四份历史＋Read）；ADR-0033/0034 按更正后编号落地。
- **#102**：PDF 字节经 original_pdf 核验、backend 期望独立追加不随替换继承（`test_fixture_pdf.py:45,113`）、三态定位 shape_only。
- **#103**：计划冻结唯一 N（`Field(ge=5, le=10)` 默认 5）、邮箱缺失连计划不建立（`test_invalid_contact_cannot_create_even_a_plan`）；**两轮上限**（`source_http.py:157` `for round_no in (1, 2)`，`retry_count=rounds-1`）符合 2026-10-26 Owner 裁决；每轮 30s 单调时钟贯穿＋connect 10s、8 MiB 解压累计、5 跳、Retry-After>5s→`deferred_retry_after`；`channel_not_installed` 终态零请求（`test_uninstalled_channel_is_a_frozen_zero_request_result`）与 `not_attempted` 分列；邮箱只入 UA（`source_http.py:173`），`b"audit@example.org" not in raw` 断言备份字节；doiRA 路由（`acquisition_policy.py:65`）。
- **#104**：类别闭集四行表＋负例（`sampling_rules.py:28-75`：`dc:type=article`/`dc.type=论文`/Crossref/DataCite）；Wiley 分节原样保存不判定；三态台账（评论补充）与 AIES citation_doi→RA 路线均有测试。
- **#105**：正向识别＋`unrecognized_page_shape`；主区块隔离（abstract-en/PLS 只记定位）；Feed 前置/尾随剥离；截断五信号（`short_under_100`/`trailing_ellipsis`/Read more/阅读更多等，`abstract_parser.py:103-107`）；A6 仲裁复用 `from paper_radar.papers.rules import SOURCE_PRIORITY, choose_fields`（不改 A6）；高优截断/低优完整冲突单独计数（`abstract_rules.py:302-307`）；汇总粒度含 `strategy_version`/`channel`（`abstract_models.py:108-120`）。
- **#106**：resume 网络前全身份核验（`test_resume_checks_full_execution_identity_before_any_mutation_or_http`）；started→`outcome_unknown`；replay 历史版本缺失拒绝；新 parser 仅服务 API。
- **#107**：`abstract_audit`↔`journal is None` 整计划绑定（`models.py:113`）；backup 第三个 `FixtureAudit.validate_all` 接线（`backup/service.py` diff）；非空 a704 升级与重哈希篡改拒绝测试实跑通过。
- **#108**：required A10 组依赖 (A1, 完整 A2, A3, A6)（`a2_full_acceptance.py`）；`.a10.json` 入 `SUPPORTED_GROUP_FORMATS`；A8/A9 计数 13→14 已改（`test_a8_entry.py:44` 等）；`NOT_ASSESSED` 17 项逐项覆盖票面清单（含 `four_journal_live_5_to_10`、`ams_403_strategy`、`browser_render`、`stage_a`）；37 个新测试文件全部由 `a10_scope` 登记（120 项绑定）；693 项需求台账含正文＋评论 permalink 与 `covered/superseded/not_assessed/operational` 四态；FORMAT_VERSIONS 含注册/parser/acquisition_strategy/channels。
- **无越界**：src 既有文件仅 3 处小改（backup×2、cli 挂载），无 A10 无关改动；无新依赖/lockfile 变更/浏览器导入。

### Findings

**无发现**（在下列未核实范围内）。未发现缺失、走样或越界；各票「行为子集验收、完整门禁 #108 收口」的拆票裁决与实际交付边界一致，未把暂缓项（渲染运行时、AMS 403、四刊 live）误宣称为已交付，也未把 NOT_ASSESSED 项当作本次缺失。

### 完成状态与未验证范围

本轴**完成**。未核实项：①完整 `./scripts/check-offline` 未由本轴重跑（约 27 分钟；以只读 `verification-status` 对 run `aec731e2…` 的独立复核替代，结论非转述）；②693 项台账按冻结材料抽样（约 20 条＋结构核对），未逐条验证映射正确性，`review_state=reviewed` 为登记自述；③`docs/verification/a10-scope-review.md`（162 行）与 scope 审阅过程真实性未独立重演；④真实 live 行为（四刊、渲染、凭据）按票面明确未验收，本轴未尝试；⑤其余非 A10 测试文件（94 个）的 a704→a1001 字面量替换仅抽样核对，完整门禁的 5251 用例由该 run 回执背书。

## 一行总结

- **Standards**：6 项发现（F1–F6，全部 P2/P3 判断线索级、无硬违规）；本轴最重 = **F2**（`resume_rules.py:46-57` 与 `history_rules.py:9-21` 两份版本表值恰好一致但无恒等断言，未来漂移将使 resume 与 replay 判定不一致且无测试可捕捉）。
- **Spec**：0 项发现；本轴最重 = 无（在披露的 5 项未核实范围内）。


## 本次逐项核实与处置（#100 follow-up）

原报告以上内容逐字保留；以下是实现者针对基线 `8f653711986266403a7b7e25c2d98a24c2ece896` 的独立核实。r1/r2重叠项合并实现，每个编号分别结论。公共测试seam沿用已批准的FixtureAudit、真实临时SQLite、ArtifactStore、backup/restore和HTTP替换边界；不引入live、新依赖、Frozen/A6/migration或已登记版本变化。范围与独立计数见 `docs/verification/a10-scope-review.md`，台账指针见 `tests/fixtures/a10_coverage.json`。

| 编号 | 性质与结论 | 证据、理由与改动/验证指针 |
| --- | --- | --- |
| F1 | 维护建议，部分采纳 | 重复只读事务成立；新增 `fixture_audit/service_reads.py::read_snapshot`、`find_plan`，Acquisition/Sampling/Abstract保留各层loader及原错误path。写事务/快照捕获/六服务异常语义并不相同，拒绝把全部连接模板统一成跨层框架。`test_audit_sampling.py`、`test_fixture_audit_references.py`及恢复子集验证公共行为。 |
| F2 | 维护建议，拒绝恒等断言/合表；采纳交叉注释 | 当前执行准入与已发布历史回放是两项独立语义。未来当前升级时必须拒绝旧计划继续，但仍可回放历史v1，强制两表恒等会禁止这一合法状态。`resume_rules.py`/`history_rules.py`加交叉说明；`test_audit_replay.py::test_frozen_v1_replay_does_not_consume_current_default_version` 同时断言旧回放保持、当前版本漂移拒绝resume。 |
| F3 | 维护建议，采纳一致行为 | 三服务list/show共享窄只读助手；sampling/abstract/interpretation保留材料读取统一到 `read_material(..., path=原路径)`。没有统一不同层的loader或提高查询层级，原 `sampling.material`、`abstract.material`、`data_root` 保持。公共子集和恢复验证原行为。 |
| F4 | 性能重复成立，采纳 | 原有引用且有根的validate_all经list与末尾两次全材料核验。改私有 `_list(..., verify_audit_materials=False)` 供validate_all使用，末尾统一 `_validate_audit_materials()`；公共list仍核验，root=None不会跳过全核验。既有完整引用/损坏材料/backup恢复负例验证闭包；不添加断言私有调用次数的镜像测试。 |
| F5 | 维护建议，采纳 | `abstract_parser.py::_EXTRA_TOKENS` 统一四个token映射，保持原有插入顺序及Feed/publisher各自遍历/隔离语义；`test_audit_matrix_boundaries.py` 等既有公共解析行为在最终门禁覆盖。 |
| F6 | 维护建议，采纳 | acquisition保留材料上限复用 `source_http.SOURCE_BYTE_LIMIT`，不改变8 MiB及解压/两轮语义；`test_audit_http.py` 24例通过，相关acquisition及完整门禁继续验证。 |

本次已实际执行的验证（均 `uv run --offline --locked`、`-p no:randomly`、离线）：

- red：`pytest -q tests/test_audit_sampling.py -k full_execution` → **20 failed / 2 passed**（修前证据；预期失败）。
- green：`pytest -q tests/test_audit_sampling.py` → **25 passed**。
- 公共行为批次：`pytest -q tests/test_audit_sampling.py tests/test_audit_reinterpret.py tests/test_audit_replay.py tests/test_fixture_registry.py tests/test_fixture_pdf.py tests/test_fixture_audit_references.py` → **91 passed**。
- 恢复/HTTP批次：`pytest -q tests/test_fixture_pdf.py tests/test_fixture_recovery.py tests/test_fixture_pdf_recovery.py tests/test_audit_http.py tests/test_audit_sampling_recovery.py tests/test_audit_matrix_recovery.py tests/test_audit_resume.py` → **75 passed**。
- `ruff check .` → **All checks passed**；`mypy src/paper_radar/fixture_audit` → **42 source files通过**。

A10固定分母由425→448（37模块保持），旧scope计数不变；只读scope审计/收集不代替执行。最终门槛为代码、台账和本两份处置报告提交到当前分支且稳定后，重新实际运行 `./scripts/check-offline` 退出0，并以 `./scripts/verification-status <新run_id> --json` 复核 `passed/verified/applicability=same`。实际run_id和最终结果保存在忽略的verification-runs及工作树外 `/tmp/paperradar-a10-review-followup/result.md`，不在完成后回填本报告导致身份变化。此处不借用旧run 5251通过替代新门禁。

未运行/未授予资格：四刊live、来源长期稳定/B阻断判据、渲染/授权/API/仓储运行时、PDF/Docling、生产模型/Pi RPC、校准、NAS及完整阶段A；本次离线修复不改变这些NOT_ASSESSED边界。

提交前补充实跑：`pytest -q tests/test_a10_scope.py tests/test_a10_coverage.py tests/test_audit_matrix.py tests/test_audit_matrix_boundaries.py tests/test_audit_acquisition.py -p no:randomly` → **79 passed**；`./scripts/audit-verification-scope --collect --json` → **exit0 / collection=ok / issues=[] / affected_groups=[]**；正式配置 `uv run --offline --locked mypy` → **619 source files通过**；全树Ruff format/check通过。一次额外 `mypy .` 把Git忽略的旧verification-runs维护脚本纳入而失败（587 errors/10历史脚本），没有修改那些历史材料；正式门禁配置范围通过。
