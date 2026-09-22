# Issue #12 离线验证证据审查（Standards / Spec 双轴）

- 固定点：`HEAD^`（= `6f7e4a24cf9f97ea651b2cf20d128fab43b98681`）；`HEAD` = `7a4792ca6ba651ba36f6cd72ff33948f55472d19`
- 范围验证：`git log HEAD^..HEAD --oneline` 恰为 `7a4792c Implement offline verification evidence for #12`
- Diff 命令：`git diff HEAD^...HEAD`（8 文件，+634/-37）
- 规格来源：GitHub Issue #12 正文（5 条 Acceptance criteria）+ 全部 comments（经 `gh api repos/MeteoBoy4/PaperRadar/issues/12/comments` 核实为 0 条）；父 issue #1「阶段 A1」作为范围背景
- 标准来源：`AGENTS.md`、`CONTEXT.md`、`docs/agents/*.md`、`docs/adr/*.md`、`docs/contracts/*.md`、本 diff 新增的 `docs/verification/offline-evidence.md`、`pyproject.toml`、`tests/deny_external_io/sitecustomize.py`，外加 Fowler smell 基线
- 审查方式：Standards 与 Spec 两个独立子代理并行、只读、各自独立上下文（无 shell，只读静态核对），仅聚合不混合排序；未修改代码、未创建 commit、未触碰 Issue
- 聚合者只读抽查（未运行测试）：对 finding 的行号引用做了核对——`datetime.UTC`/`StrEnum` 实为 `scripts/offline_evidence.py:13,14`（Standards finding 1 原文写作 `:11,14`），被删测试实为 `tests/test_cli_help.py` 旧 `123-135` 行（finding 6 原文写作 `:121-132`）；其余引用（`offline_evidence.py:274/329/340-348`、`.gitignore:208`、`tests/test_offline_evidence.py:15/185-221/224-237`、失败样本 `verification-runs/4ddcdafe…json` 的 `completed=true` + `contracts not_run` 且仍带四份哈希）核对一致

## Standards

### 硬性违规

**1. `scripts/check-offline:8` — 入口未使用项目托管环境**

- 依据：AGENTS.md「依赖与外部服务」原文：「项目初始化后统一使用项目管理的 Python 环境和 `uv`。」
- 实际影响：`exec python3 -m scripts.offline_evidence` 绑定宿主 PATH 解释器（本机 `/usr/bin/python3`；`.venv/pyvenv.cfg` 记录解释器为 3.14.4），而非锁定环境；同一 diff 在 `scripts/offline_evidence.py:164-179` 已用 `uv run --offline --locked python -c` 取环境信息，入口自身却绕过 uv。`scripts/offline_evidence.py:13,14` 需要 `StrEnum` / `datetime.UTC`（≥3.11），而 `pyproject.toml` 只声明 `requires-python = ">=3.12,<3.15"`：宿主 `python3` 低于 3.11（或多解释器镜像）时入口在写任何证据前以 ImportError 退出，`verification-runs/` 无文件，失败也未被记录为失败证据。本机不复现（`verification-runs/*.json` 为真实产物），未运行核实。
- 最小修复：`exec uv run --offline --locked python -m scripts.offline_evidence`

**2. `docs/verification/offline-evidence.md:25-27` — 「运行时先写出」与实际写入时机不符**

- 依据：AGENTS.md「文档维护」（文档须与行为同步）；该文件是本 diff 交付的文档，其陈述必须与实际代码行为一致。
- 实际影响：证据首次落盘在 `scripts/offline_evidence.py:274`，之前已跑 `_git_metadata`（:260，两个 git 子进程）与 `_environment_metadata`（:262，一次 `uv run` 启动，可能耗时数秒）。SIGTERM 处理器（:336-341）抛出的 KeyboardInterrupt 不在 `_environment_metadata` 的 `except`（:190）覆盖范围内，故该窗口内被终止不会留下任何 `verification-runs/<run_id>.json`，与文档「运行时先写出所有检查均为 `not_run` 的新文件」「突然终止时已有文件保持 `completed=false`」的承诺不符。
- 最小修复：把首次 `_write_evidence` 提到身份探测之前（先写占位字段，探测后原子覆盖），或把文档改为「检查阶段开始前写文件；身份探测阶段被终止可能不产生文件」。

**3. `docs/verification/offline-evidence.md:17` — `environment` 字段的 null 语义比代码强**

- 依据：同上（文档与行为一致）。
- 实际影响：文档称「无法取得时值为 `null`，`missing_reason=environment_unavailable`」；代码 :185-189 按名写 `dependencies.get(name)`，内嵌探测（:149-150）对 `PackageNotFoundError` 也写 `None`，因此存在「个别依赖为 `null` 而 `missing_reason=null`」的合法输出（例如环境未含 dev 组时的 ruff/mypy/pytest）。按文档解析会把部分缺失误读成整体不可用。
- 最小修复：文档补一句「个别依赖不可得时该项为 `null`；仅整体探测失败时 `missing_reason=environment_unavailable`」。

### 判断性（基线 smell）

**4. `scripts/offline_evidence.py:45,28,233-234` — 疑似 Speculative Generality**

- 依据：`default_checks()`（:58-107）从不传 `enabled=False`，也从不覆盖 `contract_names`/`contract_version`；这些开关与 `CheckReason.SKIPPED` 仅由 `tests/test_offline_evidence.py:34-36,170-178` 使用。
- 实际影响：泛化入口允许空检查集合，:329 的 `all(...)` 对空序列为 True → 可写出 `overall=passed`、`completed=true` 而零检查执行，与 AGENTS.md「验证」「没有实际运行的检查，不得声称其已经通过」的意图冲突（当前不可达仅因 `main()` :343-345 恰好传全量计划）。
- 最小修复：删除这些仅测试使用的开关（契约清单按文档 :36 直接改 `CONTRACT_NAMES`），或在 `run_offline_verification` 开头拒绝空 checks。

**5. `scripts/offline_evidence.py:64-105` — 疑似 Duplicated Code**

- 依据：同一命令写两遍——tokens（:64、:69、:77、:84、:89、:94-104）与 `help_zh` 内嵌文本（:65、:71-73、:79-80、:85、:90）。
- 实际影响：没有测试把 `help_zh` 与 `command` 绑定（`tests/test_offline_evidence.py:224-237` 只查 id 与 `--contract` 计数），改命令漏改提示时操作者会按提示重跑错误命令。
- 最小修复：由 `command` 派生提示文本（如 `"请单独运行：" + " ".join(command)`），或加一条断言二者一致的测试。

**6. `tests/test_offline_evidence.py:224-237` — 被删守护的弱化替换**

- 依据：被删用例（`tests/test_cli_help.py` 旧 `123-135` 行，diff 中已移除）逐字断言四条契约名；替代用例只断言 `--contract` 出现 4 次与 2 个名字，`CONTRACT_NAMES`（`scripts/offline_evidence.py:49-54`）与 `ContractName` 亦无交叉断言。同类漂移风险已记录在 `intent/review/contract-help-version-drift-risk.md:31-37`、`intent/review/issue-11-batch-contract-check-review.md:84-87`。
- 实际影响：把 `reuse-assessment` 写成 `reuse-assessments` 仍是 4 次，测试依旧绿，离线验收的契约集合可静默窄化或写错。
- 最小修复：在新用例中断言 `sorted(CONTRACT_NAMES)` 等于四个字面名。

**7. `.gitignore:208` — 分组与内容不符**

- 依据：基线 smell（命名/分组未揭示内容）；该行插在 `# Ruff stuff:`（:206）与 `.ruff_cache/`（:207）之间。
- 实际影响：读者据注释会把 `verification-runs/` 当成 Ruff 缓存，而它是本 diff 的验收证据目录（`docs/verification/offline-evidence.md:5`）。
- 最小修复：移出 Ruff 段，单独一行注释指向该文档。

## Spec

### (a) 规格要求但缺失或部分实现

**A1（P2，判断性风险）入口依赖未锁定的系统 `python3`**

- 位置：`scripts/check-offline:8`；`scripts/offline_evidence.py:340-352`、`:14`（`StrEnum`）
- 依据：父 spec「使用 uv 和提交的 lockfile 管理运行及开发依赖，固定受支持的 Python 版本」「完整检查使用锁文件且可脱网运行」；Issue #12 AC2「失败有可定位且安全的原因」
- 影响：入口从只依赖 `uv` 变为要求 PATH 上存在 ≥3.11 的 `python3`，该解释器不受 `uv.lock` 约束；系统为 3.10 或缺少 `python3` 时以 `ImportError` traceback / 127 结束，既不生成证据也无受控中文原因。证据里的 `environment.python`（样本为 `3.14.4`）取自 `uv run` 子进程，并不描述真正驱动本次运行的解释器。本机 `python3` 版本**未运行核实**。
- 最小修复：`exec uv run --offline --locked python -m scripts.offline_evidence`。

**A2（P2，判断性风险，未运行核实）中断只在子进程执行期间被捕获**

- 位置：`scripts/offline_evidence.py:277-323`（`try` 只包 `subprocess.run`）、`:336-341`；`tests/test_offline_evidence.py:185-221`
- 依据：AC2「跳过、启动失败或中断不能复用上次结果伪造本次通过，失败有可定位且安全的原因」；`docs/verification/offline-evidence.md:5-6`「终端最后打印准确路径和结果」
- 影响：Ctrl-C/SIGTERM 落在两次检查之间（打印、`_write_evidence`、循环本身）不被捕获，进程以未捕获 traceback 退出且不打印证据路径；证据只留 `completed=false`，终端无任何受控原因。现有测试仅 monkeypatch `subprocess.run` 抛 `KeyboardInterrupt`，覆盖不到该路径。
- 最小修复：在 `run_offline_verification`/`main()` 外层捕获 `KeyboardInterrupt`，写入 `interrupted` 终态后再打印路径。

**A3（P2，判断性风险＋确认的文档遗漏）契约清单与版本硬编码，同步说明只覆盖名称**

- 位置：`scripts/offline_evidence.py:49-55`、`:343-345`；`docs/verification/offline-evidence.md:36-37`；`tests/test_offline_evidence.py:224-237`
- 依据：AC3「可以在当前仅研究边界快照存在的工程状态下记录该范围的结果，也能随契约注册扩展；局部通过绝不宣称完整 A1 或阶段 A 通过」；AC1「所验契约的声明版本」
- 影响：入口只能检查硬编码的四份 v1（范围仅函数参数，无 CLI/配置选择），且文档只要求同步 `CONTRACT_NAMES`、未提 `CONTRACT_VERSION`。注册表新增契约或新增 v2 快照而常量未改时，`contracts` 检查与证据仍 `overall=passed`，新快照实际未被检查；替换被删测试的 `command.count("--contract") == 4` 同样不会因注册表扩容而失败。
- 最小修复：测试中断言 `set(CONTRACT_NAMES) == {name.value for name in ContractName}`（版本同理）；文档补 `CONTRACT_VERSION` 同步要求。

**A4（P2，判断性风险）离线入口本身无任何自动化断言**

- 位置：`tests/test_offline_evidence.py:15`（只导入 `Check/default_checks/run_offline_verification`）；`scripts/offline_evidence.py:340-352`；`scripts/check-offline:8`
- 依据：AC5「将证据产出作为开发/验收入口能力……相关测试及完整离线入口实际通过」；父 spec 验收矩阵「安装与入口：……完整检查使用锁文件且可脱网运行」
- 影响：删除 `tests/test_cli_help.py` 原 123-135 行后，仓库内再无测试读取 `scripts/check-offline` 或执行 `main()`：入口与证据计划的接线、`overall`→退出码 0/1 映射、SIGTERM 处理器均无断言，入口改错目标或以 0 退出都不会被发现。
- 最小修复：加薄集成测试运行 `./scripts/check-offline`（或断言其 `exec` 目标）并断言失败运行的退出码与 `verification-runs/*.json`。

### (b) 规格没有要求的行为（范围蔓延）

无。`.gitignore` 条目、`scripts/__init__.py`、文档与 README 段落均为本任务交付所必需，未新增业务 CLI、数据库或调度能力。

### (c) 看起来实现了、但实现可能错误

**C1（P2，确认的文档-实现不一致）早停/失败运行中 `completed` 与契约哈希会误导**

- 位置：`scripts/offline_evidence.py:263`、`:274`、`:325-331`；`docs/verification/offline-evidence.md:13`、`:18`；样本 `verification-runs/4ddcdafe952c46008153b0fe8d0fa842.json:33-44`
- 依据：AC1「由实际执行的离线验证流程生成证据，记录……明确哪些检查真实运行、哪些失败或没有运行」
- 影响：文档定义 `completed` 为「运行是否走到结尾」，实现是 `completed = not interrupted`；首个失败即停止后续检查的运行仍写出 `completed: true`，同一样本 `checks[5].status=not_run` 却仍带四份 `contracts[].schema_sha256`（在检查执行前采集）。按 `completed: true` 或「有哈希」读取会把未执行检查当成已执行、契约当成已核对。
- 最小修复：文档改为「是否未被中断」，或早停时写 `completed=false`；`contracts` 项加检查状态，未运行时哈希置 `null`。

## 汇总

Standards 共 7 条（3 条成文标准违规 + 4 条判断性 smell），Spec 共 5 条（4 条缺失/部分实现 + 1 条实现可疑），范围蔓延 0 条。Standards 轴最严重的是 `scripts/check-offline:8` 入口绕过项目托管环境、失败时既不留证据也无受控原因；Spec 轴最严重的是 A3 契约清单/版本硬编码，注册表扩容后仍可产出 `overall=passed` 的误导证据（C1 的 `completed` 语义与之叠加）。

## 复核与处置（Issue #12 后续修订）

本节记录对上述每条建议的独立核实。原审查结论保留，便于追溯。

| 条目 | 处置 | 核实与改动 |
| --- | --- | --- |
| Standards 1 / Spec A1 | 接受 | Shell 入口改为 `uv run --offline --locked python -m scripts.offline_evidence`，使用项目托管解释器。uv 在 Python 启动前失败时无法由 Python 记录 JSON；文档明确这一启动边界，入口仍返回非零。薄集成测试核对调用参数与退出码。 |
| Standards 2 | 接受 | 首份 JSON 移到身份探测前写入，身份字段先标记未采集；身份探测被中断后写 `incomplete`。文档说明项目 Python 启动前的例外。 |
| Standards 3 | 接受 | 文档区分单个依赖版本为 `null`、整个环境不可用，以及探测尚未开始三种情况。 |
| Standards 4 | 部分接受 | `enabled=False` 用于验证跳过状态，契约范围参数用于验证扩展后的证据范围，保留。增加空检查计划拒绝规则，消除零检查却 `passed` 的真实风险。 |
| Standards 5 | 接受 | 生产检查的中文重跑提示从固定命令参数生成，不再维护第二份命令文本；测试核对二者一致。测试注入的命令仍使用通用提示，避免回显合成敏感参数。 |
| Standards 6 | 接受 | 测试对照权威 `ContractName`、`ContractVersion`，逐一核对每份 `--contract`，避免只靠数量与两项名称通过。 |
| Standards 7 | 接受 | `verification-runs/` 增加独立的 `.gitignore` 注释，不再归在 Ruff 缓存段。 |
| Spec A2 | 接受 | 捕获身份探测和检查之间的中断，保留已完成检查的结果，将尚未运行项记为 `interrupted`，写回可解析证据并由入口打印路径；增加两处中断回归测试。 |
| Spec A3 | 部分接受 | 增加注册表名称与版本守护测试，文档要求新增契约或版本时同步更新两个常量。拒绝额外的运行时契约选择入口：Issue #12 要求记录本次已实现且实际选择的范围，不要求开发/业务 CLI 动态选择；新增版本会先让守护测试失败，阻止静默遗漏。 |
| Spec A4 | 接受 | 增加 Shell 包装层的 `uv` 调用与退出码集成测试、`main()` 失败退出与路径测试。完整入口仍由仓库离线验证命令实际运行，不在 pytest 内递归运行自身。 |
| Spec C1 | 拒绝数据结构改动，接受文档澄清 | `completed=true` 表示记录流程已收尾，可同时有首个失败导致的 `not_run`；`contracts[].schema_sha256` 是磁盘文件身份，不是检查通过证明。是否运行与通过由 `checks[].status` 唯一判断。把未运行项的文件哈希清空会丢失可用身份信息；文档现明确这两层含义。 |

复核验证：`tests/test_offline_evidence.py` 的 11 项测试通过；`./scripts/check-offline`
的 lockfile、格式、静态规则、类型、全部离线测试和冻结契约六项检查通过。未运行
live 来源、模型或 PDF 验收；本证据仍不宣称完整 A1 或阶段 A 通过。
