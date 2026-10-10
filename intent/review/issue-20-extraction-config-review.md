# Issue #20 代码审查：版本化正文提取配置

- **审查对象**：`328cdb4 Implement versioned extraction configuration (#20)`（审查时 HEAD）
- **固定点**：`HEAD^`（`d23841ad86b2d9afc9129034ba274f1f2b72e164`）
- **审查范围**：仅 `git diff HEAD^...HEAD`（26 个文件，+1410/-30）
- **规格来源**：GitHub Issue #20 正文（10 条 AC）+ 全部 3 条 comments；父 spec Issue #15 Decisions 4–5、11–13 及补充一 2/6/14、补充二 24–25/42–43、版本标签规则；`intent/discussions/docling-issue-20-live-probe.md`（重点 §5、§7.4、结论 1–2）；`intent/discussions/v2-body-parser-backend-seam.md`
- **Standards 来源**：`AGENTS.md`、`CONTEXT.md`、`docs/agents/domain.md`、ADR-0010/0023/0025、既有 `src/paper_radar/config/` 代码惯例，外加 Fowler smell 基线
- **审查方式**：只读两轴并行审查；未修改代码、未创建 commit、未触碰 GitHub Issue
- **独立验证**：本 commit 新增 5 个测试模块 113 条全部通过，仓库全量 `pytest` 716 条通过；`scripts/a2_scope.py` 登记的 33 项钉住哈希与 HEAD 实际字节逐一重算全部一致；`tests/deny_external_io`、`tests/deny_network`、`contracts/`、`pyproject.toml`、`uv.lock` 零改动

## Standards

**未发现 hard violation。** 本 commit 遵守 AGENTS.md 核心不变量、数据与版本控制纪律、模块解耦、中文文本、脱敏与验证要求；文档同步完整。仅 5 条 judgement call 级基线 smell，均低严重度。

### 已核实的合规点（抽查依据）

- **纯编译层无 I/O 依赖**：`extraction*.py` 只 import 同层模块，不引入 YAML/SQLite/Docling；`tests/test_config_extraction_architecture.py:8-15` 用导入检查强制此边界，无循环依赖。
- **不可变版本登记**：extraction 材料进入 `config_versions` 字节哈希绑定，`tests/test_config_extraction_persistence.py:28-58` 证明同键换字节被拒、须新建声明版本，符合"已版本化的语义配置不可原地修改"。
- **同事务原子性**：复用既有 `save_snapshot` 事务；回滚测试（`test_config_extraction_persistence.py:103-136`）证明不留部分结果。
- **错误脱敏**：校验错误经 `yaml_loader.py:111-114` 泛化为字段路径+固定文案，测试断言敏感标记不回显。
- **幂等**：两次 compile 相等有测试断言；`compiled_config()` 派生展开确定性。
- **"无需 migration" 声明属实**：`storage/schema.py:19,43` 的 `kind` 列为 `String(32)` 无 CHECK 约束，新增 `MaterialKind.EXTRACTION` 不需 migration。
- **无新依赖**：`pyproject.toml`/`uv.lock` 未动，符合 lockfile 纪律。
- **中文 help/错误、CLI `--help` 零 I/O**：`cli.py:26-28` 新增中文说明；测试断言 help 不落盘。
- **配置就绪语义**：`compile.py:311-314` 的 ready 只表示材料合法完整，help 与 `docs/contracts/extraction-config.md` 均明示不证明 fixture gate/资源检查通过。
- **文档同步**：CONTEXT.md、ADR-0025（新增）与 ADR-0010（顶部标注被取代）、runtime-config.md、README、intent/draft.md、offline-evidence.md 均已同步；ADR 编号接续无冲突。

### Findings（均为 judgement call）

**S-1. 通用装载器内的类型特判（Repeated Switches 苗头 / Divergent Change）**
- 位置：`src/paper_radar/config/service.py:144-160`
- 现象：`_versioned_yaml_material` 的 TypeVar 约束名单扩到 5 个类型，函数体内新增 `config.compiled_config() if isinstance(config, Extraction) else config.model_dump(mode="json")`。通用函数现在认识具体材料类型。
- 影响：低。当前只有一个特判，行为正确；但今后每加一类需要派生存档字段的材料，都要回来改这个共享函数。
- 最小修复：给各配置类型定义统一方法（如 `compiled_config()`，默认返回 `model_dump(mode="json")`，`Extraction` 覆写），通用函数只调方法不判类型。

**S-2. 派生哈希属性暂无生产消费者（Speculative Generality）**
- 位置：`src/paper_radar/config/extraction.py:52-70`（`backend_config_hash`、`model_artifacts_hash`）
- 现象：两个属性本 commit 内只有测试消费，生产代码无人调用；`model_artifacts_hash` 的 `None` 分支在 V1 不可达（layout/table 为必填）。同 commit 的 `docs/contracts/extraction-config.md:95-97` 将其登记为"供 A2-08 投影"的契约，而 A2-08 投影不在本票。AGENTS.md 范围控制要求"只实现当前任务明确需要的内容"。
- 影响：低。属性简单、已测试、已写入文档契约，保留代价小，但属于为未到需求预建的 API 面。
- 最小修复：严格按范围控制可删到 A2-08 再加；若保留可接受，但 `None` 分支不可达值得注明。

**S-3. 阶段名 magic string（Primitive Obsession 边缘）**
- 位置：`src/paper_radar/config/extraction.py:115-121`（`("layout", …)` 等）及 `ModelArtifactIdentity.stage: str`（`extraction.py:34`）
- 现象：AGENTS.md 写明"优先使用明确的领域类型和受控 enum / reason，避免 magic string"；仓库对同类受控词表（`ExcerptSelectorVersion`、`NormalizationVersion`）用了 StrEnum，而模型阶段名是裸字符串。
- 影响：低。封闭三元组有事实约束；但阶段名进入存档语义与哈希，拼写漂移不会被类型系统拦截。
- 最小修复：定义 `ModelStage(StrEnum)`（layout/table/formula）替换裸字符串。

**S-4. `enabled_formula_identity` 命名（Mysterious Name，极轻微）**
- 位置：`src/paper_radar/config/extraction.py:84-87`
- 现象：该 model_validator 实际校验"policy 开关与 formula 模型槽存在性一致"，名字读起来像名词短语，不揭示校验意图。
- 影响：极低，仅可读性。
- 最小修复：改名如 `formula_flag_matches_model_slot`。

**S-5. 不可达的 toolchain 守卫（死代码）**
- 位置：`src/paper_radar/config/extraction_toolchain.py:34-35`
- 现象：`ToolchainId` 是单值 Literal，且 `backend_identity` 只在 pydantic 校验完成后被调用，`if toolchain != "docling-2.135.0-cpu-v1": raise` 按类型系统不可达。
- 影响：极低。防御性代码成本极小，但是死分支。
- 最小修复：可删；若作为清单演化路标保留也可接受。

### 审查限制

本轴未运行测试套件（只读纪律）；以可静态验证的替代检查代替（哈希钉 33/33 一致、存储层无枚举约束、文档声明与代码逐项比对），测试结论以 Spec 轴实跑与 `docs/verification/offline-evidence.md` 登记为准。

## Spec

### (a) spec 要求但缺失或部分实现

**A-1（轻微）：OCR=true 拒绝时缺少"V1 不支持 OCR"的专属指引**
- Spec 原文：Issue #15 补充二第 42 条："建议 extraction 类型把 OCR 固定为字面量 `false`，写 `true` 时拒绝并给出'V1 不支持 OCR'的指引。"（Issue #20 正文"范围依据"明确引用补充二 42–43。）
- 代码位置：`src/paper_radar/config/extraction_policy.py:14`（`do_ocr: Literal[False]`）+ service 层通用错误包装。
- 依据：拒绝行为已实现且有测试（`tests/test_config_extraction_validation.py` 的 `do_ocr: true` 用例通过），但实测报错为 `extraction.policy.do_ocr：字段缺失、类型错误或不受支持`——与"缺字段/错哈希/未知 toolchain"共用同一条泛化受控原因，未给出 #42 要求的"V1 不支持 OCR"可操作指引，用户无法从错误中区分"填错格式"与"该能力 V1 明确关闭"。
- 影响：低。不泄漏、不误放行；仅错误可操作性略低于 spec 建议，OCR 语义安全不受影响。
- 最小修复：service 层对固定 Literal 拒绝且输入值等于禁止能力开启值（`do_ocr: true`、`do_table_structure: false` 等）时追加受控原因短语如"该能力在 V1 固定关闭"；或在 `docs/contracts/extraction-config.md` 错误章节明确此统一文案即表示 V1 边界。

**本类其余各项均未发现缺失**：AC1（工具链封闭清单+按阶段模型 commit/文件哈希+必填性与哈希格式文档化）、AC2 禁止值拒绝、AC3 资源/凭据字段拒绝且脱敏、AC4 受控 v1 身份+未知版本拒绝+无字节登记+漂移限制已文档化、AC5 通用 check/compile/load 复用+同事务+重启回放、AC6 纯语义对象+独立分量、AC7 CLI/公共服务覆盖七类场景、AC8 真实临时 SQLite+回归/CLI 集成测试、AC9 中文 help/错误+脱敏、AC10 测试独立模块+A1 资产保留+文档同步，逐条核对均有实现与测试。

### (b) spec 未要求的行为（范围蔓延）

**B-1（授权事实已由用户确认，残余为留痕建议）：公式增强默认启用超出 Issue #20 AC2 字面边界**
- Spec 原文：Issue #20 AC2："按照当前 V1 规范固定 CPU、单论文串行、**OCR/公式**/图片/图表增强/远程与外部插件**关闭**、表格结构识别开启。"seam 文档第四节（2026-10-10 采纳）："不改变 V1 的单 backend 行为：OCR、**公式**/图片增强、远程插件**照旧关闭**（ADR-0010），本稿不触碰。"
- 代码位置：`src/paper_radar/config/extraction_policy.py:16`（`do_formula_enrichment: bool = True`，policy 中唯一默认开启的增强）；`extraction_models.py` 整个 `FormulaModel` 槽；新增 `docs/adr/0025-allow-local-formula-candidates-with-source-review.md`；连带 `CONTEXT.md:261,350`、`intent/draft.md` 5 处、ADR-0010 顶部加注。
- 依据：支持该行为的规格链是 live-probe §7.4 第 2 项，原文为条件式建议"**如果确实需要**理解独立公式，增加 CodeFormulaV2 的局部候选转写"。ADR-0025 声称"2026-10-10 用户在 Issue #20 实施时明确允许并默认启用"；该授权事实不存在于任何规格文件（Issue #20 三条评论均未提及公式），但与 seam 文档第四节"照旧关闭"存在同日文本冲突。
- **主审查确认**：本次审查请求中用户明确陈述"Docling 配置项（或初始默认值）的设立……根据 live-probe 所述进行了调整（重点参考第五部分和 7.4 和 1、2 两小项）"，与 ADR-0025 的授权声称互证，授权事实成立。故此项不构成代码缺陷，残余问题仅为可追溯性：Issue #20 页面本身无该决定记录，seam 文档第四节的冲突文本未同步修订。
- 影响：实现质量本身高——ADR-0025 按流程显式 supersede ADR-0010 公式条款，CONTEXT/draft/README/阶段 F DoD 同步完整，源/候选分离与裁切核查义务已写入契约文档，公式槽与开关一致性有强制校验（`enabled_formula_identity`），可显式关闭且有测试。残余风险仅为后续读者对照 Issue/ seam 文本时的口径不一致。
- 最小修复建议（不需要改代码）：由用户在 Issue #20 下补一条评论记录该决定并与 ADR-0025 互链；顺手修订 seam 文档第四节"照旧关闭"的过时表述。本审查按要求不代发 Issue 评论。

**本类其余核查未发现蔓延**：`component_versions` 收录 torch/torchvision/transformers 有 live-probe §5.1 第 2 项明确授权；`formula_evidence`/`separate_formula_source`/`formula_pdf_crop_review` 三个非 Docling 原生 policy 字段有 live-probe §7.2.B 与 ADR-0025 依据；未建 backend 注册表/自动 fallback/A-B（seam 第四节）、未新增依赖、未建无消费者数据表（AC3 末句）、未把 excerpt selector/chunking 塞入 extraction（拒绝清单含 `excerpt_selector_version`/`chunking_version`，有测试）。

### (c) 看似实现但实现方式疑似错误

**本类未发现问题。** 重点核对过的高风险点均判定正确：

- `BackendIdentity.backend_version` 取 docling 版本而非 PDF 后端包版本——初看疑似违背 Issue #20 评论 3（"后端选择+所选后端的包版本"两项），但所选后端包版本（pypdfium2 5.14.0 / docling-parse 7.22.2）完整保存在 `component_versions` 且按后端条件取舍，`backend_id`+`backend_version` 与 seam 文档 §3.2 的结构化字段命名一致，无信息丢失。
- 声明版本标签/toolchain 标签不进入 `ExtractionSemantics`（符合 Issue #15 补充二 #21 及评论 3 确认的规则）：改名换版本产生新快照但语义对象相等，有跨进程测试。
- `load_config_snapshot` 对 extraction 重放时重新校验 `compiled_config()` 与存档展开一致，清单漂移拒绝（`service.py:369-373`），损坏脱敏有测试。
- 快照包络新增材料种类未提升 `FORMAT_VERSION`（仍为 1），符合 `runtime-config.md` 既定纪律；`NOT_IMPLEMENTED` 改名 `body_extraction_execution` 语义准确且证据文档已同步。
- Docling 2.135.0 源码核对：threaded 后端确实消费 `enforce_same_font`/`include_bitmap_images`/`render_pages`/`render_scale`，pypdfium2 后端只消费 `password`（凭据，正确排除）——`extraction.py` 两个后端的 `pdf_options` 冻结值与上游实际语义消费者及默认值精确一致。

### 补充观察（非 finding）

- 最新 A2 验收结论（`verification-runs/18f4dfed….a2.json`，status=passed）记录的 `code.commit` 是 `d23841a`（HEAD^）而非本 commit——该项目"先跑完整离线验证再提交"的既定模式（worktree 哈希绑定），证据链完整。
- AC2 正例要求"语义变化正例使用允许的后端/版本/模型哈希差异"——`test_new_versions_change_only_their_extraction_semantics` 覆盖 backend/commit/file_hash/table_mode 四种，符合。

## 原审查汇总

- **Standards 轴**：0 条 hard violation，5 条 judgement call；最重为 S-1（`service.py:144-160` 通用装载器的类型特判，每次新增派生材料种类都要改共享函数）。
- **Spec 轴**：(a) 1 条轻微部分实现（A-1，OCR 拒绝指引不专属）；(b) 1 条（B-1，公式默认启用——授权已经用户确认，残余为 Issue 留痕建议）；(c) 0 条。最重为 B-1 的规格文本可追溯性缺口。


## 逐条核实与处理（2026-10-10）

本节记录对 `328cdb4` 原审查建议的实施结论；上文保留原审查事实与原统计。
“人工针对性检查入口”未作为本次阅读或执行入口，其中内容原样保留。
本次仅改进 Issue #20 配置边界，不执行 PDF 解析、模型下载或后续 ticket。

| 项目 | 判断与处理 | 核实依据和取舍 |
| --- | --- | --- |
| S-1 通用装载器的类型特判 | 暂不采纳统一方法的改法 | 维护风险合理，但当前仅 Extraction 需要派生归档，其余四类只是 Pydantic JSON dump，尚无重复 switch。给五类配置都引入新方法/共同基类会扩大改动，现有封闭 TypeVar 也有助于限制可登记类型。保留当前局部特判；若出现第二类需要派生归档的材料，再根据实际消费者提取共同边界。 |
| S-2 派生哈希暂无生产消费者 | 保留，补充文档 | 用户明确要求 V2 backend 接缝；draft §3.4、seam §3.2 的结构化 descriptor 本来就要求配置/模型身份及无模型时的空值。现有属性只是只读内容身份，没有实现 A2-08 投影、阶段输入指纹或缓存流程，删除已公布接口没有当前收益。文档明确 V1 必填 layout/table，实际 hash 恒非空；None 只表示中立语义对象的空模型清单。 |
| S-3 模型阶段名裸字符串 | 采纳 | 新增并公开 ModelStage（layout/table/formula），ModelArtifactIdentity.stage 和内部阶段枚举使用该类型。合法值仍序列化为原小写字符串，回归确认原快照与语义哈希不变。 |
| S-4 校验器名字不揭示意图 | 采纳 | enabled_formula_identity 改为 formula_flag_matches_model_slot；开关与模型槽的一致性规则保持原行为。 |
| S-5 toolchain 守卫不可达 | 保留 | Literal 是静态类型提示，不提供 Python 运行时校验。直接调用辅助函数传入未知工具链时，现有守卫实际可达并抛出 ValueError（本次已独立执行确认）。普通服务路径虽先经 Pydantic 校验，这条低成本保护仍能避免未经过该路径的调用静默复用错误清单。 |
| A-1 OCR 拒绝指引不专属 | 采纳并补回归 | policy 对明确 true 产生受控 v1_ocr_disabled 原因；YAML 边界只映射白名单原因，公共服务/CLI 提示“V1 不支持 OCR；请将 do_ocr 设为 false 或省略；扫描稿需等待 V2”。其他类型错误继续使用原脱敏原因，不回显模型异常 input/context/message。 |
| B-1 公式增强授权与规格留痕 | 文档部分采纳；不撤回已授权行为 | 原实施会话中用户对范围确认的明确答复为“允许并默认启用局部公式候选转写，同步修订 ADR 和配置文档”，授权充分。seam 文档第四节的过时表述确有冲突，已修订并链接 ADR-0025，状态行也标明后续裁决。Issue 页面补评论属于额外发布，本次请求是提交关联 Issue 的 commit；决定通过本报告、ADR 与 seam 留档，commit 引用 #20，不代发远端评论。 |

本次采纳的是具体可读性、错误指引和文稿同步改进；S-1/S-2/S-5 不构成已证实的行为缺陷，保留取舍及理由供后续实际需求复核。

### 验证记录

- 新增回归在修正前出现 4 项失败、2 项通过：捕获裸字符串阶段与 OCR 指引不足；修正后 6 项全部通过。
- Issue #20 五个相关模块共 119 项通过（公共服务、真实 SQLite、CLI、配置结构和导入边界）。
- 额外用改动前编译保存的真实 SQLite 快照执行改动后 load，旧快照成功回放；snapshot ID `ba91a2df31e69d9caa248ee0ffb899dfaa2302a0b0d8fde6cac1047a0acd42d4`、backend config hash `c5ab2231b523d646b9766610c262fcc602fc6c6d9b2803bd011c813d3e53adcb`、model artifacts hash `a68e0a79937ae0622c5d47103225ab9571e2399ec3764e07a603877c6106fd38` 保持不变。
- Ruff 格式/静态检查与 mypy 已通过。最终仓库验证入口为 `UV_CACHE_DIR=/tmp/paperradar-uv-cache ./scripts/check-offline`（lockfile、格式、静态规则、mypy、全部 pytest、冻结契约、A1/A2-01 机器结论）；实际运行结果及机器证据 ID 记录在本次关联 #20 的 commit 说明中。
- 原始四份 v1 冻结契约、A1/A2-01 固定测试、migration 和 uv.lock 未修改；本次不需要 migration。


## 人工针对性检查入口

以下入口均不需要改动代码即可执行；标注"无法直接验证"的项说明替代依据。

### 1. CLI 端到端实跑（最直观的功能检查）

在临时目录操作，不触碰真实用户数据：

```bash
# help 安全性：不读配置、不开库、退出 0
uv run paper-radar config check --help

# 只读检查（不建库即应给出受控错误或就绪报告）
uv run paper-radar config check --settings examples/config/settings-extraction.yaml --database /tmp/pr-review/x.db

# 完整链路：显式建库 → 编译 → 重复编译验证幂等身份
uv run paper-radar db upgrade --database /tmp/pr-review/x.db
uv run paper-radar config compile --settings examples/config/settings-extraction.yaml --database /tmp/pr-review/x.db
uv run paper-radar config compile --settings examples/config/settings-extraction.yaml --database /tmp/pr-review/x.db  # 应得同一快照身份
```

针对 AC7 的七类负例，复制 `examples/config/extraction/extraction-example-v1.yaml` 到临时目录逐一篡改后跑 `config check`：
- 缺项：删掉 `models.table` 整段 → 应报告 extraction 未就绪及缺项；
- 禁止开关：`policy.do_ocr: true`、`policy.do_table_structure: false` → 应拒绝（可顺带验证 finding A-1 的实际报错文案）；
- 错误哈希：把某 `sha256` 改成非 64 位十六进制 → 应拒绝且不回显输入值；
- 资源/凭据字段：加 `timeout_seconds: 60` 或 `hf_token: ...` → 应按未知字段拒绝且不脱敏失败；
- 未知算法版本：`normalization_version: v2` → 应拒绝；
- 新版本回放：复制一份改 `version:` 标签与某个 commit/哈希 → 编译应产生新快照且旧快照仍可查询（AC5 语义变化正例）；
- 不可变性：保持 `version:` 不变只改一处注释或空白 → 重新 compile 应被拒绝（不可原地修改）。

### 2. 定向测试（最小范围）

```bash
uv run pytest tests/test_config_extraction.py tests/test_config_extraction_validation.py \
  tests/test_config_extraction_persistence.py tests/test_config_extraction_cli.py \
  tests/test_config_extraction_architecture.py -q
```

分别对应：纯语义对象（AC6）、校验负例（AC1/2/3/4）、真实临时 SQLite 持久化承诺（AC5/AC8）、CLI 集成（AC7/AC9）、纯配置层无 YAML/DB/Docling 依赖的架构边界（AC6/AC10）。

### 3. 仓库完整离线验证

```bash
./scripts/check-offline
```

执行 lockfile/格式/静态规则/类型/全部测试/四份冻结契约，并在 `verification-runs/` 新建本次证据与独立 A1、A2 结论（注意其记录的 commit 身份是运行时的 worktree 身份）。

### 4. A1 资产零改动核对（AC10 保留承诺）

```bash
git diff HEAD^...HEAD --stat -- tests/deny_external_io tests/deny_network contracts/ scripts/a1_scope.py pyproject.toml uv.lock
```

输出应为空；`scripts/a2_scope.py` 中 33 项钉住哈希可用 `sha256sum` 对照各文件逐一重算。

### 5. 文档与示例一致性

逐字段对照 `docs/contracts/extraction-config.md` 与 `examples/config/extraction/extraction-example-v1.yaml`，重点：字段必填性表、哈希格式、拒绝清单、`do_formula_enrichment` 默认值与 ADR-0025 表述、以及"配置就绪不证明 fixture gate/资源检查通过"的声明位置。

### 6. 无法直接验证的项（说明替代依据）

- **Docling 冻结值与上游语义的真实一致性**：`extraction.py` 中两个后端的 `pdf_options` 冻结值是否匹配 Docling 2.135.0 实际行为，本仓库离线无法验证（按设计不安装 Docling）。替代依据：`intent/discussions/docling-issue-20-live-probe.md` 的实测记录；如需人工复核，须在该 live-probe 环境（或新建安装了 `docling==2.135.0` 的环境）中检查 `docling/backend/docling_parse_backend.py` 的选项消费点。
- **示例配置中的模型哈希**：`extraction-example-v1.yaml` 的 commit/文件哈希是显式标注的合成值（文件头注释"不是实际模型，禁止用于正式解析"），不对应真实制品，无法也不应对照 HuggingFace 验证。
- **B-1 的 Issue 留痕**：公式默认启用的决定在 Issue #20 页面无记录；本审查不代发评论，需用户自行补记并与 ADR-0025 互链。
