# Issue #29 阶段 A3 全量审查 R2（Standards / Spec 双轴）

- 固定点：`main` = `91080ba9805da462c0b5a6213ab266b2971e1f98`（即 merge-base）
- Diff 命令：`git diff main...HEAD`（HEAD = `b930b95`；75 文件，+7883/−199）
- Commit 列表（`git log main..HEAD --oneline`）：
  - `b930b95` refactor(storage): address A3 review follow-ups
  - `a09c3cc` fix(backup): reject FIFO manifests and redact group options (#29 review fixes)
  - `c0ce26a` feat(verification): bind A3 acceptance to current offline run (#35)
  - `cb826b3` feat(restore): verify isolated copies without original roots (#34)
  - `bbb735a` / `a52b0c9` 分支合并
  - `d2023dc` feat(backup): create and verify self-contained WAL backup batches (#33)
  - `dbe8819` feat(storage): publish complete extraction artifacts atomically (#32)
  - `660d553` test(storage): enforce immutable reuse and verify SQLite constraints (#31)
  - `bc7b843` feat(storage): safely upgrade and persist immutable single-file artifacts (#31)
  - `8d09251` refactor: share offline acceptance checks (#30)
- 规格来源：GitHub Issues #29（父票正文 + 三条约束力评论：实施前补充 / 用户裁决 / 第三轮收口）与子票 #30–#35；本地镜像 `.scratch/code-review-issue29/spec.md`
- 标准来源：`AGENTS.md`、`CONTEXT.md`、`docs/agents/{python-conventions,testing,refactor,cli-output,invariants,scope,documentation,domain}.md`、`docs/adr/`（含新增 0027 与被引用的 0006/0008/0009/0017/0018/0023/0026）、`docs/verification/offline-evidence.md` + Fowler smell 基线
- 审查方式：Standards 与 Spec 两个 reviewer 子代理（只读 explore）并行，仅聚合不混合排序；本次审查未修改代码、未创建 commit
- 与 R1 的关系：R1（`issue-29-a3-full-review.md`，针对 `a09c3cc`）的 Standards 五项发现经本轮核对已在 `b930b95` 全部修复；本轮覆盖含两轮 review fixes 的完整 diff

### 聚合者抽查说明

聚合者用仓库 shell 抽查了两轴全部可定位的新发现（共 6 处），均属实：

- `SINGLE_FILE_KINDS`（`src/paper_radar/storage/artifact_contract.py:34`）在 src/tests/docs/scripts 全仓零引用，死代码属实。
- `tests/test_a2_full_entry.py:18`、`test_verification_compatibility.py:14`、`test_verification_integrity.py:15`、`test_verification_run.py:16` 四处确实从 `tests.a3_acceptance_support` 导入 `fake_checks`。
- `backup/restore_cli.py:80-86` 两段 except 内联「echo 失败 + `Exit(2)`」，而 `backup/cli.py:76-79` 已有 `_failed` helper。
- 三份 `paused_*` 子进程屏障（`tests/artifact_support.py:46-78`、`tests/extraction_support.py:30-69`、`tests/restore_support.py:75-114`）确为同形脚手架（双 pipe 握手 + env 传 fd + select 15s + finally kill），仅参数不同。
- `docs/contracts/artifact-store.md:4` 原文确为「备份与恢复由各自的后续票交付」，与本 diff 已交付 #33/#34 矛盾。

## Standards

**上一轮五项核对（b930b95 均已修复）**：`sync_directory` 与 `controlled_path` 已提取至 `src/paper_radar/storage/filesystem.py:12-39`，blob_store 与 backup 两侧复用并各自映射领域错误；CLI 重复提取为 `backup/cli_support.py`（`BatchGroup`/`BatchCommand`/`show_result`）；SQLite 头魔数已命名（`backup/service.py:63-67` 常量+注释）；`storage/schema.py:1` docstring 已更新为「配置事实与不可变制品登记」。

**硬违规（明文标准）：0 项。** 逐项核对：`cli-output.md`（中文输出、错误含下一步、`--help` 无 I/O 由延迟 import 保证）；`testing.md`（migration 测试含 a201→a302 真实升级与恢复路径，FIFO 修复有回归测试）；`invariants.md`（a302 仅追加 CREATE TABLE/INDEX，blob 在文件系统、登记在 SQLite）；`documentation.md`（CONTEXT.md 新词、ADR-0027、两份 Contract、README、offline-evidence、draft.md 同步）；`python-conventions.md`（确定性/I/O 分离，无新依赖，受控 reason enum）；`refactor.md`（依赖方向 storage←backup 正确，`test_backup_architecture.py` 固化边界）；`scope.md`（无 V2 能力）。

**Smell（judgement call）：**

1. **Duplicated Code（本轮最重）**：子进程管道屏障脚手架三份同形拷贝——`tests/artifact_support.py:46-78`、`tests/extraction_support.py:30-69`、`tests/restore_support.py:75-114`，均为「双 pipe→Popen(env 带 `A3_READY_FD`/`A3_RELEASE_FD`, pass_fds)→select 15s→读 `b"R"`→finally kill/communicate/close」约 30 行；`checkpoint()` 也在三个 sitecustomize 各写一遍（`extraction_process/sitecustomize.py:11-13`、`restore_process/sitecustomize.py:11-13`）。宜提取共享 `paused_subprocess` 原语。
2. **Speculative Generality**：`SINGLE_FILE_KINDS`（`src/paper_radar/storage/artifact_contract.py:34`）全仓无任何引用（生产、测试、文档、fixture 均无），Contract 也未提及，属死代码。
3. **Duplicated Code（小）**：`backup/restore_cli.py:80-86` 把「echo 失败+`Exit(2)`」内联写了两遍，而 `backup/cli.py:76-79` 已有 `_failed` helper；同一轮提取 cli_support 后留下的不一致。
4. **依赖方向（轻）**：通用/A2 验收测试（`tests/test_verification_run.py:16`、`test_a2_full_entry.py:18` 等四处）改从 `tests.a3_acceptance_support` 导入 `fake_checks`，使 A2/通用 runner 测试反向依赖 A3 scope；系哈希钉死 A2 support 字节的代价，仍值得注意。

## Spec

**R1 两项声明修复均已落在 HEAD**：FIFO 清单阻塞由 `src/paper_radar/backup/files.py:46`（S_ISREG 前置）、`:55`、`:84-85`（特殊文件拒绝）修复，有界进程回归在 `tests/test_backup_integrity.py:185`；组级未知选项脱敏由 `src/paper_radar/backup/cli_support.py:29-46`（BatchGroup/BatchCommand parse_args 包裹）修复，`tests/test_backup_cli.py:77` 覆盖组级 SECRET 选项。

**抽查确认符合规格**（#35 为主）：A3 组追加于生产登记处，`required=True`、`dependencies=("A1","完整 A2")`（`scripts/a2_full_acceptance.py:393-400`），判据另行要求两份前置 passed（`scripts/a3_acceptance.py:257-262`）；回执显式并入 A3 模块（`scripts/a2_test_receipt.py:28`）；五份文件同 run_id 有测试（`tests/test_a2_full_entry.py:70-87`）；最新本地运行 `0453ec64…a3.json` passed 且 `code.commit=b930b95`、dirty=False。三份 scope 全部 59+56+152 条哈希与 HEAD 逐字一致，b930b95 触及文件均同提交重绑。restore 目标保护/重叠只查批次（`backup/restore.py:38-49`）、POSIX rename 发布符合裁决；备份用 renameat2(RENAME_NOREPLACE)（`files.py:143`）；DELETE 副本在切换后才哈希（`service.py:248`）；并发不锁根论证写入 `docs/contracts/artifact-store.md:100-102` 与 `backup-restore.md:100-102`；`--output` 存在性语义固定在 `backup-restore.md:30-32` 并有反向报错测试；help 六段/`<backup-batch>`/无 `run-due`/脱敏均符合。

**(a) 缺失**：1 项轻微——`docs/contracts/artifact-store.md:4` 仍写「备份与恢复由各自的后续票交付」，与同 diff 已交付的 #33/#34 及 `backup-restore.md:3`「现已开放」矛盾，不符合 #29 Decision 22 文档同步要求。

**(b) scope creep**：未发现（无 backup_runs/GC/新命令/新依赖，pyproject 未动）。

**(c) 实现错误**：未发现。

## 小结

- **Standards**：硬违规 0、smell 4（均 judgement call）；最重：测试子进程屏障脚手架三份拷贝。
- **Spec**：缺失 1（轻微文档过期）/ scope creep 0 / 实现错误 0；最重：`artifact-store.md:4` 过期交付状态表述。

## 修复核实记录（2026-10-17，关联 #29、#31、#32、#33、#34、#35）

以上审查原文保留。一个实现子代理逐项对照现有代码、ADR-0027、制品/备份恢复
Contract 和原父票裁决核实，四项采纳，一项保留现有组合适配。四项 Standards
建议均属可维护性判断，不是已复现的功能 Bug；Spec 的交付状态描述确已过期。

| 原建议 | 核实结论与具体处理 |
| --- | --- |
| Standards 1：三份进程屏障与 checkpoint 重复 | 采纳。新增仅依赖标准库的 `tests/a3_process_support.py`，统一双 pipe 握手、FD 传递、15 秒有界等待、kill/communicate 与 FD 清理；三类 `paused_*` 保留各自命令、phase 和失败消息，启动钩子与多文件发布的 temporary phase 共用 `checkpoint()`。子进程显式把钩子目录与仓库根加入 `PYTHONPATH`，保证从安装入口或临时 cwd 启动时仍可加载共享支撑；独立恢复 CLI 故障用例同步适配。既有真实进程强杀/并发用例仍须先收到屏障信号，随后核验登记与文件残留，不能靠跳过钩子得到成功。 |
| Standards 2：`SINGLE_FILE_KINDS` 无引用 | 采纳。全仓检索确认定义之外没有消费方，移除死常量；五 kind/角色规则仍由原 `KIND_ROLES` 和权威模型约束，没有改变 Contract 或身份字节。 |
| Standards 3：恢复失败输出重复 | 采纳。在现有 `backup/cli_support.py` 增加 `show_failure()`，备份和恢复共用中文失败格式与退出码 2；各服务继续构造自己的受控 reason，包括不同的中断错误类型，原消息、脱敏和延迟加载边界保留。备份/恢复 Contract 同步说明共用失败输出。 |
| Standards 4：通用/A2 测试依赖 A3 支撑 | 不采纳结构性改动，保留组合适配。四个文件实际测试的是生产完整验收计划；`test_a2_full_entry.py` 明确要求同次五份主要文件、A3 状态与依赖哈希，其他入口同样调用完整计划或生产组登记，因此需要含 A3 固定用例的 fake 回执。`tests.a3_acceptance_support.fake_checks` 在固定 A2 支撑之上适配临时回执，未使生产底层或 A2 独立判据依赖 A3。仅移动/改名不消除组合入口对当前完整回执的必要依赖；新增注册器或参数化会增加间接层。本轮维持旧 A2 支撑原字节，不把这一项声称为已修复的代码问题。 |
| Spec (a)：存储 Contract 仍说后续交付备份/恢复 | 采纳。改为自包含备份与隔离恢复已交付，并链接 `backup-restore.md`；存储只证明原字节完整保存的业务边界继续保留。 |

新增共享支撑显式加入 A3 固定源码范围，并逐项重绑本次受影响源码/测试哈希。
原固定用例计数、A1 资产、A2 支撑与两份 A2 scope、旧 migration、Frozen Contract、
制品/备份格式与 Stage fingerprint 语义均保持不变。本轮属于局部维护重构，沿用
已有公共服务、真实 CLI/进程和离线验收组合测试，没有新增镜像私有实现的测试。

### 提交前实测

- 首轮相关公共存储/多文件发布/恢复强杀/真实 CLI 回归：121 passed（19.65s）。
- 扩展子集覆盖存储、迁移、备份、恢复、wheel、A2/A3 判据及完整入口组合：334 passed（62.34s）。
- temporary phase 也复用 checkpoint 后，补跑 `tests/test_extraction_artifacts.py`：34 passed（3.25s）。
- `uv run --offline --locked ruff check src scripts tests`：通过。
- `uv run --offline --locked ruff format --check src scripts tests`：194 files already formatted。
- `uv run --offline --locked mypy`：Success，194 source files。
- `git diff --check`：通过。

完整离线门槛在本轮修改与报告一起提交后的干净提交上执行，以同次
`verification-runs/<run_id>.a3.json` 为准，本报告不提前声明该门槛通过。
未进行 live 或真实 NAS 验收；hard-link、Linux 原子重命名的既有文件系统要求保持不变。
