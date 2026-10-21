# Issue #60 双轴审查：只读 scope 审计

- 审查范围：`git diff 3b1c8c0...HEAD`（固定点 `HEAD~2` = `3b1c8c0`）
- 提交：`00b84fa` feat: add read-only verification scope audit (#60)、`dd2723c` fix: reject unchecked secondary scope bindings (#60)
- 变更规模：12 个文件，+1278 行
- 规格来源：GitHub issue #60（body 与两条评论；评论中的「实现注意点」「首版范围可以缩小」视为规格）
- 标准来源：`AGENTS.md`、`docs/agents/{python-conventions,testing,cli-output,documentation,invariants,domain,refactor}.md`、`GLOSSARY.md`、`docs/verification/offline-evidence.md`、`docs/contracts/verification-scope-audit.md`，另加 skill 规定的 Fowler 坏味道基线
- 方式：Standards 与 Spec 两个只读子代理并行审查，本文件只做汇总，不跨轴重排
- 未执行：`./scripts/check-offline`、pytest、Ruff、mypy（本次要求不修改代码；下列「实现有误」项未经运行验证）

## Standards

**P1（硬违规·文档标准）**
1. `docs/agents/python-conventions.md`「用明确的领域类型和受控 enum / reason 表达状态与原因」——原因全是裸字符串：`scripts/verification_scope_audit.py:70-74,98-169`、`scripts/verification_scope_collection.py:24-102`、`scripts/audit_verification_scope.py:78-83`。仓库既有对照 `scripts/offline_evidence.py:25-45`（`CheckStatus`/`CheckReason`）、`scripts/a1_acceptance.py:53`（`A1ReasonCode`）。最小修法：在 `verification_scope_audit.py` 增 `StrEnum` 原因/kind/role，四处复用。
2. Duplicated Code（判断项）——受影响组传播算两遍：`verification_scope_audit.py:186-197` 与 `audit_verification_scope.py:88-96`；后者还有 Feature Envy（直接改 `report` 字典并重算 `affected_groups`）。修法：把收集结果合并下沉为审计模块内的一个函数。
3. Duplicated Code——计数合法性判断重复：`verification_scope_collection.py:30-33` 与 `verification_scope_audit.py:150`。

**P2（判断项）**
4. Speculative Generality——`verification_scope_registry.py:222-227` 的 `load_scopes(*, writers=…)` 仅测试注入使用，与 `docs/contracts/verification-scope-audit.md:20` 声明的边界 `load_scopes(root)` 不符。
5. 冗余字段/Data Clumps——`Scope.count_tests`（`verification_scope_audit.py:19`）恒等于 `bindings["test"]`（`registry.py:214-215`），回退分支 `audit.py:139-144` 仅合成登记可达；删字段即可。
6. Mysterious Name + Primitive Obsession——`_bindings`（`audit.py:36`）既解析「路径+哈希」又解析计数键；`bindings: Mapping[str, object]`、`counts: object`、报告 `dict[str, Any]`（`audit.py:17-18,78`）无记录类型。
7. `docs/agents/cli-output.md`「错误信息写明具体原因」——`audit_verification_scope.py:17-18` 丢弃 argparse 的 message，只留下一步（脱敏取舍可接受，建议至少输出错误类别）。
8. `docs/agents/documentation.md`「术语进 GLOSSARY.md」——新增公共词汇「固定 scope / writer / downstream / kind、role」未收录（部分术语此前已有）。

**正确**：I/O 与确定性逻辑分离（`audit.py:53,83`）、强制中文输出、契约文档与 README 同步、回归测试完备。

## Spec

已核对、未发现问题的高风险项：只读（`verification_scope_audit.py:53-77` 仅读文件；`audit-verification-scope:20` 用 `-I -B`）；旧切片覆盖（`verification_scope_registry.py:205-233` 由 `acceptance_groups()` 推导 6 组，A2-full 合并 A1 测试 `:189-197`）；bool 计数拒绝（`:189` `type(...) is not int`）；重复路径/计数 key（`:147-151`、`:127-129`）；循环/自引用（`:175-183`）；collect 不写回执、不把实测当分母（`verification_scope_collection.py:32-40,63`）；异常不静默为空（`:198-204` 与 `audit_verification_scope.py:73-79`）。

**缺失/部分**
- `--collect` 需审计先通过（`audit_verification_scope.py:84-86`），所以新增测试模块时 `count_keys_mismatch`（`verification_scope_audit.py:187`）会先拦下，看不到实测数量，只能先猜分母。

**超范围**
- `docs/contracts/verification-scope-audit.md:3` 自述“不是 Frozen Contract”，却放进 `docs/contracts/`（该目录按 `docs/agents/documentation.md` 属公共契约）；issue 只要求更新 `docs/verification/offline-evidence.md`。建议移到 `docs/verification/`。

**实现有误**
- P2 `audit_verification_scope.py:88-95`：任何非 `ok`（`collection_timeout`/`unavailable`/`collection_failed`/空 `expected`→`invalid_counts`）都把全部 126 个模块判为不符，用“所有有计数登记的组”覆盖审计得到的 `affected_groups`，报告会误指影响面。最小修复：仅 `reason == "count_mismatch"` 时重算，其余保留审计结果。
- P2 `tests/test_verification_scope_registry.py:24-36`、`tests/test_verification_scope_cli.py:78` 硬编码 431/126/2519；新测试按 issue 未登记进 scope（正确），故这三处需人工随 scope 变动维护。

**Merge verdict: OK with notes**（请另行运行 `uv run --offline --locked …` 与 `./scripts/check-offline` 确认 431/2519 等断言与 lint/mypy 实际通过；本次只读未执行）。

## 汇总

- Standards：8 条（1 条硬违规 + 7 条判断项），最严重为 reason/kind 使用裸字符串（`verification_scope_audit.py` 等三处），违反 `docs/agents/python-conventions.md` 的受控类型约定。
- Spec：3 条，最严重为 `--collect` 被审计前置门禁挡住（`audit_verification_scope.py:84-86`），恰好在“计数未登记/不一致”这一最需要实测数字的场景下不可用。

## 实施方逐项核实与处理

关联：[Issue #60](https://github.com/MeteoBoy4/PaperRadar/issues/60)。核实基点为
`dd2723c`；上方保留原始审查记录和当时的行号，以下为实际运行后的判断。
原汇总将 Spec 计为 3 条，但正文包含 4 个可独立判断的建议，故本次共核实 12 项。

| 编号 | 建议 | 判断 | 核实与处理 |
| --- | --- | --- | --- |
| S1 | 原因、kind、role 使用受控类型 | 采纳 | 新增并复用 `AuditReason`、`FileKind`、`FileRole`，登记解析错误也保留枚举原因，JSON 字符串值保持兼容。接受类型与规范改进；未发现原裸字符串本身放宽验收判据，不将其等同于 P1 数据安全缺陷。 |
| S2 | 收集结果合并下沉，统一影响传播 | 采纳 | `merge_collection` 在审计模块合并结果，复用 `_affected_groups`；CLI 仅负责调用与输出。完整计数差异追加影响及下游，不覆盖已有哈希或登记问题。 |
| S3 | 正整数计数校验重复 | 采纳 | `valid_case_count` 统一严格正整数接收边界，继续拒绝 bool、零、负数、字符串和浮点数。 |
| S4 | 删除 `writers` 注入参数 | 部分采纳 | 保留显式文件 I/O 测试边界，用于合成真实 scope/writer、新组及非法导入的回归；不是未来插件能力，也没有 CLI 覆盖入口。契约已补全 `load_scopes(root, *, writers=None)` 的实际签名与用途。 |
| S5 | 删除冗余 `Scope.count_tests` | 采纳 | 生产构造中与 `bindings[test]` 完全重复，已删除字段和回退分支，只保留一份测试清单。 |
| S6 | 解析函数命名及记录类型不清楚 | 部分采纳 | 将 `_bindings` 改为 `parse_file_bindings`，输出改为 `FileRecord`、`IssueRecord`、`CountRecord`、`CollectionResult`、`AuditReport` 等 `TypedDict`。原函数解析的是文件绑定，计数 key 只是从合法测试绑定派生，不存在另一种计数键解析职责。保留 `Scope.bindings`/`counts` 的原始 `object` 输入，以便验证并拒绝非法登记，不能用合法输入类型代替运行时校验。 |
| S7 | 参数错误缺少原因类别 | 采纳 | 输出 `unknown_argument`、`invalid_option_value` 或 `invalid_arguments` 及中文原因和下一步，仍不回显参数值或 argparse 原始消息。 |
| S8 | 将工具字段加入 GLOSSARY | 不采纳 | scope/writer/downstream/kind/role 是验收维护技术术语与字段，未引入论文、配置或校准的新领域概念；在工具契约集中解释，避免将通用实现字段逐一扩展为领域词汇。 |
| P1 | `--collect` 被哈希/计数审计前置拦截 | 采纳 | 已复现：空计数表时原实现返回 `audit_failed`，没有模块实测数。现在仅从明确测试清单取目标，允许哈希漂移或计数错误时收集；缺失、非法或冲突分母只作为未知预期，返回诊断数量，原审计仍非零。非法绑定、未知登记和引用图错误仍阻止收集。 |
| P2 | 非 Frozen Contract 文档不应放 contracts 目录 | 不采纳 | `docs/agents/documentation.md` 明确要求“公共契约进 docs/contracts/ 与 README.md”。公共开发命令契约与 Frozen Contract 是不同概念；原文已明确其不是冻结 Schema。保留文档位置，并同步修订维护入口。 |
| P3 | 收集超时/不可用/失败误报全部计数组 | 采纳 | 已用 conftest 导入失败复现：正常登记也误报 A2-01 受影响。现在仅 `count_mismatch` 追加可定位的组；timeout、unavailable、failed、skip、deselect 保留既有影响。退出码仍非零，不把无法核验当作通过。 |
| P4 | 431/126/2519 形成额外维护副本 | 采纳 | 删除生产基线总数和固定六组列表断言，改为从 `acceptance_groups()` 取 writer，并逐项与其实际导入的测试/源码/fixture 和计数常量比对；CLI 收集比对完整模块映射。小型合成回归仍使用独立字面量期望，不从被测算法重算答案。 |

### 回归与边界

- 修复前运行 `uv run --offline --locked pytest -q tests/test_verification_scope_cli.py -k 'unregistered or blame'`，两项失败分别复现缺少实测模块数量和错误归因。
- 修复后 4 个 `test_verification_scope_*` 文件共 54 项通过；覆盖缺失/非法分母仍可诊断、参数化从 2 例增加到 3 例时在哈希重绑前即可诊断且不写回分母、额外计数 key 不扩大集合、收集失败脱敏、6 类不完整收集保留已有影响，以及计数差异追加下游时不丢失既有漂移。
- 放宽计数诊断准入时另行复核缺失/不可读边界：新增 4 项回归确认缺失测试/源码、指向仓库外的链接仍不能进入收集。修复前四项均失败，补充准入限制后通过；不执行外部链接中的代码。
- `uv run --offline --locked mypy`、`uv run --offline --locked ruff format --check src tests scripts`、`uv run --offline --locked ruff check src tests scripts` 均通过；审计/范围/回执相关回归 111 项通过，此后补充的参数化变化回归也通过。
- 最终 `./scripts/check-offline` 返回 0，run_id 为 `8169c9ecaae24f9c85e4cad32932c58f`。lockfile、格式、静态规则、类型、全部 pytest、四份冻结契约均通过；A1、A2-01、完整 A2、A3、A4、A5 均为 `passed`。首轮为补齐缺失/根外链接回归而主动中断，保留其失败/未完成证据，不作为通过依据。
- 未修改任何固定验收 scope、正式六项检查、回执协议、Frozen Contract 或阶段指纹；未运行 live 来源、模型、Pi 或 NAS 验收。`--collect` 会执行测试模块/conftest 的导入代码，诊断数量始终不能代替真实测试执行或正式分母。
