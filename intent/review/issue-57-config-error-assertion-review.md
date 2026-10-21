# Issue #57 双轴审查：ConfigError 负例断言约束

> 以下保留原审查记录；2026-10-21 的逐条核实、处理决定与修复验证见文末「实施侧核实与处理」。

- 审查范围：`git diff HEAD~2...HEAD`（固定点 `HEAD~2` = `94ed89e`，HEAD = `3d39d42`）
- 提交：`3df7aa5` test: constrain ConfigError failure assertions (#57)、`3d39d42` test: require assertions for captured ConfigError (#57)
- 变更规模：9 个文件，+203/−13（新增 `tests/test_config_error_assertion_architecture.py` 189 行；4 个 scope 文件仅改登记哈希）
- 规格来源：GitHub issue #57（body + 核对评论；labels: `enhancement`、`ready-for-agent`；`blockedBy` #61 已关闭）
- 标准来源：`AGENTS.md`、`docs/agents/{testing,python-conventions,documentation,refactor,invariants,scope}.md`、`README.md`/`GLOSSARY.md` 相关段落、既有 `tests/*_architecture.py` 约定，另加 skill 规定的 Fowler 坏味道基线
- 方式：Standards 与 Spec 两个只读子代理并行审查，本文件只做汇总与逐条核实，不跨轴重排。两个子代理均无 shell 权限，未能自行运行 diff/测试；工作树干净、改动已在 HEAD 提交，故改以 HEAD 文件内容 + `verification-runs/` 回执核对。
- 汇总者独立核实（只读）：`sha256sum` 抽查 `tests/test_config_projection_algorithms.py`、`tests/test_stage_input_{extraction,reuse}.py`、`scripts/a{2_full,3,4}_scope.py` 实际字节与各自绑定方登记值全部一致；`uv run --offline --locked pytest -q` 跑上述三个模块 + 新增守卫模块 = 127 passed；`verification-runs/58c83ca9….json` 记录 HEAD `3d39d42`、`dirty:false`、六项检查（lockfile/format/lint/types/tests/contracts）全部 `passed`，即完整 `./scripts/check-offline` 已在当前提交上返回 0（由实施侧产出，非本次审查运行）。

## Standards

（子代理报告，保留原判断措辞；每条后的「汇总者核实」为父会话补充）

**Correct**

- 4 处收紧（`tests/test_config_projection_algorithms.py:111,140`、`test_stage_input_extraction.py:132`、`test_stage_input_reuse.py:345`）都使用 `match=rf"^{group}\.{field}："` 这类似受控字段路径的方式，符合 `docs/agents/testing.md` 新增的「负例必须断言受控的字段路径或错误类别」；`tests/` 下已无裸 `pytest.raises(...ConfigError):`。
- 新模块把纯 AST 判定 `config_error_assertion_violations(source, filename)` 与读文件分离，符合 `python-conventions.md`「确定性逻辑与 I/O 分离」；文档在同一变更内更新，符合 `documentation.md`。
- 新测试文件未登记进 A1–A5 scope 是正确的（`docs/verification/offline-evidence.md:98`「未登记文件与额外计数 key 不会成为收集目标」）。

**Finding（硬性标准，P1）** `tests/test_config_error_assertion_architecture.py:26-46` 的 `_asserts_bound_error` 只要求后续断言引用绑定名，因此接受只有泄漏断言、既不断言字段路径也不断言错误类别的负例：`tests/test_config_journals_validation.py:136-138`、`test_config_adapter_validation.py:134-136`、`test_config_value.py:217-219` 只剩 `assert "PRIVATE_MARKER" not in str(error.value)`。这与 `docs/agents/testing.md` 新增的「不能只凭异常类型就判定成功」不一致（该模块自己的 docstring 承认较弱的规则）。最小修复：让断言必须命中字段路径或类别（否决纯 `not in` 型断言），或把文档措辞改为实际强制的「`match=` 或 `as` 绑定后断言」。

> 汇总者核实：三处被点名的用例均为既有文件、不在本次 diff 内（本次只改了 4 处 raises）；issue #57「范围 2」明确允许「用 `as` 绑定异常、随后对它做断言」，因此 Spec 轴不算缺失。冲突点真实存在，但落在「testing.md 措辞强于 AST 守卫实际强度」——属文档与守卫的一致性问题，不是本次新增用例的违规。

**Finding（判断项 P2）**

- Mysterious Name：模块后缀 `_architecture` 与既有模块边界测试不同义，这里检查的是测试写法 → 改名 `test_config_error_assertion_conventions.py`；`config_error_assertion_violations` 缺 `_` 前缀（同目录 `_imports`、`_local_nodes` 都带）。
- Duplicated Code：`parents` 映射与 AST 遍历与 `tests/config_test_support.py:97-100` 重复 → 收入该 support 模块。
- Primitive Obsession：违规以 `f"{filename}:{node.lineno}"` 裸字符串返回。

> 汇总者核实：`tests/config_test_support.py:97-100` 实为 `imported_modules()`（无 parent 映射），全仓库 `iter_child_nodes` 只出现在新模块（2 处），**该 Duplicated Code 不成立**。`_architecture` 后缀在本仓库既有多为模块边界/依赖方向测试，用于「测试写法约束」确有偏差，保留为判断项。

**Finding（待确认，P2）** `scripts/a3_scope.py`、`scripts/a4_scope.py` 未登记本次任一改动/新增测试文件（仅 `a2_full_scope.py:52,256` 与 `a5_scope.py:46,50,75,91`），其「哈希重绑」无可见原因。请运行 `git diff HEAD~2...HEAD -- scripts/a3_scope.py scripts/a4_scope.py` 核对，并运行 `./scripts/check-offline`（哈希只能由审计实测）。

> 汇总者核实：**不成立**。a3 登记 `scripts/a2_full_scope.py`、a4 登记 `scripts/a3_scope.py` 与 `scripts/a2_full_scope.py`，改上游哈希必然级联——正是 issue #57「scope 重绑」要求的 `a2_full→a3→a4→a5` 顺序；实测登记值与文件字节全部一致，`collected/passed` 计数未变。

**Merge verdict: OK with notes**

## Spec

（子代理报告，保留原判断措辞；每条后的「汇总者核实」为父会话补充）

**核对方式说明**：`watchdog_diff` 显示工作树相对审查起点无改动，工具不覆盖已提交区间，且本会话无 shell/git，故以 HEAD 文件内容 + `verification-runs/` 审计记录交叉核对（而非逐行 diff）。

**(a) 规格缺失/半成品**：未见缺失。四处断言已锚定并转义（`tests/test_config_projection_algorithms.py:111` `match=rf"^{group}\.{field}："`、`:140` `^escalation\.excerpt_priority：`；`tests/test_stage_input_extraction.py:132`、`tests/test_stage_input_reuse.py:345`）；AST 守卫含四类合成样例与准确位置断言（`tests/test_config_error_assertion_architecture.py:94-196`）；`docs/agents/testing.md:4` 一字不差的补句。唯一无沉淀物的是「临时触发另一字段错误应失败」的一次性手工验证（规格本来说明不必沉淀），无法核对。

**(b) scope creep**：无法枚举完整 diff（同上限制）。间接证据表明未越界：注册表审计在 HEAD 上 `actual==expected` 且无 `HASH_DRIFT`（`verification-runs/58c83ca9….a2-full.json`、`.a4.json:312`、`.a5.json:209-217,507-533`）；生产源码哈希在早前回执与新回执一致（`0a0606f8….a2-full.json:360-362` vs `58c83ca9….a2-full.json:360-362`，`src/paper_radar/config/__init__.py` = `e8e1844c…`）；守卫模块未出现在任何 scope 登记（仓库内 grep 无登记点），符合「默认不登记」。

**(c) 实现正确性**：正则均锚定 + `\.` 转义 + 全角 `：`，且 HEAD 回执显示 `exit_code 0`、`test_config_projection_algorithms.py` 11 passed、`test_stage_input_extraction.py` 38（子代理原文误写为 `test_config_stage_input_extraction.py`，已更正）、`test_stage_input_reuse.py` 63（`58c83ca9….pytest.json`），说明匹配的是真实消息。哈希级联顺序正确：`a2_full_scope.py:256-257` = `e9a7be…`；`a3_scope.py:307-309`→`05502a…`；`a4_scope.py:341-343`→`f2d37c…`；`a5_scope.py:140-150`→`05502a…/f2d37c…/56c494…`，全部与文件实际哈希一致。用例计数未变：早期回执与新回执逐模块 collected/passed 完全相同（11/38/63 及其余全部模块）。

> 汇总者核实：(a)(c) 结论与我独立执行的 `sha256sum` 与 127 passed 一致；(b) 我已查看完整 diff，9 个文件全部落在 issue #57「范围」1–3 内，无生产代码改动，无 YAML 辅助器，用例输入构造未变。

**Finding: P2** 守卫只识别字面 `pytest.raises`（`test_config_error_assertion_architecture.py:71-88` 要求 `func.value.id == "pytest"`），`from pytest import raises`、`import pytest as pt`、`from … import ConfigError as CE` 三种写法会漏检；当前仓库无这些写法（grep 无匹配），不影响现状。最小修复：在模块 docstring 记录该边界，或放宽到 `func.attr == "raises"` 且首参名以 `ConfigError` 结尾。

**Finding: P2** 绑定放行仅要求「同作用域后续任一 `assert` 引用该名」（`:33-60`），同一函数内两个 `with pytest.raises(ConfigError) as error` 只有后者被断言时前者也放行；docstring 已声明不分析控制流，属记录性局限，无需现在改。

> 汇总者核实：两条均成立且均为守卫的已知边界；`grep "from pytest import\|import pytest as"` 在 tests/ 下无结果，与报告一致。另确认守卫对 `with` 体内的 `assert` 会因 `lineno <= end_lineno` 被跳过，不会误放行「在 with 体内断言」的写法。

## 汇总

- Standards：7 条发现（1 条硬性 P1：守卫对「仅泄漏断言」放行，与 `testing.md` 措辞不一致；4 条判断项；2 条经汇总者核实不成立）。同轴最重：P1 守卫强度与文档措辞不一致。
- Spec：2 条发现（均为 P2 守卫边界：raise 别名/导入别名漏检、同作用域重复 with 的绑定放行）。无缺失、无 scope creep；同轴最重：P2 守卫别名漏检（现状无害）。

## 实施侧核实与处理（2026-10-21）

核对基线为 `3d39d42`。本次重新读取了 [Issue #57](https://github.com/MeteoBoy4/PaperRadar/issues/57) 的正文、评论与完整原生关系（无子任务，唯一前置 #61 已关闭），并直接检查 `94ed89e...3d39d42` 的完整 diff、被点名的历史用例和测试支撑代码。下表将合并在原报告同一条中的命名建议分开处理，逐条记录取舍。

| 建议 | 核实判断 | 处理 |
| --- | --- | --- |
| Standards P1：仅泄漏断言也被守卫放行，故违反新增测试规范 | **部分采纳风险说明，不接受 P1 定性及建议的机械判据。** 三处被点名的历史用例确实只有敏感内容未泄漏断言；但本票明确要求守卫检查 `match=` 或绑定后断言的形式，并未要求静态证明断言语义。这些历史用例也不属于原实现 diff。测试规范是人工审查要求，不能把形式守卫当作规范的完整证明。 | 保留「负例必须断言受控字段路径或错误类别」原规则；在 `docs/agents/testing.md` 和守卫模块 docstring 明确形式检查不能代替语义审查，且仅泄漏断言不满足该规则。不把规范降级为任意 `assert`，也不一概拒绝 `not in`：既有 `error_message()` 先检查泄漏、再返回消息供调用方与固定错误文本比较，单凭运算符不能判断完整测试是否验证了目标原因。三处历史用例的断言质量局限仍保留说明，本次不批量迁移已冻结测试。 |
| Standards 判断项：将 `_architecture` 改名为 `_conventions` | **不采纳。** Issue #57 明确要求「AST 架构测试」，仓库没有把 `_architecture` 限定为模块依赖测试的命名硬规则。 | 保留文件名；改名只会造成已有引用和审查位置变动，没有修复行为问题。 |
| Standards 判断项：纯检测入口加 `_` 前缀 | **不采纳。** `config_error_assertion_violations(source, filename)` 是供合成源码测试使用的纯检测入口；`_local_nodes` 等函数是该入口的内部实现，两者用途不同。 | 保留入口名称，不把公开测试入口与内部 AST 辅助函数强行统一命名。 |
| Standards 判断项：与 `config_test_support.py` 存在重复，应提取共享辅助器 | **不成立。** 该处实际是 `imported_modules()`，没有 parent 映射，也不执行相同判定；原报告汇总者已纠正。 | 不修改共享 support，避免为不存在的重复引入耦合及额外 scope 重绑。 |
| Standards 判断项：`filename:lineno` 返回字符串属于 Primitive Obsession | **不采纳。** 这里没有领域身份或结构化消费方，只需输出规格要求的诊断位置。 | 保留位置字符串及其字面量预期测试，不引入仅用于格式化诊断的小类型。 |
| Standards 待确认：a3/a4 哈希重绑无依据 | **不成立。** a3 绑定 a2_full scope；a4 绑定 a3 和 a2_full scope；更新上游必然级联。 | 本次再次执行带收集的 scope 审计，哈希与固定用例计数全部匹配。新增守卫仍未登记进 scope，本轮也无需改动任何 scope 文件。 |
| Spec P2：显式导入或别名写法漏检 | **采纳问题，拒绝过宽的匹配建议。** 新增合成回归先复现了 `from pytest import raises`、`import pytest as pt`、`ConfigError as CE` 三种漏检。只按 `.raises` 或名称后缀匹配会误伤已有反例 `other.raises(ConfigError)`。 | 根据显式 `Import` / `ImportFrom` 收集 pytest、raises 和 PaperRadar ConfigError 的别名；同时覆盖带 `match=`、绑定后断言的合法别名形式。保留无关调用放行样例。动态赋值与导入名遮蔽仍在模块说明中明确排除。 |
| Spec P2：重复 `with ... as error` 借用后一异常的断言 | **采纳并修复，不只记录局限。** 最小源码复现显示，第一次捕获未被断言时仍会放行。 | 后续 `with` 重绑会清除同名关联；区分 if/else 互斥分支，兼容既有分支外共用断言；若先用其他变量保存第一次异常，后续对保存值的断言仍有效。新增负例与这两种合法形式的正例。 |

### 本轮验证

- 修复前新增回归：守卫模块 `4 failed, 17 passed`，失败正好对应三种别名漏检及重复绑定借用断言。
- 修复后相关验证：守卫模块及原 Issue #57 三个模块，加上审查点名的 `test_config_material_compatibility.py`、`test_config_journals_validation.py`、`test_config_adapter_validation.py`、`test_config_value.py`，合计 **453 passed**。守卫从 15 个增加到 23 个合成/仓库检查用例；已登记模块及其固定用例计数未改动。
- `uv run --offline --locked mypy`：289 个源码文件通过；Ruff 格式与静态规则均通过。
- `./scripts/audit-verification-scope --collect --json`：返回 0，收集核对 `ok`；`./scripts/dev-environment check --json`：返回 0。
- 重新核实原审查无法确认的手工反例：临时在 `excerpt_priority` 用例的编译前将 `settings.profile` 改为列表，确实因 `Regex pattern did not match` 失败，实际先报错字段为 `settings.profile`；`finally` 中完整恢复了原字节，没有保留输入构造改动。
- 完整离线验收：`./scripts/check-offline` **返回 0**；lockfile、格式、静态规则、类型、全部 pytest 和冻结契约均通过，同次 A1、A2-01、完整 A2、A3、A4、A5 全部 `passed`。回执为 `verification-runs/f6dcc9f9291d4ca0939b2dba47caff5f.json` 及同前缀各组结论；证据记录基线 HEAD `3d39d42`、`dirty:true`（本轮修复尚未提交）。验证结束后仅补充了本报告的结果说明，受检代码与固定材料未再修改。

本轮只修改未登记的守卫模块、测试规范说明及本报告；未改生产代码、原有用例输入或冻结契约。AST 守卫仍不做一般控制流、跨函数或断言语义证明；本轮未运行 live 验收。
