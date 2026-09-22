# Issue #13 A1 验收结论审查（Standards / Spec 双轴）

- 固定点：`HEAD^`（= `cb05ae57e4a130595c6c07302f45986d99c0a350`）；`HEAD` = `0335689e79030904100b105670c4c19e27e66aa9`
- 范围验证：`git log HEAD^..HEAD --oneline` 恰为 `0335689 Implement A1 acceptance conclusion for Issue #13`；`git diff HEAD^...HEAD --stat` 为 9 文件、+767/-17
- Diff 命令：`git diff HEAD^...HEAD`（三点，相对 merge-base）
- 规格来源：GitHub Issue #13 正文（5 条 Acceptance criteria）+ 全部 comments（1 条维护者四点边界补充，均为本票规格）
- 标准来源：`AGENTS.md`（编码流程 / 验证 / 文档维护 / 数据与版本控制 / LLM 与证据规则 / 范围控制 / 面向用户的行为）、`CONTEXT.md`、`docs/agents/*.md`、`docs/adr/*.md`、`docs/contracts/frozen-contracts.md`、`docs/verification/offline-evidence.md`（本次被改版本）、`README.md`、`pyproject.toml`，外加 Fowler smell 基线
- 审查方式：Standards 与 Spec 两个独立子代理并行、只读、各自 fresh 独立上下文（子代理只运行 git 只读命令与 read/grep，未修改任何文件、未创建 commit、未运行 pytest / check-offline / export / check、未触碰 Issue），聚合者只按 skill 要求分别呈现，不混合排序
- 聚合者只读抽查（未运行测试、未复跑审查）：对 finding 行号逐条核对，修正了子代理原文中的若干偏移——Standards 1 原文 `200-214` 实为 `scripts/a1_acceptance.py:187-214`；Standards 3 原文 `offline_evidence.py:196-208` 实为 `:214-224`；Standards 4 原文 `84-94` 实为 `86-94`（`path.lstat()` 在 :88）；Standards 5 原文 `232-235` 实为 `234-236`；Standards 6 原文 `64-68` 实为 `65-69`；Standards 7 原文 `223-229`、`237` 实为 `223-230`、`240-241`；Standards 8 原文 `41-70` 实为 `45-74`；Spec 5 原文 `157-161`、`check.py:227` 实为 `159-161`、`check.py:216-217`。其余引用（`a1_acceptance.py:43-63/109-113/128-145/299-300/317-329/333-341`、`tests/test_a1_acceptance.py:189-199`、`scripts/check-offline:20-23`、`docs/verification/offline-evidence.md:65`）核对一致
- 未运行验证的声明：两轴均未运行测试；Spec 轴引用的工作区既有结论 `verification-runs/3cb60666…a1.json`（`status=passed`、`a1_verified=true`、commit `0335689`、`dirty=false`）由聚合者抽查确认存在且字段相符，但未在本次审查中重跑入口

## Standards

### 硬性违规

**1. `scripts/a1_acceptance.py:187-214`（`_check_results`）— 受控枚举被重写为裸字符串集合**

- 依据：AGENTS.md「编码流程」原文：「优先使用明确的领域类型和受控 enum / reason，避免 magic string。」
- 实际影响：`:201-204` 重写 `{"passed","failed","not_run"}`，`:205-214` 重写 7 个 reason 值；而 `scripts/offline_evidence.py:20-35` 已有 `CheckStatus` / `CheckReason`。枚举新增值时此处静默把新值降级为 `"invalid"`，两者无同步保护。
- 最小修复：改为 `set(CheckStatus)` / `set(CheckReason)`（或按成员判断），不保留第二份字面量。

### 判断性（基线 smell）

**2. `scripts/a1_acceptance.py:43-63,109-113` 及全部 `_reason("…")` 调用点 — 可能的 Primitive Obsession + Duplicated Code**

- 依据：`reasons[].code` 是 `docs/verification/offline-evidence.md:62-63` 明示的受控词汇，却以裸字符串同时散落在 `_REASON_HELP` 的键与 14 处调用点。
- 实际影响：新增/改名 reason 时需同时改映射与调用，错排时 `_REASON_HELP[code]` 抛 `KeyError`（而非给用户可操作信息）。
- 最小修复：定义 `A1ReasonCode(StrEnum)`，`_reason` 只接受该类型。

**3. `scripts/a1_acceptance.py:317-329` vs `scripts/offline_evidence.py:214-224` — 可能的 Duplicated Code**

- 依据：两处重复「临时文件 + fsync + 发布」的原子写形状；`offline_evidence._write_evidence` 用 `os.replace`（可覆盖），新代码用 `os.link`（不覆盖），同一个「写 JSON 产物」概念分叉出两种语义。
- 实际影响：后续修改原子写（如 fsync 目录、权限）需改两处；`os.link` 在跨文件系统/不支持硬链接的目标上抛 `OSError`，行为与既有证据写入不一致。
- 最小修复：抽共享 `write_json_atomic(path, payload, *, overwrite: bool)`，两处调用。

**4. `scripts/a1_acceptance.py:86-94`（`_worktree_sha256`）— 可能的 Mysterious Name / 死分支**

- 依据：`git ls-files --cached` 会列出「索引中但磁盘已删」的 tracked 文件，此时 `path.lstat()`（:88）先抛 `FileNotFoundError`，被 :96-97 的 `except OSError` 吞掉并让整份 worktree 哈希返回 `None`；`else: b"missing\0"`（:94）不可达。
- 实际影响：删除一个 tracked 文件会从「哈希不同」退化为「哈希不可得」，结论统一下 `identity_changed`（提示文本为「HEAD、工作树或 lockfile 与本次检查身份不一致」），掩盖真实原因；哈希本身也不稳定。
- 最小修复：逐项用 `os.path.lexists` 判定，缺失项写入显式标记；或删除死分支并把该分支语义改名。

**5. `scripts/a1_acceptance.py:234-236,237-280` — 可能的报告噪声：证据不可读时继续级联判定**

- 依据：AGENTS.md「面向用户的行为」原文：「错误信息应说明可操作的具体原因，不要用模糊状态隐藏失败。」；对照 `docs/verification/offline-evidence.md:63`「`reasons` 是带 `code`、中文处理建议及可选检查/契约 `item` 的列表」。
- 实际影响：`evidence is None` 时仅追加 `evidence_unavailable`，随后仍继续对空 dict 做 identity/scope/completed/overall 判定，产出 `evidence_identity_mismatch`、`evidence_scope_mismatch`、`run_incomplete`、`offline_checks_not_passed`、`check_scope_mismatch`、`contract_scope_mismatch` 等一串由「无输入」派生的理由，淹没唯一真因。
- 最小修复：证据不可读/非 dict 时记录单一理由并提前返回（仍输出带 `status=failed` 的结论文件）。

**6. `scripts/a1_acceptance.py:65-69`（`RunIdentity`）— 可能的 Primitive Obsession**

- 依据：`code: dict[str, str | bool | None]` 承载 HEAD 提交与 dirty 标记，消费方靠 `.code["commit"]`、`.code["dirty"]` 字符串键访问；键名事实来源在 `scripts/offline_evidence.py:git_metadata`。
- 实际影响：键名拼错、`git_metadata` 改键名时无类型保护，错键得到 `None` 而非报错，可能与「git 不可用」混淆。
- 最小修复：改为小 frozen 类型（如 `CodeIdentity(commit, dirty)`）或直接 `TypedDict`。

**7. `scripts/a1_acceptance.py:223-230,240-241` — 可能的 Speculative Generality**

- 依据：`expected_run_id` 的两个调用点中，`run_a1_verification:339-340` 传入的正是 `evidence["run_id"]`，而 `write_a1_conclusion` 内部又要求它与 `evidence_path.stem` 相等（:240-241），即参数与文件名互相印证但都源自同一证据；`contract_target`（:228）仅测试使用。
- 实际影响：多一个可从 `evidence_path.stem` 推导的参数，增加调用方传错的空间；`:240-241` 的双重比对逻辑模糊。
- 最小修复：由 `evidence_path.stem` 推导 run_id；`contract_target` 若只为测试保留应注明，或改为测试专用注入点。

**8. `docs/verification/offline-evidence.md:45-74` — 文档维护判断：A1 结论缺字段表且判定规则五处重复**

- 依据：AGENTS.md「文档维护」要求持久化或 Schema 行为同步文档；`#12` 证据在 `:21-40` 有逐字段表格，A1 结论（新增机器可读 Schema）只以散文描述。
- 实际影响：同一判定规则（六检查全通过 + 四快照一致 + 身份一致）同时出现在 `docs/verification/offline-evidence.md:58-61`、`README.md:107-110`、`docs/contracts/frozen-contracts.md:210-213`、`src/paper_radar/cli.py:64-66`、`scripts/check-offline:11-15`，规则改动需同步五处，任一处漏改即成文档漂移。
- 最小修复：为 `.a1.json` 补一张字段表（与 #12 表格同格式），其余位置只保留一句摘要 + 链接。

**9. `pyproject.toml [tool.mypy] files = ["src", "tests"]`（既有配置，被本 diff 触及范围）— 新脚本不在类型检查范围**

- 依据：AGENTS.md「验证」要求完整离线验证覆盖改动；`scripts/a1_acceptance.py` 新增 363 行并承载 A1 结论判定，但 `check-offline` 的 types 检查不扫描 `scripts/`。
- 实际影响：产出 A1 结论的代码的静态错误（如 `baseline.code["commit"]` 键错误、`_REASON_HELP` 索引错误）不会被 types 检查发现。
- 最小修复：把 `scripts` 纳入 `[tool.mypy] files`（如为 `scripts/offline_evidence.py`、`a1_acceptance.py` 补注解）。

未发现伪造 evidence、未发现新增 V2 能力、未发现文档与实现的行为性矛盾。

## Spec

### (a) 规格要求但缺失/部分实现

**1. `scripts/a1_acceptance.py:299-300`、`:128-145` — A1 必需范围只有命令级锚点**

- 依据：AC1「固定 A1 必需检查范围：工程/帮助、三种输出完整验证、原因组合、四份正式快照、单份和批量导出/检查、冲突/恢复、隐私和模块边界、证据记录」；AC2「不以测试进程退出 0 单独推断」。
- 实际影响：结论只有 6 个 `required_checks`（命令 id：lockfile / format / lint / types / tests / contracts）+ 4 个契约名；`_check_scope` 只核对 id、status、reason、exit_code。上述 8 类契约能力当前唯一信号是 `tests` 这一个聚合退出码——删除或改名 `tests/test_contract_export.py`、`tests/test_screening_architecture.py` 等能力测试后 pytest 仍退出 0，结论照样 `a1_verified=true`。
- 最小修复：结论固定 `required_test_modules`（路径 + 内容哈希），缺失或漂移即 `failed`；范围清单与 `CONTRACT_NAMES` 一样受测试与注册表交叉核对。

**2. `tests/test_a1_acceptance.py:189-199` — `--help` 守护对真实仓库无区分能力**

- 依据：AC 边界③要求负例不污染已提交 `contracts/` 与真实 `verification-runs/`；`docs/verification/offline-evidence.md:3`「`--help` 只打印中文帮助，不启动检查或写入证据」。
- 实际影响：`scripts/check-offline:4-5` 先把 cwd 设为真实仓库根，脚本又以绝对路径调用（`tests/test_a1_acceptance.py:191`），因此该用例的 `cwd=tmp_path` 与「`list(tmp_path.iterdir()) == []`」断言对真实仓库无约束；若回归使 `--help` 继续执行完整计划，stdout 仍含断言所需的 `"A1"`（`scripts/a1_acceptance.py:342-345` 打印 `[A1 验收] …`），用例全绿且在真实仓库写入证据。
- 最小修复：比照 `tests/test_offline_evidence.py:262-266` 把 wrapper 复制进临时 git 仓库运行，并断言 stdout 不含 `[离线检查]` / `[A1 验收]`、`verification-runs/` 未新增文件。

**3. `scripts/a1_acceptance.py:333-341` — 中断窗口无结论文件**

- 依据：AC「批量中断时不可通过」；`docs/verification/offline-evidence.md:65`「运行未收尾或中断为 `incomplete`」。
- 实际影响：`run_a1_verification:338-341` 在 `run_offline_verification` 收尾后、`write_a1_conclusion` 内 `capture_identity`（:232）阶段收到 SIGTERM 时，KeyboardInterrupt 未被捕获，入口以 traceback 退出，只留下 `<run_id>.json`、无 `.a1.json`；文档承诺的中断 `incomplete` 结论不成立。（今日真实入口的 e2e 用例用假 uv 在 `contracts check` 阶段注入中断，走的是证据侧 `incomplete` 路径，不覆盖该窗口。）
- 最小修复：在 `run_a1_verification` 包 `try/except KeyboardInterrupt`，中断时写入 `status=incomplete`、`reason=run_incomplete` 的结论文件并保留非零退出。

### (b) 范围蔓延

**4. `scripts/check-offline:20-23` — 未知参数 `exit 2` 分支未被规格要求且未写入帮助**

- 依据：维护者 comment 边界④只要求「同步 …… 相关 `--help`」；AC5 要求「不新增阶段 A 剩余能力」。
- 实际影响：帮助文本（:9-15）未声明「未知参数返回 2」，用户传入参数时行为不可预期；该退出码语义未与既有 `paper-radar` 的错误码约定（校验/版本冲突/检查不一致返回非零，见 `docs/contracts/frozen-contracts.md:22-24`）对齐说明。
- 最小修复：在帮助中补一行「未知参数：返回 2 并提示 --help」，或改为忽略多余参数保持 `set -euo pipefail` 的默认行为。

### (c) 看似实现但实现错误

**5. `scripts/a1_acceptance.py:159-161` — `ContractCheckError` 一律记为 `snapshot_invalid`**

- 依据：AC2「给出未通过/未完成及具体原因」；`src/paper_radar/contracts/check.py:216-217` 显示 `check_frozen_contracts` 只在选择无效时抛 `ContractCheckError`（逐份错误在 `:233` 起被转为 item），即唯一可达类别是 `invalid_selection`。
- 实际影响：契约名或版本未实现时，原因误报为「冻结快照缺失或不一致；逐项运行 contracts check 定位并修复」，指向错误修复动作（4 份 v1 均已实现，今日不可达）。
- 最小修复：按 `error.category` 分流 reason code（`invalid_selection` → `contract_scope_mismatch` 或新 `invalid_contract_selection`），仅 `MISSING_SNAPSHOT` 等快照类归为 `snapshot_invalid`。

### 透明说明与残余风险（Spec 轴子代理声明）

- 第一条 `git diff` 命令曾向仓库外 `/tmp/a1diff.txt` 重定向（仓库零写入）；评审前后 `git status --porcelain` 均为空、`verification-runs/` 条目数 18 未变、HEAD 未变（聚合者复核一致）。
- `write_a1_conclusion` 是公共 Python API，可传入任意历史 evidence：只要 run_id 命名、scope、快照哈希与本次 HEAD/工作树/lockfile 一致，仍会产出 `passed` 结论；CLI 无此路径，边界①「不复用历史 evidence」目前只由调用方保证。
- `verification-runs/` 被 gitignore，结论与证据不进版本控制，评审者只能看工作区文件。
- 三份结论文档（`offline-evidence.md`、`frozen-contracts.md`、`README.md`）与 `cli.py`、`check-offline --help` 逐条比对后未发现其他不符。

## 汇总

- Standards：9 条（1 条硬性违规 + 8 条判断性）；本轴最严重为 H1：`scripts/a1_acceptance.py:187-214` 把 `CheckStatus` / `CheckReason` 受控枚举重写为裸字符串集合，新增枚举值时静默降级为 `"invalid"`。
- Spec：5 条（3 条缺失/部分实现 + 1 条范围蔓延 + 1 条实现错误）；本轴最严重为 S1：`scripts/a1_acceptance.py:299-300`、`:128-145` 的 A1 必需范围仅到命令级锚点，删除能力测试后仍可输出 `a1_verified=true`，与 AC1/AC2 直接冲突。

## 实施者逐条复核与处理

以下判断针对报告所审查的 `0335689`；保留上文原始发现，便于复核其依据。

| 编号 | 判断 | 处理与依据 |
| --- | --- | --- |
| Standards 1 | 采纳 | `_check_results` 复用 `CheckStatus`、`CheckReason`，不再维护第二份状态和原因字面量。 |
| Standards 2 | 采纳 | 新增 `A1ReasonCode`；结论原因的调用点与中文说明使用同一受控枚举。 |
| Standards 3 | 不采纳抽取建议 | #12 证据需要原子**更新**同一文件，#13 结论需要原子**发布且禁止覆盖**。共享一个带 `overwrite` 开关的写入器会把不同的持久化语义混在一起。当前临时文件与结论文件位于同一目录，审查所说的“跨文件系统硬链接”在该调用路径中不会发生；不支持硬链接的文件系统会明确失败，不会产生错误的通过结论。 |
| Standards 4 | 采纳 | 已删除的受控文件写入确定性的 `missing` 标记，保留可比较的工作树哈希；另有文件类型 `other` 标记和回归测试。 |
| Standards 5 | 采纳 | 证据不可解析时只报告 `evidence_unavailable`，仍发布 `failed` 结论，不再派生一串无输入造成的错误。 |
| Standards 6 | 采纳 | `git_metadata` 和 `RunIdentity` 共享 `CodeIdentity` TypedDict；完整类型检查覆盖 `scripts/`。 |
| Standards 7 | 不采纳 | `expected_run_id` 由**本次执行在内存中返回的证据**提供，与从磁盘读取的 `run_id`、文件名核对；直接改成文件名会丢失这一交叉核对。`contract_target` 是临时目标的测试 seam，避免负例污染已提交快照。生产入口只接收本次运行返回的证据路径。 |
| Standards 8 | 部分采纳 | 已为 `.a1.json` 补逐字段表；README、契约文档和 `--help` 只保留各入口需要的一句用途摘要与链接/路径，不移除用户在该入口判断副作用所需的简要说明。 |
| Standards 9 | 采纳 | `pyproject.toml` 的 mypy 检查范围加入 `scripts`，完整离线入口现在类型检查 A1 判定代码。 |
| Spec 1 | 采纳 | `scripts/a1_scope.py` 固定已交付能力的测试模块路径和内容 SHA-256；A1 结论逐项记录并拒绝缺失/漂移。`tests` 执行清除外部 `PYTEST_ADDOPTS`，避免环境变量缩小测试范围。固定模块变更须审查并更新清单。 |
| Spec 2 | 采纳 | `--help` 测试改在临时仓库复制脚本运行，并确认没有检查或 A1 运行输出、没有新建证据目录。 |
| Spec 3 | 采纳 | #12 证据返回后、A1 结论发布前的可捕获中断会重试生成 `incomplete` 结论；回归测试在身份采集处注入中断。强制终止无法保证写出结论，文档已写明。 |
| Spec 4 | 不采纳“范围蔓延”判断，采纳帮助补充 | 拒绝未知参数防止误把带参数的命令当成完整验证，是现有脚本入口的输入校验；帮助已说明返回 2。没有新增业务能力。 |
| Spec 5 | 采纳 | `ContractCheckErrorCategory.INVALID_SELECTION` 归为契约选择/范围错误，不再误报为快照损坏；逐份快照失败仍由公共检查结果报告。 |

报告指出的历史证据 API 风险需按调用边界解释：`write_a1_conclusion` 是脚本内的判定函数，生产入口 `run_a1_verification` 只把**本次** `run_offline_verification` 返回的路径和 run_id 传入；没有读取任意历史证据的 CLI。直接调用该 Python 函数并自造输入不能视为产品验收入口。`verification-runs/` 继续忽略版本控制，提交后可从干净 HEAD 再运行入口生成本地可复核结果。
