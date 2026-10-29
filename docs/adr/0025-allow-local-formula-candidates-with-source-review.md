# 允许局部公式候选转写并保留源证据核查

状态：已接受；日期：2026-10-10；依据：[基线裁决原文](https://github.com/MeteoBoy4/PaperRadar/blob/91e5d02e199f1921ca8afd2b7bdb8f257e6264f3/docs/adr/0025-allow-local-formula-candidates-with-source-review.md)；补充／部分取代：无另列关系；正文边界继续适用。

2026-10-10 用户在 Issue #20 实施时明确允许并默认启用 CodeFormulaV2 局部公式候选转写，依据 `intent/discussions/docling-issue-20-live-probe.md` §7.4 第 1–2 项：初始采用 Egret medium 原生文本链，公式增强能改善独立公式的可读性，但实测仍有字符错误，不能承诺精确恢复。本决策取代 ADR-0010 中“公式增强关闭、公式只保存占位”的限制；Docling 单一正文解析器、CPU、单论文串行、OCR/代码/图片/图表增强/远程与外部插件关闭及表格结构开启继续适用。

启用公式候选时冻结 CodeFormulaV2 的 commit、全部推理文件哈希、Transformers/float32 和裁切扩展策略；可以显式关闭并省去未使用的公式模型身份。后续 parser/canonical 制品必须分别保留原始 orig、候选转写、原 PDF 页码/bbox/源 charspan，提供 PDF 裁切人工核查；生成 LaTeX 不冒充原字符区间，也不得在未复核时支持主要发现、评分或复用建议。未检出或不能可靠转写的公式继续提供定位占位，行内科学符号、表格和扫描稿不因该能力被视为已修复。

#20 只交付配置登记与回放，不执行公式增强或裁切，不宣称四刊 fixture gate、确定性或资源检查通过。解析实现前必须将源/候选分离、裁切回查、转写失败降级与中英文 fixture 纳入质量门槛。工具链、模型、策略或 normalization 改变仍是独立 extraction 配置语义变更，后续校准流程由用户按 ADR-0020 分级，保存快照本身不启用自动精读。
