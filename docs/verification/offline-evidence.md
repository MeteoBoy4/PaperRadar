# 离线验证证据

运行仓库根目录的 `./scripts/check-offline`；`./scripts/check-offline --help` 只打印中文
帮助，不启动检查或写入证据。脚本按固定顺序实际执行 lockfile
一致性、格式、静态规则、类型、全部离线测试和已选择的冻结契约一致性检查。每次
运行会在被 Git 忽略的 `verification-runs/<run_id>.json` 生成 #12 离线证据，
并在 `verification-runs/<run_id>.a1.json` 生成独立的 #13 A1 结论，
在 `<run_id>.a2.json` 生成 #16 A2-01 结论，在 `<run_id>.a2-full.json` 生成
#25 完整 A2 结论，在 `<run_id>.a3.json` 生成 #29/#35 独立 A3 结论，
在 `<run_id>.a4.json` 生成 #36/#45 独立 A4 结论，
在 `<run_id>.a5.json` 生成 #47/#54 独立 A5 结论，在 `<run_id>.a6.json` 生成 #67/#75 独立 A6 结论，
在 `<run_id>.a7.json` 生成 #76/#84 独立 A7 结论；终端打印九个主要路径及结果。测试另外生成同次
`<run_id>.pytest.json` 脱敏执行回执。控制方在全部组发布后，最后写出
`<run_id>.terminal.json` 终态记录并打印路径，正常成功共十一份 JSON。
整套检查仅执行一次，各文件
共享本次 `run_id` 并绑定实际证据哈希。仅本次 A1、完整 A2、A3、A4、A5、A6 与 A7 均通过时入口返回 0，
A2-01 继续独立记录原有范围。离线测试与迁移验收使用临时数据库，不操作用户数据库。
重跑不会覆盖旧证据或结论，也不会沿用旧检查状态。入口使用
`uv run --offline --locked` 启动项目 Python；若 uv 在启动 Python 前失败，
本次尚无证据文件，终端会收到 uv 的非零退出码。

`<run_id>.pytest.json` 只是 pytest 子进程的内部回执，不代表整次运行状态；
判断运行是否完成及通过，只看入口退出码和本次各组结论，不能把回执中的
`completed` 或 `exit_code` 当成完整入口的结果。运行中或中断后的回执也不能单独
作为通过依据。

开发者可用 `./scripts/verification-status <run_id> --runs-dir verification-runs --json`
只读查询进度和可信终态；省略 `--json` 显示中文。命令不启动 uv 同步、测试、迁移或
模型，不写入证据、字节码或 Git 索引；历史组不追加状态工具测试；A6/A7 显式绑定各自状态格式及新增反例。
状态、阶段、退出码、终态格式和历史兼容规则见
[状态查询契约](../contracts/verification-status.md)。缺少终态记录时只能证明
“终态未证实”，包括旧运行、发布中、发布崩溃与被强杀的控制方；不据 PID、mtime
或 pytest 的 completed 推断成功或进程存活。当前工作树是否匹配另行报告，
历史通过不会因为后来修改代码而被改写成失败。

控制方启动检查和环境探测子进程前，清除继承的 `PAPER_RADAR_TEST_RECEIPT` 与
`PAPER_RADAR_TEST_RUN_ID`；仅 `tests` 检查重新绑定本次回执路径和 run_id。
每项检查使用独立会话和进程组；KeyboardInterrupt 或 SIGTERM 中断时先对整组发送
SIGTERM，等待至多两秒，再向残留进程组发送 SIGKILL。Linux 上通过 `/proc` 核对组成员、
用 pidfd 等待退出并复扫后代，确认没有存活成员、回收直接子进程后才记录 `interrupted`；
不等待已退出后代的僵尸记录被其收养者回收。组长提前退出也不省略后代清理，清理期间
重复的 SIGINT/SIGTERM 不打断回收。两秒仅是 SIGTERM 的宽限期；SIGKILL 后等待
退出确认没有总超时。内核不可中断睡眠（D 状态）的成员可能使控制方持续等待；
这时不会声称已回收，也不会发布正常的 `interrupted` 收尾。需要先排除宿主 I/O
阻塞；若强杀控制方，已有证据仍是不完整的运行记录，不能当成通过。

证据格式版本为 `1`，字段含义如下：

| 字段 | 含义 |
| --- | --- |
| `run_id`、`started_at`、`finished_at` | 本次随机运行标识及 UTC 时间。未正常结束时 `finished_at` 可为 `null`。 |
| `completed`、`overall` | `completed` 表示本次记录已正常收尾，不表示所有检查都已执行；首个失败使后续检查未运行时它仍为 `true`。总结果固定为 `passed`、`failed`、`incomplete`。只有所有检查本次均实际通过才为 `passed`。 |
| `scope` | 仅证明 Issue #12 的已实现离线范围。`full_a1_verified` 和 `stage_a_verified` 固定为 `false`；`not_assessed` 列出未作验收声明的能力。 |
| `code` | `git rev-parse HEAD` 的提交 SHA 与运行前 `git status --porcelain` 推导的未提交变更标记。无法取得时为 `null`。不保存文件名或 diff。 |
| `lockfile_sha256` | 本次工作树 `uv.lock` 的实际字节哈希；不可读取时为 `null`。 |
| `environment` | 通过项目锁定环境取得的 Python、Pydantic、Typer、pytest、Ruff、mypy 版本。单个依赖缺失时该项为 `null`；整体探测失败时各项为 `null` 且 `missing_reason=environment_unavailable`；探测尚未开始时为 `not_collected`。 |
| `contracts` | 本次契约检查计划选择的名称、声明版本与磁盘 `schema.json` 实际字节 SHA-256；文件不可读取或探测未完成时哈希为 `null`。即使 `contracts` 检查未运行，也可已有文件哈希；是否核对通过只能看 `checks` 中的 `contracts` 状态。 |
| `checks` | 每项固定 `id`、`status`、`reason`、`exit_code`；失败项另有固定的中文 `help_zh`。不保存命令参数、原始输出或异常文本。 |

`status` 只能是 `passed`、`failed`、`not_run`。`reason` 只能是 `none`、
`not_started`、`skipped`、`prior_failure`、`interrupted`、`exit_nonzero` 或
`launch_error`。`exit_nonzero` 附进程退出码；`launch_error` 表示命令无法启动；
中断时当前检查记为失败，后续检查记为未运行，`overall=incomplete`。首个失败会
停止后续检查，未运行项不会复用先前运行的通过结果。项目 Python 启动后先写出
所有检查均为 `not_run`、身份字段尚未采集的新文件，再探测身份并执行检查；每项
结束后原子更新。运行中被中断时会尽力记录 `overall=incomplete` 并打印路径；
突然终止时已有文件保持 `completed=false`，不能当成通过。

失败时按 `checks[].id` 和 `help_zh` 定位并单独重跑检查。脚本有意不保存也不回显子进程的原始输出，
避免测试失败信息泄漏 Profile、摘要、正文、Prompt、secret 或模型响应。维护者可按
`scripts/offline_evidence.py` 的固定计划单独重跑对应检查取得本地诊断；不要把
含敏感输入的原始输出加入验收证据。`contracts` 项的详细失败类别也可通过已存在的
`paper-radar contracts check` 命令单独查看。

证据记录的是一次实际执行；其中 #12 的 `full_a1_verified=false` 与
`stage_a_verified=false` 保持固定。A1 结论单独核对完整范围，不改写这份证据。
新增已实现冻结契约或声明版本时，同步更新脚本的 `CONTRACT_NAMES`
和 `CONTRACT_VERSION`，使检查命令与证据范围一起更新；测试会与权威注册表核对。

## 固定 scope 维护审计（#60）

改动固定源码、支撑文件、测试或向量后，先运行独立开发入口：

```bash
./scripts/audit-verification-scope
./scripts/audit-verification-scope --json
./scripts/audit-verification-scope --collect --json
```

默认只读核对每个 writer 消费的显式路径和 SHA-256，显示登记值与当前值、缺失/
不可读/漂移、重复路径、计数 key 与测试集合不一致、非法计数（含 bool）、scope
引用链和拓扑处理顺序。每个 scope 的 downstream 列出修改它后需要重新核对登记的
下游；affected_groups 同时包括直接问题及传播影响。循环和自引用拒绝提供处理顺序。
source 中的 scripts/tests 路径另标为 support，fixture 类别保留向量/材料的具体路径。
JSON 包含全部文件、固定计数和受控原因；文本显示问题和候选哈希，不显示文件内容。
退出码 0 表示审计匹配，1 表示漂移或无法核验，2 表示参数错误。

组清单从 `acceptance_groups()` 的每个 `write` 来源推导，包含 optional A2-01，
不硬编码 A1–A7 模块列表。writer 对 `scripts.*_scope` 的显式导入是维护契约；
只消费 `REQUIRED_TEST_MODULES`、`REQUIRED_SOURCE_MODULES`、
`REQUIRED_FIXTURE_FILES`、`REQUIRED_TEST_CASE_COUNTS` 与明确允许的元数据。
新常量、重命名、不支持的导入或表达式必须人工扩展工具契约后才能继续审计；不能因
无法识别而当成空集合。支持 A3 的子清单展开，检查最终 writer 消费的汇总，避免
把子清单和总清单重复计为登记。完整 A2 同时核对它明确导入的 A1 测试哈希和计数。
附加 scope 的源码、fixture 或计数导入当前明确拒绝；模块式 scope 导入仅允许
`SCOPE`、`ISSUE` 等明确元数据属性，不能通过属性或别名访问绕开登记核对。

`--collect` 可在文件哈希漂移或计数 key/分母错误时，用独立 pytest 进程、
`--collect-only`、禁用 cacheprovider/字节码及回执插件，收集显式测试清单中的模块。
缺失、非法或冲突分母仅给出诊断计数，原审计仍返回非零；未登记文件与额外计数 key
不会成为收集目标。缺失/不可读材料（含仓库外链接）、未知登记、非法绑定或引用图
错误仍阻止收集。子进程清除
`PAPER_RADAR_TEST_RECEIPT`、`PAPER_RADAR_TEST_RUN_ID`、`PYTEST_ADDOPTS`、
`PYTEST_PLUGINS`，关闭第三方插件自动加载并清空配置 addopts。只在 `/tmp` 的独立
临时文件中传递受控模块计数，退出后移除，不保存或回显原始 stdout/stderr。
参数化按节点计数，模块级 skip、deselect、收集失败/超时均不能通过；函数级 skip
标记仍算被收集节点，不宣称实际执行或通过。收集不写正式回执或验收文件，也不能
代替真实测试执行，更不能将实测数量写成固定分母。
收集超时、不可用或失败不意味着所有模块计数漂移，保留已有受影响组；只有完整
计数比对发现差异时才追加可定位的组和引用传播，既有哈希/登记问题不会被覆盖。

本工具不扫描未登记文件以扩大 required 范围、不自动更新哈希或计数、不登记进任何
scope，也不加入 `default_checks()` 的固定六项检查。人工审阅候选并按拓扑顺序修改
scope 源码后，重新审计，再运行完整 `./scripts/check-offline`；正式入口保留独立
漂移检查，历史证据与冻结判据保持原义。开发接口与 JSON 字段见
[审计命令契约](../contracts/verification-scope-audit.md)。

## 运行组织与验收组登记

`scripts/verification_run.py` 负责一次运行的身份基线、同次证据、验收组发布顺序、
中断传递、终端结果和整体通过判断；`scripts/verification_identity.py` 维护原有
HEAD、工作树与 lockfile 身份算法。`scripts/offline_evidence.py` 继续执行固定六项
子进程检查、失败停止、脱敏输出和运行中证据更新；回执仍由
`scripts/a2_test_receipt.py` 在唯一 pytest 进程中记录。这两个底层实现未作重构。

生产登记位置是 `scripts/a2_full_acceptance.py` 的 `acceptance_groups()`。
`AcceptanceGroup` 显式声明名称、输出后缀、结论入口、前置结论及是否影响整体通过；
重复名称、重复输出或缺少前置组会在检查前拒绝。顺序只决定发布先后，不隐含通过依赖：

| 验收组 | 输出后缀 | 前置结论 | 影响整体通过 |
| --- | --- | --- | --- |
| A1 | `.a1.json` | 无 | 是 |
| A2-01 | `.a2.json` | 同次 A1 | 否 |
| 完整 A2 | `.a2-full.json` | 同次 A1 | 是 |
| A3 | `.a3.json` | 同次 A1、完整 A2 | 是 |
| A4 | `.a4.json` | 同次 A1、完整 A2、A3 | 是 |
| A5 | `.a5.json` | 同次 A1、完整 A2、A3 | 是 |
| A6 | `.a6.json` | 同次 A1、完整 A2、A3、A5 | 是 |
| A7 | `.a7.json` | 同次 A1、完整 A2、A3、A5、A6 | 是 |

完整 A2 另由自己的判据验证同次 pytest 回执、证据和已发布 A1，并在发布前再次
核对这些文件的实际字节绑定；它没有 A2-01 通过依赖。各组的原因、格式、严格性与
中断恢复继续由自己的验收模块维护。A1 恢复沿用自己的结论状态；A2-01 发布中断
即使补写为 passed，也继续把中断传给完整 A2。最后发布阶段的中断仍可能没有
完整结论，不会覆盖已发布文件来修复状态。

八组的 `write_*_conclusion` 兼容入口共用
`scripts/verification_publication.py` 的 `publish_conclusion`：保持原 JSON
序列化规则，临时文件独占创建、flush/fsync 后通过 `os.link` 原子发布；目标已存在
即失败，finally 清理临时文件。运行中证据与回执仍可原子更新，不使用此最终发布入口。

新验收组以显式代码加入登记，提供自己的判据，调用同一个最终发布函数；可选提供
组内中断恢复规则，无需在组织核心增加组名称分支。当前回执显式记录 `a1_scope`、`a2_full_scope`、`a3_scope`、`a4_scope`、`a5_scope`、`a6_scope` 与 `a7_scope` 的固定测试模块合集。
新增组仍须显式扩展执行范围；没有自动发现插件、独立检查计划或动态调度。
测试中的合成组只证明组织扩展能力，不代表新增产品验收能力。

A4/A5/A6/A7 的环境版本采集与真实临时库迁移探针共用 `verification_checks` 的原语；
各组继续独立维护依赖清单、原因词表、异常分类、登记 head 与通过判据。

#48–#53 的 boundary/value/extraction/reuse 阶段输入服务由普通离线 pytest 验证，
配方、固定向量及证明边界见[阶段输入契约](../contracts/stage-inputs.md)。extraction 测试
不读取 PDF 或运行 Docling，包含纯未来 normalization fixture 与真实编译拒绝反例。
正文 reuse 使用真实 ArtifactStore 的成员哈希验证 manifest 审计隔离与消费内容变化，
另有正文/混合来源固定向量、同次来源一致性、不可变性与无 I/O 回放验证。
#54 将这些固定测试显式登记进独立 A5 结论，不改写既往结论范围。

#53 新增四阶段参数化共同契约、薄配置传播检查和独立进程隔离恢复复现。恢复用例建立
两份真实配置快照与非空 original_pdf/source_snapshot/extraction 制品，移走原根和恢复根后，
新进程只从恢复库 load 明确历史快照，并重新 get_artifact 取得 payload/reading/evidence_map
成员，重建 boundary/value/extraction、结构化 reuse 与正文 reuse；原成员哈希不跨进程。
两个启用主题、不同 PYTHONHASHSEED/cwd/构造顺序均匹配独立固定向量，错误历史投影拒绝，
精确文本与摘录顺序变化仍改变身份，恢复 DELETE 数据库字节保持不变。
文件/数据库/网络拒绝哨兵与架构测试证明纯构造、回放和比较无隐式 I/O；
caplog、repr、受控异常和 stdout/stderr 验证敏感内容不泄露。

独立执行恢复路径（只运行相关回归，不发布 A5 结论）：

```bash
uv run --offline --locked pytest -q tests/test_stage_input_recovery.py::test_isolated_restore_rebuilds_all_stage_inputs_from_restored_members
```

共同契约与薄交叉检查在 `tests/test_stage_input_common_contract.py` 和
`tests/test_stage_input_dependencies.py`，语义范围见[阶段输入契约](../contracts/stage-inputs.md#隔离恢复跨进程与后续消费者义务)。
书目/供给隔离仅由严格拒绝额外字段和真实 adapter 审计版本变体证明，不创建安装记录，
不声称“卷期页码更新到任务不重跑”已端到端验证。当前七份主要文件及额外 pytest 回执
不改变 A1/A2/A3/A4 既有能力范围；阶段 A、RPC、NAS/live、自动精读仍未验收。

#28 保留原 A1/A2-01 固定测试字节，只更新经审查的验收源码哈希，登记提取出的
运行身份、组织、发布模块，以及新回归模块、固定用例数量和终端输出 fixture。
`tests/fixtures/verification_transcripts.json` 的八种输出取自重构前 `e3a7ff3`
及当时已有的配置材料组装工作树；仅替换输出目录和随机 run_id，逐字节比较正常、
检查失败、检查中断、旧切片失败和 A1/A2-01 发布前后中断的终端输出及退出码。
新增回归另覆盖合成组的整体通过设置、发布失败清理、最终发布中断、仅收集、取消
选择和发布前回执替换；原真实子进程、临时 SQLite、脱敏和旧入口回归继续执行。

## A1 独立结论

`<run_id>.a1.json` 的格式版本为 `1`，字段如下：

| 字段 | 含义 |
| --- | --- |
| `run_id`、`evidence_file`、`evidence_sha256` | 绑定本次 #12 证据的运行标识、文件名与完整字节哈希。 |
| `scope`、`issue`、`not_assessed` | 固定 A1 范围、Issue #13 与明确未验收的阶段 A/B 能力。 |
| `required_checks`、`checks` | 固定六项检查的顺序与本次逐项状态、原因、退出码。 |
| `required_test_modules`、`test_modules` | A1 已交付能力测试的固定路径/内容哈希与本次逐项核对结果。 |
| `required_contracts`、`contract_version`、`contracts` | 四份 v1 契约的固定选择与本次只读核对结果、实际哈希。 |
| `code`、`worktree_sha256`、`lockfile_sha256` | 本次 HEAD、未提交变更标记，以及工作树和锁文件的哈希。工作树哈希覆盖 Git 管理及非忽略文件的路径、类型、权限模式和字节。 |
| `environment` | Python 与关键依赖版本；缺失时不能通过。 |
| `status`、`a1_verified`、`stage_a_verified`、`reasons` | `status` 为 `passed`、`failed` 或 `incomplete`；只有 `a1_verified=true` 代表 A1 通过，`stage_a_verified` 固定为 `false`；失败原因带受控代码、中文建议及可选项目名。 |

结论只保存哈希，不保存测试、快照或工作树文件内容。固定测试范围记录在
`scripts/a1_scope.py`；有意修改这些测试时须审查对应能力，并同步更新哈希。
`tests` 检查不继承外部 `PYTEST_ADDOPTS`，避免环境变量暗中缩小固定测试范围。

判定要求本次证据保留 #12 的固定 scope、`completed=true`、`overall=passed`，
六个固定检查按顺序全部实际通过（`status=passed`、`reason=none`、
`exit_code=0`），固定测试模块均存在且内容匹配，环境版本完整，
且四份 v1 快照在结论生成时仍由只读公共检查逐项确认与权威定义一致、与本次证据
哈希相同。运行前后的 HEAD、工作树与 lockfile 必须相同，并与证据中的 HEAD、
未提交变更标记和 lockfile 哈希相符。文件时间和历史成功记录不参与判断。

缺快照、版本漂移、证据与当前快照哈希不一致、测试模块缺失或漂移、检查跳过/失败
均为 `failed`；可捕获的运行中断为 `incomplete`。修复后完整重跑会得到新的
`run_id` 和结论，旧结果保留。完整入口另须本次完整 A2、A3、A4 与 A5 通过才返回 0。
若 uv 尚未启动 Python 或进程被强制终止，可能没有本次结论文件；前者保留 uv 的
非零退出码，后者已有的 #12 证据仍不能作为 A1 通过。

固定 A1 范围包括工程与帮助、三种输出的完整验证、原因组合、四份正式快照、
单份和批量导出/检查、冲突与恢复、隐私和模块边界、机器证据记录。该结论复用
现有离线测试和固定 `check-offline` 计划，不将未实现规则当作通过。`not_assessed`
明确列出阶段 A 剩余的 RuntimePlan、持久化、指纹、任务与共享接口、doctor、
结构化日志、备份恢复和真实来源审计，以及阶段 B 与自动全文精读；A1 通过不开放
这些能力，也不自动修改父 Issue。此处 `RuntimePlan` 是 A1 的历史范围文字，
现对应 `RuntimeConfigSnapshot`；A2-01 的结论另行记录其已实现切片，不回写
A1 结论的历史含义。

## A2-01 独立结论

`<run_id>.a2.json` 绑定同次 #12 证据的 SHA-256 和 `<run_id>.a1.json` 的
SHA-256。它核对 A1 已通过、本次六项离线检查全通过、A2 测试与 config/storage
源码的固定字节哈希、运行前后的 HEAD/工作树/lockfile 身份。固定范围定义在
`scripts/a2_scope.py`，与 A1 的 `scripts/a1_scope.py` 分开；更新 A2 行为时应
审查并更新对应哈希，不修改 A1 固定测试哈希。A2-02/A2-03/A2-04/A2-06 的新回归测试仍由完整 `tests` 检查覆盖；A2-01 固定测试模块保持原字节。此处未实施项按当前实现逐槽列出；A2-04 开放 reuse 提示词、reuse-assessment/decision-reasons 契约与升级参数后，从当前清单移除这些缺项；A2-06 开放 reading 提示词后也移除其缺项，Read 实际执行与权威输出契约仍未实施。这不改写历史 A2-01 结论。

结论记录锁定 Python 环境中的 Alembic、SQLAlchemy、PyYAML 版本、随包 Alembic
实际 head、快照编译格式版本，以及未实施项。A2-03 增加 topics 源码身份，更新受影响源码哈希；历史 A1/A2-01 固定测试字节不变。
A2-03 审查改进继续更新受影响源码哈希，并登记新增测试支撑模块的哈希。
可变回归模块改用该模块提供的材料工厂、CLI 入口与导入检查；固定测试文件内
原有辅助函数保留，避免为了整理测试重标历史验收。A2-04 更新受影响源码哈希，并登记纯 escalation 类型模块及 `tests/config_reuse_support.py` 支撑工厂的固定哈希；新服务、参数和 CLI 回归随完整测试执行，A2-01 固定测试字节继续保留。快照格式与 migration 不变。
A2-05 更新受影响源码哈希并登记正文提取配置类型、受控工具链及测试支撑；正文提取配置回归随全部测试执行，不安装 Docling 或执行 PDF 解析。A1/A2-01 固定测试、四份 v1 契约、快照格式与 migration 保持原身份；未实施项中的正文提取改为尚未交付的实际解析执行。
A2-05 审查改进更新受影响源码哈希，补充模型阶段受控类型、OCR 边界指引及合法配置身份不变的回归；A1/A2-01 固定测试与验收 scope 保持原身份。
#26 更新经审查的配置源码绑定，并登记 adapter 配置权威与装载模块的固定哈希。
审查改进还登记 `tests/config_adapter_support.py` 的固定字节哈希，绑定已审查的
合成 Prompt、资源哈希及材料工厂；后续修改该文件会由 `scope_drift` 检出。
新增 adapter 公共服务/SQLite/CLI 回归随完整测试执行；A1/A2-01 固定测试字节、
scope、快照格式及 migration 不变，不把 adapter 分量当作统一阶段投影或完整 A2。
#26 的通用 Pydantic 错误指引也适用于既有 Profile/models/topics/escalation/extraction：
缺字段、未知字段、非法类型或受控值分别给出中文修正指引，保留既有“类型错误”
分类。此附带变化不改变输入接收规则、退出码、快照身份或校准语义；错误仍不回显值。
#21 更新受影响源码绑定，登记 Read 配置权威和固定合成材料工厂的哈希。
Read 公共服务、SQLite 原子登记、版本保护、跨进程回放、真实 CLI 及 help 回归随
完整测试执行；新增受控 chunking 错误提供文本 v1 的修正指引。快照格式与 migration
不变，不改变 A1/A2-01 固定测试，也不将 Read 配置保存标为实际 Read 或阶段 B 通过。
#21 审查改进将业务 Prompt 名统一为受控枚举、路径固定为映射，Read 材料工厂
显式写入完整 YAML；同步受影响源码与工厂哈希。新增公共服务回归使用重构前
`257ee92` 的四种固定快照身份，证明 boundary/value/reuse/reading 的加载、
保存和历史回放身份不变；完整测试覆盖该回归，不重标 A1/A2-01 固定测试。
#22 更新受影响的配置源码绑定，登记纯 journals 类型与固定合成材料工厂的哈希。
期刊字段与规范化冲突、版本保护、事务回滚、跨进程回放及真实 CLI 回归随完整
测试执行；从当前未实施清单移除期刊配置。A1/A2-01 固定测试、scope、四份 v1
契约、快照格式及 migration 保持不变，不把登记信誉标为评分或排序已实现。
#22 审查改进统一期刊自定义错误与公共 YAML 边界的权威指引，并为材料工厂的
settings 读写显式指定 UTF-8；同步两项受影响源码哈希。现有期刊服务、CLI 与
持久化回归继续验证相同的接收规则、脱敏错误和历史回放，不新增阶段语义。
主题、value、复用升级、期刊与正文提取配置的新增行为由公共服务/真实 CLI 回归测试随本次完整测试验证，不把结论重标为完整 A2 通过。阶段配置投影与校准基线
在 A2-01 范围内未作验收，历史格式字段继续为 `null`；#23 已实现的能力另由下文
完整 A2 结论覆盖。A2-01 通过不等于完整 A2、阶段 A、正式
校准或自动精读通过。结论只保存文件哈希和受控状态，不保存配置正文、Prompt、
secret 或子进程输出。`status` 为 `passed`、`failed` 或 `incomplete`，只有
`a2_01_verified=true` 表示本票固定范围通过。

#24 更新经审查的 SQLite 连接、登记事务与 compile 帮助源码绑定；新增公共服务与
真实安装 CLI 回归随完整测试执行。测试通过独立连接屏障和子进程管道握手控制
并发及故障位置，不依赖 sleep；覆盖同材料复用、版本冲突、固定 5 秒锁等待、
SQL 失败、连接中断、提交前进程终止、来源文件替换和脱敏。A1/A2-01 固定测试、
原有外部 I/O 哨兵、四份 v1 契约、快照格式与 migration 保持不变；不将这些回归
升级为完整 A2 机器结论，完整 A2 由 #25 的下列独立结论记录。
审查补充孤儿引用的拒绝和只读一致性回归，防止重新编译从可变来源补回损坏历史，
或 check 在并发提交期间误报损坏；同步登记事务源码绑定。

## 完整 A2 独立结论

`<run_id>.a2-full.json` 的格式为 **2**，scope 固定为
`a2_versioned_config_snapshots`、issue 为 25。生产入口是
`scripts/check-offline` → 原有 `scripts.a1_acceptance` 启动入口 →
`scripts.a2_full_acceptance` → `scripts.verification_run`，
完整六项计划只执行一次。A2-01 仍写 `<run_id>.a2.json`，保留自己的 scope、
固定测试字节与历史未覆盖项；它的结果不能代替完整 A2，也不再决定完整入口退出码。
#12 格式 1、五个原有依赖字段和 A1 固定测试及 `not_assessed` 保持原义。

| 字段 | 判据与含义 |
| --- | --- |
| `run_id`、`evidence_file`、`evidence_sha256` | 与本次 #12 文件名、内容 run_id 和实际字节哈希一致。 |
| `a1_conclusion_file`、`a1_conclusion_sha256` | 同次 A1 实际文件和哈希；文件内容须与执行器返回的结论一致，且本次 A1 必须通过。 |
| `required_checks` | 固定 lockfile/format/lint/types/tests/contracts 顺序，每项本次实际通过、reason 为 none、exit_code 为整数 0；缺项、跳过或失败均拒绝。 |
| `test_modules`、`source_modules` | 固定路径、expected_sha256、actual_sha256 和 passed/failed；缺文件或字节漂移不能通过。 |
| `pytest_receipt_file`、`pytest_receipt_sha256`、`test_execution` | 绑定本次 pytest 原始脱敏回执的文件名与实际哈希；逐个固定模块核对收集、通过、失败、跳过、取消选择和未完成计数，只有收集与完整通过数量均等于固定数量，其他四项均为 0 才通过。 |
| `fixture_files` | `examples/` 固定合成材料逐文件的 SHA-256 身份与核对结果，不保存配置或 Prompt 正文。测试材料工厂和进程哨兵的字节另列在 source_modules。 |
| `environment` | 当前锁定 Python 及 Alembic、SQLAlchemy、PyYAML 的实际安装版本；版本缺失失败，新依赖不追加到 #12。 |
| `migration_revision` | 另建临时 SQLite、真实 base→head 后从库内 alembic_version 读取唯一 revision，并核对随包 head 与显式固定的 a405_pi_cleanup_execution；未登记新 head、升级失败或读取失败均拒绝。无用户数据库参数。 |
| `format_versions` | snapshot 为 1；stage_projections 分别记录 boundary/value/reuse/extraction/read/suggestion，各为 1；calibration_baseline 为 1；adapter_semantics 为 1。逐项独立匹配，不能只写一个总版本。 |
| `code`、`worktree_sha256`、`lockfile_sha256` | 本次实际身份，须与 A1 运行前后核对过的身份及 #12 一致。材料与代码在运行期间变化均拒绝。 |
| `status`、`a2_verified`、`reasons` | passed/failed/incomplete；只在无失败原因时 a2_verified=true。原因仅受控代码、中文指引及可选受控文件路径/依赖名称，不保存原始异常、SQL、输入值或进程输出。 |
| `stage_a_verified`、`live_verified`、`not_assessed` | 前两项恒 false；固定列明剩余能力，不从 A1 历史未覆盖项推断当前能力。 |

固定范围在 `scripts/a2_full_scope.py`：显式列出 A2-01–A2-09、#26 adapter、
已交付 #27 快照发现，以及本票验收、真实示例、入口测试；不在运行时扫描测试目录
后自动生成期望。修改行为或升级格式时须先逐项审查对应规格与测试，再显式修改清单
中的字节哈希/受支持版本。不能为取得绿色结果自动刷新期望；A1/A2-01 固定测试
不得借此重标。当前源码绑定因完整入口帮助变化只更新 A2-01 的 wrapper 源码哈希，
原五个固定测试、scope 和历史格式 null 不变。

完整 A2 格式 2 增加必需的实际执行回执绑定，替代开发中的仅文件哈希/总退出码判据。
回执格式独立为 1，由 `scripts.a2_test_receipt` 插件在本次唯一 pytest 进程中生成；
不修改 #12 或 A1 的格式、字段和历史结论。固定测试模块及其用例数量一并显式冻结，
包括 A1 原固定范围；根 conftest、插件或筛选参数使固定用例少收集、skip、xfail、
取消选择或未完整经过 setup/call/teardown 时，即使 pytest 总退出 0，完整 A2 也失败。
旧格式、旧 run_id、缺回执或回执在核对期间漂移都不能通过；收集中断保留 incomplete。
仅收集不执行也不能通过。新增或变动固定用例须先人工核对，再显式更新固定计数与字节，
运行时不会自动收集后刷新期望。

回执仅保存固定模块路径和整数计数，不保存测试名、参数化 ID、skip 原因、捕获输出、
traceback 或原始异常。进程启动即写 incomplete 初态，收集后更新，最终记录结束状态；
没有配置时直接加载插件不写文件，不改变普通子集测试的使用方式。

完整 A2 的原因由 `A2FullReasonCode` 管理，状态复用既有 `OverallStatus` /
`CheckStatus`；回执的六项计数由 `ReceiptCounter` 与 `RECEIPT_COUNTERS` 统一定义。
这些类型只约束实现，序列化仍为原有字符串、字段和整数；完整 A2 格式保持 2，
回执格式保持 1。真实子进程回归继续使用独立字面量断言六个字段，避免生产者与
验证器共享字段定义后掩盖公开格式漂移。

A2-01 写出期间发生中断后，若本次检查已经全部通过，补写的旧切片结论可按自身
范围记 passed；同次完整 A2 必须为 incomplete，入口返回非零。两者 scope 不同，
旧切片的通过不会覆盖或恢复本次完整验收；不为状态对称而更改旧切片接口或历史格式。

### 父规格与评论覆盖

下列模块均在完整 A2 固定测试清单中；表内模块名省略 `tests/` 和 `.py`。
它同时核对 #15 Decisions、Testing Decisions、DoD、补充一 #1–20、补充二 #21–46
与已确认的版本标签隔离，不声明其外部依赖或后续业务流程已经实现。

| 规格/补充 | 验证边界和固定模块 |
| --- | --- |
| Decisions 1–5、补充一 1–5、8–9、20、补充二 23、30–32、40–45 | `test_config_service`、`test_config_validation`、`test_config_boundary`、`test_config_value`、各类 validation/architecture 模块：六段 Profile、纯 selector/根目录/封闭名、严格 YAML、占位和未配置、中文受控错误、层级隔离。 |
| Decisions 6–10、补充一 3、8、10–11、15、17、19、补充二 28、33–35 | `test_config_service`、`test_config_boundary`、`test_config_value`、各类 persistence：真实迁移、metadata 一致、外键唯一约束、原子登记、精确 schema+manifest 字节、跨进程回放、输入零改写、只读模式、未知格式与损坏拒绝。无新增 migration，所以本票不增加伪“上一 revision 升级”案例。 |
| Decisions 11–14、补充一 1、6–7、9、12–14、16、补充二 21–27、32、39 | `test_config_projections`、`test_config_projection_algorithms`、`test_config_projection_formats`、`test_config_projection_adapters`、`test_config_diff_service/cli/review`：固定独立期望，声明标签/停用主题/期刊/模型与 adapter 槽隔离、集合排序与有序次序、算法受控身份、六投影/基线独立版本与空值、只读脱敏 diff。资源字段拒绝按补充二 43，OCR true 拒绝按 42，不采用被后续修正的早期 OCR/资源开关建议。 |
| Decision 4、补充二 29 | `test_config_journals`、`test_config_journals_validation/persistence/cli`：ISSN 格式、校验位、规范化后冲突、期刊冻结与回放；不进入评分或投影。 |
| Decisions 8、15–16、补充一 15、18、补充二 33–34、37 | `test_config_transactions`、`test_config_transaction_cli`：独立连接竞争、跨进程握手、固定 5 秒锁等待、SQL/连接/进程故障、恢复重试、材料替换、孤儿引用拒绝；compile 与 check 的一致读视图。 |
| Decisions 15–17、补充二 36–41、46 | 原 A1 固定模块与 I/O 哨兵不变；所有 `test_config_*cli` 与架构模块、`test_a2_full_entry`：真实配置入口只拒网络，help 拒网络与数据库；公共 Contract、CLI、布局、投影依赖与版本演进、迁移及恢复文档交叉引用。#27 已交付 CLI 唯一前缀，公共 diff 仍为完整 ID。 |
| Decision 17、Testing Decisions/DoD、补充一 20、补充二 36–38、45–46、#25 澄清评论 | `test_a2_full_acceptance/entry/examples` 与 `test_a2_test_receipt`：同次结论及执行回执绑定、一次计划、实际临时库 head、完整格式与依赖、固定材料哈希、旧格式/缺项/漂移/中断拒绝、固定用例 skip/deselect 拒绝、无覆盖旧结论、真实示例回放和 CLI；保留 A2-01 共存和 A1 历史含义。 |

配置、持久化、投影与 CLI 的公共契约分别见
[运行配置](../contracts/runtime-config.md)、[阶段投影](../contracts/config-projections.md)、
[adapter](../contracts/adapter-config.md)、[解析配置](../contracts/extraction-config.md)、
[历史查询](../contracts/config-snapshots.md)。迁移与中断恢复遵循运行配置中的 SQLite
短事务协议；它不是备份恢复。目录与领域定义核对 `intent/draft.md` §6 和 `CONTEXT.md`；
没有新增领域决策或变更快照/投影身份算法。

完整入口只有本次 A1、完整 A2、A3、A4 与 A5 通过时返回 0，否则非零。运行中断记为 incomplete；
在发布完整 A2 前发生的可捕获中断会得到 incomplete 结论。进程被强制终止或在最终
原子发布中被终止时可能没有完整结论，缺结论绝不等于通过；已有 #12 若仍
completed=false，同样不能继承历史成功。已有结论不可覆盖，修复后须用新 run_id
重新执行整套检查。

完整 A2 的未覆盖项包括阶段输入指纹、全量业务事实与 blob/artifact、task/lease 和
共享资格/可见性接口、doctor、运行日志、备份恢复、真实来源审计、Pi 供给与 RPC、
实际算法/Docling/Read、校准工作流/门禁、阶段 B 与自动精读。合成 fixture、配置
ready 和 A2 passed 都不能证明正式校准或阶段 B 就绪，stage A 与 live 恒未验收。

## 配置材料组装重构的兼容证据

`test_config_material_compatibility` 通过公共 check/compile/load 入口验证七类
YAML 材料。`tests/fixtures/config_material_compatibility.json` 的期望结果在修改
生产代码前，由 `e3a7ff3` 实现生成并固定：含 16 种选择组合的快照身份和 126 条
当前装载／历史回放的完整中文错误文本。测试以 UTF-8 字节比较错误与身份，
并核对快照正文哈希、删除来源后的回放、混合错误的首条消息，以及历史条目缺少
编译值时仍优先报告原始内容解码错误。新增模块共 152 个用例，另在旧实现上通过
同一套用例，避免把新实现的行为误当成兼容期望。

本次仅更新经审查的 `config/service.py` 源码绑定，登记新的
`config/material_assembly.py`，并在完整 A2 登记新增测试、用例数量与固定 fixture。
原 A1／A2-01 固定测试、冻结契约、快照格式、投影身份与 migration 均不变。
范围哈希只证明已审查的文件内容，不替代行为测试或真实执行回执。

## 验收共享判定原语

#30 将完整 A2 实际消费的同次文件绑定、固定文件哈希记录、回执完成状态与逐模块
计数、运行身份匹配及发布前字节复查提取到 `scripts/verification_checks.py`。
该模块不依赖 A2/A3 scope、原因词表或业务模块；调用方显式提供固定清单和预期
用例数。布尔值不能充当退出码或计数，缺失计数不会补成零。

共享模块只提供核对原语。各组仍负责自己的格式、前置结论通过要求、固定检查、
范围非空与一致性、依赖版本、真实迁移、业务格式及失败/中断原因；完整 A2 保留
原有格式 2、回执格式 1、原因词表和中断优先级。`acceptance_groups()` 仍在
`scripts/a2_full_acceptance.py`，运行组织器与不可覆盖的原子发布协议不变。
共享 helper 的完整字节与新增公共边界回归纳入完整 A2 固定清单，不扩展 A2 的
业务能力范围。原固定测试、兼容终端 fixture、A1/A2-01 格式、revision 和冻结契约
保持原身份；此重构不登记 A3 组，也不声明 A3 已通过。


## A3 备份创建与校验切片（#33）

新增独立备份服务/真实CLI/wheel/WAL与损坏拒绝回归，固定登记在
`scripts/a3_scope.py` 的 BACKUP 清单；本切片结果由 #35 的同次 A3 结论聚合。
本票只更新经审查的根 CLI 在两份旧 A2 scope 的源码哈希，其他既有绑定与固定测试
保持原字节。完整离线测试实际执行备份回归；#35 已显式并入 A3 回执范围。
批次 Contract 与既有组的判定责任分开，不新增运行组织器或改变旧结论格式。

## A3 独立结论

`<run_id>.a3.json` 的格式为 **1**，scope 固定为 `a3_artifact_backup_restore`，
`parent_issue=29`、`issue=35`。它通过原有唯一 `acceptance_groups()` 追加：
`required=True`、`dependencies=("A1", "完整 A2")`。依赖只安排顺序；A3 自己检查两份
同次前置均 `status=passed`、各自 verified 严格为 true，A2-01 仍为非必需历史组。

当前七份主要文件是基础证据、A1、A2-01、完整 A2、A3、A4、A5；
`<run_id>.pytest.json` 是额外第八份绑定对象。没有回执、没有结论或没有完整执行都不能
宣称通过。完整计划只执行一次；A3 不自行再启动 pytest 或复制运行组织器。

| 字段 | 判据与含义 |
| --- | --- |
| format_version、scope、parent_issue、issue | A3 自身固定格式/范围；不重标 A1/A2 历史格式 |
| run_id、evidence_file/sha256 | 本次文件名、内容身份、#12 固定 scope 与字节哈希一致 |
| a1_conclusion_file/sha256 | 同次 A1 文件；内容须等于执行器返回值，格式 1、issue 13、原 scope、verified true |
| a2_full_conclusion_file/sha256 | 同次完整 A2 文件；格式 2、issue 25、原 scope、verified true；它记录的证据/A1/回执名字与哈希也必须匹配 |
| pytest_receipt_file/sha256、test_execution | 同次回执格式 1；必须 completed=true、整数退出码 0，逐个 A3 模块收集/完整通过等于固定数，其余四计数为 0；布尔、浮点、字符串、负数与缺失均拒绝 |
| required_checks | 原六项固定顺序，status=passed、reason=none、严格整数退出码 0；缺项/跳过/失败拒绝 |
| test_modules、source_modules、fixture_files | 每个显式路径的 expected/actual SHA-256 与受控结果；清单非空，测试清单和计数键集合必须一致 |
| environment | 实际 Python、SQLite、Alembic、SQLAlchemy、PyYAML、Pydantic、Typer 版本；缺依赖失败，不追加 #12 字段 |
| migration_revision | 另建临时 SQLite，真实 base→head 后读取唯一 alembic_version，并核对实际随包 head 与固定 a405_pi_cleanup_execution；失败/未知新 head 拒绝，无用户库参数 |
| format_versions | artifact=1、blob_layout=1、backup=1、backup_database_revision=a405_pi_cleanup_execution，逐项核对实际常量 |
| code、worktree_sha256、lockfile_sha256 | 本次实际身份完整、等于运行前基线、等于两份前置和基础证据的对应身份 |
| status、a3_verified、capabilities | 仅无任何失败原因时 passed/true；六项保守共用整组状态，不根据部分通过或空集合独立宣称业务能力 |
| stage_a_verified、live_verified、not_assessed | 前两项恒 false；后者明确列出全部尚未验收能力 |

`capabilities` 明确分为 artifact_publication、migration、wal_backup、
manifest_verification、isolated_restore、restored_queries。它们只描述本次固定离线范围；
不从磁盘空集合推导论文事实、阶段指纹、attempt/lease、共享资格/校准可见性、报告重建、
任务续跑、doctor/日志、Pi 执行/环境恢复、Docling/Read、真实来源、NAS、阶段 B 或自动
精读资格。这些名称均在 `not_assessed` 保留，A3 passed 不自动关闭/改写父 Issue #29。

共享 `verification_checks` 真正承担同次文件绑定、固定文件哈希、回执头/计数与身份核对；
各组继续负责范围、版本和原因。发布前复查证据、两份前置与回执的字节，并重新比较两份
前置文件内容与返回值。捕获中断为 incomplete；最终发布中断/强杀可能没有 A3 文件，
已有 A1/A2 结论保留，入口不能把完整 A2 passed 当作整体成功。A3 使用同一不可覆盖的
`publish_conclusion`，不覆写旧结论来修复失败。

原因词表由 `A3ReasonCode` 定义，只有受控中文指引与可选的已登记文件/模块/依赖名，
不保存测试名、参数 ID、skip 理由、捕获输出、原始异常、配置、Prompt、正文或凭据：

| code | 含义 |
| --- | --- |
| evidence_unavailable | 本次基础证据不可读 |
| binding_mismatch | 同次文件名/run_id/字节哈希/返回值或前置的反向绑定不一致 |
| format_mismatch | 基础证据、前置或回执格式不受支持，包括布尔版本 |
| prerequisite_not_passed | A1 或完整 A2 本次未通过，依赖登记不提供通过继承 |
| check_not_passed | 固定六项未全部实际通过 |
| scope_drift | 显式清单缺失、字节漂移或计数键集合不符 |
| dependency_unavailable | 必需实际依赖版本不可得 |
| migration_unavailable | 实际临时库迁移失败/读取失败/出现未登记 head |
| storage_format_drift | 存储/备份格式常量与固定版本不符 |
| identity_changed | 运行基线、当前身份或前置身份不一致 |
| run_incomplete | 捕获中断、前置/证据/回执未完成，优先得 incomplete |
| test_execution_not_passed | 固定模块实际执行不足，或回执缺失/无效 |

### 父规格与三轮裁决覆盖

固定范围在 `scripts/a3_scope.py`：已有分票清单显式聚合，逐模块用例数独立收集核对后
登记，运行时不扫描目录生成自己的期望。回执插件只增加这组显式模块，完整 A2 继续仅
校验自身固定集合，允许回执包含 A3。当前各 scope 的 revision 显式登记为 a405_pi_cleanup_execution；
新 migration 字节只进入 A3 清单，不扩大 A2 的业务范围，旧 a201 文件保持原字节。

| 父规格/裁决 | 本次固定公共回归 |
| --- | --- |
| Decisions 3–5、评论二/三的固定词表、身份向量与严格角色 | test_artifact_contract、test_extraction_artifacts：独立字面量 SHA-256/制品向量、完整角色、共享内容、格式/非法输入拒绝 |
| Decisions 6–8、评论一/二的文件先发布与路径权限 | test_artifact_store、test_extraction_artifacts：分段输入、只读不可变、无覆盖、根内链接拒绝、真实登记、幂等、独立进程竞争与部分发布/事务中断重试 |
| Decision 9/19、评论一的原子迁移、评论三的绑定边界 | test_storage_migrations：真实 a201→a302、base→head、原子 DDL/stamp 回滚重试、旧快照字节/身份/回放、约束与非法 revision 分类；test_a3_acceptance 另拒未登记新 head |
| Decisions 10–12、评论一 WAL/DELETE 陷阱、评论三并发收缩 | test_backup_service：主文件复制负对照确实丢已提交事实；在线副本保留提交、排除未提交，固定后新提交留以后；不新增备份×并发发布专门测试 |
| Decision 13、评论一/三只读与清单外条目 | test_backup_integrity、test_backup_service：全量哈希、登记双向匹配、配置公共回放、staging/WAL/SHM/journal/多余空目录拒绝；成功和失败均比较字节和目录集合 |
| Decisions 14–15、评论二的隔离恢复/目标规则 | test_restore_service、test_restore_failures：原库/配置/内容根改名后新进程查询、回放、读取；独立 inode、移动根、目标保护、正常并发占用与复制/发布强杀；显式 upgrade 回 WAL，历史事实不变 |
| Decisions 16–18、评论三 help 六锚点 | test_backup_cli、test_restore_cli、test_backup_wheel：真实安装 CLI、隐私/中文/0或2、原 I/O 哨兵下 help、本次 wheel 无 Git，未运行 NAS 或模型 |
| Decision 20、评论一第五部分/评论三的同次证据 | test_a3_acceptance、test_a3_test_receipt、test_a3_entry：严格计数、回执/前置/材料/身份漂移、旧格式/旧运行/缺失/中断拒绝、最终发布无覆盖；原 entry/compatibility/integrity/run 回归同步覆盖第五份主要文件 |
| Decision 21、完整并行切片组合 | test_a3_combination：两个完整配置快照、单文件＋extraction 四角色共享 blob；原根移走，新进程 CLI/公共服务完整回放/读取、升级后保持历史事实；未来业务能力显式未验收 |

#35 仅对本次追加组所必需的旧入口测试/终端 fixture、验收脚本与 wrapper 字节逐项重绑；
原 A1 固定资产、旧 A2 support/哨兵、四份契约与旧 migration 保持原字节。新 A3 support
组合历史材料工厂，只重写临时 fake-check 回执 writer，既不修改 copied scope 来放宽
生产判据，也不 stub A3、删除必需组或动态刷新期望。终端 fixture 保留八个历史 case 的
全部原有行，只按本票声明的原因/状态追加 A3 行，并继续完整字节比较。

范围与公共行为交叉引用：[制品](../contracts/artifact-store.md)、
[备份/恢复](../contracts/backup-restore.md)、[运行配置](../contracts/runtime-config.md)、
[阶段投影](../contracts/config-projections.md)。


## A4 独立结论（#36/#45）

`<run_id>.a4.json` 格式 1、scope `a4_pi_supply_lifecycle`、parent_issue=36、issue=45。
沿用唯一固定计划和回执插件，A4 不再启动 pytest；最终入口要求所有 required 组本次通过。
A4 交付时六份主要文件另加回执共七份；追加 A5 后主要文件七份、含回执共八份。
测试前失败可无回执，仍尽力发布失败/未完成结论。
最终发布中断或 I/O 错误传播非零，已有前置与历史文件保持原字节，不覆盖或借用历史成功。

A4 独立核对本次基础证据、A1、完整 A2、A3、回执文件名/run_id/实际 SHA-256，前置
内容必须等于写出器返回值。A1/fullA2/A3 的范围、issue、严格整数格式、passed/verified
以及相互反向绑定均须匹配。证据仍是原六项固定检查，全部真实整数 exit_code=0。
发布前重查全部输入文件字节、三份前置返回值和运行前后 HEAD/dirty/工作树/lockfile。
环境记录实际 Python、SQLite 与六项依赖版本；真实独立临时库 base→head 后读取唯一 revision，
必须等于随包 head 和已登记 `a405_pi_cleanup_execution`，不读取用户库或接受任意新 head。

`format_versions` 从生产 SupplyManifest/CleanupPlan 的权威 Schema 读取实际 const，
核对 supply_manifest=1、derived-lock-v1、tree-v1、install-policy-v1、cleanup_plan=1、
library-install-window-v1、cleanup_tree=tree-v1、allocated-inode-v1；整数与布尔不混用。
`scripts/a4_scope.py` 固定登记每个实际 source/test/fixture 的完整字节哈希和逐模块正整数用例数，
由开发时独立收集和审查后写入；交付运行不扫描目录生成 expected、不刷新预期或降低分母。
回执 completed=true/整数 exit_code=0，每模块 collected=passed=固定N，其余 failed/skipped/
deselected/incomplete=0；缺失、少跑、仅收集、跳过、非法计数、漂移与中断均失败。

capabilities 单独列 prepare、verify、rebuild、activate、install_protection、cleanup_plan、
cleanup_execute、doctor、export、isolated_restore；十项保守共用整组状态，全部通过才完整 A4。
未批准 A4a/A4b 截断，不以空集合推断缺少能力通过。组合用例经公共服务准备/核验/重建、
激活、真实 flock 保护、生成并执行非空清理，再导出材料和备份隔离恢复配置、制品、检查/
激活/计划/清理审计；退役实例不复活，原根不可达仍能导出同字节 D5 证据。

`live_install_verified`、`rpc_verified`、`stage_a_verified`、`live_verified` 恒 false。
真实 prepare 的 install_check 只能在用户库 `pi supply show` 回查；#37 的一次性机制 spike
不替代完整离线能力或真实供给验收。not_assessed 保留 live/RPC、阶段 A/B、真实来源、NAS、
自动精读与实际 Pi 模型执行；没有成功布尔导入捷径。

原因沿用受控词表 evidence_unavailable、binding_mismatch、format_mismatch、
prerequisite_not_passed、check_not_passed、scope_drift、dependency_unavailable、
migration_unavailable、storage_format_drift、identity_changed、run_incomplete、
test_execution_not_passed；A4 中文建议独立，run_incomplete 优先 incomplete，其他原因 failed。
不回显原始异常、参数、测试名称、skip 理由、模型输入或子进程输出。

本次只对必要受影响的 A2/A3 源码、入口/兼容 fixture 字节重新审查绑定；旧业务范围、
optional A2-01、旧 migration、A1 固定测试与四份冻结契约保留。全部需求逐条归属见
[A4 父规格与评论对照](a4-requirements.md)。


## A5 独立结论（#47/#54）

`<run_id>.a5.json` 格式 1、scope `a5_stage_input_fingerprints`，issue=47、parent_issue=47。
生产登记处以 required=true 追加；只依赖同次 A1、完整 A2、A3，不依赖 A4 通过。
A4 仍是整体必需组：仅损坏 A4 专属供给向量时，A5 可以 passed，完整入口仍非零；
仅损坏 A5 向量时，A1/完整 A2/A3/A4 可以 passed，完整入口仍非零。这与前置失败
导致 A5 prerequisite_not_passed 的归因分别验证。

七份主要 JSON 加同次 pytest 回执共八份，仍只执行一次固定六项离线计划。
A5 不读取用户库，不另跑 pytest，不复制组织器。结论只保存格式、身份哈希与受控结果，
不保存论文文本、摘录、Profile、Prompt 或完整载荷。固定向量内仅有合成文本，其字节
以 fixture SHA-256 绑定，不复制到结论。原 A1 的 not_assessed（含 stage_fingerprints）
保留其历史含义；A5 能力只由新结论声明。

| 记录 | A5 独立判据 |
| --- | --- |
| run_id、输入文件名/SHA-256 | 基础证据、A1、完整 A2、A3、回执均来自本次；文件内容等于前置写出器返回值；前置的 evidence/A1/fullA2/receipt 反向链接同样一致 |
| 前置身份、格式与状态 | A1 issue13/格式1、完整A2 issue25/格式2、A3 parent29/issue35/格式1，固定scope，status=passed、verified严格true；A4不进入本组前置 |
| required_checks | lockfile/format/lint/types/tests/contracts 固定顺序全部通过，reason=none，严格整数exit_code=0；未执行、跳过或缺项失败 |
| 固定范围 | a5_scope 显式登记11功能测试模块412例，以及本组验收/入口/回执测试、生产源码、支撑与13个阶段输入向量文件；清单非空且测试清单与数量key完全对应 |
| test_execution | 回执格式1、同run、完成、严格整数exit_code=0；每模块collected=passed=固定正整数，其余四计数严格整数0；bool/float/str/负数/缺项、skip/deselect/collect-only均拒绝 |
| format_versions | 从真实生产只读stage输入配方与原投影权威读取：boundary/value/reuse/extraction各1；嵌套版本严格整数，bool不能冒充1，不复制scope期望作为实际值 |
| environment、migration_revision | 实际Python/SQLite/依赖版本，独立临时库真实base→head读取唯一a405_pi_cleanup_execution并与随包head匹配；不引入新migration |
| code/worktree/lockfile | 当前身份完整，等于运行前baseline、证据和三份前置；code.dirty在所有身份及baseline中必须是真正bool；基础scope的false标志拒绝0冒充 |
| 发布前复核 | 再查五份输入字节及三前置返回对象；篡改、串用和身份漂移拒绝；最终结论原子不可覆盖，捕获中断优先incomplete，发布I/O或强杀可能无结论并保持非零 |
| capabilities、未覆盖项 | boundary/value/reuse/extraction/payload_replay/comparison/isolated_restore_replay七项共用整组状态；全部通过才a5_verified=true；stage_a_verified/live_verified/rpc_verified恒false |

未验收项明确保留 Read/suggestion/report 指纹、论文事实映射、任务预算、资格选择、RPC、
Pi/Docling实际执行、正式校准工作流、真实来源、NAS、阶段 A/live与自动精读。
相同输入指纹不证明缓存存在或有资格复用，changed不刷新预算、不撤销人工决定、不改写正式分析。

### #47 正文与三轮评论对照

下表模块名省略 `tests/` 和 `.py`；输入契约与固定向量见
[阶段输入](../contracts/stage-inputs.md)。三条评论分别是
[实施前补充](https://github.com/MeteoBoy4/PaperRadar/issues/47#issuecomment-6265057026)、
[C1裁决](https://github.com/MeteoBoy4/PaperRadar/issues/47#issuecomment-6265245363)、
[第三轮补充](https://github.com/MeteoBoy4/PaperRadar/issues/47#issuecomment-6266736991)。
#54 [最终澄清](https://github.com/MeteoBoy4/PaperRadar/issues/54#issuecomment-6268582853)
固定本组依赖、七主要文件、历史范围与隐私边界。

| 正文/评论要求 | 已登记行为与未验收边界 |
| --- | --- |
| Decisions1–5、14–16、19；Stories1–5、17–20、24–26 | test_stage_inputs/replay/comparison/common_contract/architecture：唯一快照门面、四阶段封闭集合、就绪门禁、身份域/格式、严格拒绝、不可变、无I/O、脱敏只读比较；没有临时Read Schema或新事实表 |
| Decisions6–7；Stories1–7、20–23；补充一的薄配置矩阵/书目约束 | test_stage_input_value/comparison/dependencies/common_contract：精确Unicode/换行、截断标记、已启用主题仅value、真实投影传播、Read/期刊tier/adapter审计隔离；主题权重字段不存在，书目字段拒绝不等于论文事实映射端到端验收 |
| Decisions8、11–12；Stories8–10、14；C1全文；第三轮一 | test_stage_input_extraction/extraction_reuse：PDF哈希+extraction投影、纯未来normalization fixture及真实compile拒绝；不消费题名/DOI/摘要，阶段F的封面识别质量分歧保留为Contract已知未决问题，不修改§4.9 |
| Decisions9–13；Stories11–16；补充一来源/正文闭包；第三轮五 | test_stage_input_reuse/extraction_reuse：非空有序摘录、权威ID/kind、结构化payload内容身份、正文extraction指纹+reading/evidence_map、真实ArtifactStore的manifest审计隔离、同次一致正文、同源输出context；不判断来源存在/合法/质量或实现选段 |
| Decisions14–17；Stories17–25；第三轮一/三/四/五 | test_stage_input_common_contract/replay/comparison/value：严格小写SHA-256、原因封闭脱敏、非法Unicode拒绝、回放不读配置/数据库/制品库、合成独立字面量向量、生产算法v2拒绝；stage_inputs只单向依赖config/screening公共面 |
| Decisions15、18–19；Stories26–27；补充一历史恢复/副作用与第三轮五 | test_stage_input_recovery + stage_input_process/recovery_support：真实非空备份隔离移动、恢复后get_artifact成员、历史投影重建、不同hashseed/cwd/无序构造顺序、错误历史快照拒绝、数据库字节不变；不改人工决定/分析，后续消费者义务留在Contract |
| Decisions20–21；Story28；补充一七/八、第三轮二/六、#54最终澄清 | test_a5_acceptance/entry/test_receipt及既有entry/integrity/compatibility/run：显式required登记、三前置、独立格式/实际迁移/固定哈希/严格回执、A4与A5归因、缺失漂移篡改中断拒绝、历史不覆盖、七主要文件、A1历史not_assessed原样；不宣称完整阶段A/live |

#54 仅重绑接入影响的旧源码、wrapper、入口断言和终端fixture；旧用例分母保持原数。
固定哈希按 a2_scope wrapper、完整A2 scope、A3 scope、A4 scope、A5 scope 顺序登记，
避免循环绑定。终端fixture的八种历史case原有行保留，按已确定A5判据追加新行；
交付运行不扫描目录生成expected，不刷新向量或降低分母。旧证据保留，任何修复用新run_id重跑。

### #69 首条 DOI 论文事实路径（尚未注册 A6）

本切片新增公共论文事实服务、严格 DOI/文本规则、有界出版者原始来源、唯一身份与
完整候选引用式修订、只读 paper show/trace、a601_paper_facts 迁移与非空本机恢复。
独立用例置于 test_paper_identity/inputs/service/acquisitions/cli/process/migrations/backup 新模块，
固定 DOI/文本向量位于 tests/fixtures/paper_facts_v1.json；旧固定模块的用例分母不变。
真实进程屏障验证两进程竞争、5 秒忙锁、发布后/事务中/提交后未返回的强杀恢复，
以及两次 SELECT 之间提交的不可见性。移除显式 BEGIN 的故障实验必须使后一用例失败。
备份副本与恢复路径拒绝外键合法的跨版本 provenance、同版本错获选候选、缺失获选字段、
候选正文篡改与错来源 kind；重算外层数据库哈希不能掩盖损坏。

| 重审范围 | 原因与保持项 |
| --- | --- |
| a2_scope、完整 A2、A3、A4、A5 的 migration_revision 与旧测试当前-head断言 | 实际 head 追加 a601，历史 a405 migration 原字节不改；旧分母不变 |
| cli.py 及绑定它的 A2/完整A2/A3/A4 | 注册 paper 只读组并说明用途；root 与新 help 禁外部 I/O 验证 |
| backup manifest/service 与 A3 绑定 | 显式支持 a601，在固定副本上增加完整论文历史语义校验；未来 head 仍拒绝 |
| 受影响旧验收测试/历史升级测试及下游scope字节 | 当前head或已登记上游scope发生必要变化；不刷新旧证据，不追加旧模块用例 |

逐项旧哈希/新哈希/原因与最终重跑 run_id 由本次交付的独立重绑台账保存；台账在工作树外
生成，避免把最终 run_id 写入被同次身份哈希的材料。固定源码哈希按 a2_scope wrapper、
完整 A2、A3、A4、A5 拓扑重审，audit-verification-scope --json --collect 检查旧分母。
长门禁预留 30 分钟并先运行 dev-environment check，实际耗时及九份原始 JSON 以交付记录为准。
本次不注册 A6、不改写 A5 历史 paper_fact_mapping 未覆盖结论；跨来源、Feed、人工修正、
版本关系、输入映射、真实来源/LLM/Docling/RPC/NAS 与完整阶段 A/live 未验收。

#69 后续用户裁决另由 test_paper_acquisitions 覆盖乱序同值取得、复用候选不发布新响应大包、not_retained/空请求的原结果重试和同键异解析拒绝；backup 用活跃 WAL 中的非空取得事实验证隔离恢复，不变更 Feed D3。

#69 的最终重解析裁决由 test_paper_reparse 覆盖：完整声明必填、partial/economical拒绝、
同材料parser单调与同版本解析恒定、旧请求原结果、有效非空解释整体替换、不同材料缺项
不清空、全空v2保护，以及公共历史查询结合既有A5 builder证明旧文本输入保留/新摘要指纹改变。
完整历史重建/指纹链与正式映射留给#73，跨来源fallback留给#71/#74；这些不在#69提前实现。


### #70 Feed 发现切片（尚未注册 A6）

新用例独立置于 test_feed_registration/inputs/discovery/identity/arbitration/cli/process/migrations/backup，
不加入 A1–A5 固定分母。公共服务与真实 SQLite/ArtifactStore 覆盖规范 Feed URL、单 item 全字节指纹、
无 DOI 连续关联/唯一补 DOI、跨 Feed 同 DOI、身份冲突整笔拒绝、D3 A→B→A 只推进 last_seen、
完整重解析与 parser 单调、出版者优先/Feed 补缺与跨来源 fallback。既有 #69 Feed 拒绝负例改为缺真实 entry ID，
保留受控拒绝目的和用例数，不能在生产隐藏拒绝合法 Feed。

真实两进程覆盖重复发现、不同 Feed 同 DOI、补 DOI 竞争，发布后/事务中/已提交未返回的强杀重试；
真实非空 a601 数据含配置、制品、Pi 与出版者候选/作者/修订，从 a601→a602 升级，并在重建 DDL/stamp
故障或强杀后检查旧事实完整回滚。恢复从活跃 WAL 备份，原目录改名后在搬迁根的新进程只读查询，
保留无 DOI、无字段发现、全部解释、原始 DOI 书写与原文；a601 旧事实未知原书写为 NULL。
外键合法且重算外层哈希的 fingerprint、来源 payload、条目目标、解释归属、raw DOI、未使用 Feed URL
损坏都由 verify/restore 拒绝，批次不被修复。另以与写入口共用的 entry 校验覆盖空白、UTF-8 字节超限、
SQLite BLOB 非法 Unicode 形状；URL/时钟形状和首次/后续解释时点与发现边界的冗余一致性也由同一闭包校验拒绝。

重审仅为实际新 head a602 调整旧当前-head断言、未来 head fixture 的 down_revision、backup 显式支持门禁，
并依 a2_scope→完整 A2→A3→A4→A5 拓扑重绑实际受影响源文件与下游 scope 原字节。
旧分母及 A5 历史 paper_fact_mapping 未覆盖含义不变，不修改 a601 或旧证据，不注册 A6。
旧/新哈希、理由、最终 run_id 及九份原字节证据保存在工作树外的本票交付台账中。
未验证真实 Feed/guid 覆盖、上游 entry 稳定性、截断质量、parser 完整性、网络来源、LLM/Docling/RPC/NAS；
阶段 C 强冲突观察持久化与 parser 固定样本回归门禁保持。


### #74 组合备份与历史输入恢复（尚未注册 A6）

新增 `test_paper_recovery_combined/integrity/damage`，独立于 A1–A5 固定模块和分母。
所有成功事实由 PaperFacts/config/ArtifactStore 公共服务构造；SQL 仅用于只读检查与故意损坏。

| #74 验收要求 | 离线证据与边界 |
| --- | --- |
| 至少两篇、多 DOI/版本、四来源/冲突/人工、旧新配置 | paper_recovery_support 组合工厂与 combined：同一真实库，trace/show 全形状摘要及两阶段载荷散列比较；不携带原文到子进程 |
| 正式有/无摘要升级、旧预印本、never-selected | combined 两个正式摘要组合；明确历史 version/revision/snapshot，从未选中 selection=null，不跨版本补摘要 |
| 无 DOI 后补、跨 Feed、A→B→A | combined：同 UUID、发现/first-last-seen/候选/取得/修订保留，另有仍无 DOI 正例；Feed 回摆只 last_seen |
| 完整解释、fallback、新摘要、全空保护、重复取得 | combined：同材料 v2 缺摘要、registry 补缺追加 provenance 修订、v3 文本改变、v4 全空不清除，旧精确重试与轻量候选引用 |
| effective/endpoint_missing/requires_merge、零端点 | combined 与完整副本公共 validate_all；跨 Paper 不合并、关系-only 不造空版本，独立关系不撤销 |
| 真 WAL、禁原目录、恢复后再搬迁、独立进程 | combined：WAL 非空且最终事务进入副本；便携批次，audit 拒绝原根/改名根/原备份源与 SQLite URI/枚举；恢复及两个不同 cwd/hashseed 读者均为新进程 |
| 仅从恢复候选重建历史输入 | paper_recovery_reader 只接受 ID/revision/snapshot/独立哈希与长度，比较两阶段 fingerprint/payload SHA、完整字段依据/真实选择；无外部题名摘要/配置对象 |
| 共用语义入口且只解析副本 | integrity 首片 red→green；create 复制后统一调用 verify_contents，坏源字节 file_corrupt；damage 语义拒绝且原库/批次不变、目标不发布 |
| 重哈希且 FK 合法的代表性损坏 | damage：item/payload、跨版本 provenance、DOI 归属、错获选候选、缺完整修订字段、选择、原关系断言、错 kind；verify/restore registration_invalid，批次不修复 |
| 缺/坏 blob、未来 revision | damage：file_missing/file_corrupt/unsupported_revision；旧 a405 拒绝继续由 test_paper_backup 保护，不升级批次 |
| trace 可选字节核验与默认无 blob I/O | integrity：仅关系材料缺失/损坏时默认 trace 仍读，显式服务/CLI 受控拒绝且无原文；combined 子进程默认 show/trace/map 拒绝 blobs 根访问仍成功 |
| 无静默修复/历史变化 | combined：源库逻辑 dump、恢复库 dump/业务文件、便携批次字节前后一致；damage 成败批次均只读，失败无恢复目标；SQLite WAL/SHM 临时协调文件不当业务事实 |

不改变 backup format 1，不新增 migration，不改 a601–a604，不提前注册 A6；A5 历史
paper_fact_mapping NOT_ASSESSED 原样保留。必要源码哈希按 A2 wrapper→完整 A2→A3→A4→A5
拓扑重审，仅 backup/service.py 校验时点与传播 scope 变化；旧分母、旧原始证据不变。
旧/新 scope、TDD、实际 I/O/子集耗时与最终九份原 JSON/哈希保存在本票工作树外证据台账。
长门禁前执行 dev-environment check，留 30 分钟观察预算；#75 仍须集成后重新产生最终 run_id。

只证明离线历史重建；完整阶段 A、live、真实来源/截断检测、RPC、Docling/NAS、任务续跑、
资格/预算/校准均未验收。阶段 C parser 升级固定样本和强冲突观察持久化门禁持续未验。


## A6 独立结论（#67/#75）

`a6_scope.py` 将业务规格 #67 与最后验收子票 #75 区分登记。只有同次 A1、完整 A2、A3、A5
通过，固定六检查与完整严格整数回执匹配，固定测试/源码/合成材料无漂移，真实临时库
base→head 得到随包实际 head（#75 交付时为 `a604_version_relations`，当前为
`a704_screening_retry`），并且运行前后代码/工作树/lockfile 相同，才有
`a6_verified=true`。A4 不构成业务前置，但 A4 失败仍令完整入口非零。

格式期望固定为 `paper_facts/doi_rules/text_norm/feed_item_fingerprint/reason_catalog/mapping_result=1`、
boundary/value 输入 1 与 backup 1，实际值逐项读取生产权威。Feed 生产纯规则声明版本 1，
计算原始单 item 全字节 SHA-256，不改变既有字节语义。`mapping_result` 实际值从
`ScreeningMappingResult` 的 dataclass `format_version` 字段默认值读取，与固定期望独立核对，
不复制期望作为实际格式。bool/float 不能冒充整数格式或回执计数。

`capabilities` 固定十二项，`capability_evidence` 逐项记录已绑定的固定用例与材料映射，
见 `tests/fixtures/a6_capabilities.json`；version_selection/field_arbitration/historical_rebuild/
isolated_restore 明确包括 #74 完整组合库和独立进程读者。论文事实业务测试模块与 A6
协议测试使用独立固定分母，A1–A5 旧模块/分母及 A5 `paper_fact_mapping` 历史含义保留。
collect 只审核分母；少执行、skip、deselect、collect-only、缺材料、篡改、未知格式、
身份漂移、中断和缺终态均不能形成完整通过。结论不可覆盖，状态仍由既有终态协议查询。

先完成代码/帮助/终端 fixture，再按 A2 wrapper→完整 A2→A3→A4→A5→A6 重审绑定，
无自绑定或反向循环。旧/新 SHA、理由及复验 run_id 台账置于工作树外，不参与自身 run_id
身份哈希。先合入最新 integration、冻结提交，长门禁前只读检查开发环境，留至少 30 分钟
观察预算；真实退出码 0 后再核对 status=passed/verified、applicability=same。分支运行仅为
阶段证据，最终集成与审查修复后的工作树须另生成正式 run_id，旧成功不能替代新身份。

stage_a_verified/live_verified/rpc_verified 恒 false。真实来源和所有来源假设、parser 真实
完整性、HTML/截断检测、merge/undo/arXiv/PMID、metadata_ready/eligibility、任务预算与完整
可见性、RPC/Pi/Docling/NAS、校准/自动精读及完整阶段 A 未验收。阶段 C 真实 Feed 接入前
必须补强冲突观察持久化；parser 升级前必须固定样本回归并声明关键字段减少，离线 A6
不绕过这两项门禁。[完整规格与评论对照](a6-requirements.md)列出具体能力、测试及未覆盖项。


## A7 独立结论（#76/#84）

当前完整入口为九份主要证据/结论，加 pytest 回执与 terminal 共十一份 JSON。
以上 A3–A6 分票小节中的八/九/十份均对应其交付时的历史范围，不改写原 JSON。
`a7_scope.py` 区分父规格 #76 与验收子票 #84；`.a7.json` 格式 1 与状态读者解析能力
同提交交付。A7 直接前置精确为同次 A1、完整 A2、A3、A5、A6，A4 继续为总门禁必需。
缺前置/失败、旧 run、错 scope/issue/格式/verified 或前置反向链接不一致均不得通过。

`FORMAT_VERSIONS` 固定 screening_tasks/task_reason_catalog/task_query_result=1、
boundary/value stage_inputs=1、backup=1。实际值分别读取生产常量、真实
TaskQueryResult 默认值与输入/备份权威；bool/float 不得冒充整数。临时库真实
base→head 必须到达随包实际 `a704_screening_retry`，不以期待常量替代迁移探针。
`task_query_result` 与 `task_reason_catalog` 不新增到四份 Frozen Contract，
`CONTRACT_NAMES` 和原契约检查集合保持。

固定材料包含全部任务能力、#77 的权威 validation.py 与独立严格 JSON 93 例、
#78–#83 的 283 例、#84 协议负例和实际 worker/隔离读者/fixture。预期分母先按测试源
及参数化人工审阅，collect 仅核对；不自动用实测数回填。真实 pytest 插件逐模块记收集、
通过、失败、跳过、取消选择和未完成数。缺失、少执行、skip、deselect、collect-only、
错误回执/整数、材料漂移和中断都不能使 `a7_verified=true`。
15 项 capabilities 逐项映射固定用例和材料，完整追溯见
[A7 验收矩阵](a7-requirements.md#a7-08--84-独立验收与可信终态)。

结论还绑定六项基础证据、各前置实际字节哈希、真实回执和同次代码/工作树/lockfile；
发布前再次复核。控制方 terminal 必须绑定全部登记组且完整一致，缺失/篡改终态不显示
整体通过。最终须等待真实 `check-offline` exit0，再以只读 `verification-status` 核对
passed/verified 且 applicability=same；历史成功不能替代当前运行，查询不修补旧证据。

源码/帮助/回执与旧绑定按 scope audit 的 downstream 同波重审，原固定用例不删、
分母不降；A7 scope 不哈希自身。旧/新 hash、身份、理由、最终 commit/run_id 与原始
十一份 JSON 留在工作树外台账，最终 run_id 不写回受哈希材料。

A7 仅覆盖 boundary/value 离线 test 执行边界，rpc_verified/live_verified/stage_a_verified
恒 false。not_assessed 明列 rpc_compatibility、pi_execution、real_model_usage_cost、
original_title_language_production_source、metadata_ready、complete_eligibility、daily_quota、
two_stage_orchestration、suggestions_decisions、calibration_visibility、reuse_tasks、
extraction_tasks、read_tasks、merge_budget、screening_cli、paper_trace_cli、nas_restore、
stage_a、live、automatic_fulltext_reading。test 输出不作为生产筛选或校准依据。
