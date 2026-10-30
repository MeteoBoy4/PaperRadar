# Issue #120 A 窄收口双轴审查 R2

审查固定点：`main` = `b04c8d5da2fabc0d384bebbfde0d65e845873789`（merge-base 同值）。
审查候选：`HEAD` = `3f41b1adc8b9826d1895ea78e9b3c5cc25778a85`。
差异：`git diff main...HEAD`，72 文件、+6647/−175；提交：`git log main..HEAD --oneline`（14 条，含 #121–#125 与 08d4c26 `fix/120-review-findings`）。
方式：Standards 与 Spec 两轴各由一个全新上下文的子代理独立完成，两个子代理均具备只读 bash 与 read，可访问 GitHub Issue、git 历史、源码与测试；两轴结果分列，不合并、不跨轴重排。本次审查**未修改代码、未创建 commit、未 push、未运行 live**；工作树保持原样（仅存在审查前既有的未跟踪文件 `intent/review/issue-120-main-review-r1.md`，未触碰）。

## Standards

**完成状态**：Standards 轴审阅完成（以实际读取的来源为限），未发现阻断性问题。工具：`read` + 只读 `bash`（`git diff main...HEAD`、`rg`、`--collect-only`、两个 `/tmp` 合成探针）。**未访问来源**：`docs/agents/{llm-evidence,calibration,scope,domain,refactor,issue-tracker}.md`、`docs/contracts/{frozen-contracts,pi-supply,fixture-audit,...}` 全文、ADR-0027–0036 全文；Issue #120 评论裁决原文与永久链接离线不可达，凡涉裁决适用范围一律「未核实」。**未运行**：完整门禁、mypy/ruff、live/Pi/Docling/模型。仓库未改：HEAD 仍为 `3f41b1a`。

四项 r1 修复已核实落地：`Applicability` 共享闭集（`success_models.py:11`、`models.py:129/151/204`、`tests/test_eligibility_review.py:89`）、`_artifact_presence_contradictory`（`rules.py:333`）、系统 accepted 只增请求（`rules.py:166–180`、`intent/review/issue-120-a-narrow-review-r1.md`）、`Concept.READ_PREREQUISITES`（`rules.py:200`）。`scripts/a*_scope.py` 全部登记哈希与当前文件一致（探针遍历 `REQUIRED_*`，drift=0）。

1. **[P3｜文档化硬要求] 长期验证页把原始证据指向仓库外 `/tmp`**
   - 位置：`docs/verification/doctor-readonly.md:26–27`、`docs/verification/a-narrow-delivery.md:73`。
   - 标准：`docs/agents/documentation.md`「证据按次冻结于 `docs/verification/` 和 `verification-runs/`」「票的实施过程、审阅发现留在 issue 评论、PR 与 `intent/review/`，不进入长期文档」。
   - 影响：`handoff-124.md`、scope 重绑报告放在会消失的 `/tmp`，事后不可复核；「隔离副本受控回归／红→绿／6 项通过」属票内过程。
   - 复现：`grep -n "/tmp/paperradar-issue-120" docs/verification/*.md` → 命中上述两行（`intent/review/` 的同类引用属允许位置）；本报告聚合时已复核该命中。
   - 测试核查：不适用；但文中数字可核：`--collect-only` 得 doctor 42、T07 6、`test_eligibility.py` 50，与正文一致。
   - 最小建议：两句改为「开发期检查不构成冻结证据，原始记录见 #124/#125 评论」。成本 2 句；风险低（该两页未被 `scripts/a*_scope.py` 登记哈希）。

2. **[P3｜判断项：文档边界偏离 + 测试缺口] 首个事件创建整条数据根父链**
   - 位置：`src/paper_radar/runtime_logging/files.py:51` `FileSink.emit` 中 `self.root.mkdir(parents=True, exist_ok=True)`。
   - 标准：`docs/contracts/runtime-logging.md`「位置是 `<显式所选根>/logs/`」「构造服务或 `FileSink` 不访问文件系统，首次事件才尝试创建日志目录」。
   - 复现（实际运行 `uv run --offline --locked --no-sync python` 探针）：构造后 `exists=False`（合规）；emit 后根及全部缺失父目录被创建，`logs/` 只是唯一子项。
   - 测试核查：`tests/test_runtime_logging_readonly.py`、`tests/test_runtime_logging_files.py` 均用已存在 `tmp_path`，无「根缺失／只建 `logs/`」用例（`rg "mkdir|exists\(\)"` 已查）。
   - 影响：`--data-root` 拼错时静默建出空制品根。建议只在根存在时 `os.mkdir` 建 `logs/`，或仅建单层；补一条回归。成本 3 行 + 1 测试；风险：新根失去日志（仅降级，契约允许）。

3. **[P3｜判断项：Duplicated Code + 测试缺口] 日志封闭词表是领域 enum 的手抄副本**
   - 位置：`src/paper_radar/runtime_logging/schema.py:27/53/64` 复制 `SourceReason`（`fixture_audit/acquisition_models.py:20`）、`FailureKind`、`TaskReason`（`screening_tasks/errors.py:10`）。
   - 标准：`docs/agents/python-conventions.md:8`「用明确的领域类型和受控 enum / reason 表达状态与原因」；`docs/contracts/runtime-logging.md`「非法已知字段使整条事件拒写」。
   - 复现：探针比对三者，当前 `missing: []`（无现实缺陷）；但新增领域原因会整条丢事件、只 warn 一次（`events.py:85`）。`rg "REASONS|KINDS|CATEGORIES" tests/` 无命中，无同步测试。
   - 最小建议：保持运行期封闭集（勿派生），加一条覆盖性断言测试。成本 1 测试；风险近零。

**合并的低优先级判断项（篇幅所限不展开）**：doctor 九类 label 中英混排（`doctor/cli.py:27` "Feed readiness" 等）与 `cli-output.md`「默认使用中文」/`doctor.md`「中文终端文本」有小偏差；`rules.py:217` 新公共 scope token `explicit_read_prerequisites_no_claim_or_budget` 未登记于 `eligibility-visibility.md:105–108`（`documentation.md`「每项行为的详细规则只在所属 Contract 定义」）；两份新 AST 守卫 `_violations`（`test_eligibility_architecture.py:9`、`test_calibration_visibility_architecture.py:22`）与既有 `test_screening_architecture.py` 扫描器三者同形；`ScreeningTasks.run_once`/`_run_once`（`service.py:174–218`）重复 `callable(executor)` 与 `get_receipt`。

## Spec

**完成状态**：审阅已完成（只读）。已访问：`gh issue view 120/121/122/123/124/125 --comments`（正文+全部评论，D1–D7 裁决与实现者完成报告分开引用）、`git log main..HEAD`、`git diff main...HEAD`（72 文件）、`intent/review/issue-120-a-narrow-review-r1.md`、`intent/draft.md`（§4.6/§6/§8.7/§14/§11 A/§4.10）、ADR-0036/0037、`docs/roadmap.md`、三份新 Contract、`docs/verification/{a-narrow-delivery,doctor-readonly,t07-call-isolation}.md`、`verification-runs/815b2140…{terminal,}.json`、`/tmp/paperradar-issue-120/fixes-scope-final.json`。工具：bash（只读）、read、gh。**缺失来源**：无。**未运行**：`./scripts/check-offline`、live/Pi/模型/Docling/网络；scope 审计未重跑（只读核对保留 JSON）。

**r1 四项独立复核（非转述）**：S1 `Applicability` 已复用 A7 封闭字面量（`eligibility/models.py:9,130,151,204`）；S2 已抽取 `_artifact_presence_contradictory`（`rules.py:333`）；P1 已删除 `MANUAL_DECISION_REQUIRED`（全仓仅存于 review 记录），`_decision` 不再要求人工来源，`manual` 只要求引用当前生效 accepted（`rules.py:176-179`）；P2 新增 `Concept.READ_PREREQUISITES`（`rules.py:200-208`），另有 `test_experiment_single_read_prerequisites_do_not_require_a_request`。实测 `uv run --offline --locked --no-sync pytest tests/test_eligibility.py tests/test_eligibility_review.py tests/test_eligibility_architecture.py tests/test_calibration_visibility*.py` → **144 passed**；`test_doctor_process/readonly/t07` → **48 passed**；`test_runtime_logging_{tasks,files,readonly,entries}+test_a_narrow_composition` → **33 passed**。四项未引入新偏差。

**已核验的硬裁决（无 finding）**：D3 退出码只由基础+选择层决定且固定附「0 不代表任何阶段可运行」（`doctor/cli.py:104,167-169`；`test_doctor_process.py::test_help_and_usage_errors_have_no_io_or_sensitive_echo` 覆盖 `all`/`--json`/冲突/缺快照/`pi-supply --settings` 全为 2）；D4 质量×根用途矩阵字面量断言（`test_eligibility.py:366-404`）；D5=b 已落 §4.6+ADR-0037 且 `TASK_DETAILS` 恒允许、日志不省略 `paper_id/stage`；D2 事件闭集/`propagate` 等价/`capfd`/双进程轮转/符号链接均有用例；D7 Feed/元数据钩子已接（`feed_ingestion/service.py:119,196`、`feed_metadata/service.py:79,143`）；D1=b 登记未动 required/后缀/十四份 JSON，台账 21 个被引测试节点经脚本核对全部存在。B/C/D/H、Pi/Live/Cwd、四刊审计、Docling、正式校准、NAS 均按裁决留待下游，不报为缺失。

---

1. **[P3][implemented-but-wrong（轻微）] 首次事件创建工作区整棵所选根，而非仅 `logs/`。**
   文件：`src/paper_radar/runtime_logging/files.py:51`，`FileSink.emit`。
   裁决引用：`docs/contracts/runtime-logging.md:11`「构造服务或 `FileSink` 不访问文件系统，首次事件才尝试创建**日志目录**」；D2「`logs/` 只在执行路径第一次写事件时创建」。
   影响：`audit run --data-root <拼错路径>` 会静默制造父链目录树（并随即失败），使「显式所选根」的事实变成被创建；不影响业务回执或只读路径（只读路径从不 emit）。
   复现（已运行）：在 `/tmp` 执行 `RuntimeLog(FileSink(Path('/tmp/.../probe/typo/root'))).emit('claimed', component='screening', task_id='a'*64)`，输出 `exists before: False` → `exists after: True`（整条 `probe/typo/root/logs/` 被创建）。
   已有测试核查：`tests/test_runtime_logging_files.py`、`tests/test_runtime_logging_entries.py` 全部以已存在的 `tmp_path` 为根，**未覆盖根不存在**；`test_runtime_logging_readonly.py` 只证明只读路径不建目录。
   最小建议：`FileSink.emit` 只 `os.mkdir("logs")`（`dir_fd` 打开已存在根），根不存在时按写失败降级；或在 Contract 明确「执行入口会创建所选根」。任一即可，不改事件语义。

2. **[P3][scope creep（文档，可选）] GLOSSARY 新增 9 个术语，裁决只要求四类。**
   文件：`GLOSSARY.md`（诊断四态、校准可见性、隐藏条件、专用校准路径、资格判定、资格原因、资格支持范围、正文质量依据、运行日志）。
   裁决引用：#120 实施前复核七.3 与 D1 段落「GLOSSARY 新增四个术语：诊断四态、运行日志/结构化事件、资格判定与资格原因、校准可见性」；#125 验收仅要求「四类术语完整」。
   影响：无行为影响；四类均齐全，其余 5 条为共享规则同簇术语，但属于未被要求的权威面扩张，后续变更需同步维护。
   已有测试核查：未覆盖（纯文档，无断言）。
   复现：`git diff main...HEAD -- GLOSSARY.md`（+36 行，9 个术语块，聚合时已复核）。
   最小建议：不回退即可；若求最小，在 `docs/contracts/eligibility-visibility.md` 注明这 5 条属该 Contract 的术语簇，避免被当作独立权威。

**未核实/限制**：门禁结论仅只读核对 `.terminal.json`（`commit=3f41b1a`、`dirty=false`、`exit_code=0`、`materials_consistent=true`、`worktree/lockfile` 摘要与完成报告一致）与 `fixes-scope-final.json`（`exit_code=0`、`issues=[]`、`affected_groups=[]`），未重跑；未读完全部 781+424 行断言，抽样覆盖 D3/D4/D5/D2 每条。仓库未被修改。

## 汇总

Standards：3 项 finding（1 项文档化硬要求、2 项判断项），轴内最高 P3；Spec：2 项 finding（1 项实现轻微偏差、1 项文档 scope creep），轴内最高 P3。两轴均未发现阻断性问题；两轴均披露了未运行项（完整门禁、live/Pi/Docling）与未核实来源。

## 本轮逐项核实与处置（原审查正文保留）

基线 `3f41b1a`，唯一 implementer 直接编辑 main，无子代理、不 push、不写 Issue。
下表按 implementer guide 的十类覆盖两报告正文及全部“低优先级合并判断项”；
Issue 裁决由协调者独立核验，本轮以本地规格、ADR、源码与公开入口回归落实。
原审阅的来源缺口、历史运行和结论保持原样；本附录不是对旧审阅执行历史的改写。

| 编号／两报告对应项 | 裁定 | 实际落实与证据 |
| --- | --- | --- |
| 1 Main-Spec：跨版本同指纹 current | 采纳 | §8.5/ADR-0031 明确跨版本仍适用；仅删 eligibility/rules.py 的 Screening 版本相等条件。test_same_fingerprint_screening_remains_current_across_versions 通过单篇/批量入口组合当前制品、系统决定、Read 前置、自动与请求；历史/未知、缺版本/引用、交叉制品引用仍拒绝；test_current_pdf_still_requires_the_current_version 保留 PDF 绑定 |
| 2 R2-Standards 2／Spec 1：日志造根 | 采纳 | FileSink 仅打开已有显式根，以目录 fd 建 logs；根缺失按写失败降级。test_missing_selected_root_does_not_create_its_parent_chain 覆盖仅缺根与缺父链，独立进程核对固定中文警告只一次；已有根首次事件正常写。test_missing_log_root_preserves_task_success_and_attempts 核对业务成功字节、回执和一次 attempt |
| 3 Main-S1／R2 合并：doctor 标签 | 采纳 | 标签中文化、D3 固定句原文保留；readiness 是明确用户裁决例外，category/result/reason/scope 及六阶段技术名保持。所选配置、失败路径、只读测试和旧 pi-supply 黄金字节用例通过 |
| 4 Main-S2：公共 Contract 漂移 | 采纳 | feed-ingestion/feed-metadata/feed-pipeline/ScreeningTasks 构造签名补 sink/clock/monotonic；fixture-audit run 正文与 resume 表原位补日志摘要/链接。未来入口仍按原承接边界，不宣称接线 |
| 5 R2-S1：长期页指向临时证据 | 部分采纳 | doctor-readonly/a-narrow-delivery 移除 /tmp 证据指针及票内红绿/计时叙述，保留范围、测试节点与 #124/#125 永久评论。明确开发记录不构成冻结证据，不声称评论保存临时原始字节；未复制旧 /tmp 或迁移 verification-runs |
| 6 R2-S3：封闭白名单重复 | 部分采纳 | 当前无词表漏项；保留独立封闭安全白名单，不由领域 enum 自动派生运行期放行。test_runtime_logging_vocabulary 逐值通过 RuntimeLog/FileSink 验证全部 SourceReason/FailureKind/TaskReason；未来新增领域值若未审查放行会失败。未知值、URL、原始载荷使整条事件拒写 |
| 7 R2 合并：请求 scope 漏文档 | 采纳 | eligibility-visibility 原 scope 段登记 explicit_read_prerequisites_no_claim_or_budget；区分 manual_request 存在事实、请求的 Read 前置、领取和预算，不改返回语义 |
| 8 两报告 AST 重复 | 部分采纳 | 仅两份新增架构守卫提取 pure_dependency_support；保留各自 allowed_imports/type_only_imports 政策与全部原负例；新增可见性在 TYPE_CHECKING 内仍拒绝领域投影的反例。历史 test_screening_architecture.py 未改，无泛化扫描平台 |
| 9 R2 合并：run_once 重复 | 采纳 | wrapper 将已校验的不可变 RequestReceipt 传入私有执行路径，去掉该处重复 callable/get_receipt。load_input 自身的公开边界校验、claim/租约/attempt、领取后 correction 重读和结算不变。无效 executor/receipt 拒绝原因与不占 attempt、不发事件回归，以及原异常/中断/竞争/预算回归通过 |
| 10 R2-Spec 2：九词超过四类 | 拒绝数量上限解释 | 四类齐全不等于最多四词；其余是已实现内存事实的同簇导航，删除会损失领域含义。GLOSSARY 原字节未改，Contract 只链接 Evaluation/Processing 词簇，不重复定义或新增权威 |

合计：6 类采纳、3 类部分采纳、1 类拒绝数量上限解释。重复 finding 通过统一编号合并，
未将报告 r1 已修的四项重新算作本轮缺陷。

### 红绿与职责核实

- Screening 公共回归先出现 1 failed（screening_contradictory）、1 passed；修复后切片 116 passed。
  协调者随后识别空串来源版本原先被错误版本比较间接拒绝，删除比较会放宽该输入安全边界。
  test_empty_screening_origin_version_is_contradictory 先从公共入口复现 eligible=true（1 failed），
  再改为 `not artifact.version_id` 保留缺失／空串的 screening_contradictory 拒绝；
  单篇／批量及系统决定、Read、请求全部受控拒绝，合法跨版本 current 与 PDF 绑定保持。
- 缺失日志根公共回归先 1 failed、1 passed，明确因父链被制造而失败；修复后通过。
  原始缺根探针重跑 data_root_created=false、parent_created=false，固定中文警告受控。
- doctor 标签公共 CLI 回归先 2 failed；修复后 doctor 42 passed，含旧 pi-supply 字节比较。
  主协调者提交后发现本轮曾把 D3 固定句的 readiness 翻译，超出了显示标签修复范围。
  依据 #120 用户最终裁决 issuecomment-6520223100 的 D3（非完成记录）恢复 SUCCESS_NOTICE
  与 doctor Contract 原句；readiness 在此是明确用户裁决例外。强化公共 CLI 测试，使用
  裁决的完整独立字面量核对成功输出最后一行，不从生产常量导预期，覆盖 basic、
  settings/snapshot 及阶段缺项；先 2 failed 再恢复原句。九类标签中文化保持。
  恢复后 doctor 公共子集 42 passed，CLI compatibility 59 passed，Ruff、严格 mypy 和
  只读 scope 均通过；固定句与 doctor Contract 已对照 3f41b1a 原文一致。
- 收紧日志职责后，旧日志序列用例暴露对 logger 提前建业务根的依赖（10 failed、91 passed）。
  仅在完整事件序列用例中显式准备根；根缺失用例独立证明降级、不造根与业务不变。
  业务在自身制品路径需要时仍可建根，根就绪前的事件不缓存、不补写。
- run_once 是等价去重；先运行公开拒绝/原日志与架构回归 49 passed，再改私有参数传递。
  没有用私有调用顺序或 get_receipt 调用次数充当业务断言。
- 日志白名单与 AST 改动属于覆盖补强／等价共享；领域覆盖从领域类型收集测试参数，
  运行期仍独立校验。全部既有负例和不同 TYPE_CHECKING 政策保持。
  独立进程内模拟 SourceReason 新增 future_reason、保持运行期白名单不变，
  该公共覆盖守卫按预期 1 failed（59 deselected），证明新增原因不会被无声遗漏；未改源码。

### 实际验证与 scope

相关 pytest（资格／可见性／日志／组合及 A7 attempt/applicability）300 passed；
doctor 两模块另 42 passed。补齐仅缺根参数后的文件日志模块复验 8 passed。
空串安全补充后的资格、架构与公共组合子集另 133 passed；最终 Ruff、严格 mypy 和
只读 scope 重新核验通过，该补充只动未绑定规则与测试，按协调者指示未重复 compatibility-all。
Ruff lint 全 src/tests/scripts 通过，format 全部 690 文件通过；严格 mypy 全部 689 文件通过。
原始 cross-version 与 missing-root 两探针均通过。以上均为离线合成临时事实，无用户库或外部来源。

scope 先保存只读基线（exit_code=0，无漂移），修改后确认直接漂移仅为
ScreeningTasks service 与 fixture-audit Contract；按既有 DAG 重绑 A7→A8→A9→A10
共 9 个哈希引用。AST 去除 SHA256 字面量后与基线完全相同，required 集合、测试清单和
历史分母未改；最终 `audit-verification-scope --collect --json` exit_code=0、issues=[]、
affected_groups=[]、collection.reason=ok。Frozen Contract、lockfile、旧 verification-runs、
规格和 GLOSSARY 未改。完整运行结果待协调者在本轮提交后另行启动，不借用旧结论。

首次兼容组合在 scope 重绑前启动，出现失败后用 SIGINT 终止（退出 2，未获得完整失败详情），
该次不作为通过证据；重绑后 `./scripts/check-compatibility all` 完整运行，
176 passed，退出 0，入口总耗时 248.51 秒；该组合只做开发期兼容检查，不是完整门禁。
最终 Ruff lint/format、严格 mypy 均通过；两报告原始正文分别以
11617/3996 字节前缀 SHA256 核对完全保留，只在文末追加本轮处置。
暂存两报告后，默认 `git diff --cached --check` 报原 main-review-r1 正文 9 处行尾双空格
（Markdown 换行）；它们已在本轮导入前存在，按“原文字节保留”要求保留。
排除两报告的默认检查通过；仅本次命令以 `core.whitespace=-blank-at-eol` 检查全部暂存内容也通过，
不修改仓库配置或原报告字节。这不是代码新增的空白问题。

原始输出与 scope 旧/新哈希明细留在 `/tmp/paperradar-issue-120-r2/`，仅供开发交接，
本附录记录的结论不以临时路径的永久可用为前提；这不是新增正式冻结验收。

### 未验边界

本阶段未启动完整 check-offline，也未验证 live 来源、Pi/模型/RPC、cwd 隔离、Docling、
正式校准、生产 Read/队列、四刊质量或 NAS；原下游承接与 stage_a_verified=false 保持。
后续门禁 run_id/提交 SHA/终态只放工作树外并由协调者回帖 #120/#125，不回写已提交报告。
