# Issue #61 双轴审查：回执隔离与进程组回收

- 审查范围：`git diff HEAD~2...HEAD`（固定点 `HEAD~2` = `02895f9`，HEAD = `779f2b6`）
- 提交：`800bfc4` fix: isolate offline verification receipts and process groups (#61)、`779f2b6` fix: await group exit before interrupted evidence (#61)
- 变更规模：20 个文件，+423/−79
- 规格来源：GitHub issue #61（body，无评论；labels: `bug`、`ready-for-agent`）
- 标准来源：`AGENTS.md`、`docs/agents/{python-conventions,testing,cli-output,documentation,invariants}.md`、`docs/verification/offline-evidence.md`、`GLOSSARY.md`，另加 skill 规定的 Fowler 坏味道基线
- 方式：Standards 与 Spec 两个只读子代理并行审查，本文件只做汇总，不跨轴重排
- 未执行：`./scripts/check-offline`、pytest、Ruff、mypy（本次要求不修改代码；运行验收两条为「未验证」）。汇总者另做了只读 SHA-256 抽查：`scripts/offline_evidence.py`、`tests/a2_full_support.py`、`tests/fixtures/verification_transcripts.json` 与五个 scope 文件在所有绑定方（含 a2_full/a3/a4/a5 间的级联）的登记哈希与实际字节全部一致，级联顺序 a2_full→a3→a4→a5 成立。

## Standards

### 硬违规（文档化标准）：未发现

已逐条核对的新增文档声明与代码（`docs/verification/offline-evidence.md` 新段落 ↔ `scripts/offline_evidence.py`）：

- 「清除继承的 `PAPER_RADAR_TEST_RECEIPT`/`PAPER_RADAR_TEST_RUN_ID`；仅 `tests` 重新绑定」↔ `_child_environment()`（offline_evidence.py:130-134）与 `_run_checks` 中 `if check.id == "tests"` 分支，一致。
- 「独立会话和进程组」↔ `_run_check` 的 `start_new_session=True`。
- 「SIGTERM 中断」在生产可用：`main()` 有 `signal.signal(signal.SIGTERM, _interrupt)`（offline_evidence.py:487），测试 controller 自装 handler 属合法复现。
- 「等待至多两秒」↔ `deadline = time.monotonic() + 2`；「清理期间重复 SIGINT/SIGTERM 不打断」↔ SIG_IGN + finally 恢复；「/proc 核对、pidfd 等待、复扫」↔ `_kill_and_wait_for_group` 的 `empty_scan` 双扫描。
- 「15 个新增用例，3→18」：10（嵌套）+1（环境归属）+4（中断）=15；`a2_full_scope.py`、`a4_scope.py` 计数均改为 18。
- 各 scope 文件哈希散点重绑是 `offline-evidence.md`「固定 scope 维护审计」规定流程，非 Shotgun Surgery。
- `cli-output.md`、`GLOSSARY.md`、`invariants.md`、`documentation.md`：无公共契约/术语/架构偏离，无需 ADR 或 glossary 条目；终端 fixture 仅删 `environment_unavailable` 行，已写入文档。

**未验证项（需补跑）**：登记哈希与实际字节一致性（汇总者已只读抽查通过）及 `./scripts/check-offline` 返回 0——子代理只读审查无法运行。

### 判断项（坏味道基线，均非硬违规）

1. **Data Clumps**：`(tmp_path, monkeypatch)` 成对穿越 `fake_checks` 四层链与约 15 个调用点（tests/a2_full_support.py:78、a3_acceptance_support.py:42、a4:43、a5:42 及各 `test_*_entry.py` hunk）。可捆成 fixture 或小上下文对象。
2. **Duplicated Code / Middle Man（疑似）**：a3/a4/a5 的 `fake_checks` 主体仍是「转发上一层 + 复写同一段 `write_receipt.py` 三行脚本」，diff 只把参数继续穿透；形状可上提到 `a2_full_support`。属既有形状被传播。
3. **Primitive Obsession（疑似）**：`_stop_process_group` 把 `process.pid` 当 pgid 用（offline_evidence.py:296、303、308），仅因 `_run_check` 的 `start_new_session=True` 才成立；显式传 pgid 或小类型可让该不变量诚实。

### 子代理结论：OK with notes

文档声明与实现一致，无硬违规；三个判断项可留待后续清理。合并前须补跑 `./scripts/audit-verification-scope` 与完整 `./scripts/check-offline` 确认哈希登记与全绿。

## Spec

**审查方式**：完整读取 diff（1072 行）并核对 `scripts/offline_evidence.py`、`tests/a2_full_support.py`、各 scope 文件与 docs。无法运行测试。

- **Correct（spec 各条均已落实）**：
  - 「移除两个回执变量；只有 tests 检查重新设置」：`offline_evidence.py::_child_environment`（L130-134）应用于探测与全部检查；tests 分支重设（L360-365）。新用例 `test_only_tests_check_receives_its_own_receipt_environment` 直接断言 7 次子进程的变量归属。
  - 「独立进程组…SIGTERM→限时→SIGKILL，全部回收后才记录 interrupted」：`_run_check` 用 `start_new_session=True`；`_stop_process_group`（2 秒宽限）+ `_kill_and_wait_for_group`（/proc+pidfd）后 `process.wait()` 才落 `interrupted`。SIGTERM 入口已有（`offline_evidence.py:487`、`a2_full_acceptance.py:442`）。
  - 「假 uv 精确匹配 `-m pytest`」：`a2_full_support.py:108` 改为 `*" -m pytest"*`，fixture 内 `monkeypatch.delenv` 两个变量，a3/a4/a5 支持层级联传参，全部调用点已更新（grep 核对无遗漏）。
  - 验收回归测试：哨兵测试覆盖 spec 点名的 5 个模块 ×「不得被创建或改写」；静态推断修复前会失败（探测命令以独立参数传 `pytest`，旧模式 `*" pytest"*` 命中后 writer 写哨兵）。进程组测试用 socket 屏障、无固定 sleep、pidfd 验证全组退出且标记文件不出现，预修复路径断言必失败。
  - 「format_version/六项检查/reason 词表/中断语义不变」：仅 fixture 删除假回执伪影 `environment_unavailable` 行，其余字节保留。
  - 级联重绑：`offline_evidence.py` 在 a2_full/a3/a4/a5、`a2_full_support.py` 在 a2_full/a4/a5、`a1_scope.py`/fixture 等绑定方均更新，计数 3→18（实际 18 个用例，已数）。
- **Finding（P2，仅报告）**：
  1. `git_metadata` 的两个 git 子进程也套用 `_child_environment`（offline_evidence.py:151,160），超出 spec「任何检查或环境探测子进程」字面范围；无害的一致化。
  2. docs 新增段落写入「15 个新增用例…从 3 例增至 18 例」等测试登记细节，超出 spec 对该文档的要求（仅要求写明回执语义），属易过时的维护负担。
  3. `_kill_and_wait_for_group` 中 `poller.poll()` 无超时（offline_evidence.py:289）：组成员若处 D 状态，SIGKILL 不生效，中断路径将无限挂起而非记录 interrupted。符合 spec「全部回收后才记录」，但为极端场景挂起风险。
- **未验证**：验收两条运行项（先跑相关测试、`./scripts/check-offline` 返回 0）因只读环境无法执行。

**子代理结论：OK with notes**（P2 项不阻塞；运行验收需补跑）。

## 汇总（每轴一行，不跨轴排名）

- **Standards**：共 3 项（0 硬违规 + 3 判断项）；轴内最重 = `fake_checks` 四层链的 `(tmp_path, monkeypatch)` Data Clumps。
- **Spec**：spec 要求项全部落实，另 3 项 P2 发现（2 处轻微超范围 + 1 处极端挂起风险）；轴内最重 = `_kill_and_wait_for_group` 的 `poller.poll()` 无超时，D 状态组成员可致中断路径无限挂起。


## 2026-10-21 实现复核与处置

关联 [Issue #61](https://github.com/MeteoBoy4/PaperRadar/issues/61)。以上保留原始只读审查结论；其中“未执行”“未验证”描述的是原审查时点，本节记录本轮实际处理与验证。复核基线为 `779f2b6`，未提交本轮变更前核对原规格与安全约束。

### 逐条结论

| 审查项 | 判断与处置 | 依据与边界 |
| --- | --- | --- |
| Standards 1：`(tmp_path, monkeypatch)` Data Clumps | 部分接受，合并 Standards 2 处理；移除穿越四层的转发链 | 两个参数本身是 pytest 常规依赖，不构成必须引入上下文类型的证据。现在只传给 `a2_full_support.fake_checks` 的单一实现；本地清理继承回执变量的行为保留，不扩大到全局 fixture。 |
| Standards 2：重复 writer / Middle Man | 接受；删除 a3/a4/a5 的 `fake_checks` 包装与相同脚本重写 | 入口测试直接调用唯一 `a2_full_support.fake_checks`，通过必填 keyword `receipt` 指定原来各自使用的 A3 或 A5 完整载荷；各层 `passed_receipt` 的范围组合职责保持原状。写脚本从至多四次降为一次。 |
| Standards 3：将 `process.pid` 隐式当 pgid | 接受明确不变量的建议，不新增仅包装整数的类型 | 在 `start_new_session=True` 的启动边界命名 `process_group = process.pid` 并注明 POSIX 组长约束，显式传入 `_stop_process_group`；清理阶段仅使用该组标识。真实子进程回归继续验证 PGID 等于 SID 且不同于控制方 PID。 |
| Spec 1：`git_metadata` 清理回执变量被认为越界 | 拒绝移除防护；保留现状 | Git 身份探测同属控制方启动的子进程，与检查/环境探测共享继承环境边界；回执变量仅授予本次 tests 是更完整且无副作用的约束。保留隔离不更改 Git 身份算法或证据字段。原审查也已将其判断为无害的一致化，无合理依据恢复外层回执变量泄漏。 |
| Spec 2：指南记载测试数量等历史细节 | 接受；删除指南里的 #61 用例数量、替身、scope 与终端 fixture 修改历史 | 稳定指南保留用户可观察的回执隔离、进程组回收与证据语义；实施历史移至本节，避免与实际清单发生漂移。 |
| Spec 3：`poller.poll()` 无总超时，D 状态可持续阻塞 | 风险成立；拒绝直接加总超时退出的改法，保留安全行为并明确边界 | Issue 要求“全部回收后才记录 interrupted”，且禁止改变中断语义与 reason 词表。超时后正常收尾会谎报回收；抛出 `TimeoutError` 又会被当前 OSError 分支误记为 `launch_error`，不能作为兼容修复。指南明确两秒仅是 SIGTERM 宽限期，SIGKILL 后等待真实退出无总超时；D 状态依赖宿主 I/O 恢复，强杀控制方时已有证据仍不完整。本轮未声称修复该内核阻塞风险。 |

### 从稳定指南移出的 #61 实施历史

原交付新增 15 个回归参数实例，`test_verification_integrity.py` 从 3 例增至 18 例：五个受影响模块 × 外层回执存在/不存在共 10 例、环境探测与六项检查的变量归属 1 例，以及 SIGINT/SIGTERM × 后代是否忽略 SIGTERM 的真实进程场景 4 例。原用例保留，完整 A2/A4 显式登记。进程场景使用 socket 屏障、pidfd 和单 CPU 文件 I/O 审计，确认写中断证据前后代已退出，不以固定 sleep 推断退出。原 A1 中断替身改为 Popen，原分母不变。failed/interrupted 终端 fixture 仅去掉假 uv 环境探测误命中产生的 `environment_unavailable` 行。本轮保留全部历史回归与 fixture，不修改用例数量、证据格式、六项检查、原因词表或结论判据。

### 本轮实现与 scope 审计

本轮修改限于验证控制方、上述测试支撑和直接调用者、离线指南及本报告。没有新增行为 Bug 修复或新测试边界：本轮是测试支撑去重、显式化进程组身份和文档纠正，沿用用户已确认的入口回执隔离与真实控制方子进程两个边界，不为行为不变的重构新增实现耦合测试。没有新红灯测试；已有 18 例 integrity 回归在修改前通过，用于重构前后行为对照。

先只读运行 scope 审计，确认本次漂移仅来自已审阅的 `scripts/offline_evidence.py`、四份测试支撑、七份直接入口/验证测试。逐项确认显式路径与候选 SHA-256 后，以字面量重绑，按完整 A2 → A3 → A4 → A5 顺序更新下游引用。未更新 A1、optional A2-01、固定分母、向量或终端 fixture，也没有用实际值批量刷新所有 expected。

- `scripts/a2_full_scope.py`：`6a9b14f6e6739c8166f4a2f8316a790511872126e781bed347e157e691103caa`
- `scripts/a3_scope.py`：`a542200ab7db153c90c27491f421cf09f02096b485aab1088103653f6e80f259`
- `scripts/a4_scope.py`：`621da3014fc45815609605bc5be4d52244db78d30a8a430241a3dba602ff2693`

### 实际验证

- 修改前：`uv run --offline --locked pytest -q tests/test_verification_integrity.py`：18 passed。
- `./scripts/dev-environment check`：返回 0，Python 3.14.4，容量严格大于 5 GiB；pytest 残留只作提示。
- `uv run --offline --locked ruff check`（本轮 12 个 Python 逻辑文件，含 `--fix` 整理 7 个导入问题）及 `ruff format`：通过。
- `uv run --offline --locked mypy src scripts tests`：返回 0，288 个文件无类型问题。
- `./scripts/audit-verification-scope --collect --json`：返回 0，126 个显式模块收集核对通过，`affected_groups=[]`、`issues=[]`。

- `uv run --offline --locked pytest -q tests/test_verification_integrity.py tests/test_verification_run.py tests/test_verification_compatibility.py tests/test_a2_full_entry.py tests/test_a3_entry.py tests/test_a4_entry.py tests/test_a5_entry.py tests/test_offline_evidence.py tests/test_a1_acceptance.py`：返回 0，75 passed in 46.68s。
- 完整门槛前再次执行 `./scripts/dev-environment check`：返回 0；随后 `./scripts/check-offline` 返回 0，lockfile、format、lint、types、全部 pytest、冻结契约六项全部 passed。
- 本次 `run_id=0a0606f8cfd544929c10e8302468770b`；[基础证据](../../verification-runs/0a0606f8cfd544929c10e8302468770b.json)为 `overall=passed`、`completed=true`，同次 A1、A2-01、完整 A2、A3、A4、A5 均 passed。同次 pytest 回执 `completed=true`、`exit_code=0`，固定清单 126 个模块 collected=passed=2534，failed/skipped/deselected/incomplete 均为 0。
- `git diff --check`：返回 0。

本轮完整门槛已完成，补齐原审查未执行的运行验收。完整门槛运行中工作树保持不变，结束后仅补充本报告（不受 scope 绑定）的验证事实；证据对应验证时点，之后提交与报告落字不表示重跑。未运行 live 外部服务、未操作用户数据库；未制造真实内核 D 状态，无法证明宿主 I/O 无期限阻塞时控制方能自行结束。
