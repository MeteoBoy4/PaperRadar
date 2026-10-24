# 阶段 A8 双轴审查 r1（#85 / #86–#91）

- 固定点：`main` = `7473c1c8cd986827e55d9e8d12fa8cc18bf7ba89`
- 被审：HEAD = `da9b9ff`，工作树干净、无未提交修改（审查开始前与两子 agent 结束后均由聚合者以 `git status --porcelain` 核实）
- diff：`git diff main...HEAD`（三点，对 merge-base）＝ 74 files, +9286/−84
- 提交映射（`git log main..HEAD --oneline`，新→旧，共 14 个）：`da9b9ff` Merge #85（review fixes 收口）、`465b3af` fix(llm): finish interrupted RPC cleanup and validate cancel queue ACKs（#85 审查修复，无独立子票）、`b1014e3`/`0270c97` → #91、`0a7137f`/`c03a89f` → #90、`297e092`/`8196f93` → #89、`c809fdc`/`8f50be1` → #88、`387e4c4`/`fdd1fe9` → #87、`ca845b8`/`7a8dcbc` → #86
- 两轴分别由独立只读子 agent 执行（互不共享上下文）；本文按轴分列，未跨轴合并或重排。两轴提示均已附加 `~/Prompts/code-review-enhancement.md` 全文（800 词上限、七字段证据格式、只读与脱敏）。

## 工具与来源（两轴共同）

**子 agent 实际可用**：两轴均为 delegate（read/grep/find/ls/**bash**/contact_supervisor；工具集中另有 edit/write 但任务明令禁用，两轴自述未使用）——本轮子 agent 均被授予 bash，实际运行了只读 git、只读 `gh issue view` 与 `uv run --offline --locked` 下的 pytest/ruff/mypy，并在各自报告内注明命令与结果。

**两轴独立实跑（互相印证）**：全部 20 个 `tests/test_a8_*.py` 两轴各自分批跑完，均为 **613/613 passed**；Standards 轴另跑 `uv run --offline --locked ruff check src/paper_radar/llm/ scripts/a8_*.py tests/a8_*.py tests/test_a8_*.py` 与 `mypy src/paper_radar/llm/`，均通过；Spec 轴另跑 `./scripts/verification-status a0cf232a…`（只读）→ passed/verified/same（4254/4254）。

**Pi 事实核对**：两轴各自按本机 Pi 1.4.0 安装包（`/home/meteoboy4/.pi/agent/install/releases/1.4.0/node_modules/@earendil-works/pi-coding-agent/`，以 `docs/docs.json` 为导航）核对了冻结的 RPC 描述与请求向量：thinking 七档（rpc-commands.md:282 / pi-ai models.js）、clear_queue 响应 `{steering,followUp}`（rpc-commands.md:107-127）、prompt disposition 三值、new_session cancelled、get_state、set_auto_retry/compaction、get_commands、agent_settled、Usage 必需 `cost`（message-types.md:67-90）、message_update 携带 usage、stopReason 全集、`set_model` provider/modelId 且返回完整 Model 对象、cwd 段 `<cwd>\n…\n</cwd>` 包装（system-prompt.js:110-118）、LF 帧+CRLF 容忍——两轴结论一致：内核实现与 1.4.0 文档/源码一致；fixtures README 三个 SHA-256 抽查与本地安装实算一致（Standards 轴）。

**标准来源（Standards 轴）**：仓库无 `CODING_STANDARDS.md`/`CONTRIBUTING.md`（已核实不存在）；取 `AGENTS.md`、`docs/agents/{python-conventions,testing,invariants,calibration,llm-evidence,cli-output,documentation,scope,refactor}.md`、`GLOSSARY.md`、`docs/adr/0026`、`docs/contracts/*`（含新增 `pi-rpc.md`）+ Fowler smell 基线 12 条。Ruff（lint+format）与 mypy 由 `./scripts/check-offline` 强制，凡工具已强制的跳过不报。

**Spec 来源（Spec 轴）**：#85 正文 + 4 条评论（补充×2、D1–D4 裁决、P3 采纳）及 #86–#91 正文 + 各评论全部读取；关系完整性核验通过（#85 subIssues totalCount=6=len(nodes)；#87–#91 blockedBy 链 86→…→91 线性，无 unknown）。佐证规格：`intent/draft.md`（文首导航）、`docs/verification/a8-requirements.md`（对照 issue 原文审查，其本身亦为被审物）。

**不可用或未使用**：全量 `./scripts/check-offline` 未复跑（两轴均如实披露）；台账中「工作树外审计报告」（issue-91-before-audit.json 等）不可读（Spec 轴 F3，未验证）；未运行任何 live（真实模型调用/真实 Pi RPC 进程/网络 feed）。

**聚合者补充核验（本会话）**：S1 事实 claim 已 grep 复核（`src/paper_radar/llm/rpc.py:29` tuple 与 `src/paper_radar/llm/rpc_messages.py:45` set，七值相同；校验引用 rpc.py:212,238,409 与 rpc_messages.py:208）。

## Standards

（成文标准优先；smell 基线仅作判断线索。子 agent 自述完成状态：审阅完成——阅读范围与实跑命令见上文共同节。）

**无成文标准违例**。逐项核对：确定性/I-O 分离（协议内核 `rpc*.py` 零配置依赖，仅 `calls.py` 组合层引用 config/stage_inputs，无环、无上行依赖，refactor.md ✓）；受控 enum/reason（`RpcReason`/`DescriptionReason` StrEnum，python-conventions ✓）；负例断言受控原因而非异常类型（testing.md ✓，已抽读证实）；测试全离线合成（无真实 Pi/网络）；llm-evidence 隐私（llm/ 无 logging，prompt/model 字段 `repr=False`）；cli-output 中文（`a8_acceptance.py` `_HELP` 全中文）；documentation.md 同步（GLOSSARY/ADR-0026/契约/README/draft 齐备）；无新依赖、无新 migration（`a704_screening_retry` 为既有 head，invariants ✓）；calibration 未触碰（test-only 接线，`rpc_verified=false`）；V2 范围未越界（无 fallback/UI）。工具强制项（Ruff/mypy/format）已实跑通过，按规则不报。a*_scope.py 散点哈希更新与 a8_acceptance 复刻 a7 形状均为仓库明示许可的冻结分派模式，不报 Shotgun Surgery/Duplicated Code。

### S1 thinking levels 词表双处硬编码（判断题·Duplicated Code，低）— P2
- **类别/影响**：`src/paper_radar/llm/rpc.py:29`（tuple `_LEVELS`）与 `src/paper_radar/llm/rpc_messages.py:45`（set `_LEVELS`）值同（与 Pi 文档 rpc-commands.md:282 核对一致）。两处各自参与档位校验/通知校验（rpc.py:212,238；rpc_messages.py:208），未来登记新档位须同步改两处+契约。
- **标准引用**：Fowler 基线 Duplicated Code（判断线索；无成文标准直接禁止）。
- **已有测试核查**：`test_a8_rpc_protocol.py` 覆盖非法档位两条路径（`RpcFailure(reason)` 精确断言），但均基于当前常量，防漂移无测试——属「覆盖不足」（防漂移缺一类实现方式）。
- **复现/限制**：纯静态，无需运行；行号已由聚合者 grep 复核一致。
- **最小建议**：在 `models.py`（与 `PROTOCOL_PROFILES` 同居）定义一次并两处导入；因模块哈希冻结（`scripts/a8_scope.py` REQUIRED_SOURCE_MODULES），需同票重登记哈希，机械成本约 20 分钟，风险低（7 批测试全绿可即时回归）。

### S2 中断补偿循环形状 4 处相似（判断题·Duplicated Code 形状，低）— P2
- **类别/影响**：「中断补偿、每步至多补做一次、共用首次绝对期限」循环形状出现 4 处：`rpc.py` `_cleanup`、`run_call` finally、`rpc_pipes.py` `terminate`、`_wait_group` finally。各变体失败策略刻意不同（如 `_wait_group` 原异常为中断时不重抛中断、`terminate` 以 `incomplete` 标记完成状态），且为契约成文要求（pi-rpc.md「每轮清理中被中断的步骤至多补做一次…全部补偿共用首次 terminate 绝对期限」）。
- **标准引用**：Fowler 基线 Duplicated Code（判断线索；契约明确要求各变体语义）。
- **已有测试核查**：`test_a8_rpc_lifecycle.py`（67 例，全绿）逐场景覆盖四种补偿语义，断言精确原因。
- **复现/限制**：纯静态。
- **最小建议**：暂不抽取（统一 helper 需 3–4 个策略参数，反而增加耦合）；仅在下次触及该文件时顺带收敛。修改成本中、风险中（清理语义是安全关键路径），列为可选可维护性建议，非违例。

**未核实/未展开（Standards 轴披露）**：#85 正文/评论全文（仅元数据；裁决符合性属 Spec 轴）；`a8_acceptance.py` 尾段（约 300/570 行处）未逐行读（余下为同形核对循环）；全量 `./scripts/check-offline` 未复跑。

## Spec

（Spec 来源、Pi 事实核对与实跑命令见上文共同节；子 agent 自述完成状态：审查完成，在已核实范围内。）

**核对结论（按 issue，均符合）**：
- **#86**：D1–D4/P3 文档同步齐（GLOSSARY 三术语+Avoid、ADR-0026 日期补充、draft 文首/§2.4/§7.7、adapter-config/screening-tasks）；双 snapshot（calls.py:69-77 投影相等；a8_call_support.prepare_call 语义取 `load_input`、审计取回执 snapshot）；P3 映射 INVALID_CONTEXT/CONTEXT_CONFLICT/CORRUPT_REFERENCE 断言 TaskReason（test_a8_call_rejections.py:70-75）；12 向量含斜杠/U+2028/伪造 RPC 行（paper-2 恶意摘要）+跨进程 hashseed 复核；20 哈希+DERIVED-01…11 三态登记。
- **#87**：串行初始化 9 命令、EARLY_RECORD、started 判据、事件状态机、system 补丁形状、D2 分层（rpc_messages.py:217-248 返回观察值，接线填 reported_*，A7 判 model_mismatch）、常量关系 <600s（test_a8_rpc_protocol.py:322-330）均在。
- **#88**：事件封闭表/穷举负例、副本严格类型比较（`_same_json`）、D3 totalTokens==0→null、近界 DERIVED-11 正例齐。
- **#89**：PipeSession pgid 核验、并发双读/部分写、/proc+pidfd 整组回收、clear_queue→abort 且校验 steering/followUp（rpc.py `_cancel`）、KeyboardInterrupt 原样上抛+finally 补偿清理（rpc.py:428-466）。
- **#90**：穷举 RpcReason→四类映射、异常→executor_error/origin=exception、包装/子类→protocol_error（test_a8_rpc_recovery.py:212-256）、A→B→A 审计回摆、非空 WAL 隔离恢复+唯一继续用例。
- **#91**：a8_scope 不自绑定、同次六前置（a1/a2/a2-full/a3/a5/a6/a7）绑定、状态工具识别 .a8.json、40 用户故事逐项落点表、rpc/live/stage_a 恒 false；review-fix `465b3af`（中断清理闭环+clear_queue ACK 校验）已合入 `da9b9ff` 且台账记录复核关闭。
- **A7 源码/支撑/分母零改动**（仅两个 entry/status 测试换 import 与份数 11→12，属 #91 AC7 批准的集中重绑波，a7_scope 相应哈希按 DAG 更新）。

### F1 A8 专项约 86s，超 #89「约 60s」规模控制目标（信息级，无行动）
- **类别/影响**：测试规模超目标约 43%；#91 评论与台账均已披露并保留理由（完整恢复覆盖）；spec 措辞为目标非门禁，不算缺失。
- **需求引用**：#89 规模控制目标措辞。
- **已有测试核查/复现**：不适用（非缺陷）；两轴实跑 613/613 通过。
- **最小建议**：无行动；后续阶段若测试时长继续增长再议。

### F2 三个既有测试文件被修改（信息级，合规确认）
- **类别/影响**：`tests/test_a7_entry.py`、`test_a7_status.py`、`test_verification_status.py` 被修改，与 #85 二补 §一.6「不改 A7 固定测试」存在字面张力；但未追加用例、分母不变，属 #91 AC7「按审计闭包集中重绑」的批准操作，台账有 DAG 记录。判定为已裁决范围内的合规行为。
- **需求引用**：#85 二补 §一.6 vs #91 AC7（后者 narrower 且更晚，按评论优先规则适用）。
- **最小建议**：无行动。

### F3 台账外部审计材料不可独立复核（未验证披露，不构成缺陷疑点）
- **类别/影响**：台账所述 #86 只读审计输出、#91 工作树外审计报告（issue-91-before-audit.json 等）位于工作树外不可读取，未能独立复核。
- **限制**：未验证；不构成缺陷疑点。
- **最小建议**：如需闭环可在后续阶段把这些材料的哈希登记进可核查位置。

**缺失/scope creep/实现缺陷类发现：无**（在已核实范围内）。

## 汇总（按轴，不跨轴排序）

- **Standards**：2 条发现（S1、S2，均为 smell 判断题·低危·P2）；无成文标准硬违例；轴内最重 = **S1**（thinking levels 词表双处硬编码，未来加档位需双处+契约+冻结哈希三处同步）。
- **Spec**：3 条发现（F1 信息级、F2 合规确认、F3 未验证披露）；缺失/scope creep/实现缺陷类发现为零；轴内最重 = **F1**（约 86s 超 #89 约 60s 目标，已披露且为目标非门禁）。

## 2026-10-24 逐项核实与处理（追加，原报告保留）

本节核实当前实现与 #85–#91 原始规格/全部补充裁决，不追溯改写上文审查者的历史记录。
追加前原文字节 SHA-256：`1a6925da38f83164166a65b6af30e1c3e3c260d8895fb9ecc4ca2e34cde8aef3`。
Pi 依据仍是指定 1.4.0 安装；按 docs/docs.json 定位并重读 rpc-commands.md 的七档和
clear_queue 形状，对照 dist/modes/rpc/rpc-mode.js；仅静态读取，无 Pi/Node/live 执行。

| 原编号 | 核实与处理 | 落点/验证依据 |
| --- | --- | --- |
| Standards S1 | 接受。两份词表确实相同但重复；在 models.py 集中 ThinkingLevel Literal，get_args 派生 THINKING_LEVELS，rpc/rpc_messages 共用。不会上行依赖 config。改用 frozenset 前增加描述/通知的 str 类型检查，避免 list/dict 异常被误分为 transport_error。 | llm/models.py、rpc.py、rpc_messages.py；test_a8_rpc_protocol.py 新增七档全程成功、3种非法描述和3种畸形通知，期望七档独立取自 Pi 文档；既有最终消息类型负例继续覆盖。 |
| Standards S2 | 不抽取。原建议本就允许暂不处理；四处补偿的异常优先级、完成标记及原中断保留不同，统一需引入策略参数，会掩盖安全语义。 | rpc.py/rpc_pipes.py 保留；test_a8_rpc_lifecycle.py、test_a8_rpc_pipes.py 现有公共行为回归。 |
| Spec F1 | 接受信息结论，无需性能硬门禁。#89 后续明确约5s/60s是目标，不能在慢机器上用紧墙钟阈值判失败。完善台账，披露审查测得完整组86–96s、非空恢复7.6–8.2s及保留完整恢复链理由。 | a8-requirements.md 新增收口节；pi-rpc.md 记录替代规则；既有 test_a8_tests_use_no_sleep_for_synchronization 已覆盖全部*a8_*.py。 |
| Spec F2 | 核实后不改。#91 的集中注册兼容与按审计闭包重绑允许这些入口/状态测试调整，未增加A7用例或改变分母；不能把早期限制从后续裁决中割裂。 | 对照 #85 第二次补充、#91 AC7及现行 a7_scope；本轮旧组能力/分母/head/契约不变。 |
| Spec F3 | 接受其“未验证披露”，本轮已补核查，不认定为产品缺陷。外部材料现在可读；#86审计及#91初始审计均exit0、无漂移，最终绑定记录113项/8个scope。保留在工作树外，不据此扩大冻结材料清单。 | /tmp/paperradar-85/issue-86-scope-audit.json 与 issue-91-before-audit.json 同 SHA-256 `f8f6177535f54619175dff1f909397e251980b688aba329bbff028567e5b9c32`；issue-91-bindings-final.json SHA-256 `e397af94eb9e958b186c2f4a11d40f095f1e569a9856f725cb933f56b7f4648b`。 |

新增16项按测试定义独立推导：七档7+描述3+通知3+合法poll2+放大poll1，protocol从53到69，
A8总数从613到629（功能457+验收172）。新测试先在旧实现通过，属安全行为补充刻画，
本轮没有虚构红→绿缺陷。协议子集69项、A8相关Ruff/format与严格mypy（39文件）通过。
完整A8子集、scope --collect及最终完整门禁的结果由本节后续验证记录/稳定提交证据收口；
不沿用旧完整运行宣称当前树 same，不在绑定台账回写最终run_id。真实Pi/模型/隔离与live仍未验证。

收口验证：全部A8子集 **629 passed/86.29s**，最慢非空恢复7.53s；上述静态检查通过。
`./scripts/audit-verification-scope --collect --json` exit0、affected_groups=[]、issues=[]，
233模块collection与人工固定分母一致；git diff --check通过。113条历史绑定记录的new_sha256
已逐条对照#91实现提交0270c97实际文件，0差异。三份原始报告均与备份比较原文字节前缀一致。
完整check-offline留给提交后稳定树最终门禁，不将本轮子集或旧历史结果标为当前完整通过。

另更正原Spec核对结论中“同次六前置（a1/a2/a2-full/a3/a5/a6/a7）”的括号：
它列了七项，实际A8直接前置是A1、完整A2、A3、A5、A6、A7六组，不含A2-01；
A2-01仍在总门禁登记中。原文保留，未改变实际依赖或验收能力。
