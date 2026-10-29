# JGR Feed parser v1 固定回归边界

生产身份 `jgr-feed-parser-v1`、版本 1；这是首次生产交付，无旧生产版本可比较。
共享审计身份提取、RSS/Atom/RDF 顺序规则和主摘要/截断规则，不改旧审计解释。
新增生产差异仅为：完整遍历（不限前50项）、真实单item字节范围、受控Wiley落地页path
提取、逐item错误回查及向PaperFacts提交。审计候选模型和默认前50项上限保持原行为。

| 关键字段 | 固定合成材料预期 | 与旧审计解释的关系 |
| --- | --- | --- |
| 题名 | `Original title`；实体解码 `Exact & title` | 同一主摘要解析器的title规则 |
| 主摘要 | 非截断的完整英文句子；不拼接附加区块 | `audit-abstract-v1` / `audit-truncation-v1` |
| DOI | 裸DOI/显式DOI沿用严格规范；Wiley `/doi/abs/10.1029/2025JD043927` → `10.1029/2025jd043927`；query不产生DOI | 显式DOI与审计一致；新增独立受控path提取 |
| entry ID | 原 `entry-1`、`odd`；缺失则不制造ID | 与审计上游ID规则一致 |
| 类别 | `Editorial`、`prism:section=Letter` 原样保存 | 与审计一致，不预过滤 |
| 原字节 | 含属性中的 `>`、实体、继承前缀、空标签和原结束标签 | 审计不提供该生产字节切片 |

固定材料与公共断言保存在 `tests/test_feed_ingestion.py`。共享审计回归继续独立执行。
这些材料均为合成，不是本轮来源审计；未增加A6/A10历史分母或live证明。

后续parser升级须固定旧材料、保留旧身份实现并登记新版本；逐项列出题名、主摘要、DOI、
entry ID、类别的增加、减少及原因，检查完整解释与全空保护。真实材料差异复核由EXP-1/B
补齐，不能以本页合成预期代替。不得用新parser回写旧检查/解释。
