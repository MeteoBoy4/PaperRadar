# ica-advise：#2 批量导出用返回值表达部分失败（选 a）

日期：2026-09-22
状态：已决。
来源：架构审视报告（/tmp/architecture-review-20260922-114145.html）候选 #2；grilling Q2。前序：ica-advise-snapshot-verdict-seam.md（Q1）。

## 决策是什么

`export_frozen_contracts` 现在成功返回 tuple、部分失败抛 `ContractBatchExportError`（异常携带 completed / failures / selected_names / version），由 CLI 自己 join 并在 `cli.py:195-199` 发明"因批量停止而未尝试"的第三态。Q2 在三种收法中抉择：

- (a) 完全对称：批量导出永不因逐项失败抛异常，总返回 `ContractBatchExportResult`（含 `.passed`），仅选择无效仍抛；
- (b) 保留异常但携带完整 items；
- (c) 返回 result + 显式 `raise_for_failure()`。

**选定 (a)。** 与 `check_frozen_contracts` / `ContractBatchCheckResult` 同形：请求整体非法（选择无效）→ 异常；逐项结局（created / unchanged / failed / not_attempted）→ items。

## 为什么

- 调查确认 `ContractBatchExportError` / `export_frozen_contracts` 的消费者只有 `cli.py`、`tests/` 和 `contracts/__init__.py` 的 re-export；`scripts/` 不使用（a1_acceptance 用 check，offline_evidence 走 CLI 子进程）。项目为私有 0.1.0 单用户工具，无外部 Python 调用方，改法可随仓库一次性完成。
- check 侧已是同款形状且运行良好；(a) 是对齐先例而非发明。"契约 D 因批量在 C 停止而未尝试"作为 `not_attempted` outcome 第一次在模块内有一等表示，不再只能靠 stderr 字符串匹配观察（test_contract_cli.py:196-198）。
- (b) 保留双形状：CLI 仍要两条渲染路径，"部分成功靠异常携带成功结果"的反模式仍在，未解决 #2 的核心问题。
- (c) 是投机通用性：唯一真实调用方（CLI）必须完整渲染各项并按 `.passed` 给退出码 2，`raise_for_failure()` 将是死代码，还增加公共面与测试负担。
- 失败通道语义规则明确化：选择无效（请求整体非法，发生在触碰目标目录之前）→ 异常；逐项结果（含失败与未尝试）→ items。`.passed` 仅当全部 item 为 created / unchanged，对应文档"全部完成（含 unchanged）返回 0"。

附带约束：单份入口 `export_frozen_contract` 保持"成功返回一个结果、失败抛 `ContractExportError`"（与 `check_frozen_contract` 对称），从批量结果的对应 item 派生；CLI 输出与退出码逐字不变（含 not_attempted 的"批量导出已停止"指引文本）；删除 `ContractBatchExportError` 与 `ContractBatchExportFailure`；`contracts/__init__.py` 导出表同步；测试从断言异常改为断言 items / outcome。

## 是否改变外部行为

CLI 用户可见行为不变（输出文本、退出码 0/2、目录布局、快照字节）。变化仅在维护者侧 Python 接口：批量导出的逐项失败从异常通道改为返回值通道，并删除两个异常类型。该约定记录于 `docs/contracts/frozen-contracts.md`"受控结果与错误"，须同步更新（AGENTS.md 的文档联动要求）。无持久化、Schema、fingerprint 或校准语义变化。

## 是否需要 ADR

否。这是模块接口形状的重构，不偏离 `intent/draft.md`（:877 仅要求 `contracts/` 为权威 Schema 的冻结快照，不规定 Python API 的异常约定），不触碰领域不变量；文档同步即可，不构成需 ADR 记录的架构偏离。
