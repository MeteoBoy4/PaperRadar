# Issue #18 代码审查：A2-03 编译主题与价值预测配置并准确报告缺项

- 审查范围：`git diff HEAD^...HEAD`，经核实恰好一笔提交（固定点 `a13feb08`）：

  ```
  218e493 feat(config): compile topics and value configuration (#18)
  ```

- 规格来源：GitHub Issue #18 正文（9 条 Acceptance criteria）与全部 comments（1 条收口评论，含两点绑定澄清：①「主题文件完全未配置」指 settings 未选择 topics 版本，空集合与全部停用均判 value 就绪且投影身份相同；② enabled 必填、仅显式 true/false，name/description 以 strip 后非空为合法）；父票 #15 Decisions 4–6、11–12，补充一 1、12、20，补充二 21、30、32、36，以及「声明版本标签不进入阶段投影和基线」的确认。
- Standards 依据：AGENTS.md、CONTEXT.md、docs/agents/domain.md、相关 ADR、docs/contracts/ 与 docs/verification/ 文档、Fowler smell 基线；工具强制项（ruff / mypy strict）不在此轴重复。
- 审查方式：只读双轴独立审查（Standards / Spec 两个并行子代理），关键发现已经主代理抽查复核（`service.py:185-201`、`compile.py:106-117,224-236`、`topics.py:10`、`tests/test_config_value.py:22`、`scripts/a2_scope.py` 与 `cli.py` diff 均与报告一致）。Spec 轴离线运行完整测试套件（512 通过，含 71 个新增），并逐字节核对 examples 契约副本与 `a2_scope.py` 钉住哈希；因子代理只读约束未端到端执行 `./scripts/check-offline`（其哈希敏感输入已人工核对）。未修改代码、未创建 commit、未评论或关闭 Issue。

## Standards

**结论**：未发现对文档化标准的硬性违规。版本材料不可变（同身份异字节拒绝）、check 只读、整次编译回滚与幂等、`--help` 纯净、中文错误脱敏（不回显输入值/secret）、离线测试边界、文档同步（runtime-config.md / draft.md / offline-evidence.md / README / a2_scope 哈希）均有实现或测试支撑；`yaml_loader` 收紧 `!!bool` 隐式转换不影响任何已接受版本文件（无既有模型含布尔字段）。以下 8 项均为 baseline 判断项，无硬性违规。

1. **possible Duplicated Code — src/paper_radar/config/service.py:185-201**
   依据：Fowler 基线 Duplicated Code。topics 装载块是 profile（155-165）、models（167-184）同款「read_yaml → 版本不一致抛 `X.version：与 settings.X 不一致；请选择匹配版本` → append `CompiledMaterial(Material(*_KEY, version, raw), model.model_dump(mode="json"))`」的第三份近似拷贝。
   实际影响：下一种材料将产生第四份拷贝；错误措辞等修正会在多点漂移。
   最小修复：抽 `_versioned_yaml_material(path, model_cls, label, key, selected)` 供三处调用。

2. **possible Data Clumps / 长参数列表 — src/paper_radar/config/compile.py:110-117 与 service.py:140-149**
   依据：Fowler 基线 Data Clumps。`compile_snapshot` 现收 6 个位置参数，`_selected_materials` 返回对应的 6 元组，在 service.py:239、259 同样解包、404 处重组；`(profile, profile_material)` 对与不断增长的尾部整体同行。
   实际影响：每加一种材料需在多处对称修改签名与元组，顺序错位即静默错配。
   最小修复：把已选材料收成一个小 frozen 类型双向传递。

3. **跨模块私有导入 — src/paper_radar/config/topics.py:10**
   依据：AGENTS.md「项目可读性：保持清晰的模块边界」。`from paper_radar.config.schema import _valid_declared_version` 是 `src/` 内唯一的下划线名导入（其余均为公开名）；ruff 未启用 SLF，工具不拦。
   实际影响：schema.py 的私有 helper 实为隐藏公共契约，且被 `scripts/a2_scope.py` 哈希钉住，改名或挪动会波及验收范围。
   最小修复：改名为 `valid_declared_version`，或移到 identity.py 之类的共享模块。

4. **magic string 延续 — src/paper_radar/config/compile.py:224-236**
   依据：AGENTS.md「编码流程：优先使用明确的领域类型和受控 enum / reason，避免 magic string」。`prompt_reason("boundary", …)`、`contract_reason("value-prediction", …)` 等使用字面量，而 service.py:47-50 已有 `_CONTRACT_NAMES` 受控映射（`ContractName`）。
   实际影响：契约材料名在两个模块各写一份字面量，改名需双点同步；`"boundary"` 字面量属既有代码，本 diff 延续并扩大了该模式。
   最小修复：compile.py 导入 `ContractName`（contracts 不反向依赖 config，无循环）或抽出一份共享名称映射。

5. **类型宽于实际状态 — src/paper_radar/config/compile.py:106**
   依据：不可能状态 / 文档承诺不符。`topics_status` 用三值 `SlotStatus`，但主题只会是 `configured`/`unconfigured`（docs/contracts/runtime-config.md 也只承诺这两值）；cli.py:45 会直接打印 `placeholder`。
   实际影响：类型与公开 Contract 承诺不符；若未来误产 placeholder 状态，会以合法词汇混入 CLI 输出。
   最小修复：收为二值枚举，或加注释/assert 固定两值约定。

6. **possible Mysterious Name — src/paper_radar/config/service.py:362-366**
   依据：Fowler 基线 Mysterious Name。反查循环变量命名 `field`，其他位置同一概念均称 `selector`。
   实际影响：轻微阅读成本，同一概念两个名字。
   最小修复：改名 `selector`。

7. **possible Speculative Generality — src/paper_radar/config/compile.py:106-107**
   依据：Fowler 基线 Speculative Generality。`topics_status = SlotStatus.UNCONFIGURED` / `enabled_topics = ()` 带默认值，但唯一构造点（compile.py:282）两个都显式传入。
   实际影响：默认值暗示存在不传的调用方，实则没有，读代码时多一条要排除的路径。
   最小修复：删掉默认值。

8. **测试私有跨导入 — tests/test_config_value.py:22、tests/test_config_value_cli.py:10-11**
   依据：仓库既有模式是共享非测试支撑模块（`tests/contract_snapshot_support.py`）；本 diff 引入 `from tests.test_config_boundary import _inputs`、`from tests.test_config_cli import _run`、`from tests.test_config_value import _value_inputs` 等私有跨测试导入。
   实际影响：重命名 `_inputs` 会同时破坏两个不相关测试模块；测试间形成隐式耦合。
   最小修复：把共享夹具移入支撑模块。

## Spec

核对方式：fetch 了 #18 正文/评论、#15 及三条补充评论，通读 diff 全部源码与测试，并打开实现文件（`config/topics.py`、`compile.py`、`service.py`、`schema.py`、`yaml_loader.py`、`cli.py`、两个新测试模块、examples、runtime-config.md）逐一复核；离线运行完整测试套件（512 通过，含 71 个新增）；验证 `examples/contracts/screening/value-prediction/v1/` 与根 `contracts/` 权威快照逐字节一致；核对 `a2_scope.py` 全部钉住哈希与当前字节一致。

**验收标准逐条结论**：

1. **严格主题集合**（slug 受控规则、拒绝未知字段/重复 ID/非法大小写/空白变体/隐式布尔、不生成不编辑主题）——满足：`topics.py:12-61` 实现 `^[a-z][a-z0-9-]{0,63}$`、`extra="forbid"`、strict 模式，各拒绝路径在 `test_config_value.py:173-218` 有断言；slug 规则已写入 runtime-config.md 与 draft.md。
2. **空集合 vs 未配置不混同**——满足：`compile.py:237` 仅在 `topics is None` 时加 `MissingReason.TOPICS`；空集合/全部停用判 value 就绪且 `enabled_topics == ()` 相同、差异只留完整快照，收口评论①的语义由 `test_empty_and_disabled_sets_keep_distinct_history_and_same_enabled_semantics` 显式断言。
3. **复用 A2-02 材料验证与登记路径、整次编译回滚**——满足：service.py:96-137 经 `paper_radar.contracts` 公共 API 共享 `_contract_materials`；回滚由触发注入与跨材料冲突测试证明。
4. **value/boundary 就绪依赖隔离、非法材料整次失败**——满足：compile.py:220-238 两阶段原因各自独立，互不含对方材料；已选非法材料使 check/compile 整次失败（两个操作均有测试）。
5. **完整快照 vs 已启用语义、版本标签不入投影**——满足：payload 材料携带完整 topics dump+版本+字节哈希；`enabled_topics` 只含 id/name/description（无版本无哈希），符合收口评论与 #15 c3 确认；runtime-config.md 已记录该区别。
6. **测试与文档覆盖、A1 topic_ids 契约不变**——满足：空集合/全部停用/合法启用/未知字段/坏 ID/同版本拒绝/新版本成功/重启 load 均有公共服务与真实 CLI 覆盖；根 `contracts/` 未动。
7. **测试边界（真实临时 SQLite、离线）**——满足；新测试在 A2 自有模块，a2_scope 哈希已含 topics.py 并与当前字节一致。
8. **中文 help/错误脱敏/help 纯净**——满足：cli.py help 中文更新；help 测试断言不产生文件；service 与 CLI 测试均断言 secret 标记不回显。
9. **A1 哈希与模块边界**——满足：`scripts/a1_scope.py` 与四份 v1 冻结契约未动；`test_config_architecture.py` 字节不变；新增 topics.py 纯编译测试；收口评论②（enabled 必填严格布尔、strip 后非空 name/description、无 placeholder）在 `test_config_value.py:242-257` 落实。

### (a) 遗漏/部分实现

无。

### (b) 范围蔓延

无。每个被触文件都能对应到明确验收条或文档同步规则；A2-08 的阶段投影身份未提前实现（`NOT_IMPLEMENTED` 仍含 `stage_config_projections`、`calibration_baseline`），主题无权重/关键词语义。

### (c) 错误实现

无。逐项核实未发现与规格相悖的实现。

## 汇总

- Standards 轴：8 项发现（均为 baseline 判断项，无硬性违规）；最严重为 service.py:185-201 版本化材料装载形状的第三次复制，材料种类再增时需多点对称修改。
- Spec 轴：无发现。9 条验收标准与收口评论两点澄清全部落实，无遗漏、无范围蔓延、无错误实现。

## 人工针对性检查入口

以下入口可对本次变动范围（topics 严格集合、value 提示词/契约接入、两阶段就绪隔离、快照回放）做人工复查，全部离线，不需要网络、凭据或真实研究资料：

1. **CLI 全链路演练**：用 `examples/config/settings-value.yaml`（配合 `profiles/profile-example-v1.yaml`、`topics/topics-v1.yaml`、`prompts/` 与 `examples/contracts/screening/value-prediction/v1/`）在临时目录执行 `uv run paper-radar config compile --settings … --database …`，观察新增「主题集合：configured」行与 boundary/value 两阶段各自的就绪/缺项行；再以 `config check` 验证只读路径输出一致。
2. **空集合/全部停用/未配置三态对照**：分别构造 settings 不含 `topics:` 键（应报 value 缺项 `topics`）、`topics: []`（value 应就绪）、topics 文件内全部 `enabled: false`（value 应就绪）三种输入跑 check；后两者的 value 投影语义（无已启用主题）应一致，差异只体现在完整快照（可用 sqlite3 只读查询快照行对照）。
3. **严格校验负例**：手工编辑 topics YAML——重复 ID、大写 ID、`enabled: yes`（隐式布尔）、缺 `enabled`、未知字段、空白 name——逐项应得到只含字段路径与受控原因的中文错误，且不回显输入值。
4. **版本不可变与重启回放**：compile 成功后改 topics 文件一个字节而不改版本，再次 compile 应失败且无新事实入库；提升版本并切换 settings selector 后 compile 应成功，且旧版本材料仍可在新进程 `config check` 中回放，快照身份稳定。
5. **整次编译回滚**：在其余材料全部合法的情况下使 value 契约选择非法（或契约字节漂移），compile 应整次失败；用 sqlite3 只读对比前后行数，确认新增登记未残留。
6. **机器可读结论对照**：查看 `verification-runs/*.a2.json` 的 `not_implemented`，应已不再含 `topics`、`prompts_value…`、`contracts_value_prediction…`，改含 `prompts_reuse_reading`、`contracts_reuse_assessment_decision_reasons`；与 `docs/contracts/runtime-config.md` 字段表逐项对照。
7. **文档走查**：`docs/contracts/runtime-config.md` 的主题 slug 规则对照 `src/paper_radar/config/topics.py` 正则；`intent/draft.md` 与 `docs/verification/offline-evidence.md` 的同步段落对照 `scripts/a2_scope.py` 的 `NOT_IMPLEMENTED` 与哈希清单。
8. **无法直接人工验证的部分**：最终投影身份与校准基线隔离由 A2-08 验收，本票明确不交付，无运行入口；本票按设计不产生模型调用或网络行为，无法也不应经真实 LLM 验证。子代理因只读约束未端到端执行 `./scripts/check-offline`，如需完整验收证据可在允许写入 `verification-runs/` 的环境补跑。


## 建议核实与落实（Issue #18）

本次按原报告的 Standards 1–8 逐条核对当前接口、调用方及测试。八项均是合理的
维护性建议，未发现行为缺陷；第 5、7 项属于收紧类型与构造约定，不应解释为
现有 CLI 会误输出 placeholder。Spec 九条通过结论与当前实现一致，没有新增功能
需求。按用户要求跳过「人工针对性检查入口」，未读取该节内容或执行其中入口。

| 项 | 判断 | 实际处理 |
| --- | --- | --- |
| 1 重复 YAML 加载 | 采纳 | service 中抽出 `_versioned_yaml_material`，Profile/models/topics 共享读取、版本一致性检查和材料编译；仍使用同一份原始字节校验、哈希、登记。类型参数限于已支持的三种模型，不增加通用加载框架。 |
| 2 六参数/六元组 | 采纳 | 纯编译层引入 frozen `SelectedMaterials`。活跃读取与历史回放均按具名字段构造；check/compile/版本登记与 `compile_snapshot(materials)` 传递同一对象，避免顺序错配。 |
| 3 私有版本校验导入 | 采纳 | `_valid_declared_version` 更名为公开 `valid_declared_version`，schema 与 topics 共用，版本规则不变。 |
| 4 名称字面量 | 采纳 | 提示词使用已有 `StageName.BOUNDARY/VALUE`，契约使用 A1 权威 `ContractName`，就绪判断与加载引用同一枚举；不复制契约枚举或 Schema。 |
| 5 主题状态类型过宽 | 采纳 | 公开二值 `TopicsStatus`（configured/unconfigured），快照与 CLI 使用该类型，文档同步；不增加 placeholder。 |
| 6 field 命名 | 采纳 | 历史加载中的契约反查统一命名为 selector。 |
| 7 未使用的默认值 | 采纳 | `RuntimeConfigSnapshot.topics_status/enabled_topics` 改为必填构造参数；唯一构造点继续显式提供，旧快照从保存材料派生这两个值。 |
| 8 跨测试私有导入 | 采纳，保留固定测试资产 | 将可变测试中的 boundary/value 材料工厂移至 `tests/config_test_support.py`，新测试统一从该模块使用具名支撑函数、真实 CLI 与导入检查。已固定哈希的 A2-01 CLI/架构测试保持原字节，其内部历史辅助函数不迁移；新测试不再导入它们。支撑模块列入 A2 源码/支撑哈希清单。 |

配置文件契约、快照包络/身份格式、migration、中文输出及持久化行为均不变；
未增加后续票的阶段投影、校准门禁或流程。更新 runtime-config 与离线证据文档，
仅更新本次受影响源码及新增支撑模块哈希，不重标 A1/A2-01 固定测试。

本次验证使用项目锁定环境：

- 相关测试：`uv run --offline --locked pytest -q tests/test_config_value.py tests/test_config_value_cli.py tests/test_config_boundary.py tests/test_config_cli.py tests/test_config_architecture.py`，99 项通过。
- 类型检查：`uv run --offline --locked mypy`，通过。
- 提交前完整验证入口：`./scripts/check-offline`，实际结果以本次 `verification-runs/` 的离线证据、A1 与 A2-01 独立结论为准；不复用原审查或历史成功结果。
