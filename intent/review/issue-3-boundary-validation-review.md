# 代码审查：Issue #3 边界输出验证（HEAD~2...HEAD）

- 固定点：`HEAD~2`（ed1dba1）
- 提交：`10d785f Implement boundary output validation (#3)`、`1d14b34 Address boundary validation review findings`（经 `git log HEAD~2..HEAD --oneline` 验证恰好两笔）
- 规格来源：GitHub Issue #3（正文 + 全部 comments）
- 审查方式：只读；未修改代码、未创建 commit、未对 Issue 做写操作
- 离线验证（由审查代理实际运行）：`uv run --offline pytest tests/test_boundary_validation.py tests/test_screening_architecture.py` 39 通过；`./scripts/check-offline`（lock、ruff、mypy strict、全部 40 测试）全部通过

## Standards

整体高度合规：受控枚举、中文可操作错误、脱敏 issues、文档同步（README + 新增契约文档）、测试齐备。`validation.py:95-108` 刻意在 `except` 块外抛出 `OutputValidationError`，使 `__context__` 为 None、不泄漏 pydantic 细节并有测试钉住——这是"错误脱敏"规范的正确实现。

### (a) 违反仓库明文规范（硬违规）

**H1. 第二份手写字段清单（候选硬违规）** — `src/paper_radar/screening/validation.py:18`
- 依据：intent/draft.md §4.5"两阶段唯一权威 Schema 位于 §7.4；不得复制或私自扩展另一组字段定义"；阶段 A 测试项"不存在第二份手写字段定义"；AGENTS.md"Frozen Contract 必须从权威 Pydantic Schema 生成，不维护第二份手写 Schema"。
- 问题：`_KNOWN_BOUNDARY_FIELDS = frozenset({"boundary", "reason_zh"})` 手工复制了 `BoundaryOutput` 的字段名。规则字面针对完整字段定义，此处是字段名子集，处于规则边缘，故标为"候选"。
- 实际影响：`BoundaryOutput` 增字段后该集合静默过期，合法字段的 location 会被误渲染为 `$.<额外字段>`（把契约字段当额外字段）；现有测试 `test_boundary_authoritative_schema_contains_only_declared_fields` 只钉 schema 本身，抓不到漂移。
- 最小修复：改为 `frozenset(BoundaryOutput.model_fields)`，或新增两者一致性断言。

### (b) Fowler 基线判断题

**J1. Duplicated Code** — 同 H1（`validation.py:18` 与 `schema.py:15-16` 字段定义重复）。修复同上，一举两消。（占位文本清单在 text.py、契约文档、测试参数化三处出现属合理重复：测试钉死具体值、文档面向消费方，不报。）

**J2. 未记录的公共导出** — `src/paper_radar/screening/__init__.py:10,13`
- 问题：导出了 `EXPLICIT_PLACEHOLDER_TEXTS`（以及 `OutputErrorCategory`/`OutputValidationIssue`），但 `docs/contracts/screening-validation.md` 的"公共入口"只示例 4 个名字，未说明完整公共面。
- 实际影响：消费方无法从契约文档确定可用边界。
- 最小修复：文档补一句完整导出清单，或停止导出该常量。

**J3. 契约文档与实现措辞不一致（Minor）**
- `docs/contracts/screening-validation.md` 称"`None` 或空的**只读** mapping 合法"，但 `validation.py:90` 接受任何空 `Mapping`（含普通可变 dict）。
- `README.md` 称"失败时**返回**……受控错误"，实现是抛出（契约文档写"抛出"是对的）。
- 实际影响：小，但契约文档是后续 ticket 的对接依据。
- 最小修复：文档改为"空 mapping"、"失败时抛出"。

### 已评估未报

- `MISSING_CONTEXT`/`BUSINESS_RULE` 暂无产出路径：契约文档明文定义其为共享词汇，属契约先行，非 Speculative Generality。
- `validate_output` 硬编码 BOUNDARY 三处：当前仅一个 kind，符合"范围控制/最小改动"。
- `kind: object` 宽松签名：验证入口必须接受任意坏输入以产出受控错误，属合理边界设计。

## Spec

实现高度忠实。AC1（strict+frozen `BoundaryOutput` 仅两字段、五类拒绝、不修复）、AC2（`validate_output(kind, payload, context=None)` 单一入口、未知 kind/非空 context 失败）、AC3（占位清单固定、正反例、原文逐字保留、输入不变）、AC4（issues 仅 location/category/中文指引、额外字段名脱敏、`__cause__`/`__context__` 均为 None、敏感标记覆盖 stdout/stderr/日志）、AC5（AST 导入边界检查在离线测试、无文件导出）均有实现与测试。Comment 2 的三点补充（入口定形、共享词汇入文档、检查落在离线测试）全部兑现；`MISSING_CONTEXT`/`BUSINESS_RULE` 两个暂未产出的类别为 Comment 2② 明确授权，不算范围蔓延。

### (a) 缺失/部分实现

**A1（轻微）：导入扫描器正向自检覆盖不全** — `tests/test_screening_architecture.py:77-93`
- 依据：AC5「加入**可检测**违规导入的边界检查」。
- 问题：扫描器自检测试只验证相对导入（`from ... import cli`）可被捕获，未覆盖绝对导入（`import sqlite3`）与绝对 `from x import y` 的正向自检；`_imports_in` 的 `ast.Import` 分支（第 46-47 行）无对应自检用例。
- 实际影响：扫描器未来被改坏成漏检绝对导入时无测试报警，边界检查形同虚设。
- 最小修复：在自检 fixture 中追加 `import sqlite3` 一行并断言被捕获。

### (b) 范围蔓延

无发现。README 与 docs 更新均为 AC5「更新接口文档」要求；暂未使用的错误类别为 Comment 2② 明确授权。

### (c) 实现有误

**C1（轻微）：「只读上下文」文档与实现口径不一** — `docs/contracts/screening-validation.md:36` vs `src/paper_radar/screening/validation.py:90`
- 依据：AC2「适用只读上下文」；文档称「`None` 或空的**只读** mapping 合法」。
- 问题：实现只检查 `isinstance(context, Mapping) and len == 0`，可变的空 `dict` 同样通过；仅 `MappingProxyType({})` 出现在正例测试（`tests/test_boundary_validation.py:151-158`），空 `dict` 未被拒绝也无测试约定。
- 实际影响：调用方传入空可变 dict 被静默接受，与文档承诺的「只读」不符；因 boundary 本不需要上下文，实际语义影响为零。
- 最小修复：将文档改为「`None` 或空 mapping 合法」（成本最低且对后续 kind 更宽松），或代码中仅接受 `MappingProxyType`。

## 小结

- Standards 轴：4 项 finding（1 项硬违规候选 + 3 项判断题）；最严重为 H1/J1（`validation.py:18` 手写字段清单与权威 Schema 漂移风险）。
- Spec 轴：2 项 finding（1 项部分实现 + 1 项实现偏差），均为低严重度；最严重为 A1（导入扫描器缺绝对导入正向自检）。
- 两轴均不构成 Issue #3 验收阻塞；H1 与 C1 修复成本均为单行级。
