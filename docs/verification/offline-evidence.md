# 离线验证证据

运行仓库根目录的 `./scripts/check-offline`；`./scripts/check-offline --help` 只打印中文
帮助，不启动检查或写入证据。脚本按固定顺序实际执行 lockfile
一致性、格式、静态规则、类型、全部离线测试和已选择的冻结契约一致性检查。每次
运行会在被 Git 忽略的 `verification-runs/<run_id>.json` 生成 #12 离线证据，
并在 `verification-runs/<run_id>.a1.json` 生成独立的 #13 A1 结论，
在 `<run_id>.a2.json` 生成 #16 A2-01 结论，在 `<run_id>.a2-full.json` 生成
#25 完整 A2 结论；终端打印本次四个主要路径及结果。测试另外生成同次
`<run_id>.pytest.json` 脱敏执行回执。整套检查仅执行一次，各文件
共享本次 `run_id` 并绑定实际证据哈希。仅本次 A1 与完整 A2 均通过时入口返回 0，
A2-01 继续独立记录原有范围。离线测试与迁移验收使用临时数据库，不操作用户数据库。
重跑不会覆盖旧证据或结论，也不会沿用旧检查状态。入口使用
`uv run --offline --locked` 启动项目 Python；若 uv 在启动 Python 前失败，
本次尚无证据文件，终端会收到 uv 的非零退出码。

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

完整 A2 另由自己的判据验证同次 pytest 回执、证据和已发布 A1，并在发布前再次
核对这些文件的实际字节绑定；它没有 A2-01 通过依赖。各组的原因、格式、严格性与
中断恢复继续由自己的验收模块维护。A1 恢复沿用自己的结论状态；A2-01 发布中断
即使补写为 passed，也继续把中断传给完整 A2。最后发布阶段的中断仍可能没有
完整结论，不会覆盖已发布文件来修复状态。

三组的 `write_*_conclusion` 兼容入口共用
`scripts/verification_publication.py` 的 `publish_conclusion`：保持原 JSON
序列化规则，临时文件独占创建、flush/fsync 后通过 `os.link` 原子发布；目标已存在
即失败，finally 清理临时文件。运行中证据与回执仍可原子更新，不使用此最终发布入口。

新验收组以显式代码加入登记，提供自己的判据，调用同一个最终发布函数；可选提供
组内中断恢复规则，无需在组织核心增加组名称分支。当前回执只记录 `a1_scope` 和
`a2_full_scope` 的固定测试模块合集。新增组若需要扩大逐模块执行证明，必须在
后续任务中显式扩展回执范围；本轮没有自动发现插件、独立检查计划或动态调度。
测试中的合成组只证明组织扩展能力，不代表新增产品验收能力。

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
`run_id` 和结论，旧结果保留。完整入口另须本次完整 A2 通过才返回 0。
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
| `migration_revision` | 另建临时 SQLite、真实 base→head 后从库内 alembic_version 读取唯一 revision，并核对随包 head 与固定的 a201_profile_snapshot；未登记新 head、升级失败或读取失败均拒绝。无用户数据库参数。 |
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

完整入口只有本次 A1 与完整 A2 通过时返回 0，否则非零。运行中断记为 incomplete；
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
