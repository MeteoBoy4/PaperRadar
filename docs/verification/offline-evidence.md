# 离线验证证据

运行仓库根目录的 `./scripts/check-offline`。脚本按固定顺序实际执行 lockfile
一致性、格式、静态规则、类型、全部离线测试和已选择的冻结契约一致性检查。每次
运行会在被 Git 忽略的 `verification-runs/<run_id>.json` 生成新文件；终端最后打印
准确路径和结果。重跑不会覆盖旧证据，也不会沿用旧检查状态。

证据格式版本为 `1`，字段含义如下：

| 字段 | 含义 |
| --- | --- |
| `run_id`、`started_at`、`finished_at` | 本次随机运行标识及 UTC 时间。未正常结束时 `finished_at` 可为 `null`。 |
| `completed`、`overall` | 运行是否走到结尾；总结果固定为 `passed`、`failed`、`incomplete`。只有所有检查本次均实际通过才为 `passed`。 |
| `scope` | 仅证明 Issue #12 的已实现离线范围。`full_a1_verified` 和 `stage_a_verified` 固定为 `false`；`not_assessed` 列出未作验收声明的能力。 |
| `code` | `git rev-parse HEAD` 的提交 SHA 与运行前 `git status --porcelain` 推导的未提交变更标记。无法取得时为 `null`。不保存文件名或 diff。 |
| `lockfile_sha256` | 本次工作树 `uv.lock` 的实际字节哈希；不可读取时为 `null`。 |
| `environment` | 通过项目锁定环境取得的 Python、Pydantic、Typer、pytest、Ruff、mypy 版本；无法取得时值为 `null`，`missing_reason=environment_unavailable`。 |
| `contracts` | 本次契约检查计划选择的名称、声明版本与磁盘 `schema.json` 实际字节 SHA-256；文件不可读取时哈希为 `null`。是否一致由 `contracts` 检查结果判定。 |
| `checks` | 每项固定 `id`、`status`、`reason`、`exit_code`；失败项另有固定的中文 `help_zh`。不保存命令参数、原始输出或异常文本。 |

`status` 只能是 `passed`、`failed`、`not_run`。`reason` 只能是 `none`、
`not_started`、`skipped`、`prior_failure`、`interrupted`、`exit_nonzero` 或
`launch_error`。`exit_nonzero` 附进程退出码；`launch_error` 表示命令无法启动；
中断时当前检查记为失败，后续检查记为未运行，`overall=incomplete`。首个失败会
停止后续检查，未运行项不会复用先前运行的通过结果。运行时先写出所有检查均为
`not_run` 的新文件，每项结束后原子更新；突然终止时已有文件保持
`completed=false`，不能当成通过。

失败时按 `checks[].id` 和 `help_zh` 定位并单独重跑检查。脚本有意不保存也不回显子进程的原始输出，
避免测试失败信息泄漏 Profile、摘要、正文、Prompt、secret 或模型响应。维护者可按
`scripts/offline_evidence.py` 的固定计划单独重跑对应检查取得本地诊断；不要把
含敏感输入的原始输出加入验收证据。`contracts` 项的详细失败类别也可通过已存在的
`paper-radar contracts check` 命令单独查看。

证据记录的是一次实际执行，不等同于 A1 全部完成、阶段 A 完成、真实来源通过或
模型能力可用。新增已实现冻结契约时，同步扩展脚本的 `CONTRACT_NAMES` 选择清单，
使检查命令与证据范围一起更新。
