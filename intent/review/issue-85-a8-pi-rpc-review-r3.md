# 阶段 A8 双轴审查 r3（#85 / #86–#91）

- 固定点：`main` = `7473c1c8cd986827e55d9e8d12fa8cc18bf7ba89`
- 被审：HEAD = `da9b9ff6f0007822dc26e6f2454baae389281e9a`（分支 `integration/issue-85-pi-rpc`）；审阅开始时工作树干净
- diff：`git diff main...HEAD`（三点，对 merge-base）＝ 74 files, +9286/−84；`git log main..HEAD --oneline` 共 14 个提交
- 提交列表：`7a8dcbc`(#86) → `ca845b8`(merge) → `fdd1fe9`(#87) → `387e4c4`(merge) → `8f50be1`(#88) → `c809fdc`(merge) → `8196f93`(#89) → `297e092`(merge) → `c03a89f`(#90) → `0a7137f`(merge) → `0270c97`(#91) → `b1014e3`(merge) → `465b3af`(审阅修复) → `da9b9ff`(merge)
- 两轴分别由独立只读子 agent 执行，互不共享上下文；本文按轴分列，**未跨轴合并或重排**
- 与 #85 完成评论所称「双轴审阅完成」的关系：本条为该分支的第三次独立双轴审阅（r3），结论按本次两轴报告独立给出，不继承此前结论

## 工具与来源（两轴共同）

- **规格来源**（按 `docs/agents/issue-tracker.md`，评论优先于正文，已落盘于工作树外）：
  - `/tmp/a8_bodies.txt`：#85–#91 Issue 正文；#85 含 Problem Statement / Solution / 40 条 User Stories / 23 条 Implementation Decisions / Testing Decisions 验收面表 / Out of Scope / Further Notes
  - `/tmp/a8_issues.txt`：#85–#91 全部评论，含 #85 的四条 spec 补充评论、D1–D4 裁决结论、P3 采纳，以及 #86–#91 各自的补充边界与实现者完成报告
  - 优先级：D1–D4 裁决 > #85 补充评论（「建议默认」）> #85 正文 > 子票正文 > 子票补充评论；实现者完成报告仅作「实现了什么」的线索，须与代码核对
- **标准来源**（仓库无 `CODING_STANDARDS.md` / `CONTRIBUTING.md`）：`AGENTS.md`、`CLAUDE.md`、`docs/agents/{python-conventions,testing,invariants,llm-evidence,documentation,cli-output,scope,refactor,domain}.md`、`GLOSSARY.md`、`README.md`、`docs/contracts/{pi-rpc,adapter-config,screening-tasks,verification-status}.md`、`docs/verification/{a8-requirements,offline-evidence}.md`、`docs/adr/0026-*.md`、`scripts/{a8_scope.py,a8_acceptance.py,check-offline,verification_status.py}`、`intent/draft.md` 相关章节，另加 skill 指定的 smell baseline（已在两轴提示词中全文粘贴）
- **两轴子 agent 实际工具**：均使用 `oracle` 角色，**具备 `bash`**（只读 git/rg/sed/python3/pytest/ruff/mypy）以及 `read`/`grep`/`find`/`ls`；**无 `edit`/`write`**，未改仓库、未建 commit、未改 Issue 状态
- **本会话实跑**（由两轴子 agent 各自执行）：
  - Standards 轴：`pytest -q tests/test_a8_*.py -p no:randomly` → **613 passed / 95.76s**；`ruff check`/`ruff format --check`/`mypy` 全绿；`a8_scope.py` 三张哈希表 20+37+8 项复算 0 漂移；`REQUIRED_TEST_CASE_COUNTS` 合计 613，与 `docs/verification/a8-requirements.md:180` 一致
  - Spec 轴：A8 全组 613 passed（332 passed/16.32s + 281 passed/78.52s），`--collect-only` 与 scope 分母逐模块比对 `mismatch={}`；`./scripts/verification-status a0cf232a…` → passed / verified / **applicability=same**、4254/4254、6/6、1162s，控制记录 `code.commit=da9b9ff`、`dirty=false`、terminal exit 0；20 份材料 SHA-256 逐份复算一致
- **未运行**：完整 `./scripts/check-offline`（约 20 分钟，由已存 `a0cf232a…` 证据 + A8 全组重跑替代）；全部 live（真实 Pi/Node/模型/网络/凭据/NAS/常量 cwd/DERIVED 逐项实测）
- **缺失来源**：无。**两轴均声明「本轴完成」**

## Standards

### 工具与来源

可用：`bash`（只读 git/rg/sed/python3/pytest/ruff/mypy）、`read`/`grep`/`find`/`ls`；无 write/edit，未改仓库、未建 commit、未改 Issue。固定点 `main`=`7473c1c`，HEAD=`da9b9ff`，`git diff main...HEAD`＝74 文件 +9286/−84 / 14 提交。实读：`AGENTS.md`、`CLAUDE.md`、`docs/agents/*`（python-conventions/testing/invariants/llm-evidence/documentation/scope/refactor）、`GLOSSARY.md`、`README.md`、`docs/contracts/{pi-rpc,adapter-config,screening-tasks,verification-status}.md`、`docs/verification/{a8-requirements,offline-evidence}.md`、`docs/adr/0026`、`scripts/{a8_scope.py,check-offline,verification_status.py}`、`intent/draft.md` 相关段落。
实跑：`pytest -q tests/test_a8_*.py -p no:randomly` → **613 passed / 95.76s**（`--durations` 复跑 90.27s）；`ruff check src/paper_radar/llm tests scripts` → 全通过；`ruff format --check` → 30 files formatted；`mypy src/paper_radar/llm scripts/a8_scope.py scripts/a8_acceptance.py` → Success。脚本复核：`a8_scope.py` 三张哈希表 20+37+8 项逐一复算 **0 漂移**；`REQUIRED_TEST_CASE_COUNTS` 合计 **613**，与 `a8-requirements.md:180`「功能441+验收172｜613」一致；`CAPABILITIES`=13、`NOT_ASSESSED`=28 与文档一致。
未运行：完整 `./scripts/check-offline`（约 20 分钟）与全部 live（Pi/Node/模型/网络/凭据/NAS）。缺失来源：无。**本轴完成**。

### 发现

**F1｜判断（possible Duplicated Code / Primitive Obsession）——封闭档位词汇在内核有两份副本，`CallDescription` 仍用裸 `str`**
影响：`src/paper_radar/llm/rpc.py:29`（tuple）与 `src/paper_radar/llm/rpc_messages.py:45`（set）各存一份 7 值词汇；`src/paper_radar/llm/models.py:42` 的 `thinking_level: str` 未用 `Literal`，而同 dataclass 的 `stage`:31 / `protocol`:41 / `render_format`:49 都是 `Literal`。第三份在 `config/adapters.py` 的 `ThinkingLevel`，属架构上不可 import（`tests/test_a8_llm_architecture.py::test_protocol_modules_keep_business_dependencies_out` 已锁），不计入。失效形态是 fail-closed 但**原因错标**：只给 `rpc.py` 加新档位时 `set_thinking_level` 通过、最终消息按 `THINKING_STATE` 被拒；反之 `run_call` 在开会话前 `INVALID_DESCRIPTION`。不产生错误成功。
标准：`docs/agents/python-conventions.md`「用明确的领域类型和受控 enum / reason 表达状态与原因」。
测试核查：`tests/test_a8_rpc_protocol.py:90-96,133,269` 只用 `off/low/UNKNOWN`，**未覆盖 7 值全集，也无断言锁定两份副本一致**（`_LEVELS` 私有）。
复现：静态确认（未注入复现）。
建议：在 `llm/models.py` 定义唯一 `THINKING_LEVELS: frozenset[str]` 并把该字段收成 `Literal[...]`。成本：`scripts/a8_scope.py:179/183/191` 三处源码哈希重绑 + 重跑门禁（#91 记录 1162s）；tuple→frozenset 无行为差异。

**F2｜判断（文档准确性，接近硬要求）——受绑定台账点名不存在的公共符号 `llm.call_once`**
影响：`docs/verification/a8-requirements.md:191`「3 隐藏RPC公共服务 | llm.call_once；boundary/value 经 run_once 组合」；全库无 `call_once` 定义（`git log -S call_once` 仅 `0270c97`(#91) 引入该行），实际入口是 `paper_radar.llm.rpc.run_call`（`src/paper_radar/llm/rpc.py:387`），由另一份同样受哈希绑定的 `docs/contracts/pi-rpc.md:72` 记录。两份文档对公共 API 名称不一致。
标准：`docs/agents/documentation.md`「公共契约进 `docs/contracts/` 与 `README.md`」——契约名称须与实现一致；该行是用户故事 3 的唯一落点。
测试核查：`tests/test_a8_integrity.py`（136 项）只校验哈希/分母/漂移，不校验文档符号存在性；无覆盖。
复现：`rg -S call_once` 仅命中该行；未运行文档构建。
建议：改为 `paper_radar.llm.rpc.run_call`。成本：1 行 + `scripts/a8_scope.py:345` 哈希重绑 + 门禁；风险极低。

**F3｜判断（possible Primitive Obsession / 隐式耦合）——prompt 命令 id `"rpc-9"` 硬编码三处**
影响：`src/paper_radar/llm/rpc.py:39,285,294` 硬写 `"rpc-9"`，`:284` 用 `command_no = 9` 表达「8 条初始化命令之后」。初始化序列增删后 id 单调性静默失效，重复 id 会被误判 `RESPONSE_MISMATCH`。已有测试钉住该字面量（`tests/a8_pipe_worker.py:109`、`tests/test_a8_rpc_candidates.py:465`），漂移会显式失败而非静默接受，故仅为可维护性。
标准：无文档化硬规则直接覆盖。
测试核查：`test_a8_rpc_candidates.py`（219 项）覆盖 id/command 关联；无「初始化命令数变化后 id 仍单调」用例。
建议：提 `_PROMPT_COMMAND` 常量。成本：1 源文件 + 哈希重绑 + 门禁，收益低，可随下次触碰该文件处理。

**F4｜判断（possible Duplicated Code，被仓库先例压制，仅记录）**
`scripts/a8_acceptance.py`（570 行）与 `scripts/a7_acceptance.py`（533 行）归一化后约 40 处差异；但 a6→a7 ≈108 行/503 行、a5→a6 ≈162/412，即「每组一份 acceptance」是既有做法，按「仓库标准优先」抑制。合并需改 8 个受绑定脚本并全体重绑，不建议本次处理。

**F5｜测试缺口（非仓库文档化要求，属规格「建议默认」）——无「无 sleep / 单例 ≤5s」守卫，且已有一个 8.16s 用例**
影响：#85 首次补充 §五建议「A8 不含 `time.sleep`，单例约 ≤5s，组总约 ≤60s」。实测 `rg time.sleep` 无命中（前半满足），但 `--durations` 显示 `tests/test_a8_rpc_backup.py::test_rpc_wal_history_restores_independently_and_continues_remaining_attempt`=**8.16s**，组总 **90–96s**；组总超时已在 #91 完成评论披露，单例超限未披露，亦无守卫用例。
标准：无文档化硬规则（`docs/verification/offline-evidence.md:640` 只要求长门禁预留 30 分钟）。
测试核查：`test_a8_integrity.py`、`test_a8_acceptance.py` 均无该守卫。
复现：已运行（见上）；完整门禁未运行。
建议：加一条守卫用例（枚举模块源码无 `sleep(`，≥5s 用例显式豁免），或在台账写明不采纳替代规则。成本：新增 1 例将改变分母/哈希/文档数字并需重跑门禁；是否算本次缺失交 Spec 轴。

### 小计

5 项：**0 文档化硬违例**、功能错误 0、测试缺口 1（F5，非硬要求）、判断/可维护性 4（F1–F4）。最严重 **F1**（封闭档位词汇两份副本且无一致性断言，失效原因错标）；其次 **F2**（受绑定文档点名不存在符号）。已跑 A8 613/613、Ruff/mypy 全绿、`a8_scope` 65 项哈希无漂移；完整 `check-offline` 与 live 未验证。篇幅取舍：超出 800 词上限，已合并低优先级 smell 建议（`RpcFailure.category` 可改映射表、`calls.py` 以 JSON 字符串承载 `policy_json/user_payload_json` 的二次解析）、省略 F4 的逐 hunk 证据，未展开对 `scripts/a2–a7_scope` 哈希重绑逐项核对（仅抽查为纯哈希改动）。

## Spec

### 工具与来源

- 实际可用：`read`/`grep`/`find`/`ls`/`bash`（只读 git、rg、python、pytest、gh 数据已落盘读取）；无 `edit`/`write`，未改任何仓库文件、未改 Issue 状态。
- 规格来源：`/tmp/a8_bodies.txt`（#85–#91 正文，#85 含 40 故事/23 决策/验收面表）、`/tmp/a8_issues.txt`（#85 四条补充与 D1–D4/P3 裁决、#86–#91 补充与完成报告），并按优先级（裁决 > 补充建议 > 正文）核对；`docs/agents/issue-tracker.md` 方法。仓库落地物：`docs/contracts/{pi-rpc,adapter-config,screening-tasks}.md`、`docs/verification/{a8-requirements,offline-evidence}.md`、`tests/fixtures/pi_rpc/1.4.0/{README,request-vectors.json}`、`GLOSSARY.md`、`docs/adr/0026`、`intent/draft.md`、`scripts/a8_*`、`src/paper_radar/llm/*`、`tests/a8_*`、`tests/test_a8_*`；Pi 1.4.0 安装用于核对 DERIVED 依据。
- 实跑：`pytest -q` 前 9 个 A8 模块 → **332 passed（16.32s）**；其余 11 个 A8 模块（含 pipes/backup/integrity/entry/status）→ **281 passed（78.52s）**；合计 **613 passed**，与 `scripts/a8_scope.REQUIRED_TEST_CASE_COUNTS` 逐模块一致（`--collect-only` 比对 mismatch={}）。`./scripts/verification-status a0cf232a…` → 通过/verified/**same**、4254/4254、6/6、耗时 1162s；控制记录 `code.commit=da9b9ff`、`dirty=false`、terminal exit 0 且 9 组含 `.a8.json` v1 必需。20 份材料 SHA-256 逐份复算全部一致。未运行 `./scripts/check-offline`（约 20 分钟），改为复核已存证据 + 重跑 A8 全组。
- 未验证：真实 Pi/Node/模型、生产隔离、参数映射、常量 cwd、DERIVED 逐项实测（均为规格明确留待生产启动器者）。
- **本轴完成**；缺失来源：无。

### 发现

**S1｜(c) 文档落点符号不存在（低影响，硬缺陷）**
- 影响：绑定台账把用户故事 3 的落点写成 `llm.call_once`，仓库无此符号，后续按编号复核会找不到落点。
- 位置：`docs/verification/a8-requirements.md:191`。
- 规格引用：#91 AC8「验收文档、状态 Contract、README、A8 逐项需求与绑定台账收口」；`docs/agents/documentation.md`「公共契约进 docs/contracts 与 README」。
- 已有测试核查：**没有覆盖**。`test_a8_integrity.py` 只校验该文档的字节哈希，不校验其符号是否可解析，故断言证明不了本条语义。
- 复现：`rg -n "call_once" .` → 仅该 1 处命中；实存公共入口为 `paper_radar.llm.rpc.run_call`（`src/paper_radar/llm/rpc.py:387`）与 `__init__.py` 的 `build_call`/`render_request`。
- 最小建议：改为 `llm.rpc.run_call`（并保留「经 run_once 组合」）。成本：该文件在 `scripts/a8_scope.REQUIRED_FIXTURE_FILES` 内（sha `0d0269…`），改后须重绑哈希并重跑完整门禁，否则 A8 组报 `scope_drift`；风险低。可并入下次必然的重绑。

**S2｜(c) Contract 措辞与代码不符（低影响）**
- 影响：`pi-rpc.md` 称「RpcLimits 只允许缩短**前四项**期限」，实际第五项 `poll` 也只允许缩短（放大即 `invalid_description`）；照文档写注入参数会误判。
- 位置：`docs/contracts/pi-rpc.md:122`（固定上限段）vs `src/paper_radar/llm/rpc.py:435-442`。
- 规格引用：#89 AC4「所有时间限额含义、叠加关系及原因优先级写入 Contract」。
- 已有测试核查：覆盖不足——`test_a8_rpc_protocol.py:324` 只断言 `initialization+total+close+terminate<LEASE_SECONDS`，`test_a8_rpc_lifecycle.py` 的期限用例不断言「放大 poll 被拒」。
- 未验证限制：未构造放大 `poll` 的负例，仅静态核对（**未复现**）。
- 最小建议：改为「前四项期限与 poll」，或在 Contract 补一句 poll 同受封顶。成本同上（pi-rpc.md 亦在哈希内）；风险极低。

**S3｜判断项（P3 词汇边界），不建议本轮改**
- `calls.py` 新增封闭 `DescriptionReason`（`INVALID_CONTEXT`/`PROJECTION_MISMATCH`/`CORRUPT_REFERENCE`），再由 `tests/a8_call_support.prepare_call` 一对一映射到既有 `TaskReason`；P3 原话是「复用既有 TaskReason…不为 A8 新增词汇」，而 A7 侧 `errors.py`/`task_reason_catalog` 格式 1 与 `GUIDANCE` 确实未被改动（`test_a8_rpc_recovery.py:257`、`scripts/a8_scope.FORMAT_VERSIONS["task_reason_catalog"]=1` 锁定）。
- 判断：与「内核封闭细分原因 + 接线层换名」的既定模式一致，映射表在 `pi-rpc.md` 公开，未复制规则。仅当所有者要求全局单一词汇时才算偏离；成本为改枚举与映射各一处 + 重跑门禁。

### 已核对但不算缺失（防误报）

- #85 正文决策 13/19/21 的旧措辞仍在父 Issue 正文：规格明令「不得修改父 Issue 正文来覆盖评论」，D2/D3 的替代规则已写入 `pi-rpc.md`（内核不比较最终模型身份、`totalTokens==0` 两字段未知），故不算冲突。
- 内核期望的 1.4.0 形状与随包源码一致（抽查 `rpc-mode.js:295-400,540`、`agent-session.js:1944`、`agent-session-runtime.js:147`）：`success()` 无 data 时省略键（A8 用 `data.get(…,{})` 可接受）、`clear_queue` 返回 `{steering,followUp}` 字符串数组、`get_state.sessionFile` 可为缺键、`get_commands` 为 `{commands:[]}`、`set_model` 返回含 provider/id 的模型对象——未发现「拒绝合法 Pi 输出」的推导错误（仍非运行观测）。
- 重绑时机：A8-01…A8-05 提交未触碰受绑定文件，重绑只在 `0270c97`（#91）——符合「A8-06 才集中重绑」。
- `rpc_verified/live_verified/stage_a_verified=false`、not_assessed 沿用 A7 的 20 项词汇再补 8 项 A8 专属项，未出现同概念第二种拼写。
- 规模目标（单用例 ~5s、A8 组 ~60s）实际约 95s、恢复用例 ~8s，**已在 #85/#91 完成评论与本台账披露**，按裁决属可接受目标而非本次缺失。

### 小计

发现 3 项（1 项低影响文档硬缺陷、1 项文档措辞不一致、1 项词汇判断项），**无功能缺失、无 scope creep**；最严重为 S1（绑定台账落点符号不存在，可核查性受损，不影响运行时行为）。

## 聚合核验记录（不改变两轴分列与排序）

仅记录聚合者在本次会话中**独立复核过**的事实，不合并、不重排两轴的发现；未复核项按轴内自述标注。

- **G1｜确认（Standards F2 与 Spec S1 指向同一事实，但分属两轴不同判据）**：`rg -n "call_once" /home/meteoboy4/Projects/PaperRadar` → 唯一命中 `docs/verification/a8-requirements.md:191`；`rg -n "^def run_call"` → `src/paper_radar/llm/rpc.py:387`；`build_call`/`render_request` 在 `src/paper_radar/llm/calls.py:44,154`。**已核实**。
- **G2｜确认**：`docs/contracts/pi-rpc.md:122` 原文「RpcLimits 只允许缩短前四项期限，不能放大。」；`src/paper_radar/llm/rpc.py:435-442` 的封顶检查包含 `limits.poll > defaults.poll`。**已核实**（静态阅读，未构造放大 `poll` 的运行负例）。
- **G3｜确认**：`src/paper_radar/llm/rpc.py:29` 与 `src/paper_radar/llm/rpc_messages.py:45` 确有同值 7 元档位词汇两份；`src/paper_radar/llm/models.py:42` 为 `thinking_level: str`，同 dataclass 其它字段用 `Literal`。**已核实**。
- **G4｜确认**：`src/paper_radar/llm/rpc.py:39` 为 `command_frame("rpc-9", "prompt", …)`。**已核实**（`"rpc-9"` 其余两处未逐行复核，属 F3 所述，**部分未核实**）。
- **G5｜未核实（依赖轴内自述）**：`scripts/a8_scope.py` 65 项哈希 0 漂移、`CAPABILITIES`=13、`NOT_ASSESSED`=28、`verification-status a0cf232a… → same`、20 份材料 SHA-256 一致、F5 的 8.16s 单例计时——聚合者未复跑，接受两轴实跑记录。
- **G6｜工作树状态**：写入本文件前 `git status --porcelain` 为空；本文件是唯一新增（未跟踪）文件，未修改任何受 A8 scope 绑定的材料，因此不改变已存 `a0cf232a…` 证据的适用性。

## 一行总结

- **Standards**：5 项（0 硬违例 / 0 功能错误 / 1 测试缺口 / 4 判断项），最严重 F1（档位词汇两份副本且无一致性断言）。
- **Spec**：3 项（1 低影响文档硬缺陷 / 1 文档措辞不一致 / 1 词汇判断项），最严重 S1（绑定台账落点符号不存在）；无功能缺失、无 scope creep。
- 完整 `./scripts/check-offline` 与全部 live 行为在本次两轴中**均未运行**；真实 Pi/Node/模型、OS 隔离、参数映射、常量 cwd 与 DERIVED 逐项核实仍按规格留待生产启动器阶段。

## 2026-10-24 逐项核实与处理（追加，原报告保留）

追加前原文字节 SHA-256：`58662e387f6e78ff46afe7779fd1a0602c80ae45b781c339cdde369f2dab4b2a`。
以当前实现、#85–#91原文和全部补充裁决独立核实；Pi按指定1.4.0的docs/docs.json定位
rpc-commands.md及dist/modes/rpc/rpc-mode.js核对，未运行Pi/Node/live。

| 原编号 | 核实与处理 | 落点/验证依据 |
| --- | --- | --- |
| Standards F1 | 接受集中词表和Literal；补充纠正“tuple→frozenset无行为差异”：对list/dict直接查frozenset会抛TypeError，必须先验str类型，Literal不能替代运行时校验。唯一词表从ThinkingLevel的get_args派生，保持config分层。 | llm/models.py、rpc.py、rpc_messages.py；test_each_documented_thinking_level_completes_public_call（独立列七档），malformed_description_level（3）、malformed_thinking_notification（3）及既有最终消息畸形枚举测试。 |
| Standards F2 | 接受，与Spec S1同修。公共符号确实是paper_radar.llm.rpc.run_call，台账原llm.call_once为错误引用。 | docs/verification/a8-requirements.md 用户故事3；不为纯名称文案增加镜像测试。 |
| Standards F3 | 接受局部维护建议。本轮已触及rpc.py，将prompt序号、ID、name收为三个常量，ID由序号派生；wire固定rpc-9，初始化与取消序列不变，不引入动态框架。 | rpc.py；既有test_a8_rpc_protocol.py与test_a8_rpc_candidates.py公开wire关联回归，不断言私有常量。 |
| Standards F4 | 不改。仓库明确采用每组独立acceptance，原报告已抑制此项；本轮不扩大为跨8组的验收器重构。 | scripts/a8_acceptance.py不变；旧组能力/分母/格式不变。 |
| Standards F5 | 部分接受披露，拒绝重复守卫/硬性能门禁。原“无无sleep守卫”事实错误：test_a8_rpc_lifecycle.py::test_a8_tests_use_no_sleep_for_synchronization已以AST检查全部*a8_*.py；原台账第二次补充§五也已披露非空恢复约8s。#89明确5s/60s为目标且禁止紧墙钟误判，故保留注入期限与终局断言、完整恢复链，进一步说明86–96s/7.6–8.2s历史测量。 | a8-requirements.md收口节、pi-rpc.md替代规则；不加重复guard或5s硬失败/豁免框架。 |
| Spec S1 | 接受，与Standards F2同一修正。 | a8-requirements.md 用户故事3。 |
| Spec S2 | 接受文案与公共覆盖。RpcLimits保持默认或缩短前四项期限及poll，任一放大在会话创建前invalid_description；不改现有期限语义。 | pi-rpc.md；test_default_or_shorter_poll_completes_public_call（默认0.05/缩短0.01），test_larger_poll_is_rejected_without_session（0.051，零会话）。 |
| Spec S3 | 核实后不改。P3禁止新增A7 TaskReason/GUIDANCE/catalog，不禁止协议层DescriptionReason；协议层无业务依赖，接线按公开表映射既有TaskReason。跨层共用枚举会违反架构边界。 | llm/models.py、calls.py、tests/a8_call_support.py；test_a8_call_rejections.py精确TaskReason、test_a8_llm_architecture.py依赖守卫及test_a8_rpc_recovery.py词汇锁定。 |

### 原聚合记录与规格优先级的补充更正

- G1/G2/G3/G4均已核实并按上表处理，三处rpc-9与命令序号9均已局部收敛；G5中的
  历史实跑属于原审查者记录。本轮会另产当前树验证，不将既有passed外推为same。
- **更正G6**：“只新增untracked报告、未改受绑定材料就不改变适用性”不成立。
  scripts/verification_identity.py::_worktree_sha256 明确使用git ls-files --cached
  --others --exclude-standard，非忽略未跟踪报告也进入整体身份。主agent本轮在仅有
  三份untracked报告时只读查询旧a0cf232a…：passed/verified保持历史事实，
  applicability已为different。原G6保留为历史原文，以本段纠正；报告提交后仍需稳定树完整验证。
- 原“D1–D4 > 父票补充 > 父票正文 > 子票正文 > 子票补充”的全局排序过于笼统。
  docs/agents/issue-tracker.md规定评论优先于正文；本组子票也明确冲突以较晚评论与
  明确裁决为准。结合适用范围阅读，#86收窄autoCompaction可证明范围、#89明确
  墙钟目标替代规则、#91允许集中重绑均须采用，不能一概把子票补充降至正文之后。

新增测试人工分母7+3+3+2+1=16，protocol由53到69，A8由613到629；原实现已通过
新增刻画用例，没有为了纯重构制造红测。protocol69项、A8相关Ruff/format、严格mypy
（39文件）已通过。完整A8子集、scope --collect与最终完整门禁以本节后续验证记录/
稳定提交证据收口，不回写绑定台账最终run_id。真实Pi/模型、OS隔离、参数映射、
生产cwd与DERIVED live核实仍未验收，三个verified生产标记继续false。

收口验证：全部A8子集 **629 passed/86.29s**（最慢非空恢复7.53s）；A8相关Ruff/
format与mypy39文件通过。scope --collect exit0、affected_groups=[]、issues=[]，
233模块collection与人工分母一致；git diff --check通过。三份报告与原始备份逐一比较，
仅追加、原文字节前缀保留。完整check-offline由提交后稳定树最终运行，当前不宣称完整门禁已通过。
