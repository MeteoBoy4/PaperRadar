# 固定 scope 开发审计

## 用途与范围

`./scripts/audit-verification-scope [--json] [--collect]` 是固定验收登记的开发维护
命令，不是正式验收结果或 Frozen Contract。它核对 writer 消费的显式材料、固定
计数及 scope 引用图，不扩展 required 集合。

项目 Python 必须已通过 `uv run --offline --locked …` 准备。入口使用
`${UV_PROJECT_ENVIRONMENT-.venv}/bin/python`；相对环境路径以仓库根为准，不依赖
调用方 cwd，不启动 uv 或同步环境，也不生成字节码。解释器不可用时向 stderr
给出中文准备指引并退出 1，不输出审计报告。

## 规则

### 命令与输出

默认向 stdout 输出中文文本，不收集测试；`--json` 改为输出完整 JSON 对象，
`--collect` 显式启用独立 pytest 收集，两者可组合。`-h` / `--help` 只打印帮助并
退出 0，不加载登记或收集测试。CLI 不接受路径、组、writer 或任意 pytest 参数。

| 输出 | 含义 |
| --- | --- |
| `exit_code` | 0 登记匹配，1 有问题/无法核验；非法参数退出 2 |
| `files` | writer 消费的固定文件；`group`、`kind`、`role`、仓库相对 `path`、`expected_sha256`、`actual_sha256`（不可读时为 `null`）、受控 `reason` |
| `counts` | 各组固定 `expected_cases`；跨组同一模块计数冲突失败，不合并覆盖 |
| `issues` | 登记/图结构异常的组、scope 或 writer 位置、受控原因；不含原始数据 |
| `order` | scope 引用 DAG 的拓扑顺序；循环/自引用时为空 |
| `downstream` | 修改某个 scope 后需重算登记的传递下游，不是正式结论依赖 |
| `affected_groups` | 直接异常与 scope 修改传播可能影响的验收组；收集超时/失败不推断所有模块漂移 |
| `collection` | `reason`、`execution`、`modules`；默认 `not_requested`、`not_run`、`{}`；显式收集返回模块节点计数，读取到完整计数结果时另含非负整数 `collection_skipped`、`deselected`；`execution` 恒为 `not_run` |

`kind` 使用登记种类 test/source/fixture；`role` 将 source 中的 scripts/tests 路径
标为 support。fixture 包含固定向量，仍通过路径明确定位。文件原因仅为 ok、
hash_drift、missing_file、unreadable_file。非法路径或哈希不原样回显。

### Python 接口与登记接收

公开 Python 边界为 `audit_scopes(root, scopes)`、`load_scopes(root, *, writers=None)`、
`collect_counts(root, expected, *, timeout=120)`，以及确定性的
`collection_targets(report)` 和 `merge_collection(report, scopes, collection)`。
`collection_targets` 返回模块路径到预期分母或 `None` 的映射；不可收集或无目标时
返回整体 `None`。
`root` 为 `Path`；`scopes` 为 `tuple[Scope, ...]`；`expected` 是模块路径到严格正整数
或 `None` 的映射；`timeout` 为收集子进程的秒数上限。审计返回 `AuditReport`，收集
返回 `CollectionResult`；合并返回新报告，不改写原报告。
`writers` 仅供显式合成登记或独立目录审计
使用，不暴露 CLI 覆盖入口；默认始终读取生产 `acceptance_groups()`。
`Scope` 表达显式组、scope 位置、原始绑定和固定计数；
它不建立新的 required 集合。`load_scopes` 正常导入生产 registry，随后静态解释
writer 导入的清单 AST。清单仅允许固定赋值、字面量、常量引用、tuple/list 展开与
dict 展开；重复赋值、重复计数 key、动态增补和未知表达式失败。额外测试清单导入
一并核对哈希；附加 scope 的源码、fixture、计数绑定明确拒绝，不能静默丢弃。
模块式导入仅允许访问明确元数据属性。在生产 `acceptance_groups()` 登记新的
writer/scope 时，不必另维护审计组列表；改变导入命名约定或登记常量须同步审查
解释契约与回归测试。

`AuditReason`、`FileKind`、`FileRole` 约束受控值，输出记录使用 `TypedDict`。
`Scope.bindings`/`counts` 保留原始 `object` 输入，以便审计非法登记而非假设其已合法；
`parse_file_bindings` 和严格正整数校验是接收边界。每种文件绑定是由
`(path, sha256)` 二元 tuple 组成的 tuple；哈希须为 64 位小写十六进制。路径须为
非空、可打印的规范 POSIX 仓库相对路径，不含空段、`.`、`..`、反斜杠或 `::`；
解析后指向仓库外的链接记为不可读。计数若提供，须为 dict，key 集合须与该组测试
清单相同，值须为大于 0 的严格整数（bool 不合法）。测试清单只有 `bindings[test]`
一份，不另存计数测试清单。

默认登记包括生产 registry 中的可选组。writer 的主 scope 由唯一一个未改名导入的
`REQUIRED_TEST_MODULES` 确定；绑定常量为 `REQUIRED_TEST_MODULES`、
`REQUIRED_SOURCE_MODULES`、`REQUIRED_FIXTURE_FILES`，计数常量为
`REQUIRED_TEST_CASE_COUNTS`。主 scope 声明这些常量时，writer 必须显式消费它们。
固定清单表达式也支持负整数字面量，但非正计数仍被接收校验拒绝。允许的元数据
属性以[登记解释器的 `METADATA`](../../scripts/verification_scope_registry.py)为准。

### 显式收集

显式 `--collect` 在文件哈希漂移或计数 key/分母错误时仍可收集已明确列入测试清单的
模块。每个模块没有唯一合法预期分母时以 `None` 传给收集接口，仅返回诊断计数；
不会写成新分母。额外计数 key 不会扩展测试集合；缺失/不可读材料（含指向仓库外的链接）、
未知登记形式、非法绑定或引用图错误仍阻止
收集。原审计失败不会因收集成功变为通过。收集超时、不可用、失败、skip、deselect
保留原 `affected_groups`；只有完整 `count_mismatch` 才追加可定位的组及其下游，
同时保留已有影响。参数错误仅输出受控类别与中文说明，不回显原始参数。

收集子进程清除 `PAPER_RADAR_TEST_RECEIPT`、`PAPER_RADAR_TEST_RUN_ID`、
`PYTEST_ADDOPTS`、`PYTEST_PLUGINS`，关闭第三方插件自动加载、字节码、pytest 缓存
与正式回执插件，并清空 pytest 配置的 addopts。只在 `/tmp` 的独立临时目录传递
受控计数，退出后清理；原始 stdout/stderr 丢弃，不保存或回显。

收集进程不执行测试体；参数化按完整节点计数，函数级 skip 标记仍算收集节点，
模块级 skip 与 deselect 单列且不能通过。生产 registry 的正常导入、测试模块和
conftest 导入仍执行普通 Python 代码，静态清单解释与收集隔离不是 Python 沙箱，
因此只对已审查的仓库登记和固定模块运行。

## 错误与拒绝

JSON 的 `reason` 使用 `AuditReason` 的受控值；失败不回显文件内容、原始异常或
原始非法参数。文件级原因见上文；其余类别如下：

| 类别 | 原因 |
| --- | --- |
| 登记集合与绑定 | `empty_registry`、`duplicate_scope`、`empty_binding`、`invalid_binding`、`duplicate_path` |
| 引用图 | `self_reference`、`cycle` |
| 固定计数 | `invalid_counts`、`count_keys_mismatch`、`invalid_count`、`conflicting_counts` |
| 登记加载与解释 | `registration_unavailable`、`invalid_registration`、`unsupported_registration`、`duplicate_registration`、`duplicate_count_key`、`unsupported_scope_import`、`unsupported_writer_scope`、`unsupported_scope_constant`、`unconsumed_registration`、`unsupported_secondary_binding`、`writer_unavailable`、`registry_unavailable` |
| 收集 | `not_requested`、`audit_failed`（审计阻止收集或无可收集目标）、`collection_unavailable`、`collection_timeout`、`collection_failed`、`collection_skipped`、`collection_deselected`、`count_mismatch`；成功为 `ok`，直接调用时非法预期映射返回 `invalid_counts` |
| 参数（stderr，退出 2） | `unknown_argument`、`invalid_option_value`、`invalid_arguments` |

登记漂移或无法核验时退出 1；先审查具体原因和候选哈希，按 `order` 人工核对并
修改登记后重跑。循环、自引用或登记解释失败须先修复，不能凭候选哈希跳过。
工具不自动修复、重绑或重试；正式验收与历史状态查询使用各自入口。

## 不提供／不证明

任何审计结果都不更新 scope、分母、正式回执、历史证据或 Git 索引，不执行迁移、
模型调用或测试体，也不以扫描未登记文件扩展范围。审计匹配和收集数量不证明测试
实际通过、完整阶段 A 完成或 live 就绪；本命令不发布正式结论，不加入正式六项
检查。阶段 A 收口与最终聚合的承接责任见[路线图 A](../roadmap.md#module-a)和
[路线图 I](../roadmap.md#module-i)。

## 相关

- 依据：[#60](https://github.com/MeteoBoy4/PaperRadar/issues/60)（开发维护命令）、[规格 §11](../../intent/draft.md#十一九阶段实施与验收)、[ADR-0031](../adr/0031-screening-budget-and-derived-applicability.md)（固定材料、同次身份与离线证明边界）。
- 实现：[命令入口](../../scripts/audit-verification-scope)、[CLI](../../scripts/audit_verification_scope.py)、[审计与报告类型](../../scripts/verification_scope_audit.py)、[登记解释](../../scripts/verification_scope_registry.py)、[独立收集](../../scripts/verification_scope_collection.py)。
- 正式结论的查询边界见[verification-status](verification-status.md)；固定登记维护与历史证据见[离线验证证据](../verification/offline-evidence.md#固定-scope-维护审计60)。
