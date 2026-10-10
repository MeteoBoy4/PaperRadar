# V2 可选正文解析器后端：V1 需要预留的接缝

状态：第三节 3.1–3.7 与第四节已全部采纳（3.2/3.3/3.5 及 3.1/3.4/3.6/3.7、第四节均于 2026-10-10 采纳），draft.md 已同步；第四节的公式增强边界已按 Issue #20 实施时的用户明确确认和 ADR-0025 更新为局部候选转写；第五节（V2 演进成本）与第七节（开放问题）明确暂不裁决；不含代码变更。
触发问题：设想 V2 在 Docling 之外接入其他可选 PDF 解析工具，形成独立于其他板块、可插拔的 parser backend 模块，各 backend 统一接入 normalization。V1 的设计、代码架构和实现上有哪些需要提前注意的地方。
日期：2026-10-10。仓库 HEAD：`1841c26754874f560cb2e7a3d314a6f1fe47b5c0`。

参照文件：

- `intent/draft.md` §1.3（明确不进入第一版：draft.md:59"正文解析器自动 fallback"）、§3.4（阶段输入指纹、RuntimeConfigSnapshot 与校准语义基线，draft.md:168–181）、§4.9（Docling 正文提取，draft.md:554–625）、§4.10（Read 资格）、§5 数据表（`tasks` / `task_attempts` / `extraction_artifacts`，draft.md:766–767、801）、§6 制品目录（draft.md:883）、§10 模块边界（draft.md:1333–1340、1353、1359）、阶段 F 验收（draft.md:1700–1710）、§13 fixture registry（draft.md:2004）、§15 第二版以后候选及准入规则（draft.md:2046–2062）
- `CONTEXT.md`「正文提取物」（:252）、「正文提取质量门槛」（:256）、「受限版面内容」（:260）、「精读证据」词条
- ADR-0006（独立事实代替主状态机）、ADR-0008（阶段输入指纹）、ADR-0010（Docling 作为唯一通用正文解析器）、ADR-0012（最小 provider 链）、ADR-0017（源文件与承载分析的制品永久保留）、ADR-0020（用户分级校准相关变更）、ADR-0023（运行配置快照与校准基线分离）
- `AGENTS.md`（范围控制、核心不变量、数据与版本控制、依赖与外部服务）
- 关联讨论：`intent/discussions/docling-issue-20-live-probe.md`（"extraction 配置投影是 #23 校准基线的独立分量"）
- 实现现状：`src/paper_radar` 目前只有 `config / contracts / screening / storage`；`fulltext/` 模块尚未实现，本文讨论的正是落地前的纪律

## 一、结论

V1 设计已经把正确的接缝画出来了：backend 原始制品（`document.json`）与规范制品（`reading.md` + `evidence-map.json`）分离、extraction fingerprint 包含工具链身份、质量门槛针对规范制品断言、失败按可恢复性受控分类。**V2 多 backend 不需要 V1 预建插件系统，只需要 V1 落地 `fulltext/` 时满足五条硬纪律**：

1. `normalize.py`、`evidence.py`、质量门槛代码 **import 不到任何 docling 符号**：它们消费一个内部 canonical 中间结构，`docling_parser.py` 的职责是"Docling adapter：DoclingDocument → canonical 结构"。
2. backend 身份是指纹与数据库里的**结构化字段**（backend_id、backend_version、config_hash、model_artifacts_hash 可空），不是嵌死 "docling" 的字符串拼接；`normalization_version` 保持独立字段——normalize 语义变化提升它、影响所有 backend，backend 变化只影响该 backend。
3. fixture 期望哈希与解析失败记录都 **per-backend** 组织；"永久失败"绑定 backend×指纹，不绑定论文——否则 V2 的 OCR 类 backend 无法识别哪些无文本层 PDF 值得用新 backend 重试。
4. 长期命名中立：制品目录用 `extraction/<backend_id>/<fingerprint>/` 而非 `docling/`；`extraction_artifacts` 表拆结构化 backend 字段；"Docling" 不泄漏进用户可见文案、错误枚举和编排层约束名。
5. backend 选择与配置进入 `RuntimeConfigSnapshot` 的 fulltext（extraction）投影——它已经是 #23 校准语义基线的独立分量；V2 换 backend 是校准相关变更，须按 ADR-0020 由用户分级。

明确不做的（见第四节）：backend 注册表、自动 fallback、backend 间 A/B、按论文挑 backend。draft.md:59 已禁止 V1 做"正文解析器自动 fallback"；多 backend 本身是 V2 能力，接入时必须走 §15 准入规则："任何第二版能力必须说明它改变了哪个领域契约、需要哪些新 fixture，以及是否使既有校准失效"。

## 二、V2 目标形态与 V1 既有设计的关系

V2 目标形态：`fulltext/` 下存在多个可选 parser backend（如 Docling、OCR 类、其他版面解析器），每个 backend 独立产生 backend 原始制品，经同一 `normalize.py` 产出统一规范阅读制品与 evidence map，下游（Read、复用升级摘录、报告）只消费规范制品与质量门槛结果，不感知 backend。

V1 既有设计对这一形态友好的部分，实现时不要走样：

- **制品分离**：§4.9 规定每次成功解析同时保存 `document.json`（backend 特有）与 `reading.md` / `evidence-map.json`（规范契约）。这个分离就是 V2 的接入点。
- **指纹作用域**：ADR-0008 已规定 PDF 变化只失效解析与 Read，不触碰 Screening 指纹；`normalization_version` 独立进入 extraction fingerprint。
- **失败分类语义化**：`extraction_failed_no_text_layer` / `extraction_failed_quality_gate` / `extraction_resource_exhausted` / `extraction_timeout`（draft.md:624）描述的是解析结果语义，不是工具错误码。
- **质量门槛面向规范制品**：阶段 F 验收（draft.md:1700–1710）断言的是正文起点、标题层级、provenance 回放、占位降级，不是"Docling 返回 0"。
- **模块边界**：§10 已规定纯规则模块不导入 Docling SDK（draft.md:1358），`fulltext/normalize.py` 不产生研究结论（draft.md:1365）。

## 三、V1 落地纪律

### 3.1 canonical 中间结构与 adapter 边界（已采纳，2026-10-10；draft 已同步，以下为原始建议文本）

最重要的一条。`normalize.py` 的输入不应是 `DoclingDocument` 类型，而是一个项目内部的 canonical 中间结构：page_no、bbox、charspan、orig/text、标题层级、content layer、受限内容占位等。`docling_parser.py` 定位为 Docling adapter，负责转换与错误映射；V2 新 backend 只需新增一个 adapter。判断标准：normalize、evidence、质量门槛代码 import 不到 docling。

配套要求：**canonical 结构的最低 provenance 契约要显式写明**。阶段 F 验收要求"所有规范块 provenance 在页边界内且 charspan 可回放"（draft.md:1701），CONTEXT.md「精读证据」要求程序验证页码、坐标、字符区间存在。哪些字段是 evidence 回查必需、哪些可选、缺失时如何合法降级，必须落在 canonical 契约里，而不是以 Docling 输出能力为隐性上限。能力不足的 backend 应被质量门槛拒绝，而不是悄悄降低证据质量。

### 3.2 指纹与版本字段（已采纳，2026-10-10；draft 已同步，以下为原始建议文本）

- extraction fingerprint 的输入清单（draft.md:173：PDF SHA-256、Docling/core/parse 版本、PDF 后端、模型制品哈希、完整解析配置、`normalization_version`）实现时落成结构化 backend descriptor，`model_artifacts_hash` 允许为空——部分 backend 无模型制品。
- backend 版本与 `normalization_version` 是独立字段：前者只影响该 backend 的指纹，后者变化使**所有** backend 的旧制品过期并要求重跑全部 fixtures（draft.md:622）。
- 历史语义保持（既有裁决，多 backend 下更明显）：换 backend 产生新指纹、新制品，但不使已有人工决定与既有正式分析失效——分析引用的是当时的 artifact，按 ADR-0017 永久保留。因此 evidence 引用必须携带制品/fingerprint 身份，不能只存裸 evidence ID，否则历史分析的 evidence 无法解析回当时的制品。

### 3.3 质量门槛与 fixture registry 的组织（已采纳，2026-10-10；draft 已同步，以下为原始建议文本）

- 四刊 fixture 断言保持 backend 无关（针对 `reading.md` + `evidence-map`）。这样新 backend 接入即自动接受同一套 gate，"新 backend 必须先过四刊 fixtures"成为机制而不是文档愿望。
- **注意一个 V1 就会踩的矛盾**：draft.md:619 要求"给定固定 PDF 时 `reading.md` 内容哈希与 fixture registry 的期望值一致"。多 backend 下不同 backend 的 `reading.md` 内容大概率不同，registry 期望哈希必须按 per-(backend, fingerprint) 组织（registry 记录本身也应包含 backend/模型版本，draft.md:2004 已要求保存"Docling/模型版本"，落地时字段名取 backend 中立）。现在做对成本为零；做成全局唯一期望值，V2 就是 breaking 改造。

### 3.4 失败语义与尝试预算的作用域（已采纳，2026-10-10；draft 已同步，以下为原始建议文本）

- "永久失败"是 (backend, fingerprint) 上的永久，不是论文上的永久。draft.md:624 写"对当前指纹是永久失败，分别等待 OCR/V2"已经暗示了这一点；实现时解析失败记录与 attempt 预算（同 extraction fingerprint 最多两次，draft.md:767）都必须携带 backend 身份。fingerprint 结构化包含 backend 后，"新指纹重置预算"（draft.md:624）自动覆盖"换 backend"情形。
- 工具错误到受控枚举的映射属于 adapter 职责，不散落在 orchestration。
- `extraction_failed_no_text_layer` 对 OCR 类 backend 的语义会反转（无文本层恰是其主场）——V1 无须处理，但失败记录带 backend 身份是 V2 能处理的前提。

### 3.5 存储布局与表结构（已采纳，2026-10-10；draft 已同步，以下为原始建议文本）

- 制品目录：draft.md:883 写 `artifacts/docling/<extraction_fingerprint>/`，建议 V1 直接用 `artifacts/extraction/<backend_id>/<fingerprint>/`。现在改是零成本，V2 再改是 breaking。（已采纳并同步 draft，见第六节冲突检查。）
- `extraction_artifacts`（draft.md:806"Docling/模型配置、normalization version"）落地时拆为 `backend_id / backend_version / backend_config_hash / model_artifacts_hash / normalization_version` 等结构化列，避免 V2 migration 拆字段。
- backend 的原始输出文件可以 backend 特有（命名、格式），但 parse-manifest、evidence-map 的 schema 必须统一；manifest 中的工具链版本字段同样 backend 中立命名。
- 编排层资源约束按"独占解析资源"抽象：draft.md:348 的 backup 与解析互斥不要实现成 "Docling 锁"；timeout/内存预算作为 per-backend 配置进入 manifest 与指纹。

### 3.6 配置快照与校准基线（已采纳，2026-10-10；draft 已同步，以下为原始建议文本）

backend 选择与配置进入 `RuntimeConfigSnapshot` 的 extraction 投影。正文制品是条件式复用升级与摘录产生的共同输入，按 draft.md:181，该投影属于校准语义基线（`docling-issue-20-live-probe.md` 已确认"extraction 配置投影是 #23 校准基线的独立分量，不能再次嵌入 reuse/Read 配置投影"）。因此 V2 换 backend 会形成待分级校准变更（ADR-0020），且因为摘录与升级输入变化，大概率 major。V1 实现快照投影时不要把"Docling 配置"硬编码为投影唯一成员，而要留可枚举的 extraction 投影。

### 3.7 依赖可选化与测试替身（已采纳，2026-10-10；draft 已同步，以下为原始建议文本）

- Docling slim 本身很重（实测 18–51s、峰值 2.5–4.6GB，ADR-0010）。V1 把重解析依赖放进 `paper-radar[docling]` extra，常规离线测试不安装也能跑。
- 建立一个 **fake parser backend** 测试替身：输入固定 PDF fixture，输出预生成 canonical 结构。它同时服务于三件事——常规测试离线化（AGENTS.md 依赖规则）、normalize/gate/evidence/fingerprint 的 backend 无关性验证、以及 V2 新 backend 的验收 harness。
- backend 未安装/未启用时给出可操作错误信息（AGENTS.md"错误信息应说明可操作的具体原因"）。

## 四、明确不在 V1 做的事（已同意，2026-10-10；draft §4.9 开篇与 §十 技术栈已体现）

- 不做 backend 注册表、自动 fallback、backend 间 A/B 对比、按论文挑 backend。draft.md:59 明确"正文解析器自动 fallback"不进第一版；AGENTS.md 范围控制禁止 V1 引入 provider 自动 fallback。V1 只留**选项**（中立命名 + 干净接缝 + per-backend fixture 结构 + backend 无关失败语义），不实现多 backend **机制**。
- 不为将来多 backend 提前造第二套规范 schema：canonical 结构以 §4.9 已定义的制品契约为准，由权威 Pydantic schema 生成，不维护手写副本（AGENTS.md Frozen Contract 规则）。
- V1 的单 backend 选择与公式候选能力分别裁决：Docling 仍为唯一正文解析器，OCR、代码/图片/图表增强、远程与外部插件关闭。Issue #20 实施时用户明确允许并默认启用 CodeFormulaV2 局部公式候选转写（[ADR-0025](../../docs/adr/0025-allow-local-formula-candidates-with-source-review.md)），公式源文本、候选与 PDF 定位分离保存并通过裁切人工核查；本票仅登记配置，实际解析与核查留待后续实现，未复核候选不作为精确公式证据。

## 五、V2 接入时的演进成本清单（预先记账，暂不裁决）

按 draft §15 准入规则，V2 接新 backend 时至少要回答并完成：

1. **新 ADR** supersede ADR-0010（其标题即"Docling 作为唯一通用正文解析器"）；ADR-0012 的最小 provider 链表述一并复核。
2. **CONTEXT.md 词条同步**：「正文提取物」现写死"由 Docling 生成"（:252）；「受限版面内容」已预告"第二版可以单独评估 OCR 或 AI Agent 精确解析，不能静默改变第一版证据契约"——公式占位、表格数值不得为关键证据的证据契约不随 backend 能力自动放开，需要独立 ADR 与校准变更，不与 backend 接入捆绑。
3. **draft.md §4.9 同步**：标题与正文从"Docling 正文提取"改为 backend 中立的 extraction 章节。
4. **校准变更分级**：换/增 backend 影响摘录与复用升级输入，属校准语义基线变化，走 ADR-0020 用户分级；大概率 major（关闭门禁，等待基于既有人工标签重算或新校准）。
5. **fixture 重跑**：新 backend 先过同一套四刊 fixtures（含中英文覆盖），registry 增加 per-backend 期望；既有 Docling fixtures 不受影响（指纹未变）。
6. **清理计划复核**：ADR-0017 的"验证可重建后才能清理"判断要按 backend 配置逐一成立，被分析/建议/校准引用的制品仍永不清理。
7. **准入三问**：改变了哪个领域契约、需要哪些新 fixture、是否使既有校准失效。

## 六、与既有裁决的冲突检查

- draft.md:59（正文解析器自动 fallback 不进 V1）：无冲突。本稿建议的多 backend 是 V2 显式配置选择 + 校准分级；若 V2 想按论文自动挑选 backend，那是新的裁决点，接近被禁的自动 fallback 语义，须单独立 ADR。
- ADR-0010（Docling 唯一正文解析器）：无冲突。V1 行为不变；V2 接入时以新 ADR 显式取代，符合"有意偏离既有架构时应新增 ADR"。
- draft.md:883（`artifacts/docling/` 目录）与 draft.md:806（"Docling/模型配置"字段）：**已解决**。2026-10-10 采纳 3.5 节，draft.md 已同步为 backend 中立表述：§6 目录树改为 `artifacts/extraction/<backend_id>/<extraction_fingerprint>/`，§4.9 制品布局与 parse-manifest 字段同步，§5.5 `extraction_artifacts` 拆为结构化 backend 列，§4.1 编排互斥改为"高内存正文解析"；V1 `backend_id` 固定为 `docling`。
- draft.md:619（reading.md 哈希与 registry 期望一致）：**已随 3.3 采纳同步**（2026-10-10）。§4.9 期望值改为"给定固定 PDF 与同一 backend/解析配置时，与 registry 中按 backend 分别登记的期望值一致"；§13.2 registry 字段改为 backend 中立命名并按 backend 分别保存期望哈希；阶段 F 验收行同步为"固定 PDF 在同一 backend 下与该 backend 的 registry 期望一致"。
- §15 V2 候选清单：现有清单只列了 OCR 与 AI Agent 精确解析，未显式列"其他可选正文解析 backend"；二者高度相关（OCR backend 就是第一个候选的新 backend），V2 规划时合并考虑即可，无须现在改 draft。

## 七、开放问题（留给 V2 规划，暂不裁决）

1. V2 的 backend 选择是"用户显式全局选择"还是"按输入特征路由"？后者带自动 fallback 语义，需要独立裁决（见第六节第一条）。
2. 多 backend 并存时"当前制品"的唯一性：建议维持"每论文每 backend 至多一个当前制品、全局当前唯一（按配置选定的 backend）"，并行双 backend 制品只作为校准/评估期例外。这是 V2 契约设计，V1 不预设。
3. 新 backend 无法提供 bbox 或 charspan 时，evidence 程序验证是降级还是拒绝：取决于 canonical 最低 provenance 契约（3.1）的裁决，V1 落地时就应明确，避免 V2 被迫放宽证据规则。

## 附：如果只记五句话

1. `normalize.py` / `evidence.py` / 质量门槛代码里 import 不到 docling。
2. 指纹和数据库里 backend 身份是结构化字段，`normalization_version` 独立。
3. fixture 期望哈希和失败记录都 per-backend；"永久失败"绑定 backend×指纹，不绑定论文。
4. 目录和表名用 `extraction/<backend>`，别让 "docling" 泄漏进长期命名。
5. backend 选择进 RuntimeConfigSnapshot 的 extraction 投影，并意识到它属于校准语义基线。
