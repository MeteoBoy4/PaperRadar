# 按首发 Feed 归属派生原题名语言事实

状态：已接受；依据用户 2026-10-27 裁决。本记录补上 [ADR-0031](0031-screening-budget-and-derived-applicability.md)
D1 留下的「生产来源」缺口，不改变其冻结于预算范围、retry 不可更正、不进入 A5 载荷或阶段指纹的结论。

## 背景

value 阶段的 `ValuePredictionContext.original_title_is_zh` 是严格 bool，首次登记即冻结于
同库 `(paper_id, value, fingerprint)` 预算范围；权威校验器只用它决定 `display_title_zh`
是否合法，本身不做语言识别。A1–A10 只证明显式传入严格 bool 的工程边界，从未裁决生产
环境中由谁、依据什么产出该事实。D1 已接受「同预算范围的误标无法纠正」，因此生产者必须
先固定，且必须在产生任何真实 value 任务之前固定。

## 决策

该事实是**来源级约定**，不是逐篇文本判定：由 Paper 的首发 Feed 所属期刊按封闭表决定，
不由题名、字符集、语言检测器或模型判断。

| 首发期刊 | `journal` key | Feed | `original_title_is_zh` |
| --- | --- | --- | --- |
| 《大气科学》 | `dqkx` | `https://www.iapjournals.ac.cn/dqkx/rss/current.xml` | `true` |
| Artificial Intelligence for the Earth Systems | `aies` | `https://journals.ametsoc.org/journalissuetocrss/journals/aies/aies-overview.xml` | `false` |
| Journal of Geophysical Research: Atmospheres | `jgr` | `https://agupubs.onlinelibrary.wiley.com/action/showFeed?jc=21698996&type=etoc&feed=rss` | `false` |
| Quarterly Journal of the Royal Meteorological Society | `qjrms` | `https://rmets.onlinelibrary.wiley.com/feed/1477870x/most-recent` | `false` |

- 键是首发期刊（Feed 端点身份），不是 URL 字符串、DOI 前缀、出版者或标题文字；同一刊
  新增 Feed（例如《大气科学》`latest.xml`）沿用该刊取值，但该 Feed 是否纳入发现范围仍
  按主方案 §2.1 另行裁决，本表不自动扩大订阅。
- `false` 只表示「非中文」，不声称英文；该字段不表达其他语言，也不需要其他取值。
- 没有首发 Feed 归属的 Paper（仅经人工 DOI、URL 或 PDF 加入）没有该事实：不得默认
  `false`，也不得为其登记 value 任务，直到另行裁决。
- 归属由 Paper 的 Feed 发现事实确定。先经人工入口加入、后由 Feed 发现时，Feed 归属确立
  后可登记；已冻结的预算事实不因来源后到或映射变化改写。
- 登记入口仍要求调用方显式提供严格 bool；本裁决规定调用方必须按本表填写，不新增检测器、
  默认值或宽化接受。从 Feed 归属自动派生、策略版本持久化与任务登记集成由后续生产接线票交付。
- 映射以版本标识表达（当前 `v1`）。更换映射是新版本：只影响之后登记的 value 任务，不追溯
  改写已冻结事实、请求审计或历史任务。策略版本如何持久化由生产接线票决定，不进入 A5 载荷
  或阶段指纹，也不成为 Frozen Contract。
- 已知风险：这是刊物原始题名语言政策的来源假设，不是逐篇核验。反例（非《大气科学》Feed
  出现中文原题名，或《大气科学》出现非中文原题名）必须以新裁决和新策略版本处理，不能由
  检测器静默修正；取值错误在同预算范围仍然不可纠正。

## 后果

- value 任务不再被「来源未裁决」阻塞，但生产接线（派生、策略版本、登记集成）尚未交付，
  也未验收；A7/A8 的 not_assessed 项因此更名为 `original_title_language_production_wiring`。
- 不新增持久化字段、migration、Frozen Contract、依赖或语言检测；boundary 仍禁止该字段，
  Paper、Screening、校准语义和现有离线证据不受影响。
- 文档与 scope 绑定在同次变更中同步；历史 review、验证结论和已发布证据不重写。
