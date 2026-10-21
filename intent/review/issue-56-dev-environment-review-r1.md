# Code review：issue-56 开发环境只读检查（r1）

- 分支：`main`（HEAD = `9ee343b496530a7ab3ed4b8125a2f2b22c6a16ea`）
- Fixed point：`main~2` = `47c21148f398fa9d8885b95e8e369fdd9d27c549`
- Diff：`git diff main~2...HEAD`（三点，8 文件，+948/−2，2 个 commit）
- Spec 来源：GitHub Issue #56（2026-10-20 改写后的正文 + 全部评论；以改写版正文为最新裁决，评论中较早的「建议范围」已被正文收敛）
- 标准来源：`AGENTS.md`、`CLAUDE.md`、`GLOSSARY.md`、`docs/agents/{python-conventions,testing,cli-output,documentation,invariants,refactor,scope,domain}.md`、`docs/adr/`、`docs/verification/offline-evidence.md`、`pyproject.toml` + Fowler smell 基线（仓库无 `CODING_STANDARDS.md` / `CONTRIBUTING.md`）
- 方式：Standards、Spec 两轴由两个并行只读 subagent（reviewer，无写权限）独立审查后聚合；两轴分列，未混合排序；未修改代码、未创建 commit

审查期间执行的只读验证：`ruff check`、`ruff format --check`、`mypy --strict` 对四个 `.py` 文件全部通过；`pytest -q tests/test_dev_environment.py tests/test_dev_environment_probes.py` → 35 passed。未运行 `./scripts/check-offline`（会写入 `verification-runs/`），因此该验收项计为未验证。

---

## Standards

### 已确认合规

- 原因用 `Reason(StrEnum)` + `CheckResult`/`Report` 受控表达（`scripts/dev_environment.py:24-86`），符合 `python-conventions.md`「用明确的领域类型和受控 enum / reason」。
- 确定性检查与系统探测分层（`dev_environment.py` / `dev_environment_probes.py`），capacity/quota/git/writable 可注入，符合「确定性逻辑与 I/O 分离」与「访问放在可替换接口之后」。
- 文档同步到位：`README.md:15-26`、`docs/agents/testing.md:9-16` 说明用法与阈值；`cli-output.md` 要求的本地中文 `--help`、原因 + 下一步均具备（`dev_environment.py:40-68`、`241-253`）。

### 发现（均为 P2，判断题居多）

1. **硬违规（条件触发）** `scripts/dev-environment:8-11`：`python3` 回退无文档、无覆盖。`pyproject.toml:8` 声明 `>=3.12`，而代码用 `StrEnum`（需 3.11+）；若宿主 `python3` 低于下限，脚本在 `AGENTS.md:6`「命令统一用 uv」之外以 traceback 退出，违反 `docs/agents/cli-output.md`「错误信息写明具体原因和用户可采取的下一步」。`tests/test_dev_environment.py:347-366` 的「无 Traceback」断言只在存在 `.venv` 时成立。

2. **Duplicated Code** `scripts/dev-environment:8` 与 `scripts/dev_environment.py:90-93`：环境路径解析两处——bash 只认 `.venv`，Python 尊重 `UV_PROJECT_ENVIRONMENT`（`testing.md:12` 建议使用该变量）。两条规则不一致，改动需同步两处。

3. **Duplicated Code** `scripts/dev_environment.py:226-228` 与 `291-296` 重复构造「interpreter + temporary_unknown」报告；`171-173` 两处 `CAPACITY_UNKNOWN` 同形。可抽一个 `Report.temporary_unknown(project)` 工厂。

4. **Primitive Obsession / 受控 vocabulary 不完整** `scripts/dev_environment.py:216-238`、`166-209`、`300-308` 及测试断言：检查名（`"capacity"`、`"inodes"`…）与 `facts` 键都是裸字符串，散落多处；键集合正是 `--json` 对外契约却无类型。可加 `Check(StrEnum)`，`facts` 换成小 dataclass。

5. **Divergent Change / 阈值重复** `scripts/dev_environment.py:20-21` 与 `epilog`（`265-266`）、`docs/agents/testing.md:15`、`README.md` 四处同值；改阈值或文案都要动同一文件。阈值宜只在常量与文档中各留一处，帮助文本引用常量。

6. **测试依赖真实环境（判断题）** `tests/test_dev_environment.py:371,400` 直接读仓库真实 `.venv/pyvenv.cfg`，而 `testing.md:12` 允许 `UV_PROJECT_ENVIRONMENT` 指向别处；非固定 fixture，该配置下会 `FileNotFoundError`，与 `docs/agents/testing.md`「常规测试完全离线：使用固定 fixture / mock」不符。最小修复：按被测算逻辑解析环境路径。

**Standards 轴结论**：无 P0/P1；建议随下轮小改动收敛第 2、3 条。

---

## Spec

### 已正确的部分

`.python-version`=`3.14`；临时根 resolve + 真实 `git rev-parse` 隔离测试（含空格路径、符号链接）；容量 `min(statvfs, quota−used)` 且配额不可读→`quota_unknown`；`if_dqblk` 布局/KiB 换算/`QCMD` 编码正确（`dev_environment_probes.py:28-42,62-76`）；ENOSYS/ESRCH/EPERM→未知不崩溃；残留只提示并给 `chmod -R u+w … && rm -rf -- …`；审计钩子测试证明不改文件、`pyvenv.cfg` 不变；`default_checks()` 与 a1–a5 scope 均未登记。

### (a) spec 要求但缺失 / 不完整

1. **P2 未用 `tempfile.gettempdir()`**（spec 正文原文点名），改为候选顺序 + `os.access`：`scripts/dev_environment_probes.py:111-119,108`。与 pytest 实际 basetemp 可能不一致（mode 可写但创建失败、tempfile 内部缓存）；`docs/agents/testing.md:16` 已自述局限，但 `--json` 无机器可读标记。可考虑在 facts 增 `temporary_probe: "access_only"`。

   > 聚合注：spec 同时要求「不修改任何文件」，而 `tempfile.gettempdir()` 会创建探测文件 → 实现方选择了后者并写入 `testing.md`。这是 spec 内部两条要求之间的取舍，不是随意偏离；但 `--json` 使用方无法从结果区分「access-only 判定”。

2. **未验证项**：`./scripts/check-offline` 返回值、全新 worktree 首次 `uv run` 输出 3.14.x、真实配额/inode 判定。

### (b) spec 没要求的行为（scope creep）

1. **P2 自定 `MIN_AVAILABLE_INODES = 50_000` 并作失败门禁**（`scripts/dev_environment.py:21,202-203`）；spec 只说「同时报告可用 inode 数」。inode <50000 而空间充足时会退出 1，spec 未授权该阈值。
2. **P2 `RESIDUE_UNKNOWN` 计入非零退出**（`scripts/dev_environment.py:83`）；spec 只说残留「仅提示…不自动删除」。
3. **P2 `README.md:15,22` 改动与 `UV_PROJECT_ENVIRONMENT` 支持**（`scripts/dev_environment.py:105-108`）不在「范围」1–3 内。
4. **P2 入口 `exec .venv/bin/python -m …`**（`scripts/dev-environment:7-13`），验收要求「Python 命令统一用 `uv run --offline --locked …`」；为满足「不修改任何文件」的取舍合理，`testing.md:14` 已说明。

### (c) 看似实现但可能错误

1. **P2 `read_quota` 的架构白名单**（`scripts/dev_environment_probes.py:49-55`）：与 spec「自 5.1 起，新系统调用在各架构上编号统一，为 443」矛盾；ppc64le/s390x 等架构恒报「配额未知」→ 恒退出 1，「环境健康」不可判定。最小修法：删白名单，靠 ENOSYS 兜底。
2. **P2 `scripts/dev_environment.py:115` 只接受 `X.Y`**：若 `.python-version` 写成 `3.14.1`/`3.14t` 判 `python_unknown` 并失败（spec 规定的文件内容是 `3.14`，属健壮性缺口）。
3. **P2 残留统计遇不可读目录整体降级**（`scripts/dev_environment.py:153`）：`iterdir()` 一次 `OSError` 即放弃，给不出 spec 要求的体积数字；可记录 `unreadable_dirs` 继续统计。

**Spec 轴结论**：无 P0/P1；建议语义上把 inode 门禁与 `residue_unknown` 收敛为 report-only，与 spec 的「报告/提示」措辞对齐。

---

## 汇总

- **Standards**：6 条发现（1 条条件触发的硬违规 + 5 条判断题/基线 smell）；轴内最重者为 `scripts/dev-environment:8-11` 的 `python3` 回退可能在无 `.venv` 时以 traceback 退出，违反 `cli-output.md`。
- **Spec**：9 条发现（(a) 2、(b) 4、(c) 3，均为 P2）；轴内最重者为 `scripts/dev_environment.py:21,202-203` 自加的 `MIN_AVAILABLE_INODES = 50_000` 失败门禁——spec 只要求报告 inode 数，该门禁会在空间充足时导致退出 1。

未验证的 live 行为：`./scripts/check-offline` 是否返回 0、全新 worktree 中 `.python-version` 对 uv 解释器选择的实际效果、真实 tmpfs 配额/inode 的读取结果。`pytest` 相关验证使用私有 `TMPDIR` 运行，避免在 `/tmp` 留下本可归入 #62 的残留。

---

## 实施方逐条核实与处理

关联 [Issue #56：开发环境：固定解释器、临时根与容量的只读检查](https://github.com/MeteoBoy4/PaperRadar/issues/56)。
以上保留原审查结论与当时的行号；以下记录本轮处理，不把判断题直接当成硬违规。
规格重新读取了当前 Issue 正文、全部评论和完整原生依赖关系：没有子票或阻塞项。

### Standards 逐条结论

| 编号 | 判断 | 核实依据与处理 |
| --- | --- | --- |
| S1：宿主 `python3` 回退 | 采纳 | 原入口确实可能在缺少项目环境、宿主解释器过旧或缺失时回显 traceback/英文 shell 错误。入口在导入项目模块前验证 Python >=3.12；失败只显示受控中文原因和下一步。保留直接启动既有解释器，以遵守命令只读的更具体约束，不触发 uv 同步。入口及版本探测均使用隔离/禁用 site/禁止字节码选项。新增独立 checkout 用例，覆盖模拟 3.10/3.11、解释器缺失和正常回退；文档明确回退规则。 |
| S2：两处环境路径解析 | 部分采纳 | 两端规则不一致属实。bash 入口现与检查器一致使用 `UV_PROJECT_ENVIRONMENT`，相对路径以仓库为准；相对/绝对路径及空格路径均有真实入口回归。启动前选择解释器与启动后报告项目环境仍各有最小解析代码，未为了消除这部分重复增加新的启动协议或模块。 |
| S3：重复失败报告 | 部分采纳 | 临时根的自动选择和显式路径验证统一到 `check_environment()`；`main()` 不再重复构造失败报告。容量不可读时两个检查的受控失败结果用同一推导构造。不采用会读取文件系统的 `Report.temporary_unknown(project)` 工厂，避免让报告数据类型承担 I/O。 |
| S4：检查名与 facts 类型 | 不采纳本轮重构建议 | 未发现因此产生的错误；Reason 已封闭，检查名是模块内固定集合，facts 是各检查不同的 JSON 数据。Issue 未要求冻结这份开发 JSON Schema。为六类事实新增多组 dataclass 和转换层会扩大维护面；保留现有小型映射及文本/JSON 同事实测试，不将 Fowler 判断题认定为仓库硬违规。 |
| S5：阈值重复 | 部分采纳 | 帮助和原因文案确有重复常量，现由 `MIN_AVAILABLE_GIB` 同时派生字节阈值和中文帮助。自定 inode 阈值已移除。文档继续直写规格规定的容量以便阅读；README 原本没有数值阈值，审查所称“四处同值”不完全成立。 |
| S6：测试依赖真实 `.venv` | 采纳，采用固定 fixture 修复 | 审计测试确实硬编码读取真实 `.venv/pyvenv.cfg`。现改用测试创建的项目配置与解释器链接，在子进程中显式传入 fixture 项目路径；校验的是该 fixture 配置的字节不变。没有采用仅改为解析真实环境路径的建议，因为那仍依赖调用者机器状态。 |

### Spec 逐条结论

| 编号 | 判断 | 核实依据与处理 |
| --- | --- | --- |
| A1：未直接使用 `tempfile.gettempdir()` | 采纳标记建议，保留只读取舍 | `tempfile.gettempdir()` 首次选择目录会创建并删除探测文件，与同票“不修改任何文件”冲突。继续保留既有安全行为，不改为写探测；JSON 和文本事实现在都包含 `temporary_probe="access_only"`，帮助与文档明确无法保证实际写入成功，也不声称与 pytest 的实际创建探测完全等价。 |
| A2：门禁/worktree/真实探测未验证 | 属于审查未执行项，不是已证实的实现缺陷 | 上轮已有完整门禁证据 `verification-runs/0dea221190ff4232b6cab19d63010f62.json`，全部检查及 A1–A5 结论通过；也已实测新 worktree 首次离线运行输出 3.14.4、主环境配置不变及真实 tmpfs 配额。原报告“审查期间未运行”成立，不应推导为这些能力从未验证。本轮验证另列于下。 |
| B1：自定 inode 门禁 | 采纳 | 当前正文要求报告 inode 数，并未授权 50000 这个阈值。删除该阈值与 `required_inodes`；正数直接报告，耗尽时给受控提示，也不单独改变退出码。0、1、49999 均有回归，未改变容量严格大于 5 GiB 的门禁。 |
| B2：残留未知导致失败 | 采纳 | 残留属于提示信息；统计不完整或目录为符号链接时保留 `residue_unknown`，不单独阻断检查。仍不遍历根符号链接，不为它提供清理命令，不自动删除。容量/配额/隔离/解释器失败仍返回非零。 |
| B3：README 与自定义环境越界 | 不采纳 | `docs/agents/documentation.md` 要求公共入口变更同步 README；新增开发命令的简短指引是必要文档维护。Issue 自身列出 `UV_PROJECT_ENVIRONMENT` 的环境准备命令；识别该环境是准确检查“项目环境”的一部分，没有新增 prepare/复制/安装能力。现补齐了入口一致性。 |
| B4：入口未使用 `uv run` | 保留有依据的只读例外 | Issue 同时说明 `uv run --offline --locked` 可能自动同步环境，而检查命令又不得安装或修改文件；直接调用已存在的 Python 避免此副作用。文档说明此例外，维护者运行 pytest/Ruff/mypy 仍统一通过 `uv run --offline --locked`。不把检查入口改成可能写环境的 uv 调用。 |
| C1：架构白名单 | 部分采纳，拒绝无条件删除 | ppc64le、s390x 被遗漏属实，已按内核官方系统调用表补入，并用注入的 syscall 边界测试编号 443 与配额单位换算。但“所有 ABI 都可直接传 443”并不成立：MIPS 有 4000/5000/6000 基数，x32 有额外 syscall bit。因此保留未核验 ABI 的 unknown 降级，另补 x32 防误调用保护和负例，而不是靠 ENOSYS 猜测调用号。新增架构仅作模拟边界验证，没有宣称真实硬件验收。 |
| C2：支持 `3.14.1`/`3.14t` | 不采纳 | 当前票明确要求文件内容为 `3.14`，代码按该受控形态检查。支持精确补丁版本或 free-threaded 变体将引入本票没有定义的匹配与 ABI 语义；对超出当前契约的写法返回受控 unknown 合理，不作为 bug 扩范围。 |
| C3：不可读目录丢失全部体积 | 采纳 | 扫描逐条捕获读取失败，继续统计可读兄弟项；结果包含 `unreadable_entries`、`size_complete=false` 与已读体积下界，并给出受控中文提示，不回显异常/子路径。固定权限失败注入覆盖了保留至少 64 KiB 可读内容的场景。 |

ABI 核对来源：Linux v6.12 官方 [PowerPC syscall 表](https://github.com/torvalds/linux/blob/v6.12/arch/powerpc/kernel/syscalls/syscall.tbl)、[s390 syscall 表](https://github.com/torvalds/linux/blob/v6.12/arch/s390/kernel/syscalls/syscall.tbl)、[MIPS ABI 基数](https://github.com/torvalds/linux/blob/v6.12/arch/mips/include/uapi/asm/unistd.h)。s390 表通过 GitHub contents API 读取，确认 `443 common quotactl_fd`；不是仅依据旧报告推断。

### 本轮验证

- 先运行新增回归，已复现 inode 阈值误阻断、缺少只读探测标记、残留未知误阻断、缺失/旧版宿主 Python、自定义环境入口选择失败，以及 ppc64le/s390x 被排除。
- 定向命令：`uv run --offline --locked python -m pytest tests/test_dev_environment.py tests/test_dev_environment_probes.py tests/test_dev_environment_entry.py -q`，**50 passed**。
- 新增/修改 Python 文件 Ruff 检查通过；`uv run --offline --locked mypy`：**280 个源文件通过**。
- 本机 `./scripts/dev-environment check --json`：**退出 0**，实际 Python 3.14.4，读取了真实用户配额和 inode；残留仅报告，没有自动删除。
- 主环境 `pyvenv.cfg` 核对基线 SHA-256：`0422dc8a4e2ebc633abe6db363aeca9035c7613789dc5866a096b016a37be1c0`。
- 新 worktree 以 `9ee343b` 为基线（本轮未修改 `.python-version`），首次 `uv run --offline --locked` 离线安装 35 个包并输出 **3.14.4**；测试 worktree 已移除，主环境配置 SHA-256 与上述基线一致。`bash -n scripts/dev-environment` 通过；lockfile、默认检查计划与 a1–a5 scope 的 diff 为空。
- 最终 `./scripts/check-offline` **退出 0**：lockfile、format、lint、types、全部 pytest 与冻结契约均通过，A1、A2-01、完整 A2、A3、A4、A5 结论全部 passed。证据：`verification-runs/cf22bc4e0a7f4ed3a64d862e83a7b16a.json`，同 run ID 下保留各组结论与 pytest 回执。
- 完整门禁后主环境配置 SHA-256 仍与上述基线一致；门禁运行期间未修改代码，结束后仅在本报告补录验证结果。

剩余边界：access-only 探测不能证明真实写入成功；ppc64le/s390x 和旧版宿主版本分支使用模拟边界，未运行这些真实硬件/解释器的 live 验收。没有改动 `uv.lock`、默认检查计划或任何验收 scope，也没有安装 Pi/Docling、访问用户数据库或运行外部模型。
