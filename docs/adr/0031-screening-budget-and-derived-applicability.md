# 以 Paper 阶段输入承载预算，并派生筛选制品当前适用性

状态：已接受；日期：原记录未单列；依据：[基线裁决原文](https://github.com/MeteoBoy4/PaperRadar/blob/91e5d02e199f1921ca8afd2b7bdb8f257e6264f3/docs/adr/0031-screening-budget-and-derived-applicability.md)；补充／部分取代：[ADR-0035](0035-feed-derived-original-title-language-fact.md)。

原状态与裁决依据：已接受；依据 [#76 用户 D1–D4 裁决](https://github.com/MeteoBoy4/PaperRadar/issues/76#issuecomment-6356409213)；日期：原记录未单列；补充：[ADR-0035](0035-feed-derived-original-title-language-fact.md)（2026-10-27 原题名语言生产来源）。

预算与筛选制品的主体固定为同库 `(paper_id, stage, fingerprint)`，不同 Paper 不共享业务结果或次数，日期、版本 ID、请求来源、代际与配置标签都不进入 A5 语义载荷。这样输入回摆会回到既有预算；代价是将来论文合并必须另外决定预算合并，不能直接跨 Paper 复用。

当前适用性完全由明确历史 snapshot 下当前论文输入的指纹与筛选制品指纹比较派生。同指纹跨版本直接适用（current），映射成功而指纹不同为 historical，缺项等映射失败为 undeterminable 并保留 PaperReason；没有结果使用依据表、再绑定写入或提交事务中的当前论文复核。这取代 #76 原故事 29/31、决策 15–16 及缓存重新绑定测试，并按用户裁决同步主方案 §8.5，消解其旧字面读法与 §3.4/4.4 的张力；请求自己的 version/revision/snapshot 与命中回执足以保留使用审计。

D1 将原题名语言严格 bool 冻结于预算范围，不进 A5 指纹，retry 继承且不能更正；代价是误标暂无法纠正，真实 value 任务前必须另行裁决生产来源（已于 2026-10-27 裁决为首发 Feed 归属，见 [ADR-0035](0035-feed-derived-original-title-language-fact.md) 及状态行补充关系）。D3 在原权威验证器拒绝任意层重复键及非有限 JSON 常量，保持单一 Schema 和业务接收权威。D4 推迟 CLI 和 paper trace 组合，交付服务层查询/retry，使未来生产调度决定实际产品交互。具体规则与仍未交付的生产边界见[任务 Contract](../contracts/screening-tasks.md)。

## 补充裁决

依据：[#80](https://github.com/MeteoBoy4/PaperRadar/issues/80)，2026-10-23。

派生映射复用 PaperFacts 独立只读一致视图，允许相对任务事实读取滞后；登记时命中引用持久化于请求，旧回执不被后续成功改写。成功发布与业务写事务分开，竞争失败允许完整未引用响应，生产消费者必须拒绝 test 来源。

依据：[#81](https://github.com/MeteoBoy4/PaperRadar/issues/81)，2026-10-23。

接收与恢复都从预算首次历史 snapshot 经 A5 严格回放及投影核对、value_prediction_context 到 A1 权威验证，不以当前主题或新请求配置替换。没有新增表、语言检测或两阶段编排；语言误标的限制仍按 D1 保留。


依据：[#82](https://github.com/MeteoBoy4/PaperRadar/issues/82)、[#83](https://github.com/MeteoBoy4/PaperRadar/issues/83)、[#84](https://github.com/MeteoBoy4/PaperRadar/issues/84)，2026-10-23。

结论登记与 `.a7.json` 格式 1 的状态支持采用同提交绑定，以固定源码/材料/分母、真实
pytest 回执和同次身份防止遗漏或历史成功补位。任务查询/原因格式单独固定，不扩大
四份 Frozen Contract；scope 不自绑定，最终运行标识保存在工作树外以免自哈希循环。
离线 test 来源的工程证明不能代替真实 RPC、语言事实的生产接线、完整资格、生产筛选或校准。

生产来源决策及 D1 不变边界见状态行所链 ADR-0035；从 Feed 归属自动派生、策略版本持久化和任务登记集成的承接责任见[路线图 Feed](../roadmap.md#module-feed)。
