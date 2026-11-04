# #157 Read v2 纯接收 D1 覆盖

依据：[#157](https://github.com/MeteoBoy4/PaperRadar/issues/157)、[#155 最终裁决链](https://github.com/MeteoBoy4/PaperRadar/issues/155)、[ADR-0042](../adr/0042-accept-read-v2-with-final-attempt-degradation.md)。

独立 seam 是“完整原始候选 + 合法 ReadContext + 任务层策略/本代序号 → v2 接收结果或安全拒绝”。
测试只调用公共入口；Docling、模型和任务预算不在本票实现中。

## 测试模块与数量

| D1 模块 | 完整节点数 | 覆盖 |
| --- | ---: | --- |
| `tests/test_read_acceptance_v2.py` | 42 | 顺序、首次/末次、评分理由、全空下限、条目丢弃、reduce 范围、警告、安全输出、序号与上下文 |
| `tests/test_read_acceptance_v2_compatibility.py` | 26 | 两版共同行为、受限内容差异、从零重算清单与禁 extra/网络/SQLite 的冷进程 |
| 合计 | 68 | 全部独立未绑定 D1 节点；不进入 A9 或其他历史固定分母 |

不修改 A9 v1 源码、`reading/__init__.py`、15 个冻结测试模块、scope 计数、规则格式或
中央材料哈希。ADR-0010/0025 只改状态行增加部分取代回链；相应固定材料漂移交由
Body 收口按 S3 审阅，只对必要白名单处理，不机械重绑历史范围。

## v1 ↔ v2 差异矩阵

| 场景 | v1 | v2 |
| --- | --- | --- |
| 严格 JSON、UTF-8、重复键、非有限数、非对象、尾随垃圾 | 整份拒绝 | 相同；复用冻结 parser |
| 字段闭集、必填、严格类型、1..5 评分 | 整份拒绝 | 相同；复用冻结 Schema |
| 文本、语言、价值类型条件/重复 | 整份拒绝 | 相同；完整候选先检查，丢弃不能掩盖 |
| 空 evidence / 空字符串 ID | Schema 整份拒绝 | 相同，末次也不能丢弃掩盖 |
| 两项评分理由有业务坏指针 | 整份拒绝 | 相同，任何序号均整份拒绝，必填单值没有列表项丢弃语义 |
| 非末次列表项有非法/重复/未知指针 | 整份拒绝 | 相同，任务层可据安全路径要求修正 |
| 末次列表项有非法/重复/未知指针 | 整份拒绝 | 丢弃整条；可复用点的 item/how_to_reuse 一起丢，不修复、不去重或保留好引用 |
| 同一坏 ID 被多个列表项引用 | 整份拒绝 | 末次各条分别丢；合法其他条目保留 |
| main_findings/reusable_points 因丢弃同时清空 | 原指针错误整份拒绝 | `$ [output_without_support]`，任务层归 output_invalid |
| 主体原本合法为空 / 仅清空局限 | 合法空列表可接受 | 相同；局限清空只产生丢弃事件，不触发下限 |
| 合法公式/不可靠源块 | 主要发现/评分理由/可复用点硬失败 | 所有保护字段只产生 restricted_source_reference 警告 |
| 表格结构描述 / 数值仅受限命中 | 结构允许；关键字段受限数值硬失败，局限只警告 | 结构允许；所有保护字段受限数值只警告 |
| 数值未命中、范围/单位不支持、未知数值形状 | 警告 | 相同诊断语义；v2 模板不带触发字面量 |
| 候选/占位/生成文本 ID | 不存在 evidence 时整份拒绝 | 仍无证据资格；按 unknown_evidence 分首次拒绝/末次丢弃，绝不创建源或修复引用 |
| unknown_source / 身份/页面/bbox/charspan/空切片 | 上下文错误 | 相同，完整重验；领取前检查，不作为 output_invalid（父评论 3 的遗漏由评论 4/5 补回） |
| evidence_not_allowed / 业务 evidence_required | 仅 reduce 范围问题整份拒绝 | 同样仅 reduce；末次三类列表项可以丢弃，评分理由仍整份拒绝。single 不出现（父评论 3/5 的范围澄清） |
| 模型自报序号 | Schema 额外字段拒绝 | 相同；不能覆盖任务注入参数。执行器包装层的序号声明由执行组合忽略 |
| 警告/丢弃与序号 | v1 记录独立保留 | v2 带 final_attempt、{1,2} 与三版本；新代序号 1 不继承旧代丢弃许可 |
| 历史接收 | read-evidence-v1/read-numeric-v1 | 不改写 v1 记录，不追溯制造 v1 失败分析；v2 在独立模块直接导入 |

## 重算与隐私依据

重算测试使用独立字面量丢弃清单，不由生产输出生成预期；同候选、重新构造的上下文、
策略、序号及三规则版本重复计算后，逐字段比对 location/item_category/ordinal/reason/positions。
冷进程重新读取候选并构造完整 Context，同时回放 v1 历史接收和 v2 接收；导入哨兵拒绝
Docling/core/Torch/Transformers，沿用 socket/SQLite 拒绝守卫，不访问真实来源。

丢弃后只对保留条目计算数值与受限内容警告，路径仍引用原候选索引。测试覆盖坏 ID、
模型警告、数值与原文不经 repr/异常/诊断外泄；错误转换不保留含输入异常链。
位置只来自可解析的合法源；unknown/invalid ID 不另存字符串或虚构页码。

## 验证与未验范围

开发验证使用 `uv run --offline --locked pytest` 的本票与相关 Read 子集，以及新增文件
Ruff/mypy；最终结果在本票交付报告中记录。上述数量是独立覆盖清单，不是完整门禁结果。
`stage_a_verified=false`，不扩大 A1–A10 历史结论，不更新历史回执。

本票不运行完整离线门禁或 live，不实现持久任务、analysis 登记、备份恢复、Pi 执行、
自动队列或 map/reduce。持久消费者须保存并重算同一候选、Context、策略、序号、版本和
丢弃清单；备份按历史证据版本分派并处理 unsupported_rule_version，清单不符为
registration_invalid。模型指纹/预算测试与真实组合由后续 Body 消费者承接。

EXP-6 的真实父源块统计、逐字 orig 保真和缺口类别、Docling smoke、四刊质量、真实 Pi、
B 当轮闭环仍独立验证。B/H 必须显著展示未核对警告和丢弃计数；纯层通过不授予生产资格。
