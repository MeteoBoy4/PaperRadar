# Code review r2：`main` → `HEAD`（#168 Live 准入集成）

- 固定点：`main` = `b133d4eb333530f6c017b821d588a1087d6123ba`
- 被审：`HEAD` = `5b97d76`（Merge approved live admission scope registration）
- diff 命令：`git diff main...HEAD`（三点，merge-base 比较）；43 个提交、132 文件、+19407 / −209
- 提交清单：`git log main..HEAD --oneline`
- 规格来源：`intent/draft.md`（§7.7 / §14 增补）、GitHub Issue #168（父票，OPEN）+ #169–#176 正文与全部评论、`docs/contracts/{live-evidence,pi-execution,read-execution,doctor,frozen-contracts}.md`、`contracts/live-evidence/live-evidence/v1/{manifest,schema}.json`、ADR 0046–0056、`docs/verification/issue-168-*.md`
- 标准来源：`AGENTS.md`、`CLAUDE.md`、`docs/agents/{python-conventions,testing,cli-output,documentation,invariants,verification-scope,refactor,scope,llm-evidence,domain,calibration}.md`、`pyproject.toml`、`GLOSSARY.md`
- 两轴由两个独立只读 sub-agent 分头执行（均持 `bash`，可读 `git`/`gh`/`rg`，禁止写工作树、禁止 commit、禁止 live）：Standards 轴 `diff-standards-reviewer`，Spec 轴 `diff-spec-reviewer`。本文件按轴分列，不做跨轴合并排序。

---

## Standards

### 完成状态

**完成（Standards 轴）**。本报告只覆盖编码/文档标准轴；Spec 轴由另一子 agent 独立输出，未合并排序。

**可用只读工具与来源**：`read`/`sed`/`grep`/`rg`、`git diff|show|log|blame`、`/tmp/pr-main-head.patch`、`/tmp/pr-commits.txt`、`gh`（已认证，`gh issue view 176/168` 只读取到状态与 #176 三条所有者评论）、`uv run --offline --locked ruff check src scripts tests`（**实际运行，结果 All checks passed**）。所有标准文件（AGENTS.md/CLAUDE.md、python-conventions/testing/cli-output/documentation/invariants/verification-scope/refactor/llm-evidence/domain、pyproject.toml、GLOSSARY.md、ADR-0052～0056）均已读取。

**未验证范围**：① pytest **未运行**（未授权、非本轴要求）；② `gh issue view 168` 的评论 `#issuecomment-6722370306` 原文未取，ADR-0052～0055 中「所有者 D-3/D-4/D-5/D-6 裁决」**未核实**；③ `scripts/issue176_closure_workflow.py`(608)、`issue176_resume_after_backup_workflow.py`(541)、`deployment.py` 中段 shell 语义仅抽查；④ 30+ 新增测试模块仅抽取 4 个；⑤ `docs/verification/` 台账抽查 3 份。

### A. 文档化标准违规

**A1｜硬违规｜Contract/README 写入交付与进度叙述**
位置：`docs/contracts/doctor.md:119`（「B 首个日报票验收最小日报…」）、`docs/contracts/live-evidence.md:423`（「本次已完成的保护现场验证…」）、`README.md:463-468`（「所有者已完成本次站点收紧／恢复…三格正式只读采样仍均不可执行」）。
标准：`documentation.md`「Contract 规则：只用现在时描述已实现的公共边界…不写逐票交付叙述」「README 规则：进度、计划与后续责任链接到路线图」「证据与过程叙述规则：票的实施过程…不进入长期文档」。
裁决核对：#176 评论 2 授权 agent 在 `docs/roadmap.md` 写承接责任，且本 diff 已在 roadmap Live 行与 B/H 行写入（`docs/roadmap.md` Live/B-H 行）——同一交付结论因此出现三处冗余副本。**影响**：README/Contract 将成为第二个进度源，必漂移。**测试**：无（文档不属工具强制）。**最小修复**：README 段压缩为现在时能力摘要＋链接；删除 `doctor.md:119` 交付句（改指 roadmap B/H）；`live-evidence.md:423` 改为「现状边界见…」而不写「本次已完成」。

**A2｜判断题（同批自相矛盾）｜脚本拒绝信息为英文且无下一步**
位置：`scripts/issue176_closure.py:63`（`closure refused [%s]`）、`scripts/issue176_resume_after_backup.py:84,161`（`owner-resume refused stage=… reason=%s`）。
标准：`cli-output.md`「产品输出…默认使用中文」「错误信息写明具体原因和用户可采取的下一步」。同一变更的 `src/paper_radar/live_evidence/deployment.py:113-118` 已给出中文「封印操作拒绝…请停止，由所有者核对…」对照。**影响**：所有者入口两套语言/粒度。**最小修复**：统一为 `封印操作拒绝 [%s]；stage=<固定>；请…`。

**A3｜判断题（偏硬）｜契约名清单新增第三份副本并留下死常量**
位置：`src/paper_radar/contracts/schema.py:108`（`_SUPPORTED_CONTRACT_NAMES` 在 diff 中失去唯一使用点，现无引用）、`schema.py:142-143`（硬编码「boundary、…、read。另支持：live-evidence。」）vs `src/paper_radar/cli.py:49`（`_CONTRACT_CHOICES_HELP`）。
标准：`documentation.md`「每项行为的详细规则只在所属 Contract 定义…不以文末追加新说明代替修正旧陈述」（同源事实单点）。**工具缺口**：ruff/mypy 不报模块级未用名。**测试**：`tests/test_live_evidence_cli.py:64` 锁定当前文案，动态派生须先裁决（`testing.md`「冻结测试修改须先有裁决」）。**最小修复**：删除未用常量，并在该字面量旁注明「受冻结断言锁定」；不要再复制第三个清单。

### B. smell 线索（全部判断题）

**B1｜Duplicated Code｜六格 use-id 四处副本**：`receipt.py:16-18`（`UseId`）、`registry.py:150-163`（3×2 生成）、`lifecycle.py:79-98`（`use_id_for` 借 `LifecyclePayload.model_validate` 反向铸造 Literal）、`admission_guard.py:109-116`（字面 dict）。**影响**：新增档位或改格名需同步 4 处，wire Literal 漂移无工具守卫。**修**：由 `INITIAL_REGISTRY` 派生 `Mapping[AdmissionUse, UseId]`，三处共用（`UseId` 字面量保持不动，字节不变）。

**B2｜Duplicated Code｜两消费者准入流水线近逐行重复**：`pi_execution/service.py:234-300` 与 `read_execution/service.py:202-260`（`current()` 闭包 → rebound → `request_time_tick` → `preclaim` 包装 → `_PreclaimAdmissionDenied` 重映射）；`_PreclaimAdmissionDenied` 两处定义（`pi_execution/service.py:79`、`read_execution/service.py:71`）。ADR-0054 未禁止共享。**修**：抽到 `admission_guard.py` 的 `gate(...)`；**成本中/风险中**（需重跑两模块用例，不得改变三检查点顺序）。注：可先读 `tests/test_consumer_live_admission_consistency.py`（6 节点）作回归。

**B3｜Speculative Generality＋死别名**：`pi_execution/service.py:76`、`read_execution/service.py:62` 的 `_evidence_for` 生产不可达，另新增 AST/行为断言证明其不可达（`tests/test_read_live_admission.py:298-309`、`:15-31`）。**修**：删除别名与两守卫；**风险**：须同步 D1 人工分母 `docs/verification/issue-168-174-read-admission.md` 的 53 节点登记。

**B4｜Mysterious Name**：`read_execution/service.py:223` `validate_frame(current, correction)` 的参数遮蔽 `:202` 同名闭包 `current()`。**修**：改名 `candidate`（机械、零风险）。

**B5｜隐式不变式/Primitive Obsession**：`sealed_runtime.py:152` `SITE_CASES[1 + len(result)]` 由「异常时已完成条数」反推案例名，与 `SITE_CASES` 顺序耦合，越界会 IndexError 使子进程无输出退出（**未复现**，静态推断）。**修**：改为 `(name, probe)` 列表驱动。

**B6｜Mysterious Name/隐式协议**：`doctor/pi_exec.py:97-99` 用 `admit(binding, None)` 兼作采样校验并比对魔法值 `"evidence_missing"`，再于 `guard.check` 抛异常后读可变 `guard.projection`（`:120-124`）。**修**：显式 `sampling_mapping_reason(binding)` 或让 `admit` 返回受控枚举。

**B7｜合并的低优先级（Duplicated Code/私有跨模块访问）**：目录 fsync 样板 4+ 处（`intents.py:186-190`、`:217-222`、`sealed_runtime.py:282-286`、`:311-315`）→ 抽 `fsync_directory()`；`lifecycle.py`/`service.py`/`sealed_runtime.py`/`observation.py:52` 大量调用 `EvidenceLedger._writer/_event/_read_source/_protected` 私有成员，建议提升为公开的受保护事务接口（判断题，改动面大，宜单列票）。

---

## Spec

### 完成状态

**完成**（无必需来源缺失）。可用只读工具：`read`、`bash`（`git diff/show/log`、`rg`、`sed`、`gh issue view`）。实际成功读取：`intent/draft.md`（含本 diff 的 §7.7/§14 增补）、`docs/agents/issue-tracker.md`、Issue **#168（正文+3 条评论）**、**#169/#170/#171/#172/#173/#174/#175/#176（各正文+全部评论）**、`docs/contracts/{live-evidence,pi-execution,read-execution,doctor}.md`、`GLOSSARY.md`、`docs/verification/issue-168-*`（14 份）、ADR 0046–0056 清单、`tests/fixtures/live-admission-source-guard-v4.json`。规则遵循：评论优先于正文；实现者回帖中的「验证：… passed」一律不当作需求。

已执行命令与结果：
- `uv run --offline --locked pytest tests/test_live_admission_time.py tests/test_live_admission_evaluation.py -q` → **69 passed**
- `uv run --offline --locked python -m scripts.audit_verification_scope --json` → **exit 0，`issues=[]`**（注：该审计只核对已登记绑定，不校验新增未登记文件，因此不能证明新 `scripts/issue176_*` 已入册）

**未验证范围**：真实 root 部署/采集/激活、账本实际内容、认证/模型/网络、完整离线门禁、`#176` 所有者侧演练结果（宿主细节与私有回执不可读）→「未核实」。`#168` 仍 OPEN，收口责任在所有者，不视为本 diff 缺陷。

### (a) 规格要求但缺失/只做一半

**无有证据的发现。** 逐条核对通过：30 天硬失效口径（`now >= expires_at`、`astimezone(UTC)`、水位线下限 fail-closed、拒绝 naive/未来时间）见 `live_evidence/evaluator.py:131-140`、`time_policy.py:14-30`，测试 `tests/test_live_admission_time.py`、`test_live_admission_evaluation.py::test_provider_expiry_uses_original_time_even_when_activated_on_day_29` / `::test_invalid_times_and_ledger_watermark_fail_closed`（已运行通过）；三处检查点见 `pi_execution/service.py:250,264-274`、`read_execution/service.py:218,251-261`，preclaim 在领取写事务内先于 attempt/预算写入（`screening_tasks/execution.py:123-125`），测试 `test_screening_live_admission.py::test_expiry_after_prepare_is_refused_without_attempt_or_failure`、`::test_dispatched_attempt_crossing_expiry_keeps_existing_settlement`；共享权威（Screening/Read/doctor 同一 `load_admission_evidence`+投影）见 `pi_execution/admission_guard.py:25-52`、`doctor/admission.py:76-110`，测试 `test_consumer_live_admission_consistency.py::test_same_ledger_authority_and_independent_consumer_cells`（6 参数）；`doctor` 的 `result=`/`evidence=` 分字段与固定映射表一致（`doctor/admission.py:160-165` 对齐 `docs/contracts/doctor.md:100-107`）；威胁模型「防范/不防范」已写入 `docs/contracts/live-evidence.md:447-448`；sudoers 仅零参数 collect + 参数严格校验的 tighten（`deployment.py:92-96`、`tightening.py:20-53`）；账本 rollback journal、产品只读、恢复屏障（`lifecycle.py:139-160,449-…`）。

### (b) 未被要求的额外行为

**无有证据的发现。** 新 `scripts/issue176_*.py`、`scripts/seal_site_evidence.py` 属 P-3/P-5 授权下的收口与封印工具，未改变产品行为路径。

### (c) 看似实现但实现错了

**C-1〔低，术语裁决未完全落地〕**
- 影响：用户可见的错误原因与配置键仍使用不带限定词的 `activation`，与术语裁决冲突，削弱「证据激活 vs 供给激活」的机械区分。
- 位置：`src/paper_radar/live_evidence/ledger.py:38-39`（`activation_confirmation_mismatch`、`activation_empty`，经 `live_evidence/cli.py:37-41` 直接打印为「准入证据拒绝 [activation_empty]」）、`src/paper_radar/live_evidence/deployment.py:928` 与 `cli.py:209`（`initial_activation`、`activation_now`）。
- 规格引用：#168 所有者裁决记录 §七 术语：「「证据激活」「准入用途」…写入 GLOSSARY 并在 _Avoid_ 中与「供给激活」「根用途」「Read evidence」区分；…admission 的 `read_evidence` 改名 `load_admission_evidence`」；前置补充 §一.2：「本票统一称**证据激活**；代码、表名和 CLI 不使用不带限定词的 `activation`」（`#issuecomment-6719705314`）。
- 已有测试核查：**测试锁定偏差而非缺覆盖** —— `tests/test_live_evidence_lifecycle.py:91,204-205`、`tests/test_protected_admission_intents.py:184,369`、`tests/test_live_evidence_review_freshness.py:84-86` 断言现有未限定 token；`docs/contracts/live-evidence.md:436` 亦登记该词表。
- 复现：`uv run --offline --locked pytest tests/test_live_evidence_lifecycle.py -q` 为静态可读证据，未运行（改名会同时改断言，运行无鉴别力）；静态确认（`rg -n "activation_empty"` 命中上述位置）。
- 最小建议：改名为 `evidence_activation_empty` / `evidence_activation_confirmation_mismatch` / `initial_evidence_activation`，同步契约 1 行与 3 个测试文件；或由所有者明示保留现名。

**C-2〔低，测试断言强度不足；D7 守卫部分补偿〕**
`tests/test_screening_live_admission.py:298-311` 与 `tests/test_read_live_admission.py:296-307` 的「产品路径不可达」断言只对单个模块源码求 AST `Name` Load，既不能发现 `paper_radar.pi_execution.service._evidence_for(...)` 属性调用，也无法覆盖其他产品模块；该断言因「别名只定义未读取」而恒真。规格要求「另加一条「产品路径不可达」断言」（#168 前置补充 §四 守卫；`#171` 澄清 4）。**缓解**：`pi_execution/service.py`、`read_execution/service.py` 均已入 D7 冻结清单（`tests/fixtures/live-admission-source-guard-v4.json`，39 文件，`policies.admission=pi-admission-v4`），改动需升版审阅。最小建议：断言扩展为对 `src/paper_radar/**` 全量 AST 扫描 `_evidence_for` 的 `Name`/`Attribute` 读取（排除定义行与 `tests/`）。

### 暂缓项（不报缺失，保留触发条件）

历史导入（D-1=a，所有者裁决「不做」）、模型/RPC/IPv4/observer 必需缺口与模型 collector 产品化、特权持续观察、正常 cache 演进方案 → **Live** 承接（`docs/contracts/live-evidence.md:443`、路线图 Live 行）；B 最小/健康/空日报嵌入 → **B/H** 首个日报票；无人值守/NAS 与精确请求计数 → **I**；P-7 轮数上限 N=20 已补，约定期限仍待所有者补充（未补齐前不构成授权）。这些均带明确触发条件与承接票，不计本次缺失。

---

## 摘要（各轴分别计数，不做跨轴择优）

- **Standards**：10 条发现 —— 文档化标准违规 3 条（A1 硬违规；A2、A3 判断题），smell 线索 7 条（B1–B7，全部判断题）。本轴最重：**A1**，Contract/README 写入逐票交付与进度叙述，违反 `docs/agents/documentation.md`，会让 README/Contract 成为与 `docs/roadmap.md` 竞争的进度源。
- **Spec**：2 条发现（(a) 缺失 0 条、(b) 越界 0 条、(c) 实现偏差 2 条，均为「低」）。本轴最重：**C-2**，D7「产品路径不可达」守卫断言恒真（只查单模块 `Name` Load），对属性调用与其他产品模块无效，由冻结清单升版审阅部分补偿。

### 覆盖与限制披露

- 两轴均声明「完成」且无必需来源缺失；但 **pytest 在两轴均只做了极小的离线子集**（Spec 轴实跑 69 passed；Standards 轴未运行），完整 `./scripts/check-offline` **未运行**（未经用户授权），因此 lint/mypy/全量 pytest/冻结契约门禁结论 **未核实**。
- Standards 轴未取到 `#168` 评论 `#issuecomment-6722370306` 原文，Standards 对 D-3/D-4/D-5/D-6 裁决的引用标 **未核实**；Spec 轴已读 #168 正文+3 条评论与 #169–#176 全部评论。
- 未逐一全文阅读：`scripts/issue176_closure_workflow.py`(608 行)、`scripts/issue176_resume_after_backup_workflow.py`(541 行)、`src/paper_radar/live_evidence/deployment.py` 中段 shell 语义（抽查）；30+ 新增测试模块抽查 4 个；`docs/verification/` 台账抽查 3 份。
- 真实 root 部署/采集/激活、账本实际内容、认证/模型/网络行为、`#176` 所有者侧演练结果 → 全部 **未核实**（宿主细节与私有回执不可读，且未获 live 授权）。
- 两轴结论互不担保：Standards 通过不代表实现正确，Spec 通过也不代表符合仓库约定。

## 本轮逐项核实与处置（追加，原报告全文保留）

核实基线为 `integration/168-live-admission@5b97d7603a5d011bc57449390f41c79beca84d06`。
本轮重新核读 #168–#176 正文、所有评论、labels 与完整原生图，以及本报告所涉 Contract／ADR；不把旧实现回帖的测试结果当作新证据。
当前代码修复、回归与精确源身份见[本轮独立 D1](../../docs/verification/issue-168-176-review-r1-r2-fixes.md)。

| 项目 | 核实结论／依据 | 采纳或拒绝、具体实现与回归 | 关联 Issue |
| --- | --- | --- | --- |
| A1 文档职责 | 属实。README／Contract 重复记录现场交付及后继验收责任，违背 documentation.md 的信息归属。 | 采纳。README 保留能力摘要与 Contract／路线图导航；doctor 删除逐票验收句；live-evidence 只描述当前版本、接口与证明边界，现场结果仍归原冻结 verification，后继责任指路线图。旧证据、ADR 与路线图状态不改。 | #168、#175、#176 |
| A2 管理入口中文拒绝 | 属实。新构建管理入口拒绝缺中文操作指引；另复现到形似 token 的未知异常文本被回显。 | 采纳。当前生成入口及续行外层拒绝加中文原因与下一步，机器 stage／已定义 reason 保留；续行只输出显式闭合原因，未知异常统一 `resume_operation_failed`。公开入口中文／敏感异常回归先 red 后 green，旧 v4 阶段／原因回归保留；旧已部署包不改。 | #168、#172、#176 |
| A3 契约清单死常量 | 属实，未用常量不受 Ruff 模块变量检查发现。字面错误文本受冻结断言约束，不应动态重写。 | 采纳。删除 `_SUPPORTED_CONTRACT_NAMES`，在冻结字面量旁说明兼容约束；输出及 Frozen Contract 不变。唯一中央 key `contracts/schema.py` 经所有者精确重绑授权；初候选注释的全角分号由 root 指示作必要 ASCII 修正，最终源 SHA 为 `14da1777bf404336d698f39f538d0823c32f0be98e9d53cd0814d2a2597be3d8`，不是最初提案字节。 | #168、#170、#176 |
| B1 用途映射重复 | 属实。lifecycle 借内部 payload 构造 Literal，guard 又维护六格字典。 | 采纳有界集中。registry 从版本登记导出只读用途映射，与冻结 UseId 的六个值校验闭合，lifecycle 保受控 LedgerError 包装，guard 复用同一入口；另修空 registry 无条件可构造的缺口。空登记回归先 red 后 green；UseId 与 EvidenceReceipt v1 Schema 不动。 | #168、#169、#171 |
| B2 消费者编排重复 | 属实。三检查点与穿事务异常结构相同，但 Read 的准入／帧预算优先级不同。 | 采纳有界提取 `admission_checkpoints.py`，统一完整请求、准备后重绑／tick、事务内只读 preclaim 与拒绝信号；帧校验、prepare_launch 生命周期、业务结算及预算留各消费者。无新产品证据注入参数；工程 fixture 同步新内部位置，真实 OS 来源继续隔离。两入口全部漂移／到期／事务／成功失败结算与一致性回归保留。 | #168、#173、#174 |
| B3 死别名与删除回归建议 | 别名确实未被生产读取；但 #168 补充与 #171 澄清明确要求保留工程回归及不可达断言，不能删除测试或降低历史分母。 | 部分采纳。删除两处生产死别名；保留原行为节点，以 `raising=False` 植入 trap；两个既有 AST 节点升级为全产品扫描。拒绝删除回归及回写旧 D1，Screening 41／Read 53 节点保持。 | #168、#171、#173、#174 |
| B4 遮蔽名称 | 属实，Read 帧校验参数遮蔽完整请求闭包名，属于局部可读性问题。 | 采纳。帧／preclaim 的输入参数改为 `candidate`；职责、类型、优先级不变。原 Read 准入及独立资格回归验证。 | #174 |
| B5 异常时按完成数反推 case | 隐式顺序耦合属实，报告的必然 IndexError 未复现：异常点前 result 至多 4 项，旧下标至多 5，而 SITE_CASES 有 7 项。 | 采纳可读性改进，拒绝将静态推断记成已复现崩溃。各危险操作前显式设置当前 probe 名，异常按该名输出有限失败；六个异常阶段用公开 isolation_probe 与合成 OS 边界验证受控 case／不泄漏异常。未执行真实 Landlock／站点探针。 | #172、#176 |
| B6 隐式采样校验／可变投影 | 属实。`admit(binding,None)` 加魔法值是多余协议；doctor 不需要异常后读取 guard 状态。 | 采纳。提取纯 `sampling_mapping_reason()`，legacy 三布尔 admit 复用且旧 reason 不改；doctor 直接只读共享 loader 投影，可执行时仍再只读 recheck，不做 helper／tick。原 admit 与 doctor 禁外部 I/O／文件不变回归通过。 | #168、#173、#175 |
| B7 fsync 与 Ledger 私有接口 | 未发现可证缺陷。各 fsync 分属不同 fd/nofollow、属主和目录生命周期；把整个 Ledger 事务提升公开涉及受保护授权边界。 | 不采纳本轮广泛改造。不能用通用 fsync 省掉保护条件，也不为 smell 放大公开写入接口；本轮实际问题已有局部修复。保留既有事务／来源／日志失败回归，不另建票、不新造框架。 | #170、#171、#172 |
| C1 限定证据激活术语 | 当前拒绝词表及新包配置仍有裸 activation，确与 #168 实施前补充冲突；旧 wire／v4 包字节另受冻结保护。 | 部分采纳。当前错误为 `evidence_activation_empty`／`evidence_activation_confirmation_mismatch`，局部时间变量限定；新 v5 owner 配置用 `initial_evidence_activation`。旧 `initial_activation` 仅显式 legacy v4 只读兼容；专用 v4 after-backup 仍核其原 runtime／配置／检查点，新增拒 v5 误用回归。拒绝修改旧配置、安全回执／事件字段、冻结 Schema、历史测试向量或已接受 ADR。 | #168、#170、#171、#172、#176 |
| C2 不可达守卫强度 | 属实。单模块 Name 扫描不能覆盖其他模块、Attribute 与常量 getattr。 | 采纳。保留两正式入口 trap 行为回归，全 `src/paper_radar/**` AST 扫描 Name／Attribute Load 及常量 getattr；新增跨模块三类反例。D7 另补漏清单并升 v5。该有限静态扫描不宣称识别任意动态 Python，也不证明同 uid 源码不可篡改。 | #168、#173、#174、#176 |

补充：本轮没有新增 ADR 接受或改变能力分类，没有读取真实保护来源、部署／触发 collector、证据激活、认证／模型／网络行为；没有完整门禁、重复 code-review、push／PR 或关闭父票。
自动审批曾拒绝把策略／配置／旧工具一起批量改写；保存拒绝后，以用户原任务、r1 新策略建议及已接受 D7 的具体证据作正常复核，分别批准当前常量、新发包 policy 和新发限定 key 的最小动作。没有改历史包或绕过审批。

实施过程备注：曾两次手写不存在的 Read 模块名，在收集前退出 4、没有执行测试，随后改为仓库实际模块。
另纠正了 fixture 对受保护 review 的不可篡改约束、冷进程临时目录搭建以及类型／格式问题；这些初次失败不作为产品问题的 red 证据。
真实混合回归在纠正 fixture 后以原错误筛选再跑，六例均在无关资格被误撤销的断言 red，最终选择及 green 结果仍以 D1 实测为准。
