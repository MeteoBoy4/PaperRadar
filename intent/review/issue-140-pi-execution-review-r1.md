# Issue #140 Pi 执行集成双轴审查（r1）

- 固定点：`main`（`e0f8e39d1aff8b57eadfe60de44b8570423c1d40`）
- 审查命令：`git diff main...HEAD`
- 审查提交：`git log main..HEAD --oneline` 共 17 个提交，自 `b271186` 至 `db30cf5`
- 规格来源：GitHub Issues `#140`、`#141`、`#142`、`#143`、`#144` 的正文与全部评论；评论优先于正文
- 审查方式：两个 fresh-context subagent 并行只读审查，均具备 `read`、`bash` 权限；未修改代码、未创建 commit、未运行测试或完整离线门禁

## Standards

1. **Hard violation｜文档信息归属**：`docs/verification/issue-140-pi-delivery.md:125-145` 写入“双轴审阅修复”“修前失败”“随后修”等实施与审阅史；`issue-142-pi-rpc-source.md:27-28` 同类。违反 `docs/agents/documentation.md:60-63`：“票的实施过程、审阅发现……不进入长期文档。”影响：冻结证据与过程叙述混杂。最小修复：将这些叙述移至 issue/PR/`intent/review/`，台账仅保留按次证据与覆盖事实。

2. **Hard violation｜ADR 正文边界**：`docs/adr/0039-isolate-pi-with-landlock.md:25`：“后续真实标准库子进程覆盖文件和端口边界。”违反 `docs/agents/documentation.md:41`：“正文不写实现进度与排期。”影响：已接受决策混入后续验证计划。最小修复：删除该进度表述，保留代价及“不证明”边界，验证责任交路线图或台账。

3. **Judgement call｜Duplicated Code**：`src/paper_radar/screening_tasks/success.py:111-119,159-167,279-288,329-337` 与 `success_integrity.py:107-115` 重复同一段 `execution_audit` 引用核验。影响：审计规则变化需多点同步，易漏改。最小修复：提取一个小 helper 复用；保留提交时两个事务各自核验的语义。

验证：未运行测试，仅只读审查。

## Spec

发现 **1 项确定问题**：

- **[implemented-but-wrong] 审计字段不符合指定格式。** `#140` A2 明确要求：“启动策略版本、隔离策略版本、**`channel=prompt_only`**”；`#142` 验收亦要求“prompt_only 通道”。实际 `src/paper_radar/screening_tasks/pi_rpc_audit.py:33` 定义为 `protocol`，`src/paper_radar/pi_execution/service.py:206` 同样写入 `protocol`，导致格式 2 审计缺少规定的 `channel` 字段，下游按 spec 解析时无法取得必填通道。**测试：**`tests/test_pi_rpc_source.py::test_pi_rpc_boundary_survives_task_service_restart` 只验证实现自洽；`tests/test_pi_rpc_source_backup.py::test_persisted_audit_corruption_rejected_by_load_validate_and_backup` 还固化了 `protocol` 字段，未覆盖 `channel`。**最小修复：**统一将 Schema、构造、夹具及 Contract 中的该字段改为 `channel`，保留现有闭集校验。

未发现确定的 scope creep；明确交由 Cwd/Live 的事项未计为缺陷。测试：**未运行**（静态只读审查）。

---

**汇总：Standards 3 项，最严重为长期证据文档混入实施与审阅过程；Spec 1 项，最严重为格式 2 持久审计使用 `protocol` 而缺少规格要求的 `channel=prompt_only` 字段。**

---

## 外部审阅后逐项处置（#140）

本节为同一 fresh implementer 的增量；上方原报告保留原文。
判断依据为当前实现、#140/#142 正文及所有者评论、仓库冻结规则，未假定每项建议都正确。

### Standards 1：采纳信息归属判断，采用新的当前摘要

原 Pi 台账所指“双轴审阅修复”“修前失败”“随后修”等确属过程叙述；
#142 台账的两句 red→green 描述也属同类。表内覆盖、按次命令/数量/结果、
旧分母与未验证边界则是合法证据，不宜整文件迁移。
两份台账已经按次冻结，`documentation.md` 同时要求“证据按次冻结”，
因此不静默改写旧证据正文或历史 JSON。此次保留两份原台账所有字节，
新建 `docs/verification/issue-140-external-review-followup.md` 作为当前覆盖摘要，
路线图的 Pi 证据入口指向新摘要；本轮审阅及修正过程只记录在两份 review 报告中。
历史格式/195/44 与当前 format3、独立新增分母明确分开，不追溯扩大旧结论。

验证：冻结字节核对及文档链接/归属审查；当前开发验证结果见本节末尾。

### Standards 2：采纳归属问题，拒绝删除已接受 ADR 正文的建议

“后续真实标准库子进程覆盖…”混有接受时的验证过程上下文。
直接删除虽是原报告的最小建议，却违反 `docs/agents/documentation.md`：
“接受后正文冻结，只允许改状态行与错别字。”
本次没有新的隔离决策，不为删除一句话制造新 ADR。
只修改 ADR-0039 状态行，指向新的当前覆盖摘要与现场责任；正文保留原字节。
当前摘要明确工程观测不代表 Cwd/Live 实际能力，避免把历史措辞解释成现行排期。

验证：ADR 正文与修前逐字节相同，diff 仅状态行；当前现场证明限制保持。

### Standards 3：采纳，共享可空审计的引用核验

把 `execution_audit is None` 的判断收进既有唯一
`validate_execution_reference`，提交、回查、查询和恢复闭包统一调用。
提交前只读事务和发布后写事务仍分别核验同一个候选，未挪到单次事务外校验；
test 无执行审计仍不读取供给引用，pi_rpc 仍核对本 attempt 的回执审计 snapshot。
没有增加第二套字段表或放宽持久恢复校验。

验证：pi_rpc 伪造引用/幂等冲突/首次语义与本次审计差异、旧 test 成功、
失败完整性及备份/Read 冷恢复回归。

### Spec 1：采纳，严格新格式与历史格式分开

新执行审计 `PiRpcExecutionAudit` 和执行服务构造改为 `channel=prompt_only`；
新持久 `PiRpcAudit` 使用 format3/channel。
`CallDescription.protocol` 是 RPC 调用描述中的既有协议字段，继续保留。
历史 format2/protocol 由独立 `LegacyPiRpcAudit` 严格读取；不把 format2
原地改字段、不接受别名、猜版本或 channel/protocol 混用，不重写旧审计与摘要。
内存候选参数不是已存数据库格式，不为其保留歧义命名。
旧 test 审计编码与身份保持，无 migration。

先通过公共任务接收回归获得修前 `format_version == 3` 的真实失败，再修改实现；当前执行审计对象缺 channel 的断言也独立得到修前失败后修正。
新增独立字面量历史 format2 fixture，仅替换本次真实登记的 supply/install 标识，
通过公开 load/query/validate_all/create_backup/restore 回放；恢复后的原审计字节和
submission_digest 与历史输入一致。另覆盖 format2 中仅 channel、双字段、
伪装 format3、缺 protocol、浮点版本的受控拒绝。
现有未绑定新写测试仅更新 format2→3、未知3→4，节点数量与旧历史冻结测试保持。

验证：新写 channel 与无 protocol 断言、字面量旧审计查询/恢复和严格混版拒绝，
以及原 pi_rpc 接收/备份/执行来源组合；结果见下方。

### 本轮验证与限制

- 全部最终相关42模块组合：**518 passed**，229.54秒；1条既有 SQLAlchemy 循环外键 metadata 排序警告。全部60个新增D1节点与原配置/任务/回执/恢复/范围守卫均通过。
- 最终受影响来源组合：**161 passed**，108.60秒；含新/旧审计接收、查询、备份、执行、Feed、doctor与历史冷导入。
- 安全诊断及原离线入口/终端字节组合：**33 passed**，21.65秒；包含13个新诊断节点。
- `./scripts/check-compatibility all`：**176 passed**，pytest 272.11秒，入口总耗时272.74秒，退出0。
- 全仓 `Ruff check`、`Ruff format --check`、`mypy` 全部通过（格式748文件、mypy747文件）；`git diff --check` 通过。
- 显式 main 基线候选 scope 审计退出0、无 hash/baseline 漂移；5条敏感路径逐下游20项确认，289条原计数记录保持，collection 为285模块/5281节点。最终提交身份重新审阅确认留树外。
- 全量仅 collection：352模块/6385节点；未绑定67模块/1104节点。本轮D1为47+13=60，旧Pi195和历史required不扩张。

最终完整离线门禁尚未运行：提交冻结后，同次 `./scripts/check-offline` 退出0且
状态 `passed/verified/same` 才满足最终判据；run_id 与执行记录只留树外。
未运行 live、真实 Pi/Node/auth/模型、现场 cwd、TLS/DNS 或主机出站；
产品证据仍缺失，保持领取前阻断；旧证据不代表当前树通过。


## 完整门禁反馈的后续处置（#140/#144）

本节追加在前轮报告之后；前轮结论、旧台账及所有正式JSON/安全sidecar保持原字节。
完整门禁实际非零，即使固定285模块/5281节点全过，也不能据此认定整套通过。
新增安全定位指向 `tests/test_extensible_acceptance.py (call)`。

诊断遵循原公开回归：模块实际21 passed/1 failed，紧缩到
`test_synthetic_history_keeps_material_and_format_boundaries[broken_registry]`，
未修改时3.11秒稳定失败。失败副本的受控stderr证实：
verification_status→offline_evidence的顶层诊断导入→pytest_failure_diagnostics→
当前verification_groups；测试故意破坏当前登记后引发SyntaxError和空stdout。
新支持文件实际存在，原模块其余历史材料/未知格式用例通过，排除支持复制闭包遗漏。

真实修复仅将诊断读取导入移至tests实际失败分支，恢复历史状态和文件哈希入口
对当前登记的独立性。保留原broken_registry、缺失材料、未知格式、只读和扩展正例断言；
没有修改测试、放宽白名单或新造镜像测试。唯一源码哈希按实际变化精确重绑；
未重绑时现有范围守卫正确拒绝漂移，登记一致后原红节点3.12秒通过。
当前详细规则只在辅助诊断Contract维护，本轮覆盖另记新台账，不改前轮60或旧195。

- 原broken_registry节点：1 passed，3.12秒；保留原断言与只读材料检查。
- 原扩展模块/安全诊断/历史状态/离线入口组合：81 passed，113.16秒。
- 真实全量collection与receipt_modules的完整差集：67模块、1104节点显式执行，**1104 passed，520.81秒，退出0**；无skip/deselect，没有仅复验当前单模块或前轮518项组合。
- `check-compatibility all`：176 passed，pytest279.92秒，入口280.52秒，退出0。
- 全仓Ruff check、format check、mypy全通过（格式748文件、mypy747文件），git diff --check通过。
- 显式main基线候选审计无hash/baseline漂移；最终HEAD/树身份的逐组确认和固定collection单独留树外，289条原计数与41refs保持。

最终完整门禁仍待新提交冻结及根代理核实后执行；不会自行重跑或改写旧失败证据。
