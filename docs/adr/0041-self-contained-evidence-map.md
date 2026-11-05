# 以自包含 evidence-map 覆盖源字符并恢复正文消费上下文

状态：已接受；依据：[#155 评论 2](https://github.com/MeteoBoy4/PaperRadar/issues/155#issuecomment-6631023698)、[评论 3](https://github.com/MeteoBoy4/PaperRadar/issues/155#issuecomment-6631829133)、[评论 5](https://github.com/MeteoBoy4/PaperRadar/issues/155#issuecomment-6632720328)、[#156 补充](https://github.com/MeteoBoy4/PaperRadar/issues/156#issuecomment-6634181256)；日期：2026-11-04；补充：[ADR-0027](0027-address-artifacts-by-content.md)、[ADR-0036](0036-isolate-stage-b-read-experiment.md)；验证依据：[真实 SDK 来源、未知类别公式父源块与无 extra 隔离回查](../verification/issue-164-docling-smoke.md)。

## 背景

正文消费身份已冻结为 `(extraction_fingerprint, reading_sha256, evidence_map_sha256)`，
但仅有给定字符串的 ReadContext 不能证明源字符已经持久保存。若恢复依赖 DoclingDocument
SDK 或原运行目录，无 extra 的基础环境无法逐字回查；增加角色或更换身份又会破坏既有消费者。

## 决定

`evidence-map.json` 自包含页面、原始 orig/text、源类型/可靠性、层级与全部 provenance，
由 evidence_map_sha256 覆盖原始源字符。document 成员仅供审计，不参与上下文重建。
恢复按明确三元组校验成员，在无 Docling SDK 的新进程重建既有 ReadContext；同指纹不同内容
仍是不同正文，不接受裸 ID 串用。

复用 extraction 四角色与 store 格式 1。reading/evidence_map 不回写三元组的最终哈希，
先生成成员再计算哈希，manifest 保存三元组、审计成员哈希和配置身份，但不写自身最终哈希。
固定编码与源块粒度/序号规则见[正文 Contract](../contracts/fulltext-extraction.md)。

公式候选、占位和生成展示不能取得 evidence ID；只有具有逐字 orig 与完整 PDF provenance
的父源块可被引用。按行间/行内/未知记录总数、可回放父源块数和仅占位数量，并记录 map 体积。
合成统计不推定真实覆盖；smoke 的真实分类与能力上限须明确登记。首次真实 B 制品之后的
normalization 语义变化必须升版本，不能覆盖历史。

## 代价

evidence-map 比仅保存定位索引更大，并与 document 保留部分重复内容；换取无 SDK 的持久回查。
它证明已保存源字节与定位的一致性，不能独自证明 parser 对真实 PDF 的保真或各刊覆盖。
公式无父源块的类别仍不能提供 evidence，不能用生成候选或新制品角色绕过。
