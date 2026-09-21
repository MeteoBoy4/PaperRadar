# Issue #10 批量契约导出审查（Standards / Spec 双轴）

- 固定点：`HEAD~2`（= 8283c0c）
- 范围验证：`git log HEAD~2..HEAD --oneline` 恰好包含两笔目标提交：
  - `258ba15 Implement recoverable batch contract export (#10)`
  - `cfc33f3 Address batch export review findings (#10)`
- Diff 命令：`git diff HEAD~2...HEAD`（8 文件，+579/-68）
- 规格来源：GitHub Issue #10「A1-09：批量导出时预检冲突并恢复中断」正文 + 全部 comments（1 条补充边界）
- 标准来源：`AGENTS.md`、`CONTEXT.md`、`docs/agents/domain.md` + Fowler smell 基线
- 审查方式：Standards 与 Spec 两个独立子代理并行，仅聚合不混合排序

## Standards

成文标准对照（AGENTS.md 逐节核对）：**未发现硬性违规**。

- 幂等（核心不变量）：重跑不改写完整项，`test_real_cli_batch_export_uses_declaration_order_and_repeat_is_noop` 验证 mtime 不变。
- 原子性（编码流程）：发布期允许部分成功，但各快照相互独立，README 与 `docs/contracts/frozen-contracts.md` 明确披露"不承诺跨快照事务"并给出恢复路径，属合规披露。
- 受控词汇：新增 `ContractBatchExportFailure` 复用 `ContractExportErrorCategory`，失败类别未扩散。
- 测试同步：批量顺序、中断恢复、预检三态、非法选择、不可写目标均有回归测试；`deny_external_io` 钩子保持离线。
- 文档维护：README、`frozen-contracts.md`、CLI help 三处口径一致（导出批量/检查逐份、返回 0/2、声明顺序与 `ContractName` enum 一致）。
- 面向用户行为：help 与错误消息均为中文且给出可操作指引；`--help` 无网络/数据库副作用。

基线 smell（判断性提示，非硬性违规）：

1. **Duplicated Code（两处平行实现同一导出流程）**
   - 位置：`src/paper_radar/contracts/export.py:269-286`（`export_frozen_contract`）对照 `:229-255`、`:302-318`；其中 `ContractSelectionError` → `INVALID_SELECTION` 的包装块（`:276-280` 对 `:242-247`）逐字重复。
   - 实际影响：同一语义的维护点翻倍；cfc33f3 已证明只改批量一侧的 completed 簿记，单份入口易漂移。
   - 最小修复：单份入口改为 `export_frozen_contracts((name,), version, target)` 的薄封装（批量失败时对单份解包 `ContractBatchExportError` 以保持原异常类型与 CLI 输出），或至少提取共享的选择包装辅助函数。
2. **Duplicated Code（UNCHANGED 结果构造两次）**
   - 位置：`export.py:315-318`（预检期 `unchanged` 列表）与 `:330-333`（发布期 MATCHED 分支重建相同 `_successful_result`）。
   - 实际影响：同一对象构造两次；cfc33f3 的 `completed_by_name` 合并正是为缝合这两个来源而引入的复杂度。
   - 最小修复：预检期建立 `results_by_name` 映射，发布期直接复用，删除 `unchanged` 独立列表。
3. **健壮性提示（非 smell 基线，供参考）**
   - 位置：`export.py:91`，`ContractBatchExportError.__init__` 直接取 `failures[0]`，空元组不变量仅靠两个调用点维持。
   - 最小修复：构造时加断言或校验非空。

## Spec

逐项核查（对照 Issue #10 五条 AC 与 comment 四条边界）：

- 批量选择形态：`--contract` 改为可重复 `list[str]`（`cli.py:190`）；`_select_contracts` 按 `ContractName` 声明顺序重排（`export.py:255`），乱序参数输出位置递增（`test_contract_cli.py:129-131`），可复现。符合 comment #1。
- 预检覆盖：内容漂移/版本不一致/损坏/路径非法/非法选择全部在预检或选择解析阶段拦截；预检循环纯只读（`export.py:302-318`），有失败即在任何写入前抛出（`:320-326`），`filesystem_fingerprint` 断言零写入，非法选择连目标目录都不创建。符合 AC-1 与 comment #3。
- `unchanged` 语义：MATCHED 计入成功结果，重跑 exit 0 且 mtime 不变；冲突/写失败经 `ContractBatchExportError` → exit 2；逐份"已创建/未改写/未完成"标注齐全（`cli.py:168-185`）。符合 comment #2。
- 中途失败：staging+rename+finally 清理（`export.py:175-194`），测试断言失败项目录为空（无半文件）、完整项保留、exit 2 不伪装成功。符合 AC-2。
- 故障注入真实性：真实子进程跑安装入口，sitecustomize 钩子 `os.replace` 计数注入 `InterruptedError`；五场景（前置冲突三态、目录不可写 0o500、中途失败、重跑补齐、四份 sha256 对权威定义）均真实注入并断言秘密不外泄。实测 33 个测试全部通过。符合 AC-3、AC-4。
- 文档/帮助：CONTRACTS_HELP、EXPORT_HELP、README、frozen-contracts.md 均已改写批量语义，写明部分完成含义、原命令重跑方法、零配额。符合 AC-5 与 comment 文档要求。
- `contracts check` 保持单份：diff 未触碰 check 命令，文档明确"批量 check 尚未实现"。符合 comment #4。

Findings：

(a) 规格要求但缺失：**无**。

(b) 范围蔓延（轻微，两处）：

1. `src/paper_radar/contracts/export.py:104-120` — 依据：AC 仅要求"在 export 中提供清晰的批量选择"，未要求改动单份导出行为。实际：`INVALID_PATH`（lstat 遇 ELOOP/ENOTDIR）从"交给写入路径"改为预检即抛 `INVALID_TARGET` 且换新消息，`export_frozen_contract` 单份行为随之变化。影响：既有调用方观察到的错误类别/消息改变（无既有测试钉住旧行为，未破测试）。最小修复：无需回退；建议在 frozen-contracts.md 的受控错误表中明确此变化属本 ticket 引入。
2. `export.py:248-252` — 重复 `--contract` 拒绝为 `invalid_selection`；comment #1 只说"可重复"，未定义重复语义。属合理最小解释且帮助已写明"每份至多一次"。仅作记录。

(c) 看似实现但错误：**无功能性错误**。一处措辞级偏差供参考：发布失败时，排在失败项之后但预检已 MATCHED 的项报告"未改写"而非文档句"尚未处理的项报告未完成"的字面（`test_contract_cli.py` 中 reuse-assessment 断言已钉死此行为）；因 unchanged 属成功且该项快照此前已完整发布，语义自洽，可不修。

## 汇总

- Standards 轴：0 硬性违规，2 个判断性 Duplicated Code 提示；最重为单份/批量双实现平行维护（`export.py:269-286` 对 `:289-339`）。
- Spec 轴：五条 AC 全部实现且有真实故障注入测试支撑，comment 四条边界全部落实；0 缺失、0 错误实现，仅 2 处轻微范围观察；最重为单份导出 `INVALID_PATH` 错误类别随本 ticket 静默变化（`export.py:117-120`）。

## 实施 Agent 复核与处置

逐条对照 Issue #10、公开 Python 接口、真实 CLI 测试和磁盘行为后，处置如下：

1. **单份/批量导出流程重复：合理，已改进。**
   `export_frozen_contract` 现在委托 `export_frozen_contracts((name,), ...)`，并把单份
   运行中的 `ContractBatchExportError` 解包为既有 `ContractExportError`，保留原有
   单份调用方可观察的错误类型、类别和中文消息。选择、预检、发布和恢复只剩一条
   权威流程。
2. **`UNCHANGED` 结果重复构造：合理，已改进。**
   批量导出改为单一 `results_by_name` 结果账本。预检已匹配项只构造一次；发布成功
   直接补入同一账本；成功返回和失败时的 `completed` 都通过声明顺序投影该账本，
   删除了两份 `unchanged` 列表及事后合并逻辑。
3. **批量异常依赖非空 `failures` 的隐式不变量：合理，已改进。**
   `ContractBatchExportError` 构造时显式拒绝空失败集合并给出受控 `ValueError`；新增
   公开接口回归测试，确认不会泄漏无语义的 `IndexError`。
4. **单份 `INVALID_PATH` 行为变化：无需回退，文档已补强。**
   批量预检必须在写入前识别非目录组件和符号链接循环；单份入口复用同一权威流程
   后也获得相同的提前失败语义。该行为仍属于既有 `invalid_target` 受控类别，现已在
   `docs/contracts/frozen-contracts.md` 的错误表中明确其判据和预检处置方式。
5. **重复 `--contract` 拒绝：合理解释，不改代码。**
   “可重复选项”表示可多次选择不同契约，不表示同一契约应重复执行。拒绝重复值可
   避免同一快照产生两条相互矛盾的逐份状态；CLI 帮助与文档已经明确“每份至多一次”。
6. **后序 matched 项的状态措辞：代码正确，文档已校正。**
   `unchanged` 是成功状态；预检已确认一致的快照并非“尚未完成”，不应因更早的新
   快照写入失败而降格。README 和冻结契约文档现明确区分预先一致项、故障前新建项、
   失败项和尚未发布的缺失项。

处置没有扩展批量 `check`、验收证据或后续 ticket 能力。

最终验证：

- 相关导出、CLI 与帮助测试：`56 passed`；
- `./scripts/check-offline`：lockfile、Ruff format、Ruff lint、mypy、全部 `338`
  个离线测试及四份冻结契约一致性检查全部通过。
