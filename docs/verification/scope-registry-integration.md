# Verification Scope 第二步集成候选台账

本台账归并 #132–#136 的实际实现、D1 覆盖与 #137 必要重绑。
基线是第一步已收口的 `e6c1ec74c9fc8d15fc8f76d2c8a7b29fcdda9438`；
集成输入为 `01157728ca6ba1a00ebddf3d94f9910cdb915fc6`。
[机器台账](scope-registry-integration.json)保存精确旧新 SHA、消费组、entry 摘要、
逐路径审阅理由、计数与冻结字节；它不发布正式离线结论。

## 登记与历史边界

- 现有 11 组中 10 个 required，A2-01 optional。当前 1203 条展开登记、695 个路径；
  285 个固定测试模块、5281 个去重用例不减，不把新增 D1 模块塞入旧回执。
- 全部共享材料中央登记 255 路径：#134 的 252 路径加 #135 的 3 条实际新数据路径
  （生产声明、独立人工预期与其读取支撑）。各组成员、用途、分母继续显式维护。
- scope 哈希边为 0，原 41 条逐边保留为显式 refs；41 是按实际 Scope.path 重算的数量。
  旧票面及第一步冻结证据中的 42 不追溯改写，口径说明见[共享迁移台账](scope-shared-dag-delivery.md)。
- #134 迁移时物理共享 SHA 位置为 644→252，减少 392；另移除 41 条 scope SHA。
  735 是逻辑共享成员资格，含复用元组，不能当作实际编辑位置；新增三条数据后中央为 255。
- 第一步六个冻结 scope/审计模块字节全同；其清单与 SHA 保存于机器台账。
  第一步与 #132–#136 所有既有 `docs/verification/`、历史 JSON、ADR 正文均保留原字节。
- A10 覆盖文件与第一步逐字节相同：693 ID、37 来源及 SHA 保真；处置仍为
  covered 546 / operational 111 / not_assessed 29 / superseded 7。
  `A10-100-C6405695568-CLAUSE-037` 保留真实历史缺口，不追认完成。
- 业务源码、Stage fingerprint、Schema、migration 和状态读者源码/格式支持表未变。
  不新增 Scope 模块或 B/Body 功能依赖；#138 仍承接 head 字面量集中化评估。

## 必要重绑与 S3 审阅

最终输入有 60 个 hash_drift 成员、19 条实际 Git 变更路径。先完成格式和静态检查，
逐路径审阅子票实现与一次性准备，再核对当前文件 SHA、登记旧 SHA、登记位置和全部消费组，
只改 11 个中央 SHA 与 8 个组独有字面量；无 scope 哈希传播。
机器台账的 `rebindings` 是封闭白名单，未知路径、旧 SHA 或新字节必须重新审阅。

显式基线有 34 个变化，其中 26 个敏感变化需要 144 条逐变化、逐全部影响组确认。
`sensitive_review_authorizations` 分别记录 11 个 scope、10 个准备测试、生产声明、
审计 baseline/collection 支撑以及两份独立预期 fixture 的旧新文件/entry 摘要、类别、
直接/传递影响组和具体理由。中央化不掩盖 source 新成员、fixture、测试、refs 或格式变化。
#133 的 5 个新增 source 成员与 #135 的 28 个新增成员用途单列；旧迁移展开等价不含这些新增闭包。

本台账描述审阅对象，不是可复用的确认文件。确认输入位于树外，精确绑定当前
base/HEAD/target/dirty 整树身份；任何材料或 merge commit 变化后重做身份确认。
确认只解除 `confirmation_required`，hash_drift 必须先实际重绑。
本候选默认与显式（含 collect）审计的最终结果由树外报告保存，正式 run_id 也只存树外。

## 一次性 S4(b) 与独立覆盖

10 个已绑定模块保持原 78 例：`test_a2_full_entry` 7、`test_a4_entry` 5、
`test_a5_entry` 5、`test_a6_entry` 9、`test_a7_entry` 9、`test_a8_entry` 9、
`test_a9_entry` 10、`test_a10_entry` 10、`test_verification_run` 5、
`test_verification_compatibility` 9。一次性迁移 12 处总份数断言和 1 处帮助断言；
独立预期同时检查后缀集合和数量，原历史 stdout/stderr/退出码、检查数、失败和中断前缀保留。
帮助 fixture 复制轻量声明并保留 socket/SQLite 哨兵；旧模拟 executor 的成功 fixture
与新目标真实 pytest 计数分开，不能补造真实执行证明。
逐模块旧新字节和原因见机器台账及[准备台账](scope-extensible-groups-delivery.md)。

| 第二步独立未绑定模块 | 实际收集 | 能力 |
| --- | ---: | --- |
| `tests/test_scope_baseline_audit.py` | 34 | 显式基线、独立历史树、分级确认及身份失效 |
| `tests/test_scope_central_registration.py` | 17 | 中央静态语法、展开、真实漂移与用途 |
| `tests/test_scope_shared_dag.py` | 24 | 零 scope hash、显式图、writer 指针与 AST I/O 守卫 |
| `tests/test_extensible_acceptance.py` | 22 | 真实合成组执行/计数/回执/发布/终态与帮助边界 |
| `tests/test_scope_parallel_integration.py` | 7 | 不相交与冲突合并、失效候选、目标新鲜度及历史身份 |
| 合计 | 104 | 均 required=false，不增加历史分母 |

第一步 6 个独立模块仍为 93 例（4+23+18+27+4+17）。第二步对普通未绑定兼容测试与
支撑的必要适配另表记录旧新 SHA 和理由，保留强集合、图、历史展开及分母断言；
原阶段台账不改写为新结果。

## 同场景实际维护行数

比较单位统一为登记文件中**实际新增/删除/修改的行数**，只替换具体 SHA；
场景以 e6 与当前完整副本分别修改同一材料的一条注释，并在实际图的拓扑顺序重算必要登记，
最终公开审计均 exit0。原材料修改、语义审阅/逐组确认、业务实现及新组自己的登记不计入哈希维护。
每个副本的逐登记文件计数与作用组见机器台账的 `maintenance_scenarios`。

| 同一场景 | e6 新增/删除/修改 | 当前新增/删除/修改 | 当前直接/额外下游组 |
| --- | --- | --- | --- |
| `README.md` 活文档 | 0/0/0 | 0/0/0 | 0/0，仍影响整树身份 |
| `src/paper_radar/cli.py` | 0/0/40 | 0/0/1 | 7/3 |
| `tests/test_boundary_validation.py` | 0/0/42 | 0/0/1 | 2/8，测试变化仍敏感 |
| `scripts/a1_scope.py` | 0/0/41 | 0/0/0 | 1/9，结构变化仍审阅 |
| `scripts/check-offline` | 0/0/43 | 0/0/1 | 10/0 |

A1 测试的旧 2 个逻辑资格复用同一 tuple，只有 1 个物理材料 SHA，故实际为
1+41=42 行，不以 2+41=43 混算。CLI 的旧 40 行为 7 个直接 SHA 加 33 个下游 scope SHA。
当前所有非目标 scope 字节均不变；A1 scope 变化直接由登记结构和完整树身份保护。
这些计数不说明测试耗时或运行性能改善。

合成新组在当前副本只维护生产声明、独立预期数据、读者支持声明的 3 个中央 SHA，
旧 11 个 scope 与完成准备后的 10 个测试模块共 21 文件 SHA 不变，公开 scope 审计 exit0。
新组自身显式 test/writer/source 与固定分母是新增语义登记，另行审阅。
#135 的独立副本已实际运行旧 10 模块 78 例，通过且 21 文件字节不变；
本次实际合并树的 269 例组合包含 22 例真实机制正负回归，目标计数不由模拟 fixture 回填。

## 历史与开发验证

固定四个历史样本在根 `verification-runs/` 原位置读取，不搬迁；49 份 JSON SHA 全同，
failed/exit_nonzero、incomplete/interrupted、两个 passed/verified 均保持；当前 applicability 均 different。
历史 not_assessed、stage_a_verified=false 与读者独立支持格式不改。

- 相关功能组合：269 passed，包括本次 104、第一步 93、六冻结 scope/审计模块与真实回执回归。
- 全项目 Ruff check、format 检查通过（977 文件）；全配置 mypy 706 source files 通过。
- `check-compatibility all`：176 passed /270.27s，入口 exit0，总270.83s；默认 collect 审计 exit0，285模块5281例、skip0/deselect0。显式确认绑定候选提交后的结果留树外执行报告。

本候选尚须独立双轴审阅、fresh 修复及最终合并身份确认；未运行完整 `check-offline`。
唯一完整门禁由最终合并后的独立执行者按授权运行，退出 0 并查询同 run 为
passed/verified/same 后才能形成该树的正式结论。活文档修改和新 merge commit 都会使旧结论失效。
没有运行 live；本台账不证明完整阶段 A、四刊 live、Pi RPC、模型质量、正式校准、Docling 或 NAS。
