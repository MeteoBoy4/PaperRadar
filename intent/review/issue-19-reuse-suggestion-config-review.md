# Issue #19 复用升级与建议规则版本化配置审查（Standards / Spec 双轴）

- 固定点：`HEAD^`（= 81e942b）
- 范围验证：`git log HEAD^..HEAD --oneline` 恰为一笔目标提交：
  - `6f7e434 Implement versioned reuse and suggestion configuration (#19)`
- Diff 命令：`git diff HEAD^...HEAD`（24 文件，+2141/-48）
- 规格来源：GitHub Issue #19「A2-04：编译复用升级与建议规则的版本化配置」正文 + 全部 comments（1 条两点厘清）；规范引用 `intent/draft.md` §3.5/§3.7/§4.5/§7.4、ADR-0022、ADR-0023、父 spec #15 及其补充
- 标准来源：`AGENTS.md`、`CONTEXT.md`、`docs/adr/`、`docs/agents/domain.md`、`docs/contracts/` + Fowler smell 基线
- 审查方式：Standards 与 Spec 两个独立子代理并行，仅聚合不混合排序；审查过程只读，未修改代码、未建 commit、未触碰 GitHub Issue
- 审查期实际运行的验证：完整离线套件 `uv run --offline pytest tests` → 600 passed；`python -m scripts.a2_scope` 与 `scripts.a2_acceptance` → exit 0；`examples/contracts/` 两份新契约与权威 `contracts/screening/` 字节一致

## Standards

**成文标准（AGENTS.md 及仓库文档）：未发现硬性违规。** 逐项正面核实：

- Frozen Contract 从权威 Pydantic Schema 生成：`examples/contracts/screening/{reuse-assessment,decision-reasons}/v1/*` 与权威 `contracts/screening/` 字节一致，manifest `schema_sha256` 与实际字节匹配。
- 文档同步义务：README、`docs/contracts/runtime-config.md`、`intent/draft.md`、`docs/verification/offline-evidence.md` 与代码行为一致（readiness 表、缺项原因词表、NOT_IMPLEMENTED 清单均与 `src/paper_radar/config/compile.py:266-290`、`scripts/a2_scope.py:127-136` 对齐）。
- `scripts/a2_scope.py` 中哈希与真实文件字节一致（六个变更/新增模块抽验通过）。
- 中文 CLI help、错误脱敏（测试断言不回显 secret/prompt）、重编译幂等、纯逻辑与 I/O 分离（`escalation.py` 有依赖向测试）、ADR-0022 的 availability 优先顺序均成立；文档如实声明 A2 无法检测同算法版本下的代码语义变化，符合 ADR-0023 审计意图。

**Smell 基线 / 约定层面（均为 judgement call）：**

1. **Duplicated Code** — `src/paper_radar/config/escalation.py:63-76`：`supported_selector` 与 `supported_rule` 是同一 4 行校验器写两遍（`schema.py:58-65` 的 `valid_protocol` 已是第三处同形）。影响：错误措辞变化需改三处。最小修复：抽一个 `controlled_enum(enum, message)` 校验器工厂；可接受延后。
2. **约定不一致** — `tests/test_config_escalation.py:191`、`tests/test_config_reuse.py:157` 使用函数级 `from paper_radar...` 导入；其余测试模块均顶部导入。`cli.py`/`__init__.py` 的函数级导入是为保证 `--help` 无 I/O，该理由不适用于测试。最小修复：提升到模块顶部。
3. **无关改动**（AGENTS.md 完成标准「未无必要修改无关行为或文件」）— `intent/draft.md` 约 628-634、965-978 行对 `EvidenceRef`/`BoundaryOutput` 代码块的纯空行格式化与本票无关。无害，理想情况下应单独提交。
4. **范围钉扎缺口** — `tests/config_reuse_support.py` 是新增测试支撑工厂模块，但未钉入 `scripts/a2_scope.py`；而 `docs/verification/offline-evidence.md` 保留了 A2-03 先例「登记新增测试支撑模块的哈希」（`config_test_support.py` 因此钉扎）。二者择一：钉入或调整该先例句。判断性意见——新增可变测试已由完整 `tests` 运行覆盖。
5. **Divergent Change（轻微）** — `tests/test_config_escalation.py` 兼测 `identity.canonical_json` 的列表保序（`test_ordered_fixture_hash_keeps_list_order`），该职责属 identity 模块；`runtime-config.md` 已记录此理由，可接受现状。

其余 smell（Feature Envy、Data Clumps、Speculative Generality 等）均未发现；`EscalationSemantics` 与 `Escalation` 的并列是刻意的 raw-vs-semantics 分层，已有文档说明。

## Spec

**(a) 遗漏或部分实现：未发现。** 全部验收标准均已追溯到代码与测试：

- reuse 模型槽/提示词/两份冻结契约复用同一只读检查与原子登记：`src/paper_radar/config/service.py:50-56,102-143,194-202`；相同初始两槽独立修改/查询：`tests/test_config_reuse.py:123-153`。
- 集合语义（非阈值）、默认 `{3}`、严格 1–5、非空、重复拒绝：`src/paper_radar/config/escalation.py:34-36,46-51`；布尔/越界/重复/别名拒绝并有 CLI 覆盖：`tests/test_config_escalation.py:56-138`、`tests/test_config_reuse_cli.py:67-108`。
- 同版本改字节失败、`[2,3]`/`[3,2]` 身份不同但语义相同、测试预期集合为硬编码（不用生产归一化函数）：`tests/test_config_reuse_persistence.py:25-58`、`tests/test_config_escalation.py:154-187`。
- 代码受控 v1 算法身份、无假内容文件/伪造哈希、限制已写明：`escalation.py:14-19,62-74`、`docs/contracts/runtime-config.md`。
- reuse 就绪不以 PDF 已获取/extraction 就绪/value 实际输出为条件：`compile.py:266-290`，缺项原因固定且逐槽测试：`tests/test_config_reuse.py:45-120`。
- 评论两点厘清已落实：draft §3.7 改 `reuse_escalation_research_values = {3}`（`intent/draft.md:237`）、§7.4 改字段并声明别名不作输入（`intent/draft.md:1007-1016`），§3.5 本已是复数权威名；`excerpt_priority` 只收 `[availability, methods]`，其他顺序按受控原因拒绝，有序哈希用隔离 fixture 验证（`tests/test_config_escalation.py:190-198`），未扩成可切换业务规则。
- 缺项/合法多值/非法元素/未知算法版本/契约漂移/版本冲突/重启回放均有公共服务 + 真实 CLI 覆盖（重启回放经子进程公共服务，因 CLI 本无 load 命令）；依赖矩阵与文档已同步。

**(b) 范围蔓延：**

1. `intent/draft.md:628-640` 与 `968-981` — diff 在 Read/Screening 输出代码块（`EvidenceRef`、`BoundaryOutput` 等）插入类间空行，属与本票无关的格式化改动。无语义影响；建议今后格式化与行为票分开。其余新增文件（examples、docs、a2_scope 哈希）均为本票验收或仓库验证流程所要求。

**(c) 实现错误：**

1. 低风险（潜在，非当前违规）— `src/paper_radar/config/escalation.py:34-36`：`reuse_escalation_research_values` 的 `default_factory=lambda: [3]` 不经 `unique_research_values`/`min_length` 校验（Pydantic v2 默认 `validate_default=False`）。当前默认 `[3]` 合法、行为正确；但若未来默认改为空/重复/未排序，会绕过「集合非空且重复拒绝」与「编译后集合语义相同」的承诺且快照回放仍自洽。最小修复：`ConfigDict` 加 `validate_default=True`。依据：验收标准「集合非空且重复拒绝」「编译后的集合语义相同」。

其余重点怀疑项均验证为正确：未实现成 `>=3` 阈值；版本字符串非自由输入；别名未形成第二权威；同版本改字节被拒；CLI 覆盖齐全；`Escalation` 未反向依赖 storage/contracts；A1 固定哈希与外部 I/O 哨兵未动。

## 汇总

- Standards：0 硬性违规 / 5 项 judgement call；最重者：新增测试支撑模块未钉入 `scripts/a2_scope.py` 与 offline-evidence 先例不一致（第 4 项）。
- Spec：0 遗漏 / 1 项范围蔓延 / 1 项潜在实现风险；最重者：`escalation.py` 默认值未经校验器（c-1，当前不可观测）。

## 本轮逐条核实与处理

核实基线：`6f7e434`。按用户要求跳过「人工针对性检查入口」章节，原审查内容保留为历史记录；本节记录建议取舍、实际改进及验证依据。

| 原报告条目 | 核实结论 | 本轮处理与理由 |
| --- | --- | --- |
| Standards 1：枚举校验器重复 | 形状相似属实，通用工厂建议不采纳。 | 两个算法校验器各自返回不同受控类型，错误语义也不同；`valid_protocol` 还允许 `None`。当前短校验器便于单独阅读，通用工厂增加抽象而没有实际共用策略需求。原报告所说「措辞变化需改三处」并非当前维护要求，服务边界仍统一脱敏为字段路径。 |
| Standards 2：测试函数级导入 | 两处无必要的延迟导入属实，采纳整理建议。 | `canonical_json` 与 `upgrade_database` 提升到对应测试模块顶部。此处不是仓库明文违规，也不推断所有其他测试均使用顶部导入；生产 CLI 的延迟导入继续服务于 help 无 I/O 约束。 |
| Standards 3 / Spec (b)-1：无关空行 | 属实，采纳恢复建议。 | 恢复 draft 的五处类间空行，使这些区域与 `81e942b` 一致。正式离线格式检查只覆盖 `src/tests/scripts`（`scripts/offline_evidence.py:default_checks`），没有要求格式化 Markdown 中的 Python 示例。 |
| Standards 4：测试支撑工厂未钉入范围 | 缺口属实，采纳登记建议。 | 将 `tests/config_reuse_support.py` 的固定字节哈希登记到 A2 源码/支撑清单，并更新 `escalation.py` 的源码哈希及 offline-evidence 文档。既有 A1、A2-01 固定测试哈希不修改；不重标历史结论为完整 A2 通过。 |
| Standards 5：列表保序测试归属 | 跨模块调用属实，保留当前归属。 | Issue #19 明确要求用隔离序列化 fixture 验证有序列表哈希。这一测试与固定摘录顺序的拒绝测试并置，可以同时看到生产顺序约束和序列化保序承诺；单个隔离测试不足以要求新建模块，也不开放反转生产配置。 |
| Spec (a)：未发现遗漏或部分实现 | 认可原结论。 | 本轮对照 Issue #19 正文、评论和公共服务/CLI 回归，仍保持唯一触发字段、集合语义、受控 v1 算法身份、固定摘录顺序、原子登记和历史回放；未引入后续票的投影、建议执行或校准事件。 |
| Spec (c)-1：默认触发集合未校验 | 风险属实，采纳加固建议；当前 `[3]` 本身合法。 | `Escalation` 开启 `validate_default=True`，代码声明默认值也走类型、非空、去重和排序校验。当前生产默认仍为 `[3]`，现有合法材料的编译语义和快照身份不变；同步 runtime-config Contract，无须 migration。 |

### 默认值风险的复现与回归

作者声明的默认值不能通过用户 YAML 设置，因此使用继承权威配置类型和校验器的隔离 fixture，分别声明 `[3, 2]`、`[3, 3]`、`[]` 作为测试默认值。修复前，三项回归全部失败：默认顺序没有规范化、重复和空集合没有拒绝。修复后，结果分别为 `(2, 3)`、校验失败、校验失败。测试不改生产默认值，也不维护第二份生产参数 Contract。

现有公共服务默认值用例还补充了真实 SQLite 的 `compile/load` 回放断言，验证省略触发字段仍得到 `{3}` 并能保存和加载同一快照。

### 验证依据与范围

- 本轮相关回归：`uv run --offline --locked pytest -q tests/test_config_escalation.py tests/test_config_reuse.py tests/test_config_reuse_persistence.py tests/test_config_reuse_cli.py tests/test_config_architecture.py tests/test_a2_acceptance.py`，97 项通过。
- `uv run --offline --locked mypy` 与相关 Ruff 静态检查通过；正式范围的 `ruff format --check src tests scripts` 通过。
- 完整离线验证使用仓库入口 `./scripts/check-offline`；实际结论由本轮 `verification-runs/<run_id>.json`、`.a1.json`、`.a2.json` 留存，以终端返回和这些证据为准。
- 原报告顶部的 `python -m scripts.a2_scope` 与 `python -m scripts.a2_acceptance` 虽可退出 0，但两个模块均没有执行验收的 `__main__` 入口；仅加载模块不能作为已运行 A2 验收的依据。
- 本轮全部使用合成配置和临时 SQLite，不运行 live 来源、模型、PDF 或正文解析验收。同算法版本下的代码语义变化仍无法由 A2 自动检测。

## 人工针对性检查入口

以下入口可在不改动代码的前提下，对本笔提交的行为做人工验证（均离线）：

1. **CLI 端到端走查（推荐主入口）**：按 `docs/contracts/runtime-config.md` 与 `docs/verification/offline-evidence.md` 描述的流程，用 `examples/config/settings-reuse.yaml`、`examples/config/models/models-reuse-v1.yaml`、`examples/config/screening/reuse-escalation-v1.yaml` 作输入，对临时目录执行 `paper-radar config ...` 的 compile/show 命令序列，人工核对：缺项原因中文文本、非法集合（布尔/越界/重复）、未知算法版本、同版本改字节、版本冲突各错误的退出码与脱敏输出。对应自动化覆盖在 `tests/test_config_reuse_cli.py`，可直接 `uv run pytest tests/test_config_reuse_cli.py -v` 逐条对照。
2. **持久化与重启回放**：`uv run pytest tests/test_config_reuse_persistence.py -v`，或手工两次运行公共服务编译（第二次模拟重启）核对快照字节一致。
3. **集合语义与字段别名**：`uv run pytest tests/test_config_escalation.py -v`，重点看默认值、别名拒绝、`[2,3]`/`[3,2]` 身份不同语义相同、excerpt_priority 有序哈希 fixture 各用例。
4. **范围钉扎**：`uv run python -m scripts.a2_scope`（核对登记模块哈希未被悄悄改动）与 `uv run python -m scripts.a2_acceptance`（A2 阶段验收脚本）。
5. **冻结契约一致性**：`diff -r contracts/screening/reuse-assessment examples/contracts/screening/reuse-assessment`（decision-reasons 同理），确认示例副本与权威契约字节一致。
6. **`--help` 无 I/O 验证**：`paper-radar config --help` 在不存在的配置路径/无数据库环境下应正常输出中文 help，可用 `strace -e trace=openat` 或临时 HOME 观察无业务文件创建。
7. **无法直接验证项**：「A2 无法自动检测同算法版本下的代码语义变化」是文档声明的固有限制，无自动化入口，只能通过评审 `docs/contracts/runtime-config.md` 相应段落确认声明存在且措辞准确。
