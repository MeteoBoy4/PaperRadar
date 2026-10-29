# 将 B 的真实纵向实验隔离在独立数据根

状态：已接受；日期：2026-10-28；依据：[基线裁决原文](https://github.com/MeteoBoy4/PaperRadar/blob/91e5d02e199f1921ca8afd2b7bdb8f257e6264f3/docs/adr/0036-isolate-stage-b-read-experiment.md)；补充／部分取代：见本行关系回链；正文边界继续适用。 关系回链：本记录补充／部分取代 [ADR-0010](0010-use-docling-as-the-only-body-parser.md)、[ADR-0026](0026-control-pi-through-a-bounded-rpc-adapter.md)、[ADR-0030](0030-paper-version-identity-and-source-observations.md)，具体适用边界见各正文。

原状态与裁决依据：已接受，2026-10-28。依据 [#111 Further Notes 与全部后续确认](https://github.com/MeteoBoy4/PaperRadar/issues/111)：允许固定 JGR 样本在四刊正文 fixture 完成前做受限 Read，选择独立实验数据根，结果不复用、不提升。此举提前验证真实接口，同时保持 A7 的同库预算身份与正式校准边界；代价是 C 必须导入跨库暴露排除清单，生产日后处理同论文要从头执行。

## 例外与隔离

- 本 ADR 仅对 [ADR-0010](0010-use-docling-as-the-only-body-parser.md) 的四刊代表性覆盖前置给予 B 固定样本窄例外；通用质量门槛、唯一 Docling、A9 权威接收和 [ADR-0026](0026-control-pi-through-a-bounded-rpc-adapter.md) 的预算/RPC 隔离不变。F 仍交付四刊合格正文与摘录供给，D 才交付 reuse 执行与校准，G 扩展长文 Read。
- B 整条 Feed→Screening→人工决定→PDF→正文→Read→最小日报都在显式实验数据根内。根级标记随备份/隔离恢复保留；实验命令显式选择该根，普通生产 run-due、报告及消费查询拒绝它，初始化生产根不接纳实验根。真实执行来源、实验用途与质量资格是三个独立判断，生产执行来源不授予正常消费资格。
- 不在 A7 `(paper_id, stage, fingerprint)` 中增加用途维度，也不以请求来源/标签变化重置预算。实验根只绑定冻结样本；不开放任意 Paper 的“忽略 fixture”开关。准入绑定论文/版本、Feed、PDF 内容、配置与质量证据，任务、正文、分析和最小报告的引用链可回查。
- 旧实验结果只作历史回查，不复用、不提升、不提供提升入口。四刊 fixture 后来通过也不自动开启 Read/reuse 或提升旧结果。长期生产库由 C 初始化；日后同论文从正常入口重新处理、使用独立预算，不能拷贝实验成功/任务来补位。
- B 导出以强标识（DOI 与版本关联）固定的已暴露论文清单；C 在保留器启用前导入生产库，机械排除正式校准。备份/恢复、重复发现、版本变化及未来合并均不得丢失排除依据，不能仅靠临时 paper ID。
- B 保存两阶段 Screening 输出与人工决定，可展示无自动决定权的实验筛选建议；`out_of_scope` 仍停止 value。实验材料不流入普通生产建议/自动决定链；ReadAnalysisOutput 的必填 `next_action` 保留。最小报告使用最终 report run/entry 契约、可重建、标注实验范围且遵守五项/全文三项容量，不进入普通日报候选。

## 样本与质量

用户在 Screening 前按研究判断从当轮当前 JGR Feed 预选真实论文并记录理由；选定后冻结论文/版本、Feed 来源与取得的 PDF 哈希。§13.3 的历史 `10.1029/2025JD043927` 是回归样本，不能在未满足当轮发现条件时替代纵向样本。失败或 `out_of_scope` 均保留；换样另记原因和新选择，不抹去旧暴露，不修改 Profile/Prompt 迁就结果。

必须使用与生产相同的 parser/canonical/normalize/evidence 链。逐文档门槛至少核验真实 PDF 与文本层、正文起点与阅读顺序、原页码/bbox/charspan 回放、源字符与生成内容分离、受限内容降级、正文/evidence 内容身份及冻结的人工版式核查依据。Docling 退出 0 或模型文字合理均不是通过依据，质量失败不得调用 Read；Read 候选仍须 A9 权威接收。

B 首个正文生产者前落实 [StageInput C1](../contracts/stage-inputs.md#c1-已知未决问题封面识别的论文元数据依赖)：格式 1 不含题名/DOI/摘要，normalize 优先只用文档/版面信号；仅四刊 fixture 证明必要、升格式且用户再次裁决才可纳入元数据，单样本失败先阻断实验。同时明确 `orig` 由哪个持久成员哈希覆盖，不能用给定字符串内部一致代替真实恢复闭包。最小 Read 票交付 Read StageInput、任务/预算/租约/retry、analysis 持久化并决定证据/数值规则身份归属；仅影响后处理警告的变化不应未经分析触发模型重跑。

样本超过单次安全输入预算时，在任何模型调用前拒绝，或前移该样本所需完整分块能力；不得截断全文、丢章节或借用 Screening 会话。实验为显式单篇执行，不扫描自动队列；只有显式人工精读请求不占自动 Read 名额，人工 accepted 后的自动领取仍占。首次引入自动领取即须持久每日配额与重复运行防超额，手动启动 run-due 不构成豁免；每阶段两次 attempt、租约及显式 retry 纪律保持。

## 未豁免条件与证明边界

四刊首轮摘要审计仍先执行；JGR 入口判据在审计前固定为 selected 至少 5 篇，以 A10 矩阵为分母，失败/受阻不剔除，每篇至少一条已交付路线得到非 `suspected_truncated` 的主区块摘要。任一不满足阻断 B 并交回用户；其他刊不足留 C/F 补跑，不代表 A 完成。生产须复用审计版本化规则，或经 `reinterpret_audit` 追加生产解析器解释并审查差异，B 样本本身也须经生产取得完整摘要。B 只用主区块，附加区块留 C 裁决。最迟 D 正式预热冻结/首个校准批次前四刊逐刊证明稳定，四刊阈值与是否一律非截断仍待用户事先裁决，见 [主方案 §4.3/§11](../../intent/draft.md)。

真实 Profile、固定模型及认证、外发确认、合法 PDF、生产 Pi 隔离均不豁免。首次供给目标为 Pi 1.4.0，A8 离线档案不证明生产兼容，A4 1.3.0 spike 不充当兼容证据，未来升级仍走 §7.8。#111 最新评论已确认本机 cwd 为 `/srv/pi-cwd`，白名单仅此常量，无默认值显式提供；无 `.pi/`、AGENTS.md、CLAUDE.md、其他项目资源及实际 OS 隔离仍须在首次发送 prompt 的 live 探测前验证。doctor 对缺失、不符或未验收给出阻断原因。

B 最低路径人工附加合法 PDF，内容验证与版本关联先完成，DOI 检测只产生候选；TDM/授权/渲染及凭据运行时留 F。Docling extra 的安装/兼容验证和样本峰值记录不能替代 F 四刊 fixture/资源门槛。

真实 Profile、配置快照、模型原始响应、正文与证据引文仅留本机验收根并随实验根备份，不进 public 仓库。普通离线测试仅用合成或脱敏材料；许可允许的 PDF/代表页另按 §13.3 审查。本机显式脱网重放单独验收并注明非 CI 范围。必须有反例证明：同份合法分析在实验查询可见，正常消费拒绝，隔离恢复后仍然如此。

证明范围只覆盖冻结样本与纵向链，不证明四刊正文质量、通用 Docling、正常生产 Read、校准或完整阶段 A。阶段责任与历史证据见[路线图](../roadmap.md#module-b)。
