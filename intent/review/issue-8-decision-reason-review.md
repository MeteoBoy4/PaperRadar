# Issue #8 双轴代码审查：决定原因契约

- 审查范围：`git diff HEAD~2...HEAD`（固定点 `HEAD~2` = 46e28fce）
- 提交（恰好两笔，已验证）：
  - `1fe7998 Implement decision reason contract (#8)`
  - `09c40ba Address decision reason contract review (#8)`
- 规格来源：GitHub Issue #8 正文 + 唯一 comment（规格更正：直接人工决定与普通复核同一组 denied 原因），交叉对照 `intent/draft.md` §7.5 与 `intent/discussions/直接人工决定.md`
- 标准来源：AGENTS.md、CONTEXT.md、docs/agents/domain.md + Fowler 坏味道基线
- 涉及文件：README.md、docs/contracts/frozen-contracts.md、docs/contracts/screening-validation.md、src/paper_radar/screening/__init__.py、src/paper_radar/screening/reasons.py（新增）、src/paper_radar/screening/validation.py、tests/test_decision_reason_validation.py（新增）
- 审查方式：Standards / Spec 两个独立只读子代理并行执行，结果分轴聚合，不合并排序

## Standards

**硬性违反：未发现问题。** diff 与成文标准逐条核对结果：原因权威落位 `screening/reasons.py` 符合 draft.md:1330「screening/reasons.py 是受控原因的唯一权威」；16 原因、8 来源、34 组合与 draft.md §7.5 表逐项一致；内存 JSON Schema 由权威 Pydantic 类型生成，符合「Frozen Contract 必须从权威 Pydantic Schema 生成，不维护第二份手写 Schema」；磁盘冻结延后已在 README/frozen-contracts.md/screening-validation.md 三处如实标注，符合阶段化交付与文档维护要求；受控错误类别复用 `BUSINESS_RULE` 未另建同义类别；测试离线、脱敏（test:553-602 验证不回显输入）；命名沿用 `value_types.py` 的 StrEnum + MappingProxyType 模式。工具已强制项（ruff/mypy strict）跳过。

**判断性建议（possible smells）：**

1. **possible Mysterious Name** — `src/paper_radar/screening/reasons.py:114`。`_HUMAN_DECISION_SOURCES` 名为"人工决定来源全集"，实际只含三个交互入口；同属人工决定的 `METADATA_ABANDONMENT`、`MANUAL_READ_REQUEST` 在 reasons.py:254-257 才被并入 `ScreeningDecision`。影响：读者易误以为它是 `ScreeningDecision` 的完整来源集。修复：改名 `_REVIEW_ENTRY_SOURCES`。
2. **possible Mysterious Name** — `reasons.py:291`、`reasons.py:314`。`literal: Any = Literal`、`_union: Any = Union` 为动态下标把类型构造器别名为 `Any`，意图隐蔽。修复：抽具名辅助（如 `_const_model(...)`）封装 `create_model` 调用，或加一行说明。
3. **possible Duplicated Code** — `tests/test_decision_reason_validation.py:428-463`。`_combinations_expressed_by_schema` 与 `_schema_accepts` 重复 `$ref → $defs → properties` 的分支导航。修复：提取 `_branch_definitions(schema)` 迭代器共用。
4. **possible magic string 重复** — `validation.py:404-407` 的 guidance dict 键 `"result"/"source"` 与 `reasons.py:216-226` 的 `Literal["result","source"]` 跨文件重复。修复：在 reasons.py 导出字段名常量或在 `invalid_combination_fields` 返回处附带 guidance。
5. 微小：`reasons.py:78` 的 `("固定校准成员失败投影")` 多余括号与兄弟行不一致，并被 test:230 原样复制；去括号即可。

已抑制：测试重写组合表/中文说明属独立 oracle，且文档已声明"表格解释代码中的唯一组合定义，不是第二份运行时规则"，不报 Duplicated Code。

## 建议核实与处理（2026-09-21）

逐条对照 Issue #8、当前公共接口和模块边界后，处理如下：

1. **采纳。** 原 `_HUMAN_DECISION_SOURCES` 确实容易被理解成
   `ScreeningDecision` 的完整来源集合。改名为
   `_GENERAL_HUMAN_JUDGMENT_SOURCES`，明确它只表示共享一般人工判断原因的盲评、
   普通复核和直接人工决定三个入口；元数据人工放弃与人工精读请求仍作为特殊来源
   单独并入决定身份。
2. **采纳。** 将动态 `Literal[...]` 与 `Union[...]` 构造分别封装为
   `_literal_value_type()` 和 `_union_type()`，用函数名与 docstring 解释为何局部需要
   `Any`，组合模型主体不再出现含义不明的 `literal` / `_union` 临时别名。
3. **采纳。** 测试新增 `_schema_branch_definitions()`，统一完成 `$ref` 到 `$defs`
   分支定义的导航；组合集合检查与样例接受检查共用该迭代器。
4. **不采纳。** `result` / `source` 是公开原因契约的实际字段名，并已由
   `Literal["result", "source"]` 限定，不是无约束的业务 magic string。把 guidance
   附到 `reasons.py` 的返回值会让纯组合规则依赖用户展示文案；为两个固定字段额外
   导出常量也会扩大公共面。现有边界保持为：`reasons.py` 只指出不合法字段，
   `validation.py` 负责将字段转换为脱敏、可操作的中文错误。
5. **采纳。** 删除实现与独立测试 oracle 中字符串外层的多余括号，统一相邻项格式。

以上均为内部可读性调整，不改变 16 个原因、8 类来源、34 个合法组合、公共序列化值
或生成 Schema 的内容，也未引入冻结快照、CLI 或持久化能力。

复验：`pytest tests/test_decision_reason_validation.py tests/test_screening_architecture.py`
共 66 项通过；`./scripts/check-offline` 的 lockfile、格式、静态检查、mypy、全部 316
项测试及已提交 boundary 冻结契约一致性检查全部通过。

## Spec

**结论：未发现问题。**

核对明细：

(a) 缺失/部分实现：无。

- §7.5 预期表 16 行 × 结果 × 允许来源与 `src/paper_radar/screening/reasons.py:122-181` 的 `DECISION_REASON_DEFINITIONS` 逐格一致，共 34 个合法组合（三态、八来源、16 原因齐全）。
- 更正 comment 已落实：三个 denied 原因对 `direct_manual_decision` 开放（reasons.py:130-150）；denied 未引入泛化 `user_judgment`（:151-153 仅 accepted）；`model_failure` 仅两种投影来源的 pending 投影（:171-179）。
- 验收 1「未知/缺失/额外/错误类型拒绝，无自动补齐」：`extra="forbid"`、必填、`_require_enum_string` 拒绝非字符串类型（reasons.py:184-204）。
- 验收 3「唯一组合定义生成 Schema」：34 个组合模型由定义动态生成，无第二份手写映射；`screening_reason_json_schema()` 只产内存 Schema。
- 验收 4「测试期望独立」：`tests/test_decision_reason_validation.py:57-152` 的 `ALLOWED_COMBINATIONS` 为字面量硬编码（子代理逐格复核与 §7.5 一致），未导入被测 `DECISION_REASON_DEFINITIONS`；384 个受控组合全遍历断言拒绝；三种特殊原因、错误来源、投影冒充均有单列用例（:333-425）。
- 验收 5「错误不回显输入」：`OutputValidationError` 消息仅由 location/category/guidance 构成（errors.py:36-44），测试断言 marker 不出现在 str/repr/stdout/stderr/log 且 `__cause__`/`__context__` 为 None（tests:553-602）。

(b) 范围蔓延：无。无数据库写入、无 `contracts/` 磁盘快照、无 CLI 接入；文档（README、frozen-contracts.md、screening-validation.md）明确说明冻结导出留给后续 ticket，与验收 5 一致。

(c) 实现错误：无。公共入口 `validate_screening_reason`（validation.py:395-418）先脱敏校验结构、再报字段级组合错误、最后经 union 适配器返回保留身份的 `ScreeningSuggestion`/`ScreeningDecision`/`ScreeningFailureProjection`。

验证：`pytest tests/test_decision_reason_validation.py tests/test_screening_architecture.py` 66 通过；完整离线套件 316 通过。纯逻辑依赖边界（test_screening_architecture）对 reasons.py 无违规。

非阻断观察（不构成本票 finding）：

1. `intent/draft.md:233/267/620` 旧段落将精读请求决定描述为「来源为用户 / `source=user`」，与 §7.5 权威表的 `manual_read_request`（人工精读请求）来源值措辞不一致。实现按 §7.5 落地是正确的，但后续 ticket 接 CLI/持久化时需注意该旧表述。
2. 权威类型被绕过公共入口直接 `model_validate` 时，Pydantic 原生 `ValidationError` 可能携带输入值；公共入口路径已完全脱敏，验收 5 针对公共面已满足。

## 总结

Standards 轴 5 个判断性建议、无硬性违反；最严重为 `_HUMAN_DECISION_SOURCES` 命名误导（reasons.py:114）。Spec 轴未发现遗漏、部分实现、错误实现或范围蔓延。
