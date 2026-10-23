# 阶段 A7 双轴审查 r1（#76 / #77–#84）

- 固定点：`main` = `191c9e11759463bd890ff15b9e77db87624dd8ac`
- 被审：`integration/issue-76-screening-tasks`，HEAD = `47dec58`，工作树干净、无未提交修改
- diff：`git diff main...HEAD`（三点，对 merge-base）＝ 141 files, +14407/−175；`git log main..HEAD --oneline` 共 19 个提交：#77（`ed36f41`、`fd7943e`）→ #78（`30441b4`、`84b0601`）→ #79（`593e878`）→ #80（`d4acd46`、`1ab22f2`）→ #81（`f9714cd`）→ #82（`251b57c`、`cc00aaa`、`6704376`、`cb01a72`、merge `8cf30a7`）→ #83（`eaa437f`）→ #84（`60cc945`）→ 无票号 integration 收尾（`72f9938`、`9ae6819`、`fddad9f`、`47dec58`）
- 两轴分别由独立只读子 agent 执行，互不共享上下文；本文按轴分列，未跨轴合并或重排。
- #84 完成评论明确：父票 #76 待 integration 最终双轴审查与修复完成后关闭——本报告即该审查的 r1。

## 工具与来源（两轴共同）

**子 agent 实际可用**：两轴均为只读 reviewer，实际仅有 read/grep/find/ls 类工具，**无 bash**——未自跑 `git diff`（以工作树终态 HEAD=`47dec58` 全量阅读替代新增文件审查，watchdog 确认无未提交改动）、未运行 pytest、未能自取 gh issue 原文。两轴均在各自报告内披露了该限制。

**聚合者补充验证（本会话，有 bash）**：

1. `gh issue view 76–84 --comments` 逐票取回正文与全部评论；Spec 轴提示中所列裁决摘要即由此逐字摘出，子 agent 据此 + 仓库冻结落地物审查，聚合者已核对摘要与 GitHub 原文一致。
2. 修改型（非新增）文件共 58 个；其中全部 6 个 src 文件由聚合者逐 hunk 复核（见「聚合核验记录」）。
3. 实跑：`uv run --offline --locked pytest -q tests/test_a7_*.py tests/test_screening_strict_json.py` → **538 passed in 291.16s**。

**不可用或未使用**：全量 `./scripts/check-offline` 未复跑（#77–#84 各报告了 run_id 与「实际返回 0」，本次未只读复核存档）；未运行任何 live（真实模型/RPC/Pi/Feed/Docling/NAS）。

**标准来源（Standards 轴）**：仓库无 `CODING_STANDARDS.md`/`CONTRIBUTING.md`；取 `AGENTS.md`、`docs/agents/{python-conventions,testing,invariants,calibration,llm-evidence,cli-output,documentation,refactor,scope}.md`、`GLOSSARY.md`、`docs/adr/*`（含本 diff 新增 0031）、`docs/contracts/*`（含新增 `screening-tasks.md`）。Ruff（lint+format）与 mypy 由 `check-offline` 强制，凡工具已强制的跳过不报。

## Standards

（成文标准优先；smell 基线仅作判断线索。子 agent 自述完成状态：新增核心代码全量阅读；**修改型文件无法逐 hunk 对照，该部分由聚合者补齐（仅 src，6/58）**；issue #76 评论裁决未核实，按 `screening-tasks.md` 内嵌裁决文执行；pytest 未运行——后两项缺口已由聚合者部分收窄，见文末。）

**Correct（成文标准符合，证据）**：领域类型/受控原因（`TaskReason`/`FailureKind` StrEnum + 固定 GUIDANCE，`errors.py`、`attempt_models.py`）；testing.md 负例规范（`test_a7_registration.py:65-85` 断言 `reason`/`build_reason`/`field`，非仅异常类型；migration 从上一 revision 升级且非空库，`test_a7_attempt_migrations.py:56-79`）；documentation.md（GLOSSARY.md:403-418、README.md:538-565、ADR-0031、screening-tasks.md 同步；§13 的 93 例为固定预期 `scripts/a7_scope.py:58` 非实测回填）；refactor.md（依赖扁平无循环，仅 `__init__.py:30` 引 service）；敏感 repr 隐藏、租约/预算/重放语义与契约逐条对上（`execution.py` claim/renew、`success.py` submit 双事务、`derive_status` 六态）。**未发现硬违规。**

### S1 阶段映射守卫七处重复（判断题·Duplicated Code→Shotgun Surgery 倾向）— P2
- **类别/影响**：同一段「`map_screening_inputs`→按 stage 取→PaperError/CORRUPT_REFERENCE 守卫」逐字重复 3 处（`service.py:173`、`execution.py:80`、`retry.py:40`）；`mapped = mapping.boundary if … else mapping.value` 另见 `success.py:282`、`query.py:45`、`integrity.py:47`、`attempt_integrity.py:82`。新增阶段或改守卫语义需散点改 7 处。
- **标准引用**：Fowler 基线 Duplicated Code/Shotgun Surgery（判断线索；无成文标准直接禁止）。
- **测试核查**：现有行为已覆盖（test_a7_*），重构不改语义。
- **复现/限制**：仅静态；行号已由聚合者 grep 复核一致。
- **最小建议**：`repository.py` 提 `require_stage_mapping(...)`（保留 query/success 的携 reason 变体）。成本小、风险低。

### S2 「每代至多两次」以字面 `2` 散布（判断题·Primitive Obsession）— P2
- **类别/影响**：契约 §1 的预算常量以字面 `2` 出现多处（`execution.py:117,141`、`attempt_rules.py:70,72,77,79,87`、`attempt_repository.py:108`；`tables.py` CHECK `attempt_no IN (1,2)` 属 DDL 可留）；同文件的 `LEASE_SECONDS = 600`（`attempt_models.py:19`）已具名，两相对照。
- **测试核查**：行为有覆盖；属可维护性判断。
- **复现/限制**：静态；聚合者复核 `execution.py:141`、`attempt_rules.py:70,77`、`attempt_repository.py:108` 确认。
- **最小建议**：`ATTEMPTS_PER_GENERATION = 2` 并于 attempt_rules/execution 引用。

### S3 同一成文文本规则三种实现（判断题·Duplicated Code）— P2
- **类别/影响**：「非空、无 HTML、≤2048 UTF-8 字节」（契约 §8/§11）在 `rules.py:58-65`、`rules.py:104-107`、`success_rules.py:29-42` 三处实现，机制不一（strict encode vs `errors="replace"` 长度再 strict 复检），lone surrogate 等边缘行为可能漂移。
- **测试核查**：各入口有正负例；无跨实现一致性向量。
- **复现/限制**：**未复现**（未构造边缘反例），静态推断；聚合者复核三处 2048 判定确实存在且机制不同（`success_rules.py:38` 用 `errors="replace"`）。
- **最小建议**：共享 `require_safe_text(value)`（异常类别经参数区分 INVALID_REQUEST/INVALID_CANDIDATE）。

### S4 N+1 查询形状（判断题，报告不阻塞）— P2
- **类别/影响**：`service.py:260-264`（逐 id `receipt_row`）、`success.py query()`（逐 id `_row`）、`query.py:55-115`（budget→task→逐请求嵌套查询）。单用户只读规模可接受；后续扩大可合并 join。仅记录。

**已抑制 smell（成文标准优先）**：`ScreeningTasks` 对四个内部 service 的转发是 Middle Man 形状，但契约 §8 明文规定其为「唯一任务服务」；stage 封闭 if/else 属 Repeated Switches 形状，仓库契约认可封闭集合分派；`(version_id, revision_no, selection_id)` 三元组是契约定义的「论文依据」回执字段（非 Data Clump）。

**Standards 完成状态**：完成（范围为上述工具限制；修改型文件中 src 部分已由聚合者补齐，余 52 个为 tests/docs/scripts 未逐 hunk 审读）。未发现需要新裁决的「仓库标准 vs 基线」冲突；未运行全量门禁。
**FINDINGS（Standards）: 4**（0 硬违规，4 条 P2 判断题 smell）— 最严重：S1（阶段映射守卫 7 处重复，改守卫语义需散点修改）。

## Spec

（权威顺序：#76 正文 + 各子票评论区**用户裁决**（优先于正文）> 仓库冻结落地物按被审材料处理；「已在本地完成…」为实现者报告，不作规格。子 agent 自述：gh 不可用，issue 原文**未直接核实**——该缺口已由聚合者消除（裁决摘要逐字取自评论原文，已复核一致）；pytest 未运行——A7 子集已由聚合者实跑全过。）

**Correct（静态核对一致的裁决要点）**：

- #77：`screening/validation.py:151-190` 重复键/NaN/Infinity/BOM/非 UTF-8/未配对 surrogate 均先于字段与业务校验报根 `$` `invalid_json`（受控类别迁移）；`tests/test_screening_strict_json.py` 只断言新类别；#77 代码/回归哈希入 `a7-requirements.md`。
- #78：`tables.py:85` `request_id` 全库 UNIQUE；`rules.py` 的 scheduled 回执为内容寻址摘要、`repository.py replay_request` 仅 manual/retry 依 request_id 重放；CAS 复用 `papers/queries.py resolve_revision`，`papers/__init__.py` 以 TYPE_CHECKING+`__getattr__` 延迟导出（`test_a7_registration_imports` 零 I/O 哨兵）；a701 挂 a604。
- #79：`LEASE_SECONDS=600`；六态词表含 `lease_expired`；`execution.py` reclaim/recover 一律 `outcome_unknown` 不退预算；`status`/`query` 只读 BEGIN；`storage/artifact_repository.py:178` created_at 直取 `datetime.now(UTC)`；续租句柄 `token_hex` 不透明；Contract §3 明文「无回收守护进程」「两次预算≠自动可继续」。
- #80/#81：三值适用性（current/historical/undeterminable+PaperReason），PaperFacts 独立一致读、允许滞后（Contract §10/§11）；value 接收/回读共用 `frozen.py → value_prediction_context(冻结语言) → validate_output("value_prediction")`。
- #82：`retry.py` 显式 `parent_task_id`；拒绝优先级＝精确重放→PaperError（缺摘要）→facts_changed→task_not_found→already_retried(successor_task_id)→already_succeeded→not_latest→not_failed，`test_a7_retry.py::test_mapping_reason_precedes_old_generation_and_exact_replay_remains_original` 断言 PaperReason 优先；唯一后继由 `uq_screening_parent` UNIQUE 约束保证（`test_retry_parent_uniqueness_is_enforced_by_sqlite`），a704 迁移按五表闭包/FK 开启重建。
- #83：`backup/manifest.py:27 BACKUP_DATABASE_REVISION="a704_screening_retry"`，跨版本可验证性限制绑该常量写入 `screening-tasks.md §7` 与 `backup-restore.md:332-335`；`validate_all` 以当前 A1/A5 重验。
- #84：新测试统一 `tests/test_a7_*.py`；`scripts/a7_scope.py` 固定模块/分母/哈希且不自绑；`verification_status.py:76` 认 `.a7.json` 格式 1。
- D1–D4（#76 裁决）：boundary 模型 `extra="forbid"` 连 null 语言字段都拒；相反语言事实 `CONTEXT_CONFLICT`、无语言检测器（D1）；无结果再绑定写入，当前适用性全派生（ADR-0031、draft §8.5 已同步，D2(a)）；`cli.py` 无 screening/paper trace 改动（D4 推迟）；not_assessed 明列 CLI、语言生产来源、RPC、两阶段编排等，**均系裁决内推迟，不构成本次缺失**。

**Findings**：无符合证据门槛的发现。(a) 缺失/部分、 越权、(c) 实现可疑三类在可核范围内均未发现：无越权行为（screening_tasks 无网络/子进程/自读系统时钟）。

**备查两点（非缺陷）**：`derive_status` 成功后 `remaining=2-used`（规格未定义、无矛盾）；`database_errors.py` 将非 busy IntegrityError 映射 `corrupt_reference`（BEGIN IMMEDIATE 串行＋事务内重查使其不可达）。

**Spec 完成状态**：本轴审阅完成（非「零问题」套话；结论以下列未验证范围为条件）。未验证范围：a7-requirements 所录哈希与 GitHub/工作树字节一致性；冻结哈希与工作树实际字节一致性（部分由聚合者 A7 子集实跑间接覆盖）；全部测试/check-offline 实际执行（A7 子集已由聚合者补跑全过）；「测试不得跨 created_at 与租约时间轴断言先后」的逐例纪律审计；141 文件逐提交归属。
**FINDINGS（Spec）: 0**（附 2 条备查非缺陷）— 无最严重项。

## 聚合核验记录（不改变轴内排序）

- S1：7 处 `map_screening_inputs` 调用点行号 grep 复核一致（service.py:173、execution.py:80、retry.py:40、success.py:282、query.py:45、integrity.py:47、attempt_integrity.py:82）。
- S2：字面 `2` 复核确认（execution.py:141、attempt_rules.py:70,77、attempt_repository.py:108 等）；`LEASE_SECONDS=600` 具名对照成立。
- S3：三处 2048 判定复核确认，`success_rules.py:38` 确用 `errors="replace"`，机制差异属实。
- Spec 轴「issue 原文未核实」缺口：聚合者已用 `gh issue view 76–84 --comments` 取回全部正文与评论，子 agent 所依据裁决摘要与原文一致，缺口消除。
- 修改型文件 hunk 缺口：6 个 src 文件逐 hunk 复核，均与裁决一致——`backup/manifest.py`（a604→a704，#76 B12/#83）；`backup/service.py`（`ScreeningTasks.validate_all()` 语义钩子位于 `_registered_contents` 后、manifest 比对前，`TaskError` 并入受控拒绝，局部 import，#83）；`papers/__init__.py`（`resolve_revision` 延迟导出，#78）；`screening/validation.py`（严格 JSON 预解析：重复键/NaN/Infinity/surrogate 先拒绝、`RecursionError`→`invalid_json`、Mapping 路径不变，#77）；`storage/artifacts.py`+`storage/blob_store.py`（`prepare_publish` 只读预检探针，不登记制品/不建空 shard，对应 47dec58「文件/事务故障」矩阵）。其余 52 个修改型文件（tests/docs/scripts）未逐 hunk 审读。
- pytest 缺口部分收窄：A7 全部 37 模块 + `test_screening_strict_json.py` 共 **538 passed**（291.16s，`uv run --offline --locked`）；全量 `check-offline` 未复跑。
- 未核实（维持）：`verification-runs` 存档 run 只读复核、冻结哈希与工作树字节全量重算、#79 所定「测试不得跨 created_at 与租约时间轴断言先后」的逐例纪律审计、52 个非 src 修改型文件逐 hunk 审读。

## 完成状态与剩余风险

- 两轴均完成，均如实披露工具限制；必需规格来源齐备（#76 + #77–#84 正文与评论经聚合者 gh 取回）。
- 未验证范围（票面即声明未验收，不属本次缺失）：真实模型/RPC/Pi/用量成本、语言事实生产来源（D1 留待 RPC/阶段 D）、完整 eligibility/配额/编排/建议/校准、CLI（D4 推迟）、NAS/live/完整阶段 A；三个 verified 标志保持 false 与票面一致。
- 全量离线门禁本次未复跑；关闭 #76 前建议由可运行方补一次 `./scripts/check-offline` 实际执行（或只读核对 #84 所报 run_id=`005ccfe559af4282b89e4b51250030c7` 存档）及 gh 侧冻结哈希复核。
- 一行小结：**Standards 4 条（0 硬违规，最严重 S1 映射守卫 7 处重复）；Spec 0 条（附 2 条备查，无最严重项）。** 两轴不跨轴排序。


## 外部审查处置追加（保留以上原报告全文）

逐项合理性、接受/拒绝/延期理由及核实证据见 [完整处置表](../../docs/verification/a7-external-review-disposition.md)，涵盖 r1 S1–S4 与两项 Spec 备查、r2 F1–F10/Spec 1–3/G1–G6。历史重绑与运行证据见 [历史索引](../../docs/verification/a7-history-ledger.json)；当前固定范围及逐波路径/理由/绑定组见 [A7 需求台账](../../docs/verification/a7-requirements.md)。最终本轮 run_id 留在外部交接记录，避免写回冻结材料造成自引用。
