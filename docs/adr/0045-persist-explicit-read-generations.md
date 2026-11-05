# 显式 Read 独立保存代际预算与可重放接收事实

状态：已接受；日期：2026-11-05；依据：[#155 最终裁决](https://github.com/MeteoBoy4/PaperRadar/issues/155)、[#161](https://github.com/MeteoBoy4/PaperRadar/issues/161)；补充：[ADR-0031](0031-screening-budget-and-derived-applicability.md)、[ADR-0042](0042-accept-read-v2-with-final-attempt-degradation.md)、[ADR-0044](0044-freeze-read-input-rendering-and-preclaim-budget.md)。

Read 必须沿用两次预算、租约所有权与显式 retry 的纪律，但 Screening 的阶段与成功接收
绑定 boundary/value。扩张其任务类型或抽共享内核会耦合冻结历史；只持久处理视图又无法证明
末次丢弃和警告为何产生。

因此 Read 使用独立任务服务，以同库 paper/read/fingerprint 承载预算，每代最多两次，
失败终态才追加唯一后继。首次历史配置固定，语言参与输入，来源/用途标签与进程重建不刷新预算。
领取在短事务核验真实前置，执行在事务外；过期必须显式追加 outcome_unknown，不退款。

成功保存完整原始候选、上下文持久引用、真实 ordinal、接收策略、三规则版本与确定性输出、
诊断和丢弃清单。备份使用已记规则重算，未知证据规则拒绝；未知警告策略保留记录且不宣称等价。
test 执行入口没有来源开关，Pi 经专用审计端口进入同一个接收权威。模型执行真实性和现场准入
仍由实际 Pi 组合承担。

代价是维护独立任务持久层与回放闭包，保留未引用候选制品及历史代际；换取冻结 Screening
无需改造、崩溃不能补预算、路径迁移后仍可解释接受与降级的原因。
