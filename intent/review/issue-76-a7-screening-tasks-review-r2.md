# 阶段 A7 双轴审查 r2（#76 / #77–#84）

- 固定点：`main` = `191c9e11759463bd890ff15b9e77db87624dd8ac`
- 被审：HEAD = `47dec58`（`integration/issue-76-screening-tasks` 尖端）；审阅开始时工作树干净
- diff：`git diff main...HEAD`（三点，对 merge-base）＝ 141 files, +14407/−175；`git log main..HEAD --oneline` 共 19 个提交
- 两轴分别由独立只读子 agent 执行，互不共享上下文；本文按轴分列，未跨轴合并或重排
- 与 r1 的关系：仓库内已存在并发会话产出的未跟踪文件 `intent/review/issue-76-a7-screening-tasks-review-r1.md`（22:26 创建）。本文件独立产出，未读取、未修改、未覆盖该文件

## 工具与来源

- 两轴子 agent：`oracle`（只读验收角色），实际可用 `bash`（仅执行 `git`/`gh`/`grep`/`python`/`pytest` 只读用途）、`read`/`grep`/`find`/`ls`。**无 `edit`/`write`**。
- 规格来源（两轴共用，按 `docs/agents/issue-tracker.md` 方法取回，评论优先于正文）：`gh issue view 76–84 --comments`，即 #76 正文 + 4 条 spec/裁决评论 + 完成报告，#77–#84 正文与评论。
- 标准来源：`AGENTS.md`、`CLAUDE.md`、`docs/agents/{python-conventions,testing,invariants,refactor,documentation,llm-evidence,scope,cli-output,calibration,domain}.md`、`GLOSSARY.md`、`README.md`、`docs/adr/0031`、`docs/contracts/*`、`scripts/a*_scope.py`、`docs/verification/a7-requirements.md`。
- 实跑（Standards 轴，本会话）：`pytest -q tests/test_a7_status.py tests/test_a7_attempts.py tests/test_a7_formats.py` → 24 passed；`pytest -q tests/test_a7_driver_preconditions.py tests/test_a7_attempts.py tests/test_a7_success_applicability.py` → 25 passed；`./scripts/check-offline`（18m05s）→ **exit 1**（唯一原因 `identity_changed`，见聚合核验 G1）。
- 实跑（Spec 轴，本会话）：`pytest -q tests/test_a7_attempts.py tests/test_a7_retry.py tests/test_a7_success_applicability.py tests/test_screening_strict_json.py tests/test_a7_task_query.py` → **139 passed**。
- 未运行：live、RPC、Pi 执行、真实模型用量、NAS、完整阶段 A（与 A7 结论一致）。

## Standards

### 来源与工具

- 固定点 `main`=`191c9e1`，HEAD=`47dec58`；`git diff main...HEAD`＝141 文件 +14407/−175，`git log main..HEAD --oneline` 19 提交。实读：`AGENTS.md`、`docs/agents/*`（python-conventions/testing/invariants/refactor/documentation/llm-evidence/scope/cli-output/domain）、`GLOSSARY.md`、`README.md`、`docs/adr/0031`、`docs/contracts/*`、`scripts/a*_scope.py`、`docs/verification/a7-requirements.md`、`gh issue view 76–84 --comments`。
- 实际可用：bash（只读 git/gh/grep/python）、read/grep/find/ls。实跑：`pytest -q tests/test_a7_status.py tests/test_a7_attempts.py tests/test_a7_formats.py`→24 passed；`pytest -q tests/test_a7_driver_preconditions.py tests/test_a7_attempts.py tests/test_a7_success_applicability.py`→25 passed；`./scripts/check-offline`（18m05s）→ exit 1。
- 缺失来源：无。**本轴完成**；未验证范围：live/RPC/Pi/NAS 全部未运行（与 A7 结论一致）。

### 发现

**F1｜文档化硬要求（门禁终态）—— `verification-status` 与 HEAD 不一致**
`./scripts/verification-status 005ccfe…` → `applicability=different`；该证据 `code.commit=60cc945`，而 HEAD=`47dec58`，其后 4 个提交（`72f9938`、`9ae6819`、`fddad9f`、`47dec58`）改动 `screening_tasks/*`、`storage/{artifacts,blob_store}.py` 并重绑 A3/A4/A5/A6 哈希，无任何通过门禁记录。`docs/verification/a7-requirements.md:353-355` 要求"最终提交…applicability=same"。
我实跑 HEAD：6 项检查（lockfile/format/lint/types/tests/contracts）全 passed；pytest 回执 212 模块 **3615/3615 passed**，A7 子集 38 模块 **538/538**；但 A1 结论捕获 `dirty=true`、`worktree_sha256=8e2444…`，终态为 `19af0e…`，故 exit=1，唯一原因 `identity_changed`。原因是我运行期间工作树出现**并发会话写入的未跟踪文件** `intent/review/issue-76-a7-screening-tasks-review-r1.md`（22:26:36 创建，运行起于约 22:11）。→ 结论：**代码无失败**，identity 守卫行为正确；但"可信终态"仍只覆盖 `60cc945`。最小建议：在与 HEAD 一致的静止工作树上重跑并存档 run_id（成本 1 次 18 分钟门禁，风险低）。
（**聚合核验 G1 部分推翻**：HEAD 确有一条通过记录，见下。）

**F2｜文档化硬要求（数字漂移）**
`docs/verification/a7-requirements.md:319-321`「283 例 + 93 = 376，+153 = 529」；`scripts/a7_scope.py` 实际登记 38 模块 **538** 例（`47dec58` 把 `test_a7_driver_preconditions` 7→9，同文 `:362` 只改了分项未改总数）。实测回执 538 与 scope 一致。最小建议：529→538、283→285。成本极低；现有测试 `tests/test_a7_integrity.py:72-81` 只校验 scope 与回执一致，不覆盖文档数字。
（**聚合核验 G2 确认并加强**：漂移起于 `72f9938`，非仅 `47dec58`。）

**F3｜判断（Duplicated Code，源）—— `service.py` 5 处手写连接样板**
`service.py:165-221、229-241、244-268、272-290、296-320` 各自 `open_database → require_current_revision → exec_driver_sql("BEGIN…") → … → finally engine.dispose()`；`execution.py:58-70` 已有等价 `AttemptService.connection()`。建议复用（异常映射差异安全：`connection()` 不捕获 `PaperError`，`register` 的透传语义不变）。成本：`service.py` 在 `a7_scope` 哈希内，须重绑 1 个哈希并重跑门禁。

**F4｜判断（Duplicated Code）—— 阶段映射前导 7 处同形**
`PaperFacts(...).map_screening_inputs(...)` + `mapped = mapping.boundary if … else mapping.value` + `mapped.reason/None` 检查：`service.py:173-181`、`execution.py:80-88`、`retry.py:40-48`、`query.py:45-53`、`success.py:282-290`、`integrity.py:47-52`、`attempt_integrity.py:82-87`。建议抽 `map_stage(mapping, stage)`。成本：6 个绑定模块重绑 + 重跑。

**F5｜判断（Primitive Obsession + Repeated Switches）**
`{"boundary","value"}` 字面集合 4 处（`success.py:113,279`、`query.py:36`、`success_integrity.py:47`），而 `models.py:12` 已有 `Stage = Literal[…]`；公开入口仍用 `stage: str`（`service.py:70,104`、`query.py:33`、`success.py:277`）。建议内部统一 `Stage`，仅在公共边界用一次 isinstance 校验。

**F6｜判断（魔法数）** 尝试预算 `2` 硬编码 8 处：`attempt_rules.py:72,77,79,87`、`execution.py:117`、`retry.py:106`、`attempt_integrity.py:121`、`integrity.py:100`；同包已有具名 `LEASE_SECONDS`。建议 `MAX_ATTEMPTS_PER_TASK = 2`。

**F7｜判断（Duplicated Code）** 可重试失败集合重复：`execution.py:217-222` `allowed={…}` 与 `service.py:150-156` 同一 4 元集合；`run_once` 的三重类型/成员校验与 `fail()` 内校验重复。建议共享常量 + 单一校验。

**F8｜判断（成本高，不建议本次改）** `a6_acceptance.py`(503) 与 `a7_acceptance.py`(533) 结构相似度 0.922（difflib），`_reason`/`_HELP`/12 个 reason code 逐组复制；修复会连锁重绑 4 个 scope 脚本并全组重跑，建议记入后续通用化议题。

**F9｜测试缺口（机械问题）** 缺架构守卫：`tests/test_screening_architecture.py` 只守 `screening`/`contracts` 包，`tests/test_a7_registration_imports.py` 只证明 `papers` 公共导入零 I/O；spec §五/S4 要求的"任务包不导入 `pi_supply`/`httpx`/LLM、不直接读时钟"无回归保护。静态核对当前为真（grep 无命中，`utc_now` 集中注入）。建议补 1 个 AST 用例。
（**聚合核验 G3 推翻**：该守卫已存在。）

**F10｜轻微（不新增模式）** `tests/test_a7_driver_preconditions.py:166-172` 用 `chmod(0o500)` 造只读目录；以 root 运行时断言会假通过。既有先例 `tests/test_artifact_store.py:137` 同形态，仅提示。另：`blob_store.py:82,91` 的 `_path("…/pending").parent` 借虚构名取父目录属既有写法（`:172` 早已如此），不重复计。

### 已排除（有文档/先例许可）
`success.py` 在业务写事务外发布制品（ADR-0031 明确"竞争失败允许完整未引用响应"）；A3 绑定文件的哈希重绑（spec §六列为不可避免）；负例断言质量合格（`tests/test_a7_*.py` 47 处 `TaskError` 均以 `as error` + `reason` 断言，无仅凭异常类型的用例）；术语/ADR/Contract/README 同步齐备（`GLOSSARY.md:398-433` 新增 7 条、`模型失败队列` 改写）。

## Spec

### 可用工具与来源
只读 `git`/`gh`/`grep`/`uv run --offline --locked pytest`。已读取 #76 正文 + 4 条评论（实施前补充说明、D1–D4 裁决、评论之二、评论之三）+ 末条完成报告，及 #77–#84 正文与评论、`docs/contracts/screening-tasks.md`、`a7-requirements.md`、ADR-0031、`intent/draft.md` §8.5、GLOSSARY 与各 Contract 增量。审阅完成，未发现需要新裁决的真实矛盾。

### 逐条裁决核对（全部落实，无功能偏差）

- **D1(a)**：`ValueRequest.original_title_is_zh: object` 交由 `value_prediction_context` 判严格 bool（`models.py:38`、`service.py:187-194`）；boundary `extra="forbid"` 拒绝（`tests/test_a7_registration.py:59` 断言 `None/0/1/"false"` 均 `INVALID_CONTEXT`、boundary 传 `False` 亦 `INVALID_REQUEST`）；`tables.py:56-59` CHECK 冻结「boundary NULL / value 0|1」；相反值 `CONTEXT_CONFLICT` 且不新增任务；retry 继承见 `test_a7_retry.py:67/138`；Contract §2 明写「误标无法纠正」，`a7_scope.py:39` 列 `original_title_language_production_source`。
- **D2(a)**：无「结果使用依据」表/再绑定 API；`tables.py` 中 `requests.cached_success_id` 仅为命中回执，`query.py:120-131` 三值完全派生；`intent/draft.md:1384-1394` 与 ADR-0031 已改写；`test_success_applicability.py` 覆盖 parser 删摘要→undeterminable→另一来源补回→current、文本变化→historical、未知 snapshot→undeterminable、同文本新版本/无关配置→current。
- **D3(a)**：`validation.py:150-171` 单一权威严格预解析，`_unique_json_object` 任意层重复键、`parse_constant` 拒 NaN/Infinity、`except (ValueError, RecursionError)` 折叠为根 `$` `invalid_json` 且先于字段错误；`validate_screening_reason` 同经 `_validate_model`（`:434`）；`screening-validation.md:120-134` 记录受控类别迁移；新模块 `test_screening_strict_json.py`（93 例）为唯一新增，未动 A1/A2 绑定模块与冻结 Schema。
- **D4**：`git diff --name-only | grep cli.py` 为 0；Contract §6 与 `NOT_ASSESSED` 含 `screening_cli`/`paper_trace_cli`。
- **B1/B2/B4/B5/B7/B8/B11**：`rules.py:76-95` scheduled 回执含 version/revision/snapshot；`execution.py:74-140` 领取前映射校验 + 事务内 `resolve_revision` CAS；`attempt_rules.py:34-38/66-83` 600 秒、`now+D`、半开区间、`lease_expired` 且 `remaining=0`；失败封闭表 `tables.py:188-193` 与 Contract §3 表格一致；审计事实可空且区分 0/未知（`test_a7_boundary_success.py:134-144`）。
- **B12/决策 23**：`backup/service.py:179-183` 钩子在 PaperFacts 后、manifest 反查前同 try 映射 `registration_invalid`；`manifest.py:27` head 前移、format 1 不变；跨备份预算限制写入 Contract §7。
- **S1–S4**：八张原生票；续租只更新 `leases.expires_at`；`test_a7_registration_migrations.py:155-186` 以 AST 守卫替代「不同 cwd」用例，覆盖 pi_supply/httpx/LLM 与 `now/utcnow/getenv/getcwd`。
- **A7-08**：`a2_full_acceptance.py:429-437` A7 必需且前置恰为同次 A1/完整 A2/A3/A5/A6，A4 仍整体必需；`verification_status.py:76` 同提交加 `.a7.json`；`check-offline` 文案改九份/十一份；旧 scope 仅 `MIGRATION_REVISION` 与哈希位移，无分母下调（`git diff scripts/*_scope.py` 逐行核对）。
- **测试矩阵 26 行**：逐行找到对应用例（含 `*_process.py` 真实子进程/强杀、`*_backup.py` 语义损坏重哈希拒绝、`test_a7_task_query.py:60-66` 隐私串断言）。矩阵「配置语义改变不命中」由 `test_a7_value_context.py:30-79` 以「当前 screening 模型变更→historical」覆盖。
- 我实际运行：`uv run --offline --locked pytest -q tests/test_a7_attempts.py tests/test_a7_retry.py tests/test_a7_success_applicability.py tests/test_screening_strict_json.py tests/test_a7_task_query.py` → **139 passed in 16.43s**。`./scripts/check-offline` **未运行**；`verification-status 6e818ba3…` 读得 passed/verified/**same**、3615/3615、A7 独立回归在列（引用既有记录，非本次执行）；`005ccfe…` 为 `different`，已被最终结论取代。

### 发现（无功能错误类）

1. **[文档化硬要求｜台账缺口｜低]** `scripts/a3_scope.py:44-49` 已把 `storage/artifacts.py`、`storage/blob_store.py` 的哈希重绑到当前字节（我核对的 sha256 与 scope 登记一致），但 `docs/verification/a7-requirements.md` 全文 grep `blob_store`／`artifacts.py` 命中 0，「最终审查修复」（`:360-370`）只有散文，没有前几波那种「接入文件｜本波重审理由｜旧组」行。需求：决策 24「旧组受集成改动影响的绑定必须逐项重审并留理由」。已有测试核查不适用（文档台账）。限制：外部 `84-rebinding-ledger.json` 可能已记录，但 `#76` 末条评论称临时工作树已清理，我**未核实**。最小建议：在该节补一行 A3 重绑定表项，成本约 1 行文档。
2. **[可选可维护性｜判断题｜低]** 同一修复新增的 `BlobStore.prepare_publish()`（`blob_store.py:79-112`）在每次 `run_once` 领取前遍历 256 个「已存在」shard，各建临时目录 + `os.link` + 两次目录 fsync；真实档案库 shard 全存在时是每任务固定的数百次 fsync，且把 A7 的领取前预检加进 A3 共用热路径。功能上满足「领取前拒绝发布路径错误、不扣次数」（`test_a7_driver_preconditions.py:140` 等 9 例）。最小建议：改为探测顶层 `tmp/`、`blobs/sha256/` 命名空间或进程内缓存结果；风险低。
3. **[审计可复现性｜判断题｜低]** 该文档的逐条旧/新 SHA-256、最终 run_id 与十一份原 JSON 均保存在工作树外（`:204`、`:352-356`），仓库内只能核对汇总；这是为避开自引用哈希的有意取舍，但使「逐项留理由」在仓库内不可复核。最小建议：把最终 run_id 与绑定哈希清单以不被哈希绑定的附录文件（如 `verification-runs/` 索引）纳入，或明确声明仅依赖本地证据。

### 未验证范围
未运行完整 `check-offline`；未运行 live/RPC/模型/NAS；外部 rebinding ledger 与 #76 交接产物未核实；测试通过不证明真实模型端预算、资格或阶段 A 语义。

## 聚合核验（不改变轴内排序）

聚合者（本会话，有 bash）对上述发现做了独立复核，只指出**证据层面的推翻/加强**，不改两轴分列与排序：

- **G1（部分推翻 F1）**：HEAD=`47dec58` **确有一条通过记录**：`./scripts/verification-status 6e818ba30d6a4b7a83ae78cac9007bbf` → `passed / verified / same`、exit 0、3615/3615、耗时 1059 秒；`verification-runs/6e818ba3….json` 内 `code.commit=47dec5870d63bef9c6754f973211b9660b335b3c`、`code.dirty=false`、`finished_at=2026-10-23T13:17:59Z`，且 `.a7.json` 的 `a7_verified=true`、capabilities 全 `passed`。因此「HEAD 无任何通过门禁记录」不成立；`005ccfe…`（`60cc945`）的 `different` 是被这条更晚记录取代的旧证据。F1 中仍然成立的部分：Standards 轴本次实跑的 `check-offline` 因并发会话产生的**未跟踪文件** `intent/review/issue-76-a7-screening-tasks-review-r1.md`（22:26:36 创建）被判 `identity_changed` 而 exit 1——这是 identity 守卫的正确行为，**不是代码失败**（其余 6 项检查全 passed、3615/3615 通过）。剩余风险：`same` 记录与本次审阅的 HEAD 相同，但审阅后的工作树若再变动需重跑。
- **G2（确认并加强 F2）**：逐提交核对 scope 登记例数与文档声明：`60cc945` = 529/文档 529（一致）→ `72f9938` = 535 → `9ae6819` = 535 → `fddad9f` = 536 → `47dec58` = 538，而文档始终写「A7 合计固定 529 例」。即漂移起于 **`72f9938`**（未挂子票的 integration 收尾提交），`47dec58` 只是又加 2 例；业务小计 283 现应为 292（538 − 93 严格 JSON − 153 协议验收）。属文档化硬要求。
- **G3（推翻 F9）**：架构守卫**已存在**于 `tests/test_a7_registration_migrations.py:155-186` 的 `test_task_dependencies_and_pure_rules_do_not_acquire_execution_authority`：正向断言 `config`/`screening`/`stage_inputs`/`papers` 不导入 `paper_radar.screening_tasks`；反向断言 `screening_tasks/*` 不导入 `paper_radar.pi_supply`/`httpx`/`requests`/`docling`/`paper_radar.llm`，并以 AST 拒绝 `now`/`utcnow`/`time`/`getcwd`/`getenv` 调用，另加 `rules`/`errors` 不导入 SQLAlchemy/storage。该用例也在 `a7_scope.py:61` 固定（6 例）内。故「无回归保护」不成立；仅可讨论它放在了 migrations 模块这一命名位置是否直观（判断题，非缺口）。
- **G4（确认 Spec 1）**：`git show 47dec58 --stat` 含 `storage/blob_store.py`（A3 绑定）与 `scripts/a3_scope.py`（哈希 `7f6f3f67…`→`3664854101…`），而 `docs/verification/a7-requirements.md` 在该提交只改 2 行（7→9 例）。`9ae6819` 改了 `screening_tasks/*` 却**完全未改** `a7-requirements.md`。故 A7-06/07/08 与 integration 收尾波次确实缺「接入文件｜本波重审理由｜旧组」行（A7-02..05 均有）。
- **G5（确认 Spec 2 成本前提）**：`prepare_publish()` 的调用点确为 `screening_tasks/service.py:129`（`run_once` 内、`claim` 之前），循环 `product("0123456789abcdef", repeat=2)` 覆盖 256 shard，`_probe_link_directory` 内含两次 `sync_directory`；`storage/artifacts.py:49-51` 只做转手委托。
- **G6（确认 Spec 3）**：`docs/verification/a7-requirements.md` 最新节确实声明逐条哈希与 run_id 存于工作树外 `84-rebinding-ledger.json`；仓库内无该文件。

## 汇总

- **Standards 轴**：10 条发现（1 条文档化硬要求经 G2 确认、1 条 F1 被 G1 部分推翻、1 条 F9 被 G3 推翻、7 条判断题/轻微）。轴内最严重：**F2 文档分母漂移**（529 vs 实际 538，起于 `72f9938`）。
- **Spec 轴**：3 条发现，无功能错误；D1(a)/D2(a)/D3(a)/D4 与 B1–B12、S1–S4、A7-08 全部逐项核对落实。轴内最严重：**发现 1 重绑台账缺口**（A7-06/07/08 波次缺「接入文件｜理由｜旧组」行，G4 已确认）。
- **完成状态**：两轴均完成；来源齐备，无缺失来源。未验证范围：live/RPC/Pi/真实模型用量/NAS/完整阶段 A；工作树外台账（`84-rebinding-ledger.json`）未核实；Standards 轴自身那次 `check-offline` 的 exit 1 为并发未跟踪文件导致的 identity 判定，不代表代码失败。


## 外部审查处置追加（保留以上原报告全文）

逐项合理性、接受/拒绝/延期理由及核实证据见 [完整处置表](../../docs/verification/a7-external-review-disposition.md)，涵盖 r1 S1–S4 与两项 Spec 备查、r2 F1–F10/Spec 1–3/G1–G6。历史重绑与运行证据见 [历史索引](../../docs/verification/a7-history-ledger.json)；当前固定范围及逐波路径/理由/绑定组见 [A7 需求台账](../../docs/verification/a7-requirements.md)。最终本轮 run_id 留在外部交接记录，避免写回冻结材料造成自引用。
