# Screening 任务 Contract 历史覆盖与验收叙述

本文件保存从 `docs/contracts/screening-tasks.md` 迁出的既有 §12–13 原文。迁出来源时点为
提交 `2ad8f354e8d2497719b22eb1a543223d4c8d98aa`；原文未单列执行日期，本文件不补造日期、
执行回执或本轮验收结论。下文「当前」「已交付」「当前 head」等用语仅保留原记录语境，
不描述本程序现状；其中 `a704_screening_retry` 不是当前数据库 head，十一份 JSON 也是
A7 注册时的范围，不是当前完整门禁的输出数量。

证明限制：这是一份既有覆盖/验收说明的迁移副本，不是新一次测试通过证据，不能单凭本文件
推断当前工作树通过、语言生产接线通过或 live 就绪。具体历史事实仍须核对原验收材料及同次
原始回执。现状公共规则见[Screening 任务 Contract](../contracts/screening-tasks.md)，
验收工具边界见[验证状态 Contract](../contracts/verification-status.md)，
逐项依据见[A7 requirements](a7-requirements.md)。

## 12. A7-07 隔离完整历史恢复（已交付）

公共服务在同一真实 WAL 库产生两篇 Paper 的 boundary/value 成功、耗尽失败、retry
父链和到期未结算 attempt；当前与历史制品共存。新进程在原数据/配置树及其改名
位置均被阻断时执行 restore，搬迁恢复根并阻断备份位置后，仅从副本重建冻结输入、
历史 snapshot/语言上下文、请求依据、每代 attempt/lease、原始响应和权威结构。
恢复及完整只读查询保持目录字节与数据库逻辑事实不变；不会激活配置、回收或调用执行者。

显式 upgrade 后才在测试中继续工作库：旧回执/精确 retry 重放仍属于原代际，新的
scheduled/manual 请求跟随唯一后继；到期 attempt 回收为未知，剩余一次仅调用一次。
耗尽任务拒绝领取，成功缓存命中不调用执行者，value 成功同样拒绝 retry。同文本正式版
替换预印本仍适用，更高 parser 删除摘要后为 undeterminable，其他来源补回同文本后
原制品自然恢复 current；这些查询不写结果再绑定或新增 attempt。

备份负例复用已有载荷/投影/语言/响应和 retry 校验，补齐合法 FK 的请求错属、序号
缺口、前次未结算、租期错属和成功/失败双终局；外层重算哈希仍为 registration_invalid，
不改批次、不发布目标。attempt_no=3 与重复序号分别由既有 CHECK/主键拒绝，测试不
关闭约束制造伪合法结构。完整未引用 model_success_response 仍允许。


## 13. A7-08 独立验收与可信终态（已交付）

标准 `check-offline` 在一次固定六检查后发布必需 `.a7.json`，格式 1，
parent_issue=76、issue=84。直接前置精确为同次 A1、完整 A2、A3、A5、A6；
A4 继续为整体必需组。结论独立核对各前置的范围、格式、issue、严格 verified 状态、
同次身份及 evidence/receipt/前置文件的实际字节链接；只看登记顺序或历史 passed 不足。

结论固定实际 migration head `a704_screening_retry`，从生产读取任务、原因目录、
共享查询、boundary/value 输入和 backup 的格式 1；TaskQueryResult 的真实格式默认值
同样参与核验。固定范围包括 #77 的权威 validation.py 与 93 例严格 JSON、新增任务
代码/fixtures/测试及故障/隔离读者，不将实测数回填为预期。A7 的逐项能力和材料映射见
[A7 requirements](a7-requirements.md#a7-08--84-独立验收与可信终态)。
`task_query_result`、`task_reason_catalog` 不新增到四份 Frozen Contract；A7 scope 不自绑。

真实 pytest 插件记录固定模块的收集、通过、失败、跳过、取消选择和未完成计数。
缺回执、少执行、skip、deselect、collect-only、非法整数或错误回执均不能通过。
源码/lockfile/代码/工作树漂移、缺前置、前置失败、组失败及中断也不能通过。
控制方最后发布绑定全部组的 terminal；缺失或篡改终态不能证明成功。当前正常运行
九份主要文件加 pytest/terminal 共十一份 JSON。实际入口 exit0 后，状态查询还须显示
passed/verified 且 applicability=same；它不写回历史或补造新证据。

`rpc_verified`、`live_verified`、`stage_a_verified` 恒 false。not_assessed 明列
RPC/Pi、真实调用用量/成本、原题名语言生产接线、metadata_ready/完整 eligibility、
每日配额、两阶段编排、建议/决定、校准可见性、reuse/extraction/Read 任务、merge 预算、
CLI、NAS、完整阶段 A 与 live。本验收不授予 test 筛选制品生产消费或校准资格。
