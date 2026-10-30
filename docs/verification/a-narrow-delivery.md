# A 窄收口覆盖台账

本页登记 #120 新能力的独立工程证据，沿用 #114 先例；不是 A1–A10 历史通过的扩展。
新增测试不加入既有 required 组或历史固定分母，不新增 verification_status 后缀白名单，
不改变「十四份 JSON」承诺及 `stage_a_verified=false`。机器可读新增组与完整 A 结论
在 A 真正收口票（或 #112 之后）建立，B 沿用，子票无需为新增组重绑。

## 用户故事 → 公共接口 → 独立测试 → 未验项

用户故事编号取自 [#120](https://github.com/MeteoBoy4/PaperRadar/issues/120)。
“已验证”只覆盖下列纯规则与调用契约；真实消费面仍按列中责任验证。

| 用户故事 | 公共接口／责任 | 独立测试模块／本次结论 | 未验项／承接 |
| --- | --- | --- | --- |
| US1 | doctor 基础诊断（#124） | 待归并 | 真实环境／Pi/Live/Cwd |
| US2 | doctor 四态诊断（#124） | 待归并 | 真实配置与来源审计 |
| US3 | doctor 原因与下一步（#124） | 待归并 | 真实错误场景 |
| US4 | doctor 显式选择（#124） | 待归并 | 用户历史库，不读取 |
| US5 | doctor 基础与配置缺项分离（#124） | 待归并 | 正式校准 |
| US6 | doctor 阶段 readiness（#124） | 待归并 | Pi/Live、Docling、正式校准 |
| US7 | doctor 数据边界（#124） | 待归并 | 真实模型外发 |
| US8 | doctor 只读（#124） | 待归并 | 现场环境 |
| US9 | doctor 安装与 RPC 区分（#124） | 待归并 | Pi/Live/Cwd |
| US10 | 运行日志任务关联（#123） | 待归并 | B 真实执行 |
| US11 | 三个输出去向隐私（#123） | 待归并 | Pi/Live、真实来源 |
| US12 | 日志落点与保留（#123） | 待归并 | 生产现场 |
| US13 | 日志失败与业务隔离（#123） | 待归并 | 生产故障 |
| US14 | 业务制品与日志分离（#123） | 待归并 | B/C/D/H 真实回查 |
| US15 | evaluate_paper / evaluate_concept：同事实资格与全部原因一致 | test_eligibility.py：全概念两入口、排列不变、矛盾论文隔离、多原因及重复身份已验证 | B/C/D/G/H/I 真实装配与组合 |
| US16 | 人工优先、projection 不生效、系统当前制品/门禁；Read 质量×根用途×执行来源 | test_eligibility.py：五种人工来源、enabled 正例、paused/disabled/unknown 拒绝、D4 十组合及显式请求已验证 | 正式校准、来源真实性、真实 Read、排名/名额/预算 |
| US17 | accepted 的 PDF/提取/Read 独立于参考文献失败 | test_eligibility.py：reference_harvest_failed 合成组合、历史触发新需求、当前失败须 retry 已验证 | E 参考文献生命周期、Body/Docling、真实 Read |
| US18 | A7 applicability、旧人工依据标记、当前 PDF/提取引用链 | test_eligibility.py：历史成功、未知、引用矛盾、后续人工 denied 保留历史且阻止旧请求已验证 | B/C/D/G 当前性装配与真实失效消费 |
| US19 | evaluate_visibility：waiting_calibration/unrevealed OR、部分解除和全部解除 | test_calibration_visibility.py；规则已验证 | C 保留器、D 未揭晓/揭晓、身份/合并链装配 |
| US20 | Visibility.permission：论文事实/任务明细可见，Agent 内容受限 | test_calibration_visibility.py；双向合成材料投影已验证 | B show/trace/最小日报，C/D/H 真实字段裁剪 |
| US21 | 普通 set_decision/reading_request 拒绝；review 为 dedicated_path | test_calibration_visibility.py；合成写入前守卫和受控回执已验证 | B/C/D 普通动作事务前守卫与专用 review 实现 |
| US22 | 会话隔离（#125） | 待归并 | Pi/Live/Cwd，reuse/Read 生产执行器 |
| US23 | D1 独立新测试 + 本台账 + 最终集成同次门禁 | 两个 visibility 独立模块已验证；完整门禁待 #125 | 同次可信 terminal、scope 审计/必要重绑，完整 A 结论未建立 |
| US24 | eligibility / visibility 纯规则边界、支持程度与范围限定 | test_eligibility.py、test_eligibility_architecture.py、两个 visibility 模块；类型投影、AST 纯度/依赖方向、deferred 及 partial 已验证 | B 首接，C/D/H 隐藏、合并链装配，不能推定产品面已交付 |

## I/T/D → 公共接口 → 独立测试 → 未验项

编号原文由[冻结收口表](stage-a-closure.md#原实施逐条处置)维护。

| 编号 | 本轮公共接口／责任 | 独立测试／本次结论 | 未验项／承接 |
| --- | --- | --- | --- |
| I01 | 工程基础与门禁（#125） | 待归并 | 最终集成树完整门禁 |
| I10 | evaluate_visibility、evaluate_paper、evaluate_concept | 四个独立模块已验证；完整 §5.7 仍含下游 deferred，非完整 I10 结论 | B 首消费者、C 保留器与合并链装配，D/E/G/H 后续概念 |
| I11 | 日志与 doctor（#123/#124） | 待归并 | B 真实执行与 Pi readiness |
| T06 | 恢复不变量回归（#125） | 待归并 | 任务续跑与 NAS |
| T07 | 会话机制及映射（#125） | 待归并 | Pi/Live/Cwd，B/D/G 实际消费者 |
| T16 | visibility 许可矩阵及合成内容/动作消费者 | test_calibration_visibility.py；纯规则已验证 | B show/trace/最小日报首接，C/D/H 实际隐藏；不表示全部展示面已隔离 |
| T17 | 单篇/按概念批量求值复用同一判定 | test_eligibility.py：全部概念、多原因、输入顺序与矛盾隔离已验证 | B/C/D/G/H/I 调度与积压真实组合；前置通过不等于获名额 |
| T22 | §8.7 三个输出去向隐私（#123） | 待归并 | B 真实日志；本票不测试日志字段省略 |
| D01 | 最终集成树同次 required 通过（#125） | 待归并；本票未运行完整门禁 | 完整门禁与可信 terminal |
| D03 | doctor 基础与配置缺项区分（#124） | 待归并 | 正式校准、真实模型配置 |
| D04 | D1 已登记；eligibility / visibility 复用纯规则边界 | 四个独立模块及共享 Contract；登记完成，持续约束不算全部通过 | #125 收口；B 起消费者复用与组合验证，I 聚合 |

## 本票验证记录

#121 先执行两个公共行为红绿切片：缺少入口导致收集失败后 1 passed；空隐藏集合恢复
许可的断言失败后 2 passed。补齐 OR 矩阵、双向部分解除/揭晓、合成展示与动作消费者，
以及 AST 禁数据库/网络/模型/Docling/隐式时间/环境/反向 eligibility 依赖的守卫后，
两个独立模块 24 passed；合入集成基线后连同既有 Screening 架构守卫共 27 passed。
CLI compatibility 组合 59 passed；本票四个新增 Python 文件的 Ruff check/format 与
严格 mypy 均通过。只读 scope 审计退出 1：`intent/draft.md` 在 A9/A10 中出现预期
`hash_drift`，登记结构无异常，留 #125 统一审计和必要重绑。本票未运行完整门禁。

D5 的 ADR 门槛评估：任务信息披露不可撤回；无背景会令人意外；全面隐藏与排障可观测性
经过用户权衡，三个门槛均达到，决策见 [ADR-0037](../adr/0037-allow-task-details-during-blind-calibration.md)。

#122 的资格切片从缺少公共入口、最低元数据投影、人工优先、当前制品、PDF/提取、Read
请求、批量/deferred、多缺项、引用矛盾和空身份等红灯逐项转绿。两个新独立模块共 65 项，
覆盖 24 个概念与 59 个资格原因的 Contract。合入最新 integration（含 #124）后，
连同 visibility、Screening 架构、元数据、FeedPipeline、A7 applicability 和
权威原因组合的相关子集 **184 passed in 26.60s**；本票五个 Python 文件的 Ruff check、
format check 与严格 mypy 全通过。Contract 的概念/原因覆盖及两文档的本地链接检查通过。
CLI compatibility 组合 **59 passed in 65.98s**，入口退出 0（总耗时 66.45s）。
本票没有新增 CLI 命令、数据库表、迁移或依赖，未运行完整门禁、live、Pi 或 Docling。
scope 审计退出 1、`issues=[]`：22 项 hash_drift 均来自已合入 #121 的规格与 #124 的
配置/Pi 文件；本票新增资格模块、Contract 和台账没有新增历史哈希漂移，不逐票重绑。
本条不替代 #125 的最终集成审计、真实消费者组合或同次完整门禁。

## 最终集成收口

#125 在集成分支归并后只读审计实际 scope 漂移，解释并仅重绑实际改动材料和传递下游；
不逐票重绑，不修改历史冻结 JSON。审阅与统一修复后在最终集成树运行
`./scripts/check-offline`，必须返回 0 且可信 terminal 证明同次全部 required 结论通过。
退出 0 不能推导任何新增能力结论；实际新增能力由本台账的独立测试与组合证据逐项界定。
提交、run_id、status/applicability 与原始十四份 JSON 指针留收口评论或工作树外台账，
不得将运行标识写回受哈希材料。本票不宣称完整 A 完成。

## 逐项未验证边界

- **Pi**：生产离线启动器、资源/权限、真实成功来源未验，本票未调用 Pi 或模型。
- **Live**：固定 1.4.0 安装与 RPC 兼容未验，fake/合成许可不能替代。
- **Cwd**：`/srv/pi-cwd` 仅已确认，现场资源/权限隔离、DERIVED 与实际参数未验（EXP-2）。
- **四刊审计**：EXP-1/DEC-2、JGR selected ≥5 的真实主摘要判据、四刊稳定阈值及附加区块语义仍归 Audit/Source/C/F/Abstract；未访问网络。
- **Docling**：extra 安装、Python 兼容、模型/样本质量与四刊正文/摘录 fixture 未验（EXP-3/4）；EXP-6/7 仍归 Body/B。
- **正式校准**：保留器、32 篇真实样本、盲评/review/reveal/evaluation 及门禁未验（EXP-5），纯许可规则不构成校准资格。
- **NAS**：恢复与无人值守最终验收未验（EXP-5/I），不能复用历史 A3/Feed 通过代替。
