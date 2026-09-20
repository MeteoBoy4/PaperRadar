# Issue #5 当前 HEAD 独立代码审查

- 固定点：`HEAD^`（`75d2c98114d08a37197577f40bdb055dc3ae5c5b`）
- 被审查提交：`f2ea9a97319053cb2d8b335e6e5c97d4a108c348`
- 唯一审查范围：`git diff HEAD^...HEAD`
- Spec：GitHub Issue #5 正文及全部评论（1 条）
- Standards：`AGENTS.md`、`CONTEXT.md`、`intent/draft.md`、`docs/agents/domain.md`，以及 `$code-review` smell baseline

## Standards

未发现问题。变更符合仓库关于模块边界、确定性逻辑与 I/O 分离、受控 enum、中文 CLI、冻结契约单一 Schema 权威和文档同步的要求；也未发现达到可操作阈值的 smell baseline 问题。

## Spec

1. **高：损坏快照可能绕过受控错误并输出 traceback**

   - 位置：`src/paper_radar/contracts/snapshot.py:97-106`
   - 依据：Issue #5 要求“损坏……返回非零”，并要求“错误显示契约身份和可操作中文说明，不输出未经验证的文件内容”。
   - 实际影响：`json.loads()` 接受含未配对代理项（例如 `"\ud800"`）的 JSON，但随后 `_canonical_json_bytes()` 会抛出未捕获的 `UnicodeEncodeError`；超长整数也可能在解析时抛出未捕获的 `ValueError`。真实 CLI 因而输出原始 traceback，而不是稳定的 `damaged_snapshot` 与中文操作指引。手工反例已复现该 traceback。
   - 最小修复：把 JSON 解析和规范序列化期间的输入异常统一映射为 `SnapshotInspection.DAMAGED`，同时严格拒绝 `NaN` / `Infinity`；增加真实 CLI 回归测试，并断言失败前后文件系统不变。

2. **中：目录权限问题被误报为快照缺失**

   - 位置：`src/paper_radar/contracts/snapshot.py:87-88`
   - 依据：Issue #5 评论明确要求“缺失/不可读取”分别作为独立受控类别；验收标准还要求外部集成测试覆盖权限问题。
   - 实际影响：当目标根目录存在但没有搜索权限时，`os.path.lexists(snapshot_dir)` 返回 `False`，实现将其归为 `ABSENT`，最终报告 `missing_snapshot` 并建议先运行 export。用户会收到错误的恢复指引；现有权限测试只撤销 `schema.json` 的读取权限，未覆盖目录搜索权限。手工反例已复现该误分类。
   - 最小修复：用能区分 `ENOENT` 与 `EACCES` 等错误的显式路径探测，将权限错误映射为 `unreadable_snapshot`（或文档既定的 `invalid_target`），并新增目录权限的真实 CLI 集成测试和只读断言。

未发现多契约汇总等范围蔓延；除上述两项外，未发现其他缺失、部分实现或错误实现。

## 验证记录

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -p no:cacheprovider tests/test_contract_check.py tests/test_contract_cli.py tests/test_cli_help.py tests/test_screening_architecture.py`：42 passed。
- 手工只读反例：含未配对代理项的 Schema 触发未捕获 `UnicodeEncodeError`；目标根目录移除搜索权限后返回 `missing_snapshot`。

汇总：Standards 0 个 finding（无最严重项）；Spec 2 个 finding，最严重项为损坏 JSON 可绕过受控错误并泄露 traceback。

## 实施代理复核与处理

复核方式：先独立复现两个反例，再决定是否采纳；只读脚本与真实 CLI 各跑一遍。
两个 finding 均成立，且复现时发现同一根因还覆盖第三种输入：`json.loads` 在约
10 万层嵌套时抛出 `RecursionError`，同样会穿透受控错误。

### 复现记录

- Finding 1：`b'{"x": "\ud800"}'` 使 `_canonical_json_bytes` 抛出 `UnicodeEncodeError`；
  `b'{"x": ' + b"1" * 5000 + b"}'` 在解析时抛出 `ValueError`；两者经真实
  `paper-radar contracts check` 都打印 traceback。另确认 `json.loads` 默认接受
  `NaN` / `Infinity`，以及 10 万层嵌套会触发 `RecursionError`。
- Finding 2：目标根目录或中间 `screening` 目录去掉搜索权限后，
  `os.path.lexists(snapshot_dir)` 返回 `False`，`check_frozen_contract` 报告
  `missing_snapshot`，恢复指引错误。

### 处理

| Finding | 结论 | 处理 |
| --- | --- | --- |
| 1 损坏 JSON 绕过受控错误 | 合理，采纳 | `snapshot.py` 把 JSON 解析与规范序列化合并进同一受控边界：`parse_constant` 拒绝 `NaN` / `Infinity` / `-Infinity`，`except (ValueError, RecursionError)` 统一返回 `damaged_snapshot`。新增模块级参数化用例（未配对代理项、超长整数、非标准常量、过深嵌套）、一份内容自洽的 NaN 用例、真实 CLI 用例（断言非零、`damaged_snapshot`、无 traceback、无 `UnicodeEncodeError`、文件系统不变），并在导出路径补一份回归用例。 |
| 2 目录权限误报缺失 | 合理，采纳 | `snapshot.py` 用显式 `os.lstat` 探测取代 `lexists`：`PermissionError` 返回新增的 `SnapshotInspection.INACCESSIBLE`，其余 `OSError` 保持“视为不存在”以维持导出既有受控写入错误。`check` 把 `INACCESSIBLE` 映射为 `unreadable_snapshot`；`export` 映射为 `write_failed`（`目标目录不可访问`）。新增模块级（根目录与中间目录）与真实 CLI（中间目录）集成用例，均断言消息含权限、文件系统前后不变。 |

### 复核中的边界

- 真实 CLI 对 `--target` 本身有 Click 的可读性预检：目标根目录整体不可读时退出
  2 并给出英文 `Invalid value for '--target'`，不会进入契约层；契约层的
  `unreadable_snapshot` 覆盖库调用方与中间目录权限拒绝。该预检是 Typer/Click
  既有行为，本票不修改。
- `SnapshotInspection.INACCESSIBLE` 只用于“无法确认快照存在性”的权限拒绝；
  快照目录本身可探测、文件读失败仍走既有 `unreadable` 状态，导出侧行为不变。

处理后运行：相关契约测试 61 项通过；`./scripts/check-offline` 全部通过
（lockfile、Ruff 格式、Ruff 静态、mypy strict、110 项 pytest、`contracts check`）。
未运行 live 验收。
