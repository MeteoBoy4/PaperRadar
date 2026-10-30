# Pi RPC Contract 迁入历史原文

本页保留 `docs/contracts/pi-rpc.md` 在基线
`2ad8f354e8d2497719b22eb1a543223d4c8d98aa` 中的既有覆盖和证明边界原文。
它记录 A8 离线工程及当时的 not_assessed 口径，不是本轮验收台账，也不证明当前或
live 就绪。原文未单列运行日期；固定来源摘要记载的只读核对时点为 2026-10-24，
实际验收历史以 [A8 requirements](a8-requirements.md) 的各次记录为准。
下列段落保留原措辞，仅调整迁移后相对链接；历史“未交付”不作为当前组件状态。
现状接口见 [Pi RPC Contract](../contracts/pi-rpc.md)。

## 独立档案库范围

A8 独立测试档案库通过真实 migration 和配置登记使用非占位系统 Prompt、prompt_only、
1.4.0；不消费或改写 examples 的 1.1.0 与 A4 的 1.3.0 供给材料。

## 同步与规模观察目标

离线测试用注入时钟与握手/屏障推进，不用 sleep 同步；既有 AST 守卫覆盖 A8 测试与
支撑。单例约 5 s、组总约 60 s 是规模观察目标，实际耗时在验收台账披露；不以紧墙钟
阈值在慢机器上判定协议失败，语义门禁仍核对注入期限和清理终局。

## 版本回摆覆盖

D1 的首次语义 snapshot 可以声明未登记的 1.3.0；只要新回执自己的 1.4.0 snapshot
与其投影相同，就可按原语义和预算执行。回摆 1.3.0 回执仍因协议未登记在 prepare
拒绝，不刷新次数。普通声明版本、纯执行审计、日期、会话或进程重建均不改变预算；
输入 A→B→A 回到原预算，同指纹跨论文版本继续适用。每次执行描述的审计取其自己
回执，包括回摆与 retry，不能把首次语义版本冒写为本次执行版本。

## RPC 组合恢复覆盖

RPC fixture 形成的成功、失败、retry 父链和未结算历史由既有 backup/restore 原样
处理；不新增 Schema、manifest、任务失败字段或词汇。非空 WAL 离线组合用例在阻断
原数据/配置目录的新进程中核对两阶段原始成功字节、权威结构、历史输入和预算；
恢复/查询保持只读且不导入 RPC 执行入口。仅一个用例显式继续，回收未知结果后只
消费剩余一次。成功仍为 test，完整事件/失败全文/thinking/自由错误不进入备份。
这不扩大既有恢复 revision 范围，也不承诺回退备份后的全局调用预算。

## D4、来源推导与 not_assessed

Pi 1.4.0 强制追加 cwd，section 实际是 `<cwd>\n<归一化路径>\n</cwd>`；preamble 不
包装。有效指令=登记声明指令+Pi cwd 段的已知缺口。所有者仅许可不含个人信息、每次
相同、内容无意义的常量执行 cwd；A8 不选常量、不把合成路径用于生产白名单。

来源摘要与三态登记见 [固定材料 README](../../tests/fixtures/pi_rpc/1.4.0/README)。
DERIVED-01(system补丁)、02(cwd包装)、03(user回显)、04(aggregate副本)、05(临时状态)、
06(空commands)、07(ACK/档位顺序)、08(token总和)、09(settled后收尾)、10(请求回显)、
11(三份回显预算)
都只按源码推导 fail closed，尚未由真实 Pi 运行逐项确认。对应检查只证明与固定源码
一致，不能把其升级成运行观测或生产隔离结论。

DERIVED-11 正例同时使用恰好 256 KiB 请求帧、64 KiB 候选和含 system/user/
assistant 的 4 MiB agent_end 帧；完整流约三份合并回显，处于 16 MiB 累计界限内。
thinking/signature 也计入三份回显。该正例证明固定上限可接收这组合法预算；超候选/
帧/累计界限不返回半候选，也不保存原始流。

当前没有生产启动器准入或真实 Pi 兼容通过证明。 生产接线目标见[规格补充约束](../../intent/draft.md#pi-生产启动器准入)，承接责任见[路线图](../roadmap.md#module-pi)。

rpc_verified、live_verified、stage_a_verified 继续为 false。not_assessed 还包括真实 Pi
运行与供给激活、凭据、参数效果、OS 文件/进程/网络权限、自动外发抑制、原题名语言
事实的生产接线（来源规则见 [ADR-0035](../adr/0035-feed-derived-original-title-language-fact.md)）、reuse/Read等其他阶段任务、业务资格/编排/每日配额、
校准可见性/门禁、CLI、
真实论文来源/Docling/NAS/无人值守。A8 只有离线协议与 test 任务接线证明范围。

## B 首次生产接线责任（#111，目标规格）

当前提供离线协议档案与管道组件，不提供生产接线通过证明；历史 not_assessed 不变。 生产接线目标见[规格补充约束](../../intent/draft.md#b-首次-pi-生产接线)，承接责任见[路线图](../roadmap.md#module-live)。

## 历史断言的适用限制

- 上述 not_assessed 属于 A8 的历史证明范围，不能据此否定其他组件后续实现。
  Feed 语言派生、来源/策略持久化与 value 组合登记的现状见
  [Feed 组合](../contracts/feed-pipeline.md)及其[交付证据](issue-114-feed-delivery.md)。
- cwd 的上游包装是源码推导；当前 RPC 内核只核对 cwd 字符串类型，不核对包装或路径
  白名单。生产目录的确认和隔离目标见[规格](../../intent/draft.md#pi-生产启动器准入)，
  不由本页合成样例或历史表述证明。
- 同步与规模段落不把 5 s/60 s 设为硬性能门禁；实测规模与耗时仍以所链 A8 台账为准。
