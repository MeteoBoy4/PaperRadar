# 离线验证状态查询（#55）

这是开发验收工具，不属于 V1 论文业务 CLI。运行：

```bash
./scripts/verification-status <32 位小写十六进制 run_id> \
  --runs-dir verification-runs [--json]
```

默认目录是仓库的 `verification-runs/`。入口使用现有项目 Python，支持
`UV_PROJECT_ENVIRONMENT`，不启动 uv 或同步环境；解释器缺失时提示先准备环境。
`--help` 只打印中文帮助。查询只读文件和 Git 身份，不执行检查、迁移或补写历史记录。
不保存、回显原始异常、未知参数、测试参数、论文或配置载荷。

退出码：0 表示已核对的历史通过；1 表示失败、未完成、未证实或材料不可得；
2 表示参数错误。历史通过的退出码与当前工作树适用性分开，自动化若要求适用于
当前代码，还须核对 `applicability=same`。

## 输出格式 1

JSON 与中文文本展示相同事实。JSON 使用以下受控字段：

| 字段 | 语义 |
| --- | --- |
| `format_version` | 严格整数 1 |
| `status` | `passed` 通过；`failed` 失败；`incomplete` 中断/不完整；`unavailable` 材料不可得；`unconfirmed` 历史结果/终态未证实 |
| `reason` | 见下表；永不包含原始异常正文 |
| `phase` | `checking` 检查执行阶段；`publishing` 检查已收尾、结论发布阶段；`finished` 控制方终态已核对；`unknown` 无法判断 |
| `current_check` | 固定计划中首个尚未完成的检查 ID，或 `null`；不是进程存活证明 |
| `checks_passed`、`checks_total` | 固定计划的通过数和总数 |
| `elapsed_seconds` | 基础检查的开始到结束时间差；未结束时相对查询时间；无法解析为 `null`。不含结论发布时间 |
| `tests` | 回执各模块六个非负整数计数之和；不可解析为 `null`。仅供进度参考，不证明成功 |
| `exit_code` | 核对终态后展示的控制方退出决定，其他情况为 `null` |
| `applicability` | `same` 当前 HEAD、工作树和 lockfile 同身份；`different` 身份不同；`unknown` 无法核对 |

中文文本也展示输出 `format_version`；`tests` 以计数字典展示，键和数值与 JSON 相同。

| `reason` | 含义 |
| --- | --- |
| `verified` | 终态、执行事实、必需组、回执及字节/身份链接均通过 |
| `terminal_missing` | 缺少终态；不区分旧协议、仍在运行、发布崩溃或被强杀 |
| `material_unavailable` | 必需文件缺失或不可取得 |
| `invalid_document` | 非对象、坏 JSON、错误字段类型或非法/重复组登记 |
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

## 控制方终态格式 1

`run_verification` 在实际等待固定检查执行器返回、依次取得全部登记组的发布结果后，
最后使用既有不可覆盖原子发布原语写出 `<run_id>.terminal.json`：

| 字段 | 语义 |
| --- | --- |
| `format_version`、`run_id` | 严格整数 1、同次运行标识 |
| `exit_code` | 控制方将返回的严格整数退出码；全部必需组通过且控制方未中断时为 0，否则为 1 |
| `interrupted` | 控制方是否记录了组发布中断；基础检查中断还要读取其自身证据 |
| `code`、`worktree_sha256`、`lockfile_sha256` | 本次开始时采集的运行身份 |
| `evidence_sha256`、`pytest_receipt_sha256` | 基础证据和回执的实际字节哈希；失败运行可能没有回执，哈希为 `null` |
| `materials_consistent` | 发布文件名、run_id、磁盘对象与各写出器返回对象是否相符 |
| `groups` | 本次按发布顺序冻结的全部组，含可选组；每项保存 `suffix`、严格布尔 `required`、`sha256`、`format_version` |

组后缀限 `.[a-z0-9-]+.json`，不得重复或占用 `.pytest.json`、`.terminal.json`。
查询以本次终态的登记清单为准，不导入当前验收组注册表；新增组会自动记录，
以后增删生产组不改变历史范围。读者另维护明确的历史格式支持表：A1、A2-01、
A3、A4、A5、A6、A7 格式 1，完整 A2 格式 2。新增后缀或格式须先扩展读者的解析能力，
否则返回 `unsupported_format`，不能因终态自声明格式就通过；升级时保留旧格式支持。
已知组格式仍须与当次写出器登记一致，不复制各组业务判据。

格式 1 的检查计划固定为 `lockfile`、`format`、`lint`、`types`、`tests`、`contracts`，
顺序也固定。读者按这份已发布的历史定义校验 `checks`、展示总数，不调用当前的
`default_checks()` 来解释旧运行。当前执行计划改变不影响已发布历史结果；格式 1
出现缺项、乱序或新增未知检查仍拒绝，不能静默忽略。将来采用不同计划时须显式
版本化并扩展读者的解析能力，同时保留已支持的历史定义，不回填或修改旧记录。

`passed` 必须同时满足：终态退出决定为 0；基础证据完整、固定六检查均为
`passed/none` 且实际整数退出码为 0；全部必需组通过；回执格式 1、同次、完整且
实际整数退出码为 0；基础证据、全部组、回执的字节链接及必需组身份均成立。
可选组失败不会单独使整体失败，但其已登记文件仍须存在且字节不变。
查询前后复核已绑定文件，材料失配或无法判断时不显示通过。

终态是控制方完成发布后的退出决定，不是操作系统对控制方最终退出的事后证明。
调用者仍应等待入口实际退出；若终态写出后控制方被强杀，以入口真实非零退出为准。
终态记录依赖本机受信控制方；哈希用于同次材料完整性核对，不提供签名认证。

发布失败或控制方在全部组完成前退出时可能没有终态；查询保持未证实，不修补记录。
旧运行没有终态也不升级为新协议通过。旧基础证据和各组格式、原七份主要文件与
pytest 回执的含义保持不变；该阶段只另增一份终态，正常成功共九份 JSON。


A6 注册时，新运行的终态另绑定必需 `.a6.json`（格式 1），正常成功共十份 JSON：
八份主要证据/结论、pytest 回执与 terminal。A6 前置为同次 A1、完整 A2、A3、A5；
A4 仍为整体 required。查询解释每次 terminal 自带的组清单，不从当前登记反推历史；
没有 A6 的旧终态仍按原组清单解释，不补写旧文件或扩张其证明范围。
A6 未发布、丢失、篡改、未知格式、失败或不完整时不能以历史成功补位。


A7 注册后，当前终态另绑定必需 `.a7.json`（格式 1），正常成功为九份主要证据/结论、
pytest 回执与 terminal，共十一份 JSON。A7 前置精确为同次 A1、完整 A2、A3、A5、A6；
A4 继续为整体 required。读者保留上述历史组和格式支持，不为没有 A7 的旧终态补组、
补文件或扩大其证明范围。A7 失败、缺失、篡改、未知/布尔格式、范围漂移或中断均不得
显示通过；真实完整入口退出 0 后，还应核对 status=passed、reason=verified、
applicability=same。查询仍只读，同次终态不能由历史成功替代。


## A8 格式与当前输出范围

状态读者支持 `.a8.json` 格式1，同时保留 A1–A7 已支持格式（完整 A2 为2）。
当前登记的十份主要文件加实际 pytest 回执、terminal 共十二份 JSON；terminal 原样绑定
A8 的 suffix、required、格式、run_id、原始 SHA256。A8 必需且直接前置为同次 A1、完整
A2、A3、A5、A6、A7；A4 仍决定总门禁。A8 仅证明离线协议与 test 任务接线，
rpc_verified/live_verified/stage_a_verified 恒为 false。旧终态按其冻结组清单解释，
不把历史缺少 A8 当成当前 A8 通过；未知格式、缺组、字节替换、缺终态或中断均不能
得到 passed/verified，适用性仍按代码/工作树/lockfile 与当前身份独立判断。
