# 固定验收范围与集成

本文件是单 spec、跨 spec 集成和共享登记资源串行规则的唯一权威。文档分类与信息归属见
[文档维护](documentation.md)，审计字段和受控拒绝见[审计契约](../contracts/verification-scope-audit.md)。

## 材料与证明边界

- 活文档按精确路径分类解除整文件历史绑定，未知文档仍按固定材料处理。history、需求/覆盖台账、冻结摘录、ADR、Schema、代码、测试、fixture 与依赖身份继续固定。已发布证据和历史 JSON 保留原字节；新增需求或覆盖另建台账，不追溯扩大旧结论。
- 全部跨两个及以上组实际登记的共享材料在 `scripts/verification_scope_materials.py` 单处维护哈希；各组显式保留成员、用途和固定计数。单组材料保留字面量，中央引用与字面量兼容，同组重复仍拒绝。
- scope 通过 `REQUIRED_SCOPE_REFERENCES` 保留显式 DAG；scope 与中央文件不进入组内整文件哈希，由结构审计、实际材料字节和完整工作树身份保护。当前旧 scope 哈希边已全部移除，实际为零哈希边、41 条显式 refs；计数口径和逐边清单见[共享迁移台账](../verification/scope-shared-dag-delivery.md)。不恢复机械 scope 级联。
- 活文档也参与工作树身份。旧 run 的 status/reason 保持，当前 applicability 单独计算；新 merge commit 即使文件树相同，也不能沿用旧门禁作为当前树结论。开发审计、候选与组合测试均不代表正式验收。

当前集中登记与一次性新组准备的完整消费闭包、D1 模块及物理维护行数见
[集成台账](../verification/scope-registry-integration.md)。其审阅授权只描述具体材料变化；
后续执行者仍须绑定本次最终 HEAD、target 和完整工作树身份，不能复用候选确认。

## 基线、候选与 S3 确认

1. 先记录实际 HEAD、dirty 状态和本地目标分支；以目标当前 commit 作为显式 `--base`，声明 `--integration-target`。base 必须等于本地目标且为 HEAD 祖先；目标移动、旧 merge-base 或非祖先均先重新集成再分析，不隐式 fetch。分阶段实施可声明稳定本地 main 为 base/target，但 integration 中的子票漂移仍交收口处理。
2. 运行只读 `./scripts/audit-verification-scope --json`；显式基线分析加上 `--base COMMIT --integration-target BRANCH`，需要核对固定分母时加 `--collect`。分别审阅 current_change、baseline_drift 与机械/敏感分类；基线既有漂移必须单独解释和处理，本轮确认不能清掉它。
3. 审阅每条候选的实际字节、登记用途、旧新成员/计数/格式和全部直接及下游组。source/support 机械哈希变化不逐组确认；测试成员与计数、fixture/冻结负例、需求/覆盖台账与格式、仍绑定契约/证据，以及分类控制数据新增或改类，按 S3 逐具体变化、逐全部受影响组确认。
4. 确认精确绑定 base、HEAD、本地 target ref/commit、完整 dirty 树摘要、group、path、origin/category、旧新文件及 entry 摘要，并记录非空审阅理由；字段定义见审计契约。确认输入放在被审计树外。HEAD、目标或任意未忽略材料变化后，重新审阅并生成对应身份的确认；旧确认不复用。
5. 候选仅供审查；确认只解除 confirmation_required，不能消除 hash_drift 或授权写回。只按明确白名单重算实际改动及必要登记，记录组、路径、旧/新 SHA 和理由，再审计。中央变化不得掩盖成员、分母或用途变化。

## 单个 spec 的实施与收口

1. 使用 integration 分支和独立 worktree。子票记录实际修改、预期漂移及下游责任，不逐票机械重绑。独立 worktree 仍需处理语义冲突。
2. 收口先完成实际消费者的功能组合回归，再归并文档与新增 D1 覆盖台账，完成格式及静态检查。独立未绑定模块逐个登记数量，不把全量 pytest 退出约束当作进入历史回执或扩大 required 集合。
3. 执行上面的基线审计与 S3 审阅，只对必要白名单精确重绑；审计器/解释器自身旧绑定也须记录和解释。新增消费闭包单列，既有迁移的展开等价和历史证据保持。
4. 再跑审计（含必要收集）、受影响 pytest 和[触发的兼容组合](testing.md)。完成标准：无未解释漂移，固定分母不减，skip/deselect/incomplete 不算通过，冻结负例及历史字节符合裁决。
5. 独立审阅及修复完成后，提交全部身份约束材料，冻结待验树。完整门禁只按用户明确指令，由唯一执行者运行；实际退出 0 后查询同 run 为 passed/verified/same。
6. 门禁后改材料或产生新 merge commit，重新取得最终树结论；合入 main 保持已验收提交身份。最终 run_id 留在外部报告，不写回受身份约束材料。

## 跨 spec 合并

1. 后合入者先合并当前目标分支，处理真实业务及登记语义冲突，完成后重新确定 base/target。两边旧树的检查不能替代合并树检查。
2. 不相交材料保留双方有效登记，无需拿一方旧哈希覆盖另一方。同一共享文件或登记被双方修改时，按合并后实际字节重算并审阅；不选择任一方 SHA 作为成功依据。
3. Git 自动合并或人工解决文本冲突后，先检查合并树的真实登记。失效候选仍须失败；实际重算后，敏感变化满足上面的全部 S3 确认才可通过。冲突已解决不是验收成功判据。
4. 在合并树重跑只读审计、受影响 pytest，以及按变更类型触发的 `check-compatibility`；然后继续单 spec 收口的无漂移、审阅、冻结与授权门禁步骤。需要当前正式结论时，在最终树按用户指示重跑唯一完整门禁。

## 共享资源串行与后续承接

以下串行点用 GitHub 原生 blocked-by 表达对同一登记资源的写串行，只给实际争用资源的票加边：

- Alembic head：新增 migration 保持线性顺序。
- 新验收组注册：旧机制阶段串行；新机制落地后仍核对实际共同改动的 registry、测试预期或读者支持表。
- Frozen Contract 新版本：同一格式/版本登记的并发修改先确定顺序。
- 验收基础设施：共同改动入口、receipt、writer、读者或审计边界时提前明确集成顺序。

这些边不是业务功能依赖；不新增 Scope 模块，也不把 B/Body 依赖到 #126。机器可读新组机制与
实际 required 纳入分开，#114/#120 是否及何时转 required 仍由 A 真正收口票决定。

S5(a) 的 head 字面量集中化由 [#138](https://github.com/MeteoBoy4/PaperRadar/issues/138) 另行评估；
Body/B 首个新增 migration 票须在实施前核实该评估承接与结论，并按当时规则登记串行关系。
本规则不实施 head 集中化，不新增 migration，也不改变 Frozen Contract 已登记版本。
完整 A、四刊 live、Pi RPC、模型质量、正式校准、Docling 和 NAS 继续由各自验收负责。
