# 离线验证证据

运行仓库根目录的 `./scripts/check-offline`；`./scripts/check-offline --help` 只打印中文
帮助，不启动检查或写入证据。脚本按固定顺序实际执行 lockfile
一致性、格式、静态规则、类型、全部离线测试和已选择的冻结契约一致性检查。每次
运行会在被 Git 忽略的 `verification-runs/<run_id>.json` 生成 #12 离线证据，
并在 `verification-runs/<run_id>.a1.json` 生成独立的 #13 A1 结论；终端最后打印
两个准确路径和结果。重跑不会覆盖旧证据或结论，也不会沿用旧检查状态。入口使用
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
`run_id` 和结论，旧结果保留。脚本返回 0 仅当新结论通过；否则返回非零。
若 uv 尚未启动 Python 或进程被强制终止，可能没有本次结论文件；前者保留 uv 的
非零退出码，后者已有的 #12 证据仍不能作为 A1 通过。

固定 A1 范围包括工程与帮助、三种输出的完整验证、原因组合、四份正式快照、
单份和批量导出/检查、冲突与恢复、隐私和模块边界、机器证据记录。该结论复用
现有离线测试和固定 `check-offline` 计划，不将未实现规则当作通过。`not_assessed`
明确列出阶段 A 剩余的 RuntimePlan、持久化、指纹、任务与共享接口、doctor、
结构化日志、备份恢复和真实来源审计，以及阶段 B 与自动全文精读；A1 通过不开放
这些能力，也不自动修改父 Issue。
