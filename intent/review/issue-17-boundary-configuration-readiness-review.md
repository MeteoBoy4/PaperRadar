# Issue #17 代码审查：A2-02 检查并冻结研究边界阶段所需的模型、提示词和契约

- 审查范围：`HEAD~2..HEAD`（已验证 `git log HEAD~2..HEAD --oneline` 恰好两笔提交，固定点 `f01de3a`）：

  ```
  14dde40 Implement Issue #17 boundary configuration readiness
  2f801e1 Use controlled material types for config snapshots
  ```

- 规格来源：GitHub Issue #17 正文（11 条 Acceptance criteria）与全部 comments；父票 #15 Decisions 4–6、10–12，补充一 1–5、10–11，补充二 21、27、31–32、36–37、40–46，以及「声明版本不入投影」的用户确认。
- Standards 依据：AGENTS.md、CONTEXT.md、docs/agents/domain.md、相关 ADR（0006/0008/0023 等）、docs/contracts/ 与 docs/verification/ 文档、Fowler smell 基线；工具强制项（ruff / mypy strict）不在此轴重复。
- 审查方式：只读双轴独立审查（Standards / Spec 两个并行子代理），关键发现已经主代理逐条抽查复核（`service.py:93-97`、`scripts/a2_scope.py:115-125`、`intent/draft.md:1011`、`CONTEXT.md:15-16` 均与报告一致）。未修改代码、未创建 commit、未评论或关闭 Issue。

## Standards

**结论**：版本登记、幂等、事务原子性、脱敏、中文输出、受控枚举（第二笔提交把 `Material.kind` 收为 `MaterialKind`，符合 AGENTS.md「受控 enum 优先」）等硬性标准总体达标；文档同步较全。发现 1 个硬性违规、2 个文档/证据同步问题、若干轻微判断项。

### 硬性违规

1. **src/paper_radar/config/service.py:93-97**
   依据：AGENTS.md「面向用户的行为：错误信息应说明可操作的具体原因，不要用模糊状态隐藏失败」。`_contract_materials` 捕获 `ContractCheckError` 后丢弃其受控类别（missing/incomplete/damaged/version_mismatch/content_drift，各自带具体可操作指引），统一换成「冻结契约缺失、损坏、版本不一致或漂移」四选一罗列，用户无法知道实际命中哪条。
   实际影响：契约自检失败时 CLI 只报笼统原因，排查要靠猜；底层模块已有的受控失败词汇被浪费。
   最小修复：单独捕获 `ContractCheckError`，把 `error.category.value`（受控枚举，不含路径/输入值）并入 ConfigError 消息，如 `contracts.boundary：content_drift；请恢复权威 v1 快照`。

### 文档/证据同步（依据 AGENTS.md「文档维护」「完成标准」）

2. **scripts/a2_scope.py:115-125**
   依据：docs/verification/offline-evidence.md:95-98「结论记录…未实施项」；docs/contracts/runtime-config.md:28 仍写明 `prompts.value/reuse/reading` 及其他 `contracts.*`「仅 null，后续票开放」。`NOT_IMPLEMENTED` 整体删除 `prompts` 与 `frozen_contract_selection`，但 4 个提示词槽只开放 1 个、4 份契约只开放 1 份。
   实际影响：A2 验收结论 JSON 的 `not_implemented` 不再提示任何提示词/契约缺口，与同仓库契约文档直接矛盾，验收证据高估完成度。
   最小修复：改记粒度化未实施项，如 `prompts_value_reuse_reading`、`contracts_value_prediction_reuse_decision_reasons`（`models` 登记确已完成，可移除）。

3. **CONTEXT.md:16**
   依据：AGENTS.md「文档维护：领域不变量或受控 vocabulary、持久化或 Schema 行为变化需同步文档」。「配置就绪」词条仍写「A2-01 的全部阶段均未就绪」，而本变更使 boundary 在四者齐全时为 `ready`（runtime-config.md:95 已更新）。
   实际影响：权威词汇表对「配置就绪」的当前行为描述过时，误导后续 Agent。
   最小修复：将该句改为描述当前状态（boundary 可 ready，其余阶段仍因材料未开放而 not_ready）。

### 判断项（baseline smell，均轻微）

4. **src/paper_radar/config/service.py:112-167 与 260-300 — possible Repeated Switches / Data Clump**
   每种材料的「解析→对 selector 校版本→对编译值→包 CompiledMaterial」在装载路径（`_selected_materials`）与回放路径（`load_config_snapshot` 的 if/elif 级联）各写一遍；`_selected_materials` 返回 5 元组、`compile_snapshot` 收 5 参（compile.py:103-109），profile 被特殊隔离在 `additional` 之外只因编译值算法不同。下一票新增 `prompts.value` 等材料时需在 3 处对称修改。
   最小修复：抽一个按 kind 分派的「解析+核对」共享函数供两条路径调用；把 5 元组收为一个 `SelectedMaterials` 小类型。

5. **src/paper_radar/config/compile.py:186 — possible Duplicated Code**
   占位词表第三处拷贝：`prompt.raw...strip() in ("", "...")` 与 schema.py:167 Profile 段占位规则同义；另 `model_reason("screening", …)` 在 compile.py:197-201 与 214-218 原样调用两次。
   最小修复：文本占位判定收为共享 helper；screening 模型原因计算一次复用。

6. **src/paper_radar/config/schema.py:95-100、111-118、135-140 — possible Duplicated Code**
   同一 `valid_version` 函数体现在共 5 份拷贝（含既有 Profile/Models）。属既有模式的延续，非本变更新发明；可在后续顺手收为一个模块级校验函数。

7. **docs/contracts/runtime-config.md:45 — 文档措辞与实现微差**
   文档称 provider/model「精确为 `REQUIRED`…」为占位，实现却先 `strip()` 再比较（schema.py:78）；「前述三项缺失或为 null 时该槽为 unconfigured」与实现中占位判定先于 protocol 缺失判定（`provider: REQUIRED` 且无 protocol 时为 placeholder）顺序含糊。影响很小，建议文档改为「去首尾空白后精确等于」并明确判定顺序。

8. **src/paper_radar/config/service.py:329 — 疑似不可达异常**
   恢复路径 except 新增 `IndexError`，但 try 内无未防护的下标操作（`key` 为显式构造的 3 元组）。损坏恢复路径求宽可辩护，如需精简可删。

另注：a2_scope.py 的 SCOPE/ISSUE 仍为 `a2_01`/#16 而源码哈希已指向 A2-02 字节，offline-evidence.md:93 新增句已明确背书此做法（「不表示历史 A2-01 结论被改写」），按「文档标准优先」不予标记。

## Spec

核对方式：fetch 了 #17 正文/评论、#15 及三条补充评论，通读了 diff 全部源码与测试，并离线运行 `tests/test_config_boundary.py`（14 通过）及 config/A2 相关测试（54 通过）。

**验收标准逐条覆盖**：1–7、10、11 全覆盖；8 基本覆盖（见 a-2 遗留）；9 覆盖但证据粒度有缺陷（见 a-1）。

### (a) 遗漏/部分实现

**a-1. A2 机器结论的未实施项清单被整体删条目，超出本票实际交付**
1. `scripts/a2_scope.py:115-125`（`NOT_IMPLEMENTED`），配合 `scripts/a2_acceptance.py:224`。
2. spec 依据：#17 What to build「本票建立其共同加载与登记格式，阶段就绪只对本票完成的 boundary 链路作承诺。其他票在同一公共服务上补齐各自材料与依赖」；#15 Decision 17「A2 结论记录…未实施项」及用户故事 30「A2 验收证据明确说明自身范围与未完成能力」。
3. 实际影响：diff 从 `NOT_IMPLEMENTED` 删除了 `models`、`prompts`、`frozen_contract_selection` 三个条目，但本票只交付 boundary 纵向——value/reuse/reading 提示词、value_prediction/reuse_assessment/decision_reasons 三份契约选择仍未实现。此后生成的 `verification-runs/*.a2.json` 的 `not_implemented` 不再声明这些缺口，机器可读证据把未交付能力记为已交付。附带两点：`SCOPE`/`ISSUE` 仍为 `a2_01`/#16 而钉住的源码字节已是 A2-02 的；新回归模块 `tests/test_config_boundary.py` 未加入 `REQUIRED_TEST_MODULES`，其防削弱只靠完整 tests 通过（offline-evidence.md 已记录此取舍，可接受但值得知晓）。
4. 最小修复：把三个被删条目替换为细粒度条目（如 `prompts_value_reuse_reading`、`contract_value_prediction_reuse_assessment_decision_reasons`），`models` 可保持删除（三槽登记格式确实已交付）；同步 `docs/verification/offline-evidence.md` 措辞。

**a-2. draft.md 仍残留一处旧契约扁平路径**
1. `intent/draft.md:1011`。
2. spec 依据：补充二 #46（在 #17 声明的引用范围 40–46 内）「draft 写的是 `contracts/screening/boundary-v1.schema.json`，实际是 `contracts/screening/boundary/v1/{schema,manifest}.json`…A2 更新 §6 时应一并修正契约布局」。
3. 实际影响：§6 目录树已改对，但 §7 原因契约段仍写 `contracts/screening/decision-reasons-v1.schema.json`，读者会按错误路径找权威契约。
4. 最小修复：改为 `contracts/screening/decision-reasons/v1/schema.json`。

### (b) 范围蔓延

无。#17 评论明确推迟到 A2-08 的阶段投影与校准基线身份均未实现：`compile.py` 只产出快照身份与槽/阶段就绪，`NOT_IMPLEMENTED` 仍含 `stage_config_projections`、`calibration_baseline`；六阶段就绪框架是 #16 既有代码，本票仅按验收 2/3/6 增加 placeholder 缺项原因变体，不构成投影。登记材料中三槽可分别提取（models 编译值含全部三槽），符合收口要求。

### (c) 错误实现

逐项核实后未发现错误实现：

- 占位处理：词表封闭（`src/paper_radar/config/schema.py:28-30`），placeholder 判定优先于 missing（`schema.py:74-84`），混合缺失/占位返回单一受控原因（`compile.py:166-172`）；无凭据解析、协议探测或模型调用；`api_key` 等字段按未知字段拒绝且不回显值（`tests/test_config_boundary.py:237-257`）。
- 版本不可变：同身份不同字节拒绝（`src/paper_radar/storage/repository.py:39-42`）；Prompt 同字节登记两个声明版本已验证且不放宽 Profile 版本一致性（`tests/test_config_boundary.py:109-131`；`service.py:132-135`，回归在 `tests/test_config_validation.py:44`）。
- 契约登记一致性：先 `check_frozen_contract` 只读检查，再把盘字节与权威构建字节逐份比较后才登记（`service.py:85-109`），受检字节即登记字节；不支持版本/缺失/损坏/漂移均整次失败，不导出或修复；登记成功后活跃契约漂移仍被拒绝（`tests/test_config_boundary.py:134-141`）。
- 就绪输入仅限 Profile+screening 槽+boundary 提示词+权威契约（`compile.py:195-209`），不含主题、期刊、Read/reuse 模型；词汇只到 `ready`/`not_ready`+受控原因，无「校准就绪」输出。
- #17 评论收口（1）已落实：settings 单一 `models` 版本引用（`schema.py:129`），`docs/contracts/runtime-config.md` 字段表已同步修订。

验证：`uv run pytest tests/test_config_boundary.py` 14 通过；config/A2 相关五个模块 54 通过；`a2_scope.py` 钉住的 24 个文件哈希与当前字节一致。

## 汇总

- Standards 轴：8 项发现（1 硬性违规、2 文档同步、5 判断项）；最严重为 service.py:93-97 契约失败原因被压平成笼统消息，违反 AGENTS.md 错误可操作原则。
- Spec 轴：2 项发现（均为遗漏/部分实现，无范围蔓延、无错误实现）；最严重为 a2_scope.py `NOT_IMPLEMENTED` 整体删条目导致机器可读验收证据高估完成度。两轴在 a2_scope.py 问题上独立收敛（Standards #2 = Spec a-1）。

## 复核与处理（Issue #17 跟进）

以下逐条核实上文建议；原审查结论保留，便于追溯。

| 编号 | 处理 | 核实与结果 |
| --- | --- | --- |
| Standards 1 | 采纳 | A1 已提供受控 `ContractCheckErrorCategory`，原配置服务却压平失败。现在按类别给出中文处理指引，保留字段路径且不输出底层路径或异常；新增缺失、损坏及 CLI 回归。 |
| Standards 2 / Spec a-1 | 采纳 | models 三槽登记已完成，可移除整体缺项；其他提示词槽与三份契约选择尚未开放。A2 机器结论改为逐槽列出，并同步离线证据文档。 |
| Standards 3 | 采纳问题，调整做法 | `CONTEXT.md` 的 A2-01 阶段状态已过时。领域词汇表只保留“配置就绪”的定义，移除具体 ticket 状态；当前 boundary 就绪范围由 `runtime-config.md` 说明。 |
| Standards 4 | 暂不采纳 | 活跃文件检查与历史数据库回放有不同的校验依据；为了未来配置材料预先建立共享分派，会扩大本票范围。当前五元组虽可改善，但没有形成错误行为，留待新增材料时按实际需要调整。 |
| Standards 5 | 采纳 | Profile 与 Prompt 的 ASCII `...` 占位判定复用纯 helper；Screening 模型缺项原因只计算一次。 |
| Standards 6 | 采纳 | 多处声明版本格式检查改为调用同一个纯函数，仍保留各 Pydantic 字段验证入口。 |
| Standards 7 | 采纳 | 配置契约文档明确先判占位，且 provider/model 在去除首尾空白后与封闭词表比较。 |
| Standards 8 | 采纳 | 历史回放没有可能抛出 `IndexError` 的索引访问，移除该多余捕获。 |
| Spec a-2 | 采纳 | `intent/draft.md` 中原因契约的旧扁平路径改为实际冻结目录布局。 |

验证：新增回归先确认旧实现无法区分契约缺失与损坏；修复后相关配置测试 64 项通过。`./scripts/check-offline` 的六项检查和 A1/A2-01 结论均通过。未执行下节的人工针对性检查入口。

## 人工针对性检查入口

以下入口可直接用于对本次变动范围（config 模块的 models/prompts/contracts 登记与 boundary 就绪判定）做人工复查，全部为离线操作，不需要网络、凭据或真实研究资料：

1. **定向回归测试**：`uv run pytest tests/test_config_boundary.py -q`（本票新增的 14 条回归，覆盖就绪/占位/契约漂移/版本不可变/双版本同字节等核心场景）；配套 `tests/test_config_service.py`、`tests/test_config_cli.py`、`tests/test_config_architecture.py`。完整离线验证入口为 `scripts/check-offline`（A1+A2 结论均通过才返回 0）。
2. **真实 CLI 四场景走查**（对应验收标准 8）：以 `examples/config/` 的合成配置为模板复制到临时目录，按 `docs/contracts/runtime-config.md` 补齐 `prompts/` 与 `contracts/` 布局（四份 A1 v1 冻结契约从仓库根 `contracts/` 复制），先 `paper-radar db upgrade --database <临时路径>` 建库，然后依次：
   - ready：`paper-radar config check --settings ... --database ...` 与 `config compile` 应输出 boundary `ready`；
   - placeholder：把 models 文件某槽 provider/model 改为 `REQUIRED`，check 应报 `not_ready` 且原因为 placeholder；
   - 契约损坏回滚：登记成功后改坏 `contracts/` 下活跃契约字节，再次 compile 应失败且无新事实入库（可用 sqlite3 只读查询对比行数）；
   - 新增版本：新增一份同字节不同声明版本的 Prompt 或 models 文件并切换 selector，compile 应成功且旧版本材料仍可回放。
3. **机器可读结论人工对照**：查看 `verification-runs/*.a2.json` 的 `not_implemented` 字段，与 `docs/contracts/runtime-config.md` 字段表中的「仅 null，后续票开放」条目逐项对照——这正是本次 Standards #2 / Spec a-1 发现的高估问题，修复前该 JSON 不会列出 prompts/契约缺口。
4. **文档走查**：`docs/contracts/runtime-config.md`（字段表与依赖描述）对照 `intent/draft.md` §6/§7.6；其中 draft.md:1011 的扁平契约路径是已知残留（Spec a-2）。
5. **无法直接人工验证的部分**：本票按设计不产生任何模型调用、凭据解析或网络行为，无法也不应通过真实 LLM 验证；阶段投影与校准基线身份由 A2-08 组合，本票范围内无运行入口可验证，只能以「未实现且未冒充实现」为准（见 `NOT_IMPLEMENTED` 与 offline-evidence.md 声明）。
