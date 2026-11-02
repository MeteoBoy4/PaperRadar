# Issue #140 Pi 执行交付 — 双轴代码审查（r2）

- 固定点：`main` = `e0f8e39d1aff8b57eadfe60de44b8570423c1d40`
- 审查对象：`git diff main...HEAD`（三点），HEAD = `db30cf5b056fd2a253ce3680ac3f67d3da49b16b`
- 规模：82 文件，+6429 / −155
- 提交（16）：`db30cf5` `d3db207` `528a03f` `11ef61a` `3aa694c` `6258acd` `b112bb5` `8457209` `182e709` `6df488f` `8c04c94` `9967e87` `d873ab8` `211adb2` `0360224` `b271186`
- 规格来源：GitHub #140（正文＋全部评论，评论优先于正文）与子票 #141/#142/#143/#144；`intent/draft.md` §7.6/§7.7；`docs/roadmap.md`；`docs/contracts/*`；ADR-0039/0040
- 标准来源：`AGENTS.md`、`CLAUDE.md`、`docs/agents/*.md`、`GLOSSARY.md`、`docs/contracts/*`、`docs/adr/0039|0040`；外加 Fowler smell 基线（仓库标准优先覆盖）
- 执行方式：两个独立 fresh 子 agent 并行、互不可见；均带 `bash` 只读权限（`git diff/log`、`rg`、`gh issue view`、`uv run --offline --locked pytest <子集>`）
- 未运行：完整门禁 `./scripts/check-offline`、`check-compatibility`、任何 live / 真实 Pi / auth / 模型 / 网络
- 本次审查不修改代码、不创建 commit；`docs/verification/*` 内容只作为实现者声称，不作为所有者裁决

---

## Standards

来源：只读 `git diff main...HEAD`（82 文件）、`docs/agents/*.md`、`docs/contracts/{pi-execution,doctor,runtime-config,config-projections}.md`、GLOSSARY、ADR-0039/0040、`docs/verification/issue-14x*`；工具 `bash`/`grep`/`read` + `uv run --offline --locked pytest` 子集。未评 spec 符合度。

### S-1 P2 doctor 新增状态 token 未在 Contract 登记
- 类别: 文档化硬要求
- 影响: `admission` 行的 `screening_configuration_missing`、`admitted` 是公共 CLI 受控输出，却只存在于代码与测试；前者不在 `ExecutionReason` Literal 中，排障/断言无权威定义。
- 位置: `src/paper_radar/doctor/pi_exec.py:153,163,175`
- 标准/裁决引用: `docs/contracts/doctor.md:70` 只写「缺 Screening 配置或准入证据为 missing…」，同表 68–76 行对 cwd/credentials/isolation 逐 token 列明；`docs/agents/documentation.md`「公共 CLI 或配置 Contract」「受控 vocabulary」须同变更同步。
- 已有测试核查: `tests/test_doctor_pi_exec.py:283` 已把 `screening_configuration_missing` 写成期望值（测试固化未登记词汇）；`admitted` 无任何断言。
- 复现/未验证: 已运行 `grep -rn screening_configuration_missing`，仅 `pi_exec.py` 与 test 命中。
- 最小建议: 在 doctor.md:70 补两个 token，或改用已登记原因。

### S-2 P2 `timeout_invalid` 拒绝无任何用例
- 类别: 测试缺口（未覆盖）
- 影响: 文档化的领取前有限正超时拒绝有两处实现，均无回归保护。
- 位置: `src/paper_radar/pi_execution/launcher.py:217-221`；`src/paper_radar/pi_execution/service.py:125-148`
- 标准/裁决引用: `docs/contracts/pi-execution.md:194`「…超时和指令非法在领取前拒绝」、`:42`「有限正超时」。
- 已有测试核查: 未覆盖——`grep -rn timeout_invalid src tests` 仅 src 命中；tests 内 `limits=` 全为 A8 合法 FAST 值；`tests/test_pi_execution_launch.py:311-321` 参数化只有 provider/pi_version/system_prompt/snapshot。
- 复现/未验证: 已运行 `pytest tests/test_pi_execution_resources.py tests/test_pi_execution_admission.py tests/test_pi_execution_history_imports.py tests/test_models_v2.py tests/test_doctor_pi_exec.py -q` → 84 passed；无该用例。
- 最小建议: 两例（`attempt_timeout=0`/NaN；`RpcLimits(total=0)`）断言 `match="timeout_invalid"` 且 `used_attempts==0`、无 `auth-observed.json`。

### S-3 P3 doctor admission 的 PASSED 分支不可达，且同一概念两个调用点
- 类别: smell 判断线索（Speculative Generality）
- 影响: `read_evidence` 恒返回 None（`admission.py:62-64`），doctor 直接调用它（`pi_exec.py:151`），service 走可注入的 `_evidence_for`（`service.py:64`）；因此 `reason is None → Result.PASSED`/`"admitted"` 永不执行，doctor 也无法复用注入缝，该状态既不可达也无覆盖。
- 位置: `src/paper_radar/doctor/pi_exec.py:157-176` vs `src/paper_radar/pi_execution/service.py:64`
- 标准/裁决引用: `docs/contracts/pi-execution.md:165`「合成正例仅由测试私有 `_evidence_for` 注入」；doctor.md:55「始终不可执行」。
- 已有测试核查: 全仓无 `admitted` 断言；`tests/test_doctor_pi_exec.py:67,236,275` 只断言 missing/invalid。
- 复现/未验证: 已运行 `grep -rn '"admitted"' tests/` 为空；静态推断不可达（未运行覆盖探针）。
- 最小建议: doctor 改走注入缝并补一例注入 PASSED，或删除该分支并在 Contract 写死恒非 passed。

### S-4 P3 `LaunchIdentity` 双处构造，闭集用裸字符串
- 类别: smell 判断线索（Duplicated Code / Data Clumps / Primitive Obsession）
- 影响: 13 字段在两处重复拼装（`launcher.py:101-113`、`service.py:171-183`），含 `"openai"`/`"owner_provisioned_dir"`/`False`/`None` 字面量；同一闭集在 `pi_rpc_audit.py:34-36` 是 `Literal`。绑定比较（`service.py:199`）不含 `proxy_used/proxy_port/credential_*`，重复构造的不一致不会被判据发现。
- 位置: `src/paper_radar/pi_execution/service.py:171-183`；`src/paper_radar/pi_execution/launcher.py:101-113`
- 标准/裁决引用: `docs/agents/python-conventions.md:8`「用明确的领域类型和受控 enum / reason 表达状态与原因」。
- 已有测试核查: `tests/test_pi_execution_service.py:24-52` 只断言 `executor_kind` 与 audit token；`:130-161` 覆盖 evidence_mismatch，不涉 proxy/credential 字段。
- 复现/未验证: 未运行定向用例；静态比对两处构造。
- 最小建议: 由 `LaunchIdentity` 提供工厂（预绑定/预备启动共用），闭集用 Literal 类型。

### S-5 P3 screening 模型槽存在三种读取路径
- 类别: smell 判断线索（Message Chain / Duplicated Code）
- 影响: `doctor/pi_exec.py:44-46` 走投影载荷深链，`success_rules.py:80-85` 与 `success_references.py:48-51` 各自复制 raw material 扫描；投影内部形状变化会让 doctor 抛未受控 `KeyError` 而非受控检查项。
- 位置: 上述三处
- 标准/裁决引用: `docs/agents/invariants.md`「Pydantic 定义是唯一的 Schema 来源」；`documentation.md` 单一归属。
- 已有测试核查: 覆盖不足——`tests/test_doctor_pi_exec.py:283` 只覆盖 model 缺失，未覆盖投影形状变化。
- 复现/未验证: 未复现（缺投影模型分量需构造畸形快照）。
- 最小建议: config 层提供 `screening_model(snapshot)`，三处调用。

### S-6 P4 新增裸 `raise TypeError`（无消息、无受控原因）
- 类别: smell 判断线索（与 python-conventions:8 张力）
- 位置: `src/paper_radar/config/material_assembly.py:175`（同时重复既存 `:165` 助手形状）
- 已有测试核查: 未覆盖（tests 内无该属性异常断言）。
- 复现/未验证: 未复现（内部不变量分支）。
- 最小建议: 复用 `_config` 泛型助手或抛 `ConfigError`。

### S-7 P4 `+1` 未命名的共享材料分母
- 类别: 测试缺口（断言可读性/固定分母不透明）
- 位置: `tests/test_scope_shared_dag.py:222`
- 标准/裁决引用: `docs/agents/testing.md:19`（独立模块与人工维护计数）。
- 已有测试核查: 该行即测试；`:223-225` 的成员集合断言仍锁定身份，故非分母削减。
- 复现/未验证: 已运行 `pytest tests/test_scope_shared_dag.py tests/test_pi_execution_review.py -q` → 34 passed。
- 最小建议: 显式授权集合（参照 `tests/test_scope_material_inventory.py:82-84`）。

未覆盖范围：未运行完整门禁；未跑 `test_pi_execution_launch/service` 全模块（仅 collect-only 核对 13 模块计数与台账一致：15/18/3/23/21/20/15/32/1/31/3/10/3，合计 195 与 `issue-140-pi-delivery.md:26` 一致）；ADR/intent 语义、真实 Pi/Landlock 现场未验。

完成状态: 完整

---

## Spec

**审计对象**：`git diff main...HEAD`（`e0f8e39`→`db30cf5`，82 文件）。**来源**：`/tmp/pr-review-r2/issue-140…144.txt`（正文＋全部评论，评论优先）、`git diff/log`、源码直读、Pi 1.4.0 随包源码（`dist/cli/auth-command.js`、`dist/cli/credential-print.js`）。**实际运行的只读命令**：`pytest tests/test_models_v2.py tests/test_pi_execution_admission.py tests/test_pi_execution_resources.py`（50 passed）、`pytest tests/test_pi_rpc_source.py tests/test_pi_rpc_source_backup.py`（44 passed）。未运行 `./scripts/check-offline`、`check-compatibility`、任何 live。

### 逐条核对（无发现的部分摘要）

- **A1/A2**：`executor_kind` 闭集 `test|pi_rpc`（`success_models.py:18,35`）；Feed 生产改为「只接受 `pi_rpc`」（`feed_pipeline/service.py:241,286`）；审计唯一 Schema `pi_rpc_audit.py:19-58`（provider/model `min_length=1`、`provider_request_id: None`、无路径/PID/env/凭据派生字段）；交叉核对 `success_references.py:24-66` + `execution_history.py:11-35`，旧 test 审计字节 `{"executor_kind":"test"}` 不变（`success_rules.py:31-36`）。测试：`test_pi_rpc_authority_rejects_bad_candidates_without_success_raw`（`tests/test_pi_rpc_source.py:107`）、`test_real_peer_audit_corruption_is_rejected_by_query_and_backup`（`tests/test_pi_execution_integration.py:90`）。
- **A3/A9**：公共服务在 `pi_execution/`（llm 外），内核只加默认 `None` 的 `expected_cwd_section`（`llm/rpc.py:409,473`）；`a8_call_support.py`/`a8_rpc_task_support.py` 未改；无执行 CLI（`cli.py` 仅 help 文案）。
- **A4/A5/A6/A7/A8**：`use_install(database, description.audit_snapshot_id)`＋`pass_fds`，保护跨 `run_once` 与整组回收（`launcher.py:233-251`）；`system_prompt` 绝对路径/`.`/`..`、`len+1>131072` 领取前拒绝（`resources.py:74-88`）；cwd 用模块常量＋lstat/无链接/为空（`resources.py:50-60`，测试 monkeypatch 于 `tests/test_pi_execution_resources.py:13`）；env 精确相等由对端 `dict(os.environ) == expected` 断言（`tests/pi_execution_support.py:103`，用例 `test_controlled_launch_owns_fresh_resources_and_install_protection` `tests/test_pi_execution_launch.py:13`）；agent 目录仅 `settings.json`、0700、规范字节（`resources.py:16-21,152-166`）。
- **A10/A11/N1**：`read_evidence` 恒 `None`（`admission.py:75-78`）；唯一领取前宿主副作用为凭据刷新，且在证据门禁之后（`service.py:140-160`）；`min-expiry = ceil(total+terminate+close)+600s`，我核对 Pi 1.4.0 `--min-expiry` 解析支持 `s` 单位（`dist/cli/auth-command.js:47-56`）。
- **B1/B2/B3/B4/B5/B6/B7/B8/B9**：Landlock ABI≥4、`no_new_privs`、仅 443+代理端口（`isolation.py:62-137`，`tests/test_pi_execution_isolation.py:14,77,141`）；凭据目录元数据＋四根外（`resources.py:91-116`）；token 形状 `sk-` 拒绝、stderr 不进日志（`auth.py:78-92`）；代理只进 settings 且拒 userinfo（`resources.py:117-137`）；`models-v2` 分层判定（`config/schema.py:93-158`，`tests/test_models_v2.py` 全 20 例，`test_explicit_v2_compiles_both_parameters` 证明 explicit 不在编译期判非法）；证据仅内存、无 migration；doctor `pi-exec` 四态＋任一必要项非 passed 即 exit 2（`doctor/pi_exec.py:311-323`）。
- **C2/C3/C4、D、N2–N7**：五类启动器特有失败均有对应用例；`check-compatibility cli` 59 passed 已记入台账（`docs/verification/issue-141-pi-launch.md:34`、`issue-143-pi-execution.md:40`、`issue-142-pi-rpc-source.md:34`）；`doctor_pi_supply_golden.json` 未变；Contract 原地改写清单、`pi-execution.md`、GLOSSARY/README、ADR-0039/0040、D1 台账齐备；`stage-a-closure.md` 未动。路线图落地为「已完成」而非 D 中的「已规格化」，与 `docs/agents/roadmap.md`「implement-spec 收尾标完成并在已完成板块补行」一致，不计偏差。

### P-1 P3 公开闭集声明了永不产生的 `launch_reused`

- **类别**: 实现方式错误（文档/公开闭集与行为不一致，非需求缺失）
- **影响**: `ExecutionReason` 是 `pi_execution` 包级公开闭集，但 `launch_reused` 无任何产生路径；重复调用 `PreparedLaunch` 实际抛 `RpcProblem(STARTUP_ERROR)`，领取后会计为 `executor_error` 并消耗预算。按闭集枚举该原因的使用者永远等不到。
- **位置**: `src/paper_radar/pi_execution/errors.py:28`；`src/paper_radar/pi_execution/launcher.py:109-112`
- **需求/裁决引用**: #140 A9「运行日志的事件类型是闭集，本票不新增」、A11「领取后…按既有规则结算」；契约 `docs/contracts/pi-execution.md:33`「`prepared(description)` 只允许与准备时完全相同的描述、只启动一次」未规定可观察结果。
- **已有测试核查**: 未覆盖。`rg launch_reused src tests docs` 仅命中 `errors.py:28`；`tests/test_pi_execution_launch.py` 无重复调用用例。
- **复现/未验证**: 未复现（静态推断）。`rg` 结果如上，无运行时反例。
- **最小建议**: 删除该闭集成员，或重复调用抛 `ExecutionError("launch_reused")` 并在契约「错误与拒绝」中登记；两者选一即可闭环。

### 未验证范围与缺失来源

未运行完整门禁、`check-compatibility`、真实 Pi/Node/auth、`/srv/pi-cwd` 现场、TLS/DNS 与主机级出站（按裁决交 Cwd/Live，不算缺失）。测试对端在白名单中追加 Python lib 目录（`tests/pi_execution_support.py:151-156`），故「白名单足以完成 TLS/DNS」只能由 Live 证明。未独立重抓 GitHub issue JSON（用离线抓取文件），不视为缺失来源。

完成状态: 完整

---

## 父级只读核对（不改变两轴排序）

对上述最高影响的两条做最小复核，结论与子 agent 一致，均为「已核实」：

- `rg -n "screening_configuration_missing|\"admitted\"" src tests docs` → 仅 `doctor/pi_exec.py:153,163,175` 与 `tests/test_doctor_pi_exec.py:283`；`src/paper_radar/pi_execution/errors.py:6-31` 的 `ExecutionReason` 不含 `screening_configuration_missing`（S-1 成立）。`admission.py:64` 的 `read_evidence` 直接 `return None`，doctor 在 `pi_exec.py:151` 直接调用它，故 `reason is None → PASSED/"admitted"` 不可达（S-3 成立）。
- `rg -n "launch_reused" src tests docs` → 仅 `src/paper_radar/pi_execution/errors.py:28`，无任何抛出处（P-1 成立；仅闭集卫生问题，未观察到运行时行为错误）。

## 小结

- **Standards**：7 项发现（P2×2、P3×3、P4×2）；最重为 **S-1**（doctor 公共状态 token 未在 Contract 登记，其中 `screening_configuration_missing` 也不在 `ExecutionReason` 闭集内）与 **S-2**（`timeout_invalid` 领取前拒绝零用例）。
- **Spec**：1 项发现（P3）；最重为 **P-1**（`launch_reused` 声明于公开闭集但无产生路径）。
- 两轴均报告 `完成状态: 完整`；未覆盖范围见各轴末尾（完整门禁、`check-compatibility`、真实 Pi/auth/模型/现场隔离均未运行，按裁决属 Cwd/Live 承接，不计本次缺失）。

---

## 外部审阅后逐项处置（#140）

本节为同一 fresh implementer 的增量，上方原报告保持原文。
本轮新增测试在另一个 D1 台账记录，旧 Pi195 和 A1–A10 固定分母不扩大。

### S-1：采纳公共 token 登记，拒绝混入执行错误闭集

`doctor.md` 现在明确 `screening_configuration_missing` 是 admission 检查项的
公共诊断词汇；它不代表 `PiExecution` 抛出的失败，因此不加入 `ExecutionReason`。
当前无产品准入证据，admission 固定非 passed；删除不可达 `admitted`，
也不为已删除 token 创建伪正例或产品证据入口。
其他 selection/supply/cwd/credentials/isolation 的四态语义保持。

验证：现有 doctor 公共 CLI 缺 Screening 配置、缺证据/非法采样、只读及退出2回归。

### S-2：采纳并修复实际超时类型漏洞

执行服务的上限检查原本已有实现，但确实缺回归；直接 `prepare_launch`
另外实际接受 True，字符串超时会抛 TypeError。
先获得 True 与字符串的4个修前失败，再增加精确数值类型检查。
两种直接启动超时各验证 True/False/0/负数/NaN/无穷/字符串；
五项 RpcLimits 各验证0/True/NaN/无穷/超默认上限。
所有负例断言 `timeout_invalid`，服务 `used_attempts == 0`，认证观察文件缺席，
并在真实程序进程边界拒绝任何 Popen，从而验证认证/模型会话零创建。

验证：新增模块中的39个超时节点及原资源/服务前后领取边界组合。

### S-3：采纳不可达分支判断，删除正例而不扩展产品权限

doctor 复用纯 `admit(binding, None)`，当前产品事实明确缺失；
删除 `reason is None → PASSED/admitted` 路径，仅保留 missing/invalid。
不导入执行编排或 `_evidence_for`，不接收 JSON/布尔值自证通过。
服务测试私有合成证据接缝继续只证明工程组合，不能变成 doctor 产品输入。

验证：doctor 公共 CLI 只读/无程序启动/严格退出，原基本/config/pi-supply 行为与金样。

### S-4：采纳身份构造集中与闭集类型，保留证据绑定边界

`LaunchIdentity.for_install` 集中从供给清单构造身份；服务预绑定使用已登记清单，
启动器使用持保护后的当前清单，仍在准备后比较原来的证据绑定键。
认证模式、provider 和 credential_source 使用 Literal。
完整启动身份仍记录实际代理是否使用及端口，服务构造与启动构造不再各维护字段表。
不把代理 URL/端口写入校准或语义绑定：#140 B7 的所有者键不包含这些字段；
当前实际代理配置由启动预检、受控 settings 和执行审计分别负责。
供给保护及本次审计 snapshot 与预算首次语义的区分保持。

验证：原服务审计/激活切换/证据不匹配/保护回归，新增实际代理设置及身份字段断言。

### S-5：采纳纯模型槽 accessor，拒绝人为损坏内部投影测试

config 提供 `screening_model(snapshot)`，任务模型匹配、执行引用核验与 doctor 共用。
输入仍必须经过公共 check/compile/load 的严格验证；helper 不重新编译、
不改变 v1/v2 规范字节、Stage projection 或校准身份，也不引入 LLM/执行依赖。
报告设想的“投影内部形状变化”没有真实公开输入复现，不据此构造私有坏对象测试。
公共损坏 snapshot 在现有服务/doctor 边界受控拒绝，作为实际边界回归保留。

验证：v1/v2 黄金身份、projection、公共损坏快照、任务历史与 Read 冷恢复导入守卫。

### S-6：拒绝本次修改，无可达公共 TypeError

`MaterialAssembly.models` 的值只由 `_validate` 与 `_remember` 配对产生；
MODELS 的唯一 spec 是 `ModelsDocument`，其 root 是严格验证后的 Models/ModelsV2。
只有篡改私有 `_validated` 或错误内部开发改动才能到达裸 TypeError。
公共历史装载还在 `config.service.load_config_snapshot` 的既有
`except (KeyError, TypeError, ValueError, UnicodeDecodeError)` 边界转换成 ConfigError。
当前配置装载不接收调用方提供的 `_ValidatedMaterial`，没有被遗漏的可构造输入。
把不变量分支改成 ConfigError 会掩盖开发错误并新增不必要公共语义，故保持原代码，
不添加只验证人工破坏内部状态的测试。

验证：公开 models-v2 正负例、配置编译/恢复与损坏 snapshot 的受控拒绝；未声称该不可达分支有测试。

### S-7：采纳，给 #139 增量命名并保留旧分母

共享中央分母中的裸 `+1` 改为
`issue_139_central_members = {"tests/migration_expectations.py"}` 的显式集合大小，
并断言它属于当前中央成员。原252基数、准备材料增量及完整成员集合检查保留，
1175/28/41 refs 与 #139 在各组 source/fixture 的授权枚举均未弱化。
`test_scope_shared_dag.py` 仍为24节点。

验证：共享 DAG 与材料 inventory 守卫；无历史成员/数量减少。

### P-1：采纳，移除永不产生的公开原因

删除 `ExecutionReason` 中无产生路径的 `launch_reused`；
Contract 明确 `PreparedLaunch` 重复调用仍为 RPC startup_error，
领取后按既有 executor_error 消耗预算，不新增失败类别。
新增公共上下文回归先运行真实本机标准库会话，再重复调用并断言 STARTUP_ERROR，
身份不变，不产生第二会话；原领取后失败预算回归继续验证映射。

验证：新增一次性会话节点及原 service postclaim startup_error 组合。

### 补充：未绑定失败安全定位

通过公开离线执行入口运行真实隔离 pytest，在 setup/call/teardown/collection
失败时取得安全模块定位，原实现先出现无定位的修前失败。
正式 receipt v1 不扩字段或成员；独立 sidecar 从 receipt 路径派生，绑定同run_id与
receipt_sha256，消费方重新核对当前模块白名单及受控阶段。
不增加独立 env，嵌套流程不继承/覆盖外层诊断身份。
secret-bearing 参数、函数名、异常和原始输出不进入诊断与可见终端；
恶意绝对路径、坏阶段/跨run/坏哈希/缺损诊断全部返回空定位，实际非零仍失败。
正常与仅固定模块失败不建sidecar，历史终端/十四份正常证据/读者保持。
另通过真实隔离pytest将sidecar替换成FIFO，先复现入口阻塞，再以非阻塞描述符核对
普通文件并限制读取字节；修后及时返回原失败，不把坏辅助文件当作新的无界等待入口。
新 Contract 精确 live 分类只加一路径，原 inventory 全部历史绑定和元数据保持。

### 本轮验证与限制

- 全部最终相关42模块组合：**518 passed**，229.54秒；1条既有 SQLAlchemy 循环外键 metadata 排序警告。全部60个新增D1节点与原配置/任务/回执/恢复/范围守卫均通过。
- 最终受影响来源组合：**161 passed**，108.60秒；含新/旧审计接收、查询、备份、执行、Feed、doctor与历史冷导入。
- 安全诊断及原离线入口/终端字节组合：**33 passed**，21.65秒；包含13个新诊断节点。
- `./scripts/check-compatibility all`：**176 passed**，pytest 272.11秒，入口总耗时272.74秒，退出0。
- 全仓 `Ruff check`、`Ruff format --check`、`mypy` 全部通过（格式748文件、mypy747文件）；`git diff --check` 通过。
- 显式 main 基线候选 scope 审计退出0、无 hash/baseline 漂移；5条敏感路径逐下游20项确认，289条原计数记录保持，collection 为285模块/5281节点。最终提交身份重新审阅确认留树外。
- 全量仅 collection：352模块/6385节点；未绑定67模块/1104节点。本轮D1为47+13=60，旧Pi195和历史required不扩张。

完整门禁尚未运行；最终提交冻结后同次 `./scripts/check-offline` 退出0，状态为
`passed/verified/same` 才满足判据。run_id/监控记录只留树外，不改身份材料。
没有 live、真实 Pi/Node/auth/模型、cwd现场、TLS/DNS 或主机级出站验证；
Cwd/Live/B 承接保持，当前产品缺证据继续领取前阻断，`stage_a_verified=false`。
