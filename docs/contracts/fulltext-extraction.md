# 规范正文与持久证据

## 用途与范围

`paper_radar.fulltext` 将受控 parser 的完整 canonical 文档生产为 extraction 制品，
并仅凭持久成员重建 `ReadContext` 和逐字源片段。它不加载 Docling SDK。

公共入口为 `paper_radar.fulltext.artifacts.FulltextArtifacts(ArtifactStore)`：

- `publish(document, *, extraction_fingerprint, backend_config_hash, model_artifacts_hash,
  elapsed_seconds, peak_memory_bytes, document_json=None, warnings=())` 返回
  `PublishedExtraction(artifact_id, identity, quality, statistics)`。
- `load(artifact_id, *, expected_identity, expected_language="zh")` 返回完整校验后的
  `LoadedExtraction`，含 `context`、`reading`、自动质量和统计。语言只接受 zh/en。
- `lookup(artifact_id, identity, evidence_id)` 返回该证据的有序 `SourceSlice` 元组。
  每个切片由持久 `orig[start:end]` 逐字获得。

`quality.passed` 只表示自动检查通过，不授予人工版式、experiment_document_gate 或
formal_gate。生产者保存完整但失败的制品供审计，`load` 拒绝其消费并在错误上返回质量报告。

## 规则

### canonical 权威

唯一权威是 `paper_radar.fulltext.canonical` 的 Pydantic 类型，全部禁止未知字段并冻结：

| 类型 | 内容 |
| --- | --- |
| `CanonicalDocument` | format_version=1、conversion_status、pages_complete、has_text_layer、pages、blocks |
| `CanonicalPage` | 原 PDF 正页码、有限正 point 尺寸、top_left/bottom_left 原点 |
| `CanonicalBlock` | parser ref、显式文档阅读路径 order、label、逐字 orig、parser text、parent_ref、heading_level、content_layer、role、generated_text、unreliable、formula_mode、provenance |
| `CanonicalProvenance` | 原 PDF page_no、bbox=(x0,y0,x1,y1)、orig 的 code-point 半开 charspan、bbox 原点 |

`order` 是 parser 明确提供的阅读路径；SDK 容器枚举顺序和 ref 名称不决定语义顺序。
不同块的 ref/order 必须唯一，order 分量非负；parent_ref 必须属于同文档且无循环。
`role=source/generated/placeholder`、`content_layer=body/furniture/background` 分开表达。
公式类别为 display/inline/unknown；unknown 不冒充已识别的行内或行间公式。
`orig` 是证据唯一字符源，`text` 只保留 parser 的展示值，`generated_text` 单列候选。
页码不重编号。不同 bbox 原点在重建上下文时按原页高转换，持久 map 保留原原点和坐标。

入口没有题名、DOI、摘要或数据库回调。normalization 只消费文档、布局、顺序和显式分类；
不会以外部元数据补救封面识别。C1 单样本失败仍阻断 B，扩大输入须另行升格式并获裁决。

### normalization v1

1. 按 `order` 字典序排序。排序后的第 N 块使用六位起始序号 `b000001`，
   源块用对应 `s000001`，可引用证据用对应 `e000001`。序号以全部 canonical 块为基准，
   因而非证据块也占序号。引用一律同时绑定正文消费身份三元组，裸 ID 不可跨正文使用。
2. `formula → formula`、`table → table`；其余 label 的源块映射为 text。
   `picture/chart` 只展示图片占位，不能取得 evidence。caption、footnote、list_item、
   title、section_header 等文本 label 保留原 label，以 text 源规则处理。
3. 从第一原页起连续检查封面/授权页。页面内任一源块经 strip/casefold 后等于
   `repository cover sheet`、`cover sheet`、`license`、`licence`、
   `copyright and permissions`、`授权许可`、`版权声明` 即视为该类页；遇首个无信号页即停止。
   其源块保留在 map，阅读文本及 evidence 排除它们。
4. `page_header/page_footer/page_number` 或 furniture/background layer 不进入正文 evidence。
   单 provenance 的 text 块若位于页面上下 8% 边缘，且 strip 后完全相同的文本出现于
   至少两个不同原页，也作为页眉页脚排除。不用题名/DOI 猜测重复文本。
5. title/section_header 的首个层级修复为 1，后续至少 1、至多比前一个标题深一级；
   parent 层级关系保存在 map。其他文本保留原文与顺序，不静默截断正文。
6. 每个非排除 source 块提供一条 evidence，粒度是完整源块；一条 evidence 可有多条跨页
   provenance。每个非空白 orig 字符必须被其 provenance 覆盖，每个切片必须非空白；
   不拼接、清洗或重写 orig，不用生成候选填补未覆盖字符。
7. 无源公式/图片显示 `[公式不可用，见 PDF 第 N 页]` / `[图片不可用，见 PDF 第 N 页]`，
   仍须保留有效页面/bbox 和空 charspan=(0,0)。公式候选另以“生成候选，非证据”展示。
   generated/placeholder、图片、空 orig 都不取得 evidence ID；只给合法源块插入
   `[evidence:e000001]` 锚点。源或候选本身含 `[evidence:` 时将冒号转义为 `\:`，防止伪造锚点。
8. `paper_radar.content_reliability.is_unreliable(text, *, declared=False)` 是共享规则：
   parser 已标记，或包含 U+FFFD、Unicode Cs/Co、除 tab/CR/LF 外的 Cc 即 unreliable。
   普通中英文、数学符号不据此猜为不可靠。U+FFFD 同时导致自动质量 text_integrity 失败；
   私用字符只标记 unreliable，由对应 Read 规则处理其降级。

v1 的真实冻结以 smoke 结论为输入；首次真实 B 制品之后，任何上述语义变化必须升 normalization v2，
改变 extraction 身份，不能沿用 v1 改写历史制品。

### 四角色与非循环编码

复用 artifact 格式 1 的完整四角色，不增加角色、不修改正文消费身份三元组：

| 角色 | 内容与用途 |
| --- | --- |
| document | 调用方给定的不含内联二进制的原始 DoclingDocument JSON，仅供审计；未给定时保存 canonical JSON 审计记录 |
| evidence_map | 自包含页面、逐字 orig/text 源块、源类型/可靠性、全部 provenance、阅读块/层级/排除依据、生成候选和 evidence |
| reading | 按上述规范生成的模型呈现 Markdown |
| manifest | normalization、提取指纹、reading/evidence/document 成员哈希、既有 backend_config_hash/model_artifacts_hash、耗时/峰值/警告 |

JSON 成员编码为 UTF-8、键按 Unicode 字典序、ensure_ascii=False、separators=(',', ':')、
allow_nan=False，无 BOM、缩进或末尾换行；数组顺序是已规范化的语义顺序。
reading 是 UTF-8、块间两个 LF、末尾一个 LF。
三个身份哈希值仅存在于 manifest 与调用方的数据库登记，reading/evidence_map 不写入任一
最终三元组值。先生成 reading/evidence_map，再计算其字节 SHA-256，再写 manifest；
manifest 不包含自身最终成员哈希。artifact_id 继续由 store 的四角色清单决定。
因此 orig 的任何字节变化都改变 evidence_map_sha256；无需 document 或 SDK 重建源字符。
调用方明确提供的三元组是回查的权威期望，不能只凭同一 extraction 指纹接受另一正文。
manifest 的测量变化可改变 artifact_id，而不改变 reading/evidence_map 或 evidence ID。

### 自动质量与统计

转换 partial/failure、pages_complete=False 或无页面时，在规范制品产生前返回
conversion_incomplete，无质量事实、无制品登记；后续任务将其映射为提取失败与 quality_absent。
完整制品的检查返回安全字段路径及精确 `QualityFailure`，不含源片段：

| 检查 | 失败值 |
| --- | --- |
| 无可靠文本层或无非空白源字符 | pdf_text_layer |
| 没有可引用正文源块 | body_boundary |
| 全部源块（含排除块）与占位定位、字符覆盖不可回放 | evidence_replay |
| reading 与规范 map 呈现不同 | content_identity |
| generated/placeholder 带 orig 源块，或无 orig 的源展示冒充源字符 | source_generated_separation |
| 任一成员含 data URI base64 或 base64/image_data JSON 字段 | embedded_binary |
| U+FFFD、无效 UTF-8 或 JSON 编码损坏 | text_integrity |

JSON 转义先解码再检查，不能用 `\u0064ata:...` 或 `\ufffd` 绕过检查。
资格 DTO 透传失败值，中文指引由 `eligibility.presentation.quality_failure_guidance` 提供；
`EligibilityReason` 闭集保持不变。

`statistics.formula` 按 display/inline/unknown 返回 total、with_parent_source、placeholder_only。
with_parent_source 要求 `label=formula` 的源 orig 非空，且页码/bbox/charspan 全部合法、
切片非空、非空白 orig 全覆盖；其余计入 placeholder_only（含损坏定位）。
inline 总数为零只表示 canonical 未给独立 inline item，不代表不存在行内公式。
`statistics.member_bytes` 返回四成员各自 UTF-8 字节体积；这些计数可由重新读取制品重现。
合成材料只验证统计接口，不证明真实覆盖；真实分类/覆盖率及 SDK 保真由 smoke 和 F 验收。

## 错误与拒绝

- `conversion_incomplete`、`ambiguous_reading_order`、`unknown_parent`、`invalid_hierarchy`：未产生可评估的完整制品。
- `invalid_members`、`invalid_encoding`：Schema 或固定编码不符。
- `identity_mismatch`：三元组、manifest 或 document 审计成员哈希不符。
- `quality_failed`：完整制品自动检查失败，错误附 `AutomaticQuality.issues`。
- `unknown_evidence`：回查目标不属于该正文。
- 底层缺成员、篡改、登记损坏沿用 ArtifactError 的安全原因；读取失败不修补原件。

## 不提供／不证明

不提供 SDK 执行、PDF/版本关联、提取任务或唯一成功索引、预算、人工版式记录、Read 执行和
正式准入；后续消费者见[Body/B](../roadmap.md#module-body)。不实现 PDF 裁切或新增裁切角色。
备份只提供通用成员闭包；本服务的冷进程重建不证明 PDF 源字节真实性、四刊质量、实际模型调用、
真实公式覆盖、代表性资源阈值或正常生产 Read。

## 相关

- [制品存储](artifact-store.md)、[阶段输入 C1](stage-inputs.md#c1-封面识别的输入边界)、
  [Read 校验](read-validation.md)、[资格与可见性](eligibility-visibility.md)、[备份恢复](backup-restore.md)。
- [ADR-0041](../adr/0041-self-contained-evidence-map.md)、[D1 覆盖](../verification/issue-156-fulltext-delivery.md)。
- 依据：[#156](https://github.com/MeteoBoy4/PaperRadar/issues/156)、
  [#155 裁决链](https://github.com/MeteoBoy4/PaperRadar/issues/155)。
