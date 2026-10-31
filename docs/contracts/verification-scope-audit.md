# 固定 scope 开发审计

## 用途与范围

`./scripts/audit-verification-scope [--json] [--collect] [--base COMMIT --integration-target BRANCH] [--confirmations FILE]` 是固定验收登记的开发维护
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
退出 0，不加载登记或收集测试。CLI 仅接受审计选项与工作树外的确认文件路径，不接受组、writer 或任意 pytest 参数。

| 输出 | 含义 |
| --- | --- |
| `exit_code` | 0 登记匹配，1 有问题/无法核验；非法参数退出 2 |
| `files` | writer 消费的固定文件；`group`、`kind`、`role`、仓库相对 `path`、`expected_sha256`、`actual_sha256`（不可读时为 `null`）、受控 `reason` |
| `counts` | 各组固定 `expected_cases`；跨组同一模块计数冲突失败，不合并覆盖 |
| `issues` | 登记/图结构异常的组、scope 或 writer 位置、受控原因；不含原始数据 |
| `order` | scope 引用 DAG 的拓扑顺序；循环/自引用时为空 |
| `downstream` | 修改某个 scope 后受影响的传递下游，不是正式结论依赖 |
| `affected_groups` | 直接异常与 scope 修改传播可能影响的验收组；收集超时/失败不推断所有模块漂移 |
| `collection` | `reason`、`execution`、`modules`；默认 `not_requested`、`not_run`、`{}`；显式收集返回模块节点计数，读取到完整计数结果时另含非负整数 `collection_skipped`、`deselected`；`execution` 恒为 `not_run` |

`kind` 使用登记种类 test/source/fixture；`role` 将 source 中的 scripts/tests 路径
标为 support。fixture 包含固定向量，仍通过路径明确定位。文件原因仅为 ok、
hash_drift、missing_file、unreadable_file、live_document_binding。非法路径或哈希不原样回显。

### 活文档防回绑与链接

现行登记已移除规格、README、GLOSSARY 与现状 Contract 的 19 条整文件绑定。
冻结依据继续由 history、需求/覆盖台账、最小冻结摘录、ADR、Schema 及代码/测试/fixture/依赖身份承担；
[迁移台账](../verification/scope-document-migration.md)记录旧 SHA、替代依据及固定分母。
跨两个及以上组实际登记的共享材料采用单处中央哈希，各组仍维护显式成员、用途与固定计数；
仅属一组的材料可保留字面量。scope 不进入逐文件哈希，原 41 条边由显式证明引用保留。
精确母集、41 与旧描述 42 的差异见[迁移台账](../verification/scope-shared-dag-delivery.md)。
显式基线分析遵循下节规则。

审计从仓库的
[`scope-material-inventory.json`](../verification/scope-material-inventory.json)
读取唯一分类事实 `classification_rules.live_documents.exact_paths`，对规范仓库相对路径
逐项精确匹配。任何组的 test/source/fixture 清单再次登记其中路径，文件原因均为
`live_document_binding`，审计失败且不进入测试收集。未知路径继续核对固定字节，
不因目录或扩展名自动豁免；分类新增或改类须显式审阅。

Python 接口对仓库副本读取副本自己的分类数据；纯合成材料目录没有分类文件、
项目配置或 Git 仓库标志时，使用当前审计实现所属仓库的同一份规则。
仅复制审计脚本、连实现目录也没有项目/Git/分类材料的纯合成支撑，保留无分类的
合成审计语义，不声明生产活文档分类事实。
分类无法读取、非法 JSON、缺少字段、空清单、重复或非法路径均受控拒绝，
不回显原始内容，也不在完整仓库缺失分类时回退宿主规则。

普通 pytest 的[链接检查](../../tests/test_live_document_links.py)只读取上述已分类活文档
中的相对 Markdown 链接，检查指向 `docs/verification/`、`verification-runs/`、
`intent/review/` 以及清查明确列出的证据、history、coverage/台账路径是否存在。
断链报告源文档、行号与目标；外部 URL、纯锚点、其他目标及未分类文档不在范围内。
它不访问网络、不检查锚点或链接语义，也不新增验收组。目标字节仍由固定材料审计负责。

修改活文档可同时保持审计通过、scope 字节不变和 A8–A10 writer 没有 `scope_drift`。
活文档仍参与完整工作树身份，因此旧 run 的历史状态保持，当前适用性变为
`applicability=different`，不能把审计通过视为旧结论适用于新树。

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
`Scope` 表达显式组、scope 位置、原始绑定、固定计数和原始 `references`；
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

### 共享材料中央引用

[`scripts/verification_scope_materials.py`](../../scripts/verification_scope_materials.py)
只声明非空 `SHARED_MATERIALS` 字典：规范材料相对路径映射到 64 位小写 SHA。
它只包含文档字符串与这一项固定赋值，不导入其他模块、不调用函数。
scope 使用唯一、未改名的 `from scripts.verification_scope_materials import SHARED_MATERIALS`，
并在显式成员位置使用 `("scripts/check-offline", SHARED_MATERIALS["scripts/check-offline"])`。
旧字面量与中央引用可以在同一个 tuple 中共存，scope 运行时导出及静态解释结果均为原有 `(path, sha)` tuple。

全部中央条目先作结构校验；缺失、非法路径/SHA、重复 key、循环别名、动态表达式、
未知引用、改名导入及与中央条目冲突的旧字面量均拒绝。同组重复成员不按同 SHA 去重。
`Scope.bindings` 继续接收原始 object，非法结构和 replace 注入负例仍由审计报告。
writer、scope 与中央 AST 只接受规范仓库位置的普通文件，不允许链接重定向
（包括指向根内 ignored 目标），循环或不可读登记受控拒绝；普通固定材料的软链规则不变。中央文件自身禁止加入各组整文件哈希，字节仍进入完整工作树身份；审计与 writer
核对展开后的真实材料字节，中央声明本身不能证明材料匹配。

中央登记覆盖全部实际跨组共享材料，包括业务源码、固定测试、支撑、fixture 和证据；
同一路径在不同组的 kind/role 独立保留，任一测试或 fixture 用途仍为敏感变化。
各路径与逐组成员详见[迁移台账](../verification/scope-shared-dag-delivery.md)。

### scope 显式证明引用

主 scope 可声明 `REQUIRED_SCOPE_REFERENCES = ("scripts/a1_scope.py", ...)`。
静态解释器把它保留为 `Scope.references`；只接受 tuple、规范相对路径和本次登记中实际 scope 路径，
重复、自引用、未知引用和循环均受控拒绝。`load_scopes` 附带本次已解析的 scope 路径上下文，
单组审计允许已解析的外部引用，仅对传入节点建局部图。每条边方向为被引用 scope 到消费组，
保留拓扑与 downstream；这与正式 acceptance group dependencies 不同。
兼容的 `replace(scope, bindings=...)` 注入 scope 路径仍参与同一图的 self/cycle 检查。
生产 scope 不再作为材料哈希，完整入口与回执仍消费展开后的原 tuple 清单和固定计数。

A8 冻结能力台账中的 scope 指针只接受当前组经结构审计通过的显式引用；
普通代码、fixture 与其他证据继续核对固定 SHA，未列指针继续拒绝。
scope 和中央数据的完整字节仍参与工作树身份，结构与同次前置检查保护登记语义。
显式引用变化纳入基线 entry 摘要并归为敏感 registration；影响范围取旧图与新图的并集，
要求每个受影响组确认，不产生下游 scope 的机械 SHA 更新。

### 显式基线与分级确认

`--base COMMIT` 与 `--integration-target BRANCH` 必须同时提供。base 解析为明确提交，
必须是当前 HEAD 的祖先，并等于声明的本地 `refs/heads/BRANCH`（也接受完整本地分支名）
当前提交。目标分支前移后旧 base 被拒绝；不隐式 fetch、不修改 refs 或索引。
base 是本轮比较起点，target 是核实其新鲜度的本地分支，不表示该分支已包含本轮实施。
例如分阶段实施可显式以稳定本地 main 为 target/base；尚在 integration 上的子票漂移
仍是本轮待审内容，不能声称已处理。

公开接口 `audit_baseline(root, *, base, integration_target, confirmations=(), writers=None)`
读取当前树和 base 自己的登记、分类规则。历史树仅由 `git ls-tree` / `git cat-file --batch` 按 blob 原字节在 `/tmp` 临时目录
展开（不应用 archive 导出替换/忽略属性），使用冷进程读取，结束后清理；不使用当前登记或宿主模块缓存替代历史登记。
`writers` 是与 `load_scopes` 相同的显式合成 writer 清单，只用于 Python 合成材料，
CLI 不提供覆盖入口。默认无 base 的 `audit_scopes`、报告键与原有冻结测试接口保持不变。
历史/当前登记仍执行仓库 Python 代码，仅限已审查树；临时副本不是执行沙箱。

显式报告额外包含 `baseline`：实际 `base`、`head`、规范本地 `integration_target`、
`target_commit`、`dirty`、`worktree_sha256`、`baseline_issues` 和 `changes`。
每条变化保留路径、base/当前文件 SHA（缺失为 null）、原登记 SHA 集合，
以及 base/当前 `registrations`（group、scope_path、kind、expected_sha256），
直接 `groups` 和传递 `affected_groups`。两个维度独立：

- `origin=current_change` 表示相对 base 的字节或成员/计数登记语义变化；
  `baseline_drift` 表示 base 内登记与真实材料已经不符。两者可以同时出现。
- `sensitivity=mechanical` 的 `category=source_support` 包括普通 source/support 哈希
  变化和仅更新其哈希的 scope；显式证明引用、测试成员/计数、fixture、冻结负例、需求/覆盖台账、
  格式、绑定契约或证据、分类规范变化为 `sensitive`。
  类别分别为 test、fixture、registration、format_or_criteria、evidence、classification。

scope 的测试/fixture 完整绑定、source 成员与固定计数另有 `old_entry_sha256`、
`new_entry_sha256`，防止仅看文件字节遗漏注册组/成员变化；source 哈希不进入该语义摘要。
对普通材料路径，entry 摘要保存展开后的逐组 kind/SHA，中央 SHA 单独变化也会产生
材料路径的变化记录与旧新 registrations。source/support SHA 仍为机械；同一路径在任一组
具有 test/fixture 或证据用途时，按敏感变化对全部受影响组确认。中央文件整体变化不扩张
到无关组，各树读取自身中央条目，不借用当前树声明。

scope 格式等元数据、Python 常量中 FORMAT/COUNT/REQUIRED_TEST/FIXTURE/NEGATIVE/
REQUIREMENT/COVERAGE/CAPABILIT/NOT_ASSESSED/NOT_IMPLEMENTED/REQUIRED_CHECK/
DEPENDENC/MIGRATION/SCOPE/ISSUE 名称的赋值变化均保守列为敏感。
未绑定的 `scope-material-inventory.json` 控制每组分类，变化影响全部旧/新组；
不能通过移除其 scope 绑定绕过审阅。普通未登记文件不扩张验收集合，但参与树身份。

确认文件必须位于被审计工作树外，UTF-8 JSON 顶层为数组，每个元素只包含：
`base`、`head`、`integration_target`、`target_commit`、`worktree_sha256`、
`group`、`path`、`origin`（current_change）、`category`、`old_sha256`、`new_sha256`、
`old_entry_sha256`、`new_entry_sha256`、非空可打印人工审查 `reason`。
每个敏感本轮变化的每个受影响组需要一条精确匹配记录；未知/多余字段、错误作用域、
重复或旧身份确认均拒绝。工具不生成“一键接受全部候选”的确认文件。
Python `confirmations` 接受同样的 list/tuple 对象；输入不是正式回执或写回授权。

工作树身份覆盖 Git 管理及非忽略路径的类型、模式和字节，包括未登记活文档；
确认文件放在树外避免自哈希循环。继续修改同一 HEAD 下任何身份材料后确认失效，
HEAD 或 target 变化也失效。计算结束再次检查 HEAD、target 与树摘要，防止混合身份。
基线既有漂移单独失败，不能被本轮修改、更新当前登记或确认消除；先明确处理基线问题。
确认只解除 `confirmation_required`，不会清除 `files` 的 `hash_drift` 或结构错误；
候选要经人工授权修改登记后重跑才可能匹配。显式分析仍不写任何登记或正式证据。

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
| 活文档分类 | 文件级 `live_document_binding`；规则级 `classification_unavailable`、`invalid_classification` |
| 引用图 | `self_reference`、`cycle` |
| 固定计数 | `invalid_counts`、`count_keys_mismatch`、`invalid_count`、`conflicting_counts` |
| 登记加载与解释 | `registration_unavailable`、`invalid_registration`、`unsupported_registration`、`duplicate_registration`、`duplicate_count_key`、`unsupported_scope_import`、`unsupported_writer_scope`、`unsupported_scope_constant`、`unconsumed_registration`、`unsupported_secondary_binding`、`writer_unavailable`、`registry_unavailable` |
| 收集 | `not_requested`、`audit_failed`（审计阻止收集或无可收集目标）、`collection_unavailable`、`collection_timeout`、`collection_failed`、`collection_skipped`、`collection_deselected`、`count_mismatch`；成功为 `ok`，直接调用时非法预期映射返回 `invalid_counts` |
| 基线与确认 | `invalid_baseline`、`baseline_unavailable`、`baseline_registration_unavailable`、`baseline_target_mismatch`、`baseline_not_ancestor`、`baseline_drift`、`baseline_identity_changed`、`invalid_confirmation`、`confirmation_required` |
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

- 依据：[#60](https://github.com/MeteoBoy4/PaperRadar/issues/60)（开发维护命令）、[#132](https://github.com/MeteoBoy4/PaperRadar/issues/132)、[ADR-0038](../adr/0038-separate-live-documents-and-share-verification-registration.md)、[规格 §11](../../intent/draft.md#十一九阶段实施与验收)、[ADR-0031](../adr/0031-screening-budget-and-derived-applicability.md)（固定材料、同次身份与离线证明边界）。
- 实现：[命令入口](../../scripts/audit-verification-scope)、[CLI](../../scripts/audit_verification_scope.py)、[审计与报告类型](../../scripts/verification_scope_audit.py)、[登记解释](../../scripts/verification_scope_registry.py)、[独立收集](../../scripts/verification_scope_collection.py)。
- 正式结论的查询边界见[verification-status](verification-status.md)；固定登记维护与历史证据见[离线验证证据](../verification/offline-evidence.md#固定-scope-维护审计60)。
