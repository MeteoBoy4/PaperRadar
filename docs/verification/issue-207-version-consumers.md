# Issue #207 版本消费者开发回归

依据：[#207 正文及所有者补充评论](https://github.com/MeteoBoy4/PaperRadar/issues/207)。
共同基线为 `50485e2d9ad7d4b68780f24e79ebf9b9ac074202`，本地目标 `main`。
本次为开发检查与独立 D1 覆盖，不扩大 #185、旧固定分母、required 集合或正式验收结论。

## 人工消费者核对

消费者按版本变化可能破坏的公共行为、持久历史和恢复重建核对；不是 import 闭包。
以下为本次实际人工取舍，完整执行成员和逐项理由唯一维护在
`scripts/check_compatibility.py::CHECK_GROUPS`，帮助和测试导航从该目录派生。

| 类别 | 选择与理由 | 核对后保留的边界 |
| --- | --- | --- |
| renderer | 报告 CLI、分节、安全披露、发布、恢复，回放投影、B 报告质量，以及 exposure/renderer migrations；同时覆盖当前 v2 和冻结 v1 的升级、恢复与回放 | capacity、decision_order、late_results 主要保护选取/时序；logging 保护日志；不因文件名匹配全部加入。报告选择或时序同时变化时另外跑对应功能测试 |
| source-guard | 当前源码 manifest、bundle 构建、epoch 升级，以及独立 v28 原字节和 B 准入闭包 D1 | host/lifecycle 主要保护 OS 替身或冻结部署制品，旧 v1 准入协议不是当前 manifest 的消费入口；封印 CLI 的参数契约仍由相关功能回归负责 |
| migration | b008 非空 v1 根到当前 head、报告表 Schema/metadata、约束和追加保护、故障原子性，报告历史恢复/合法旧降级/v2 拒降；人工 head 唯一维护点、数据库 revision 分类、备份声明和恢复的实际消费者 | 不把十组完整验收机械纳入，不构造任意 revision 矩阵；报告历史边界只属于报告域，后续迁移按受影响域维护目录 |

`acceptance` 和 `cli` 原有目录 AST 与共同基线一致；职责与成员未扩张。
`all` 按五类登记顺序有序去重，跨类别共享模块与完整 nodeid 只执行一次。
目录的机械完整性不证明未来消费者已经找全；新增相关消费者必须同变更人工核对。

## 新覆盖与 D1 数量

新增独立未绑定模块 `tests/test_version_consumer_checks.py` 共 **7 个节点**：
目录最低消费者、顺序与去重 1 个；三类各成功/失败临时根执行 6 个。
临时根拒绝联网、SQLite 连接及 home 下凭据/真实根读取，保留正式回执字节，
检查实际选择/数量/退出码与无全量回退。SQLite 在此 synthetic runner 探针被全部拒绝；
真实消费者回归仍允许临时 SQLite。守卫不是入口提供的 OS 沙箱。

复用 `tests/test_check_compatibility.py` 的 **12 个既有节点**，保留空选择、缺模块/节点、
空模块、失败、中断、参数错误、中文纯本地帮助与外层回执隔离的原覆盖，
只把 `all` 的预期扩展到完整五类。新检查没有平行 runner。

加强既有未绑定消费者的 setup 断言，测试函数与参数化 AST 保持：

| 模块 | 实际节点 | 新增断言范围 |
| --- | ---: | --- |
| `tests/test_report_replay_projection.py` | 3 | 公共报告字节确为 renderer 2，注册含当前目标值，mutation 生效后精确 `registration_invalid` |
| `tests/test_live_bundle.py` | 11 | 人工 v29 策略、当前 fixture 确实存在、负例目标确实写入，随后精确 `source_guard_mismatch` |
| `tests/test_live_epoch_upgrade.py` | 42 | 当前 v29 manifest、源码实际变化、manifest 原字节保留，随后精确 `source_guard_mismatch` |
| `tests/test_experiment_exposure_migrations.py` | 4 | 冻结根确为 b008、非空 published v1，然后合法降级/升级/恢复 |

未改 renderer v1 zip、v28/v29 manifest、旧 migration、旧覆盖台账、冻结证据、scope 成员、
计数或中央哈希。没有 skip/deselect 代替通过，也没有把新 D1 纳入旧回执。

## 隔离旧缺陷重放

在树外临时副本 `/tmp/paperradar-207-208/replay207` 复制受控源码、tests、scripts、docs、
examples、锁文件，并建立仅用于 bundle 构建前置的本地 Git 身份；不联网、不运行 hooks。
先核对目标模块确实由对应组合选到，再通过现有 `run_checks` 对该组合中的具体失败节点
作窄重放；不是额外的完整组合测量。每次只变异该副本中的一处，随后恢复原字节复验。

| 类别与节点 | 隔离变异 | 判别边界与恢复 |
| --- | --- | --- |
| renderer：`test_report_replay_rejects_changed_registration_across_calls` | 将负例 mutation 的目标从当前 2 改回旧 1 | 当前报告存在，`altered != original` 断言失败，证明旧 mutation 没改到目标；恢复后精确 `registration_invalid` 用例通过 |
| source-guard：`test_changed_source_copy_refuses_stale_guard` | 将 epoch 消费者准备的 manifest 路径从 v29 改回 v28 | v28 文件真实存在，人工 v29 前置断言捕获 `pi-admission-v28`，未以缺文件通过；恢复后源码 mutation 生效并到达精确 `source_guard_mismatch` |
| migration：`test_nonempty_reports_revision_upgrade_failure_retry_and_restore[None]` | 在合法 v1 根升级后追加真实当前 renderer v2 报告，再执行旧报告降级 | 先断言 render 成功且实际存在一条 v2 历史，随后到达 `renderer_v2_history_present`，恢复后合法 v1 路径通过 |

三类重放均要求红退出 1、恢复绿退出 0，并排除 `FileNotFoundError`/
`ModuleNotFoundError`。最终成功记录在树外 `207-replay-results.json` 与逐次 red/green 日志；
一次性脚本和变异不入库，不交付 mutation-testing 框架。

## 开发验证与计时

环境：Linux x86_64、CPython 3.14.4、uv 锁定离线环境，本 worktree 独立 `.venv`；
`TMPDIR=/tmp/paperradar-207-208/tmp207`。组合并行测量，墙钟含该机器同期负载，
不设耗时门槛。下表为入口打印的实际去重节点数与含 uv 总耗时。

| 命令 | 模块选择 | 实际节点 | 结果 | 总耗时 |
| --- | ---: | ---: | --- | ---: |
| `./scripts/check-compatibility renderer` | 10 | 49 | 49 passed，退出 0 | 558.13s |
| `./scripts/check-compatibility source-guard` | 6 | 103 | 103 passed，退出 0 | 289.35s |
| `./scripts/check-compatibility migration` | 8 | 76 | 76 passed，退出 0 | 320.06s |
| `./scripts/check-compatibility acceptance` | 12 | 117 | 117 passed，退出 0 | 317.81s |
| `./scripts/check-compatibility cli` | 8 | 59 | 59 passed，退出 0 | 98.43s |

新 D1 的初次目录红灯为缺失 `renderer` 类别，补齐后通过；新增临时根与现有 renderer
单文件复验 `uv run --offline --locked pytest -q tests/test_report_replay_projection.py
tests/test_version_consumer_checks.py` 为 10 passed。
最终入口/帮助/目录/renderer 三文件相关复验为 **22 passed，4.30s**。
`uv run --offline --locked mypy`：1334 文件通过；改动 7 个 Python 文件的
`ruff check` 与 `ruff format --check` 通过。

只读固定范围审计使用显式共同基线及 `--integration-target main --collect`，
退出 0、无 issues、无 hash drift；285 个固定模块、5281 个去重固定节点保持，
collection skip/deselect 为 0。只修改未绑定 D1/工具和活文档；
新覆盖单列于本台账，无需重绑旧登记。
串行集成后仍须按最终身份重跑审计与受影响组合。

未运行完整离线门禁、live、真实实验根、模型、Docling 或 NAS；开发检查不替代正式验收。
#208 的 pre-commit 接口不自动调用本票三类或扩员后的 `all`。
