# 代码审查：Issue #5 只读检查一份冻结契约是否漂移

- 固定点：`75d2c98 Prevent contract help version drift (#4)`（其后无提交）
- 审查范围：`git diff 75d2c98` 加三个未跟踪新文件（`contracts/check.py`、
  `contracts/snapshot.py`、`tests/test_contract_check.py`）
- 规格来源：GitHub Issue #5 正文与唯一评论；父 Issue #1 的 A1 范围、Testing
  Decisions 与中文 CLI 契约
- 审查方式：只读两次分轴通读。**本 session 没有并行子代理能力，因此这是实现者
  自审，不是独立审查**；结论按下文 Standards / Spec 分轴记录，便于后续独立复核
- 验证（实际运行）：先跑 `tests/test_contract_check.py`、`tests/test_contract_cli.py`、
  `tests/test_cli_help.py`、`tests/test_contract_export.py`、`tests/test_contract_schema.py`，
  再跑 `./scripts/check-offline`；lockfile、Ruff 格式、Ruff 静态检查、mypy strict、
  98 项 pytest 与 `contracts check` 全部通过

## Standards

仓库没有 `CODING_STANDARDS.md`；标准来源为 `AGENTS.md`、`CONTEXT.md`、
`docs/agents/`、ADR 0006/0022 与既有代码模式。语义规则（受控类别、中文可操作
错误、只读、不泄露输入）均满足；无硬违规。

### (a) 违反仓库明文规范

无。Ruff、Ruff format、mypy strict 全绿；AGENTS.md 的“复用权威 Schema”“不建立
第二份字段定义”“错误不泄露内容”“公共 CLI 变更同步文档”“不无必要修改无关
文件”均有对应实现或测试。

### (b) Fowler 基线判断题

**J1 Duplicated Code（保留）** — `export.py:90` 与 `check.py:61` 各有一份
`_PATH_FAILURE_CATEGORIES`，把同一组 `SnapshotPathProblem` 映射到各自操作
的类别。
- 判断：不合并。两个枚举是各自公共错误词汇的一部分，显式映射让“路径问题如何
  翻译成导出/检查类别”一眼可见；合并需要在 `snapshot.py` 反向依赖操作层枚举，
  或依赖枚举值字符串相等。序列化值已被真实 CLI（`tests/test_contract_cli.py:198`）
  与检查公共接口（`tests/test_contract_check.py:210`）的用例钉住，不存在静默漂移风险。
- 严重度：低；判断题，不阻塞。

**J2 私有名跨模块导入（保留）** — `snapshot.py:11-16` 导入 `schema.py` 的
`_ManifestField`、`_MANIFEST_FORMAT_VERSION`、`_canonical_json_bytes`。
- 判断：不改名。下划线在本仓库表示 contracts 包内共享实现，不是模块私有；
  导出路径此前已这样使用。提升为公开名会扩大 `schema.py` 的公共面，收益仅是
  命名洁癖。
- 严重度：低；判断题，不阻塞。

**J3 Middle Man（不成立）** — `schema.py:95` 的 `build_selected_contract` 会把
`ContractName` / `ContractVersion` 校验与组合缺失统一翻译成受控选择错误，供
`export` 与 `check` 共同消费；它承载共享语义，不是纯转发。

**J4 测试环境假设（记录）** — 不可读取用例（`tests/test_contract_check.py:127`、
`tests/test_contract_cli.py:341`）依赖非 root 运行，与既有导出用例的 `chmod 0o500`
假设一致。单用户目标环境下可接受。

**J5 断言粒度（不成立）** — 错误测试只断言受控类别与可操作中文提示（如“权限”、
“新建版本”），帮助测试只断言必需段落与示例是否存在，未断言完整排版，符合
Issue 的可执行要求。

### 已评估未报

- `_snapshot_failure` 以 `(category, message)` 元组返回：只有一个调用方，拆成
  类型会增加噪音。
- `filesystem_fingerprint` 在无法读取文件时记录 `None`：这正是权限用例前后对比
  所需，不掩盖差异（mtime 与 mode 仍参与比较）。

## Spec

逐条验收结论：

- **AC1（显式选择、成功 0、失败非零）— 通过**：`cli.py:173` 注册 `contracts check`，
  三个选项均必选；一致返回 0 输出身份与 SHA-256；缺失、损坏、版本不一致、内容
  漂移、不可读取均以退出码 2 失败（`tests/test_contract_cli.py:270-378`）。
  类别优先级为 damaged → version_mismatch → content_drift，与导出判据一致。
- **AC2（复用权威规则、错误身份与中文、不输出文件内容）— 通过**：
  `snapshot.py:82` 复用 `contract.schema_bytes`（由 `BoundaryOutput.model_json_schema()`
  生成）与 `_canonical_json_bytes` 做逐字节比较，没有第二份字段定义；缺失、损坏、
  漂移、版本不一致、不可读取、路径失败的消息都包含 `契约 boundary v1` 身份与
  操作指引；隐私用例断言合成 secret 不出现在错误与 CLI 输出
  （`tests/test_contract_check.py:104`、`tests/test_contract_cli.py:361`）。
- **AC3（成功与全部失败路径只读）— 通过**：模块级与真实 CLI 级都用
  `filesystem_fingerprint` 对比 mtime、权限与内容；目标不存在时断言目录未被创建；
  路径逃逸用例断言目标外目录为空且符号链接保留；`deny_external_io` 子进程环境
  证明无网络/数据库访问，契约层不导入模型或 CLI（新增
  `tests/test_screening_architecture.py` 对 `contracts` 的边界检查）。
  `contracts check` 不写文件、不消耗模型配额。
- **AC4（中文帮助与外部集成测试）— 通过**：`CHECK_HELP`（`cli.py:99`）包含用途、
  参数、副作用、配额、输出去向、常见失败与可复制示例；`tests/test_cli_help.py`
  把 check 纳入三级帮助参数化与受控选择清单断言；集成测试覆盖人为篡改、缺失
  （整目录/单文件）、权限与不可读，断言非零、受控类别、无 traceback。
- **AC5（接入完整离线入口并更新说明）— 通过**：`scripts/check-offline:21` 在全部
  测试后实际运行 `contracts check --contract boundary --version v1 --target
  contracts`；README 与 `docs/contracts/frozen-contracts.md` 已把“只读 check 尚未
  实现”改为已交付并列出完整类别表；本票没有目录遍历或多契约汇总。

### (a) 缺失/部分实现

无。

### (b) 范围蔓延

无。`export.py` 的重构是为了让导出与检查共用同一份只读判据（Issue 评论明确
要求复用清单哈希判据），不是新增能力；架构测试扩展只保护新增层的纯度。未实现
批量导出、汇总检查或任何后续 ticket。

### (c) 实现有误

无发现。已核对：字节级比较先于身份判断与漂移判断；`ABSENT` 与 `INCOMPLETE`
都归入缺失且不创建目录；`UNREADABLE` 与 `DAMAGED` 分流；`version_mismatch`
要求快照内部自洽；CLI 退出码与导出一致。

### 已知边界（记录）

- 中间目录权限拒绝（例如 `target/screening` 不可遍历）会让 `os.path.lexists`
  返回 False，因而报告 `missing_snapshot` 而不是 `unreadable_snapshot`。这与
  评论③“目标根目录缺失时直接报缺失”一致，消息仍要求核对 `--target`；文件本身
  不可读时才报告 `unreadable_snapshot`。检测遍历期 EACCES 需要额外探测，本票
  不做。
- 审查中发现一处文档不准确：路径规则只写了导出会拒绝逃逸，未写 check 也拒绝；
  已在本次处理中修正。

## 小结

- Standards 轴：0 项硬违规；2 项判断题（J1、J2）经复核保留并给出理由；1 项环境
  假设（J4）记录；无 Middle Man 或断言粒度问题。
- Spec 轴：5 条 AC 全部通过；无缺失、无范围蔓延、无错误实现；1 处文档修正、1 条
  已知边界记录。
- 两轴均不构成 Issue #5 验收阻塞。

## 实施代理复核与处理

| Finding | 结论 | 处理 |
| --- | --- | --- |
| J1 路径类别映射重复 | 保留 | 显式映射保持两份公共词汇独立，序列化值已由 CLI 测试钉住；合并会引入反向依赖。 |
| J2 跨模块私有导入 | 保留 | 下划线表示 contracts 包内共享实现，与既有导出路径一致；不扩大 schema 公共面。 |
| J4 权限用例依赖非 root | 记录 | 与既有导出权限测试同一环境假设；单用户目标环境可接受。 |
| 文档路径规则未提 check | 合理，采纳 | `docs/contracts/frozen-contracts.md` 路径小节改为说明导出与 check 都拒绝逃逸路径。 |
| 中间目录 EACCES 归为缺失 | 记录为已知边界 | 与评论③一致；消息仍要求核对目标路径，文件级不可读单独报告。 |
