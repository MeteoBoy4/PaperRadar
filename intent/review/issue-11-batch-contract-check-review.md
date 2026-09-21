# Issue #11 整组契约检查审查（Standards / Spec 双轴）

- 固定点：`HEAD~2`（= e2a4541）
- 范围验证：`git log HEAD~2..HEAD --oneline` 恰好包含两笔目标提交：
  - `1f8e494 Implement batch contract checks (#11)`
  - `0d85837 Address batch check review findings (#11)`
- Diff 命令：`git diff HEAD~2...HEAD`（12 文件，+483/-81）
- 规格来源：GitHub Issue #11「A1-10：只读检查整组契约并逐项报告结果」正文（4 条 AC）+ 全部 comments（1 条三点补充）
- 标准来源：`AGENTS.md`、`CONTEXT.md`、`docs/agents/*.md`、`docs/contracts/*.md` + Fowler smell 基线
- 审查方式：Standards 与 Spec 两个独立子代理并行，仅聚合不混合排序；只读审查，未修改代码、未创建 commit、未触碰 Issue
- 验证证据：相关测试 75 项通过；全量离线测试 346 项通过；`scripts/check-offline` 通过；临时目录实测 CLI（混合失败、重复/空/未知选择、缺失目标）行为与规格一致

## Standards

成文标准对照（AGENTS.md 逐节核对）：**未发现硬性违规**。

- 单一权威 Schema：整组检查逐份复用 `check_frozen_contract` 单份判据（`src/paper_radar/contracts/check.py:233`），未建第二套逻辑；export 改由共享 `select_contracts` 统一选择校验，消除了原有重复。
- 只读与幂等（核心不变量）：check 路径无任何写入，测试以 `filesystem_fingerprint` 断言零写入；无网络/数据库/模型访问，`deny_external_io` 钩子保持离线。
- 面向用户行为：CLI help 与错误消息均为中文且给出可操作指引；`--help` 无网络/数据库副作用。
- 测试与文档同步：行为变化同步新增 `test_contract_check.py`、`test_contract_cli.py` 并更新 README、两份契约文档与 `scripts/check-offline`。
- 范围控制：批量 check 属本 ticket 既定交付，无规格外能力引入。

基线 smell 与文档一致性提示（均为判断性，非硬性违规）：

1. **文档/help 措辞与行为不一致（轻微）**
   - 位置：`src/paper_radar/cli.py:140` CHECK_HELP 称"四份均一致才返回 0"。
   - 依据：AGENTS.md「面向用户的行为」要求文本说明可操作的具体原因；`docs/contracts/frozen-contracts.md` 正确表述为"所有已选契约一致时返回 0"，且 check 允许任选 1–4 份。
   - 实际影响：部分选择时帮助文本误导退出条件。
   - 最小修复：改为"全部已选契约一致才返回 0"。
2. **Dead data / 同一语义两处消息源（Duplicated Code 倾向）**
   - 位置：`src/paper_radar/contracts/check.py:253` 通过项写入 `message_zh="冻结契约与当前权威定义一致。"`，但 `src/paper_radar/cli.py:203-207` `_write_check_item` 对 PASSED 弃用该字段、自行拼装含 SHA-256 的消息。
   - 实际影响：通过项的 `message_zh` 是死数据；同一语义存在两处消息源，未来易漂移。
   - 最小修复：CLI 直接使用 `message_zh`，或通过项不填该字段。
3. **Mysterious Name / 隐式假设（轻微）**
   - 位置：`src/paper_radar/contracts/check.py:219` 经 `contracts[0].version` 取规范版本，依赖"首元素必然存在"的隐式事实。
   - 实际影响：意图不明显；若 `select_contracts` 未来允许空集合将静默产生 `IndexError`。
   - 最小修复：`select_contracts` 直接返回解析后的 `ContractVersion`，调用方不再取首元素。
4. **硬编码示例与枚举并存（可维护性提示）**
   - 位置：`src/paper_radar/cli.py:36` `_CHECK_ALL_EXAMPLE` 硬编码四契约名，与枚举驱动的 `_CONTRACT_CHOICES_HELP`（`cli.py:41-43`）并存。
   - 实际影响：新增契约时示例会静默过时；但"显式列出完整集合"是 frozen-contracts.md 明文认可的设计，基线被部分压制。
   - 最小修复（可选）：由 `ContractName` 生成示例字符串。

## Spec

逐项核查（对照 Issue #11 四条 AC 与 comment 三点补充，并经真实 CLI 实测）：

- **AC-1 完整集合明确选择、复用单份检查、全过才返回 0**：重复 `--contract` 显式选择，无 `--all`；集合固定为 `ContractName` 受控枚举（`schema.py:148` `select_contracts`）；逐份复用 `check_frozen_contract`（`check.py:233`）；任一缺失/损坏/漂移/不可读经逐项捕获后以 exit 2 报告。
- **AC-2 逐项身份、结果与中文说明，未知选择执行前拒绝**：逐项输出固定 `ContractName` 声明顺序（实测乱序传参仍按声明顺序输出），机器可读字段 `contract/version/result/error_category` 齐全（`cli.py:210-214`）；未知/重复/空选择在读取任何快照前整体拒绝（`check.py:209-219`，实测 exit=2 且不创建目标目录）。
- **AC-3 只读、无网络/数据库/模型、不因缺失快照调用 export**：`check.py` 无任何 export 调用；测试以 `filesystem_fingerprint` 断言零写入；缺失快照仅产生 `missing` 类逐项失败。
- **AC-4 混合/全败/正常集合真实 CLI 验证、错误不泄露完整输入、文档同步、不依赖批量 export**：混合/全败/正常集合均有真实 CLI 测试（`tests/test_contract_cli.py`）且断言泄露标记不出现；三处同步完成（cli.py 三处 help、frozen-contracts.md、`scripts/check-offline` 改为一次整组 check，`test_cli_help.py` 有防回归断言）。
- **comment ①受控枚举与未知选择拒绝**：已落实（见 AC-1/AC-2），新增契约需显式扩展 `ContractName` 枚举，不会静默扩大检查范围。
- **comment ②固定顺序与机器可读字段、部分失败先报完再非零**：已落实；实测 1 损坏+1 缺失+2 通过全部报出后 exit=2。
- **comment ③三处同步、不新增第二套逻辑**：已落实；export 抽出共享 `select_contracts` 正是该要求的实现。

Findings：

(a) 规格要求但缺失或部分实现：**无**。

(b) 范围蔓延：**无**。export.py 的重构属 comment ③要求；screening-validation.md 的两句更新属文档同步，未引入新行为。

(c) 看似实现但实现错误：**无**。两处可接受的设计取舍，供知悉而非缺陷：

1. 批量存在失败时通过项也写入 stderr（`cli.py:219` 附近 `err=not result.passed`）；文档已说明"写入标准输出或标准错误"，语义自洽。
2. `message_zh` 为自由文本缀在 key=value 之后；机器解析应只取前四个字段，与 comment ②的字段清单一致。

## 汇总

- Standards 轴：0 硬性违规，4 个判断性提示（均轻微）；最重为 CHECK_HELP 退出条件措辞与部分选择行为不一致（`cli.py:140`）。
- Spec 轴：4 条 AC 与 comment 三点补充全部实现并有真实 CLI 测试与离线验证支撑；0 缺失、0 部分实现、0 错误实现、0 范围蔓延。

## 实施 Agent 复核与处置

逐条对照 Issue #11、公开批量检查接口、CLI 输出和显式集合边界后，处置如下：

1. **帮助中的退出条件措辞：采纳。** `check` 允许显式选择一至四份契约，因此
   “四份均一致才返回 0”确实会误导部分选择。现改为“全部已选契约一致才返回 0”，
   并更新真实安装入口的帮助测试锁定该表述。
2. **成功消息存在两处来源：采纳。** 批量结果中的 `message_zh` 现作为成功中文
   说明的唯一来源，CLI 直接复用它并追加契约身份、位置与 SHA-256；不再丢弃该字段
   后重新定义同一语义。公共接口测试同时固定成功消息。
3. **通过首元素取得版本的隐式假设：采纳问题，采用更小的修复。** 无需扩展
   `select_contracts` 的返回类型；批量检查现在直接遍历其返回的 `FrozenContract`，
   每项使用自身的受控名称与版本调用单份检查，删除 `contracts[0]` 假设。
4. **由 `ContractName` 动态生成整组示例：不采纳。** Issue #11 的 OWNER 补充明确
   要求未来新增契约时不得静默扩大“完整集合”。硬编码的四项示例与
   `scripts/check-offline` 共同固定当前集合边界；若以后加入契约，应显式评审并修改
   示例和离线入口，而不是让枚举扩容自动改变验收范围。

最终验证：相关帮助、检查 CLI、公共接口和导出回归测试共 `93 passed`；
`./scripts/check-offline` 的 lockfile、Ruff format、Ruff lint、mypy、全部 `346`
个离线测试及四份冻结契约整组检查全部通过。
