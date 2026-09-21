# Issue #9 双轴代码审查：四种冻结契约单独导出与检查

- 审查范围：`git diff HEAD^...HEAD`（固定点 `HEAD^` = 9a884480）
- 提交（恰一笔，已验证）：`726c0ca Implement four frozen screening contracts (#9)`
- 规格来源：GitHub Issue #9 正文 + 唯一 OWNER comment（澄清：三份新契约各固定 v1、不改写 boundary/v1 字节；快照只冻结字段与原因合法组合，运行上下文不入快照；同步更新 frozen-contracts.md 与 CLI 帮助）
- 标准来源：AGENTS.md、CONTEXT.md、docs/agents/domain.md、docs/contracts/*.md、pyproject.toml（ruff/mypy strict 工具强制项）+ Fowler 坏味道基线
- 涉及文件：README.md、contracts/screening/{decision-reasons,reuse-assessment,value-prediction}/v1/{manifest.json,schema.json}（新增）、docs/contracts/frozen-contracts.md、docs/contracts/screening-validation.md、scripts/check-offline、src/paper_radar/cli.py、src/paper_radar/contracts/schema.py、tests/test_cli_help.py、tests/test_contract_cli.py（新增）、tests/test_contract_schema.py
- 审查方式：Standards / Spec 两个独立只读子代理并行执行，关键 finding 已由聚合者抽查核实（test_contract_cli.py:182/:549 断言、cli.py 帮助文本指引），结果分轴聚合，不合并排序

## Standards

**硬性违反：**

1. **行为变化后钉住它的测试未同步** — `tests/test_contract_cli.py:182`、`tests/test_contract_cli.py:549`。
   - 依据：AGENTS.md「编码流程」：“行为发生变化时同步新增或修改测试”。本 diff 给 `ContractName` 新增三个成员（`src/paper_radar/contracts/schema.py:37-39`），`schema.py:130` 的用户可见错误消息随之变为「未知契约；当前支持：boundary、value-prediction、reuse-assessment、decision-reasons。」，但上述两处断言仍只写 `"未知契约；当前支持：boundary"`。
   - 实际影响：断言仅靠子串匹配碰巧通过，不再忠实钉住完整指引文本；契约名增删或顺序变化都不会被捕获。
   - 最小修复：改为 `"未知契约；当前支持：" + "、".join(n.value for n in ContractName)` 动态拼接断言。

**判断性建议（possible smells）：**

1. **possible Mysterious Name / 失准指引** — `src/paper_radar/cli.py:149`、`cli.py:184`。选项 help 写「完整选择见当前用途」，但四契约清单实际在「当前支持：/当前支持的契约与声明版本：」段落（cli.py:62、85、108），「当前用途」段不含清单。影响：用户按指引找不到清单。修复：改为「完整选择见上方当前支持清单」。
2. **possible Duplicated Code** — `cli.py:31-33` vs `schema.py:96-101`：两处都从 `ContractName`/`ContractVersion` 派生展示文本。判断：格式不同（项目符号 vs「、」连接）且分属 CLI 展示层与错误消息层，弱重复，被模块解耦标准抑制，可不处理。
3. **possible Duplicated Code** — `tests/test_contract_schema.py:14-18` `_CONTRACT_CASES`：目录名字符串重复 `name.value`，可用 `name.value` 替代；name→model 关联表与 `_CONTRACTS` 注册表平行属测试独立 oracle 的刻意冗余，予以保留。
4. `scripts/check-offline:23-28`：四条 `run_check` 形状相同，shell 中显式列出可接受；仅第一条沿用泛名「冻结契约一致性」而新增三条带契约名，轻微不一致，可统一命名。

已核对且无问题：文档声明与实际快照哈希一致；decision-reasons schema 顶层 34 分支声明属实；文档引用函数均存在。工具已强制项（ruff/mypy strict：行宽、导入序、类型标注）跳过；`test_contract_schema.py:90` 的多余括号属琐碎风格，不上报。

## Spec

**结论：未发现问题。**

核对明细（子代理均实际执行验证）：

(a) 缺失/部分实现：无。仅一处边际观察（非缺陷）：验收标准 3 要求逐份验证「只读检查」；参数化真实 CLI 测试（`tests/test_contract_cli.py:97-174`）对四份契约都跑了 check 并验证成功与 content_drift，但 check 前后文件系统指纹断言只在 boundary 专属测试（test_contract_cli.py:360-502）中做。check 为单一共享代码路径，风险极低，可不处理；若要严格逐份，可在参数化测试中补 fingerprint 断言。

(b) 范围蔓延：无。无批量模式（cli.py:59-60、README、frozen-contracts.md 均明确排除）；export.py/check.py/snapshot.py 未动，既有导出保护直接复用，未复制成四套实现。

(c) 实现有误：无。逐条验收标准核对：

- AC1 受控选择：`ContractName` 恰四种（contracts/schema.py:33-39），未知名/非法版本/未实现组合均拒绝且有测试（test_contract_cli.py:177-209、530-551）。
- AC2 权威生成与组合约束：decision-reasons/v1/schema.json 顶层 anyOf 恰 34 分支、每分支 `additionalProperties: false`，与 `DECISION_REASON_DEFINITIONS`（screening/reasons.py:122-181）展开逐分支一致；四份 manifest 的 `schema_sha256` 与 schema.json 实际 sha256 相符；两次独立进程构建哈希一致（跨进程确定性）；`git diff HEAD^...HEAD -- contracts/screening/boundary/` 为空，boundary/v1 字节未改写，哈希仍是文档原值。
- AC3 真实 CLI 逐份验证：首次导出、同内容无操作、冲突拒绝、只读检查、跨进程确定性均有覆盖（见上边际观察）。
- AC4 边界说明：frozen-contracts.md 新增「JSON Schema 与上下文校验边界」节；四份快照 grep 禁止字段（confidence/enabled_topic_ids/excerpt_kinds 等）无命中，且有测试锁定（test_contract_schema.py:110-128）。
- AC5 中文说明与离线入口：README、CLI help、两文档均同步；check-offline:21-28 接入四份检查并实际运行 `contracts check` 四次全部 rc=0。
- OWNER comment：三份新契约名/目录/版本固定为 v1 并写入文档表格；快照只含字段与原因组合，主题启用、摘录引用等运行上下文未入快照。

## 小结

- Standards：1 条硬性违反 + 4 条判断性建议；最严重为 `tests/test_contract_cli.py:182/:549` 错误指引断言未随契约清单扩容同步。
- Spec：0 finding（a/b/c 三类均未发现问题），五条验收标准与 OWNER 澄清全部落实。

## 实施核实与处理结果

逐条复核后的处理如下：

1. **完整错误指引断言：采纳问题，不采纳原建议的动态期望值写法。** 两处旧断言
   确实只匹配 `boundary` 前缀，无法证明完整四项指引。测试现改用一份独立、完整的
   规格字面量，同时覆盖 export 与 check。没有从生产 `ContractName` 动态生成期望
   文本，避免测试由被测注册表自证。
2. **CLI「见当前用途」指引：采纳。** export/check 的 `--contract` 帮助统一改为
   「完整选择见上方当前支持清单」，并由真实安装入口测试锁定。
3. **CLI 展示文本与契约层错误文本的弱重复：不处理。** 两者格式与职责不同，分别
   属于 CLI 展示层和纯契约错误层；跨层提取会降低模块局部性。
4. **测试中的目录名字面量：不处理。** 该表是独立规格 oracle，刻意不从生产注册表
   派生期望目录；否则名称或映射同时出错时测试可能仍通过。
5. **离线检查首项名称不一致：采纳。** 第一项改为「研究边界冻结契约一致性」，与
   其余三项均明确展示被检查契约。
6. **逐契约只读检查文件指纹：采纳为测试强化。** 参数化真实 CLI 测试现在对四份
   契约分别记录 check 前后的完整文件系统指纹并断言不变，直接覆盖 AC3 的逐份只读
   要求。
7. **工具强制项与琐碎括号：不处理。** Ruff 与 mypy 已覆盖，且不影响行为或可读性。
