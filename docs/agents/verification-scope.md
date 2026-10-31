# 固定验收范围与集成

## 当前规则

文档分类与信息归属按[文档维护](documentation.md)执行。活文档解绑不改变工作树身份：
改活文档后，历史 run 的 status/reason 保持，当前 applicability 可以是 different。
已发布证据和历史 JSON 保留原字节；新需求或覆盖记录另建文件，不能追溯扩张旧结论。

共享材料仍逐组登记，scope 引用仍传播哈希。只读入口
`./scripts/audit-verification-scope --json` 给出当前材料与下游，`--collect` 仅核对收集数量。
显式 `--base COMMIT --integration-target BRANCH` 核实 base 与本地目标相同且为 HEAD 祖先，
按来源/敏感程度独立列出变化；敏感变化须全部受影响组逐变化确认，基线既有漂移仍失败。
确认文件放在工作树外；HEAD、dirty 树或目标身份改变后须重新审阅，不能复用旧确认。
完整接口与确认字段见[审计契约](../contracts/verification-scope-audit.md#显式基线与分级确认)。
分阶段实施可声明稳定本地 main 为 base/target，但 integration 内子票漂移仍待收口处理。
分类母集与第一步迁移见[迁移台账](../verification/scope-document-migration.md)。

## 单个 spec 的实施与收口

1. 使用 integration 分支和独立 worktree。子票记录实际修改、预期漂移及下游责任，不逐票机械重绑。
2. 收口先归并功能组合回归、文档和新增覆盖台账，完成格式/静态检查，再运行只读审计。
3. 逐条审阅实际修改、基线既有漂移和纯 scope 传播；仅对白名单内实际修改及必要下游按 `order` 重算。记录组、路径、旧/新 SHA 和理由；拒绝无条件接受全部候选。
4. 再跑只读审计（含必要收集）、受影响 pytest 和[触发的兼容组合](testing.md)。完成标准是无未解释漂移、固定分母不减、冻结负例与历史字节符合裁决。
5. 独立审阅及修复完成后提交全部身份约束材料，冻结待验树。完整门禁只按用户明确指令由唯一执行者运行；必须真实退出 0，并查询同 run 为 passed/verified/same。
6. 门禁后改变材料或产生新 merge commit，须重新取得最终树结论。合入 main 应保持已验收提交身份；最终 run_id 留在外部报告，不写回受身份约束材料。

第一步独立收口到 main 后，第二步从实际 main 提交另起 integration 基线。候选审计和开发期组合不代表正式验收。

## 第二步目标与串行点

[#126](https://github.com/MeteoBoy4/PaperRadar/issues/126) 已裁决的目标由第二步落实：共享文件单处中央哈希、取消 scope 逐字节级联，保留显式成员/分母和下游影响图；按显式基线分类机械、敏感和既有漂移。测试/计数、fixture/负例、需求/覆盖与格式、仍绑定契约/证据的变化须每个受影响组确认；source/support 机械哈希变化不逐组确认。

新组机制应使用独立维护的测试预期产物清单，状态读者仍独立声明支持格式；只交付机制，#114/#120 是否转 required 仍由 A 真正收口票决定。显式基线与确认已是当前公共接口；中央登记、取消级联和新组机制仍由后续切片承接。

跨 spec 的第二步规则与自动回归由 #136 承接：后合入者先合并目标，在合并树重算、审阅登记，再跑审计、相关测试与兼容组合。同一登记冲突按合并后字节处理，不能选择任一分支旧哈希；先前门禁不能沿用为合并树结论。

Alembic head、新组注册（机制落地前）、Frozen Contract 新版本和验收基础设施改动须用 GitHub 原生 blocked-by 声明串行点。head 字面量集中另行评估，最迟 Body/B 首个新增 migration 前。完整 A、四刊 live、Pi RPC、模型质量、正式校准、Docling 和 NAS 仍由各自验收负责。
