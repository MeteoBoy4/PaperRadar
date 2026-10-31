# 全部共享材料与 scope 显式引用迁移

本次以 `13a2a8d66a013ab5737bf7653d8fe1bbc58a3337` 为迁移起点，稳定 main 仍为
`e6c1ec74c9fc8d15fc8f76d2c8a7b29fcdda9438`。这是开发期迁移事实，不是正式验收结论。
机器可读逐组母集、用途与旧 SHA 见 [JSON 台账](scope-shared-dag-delivery.json)。

起点共 11 组、1216 条登记、701 个路径。实际跨两个及以上组登记的非 scope 共享材料
为 252 个、735 个成员资格；#133 已集中 14 个，本次补齐余下 238 个。
第一步 e6 的 250 个共享路径与当前差额为 baseline、collection 两个实际消费支撑。
共享成员各自保留原 kind/role；10 个 source/test 跨用途路径及 pyproject.toml 的
source/fixture 跨用途不合并用途、不降敏感级别。单组独有材料继续保留字面量。

scope 路径由实际 `Scope.path` 集合定义，41 条逐文件 SHA 登记迁为 41 条
`REQUIRED_SCOPE_REFERENCES`。旧票面及第一步冻结描述的 42 没有第 42 条实际边；
按相同定义，原 784 与第一步 e6 都为 41。本次不改写冻结历史描述，也不制造补边。
迁移后固定材料 1175 条、692 路径；非 scope 有序逐组 path/kind/SHA 与起点完全相同，
所有固定计数、原拓扑与 downstream 相同。JSON 保留完整旧母集和逐边旧 SHA。

scope、中央登记不进入逐文件哈希闭包。旧字面量及 `replace(bindings=...)` 注入边继续
参与同一 self/cycle 检查；显式引用拒绝非 tuple、未知/非法/重复路径、自引用与循环。
完整入口和 receipt 继续消费运行时展开后的 `(path, sha)` 与固定计数，不哈希登记文件。
refs 变化纳入基线 entry 摘要和敏感 registration，影响范围合并旧图与新图；确认绑定
原有完整身份，逐全部受影响组核对，确认不解除真实 hash_drift。

系统递归核对 A6–A10 所有固定 JSON 中的 scope 指针，唯一命中是 A8
`tests/fixtures/a8_capabilities.json` 的 `a7_authoritative_acceptance/materials/1`。
冻结 fixture 保留原字节；A8 writer 用当前组经结构审计的显式引用确认该元数据指针。
普通固定材料仍核对真实 SHA，未列 scope、普通代码伪引用与非法图继续拒绝。

本次独立 D1 模块 `tests/test_scope_shared_dag.py` 共 24 例，不纳入历史 required 分母：
显式图与旧注入兼容 1、refs 变化与旧新图影响并集 1、结构拒绝 6、完整母集等价 1、
CLI/A1测试/A1 scope 三场景 3、真实 writer 强拒绝 3、基线非法 object 受控拒绝 1、writer 无关组结构隔离 1、AST 软链边界 5、根内 ignored 目标拒绝 2。
既有 #132 的 34 例、#133 的 17 例和第一步 93 例不替换、不减数。

两处已未绑定测试作最小兼容：A8/A9 第一阶段 inventory 精确预期明确扣除 14 条
实际 scope SHA 边并独立断言全部 14 条显式引用；#133 writer 回归审阅白名单加入本次
实际变化的 A8 writer。用例数与原意图保持，逐文件旧新 SHA 和理由见 JSON。
六个冻结 scope/audit 测试相对第一步原字节保留；既有验证证据、历史 JSON、ADR 正文、
业务、Schema 与 migration 不改。实际验证、候选维护处与预计漂移见以下记录与 JSON。

CLI 场景为 7 个直接组与 3 个额外下游、1 处中央 SHA；A1 固定测试为 2 个直接组与
8 个额外下游，同样只维护中央 SHA。scope 字节变化不修改其他 scope。逻辑共享登记资格
为 735→252，另移除 41 个 scope SHA 位置；成员资格行仍逐组保留。
独立 AST 核对迁移起点的实际维护位置：scope 中 630 个共享材料 SHA 字面量加中央 14 个
SHA，共 644→252，实际少 392 处；再取消 41 处 scope SHA，共少 433 处。完整 A2
通过辅助导入复用 A1 的 12 个测试成员，所以逻辑资格数与物理 SHA 位置数不同。
最终重绑、敏感确认、D1 归并与唯一完整门禁由 #137 承接；本次不接受生产候选哈希。

未执行 live；结果不代表四刊、Pi RPC、模型质量、正式校准、Docling、NAS 或完整阶段 A。

## 开发验证与预计漂移

- v3 严格白名单候选：228 例相关测试通过（122.42s），包括六冻结模块、第一步全部
  93 例和 #132/#133；随后 acceptance 117 例通过（213.43s），入口总 213.89s、exit0。
- v3 后仅收紧元数据为普通文件且无链接重定向，新增根内 ignored 目标两例。最终当前树
  新24 + #132原34 + #133原17 共75例通过（34.08s），最终 AST 边界7例独立通过。
  两版 registry SHA 在 JSON 中逐一登记；没有把旧版本组合伪称为最终树完整门禁。
- Ruff 20 个新增/修改 Python 模块 check 与 format 通过；mypy 701 source files 通过。
- 真实结构 `issues=[]`，285 个固定测试模块完整收集 5281 例，skip/deselect 为0；
  原固定分母、六冻结测试 SHA 与迁移前逐组计数一致。
- 候选只维护5处已审阅SHA：中央的 audit、registry、baseline、A8 writer 各1处，以及
  A9 的独有 CLI 字面量1处；没有任何 scope SHA 传播，生产登记未重绑。

#133 的历史40条漂移（7直接+33scope传播）与11条确认缺口保持为历史事实。
当前真实树预计12条材料漂移：继承7直接，加本次 baseline 3组和 A8 writer 2组；
稳定 main=e6 基线下共有61条逐组敏感确认缺口，包含引用/迁移语义及继承的新消费闭包。
这些变化及完整旧新entry身份留待 #137 在最终树审阅；没有提交确认文件、自动接受候选
或把减少机械传播解释为已处理历史缺口。
