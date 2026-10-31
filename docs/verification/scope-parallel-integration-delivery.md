# 跨 spec 集成独立覆盖台账

依据：[#126](https://github.com/MeteoBoy4/PaperRadar/issues/126) 的 S3(b)、S5(a)、S7(c)、S8(a)
及 [#136](https://github.com/MeteoBoy4/PaperRadar/issues/136) 的合并场景裁决。
本文件登记新增 D1 覆盖；不修改历史证据、既有 required 集合或任何组的固定分母。

## 独立测试模块

| 模块 | 用例数 | 接缝 | 覆盖能力 |
| --- | ---: | --- | --- |
| `tests/test_scope_parallel_integration.py` | 7 | 临时 Git + 公开 `audit_baseline` / `query_status` | 不相交中央登记保真；共享 fixture 自动/人工文本合并后的失效候选、真实字节重算及全部 S3 确认；target 移动、非祖先、过期 merge-base 拒绝；相同文件树的新 merge 身份与历史适用性分离 |

该模块未绑定到历史组，`required=false`。测试使用固定本地提交、独立 Git 配置与 `/tmp`
材料；不访问远端，不修改真实 main。审计保持只读，哈希重算仅在测试控制的合成登记内进行；
历史协议场景只调用状态读者，不调用正式入口、控制方或发布器，不产生正式 run。

## 不可降低的断言

- 不相交合并保留两方已审阅中央哈希，目标现有登记无需被旧分支覆盖。
- 共享材料合并完成后仍按实际字节审计；确认不能消除 hash_drift，重算后确认缺口仍失败。
- S3 确认逐变化覆盖全部直接及 DAG 下游组，entry 语义变化也纳入；重算前确认因身份/entry 变化失效。
- 无效基线受控返回明确原因，不返回可消费的 baseline 候选。
- 历史 status/reason 与 JSON 原字节保持；新 merge commit 的 applicability 独立判断，文件树相同也不能沿用旧结论。

## 规则与承接

项目唯一集成规则在 [verification-scope](../agents/verification-scope.md)，其余 Agent 指南只做触发导航；
它同时承载单 spec 顺序、跨 spec 合并、分级确认、冻结历史和实际共享资源的原生 blocked-by。
全部共享材料单处中央登记，scope 零逐文件哈希、实际 41 条显式 refs 的既有迁移事实见
[共享迁移台账](scope-shared-dag-delivery.md)，本票不改写其冻结记录。

S5(a) 的 head 集中化另由 [#138](https://github.com/MeteoBoy4/PaperRadar/issues/138) 评估，
由 Body/B 首个新增 migration 票在实施前核实承接与结论；本票不实施 head 集中化。
S7(c) 不新增 Scope 模块或 B/Body 功能依赖；#114/#120 是否转 required 仍由 A 真正收口决定。

最终统一集成须在合并树复核 #135 与本票组合，归并 D1 覆盖，审阅实际漂移和必要确认后再冻结待验树。
完整门禁仅由已获授权的唯一执行者运行；开发期结果不能替代该结论。
未验证四刊 live、Pi RPC、模型质量、正式校准、Docling、NAS 或完整阶段 A。
