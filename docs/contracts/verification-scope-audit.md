# 固定 scope 开发审计

`./scripts/audit-verification-scope [--json] [--collect]` 是开发维护命令，不是正式
验收结果或 Frozen Contract。项目 Python 必须已通过 `uv run --offline --locked …`
准备；入口直接使用项目解释器，避免只读操作触发环境同步。

| 输出 | 含义 |
| --- | --- |
| `exit_code` | 0 登记匹配，1 有问题/无法核验；非法参数退出 2 |
| `files` | writer 消费的固定文件；`group`、`kind`、`role`、相对 `path`、登记和当前 SHA-256、受控 `reason` |
| `counts` | 各组固定 `expected_cases`；跨组同一模块计数冲突失败，不合并覆盖 |
| `issues` | 登记/图结构异常的组、scope 或 writer 位置、受控原因；不含原始数据 |
| `order` | scope 引用 DAG 的拓扑顺序；循环/自引用时为空 |
| `downstream` | 修改某个 scope 后需重算登记的传递下游，不是正式结论依赖 |
| `affected_groups` | 直接异常与 scope 修改传播可能影响的验收组 |
| `collection` | 默认 `not_requested`；显式收集返回模块节点计数及受控原因，`execution` 恒为 `not_run` |

`kind` 使用登记种类 test/source/fixture；`role` 将 source 中的 scripts/tests 路径
标为 support。fixture 包含固定向量，仍通过路径明确定位。文件原因仅为 ok、
hash_drift、missing_file、unreadable_file。非法路径或哈希不原样回显。

公开 Python 边界为 `audit_scopes(root, scopes)`、`load_scopes(root)` 和
`collect_counts(root, expected)`。`Scope` 表达显式组、scope 位置、绑定和固定计数；
它不建立新的 required 集合。`load_scopes` 正常导入生产 registry，随后静态解释
writer 导入的清单 AST。清单仅允许固定赋值、字面量、常量引用、tuple/list 展开与
dict 展开；重复赋值、重复计数 key、动态增补和未知表达式失败。额外测试清单导入
一并核对哈希；附加 scope 的源码、fixture、计数绑定明确拒绝，不能静默丢弃。
模块式导入仅允许访问明确元数据属性。新增 writer/scope
不必修改组列表，但改变导入命名约定或登记常量须同步审查解释契约与回归测试。

收集进程不执行测试体；测试模块和 conftest 导入仍执行普通 Python 收集代码，因此
只对仓库已审查的固定模块运行。返回的数量不能证明 skip 测试实际通过。任何审计
结果都不会更新 scope、分母、正式回执、历史证据或 Git 索引。
