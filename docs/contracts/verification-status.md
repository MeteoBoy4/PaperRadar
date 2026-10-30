<a id="离线验证状态查询55"></a>

# 离线验证状态查询

## 用途与范围

这是开发验收工具，不属于 V1 论文业务 CLI。它只读核验同次离线材料的进度、控制方终态与当前代码适用性。运行：

```bash
./scripts/verification-status <32 位小写十六进制 run_id> \
  --runs-dir verification-runs [--json]
```

默认目录是仓库的 `verification-runs/`；入口先切换到仓库根，因此显式相对
`--runs-dir` 也相对仓库根解析。入口使用现有项目 Python：默认 `.venv/bin/python`，
`UV_PROJECT_ENVIRONMENT` 可指定绝对路径或相对仓库根的环境目录。不启动 uv 或同步环境；
解释器不可执行时返回 1，提示先准备环境，此时不输出状态 JSON。
解释器可用时，`-h`/`--help` 只打印中文帮助并返回 0；`--json` 输出 JSON，否则输出中文文本。
查询只读文件和 Git 身份，不执行检查、迁移或补写历史记录，不写字节码或 Git 索引。
不保存、回显原始异常、未知参数、测试参数、论文或配置载荷。

查询退出码：0 表示已核对的历史通过；1 表示失败、未完成、未证实或材料不可得；
2 表示缺少参数、未知选项等参数解析错误。作为位置参数解析成功、但不满足 32 位小写
十六进制的 `run_id` 返回 1，状态为 `unavailable/run_id_mismatch`，不读取该标识对应文件。
历史通过的退出码与当前工作树适用性分开；自动化若要求适用于当前代码，还须核对
`applicability=same`。

<a id="输出格式-1"></a>

## 输出格式 1

JSON 与中文文本展示相同事实。JSON 使用以下受控字段：

| 字段 | 语义 |
| --- | --- |
| `format_version` | 严格整数 1 |
| `status` | `passed` 通过；`failed` 失败；`incomplete` 中断/不完整；`unavailable` 材料不可得；`unconfirmed` 历史结果/终态未证实 |
| `reason` | 见下表；永不包含原始异常正文 |
| `phase` | `checking` 检查执行阶段；`publishing` 检查已收尾、结论发布阶段；`finished` 控制方终态已核对；`unknown` 无法判断 |
| `current_check` | 基础证据尚无 `finished_at` 时，固定计划中首个 `status=not_run` 且 `reason=not_started` 的检查 ID；否则为 `null`。不是进程存活证明 |
| `checks_passed`、`checks_total` | 固定计划的通过数和总数 |
| `elapsed_seconds` | 基础检查的开始到结束时间差，取不小于 0 的整数秒；未结束时相对查询时间；无法解析为 `null`。不含结论发布时间 |
| `tests` | 同次回执各模块 `collected`、`passed`、`failed`、`skipped`、`deselected`、`incomplete` 六个严格非负整数计数之和；不可解析为 `null`。仅供进度参考，不证明成功 |
| `exit_code` | 核对终态后展示的控制方退出决定，其他情况为 `null` |
| `applicability` | `same` 当前 HEAD、dirty 标记、工作树哈希和 lockfile 哈希同身份；`different` 身份比较不符；`unknown` 尚未完成终态核验或缺少可比较的工作树哈希 |

中文文本也展示输出 `format_version`；`tests` 以计数字典展示，键和数值与 JSON 相同。

| `reason` | 含义 |
| --- | --- |
| `verified` | 终态、执行事实、必需组、回执及字节/身份链接均通过 |
| `terminal_missing` | 缺少终态；不区分旧协议、仍在运行、发布崩溃或被强杀 |
| `material_unavailable` | 基础证据或已登记材料缺失、不可取得（含已登记可选组） |
| `invalid_document` | 非对象、坏 JSON、错误字段类型、检查计划不符或非法/重复组登记 |
| `unsupported_format` | 基础证据、回执或终态格式未知，或组格式不受读者支持/与本次登记不符 |
| `run_id_mismatch` | 标识不合法，或内容不属于所查询运行 |
| `binding_mismatch` | 材料哈希、身份、返回对象或文件反向链接不符 |
| `checks_not_passed` | 固定检查未真实完整通过 |
| `group_not_passed` | 本次登记的必需组未全部通过 |
| `receipt_not_passed` | 回执未完整成功或缺少模块记录 |
| `exit_nonzero` | 控制方退出决定非零 |
| `interrupted` | 基础检查或发布被中断，或必需组不完整 |

没有终态时，`phase` 仅描述最后可读证据的进度，不声称此刻仍在执行。
`checking` 与 `publishing` 都可搭配 `unconfirmed`；已记录中断则为 `incomplete`。
因此 pytest 的回执已完成、进程仍未退出，以及检查结束、结论尚未发布完，都不会
显示整体 `passed`。查询不轮询、不检查 PID、不依赖文件时间。

<a id="控制方终态格式-1"></a>

## 控制方终态格式 1

控制方在实际等待固定检查执行器返回、依次取得全部登记组的发布结果后，
最后不可覆盖地原子发布 `<run_id>.terminal.json`。JSON 使用 UTF-8、键排序、两空格缩进，
末尾有换行；目标已存在时不覆盖。字段如下：

| 字段 | 语义 |
| --- | --- |
| `format_version`、`run_id` | 严格整数 1、同次运行标识 |
| `exit_code` | 控制方将返回的严格整数退出码；全部必需组通过且控制方未中断时为 0，否则为 1 |
| `interrupted` | 控制方是否记录了组发布中断；基础检查中断还要读取其自身证据 |
| `code`、`worktree_sha256`、`lockfile_sha256` | 本次开始时采集的运行身份 |
| `evidence_sha256`、`pytest_receipt_sha256` | 基础证据和回执的实际字节哈希；失败运行可能没有回执，哈希为 `null` |
| `materials_consistent` | 发布文件名、run_id、磁盘对象与各写出器返回对象是否相符 |
| `groups` | 本次按发布顺序冻结的全部组，含可选组；每项保存 `suffix`、严格布尔 `required`、`sha256`、`format_version` |

组清单必须非空且至少有一个 required 组。组后缀限 `.[a-z0-9-]+.json`，不得重复或
占用 `.pytest.json`、`.terminal.json`。`required` 必须是严格布尔值，组格式必须是严格整数。
查询以本次终态的登记清单为准，不导入当前验收组注册表；当前生产组的增删不改变历史范围，
也不为旧终态补组、补文件或扩大证明范围。读者支持的后缀与格式为：

<a id="a8-格式与历史输出范围"></a>
<a id="a9-格式与当前输出范围"></a>
<a id="a10-结论支持"></a>

| 组后缀 | 支持的格式 |
| --- | --- |
| `.a1.json`、`.a2.json`（A2-01） | 1 |
| `.a2-full.json`（完整 A2） | 2 |
| `.a3.json`、`.a4.json`、`.a5.json`、`.a6.json`、`.a7.json` | 1 |
| `.a8.json`、`.a9.json`、`.a10.json` | 1 |

表外后缀或格式返回 `unsupported_format`，包括可选组；不能因终态自声明格式就通过。
组文件的格式还必须与终态登记一致。读者不重新执行各组业务判据，也不单独重算
`a9_verified` 等组内结论字段；它核验已发布组状态、格式、同次身份与字节链接。

格式 1 的检查计划固定为 `lockfile`、`format`、`lint`、`types`、`tests`、`contracts`，
顺序也固定。读者按这份已发布的历史定义校验 `checks`、展示总数，不调用当前的
`default_checks()` 来解释旧运行。格式 1 出现缺项、乱序或新增未知检查均以
`invalid_document` 拒绝，不静默忽略；当前执行计划的改变不改写已发布历史结果。

### 通过与绑定规则

`passed/verified` 必须同时满足：

- 终态退出决定为严格整数 0，且未记录中断；基础证据格式为 1、完整且 `overall=passed`，
  固定六检查均为 `status=passed`、`reason=none` 且严格整数退出码为 0。
- 全部 required 组的 `status=passed`。组发布中断、基础证据或 required 组不完整时，
  返回 `incomplete/interrupted`；否则非零控制方退出决定返回 `failed/exit_nonzero`。
- 回执格式为严格整数 1、属于同次运行、`completed=true` 且严格整数退出码为 0；
  `modules` 为非空对象，每个模块有六项严格非负整数计数。状态工具汇总计数，
  各组负责核对自己的固定测试分母及漏跑、跳过等业务判据。
- 基础证据、回执和全部已登记组均属于同次 run，实际字节 SHA-256 与终态绑定相符；
  已有 `*_file` 反向链接必须指向本次已绑定文件，配对 `*_sha256` 必须相符。
  失败运行缺少回执且对应文件链接的哈希为 `null` 时可核验失败终态，不能据此通过。
- `materials_consistent=true`；终态的代码身份、工作树哈希、lockfile 哈希完整，
  与基础证据及全部 required 组的相应身份一致。代码身份含提交 SHA 和严格布尔 dirty 标记。

可选组失败不会单独使整体失败，但其已登记文件仍须存在、可读、格式受支持且字节不变。
读者在核验中再次核对已绑定文件，返回前再次核对 terminal 字节；失配或无法判断时不显示通过。
当前工作树适用性在终态核验后独立计算：工作树哈希包含 Git 管理及非忽略文件的路径、权限、
类型和字节（符号链接使用链接目标），不包含未跟踪且被 Git 忽略的运行证据。

### 完整入口的组合边界

完整入口按顺序发布 A1、A2-01、完整 A2、A3、A4、A5、A6、A7、A8、A9、A10。
其中 A2-01 为可选组，其余均为 required；正常完整成功包含基础证据、十一份组结论、
pytest 回执和 terminal，共十四份 JSON（十二份主要文件）。当前组合中 A6–A10 的直接前置如下，
均为同次结论，不继承历史通过；一个组没有直接依赖另一组不免除后者的整体 required 地位。

| 组 | 直接前置 |
| --- | --- |
| A6 | A1、完整 A2、A3、A5 |
| A7 | A1、完整 A2、A3、A5、A6 |
| A8 | A1、完整 A2、A3、A5、A6、A7 |
| A9 | A1、完整 A2、A3 |
| A10 | A1、完整 A2、A3、A6 |

各组详细证明范围与测试材料见[离线验证证据](../verification/offline-evidence.md)，
查询不补跑检查、不刷新 scope 或需求映射。同次必需结论缺失、失败、篡改、不完整或格式
不受支持时，历史成功不能补位。自动化核对当前集成树时，须等待真实完整入口退出 0，
再核对 `status=passed`、`reason=verified`、`applicability=same`；旧 run 在集成树改变后
仍只证明旧身份。

## 不提供／不证明与恢复

终态是控制方完成发布后的退出决定，不是操作系统对控制方最终退出的事后证明。
调用者仍须等待入口实际退出；若终态写出后控制方被强杀，以入口真实非零退出为准。
终态记录依赖本机受信控制方；哈希用于同次材料完整性核对，不提供签名认证。

发布失败或控制方在全部组完成前退出时可能没有终态；查询保持未证实，不修补记录。
旧运行没有终态也不升级为新协议通过。需要新结论时重新运行完整入口取得新记录，
不覆盖旧材料；本命令不提供任务续跑或数据库恢复。数据库与制品恢复另见
[备份恢复契约](backup-restore.md)。

离线通过不证明真实模型质量、生产执行许可、校准资格或完整阶段 A；A8/A9/A10 结论中的
`rpc_verified`、`live_verified`、`stage_a_verified` 均为 false，登记范围外能力不随通过升级。
组件的实际边界分别见 [Pi RPC](pi-rpc.md)、[Read 校验](read-validation.md)与
[fixture 审计](fixture-audit.md)。完整 A 收口责任见[路线图 A](../roadmap.md#module-a)，
真实供给/RPC 见[Live](../roadmap.md#module-live)，正文与真实纵向闭环见
[Body](../roadmap.md#module-body)／[B](../roadmap.md#module-b)，最终恢复验收见
[I](../roadmap.md#module-i)。

## 相关

- 依据：[#55](https://github.com/MeteoBoy4/PaperRadar/issues/55)；同次绑定与历史证明边界见
  [ADR-0031](../adr/0031-screening-budget-and-derived-applicability.md)；阶段目标见
  [规格 §11](../../intent/draft.md#十一九阶段实施与验收)。
- 实现：[查询入口](../../scripts/verification-status)、[状态读者](../../scripts/verification_status.py)、
  [控制方](../../scripts/verification_run.py)、[生产组登记](../../scripts/a2_full_acceptance.py)、
  [身份核验](../../scripts/verification_identity.py)、[共享核验](../../scripts/verification_checks.py)、
  [原子发布](../../scripts/verification_publication.py)。
- 证据：[离线验证证据](../verification/offline-evidence.md)；只读 scope 登记审计见
  [登记审计契约](verification-scope-audit.md)，开发期入口见[兼容检查契约](check-compatibility.md)。
