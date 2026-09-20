# Issue #5 修复提交的独立代码审查

- 固定点：`3912fe9 Address contract check review findings (#5)`
- 唯一审查范围：该提交引入的快照探测与 JSON 解析边界
- Spec：GitHub Issue #5 正文及评论；`docs/contracts/frozen-contracts.md` 的受控类别判据
- 审查报告由另一 Agent 提供，以下两条 finding 为原文转录

## 审查原文

1. **中：非权限类 OSError 被误报为缺失**

   - 位置：`src/paper_radar/contracts/snapshot.py:94`
   - 依据：文档要求区分缺失、不可读取和无效目标；错误应提供准确、可操作的原因。
   - 影响：ELOOP、EIO、ENOTDIR 等全部变成 ABSENT。已复现中间目录自循环符号链接
     被报告为 `missing_snapshot`，并错误建议执行 export。
   - 最小修复：只将 `FileNotFoundError` 映射为 ABSENT；ELOOP 映射为
     `invalid_target`，其他访问错误映射为 INACCESSIBLE。

2. **中：“超长整数”判据依赖 Python 全局配置**

   - 位置：`src/paper_radar/contracts/snapshot.py:117`
   - 依据：文档明确将超长整数归为 `damaged_snapshot`，契约检查应确定、可复现。
   - 影响：设置 `PYTHONINTMAXSTRDIGITS=0` 后，同一类 5000 位整数快照会变成
     `content_drift`。
   - 最小修复：提供自定义 `parse_int` 和固定长度上限，并增加禁用解释器限制时
     的测试。

## 实施代理复核与处理

复核方式：先按 finding 给出的反例独立复现，确认成立后再修改；每处修改都补公共
seam 回归测试并断言只读。

### Finding 1：非权限类 OSError 误报缺失 — 成立，采纳（含一处有意偏离）

复现：`target/screening` 为自循环符号链接或普通文件时，`os.lstat` 的 ELOOP /
ENOTDIR 都被旧探测归为 ABSENT，公开接口返回 `missing_snapshot`。

处理：

- `snapshot.py` 的显式探测改为：`FileNotFoundError` → `ABSENT`；
  `PermissionError` → `INACCESSIBLE`；`ELOOP` / `ENOTDIR` → 新增
  `SnapshotInspection.INVALID_PATH`；其余 `OSError` → `INACCESSIBLE`。
- `check` 将 `INVALID_PATH` 映射为 `invalid_target`，消息明确指出符号链接循环或
  非目录组件，不再建议运行 export。
- 偏离说明：审查建议把 ENOTDIR 归入 INACCESSIBLE。这里将 ELOOP 与 ENOTDIR 都
  归为 `invalid_target`，因为二者都是路径结构问题，正好对应文档对
  `invalid_target` 的既有定义；ENOTDIR 在导出侧对应既有“目标路径包含非目录项”
  受控错误，归为 invalid_target 不会改变该行为。
- `export` 把 `INVALID_PATH` 纳入“尝试创建”集合，让符号链接循环与非目录组件继续
  走既有写入错误路径，导出类别和消息与修复前逐字一致（既有 CLI 测试未改动）。

新增测试：中间目录自循环符号链接 → `invalid_target`；中间目录为普通文件 →
`invalid_target`；均断言非 missing 且文件系统不被改写。

### Finding 2：超长整数判据依赖解释器配置 — 成立，采纳

复现：构造一份内容自洽（规范编码、清单哈希匹配、身份正确）的 5000 位整数
schema，在 `PYTHONINTMAXSTRDIGITS=0` 下被判为 `content_drift`；默认限制下则在
解析阶段抛 `ValueError` 被判为 `damaged_snapshot`。同一文件因解释器配置得到不同
类别，确实违反“确定、可复现”。

处理：

- `snapshot.py` 增加固定上限 `_MAX_JSON_INTEGER_DIGITS = 100` 与
  `_parse_json_integer`：schema 与清单都通过 `parse_int` 使用它，超限直接
  `ValueError` → `damaged_snapshot`。
- 上限取 100 位而不是解释器默认的 4300 位：100 远低于 CPython 整数转换阈值的
  最小值 640，因此判定不依赖 `PYTHONINTMAXSTRDIGITS` 或
  `sys.set_int_max_str_digits` 的取值；契约 schema 本身只含个位整数。
- 文档 `damaged_snapshot` 行明确写出“固定上限 100 位”。

新增测试：模块级在 `sys.set_int_max_str_digits(0)` 下断言 `damaged_snapshot` 且
文件系统不变；真实 CLI 子进程以 `PYTHONINTMAXSTRDIGITS=0` 断言非零、
`damaged_snapshot`、无 traceback；边界用例固定 100 位 → `content_drift`、
101 位 → `damaged_snapshot`，防止上限被悄悄改动。

### 验证

- 相关契约测试 `test_contract_check.py`、`test_contract_cli.py`、
  `test_contract_export.py`：67 项通过。
- `./scripts/check-offline` 全部通过（lockfile、Ruff 格式、Ruff 静态、mypy strict、
  116 项 pytest、`contracts check`）。
- 真实 CLI 手工复核：中间目录自循环 → `invalid_target` 退出 2；
  `PYTHONINTMAXSTRDIGITS=0` 下的 5000 位整数 → `damaged_snapshot` 退出 2；
  两者均无 traceback。
- 未运行 live 验收。
