# #168 / #176：Live 准入集成收口覆盖与待验边界

本台账记录最终收口工程，不替代各票冻结覆盖台账或真实 root 来源。
既有 scope、中央成员/哈希、required 集合、历史回执及固定分母保持。
本次新消费闭包仍是独立 D1；其进入正式组的方式须另行审阅，不能凭全量 pytest 退出而扩大旧组结论。
本票尚未完成真实收紧/恢复演练、唯一最终审阅及 G4 完整门禁，#176/#168 仍未收口。

## 独立模块与人工分母

下列数字按每票人工表合并，同名模块只列当前最终节点数；collect 仅用于核对。
历史台账保留其当时数字，不回写为本表。

| 模块 | 人工预期节点数 | 责任来源 |
| --- | ---: | --- |
| `tests/test_live_admission_registry.py` | 5 | [纯判定](issue-168-169-admission-model.md) |
| `tests/test_live_admission_evaluation.py` | 63 | 纯判定 |
| `tests/test_live_admission_time.py` | 6 | 纯判定 |
| `tests/test_live_admission_reader.py` | 2 | 不完整旧绑定/冷导入 |
| `tests/test_live_evidence_receipt.py` | 14 | [接收与账本](issue-168-170-evidence-ledger.md) |
| `tests/test_live_evidence_ledger.py` | 15 | 接收与账本 |
| `tests/test_live_evidence_contract.py` | 2 | 回执 Pydantic/Frozen Contract |
| `tests/test_live_evidence_cli.py` | 4 | 冷帮助与新显式契约 |
| `tests/test_live_evidence_lifecycle.py` | 36 | [生命周期](issue-168-171-evidence-lifecycle.md) |
| `tests/test_live_evidence_loader.py` | 4 | 共享 loader/持久收紧 |
| `tests/test_live_evidence_owner_cli.py` | 7 | owner 审阅/手动确认 |
| `tests/test_live_evidence_tightening.py` | 10 | 只收紧 helper |
| `tests/test_live_evidence_observation.py` | 7 | 当前受保护观察 |
| `tests/test_live_evidence_baseline.py` | 5 | stat-only 全根基线 |
| `tests/test_site_collector.py` | 14 | [β 站点采集](issue-168-172-site-collector.md) |
| `tests/test_site_deployment.py` | 8 | root 冻结部署/卸载模型 |
| `tests/test_site_tree_identity.py` | 5 | root 独立实际整树 |
| `tests/test_screening_live_admission.py` | 41 | [Screening 正式入口](issue-168-173-screening-admission.md) |
| `tests/test_current_execution_binding.py` | 1 | 真实临时当前绑定 |
| `tests/test_live_admission_source_guard.py` | 5 | 最终 v3 清单与 v1/v2 摘要锚 |
| `tests/test_read_live_admission.py` | 53 | [Read 正式入口](issue-168-174-read-admission.md) |
| `tests/test_consumer_live_admission_consistency.py` | 6 | 两正式入口同一权威/格隔离 |
| `tests/test_doctor_admission_disclosure.py` | 8 | [结构化披露](issue-168-175-admission-disclosure.md) |
| `tests/test_doctor_live_admission.py` | 9 | 实际临时账本与正式 doctor |
| `tests/test_site_deployment_checkpoint.py` | 10 | [部署检查点](issue-168-172-deploy-checkpoint.md) |
| `tests/test_site_g2_entry.py` | 9 | 单次 sudo 边界模型 |
| `tests/test_live_evidence_review_freshness.py` | 17 | [审阅与新鲜度](issue-168-171-review-freshness.md) |
| `tests/test_site_runtime_upgrade.py` | 27 | 保历史受控升级模型 |
| `tests/test_live_admission_closure.py` | 25 | 本票消费者部分证据组合、owner 演练/中断及封印包篡改模型 |
| 合计 | 418 | 29 个独立未绑定模块，非旧验收分母 |

新增支撑 `tests/live_admission_closure_support.py` 只提供无 root 文件系统模型。
本票新模块的三个组合节点逐一覆盖部分站点 active、持久撤销及恢复屏障；
两个正式消费者均不刷新凭据、不领取 attempt，doctor 对同一原 verified/缺失 RPC 事实一致。
五个 owner 顺序模型覆盖成功与临时激活/撤销/恢复/最终激活失败，始终不自动清理、回滚或授予。
九个 shell 模型覆盖冻结执行、重复拒绝及 runtime 成员/源码/权限/链接/入口/策略/用户包篡改；密码边界后的用户来源换链只执行入口内嵌的已审原字节，不让root读取用户路径。
另一个节点核对构建身份、单次 sudo 和不自动确认。三个只读采样节点核对现有模型/adapter槽元数据、同一正式构造/判定与过期拒绝；四个预算节点只查询必要标识/计数并拒绝WAL/SHM/journal，不读取payload。
替身仅位于时间、OS/子进程边界；实际临时 ledger、receive、owner CLI、helper、backup/restore 和判定均复用正式实现。
这些模型不证明真实 root、sudoers、主机重启、模型或网络行为。

## 实际站点与安全回执

所有者已执行经审阅部署/采集/受信接收，并完成新的非空站点分项证据激活。
本票以正式 `EvidenceLedger`/`EvidenceLifecycle.snapshot` 只读复核受保护属主与非空 active，未写账本。
这一事实只说明站点分项激活存在；模型、RPC、IPv4 和 observer 仍有缺项，不表示整体可执行。
宿主绑定、短 ID、UID/组能力、路径清单及指纹不写公共台账。

真实收紧、撤销持久化、独立进程重读与账本恢复仍须所有者审阅并执行新的封印包。
具体操作与中断后最终非空激活路径见[待审方案](../../intent/review/issue-168/closure-owner-plan.md)。
安全回执必须由 root 冻结流程落在受保护账本目录，包含原主张、原验证时点、激活事件时刻、
绑定摘要、用途、登记版本与期限依据；用户可写 `.scratch` 只作索引，不能自证授予。
“至少一组 active”的最终判定时点为该包最后的新进程资格查询；本次尚未产生该最终安全回执。

## 开发验证

先运行实际消费者功能组合：Screening、Read、同账本一致性、doctor 两模块与 D7 共
**122 passed in 203.55s**，退出 0，无 skip/deselect/incomplete。
新增收口包首个回归因构建模块缺失 red，最小实现后转绿。
owner 模型首次发现重复演练已因不可逆撤销安全拒绝，预期调整为精确的 closure_not_eligible；
shell 模型首次因模拟宿主根目录意外组可写触发 protected_mode，修正模型权限后通过，产品保护条件未变。
新增模块最终 **25 passed in 17.97s**；连同活文档链接、回执Frozen Contract与D7共 **36 passed in 18.00s**，退出0。
五个 Python 文件 Ruff/格式/strict mypy 与 git diff --check 通过；29独立模块逐模块collect核对 **418节点**，退出0。
只读正式采样工具 `scripts/issue176_admission_snapshot.py` 从当前供给 activation 和所选模型/adapter元数据构造请求，
不读Profile/Prompt/全文或auth内容，不刷新/领取/tighten/tick；采样输出供主代理在P6刷新后立即只读核对。
预算metadata-only回归先红后绿；只选必要ID/指纹、代际、attempt序号和每日领取标识，immutable只读防止创建sidecar，已有sidecar即拒绝。

`check-compatibility all`：**65 failed、111 passed**，176节点，pytest419.73秒，入口总耗时420.47秒，退出1。
旧登记尚未重绑；代表性历史基线已有scope_drift→prerequisite_not_passed链，但其余失败没有逐节点基线归因，不能宣称全部来自同一根因或兼容通过。
显式main基线只读审计含collect退出1，结构issues/baseline_issues为空，旧固定节点收集无skip/deselect，
仅cli.py/contracts/schema.py/pi_supply/cli.py三路径11登记机械漂移；本票未写回旧登记。

相关测试与兼容检查均为开发证据；不发布 A1–A10 或完整离线门禁结论，不写 run_id。
完整离线门禁仅在最终审阅/统一修复、精确登记裁决及冻结树后，由主代理按 G4 执行并查询同 run 的 passed/verified/same。

## 固定材料候选与后继

旧三条 source/support 漂移涉及 `cli.py`、`contracts/schema.py`、`pi_supply/cli.py`，须逐路径及所有直接/下游组审阅；
不能为消警重算未知材料、修改旧成员/分母，或用候选确认掩盖 hash_drift。
新增 Contract/Read Contract/路线图的精确分类、新 D1 闭包及当前索引现状句单列候选；
实际基线审计、完整 HEAD/dirty/target 身份与 old/new SHA 白名单保存在树外审阅材料，变化后重生成。

[路线图](../roadmap.md#模块承接索引)保持 Live 对父票前置和 B 对 Live 的依赖。
Live 承接模型 collector、项目部署、特权持续观察、模型侧重验和正常 cache 演进方案；
B 首个日报票验收共享片段在最小/健康/空日报的嵌入，H 承接完整日报；
I 承接无人值守/NAS、IPv6/新平台和精确请求计数重评。
Read 的根用途、正文质量、输入预算、两次尝试、代际与租约仍独立，F/G 资格不被证据激活代替。
P-7 虽有20轮上限但期限未补齐，本票不认证、不调用模型、不联网、不导入历史探索证据。
