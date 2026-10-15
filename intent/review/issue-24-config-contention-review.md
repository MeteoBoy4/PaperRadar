# Issue #24 代码审查：并发与中断后的编译保持唯一完整结果（A2-09）

- 审查范围：`HEAD^...HEAD`（单笔 commit `abb932c` "fix(config): preserve complete
  snapshots under contention (#24)"，固定点 `HEAD^ = 3dec919`）。
- 规格来源：GitHub Issue #24 正文（10 条 Acceptance criteria）与全部 1 条 comment
  （①有界锁等待=固定 5 秒 busy_timeout、不可配置，锁超时与版本冲突可区分且预算写入
  Contract；②复用已提交快照=幂等成功退出 0，仅同身份不同字节=版本冲突退出 2；
  ③跨进程竞争验收用文件屏障等确定同步，不依赖 sleep）。
- Standards 依据：AGENTS.md、CONTEXT.md、docs/agents/（python-conventions、testing、
  cli-output、invariants、documentation、llm-evidence、scope）、docs/contracts/ 与
  Fowler smell 基线。
- 审查方式：只读双轴独立审查（Standards / Spec 两个并行子代理）。子代理环境无
  shell，报告基于 HEAD 文件全文重建改动；主代理已对全部关键发现逐一抽查复核：
  - 行号校正：S1 精确为 `tests/test_config_transaction_cli.py:88-94` 与
    `tests/test_config_transactions.py:164-170`；S3 为 `tests/test_config_transactions.py:37`。
  - **剔除**子代理 Standards finding「Data Clumps（repository.py:119-136 手工展开
    排序四元组）」：经 `git show HEAD^:src/paper_radar/storage/repository.py` 核实，
    该 refs/expected 排序块在 #16 已存在，非本 diff 引入，不属本次审查范围。
  - `scripts/a2_scope.py` 三个新源码哈希经 `sha256sum` 核实与实际文件**完全一致**
    （cli.py `5abbc086…`、database.py `738eb3c1…`、repository.py `91a48151…`），
    解除 Spec 轴"新哈希是否匹配"的存疑项。
- 工具基线（主代理实际运行，均为只读验证）：本票相关
  `pytest tests/test_config_transactions.py tests/test_config_transaction_cli.py`
  24 passed（16.17s）；改动文件 ruff check 与 format --check 全绿；`git status` 干净。
  未重跑完整 `./scripts/check-offline`（其结果以
  `docs/verification/offline-evidence.md` #24 段落的自述为准）。未修改代码、未创建
  commit、未评论或关闭 Issue。

## Standards

### (a) 成文标准违反（硬违规）

**无。** 逐项对照通过（子代理结论，主代理复核行号属实）：

- **python-conventions（部分成功的操作放同一事务）**：`repository.py:82`
  `BEGIN IMMEDIATE` 覆盖冲突检查与全部写入，`BaseException` 时整体 rollback
  （`repository.py:147-149`）；`save_snapshot` 主体为 #16 既有代码，本 commit 只
  新增忙错误分类（`repository.py:147-157`）。
- **invariants（历史只追加）**：复用路径核对 payload 与完整引用集合、不刷新
  `created_at`；新增孤儿引用拒绝（`repository.py:40-52`）与只读 `BEGIN`
  （`repository.py:63-67`）均不写历史。
- **cli-output（错误写明原因与下一步）**：忙错误与写失败消息
  （`repository.py:152-157,161`）均含中文原因和重试指引；`config/cli.py:147-155`
  compile help 为静态文本，同步说明并发/退出码行为，不读配置不开库。
- **llm-evidence（日志脱敏）**：错误为固定文案并 `from None` 断链；新测试断言
  `PRIVATE_*`、`Traceback`、`INSERT INTO`、`parameters:` 不出现在 stdout/stderr/caplog。
- **documentation（Contract 同步）**：契约「并发、失败与恢复」
  （`docs/contracts/runtime-config.md:280-309`）、`README.md:62-66`、
  `docs/verification/offline-evidence.md` #24 段落三处同步，且与代码一致
  （如 busy_timeout=5000 固定值、`database.py:20` 单一常量来源）。
- **testing（测试边界）**：回归覆盖同材料复用、版本冲突、忙错误、进程终止、
  来源替换、损坏拒绝；用 `Barrier`/管道握手（`config_transaction_support.py:76-121`
  os.pipe+select，`config_transaction_process/sitecustomize.py`）实现确定同步，无
  sleep；sitecustomize 链入既有 `deny_network` 哨兵，只影响子进程，无生产测试钩子。

### (b) 基线 smell（判断性发现）

**S1. Duplicated Code — v2 材料构造与恢复断言形状在两个测试文件重复**

- 位置：`tests/test_config_transaction_cli.py:88-94` 与
  `tests/test_config_transactions.py:164-170`（另 `tests/test_config_transaction_cli.py:163`
  单行复用 `profile-v2`）。两处均构造 `profile-v2` + `boundary-v2` prompt
  （`PRIVATE_PROMPT_MARKER`）+ settings 重写，随后的"重跑恢复且历史快照不变"断言
  形状亦相近。
- 依据：Fowler 基线 Duplicated Code（判断性意见，非硬违规）。
- 实际影响：新增恢复场景时需在两处同步改材料构造，漂移风险低但存在。
- 最小修复：在 `tests/config_transaction_support.py` 提取共享的 v2 输入构造
  helper，两文件调用。

**S2. 计时断言上界 — 高负载下可能偶发超限**

- 位置：`tests/test_config_transactions.py:37` `assert 4.5 <= elapsed < 10`。
- 依据：判断性测试稳健性意见（非 Fowler smell、非成文标准违反）。
- 实际影响：busy_timeout=5000ms 下 elapsed 通常约 5 秒，上界 10 秒留有约一倍余量；
  极端慢 CI 上偶发失败的可能性低但非零。
- 最小修复：放宽上界（如 `< 30`）或仅断言下界与忙错误文案。

**硬违规：无。**

## Spec

### 对照清单（10 条 criteria + comment 三点边界）

1. **双连接竞争+跨进程验收：已满足** — `tests/test_config_transactions.py:56-118`
   （`Barrier` 定位于 `BEGIN IMMEDIATE` 前，两独立连接断言 `is not`）；
   `tests/test_config_transaction_cli.py:21-88`（真实安装 CLI 入口 +
   `sitecustomize.py` 管道屏障，无 sleep）。主代理实跑通过。
2. **同身份异字节至多一方提交：已满足** — `repository.py:82-102` 在
   BEGIN IMMEDIATE 内重读；两处 `different_bytes=True` 断言退出码 `[0,2]`/一成一败，
   无后写覆盖、无假幂等。
3. **短写事务+材料预固定+复用前复验：已满足** — `repository.py:73-142`；复用路径
   复核 payload（:118）与完整 refs（:128-139）；预算超限给受控忙错误
   （:152-157），无无界重试。
4. **注入失败/中断后无半条事实、可重跑：已满足** —
   `test_config_transactions.py:173-247`（snapshot/references/commit × 断连/SQL 失败）；
   `test_config_transaction_cli.py:90-133`（真实进程 kill 后重跑成功、历史不变）。
5. **读取与提交间替换来源文件：已满足** — `test_config_transactions.py:121-154`
   （提交对应固定字节 `versions[0][4] == original`，不写回输入）。
6. **脱敏+无种类分支：已满足** — marker 断言遍布两组测试；repository 对材料统一循环，
   无按 kind 分支。
7. **Contract/恢复说明+离线检查：已满足**（文档）；「运行完整离线检查」以
   `docs/verification/offline-evidence.md` #24 段落自述为准，主代理未重跑全量
   check-offline（见剩余风险）。
8. **测试边界：已满足** — 真实临时 SQLite、无网络（sitecustomize 链入 deny_network）；
   主代理实跑本票子集 24 passed。
9. **中文 help/退出码/help 不开库：已满足** — `config/cli.py:147-155` 静态文本；
   退出 0（成功/复用）与 2（冲突/忙/失败）与既有约定一致。
10. **A2 自有模块+保留固定哈希：已满足** — 五项 A2-01 固定测试与 A1 契约不在改动
    清单；`scripts/a2_scope.py` 仅重绑三个源码哈希，主代理 sha256 核实**全部匹配**。

comment 边界：①已满足（`repository.py:124-131` 区分"数据库忙（锁等待上限 5 秒）"与
"声明版本已登记不同字节"，`test_config_transaction_cli.py:135-152` 断言互斥；预算值
写入 Contract "busy_timeout=5000 毫秒，不提供配置选项"）；②已满足（复用返回同一快照、
CLI 输出与首次一致、退出 0；冲突退出 2）；③已满足（`config_transaction_support.py:76-121`
os.pipe+select 与 sitecustomize 管道握手）。

### Findings

- **(a) 缺失/部分：无实质缺失。** 第 7/8 条中"运行检查"环节原无法静态判定，已由
  主代理以子集实跑（24 passed）与哈希核对解除；仅完整 `check-offline` 未在本次
  审查中重跑。
- **(b) 范围蔓延：未发现。** check 只读一致性事务（`repository.py:53-67`）与孤儿
  引用拒绝（`repository.py:40-52`）超出字面 criteria，但分别有"使并发调用方得到
  一致的最终事实""不能……偷偷改成新内容"依据，且已写入 Contract 与
  offline-evidence（"审查补充孤儿引用的拒绝和只读一致性回归"），属规格内收口。
- **(c) 实现有误：未发现。** 复核过 BEGIN IMMEDIATE 与 SQLAlchemy 自动事务兼容
  （显式 commit/rollback 成对）、`sqlite_errorcode & 0xFF == SQLITE_BUSY` 掩码
  （`repository.py:149-153`）、复用路径 refs 排序比较、连接关闭回滚，均正确。

## 汇总

- Standards 轴：2 条判断性发现（无硬违规），最重为 S1 Duplicated Code（测试材料
  构造重复，P2）。
- Spec 轴：0 条缺失/蔓延/错误；最重事项仅为"完整 `check-offline` 未在审查中重跑、
  以 offline-evidence.md 自述为准"。

## 实现方逐条核实与处理（Issue #24）

本节以 `abb932c` 为复核基线。上文保留为该提交的原始审查记录；原行号、测试耗时
及“审查时未重跑”的说明不改写为本轮结果。

| 建议 | 核实结论 | 处理 |
| --- | --- | --- |
| S1：恢复材料构造重复 | 合理。两处都创建同样的 `profile-v2`、`boundary-v2` Prompt 和 selector；属于维护性问题，没有证据表明已导致功能错误。 | 在 `tests/config_transaction_support.py` 提取 `recovery_inputs(root)`，服务故障和 CLI 杀进程测试共同调用。 |
| S1：恢复断言形状相近 | 观察属实，但服务返回对象与真实 CLI 的退出码、stdout/stderr 是不同边界。把断言也抽到同一个 helper 会掩盖各自需证明的行为。 | 保留两处的公开结果、历史不变及脱敏断言，只共享材料构造。单独测试只需要新 Profile 时继续使用 `profile_inputs(version="profile-v2")`，不添加无关 Prompt。 |
| S2：10 秒墙钟上界存在负载敏感性 | 合理的稳健性建议；本轮基线测试未复现超时，不能称为已经发生的 CI 故障。墙钟耗时包含进程调度，不能等同于 SQLite busy handler 的预算。 | 将上界放宽至 30 秒，保留 4.5 秒下界和受控忙错误断言。没有采纳“删除上界”的备选方案，仍保留有限完成时间检查。既有双连接测试继续检查实际 `PRAGMA busy_timeout == 5000`。 |
| Spec：完整离线检查未由审查 Agent 重跑 | 这是审查覆盖范围说明，不是实现缺失。已核实原实现确有完整机器证据，而非只有文档自述。 | 本轮继续先跑本票子集，再运行 `./scripts/check-offline`；完整检查成功后才提交。 |

其余成文标准核对、Spec 1–10 和 comment 三点边界的结论经源码复核予以认可；
不增加生产功能或修改事务、迁移、快照身份、5 秒锁预算、CLI 退出码及冻结契约。
本轮没有修改 A1/A2-01 固定测试，也无需更换生产源码的固定哈希。

### 核实的历史验收证据

原实现的 `verification-runs/1c1aa6e5f5be417c98d92acc94d215ca.json` 记录
2026-10-15 03:30:12–03:31:59 UTC 的 lockfile、format、lint、types、tests、
contracts 六项检查全部 `passed`，对应 `.a1.json` 和 `.a2.json` 也均为 `passed`。
实际证据 SHA-256 为
`bd10e2a3759204894abc3e5b56f1ca8daa201759bee248d79997d0cf7137c735`，
与两份结论中的绑定一致；A2 结论绑定的 A1 结论 SHA-256
`c6575b83019f701dd5422dd01dcb6e806435102de26a8c9185ea945d57d1208d`
也与实际文件一致。这些是历史检查结果，不冒充本轮工作树的验证。

### 本轮验证

- 改动前后分别运行 `uv run --offline --locked pytest -q tests/test_config_transactions.py tests/test_config_transaction_cli.py`，均为 **24 passed**。
- `uv run --offline --locked mypy`、`ruff check src tests scripts`、`ruff format --check src tests scripts` 全部通过。
- 完整验收入口为 `./scripts/check-offline`，结论按本轮工作树与实际检查结果生成在 `verification-runs/`；该入口返回 0 是本轮提交门槛。
- 仅使用合成材料、临时 SQLite 和真实安装 CLI。未运行 live 网络、付费模型或真实用户配置验收，未推送远端或关闭 Issue。
