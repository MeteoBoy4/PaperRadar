# #168／#176 外部 r1／r2 核实修复的独立覆盖

本记录只覆盖外部两报告所引出的本轮代码、文档和回归，不回写旧证据。
基线为 `integration/168-live-admission@5b97d7603a5d011bc57449390f41c79beca84d06`。
逐条结论见原文完整保留后追加的 [r1](../../intent/review/issue-168-live-admission-review-r1.md#本轮逐项核实与处置追加原报告全文保留) 与 [r2](../../intent/review/issue-168-live-admission-review-r2.md#本轮逐项核实与处置追加原报告全文保留)。
Refs #168、#169、#170、#171、#172、#173、#174、#175、#176；父 #168 仍 OPEN，不以此记录关闭父票或恢复 Live 前沿。

## 需求与修复边界

- 共享 guard 的持久收紧只选择实际漂移／材料不符或显式失败项；到期、未激活、未测／unknown 不因混合场景被提升为不可逆失败。物理来源失信仍 fail closed 并持久收紧。
- 两消费者共用三个检查点和穿事务拒绝类型。凭据刷新前检查→准备后重绑→固定时间打点→业务事务内帧校验后只读 preclaim 的顺序保持；Read 的准入错误优先级、业务资格、attempt、预算、retry 与已派发结算不变。
- registry 导出冻结六格 UseId 的闭合只读映射；拒绝空登记与未定义用途，不借内部事件载荷制造类型。receipt v1／账本 schema1／旧事件字段不迁移。
- 删除生产死别名，保留两入口 trap 行为与既有不可达节点；全产品 AST 覆盖直接 Name／Attribute Load 和常量 getattr。该有限扫描不覆盖任意动态 Python，不防同 uid 同时改源与守卫。
- 采样结构校验成为独立纯入口；legacy 三布尔 admit 保持旧 token 和语义。doctor 只读同一 loader 投影，继续禁止 helper／tick／认证／外部 I/O。
- 管理入口中文拒绝保留机器 stage／受控 reason；未知异常即使像 token 也不回显。当前错误使用 evidence_activation 限定；新发 v5 配置使用限定 key，旧 v4 配置与专用续行目标只读兼容，旧安全回执／事件字段不改。
- 异常 probe 显式记录当前案例，不按完成数反推 SITE_CASES。没有复现旧代码 IndexError：异常前 result 最大 4，下标最多 5，SITE_CASES 长度为 7。六个异常阶段由合成 OS 边界覆盖。
- README／Contract 保留当前公共能力和导航，交付证据仍归旧 verification，后继职责指路线图。不公开整个 Ledger 写事务、不合并保护职责不同的 fsync，不删除既有工程测试。

## D1 人工节点与 collect

本轮新增独立模块 `tests/test_live_admission_review_fixes.py` 共 **24** 节点：混合漂移 2×3＝6、probe 异常 6、跨模块 AST 3、磁盘冷进程 2，以及 v4 目标拒 v5、显式源覆盖、closure 中文拒绝、resume 中文拒绝、未知异常脱敏、owner CLI 限定原因、空登记拒绝各 1（7）。
`tests/live_admission_source_support.py` 为新增 support，无测试节点；`admission_checkpoints.py` 为生产模块，不是验收组。

| 触及的既有独立模块 | 当前人工／collect 节点 | 变化 |
| --- | ---: | --- |
| `tests/test_live_admission_source_guard.py` | 7 | 原 6 保留，新增 v4 部署字节保全 1 |
| `tests/test_screening_live_admission.py` | 41 | 节点不变，trap 适应死别名删除，AST 范围增强 |
| `tests/test_read_live_admission.py` | 53 | 节点不变，trap／AST 同上 |
| `tests/test_consumer_live_admission_consistency.py` | 6 | 原节点不变，验证共享编排 |
| `tests/test_owner_resume_after_backup.py` | 27 | 原节点不变，fixture 显式模拟冻结 v4 runtime |
| `tests/test_live_evidence_lifecycle.py` | 36 | 原节点不变，当前限定原因预期同步 |
| `tests/test_live_evidence_owner_cli.py` | 7 | 原节点不变，当前限定原因预期同步 |
| `tests/test_live_evidence_review_freshness.py` | 17 | 原节点不变，当前限定原因预期同步 |
| `tests/test_protected_admission_intents.py` | 39 | 原节点不变，新发配置 key 与当前原因预期同步 |

六模块 collect 命令（新模块、D7、Screening、Read、一致性、v4 续行）得到 **158** 节点，与 24+7+41+53+6+27 相符。
旧 `31／478`、`33／522` 台账、固定 scope 成员／用途／计数／required 集合均原字节保留；本表不追溯扩大历史结论。

## 新旧策略与精确源登记

当前策略为 `pi-admission-v5`，新增 `tests/fixtures/live-admission-source-guard-v5.json`，显式 **46** 源。
相对已部署 v4 的 39 源新增两续行脚本、共享检查点、collector、site_tree、owner CLI、`pi_supply/filesystem.py`，不由目录扫描或生产依赖图自动扩张。
v5 最终 manifest SHA256 为 `5b298801df891e8284def2327e26b9a12c7db9a41554481c387c4ca915d1f03f`；它的首次摘要锚只追加在新键。

| 保留的旧 manifest | 原 SHA256（本轮逐字核对） |
| --- | --- |
| v1 | `695c4e9bc933b06bb211663796bb1dd89db52d000881c8590e82ac4e57e1a2f0` |
| v2 | `aa3cb3836b4072a8e6d66b6c99f3181f901f90aa8015e59dc24a3c82d8244ac4` |
| v3 | `78c7e3f27768e138a9137395cefb71cb0058005020cf3a4d1ac4ad9fc5726fc6` |
| v4 | `ff8a37321ea097d9d444d4840212f249431d36d2b364f275f7ca1253db7cefc1` |

`contracts/schema.py` 仅删除死常量并加冻结错误文本兼容说明。源旧 SHA256 `ab0cdf935f5ed2a0b194dac9fcf7972dbad400166f49c692d0c8ca6f1aa951bd` → 新 `14da1777bf404336d698f39f538d0823c32f0be98e9d53cd0814d2a2597be3d8`。
所有者批准该唯一中央 key；最初候选注释全角分号产生 `3f77aeb31299848745fb1ce45d98fc3be6e197f66c3798193ff7684a9117f1fe`，root 随后指示作必要 ASCII 修正，故最终字节不同于最初提案，不冒充原 SHA。
`scripts/verification_scope_materials.py` 最终 SHA 为 `61476facea5814466d3182f31fc78f088183fefd36f4ec5ccd4eaa04898589b0`；相对基线 diff 仅 schema 一个 key，直接影响 A9／A10 的普通 source，固定分母与 required 不变。

## 诊断与实际开发验证

所有测试使用 `uv run --offline --locked …`，仅进程环境设置 `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=maintenance.auto GIT_CONFIG_VALUE_0=false`；没有修改 Git 配置或 lockfile。

可复现 red：

- 两正式消费者的六种混合场景：修复前／恢复原错误筛选的受控变异下均在无关 RPC 的 `revoked` 断言失败；纠正未激活 fixture 后再以原错误筛选重跑，**6 failed**，finally 恢复修复源逐字一致。
- 空 registry 拒绝：修前 **1 failed**（DID NOT RAISE），修后受控 `admission_use_undefined`。
- closure／resume 中文原因和下一步：修前 **2 failed**；公开 owner CLI 限定原因修前 **1 failed**；未知异常 token 脱敏修前 **1 failed**。
- 磁盘源码改变与磁盘 manifest 重绑由冷进程核对实际路径／`policy_version_must_change`，不是只改父进程内存。旧四 manifest 的字节回归同时保持。

最终运行结果如下；开发子集及兼容组合不等于正式验收。

| 验证 | 实测结果 |
| --- | --- |
| 21 个最终相关离线模块（命令选择见下方） | 417 passed，267.89s，exit 0，无 skip／deselect |
| `tests/test_live_evidence_contract.py` | 2 passed，0.11s；Pydantic 权威与 receipt v1 schema／manifest 快照逐字一致 |
| `./scripts/check-compatibility all` | 实际选择 20 模块／176 去重节点，176 passed，pytest 323.62s，入口总耗时 324.17s，exit 0 |
| `ruff check src scripts tests` | All checks passed |
| 本轮 32 个 Python 文件 `ruff format --check` | 32 files already formatted |
| 本轮 31 个 Python 文件 strict mypy | Success: no issues found in 31 source files |
| 显式基线 `audit-verification-scope --collect --json` | exit 0，issues／baseline_issues 为空、无 hash_drift；仅 schema 一条 source_support／mechanical 变化，影响 A9／A10，旧绑定计数 collect 一致 |

最终相关选择：`test_live_admission_review_fixes`、`test_live_admission_source_guard`、`test_screening_live_admission`、`test_read_live_admission`、`test_consumer_live_admission_consistency`、`test_pi_execution_service`、`test_read_execution_admission`、`test_read_execution_rpc`、`test_read_execution_resources`、`test_live_evidence_lifecycle`、`test_live_evidence_review_freshness`、`test_live_evidence_owner_cli`、`test_owner_resume_after_backup`、`test_live_admission_closure`、`test_protected_admission_intents`、`test_final_admission_regressions`、`test_contract_schema`、`test_live_evidence_cli`、`test_pi_execution_admission`、`test_doctor_live_admission`、`test_live_admission_registry`（均为 `tests/<名称>.py`）。

两报告原始前缀的 SHA／长度逐字核对通过；r1 原文第 16／19 行的 Markdown 双空格硬换行亦保留。
暂存整体 `git diff --check` 仅报告这两处原文空白；排除两份原报告后无新增空白错误，不为消除诊断改写用户原文。

## 保留责任与未验证行为

本轮没有运行完整 `./scripts/check-offline`，没有沿用旧树的 passed／verified／same 作为当前树结论。
没有再次 code-review、push／PR、合入 main、关闭父票、接受 ADR 或改变能力分类。
没有实际 sudo／root 部署、collector／helper、受保护来源读取、证据激活、认证／模型／网络或读取凭据 cache 内容。
v5 与已部署 v4 不匹配，新 root 字节须所有者另行完整审阅、部署与新有效证据激活；旧 v4 专用恢复入口仍只对应其冻结原目标，不能用当前 v5 代替。
本轮离线回归不证明真实 OS `+a`、权限、Landlock、供应商行为或当前产品已经可执行。Live／B/H／I 的后继范围保持路线图与原任务图约束。
