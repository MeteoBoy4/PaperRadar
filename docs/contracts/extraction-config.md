# 正文提取配置（A2-05 / Issue #20）

`settings.extraction` 缺失或 `null` 时合法未配置；非空声明版本选择相邻
`config/extraction/<version>.yaml`。权威类型为 `paper_radar.config.extraction.Extraction`，
使用与其余材料相同的严格 YAML、check/compile/load、版本登记和事务。
只登记身份和配置，不安装 Docling、下载模型、检查本机文件或执行 PDF 解析。

初始候选遵循实测讨论 §5、§7.4 第 1–2 项：pypdfium2、Egret medium、
TableFormer accurate，并按用户确认和 ADR-0025 默认启用 CodeFormulaV2 局部公式候选。
这些选择尚需阶段 F 四刊 fixture、重复确定性与资源检查，配置就绪不证明运行就绪。

## 顶层字段

| 字段 | 必填性、默认值与约束 |
| --- | --- |
| `version` | 必填声明标签，格式同 Profile；必须与 selector 完全相同。 |
| `toolchain` | 必填，仅支持 `docling-2.135.0-cpu-v1`，从项目受控清单选择整个组合。 |
| `pdf_backend` | 可省略，默认 `pypdfium2`；另允许显式 `threaded_docling_parse`，不自动 fallback。 |
| `models` | 必填严格对象；必填 `layout`、`table`；公式开启时必须有 `formula`，关闭时必须省略或写 `null`。 |
| `policy` | 可省略或 `{}`，补全下表的显式有效值；`null`、自由 options、未知字段拒绝。 |
| `normalization_version` | 必填代码受控 `NormalizationVersion.V1`（`v1`），非文本和未知算法版本拒绝。 |

超时、内存/峰值、线程/批量/队列、模型本机目录、password、凭据及凭据引用均无 A2
消费者，任何层级出现时按未知字段拒绝并脱敏。PDF 后端包版本从工具链展开，不接受
可独立矛盾的 `backend_version`、`docling_parse_version` 或手填全局模型哈希。
不接受 excerpt selector、Read chunking 或 reuse/Read 配置嵌套。

## 受控工具链

唯一权威是包内 `config/extraction_toolchain.py` 的不可变版本清单：
`docling-slim=2.135.0`、`docling-core=2.101.1`、`docling-ibm-models=4.0.3`、
`pypdfium2=5.14.0`、`torch=2.14.1+cpu`、`torchvision=0.29.1+cpu`、
`transformers=5.19.0`；threaded 路线另消费 `docling-parse=7.22.2`。
`docling` 是转换器名称，实际实现发行包为 `docling-slim`；core 是文档数据模型，
parse 是所选 PDF 后端包。pypdfium2 路线不把未消费的 parse 包塞入语义；threaded
路线同时使用 pypdfium2 的 PDF 渲染/回查能力。版本不能由用户分别自由填写。

这些版本来自已保存的实测环境，仅表示受支持声明组合，不证明生产最小 slim 安装
兼容或 fixture 已通过。本票不新增解析依赖，当前项目执行环境仍以 `uv.lock` 为准。
未来新增工具链须创建新的受控清单身份，保留旧组合。编译将实际消费的
`backend_id`、`backend_version`、`component_versions` 与完整有效 `backend_config`
展开随快照保存；load 从 SQLite 原材料重新校验与存档的组合一致，漂移拒绝，
不能静默用新清单或新默认解释旧记录。

## 按启用阶段冻结模型文件

每个模型必填 `commit_sha` 与非空 `files`。commit 是完整 40 位小写十六进制 SHA；
每项 file 只有必填 `path`、`sha256`，后者为完整 64 位小写 SHA-256。
path 是仓库内规范 POSIX 相对路径，不能含绝对路径、`.`/`..`、空段、反斜杠、
冒号或空白/控制字符；它是制品身份，不能作为本机目录。
不联网确认 repo/commit，不读取/哈希本机文件；tag/main 不能代替不可变 commit。
清单按路径排序、重复路径拒绝，以下实际推理文件必须完整且不多不少。

| 阶段 | 模型标识 / 仓库 / 策略默认值 | 必需文件（相对于模型仓库） |
| --- | --- | --- |
| layout | `model_id: layout_egret_medium`；`repo_id: docling-project/docling-layout-egret-medium`；`engine: transformers`，均可省略、只接受该固定值 | `config.json`、`model.safetensors`、`preprocessor_config.json` |
| table | `model_id: docling_tableformer`；`repo_id: docling-project/docling-models` 固定且可省略；`mode` 默认 `accurate`，也支持显式 `fast` | `model_artifacts/tableformer/<mode>/tableformer_<mode>.safetensors`、同目录 `tm_config.json` |
| formula | `model_id: CodeFormulaV2`；`repo_id: docling-project/CodeFormulaV2`；`engine: transformers`；`torch_dtype: float32`；`expansion_factor: 0.18`，均可省略、只接受固定值 | `added_tokens.json`、`chat_template.json`、`config.json`、`generation_config.json`、`model.safetensors`、`preprocessor_config.json`、`processor_config.json`、`special_tokens_map.json`、`tokenizer.json`、`tokenizer_config.json`、`vocab.json` |

表格 mode 只在 table 槽登记一次，路径必须与其一致；cell matching 固定在 policy。
固定模型 preset/repo/engine 可以省略输入，但有效值不会从上游 options 获取。
commit 和文件哈希没有假默认值，不能省略；A2 只验证声明格式和完整性，不证明所填
字节与 repo 或 mode 的实际内容匹配。关闭的 OCR/图片/代码/全页 VLM 模型不接受为槽。
公式关闭时不能保留未消费的公式模型声明，也不把它加入语义。

## 固定有效 policy

| 字段 | 编译后有效值 |
| --- | --- |
| `device`、`paper_execution` | `cpu`、`serial`（论文之间串行；内部线程不在本票配置） |
| `do_formula_enrichment` | 默认 `true`；允许显式 `false`，与 formula 槽一致 |
| `do_table_structure`、`do_cell_matching`、`heading_hierarchy`、`use_reading_order_separators` | 固定 `true` |
| `do_ocr`、`do_code_enrichment`、`do_picture_classification`、`do_picture_description`、`do_chart_extraction` | 固定 `false` |
| `enable_remote_services`、`allow_external_plugins`、`trust_remote_code`、`formula_load_in_8bit` | 固定 `false` |
| `keep_empty_clusters`、`force_backend_text`、`generate_page_images`、`generate_picture_images`、`generate_table_images` | 固定 `false` |
| `json_image_mode`、`markdown_image_mode` | 固定 `placeholder`，不嵌入 base64 图片 |
| `preserve_provenance`、`preserve_source_text`、`preserve_content_layer`、`separate_formula_source`、`formula_pdf_crop_review` | 固定 `true` |
| `formula_evidence` | 固定 `candidate_requires_pdf_review` |

固定开关均可省略，输入只允许明确小写布尔；数字 `0/1`、布尔文本和禁止值拒绝。
这是封闭策略，不开放任意 Docling options 调参。所选工具链冻结其余内部行为；
所选 PDF 后端的有效选项也归档：pypdfium2 无额外可调语义选项；threaded 固定
`enforce_same_font=true`、`include_bitmap_images=false`、`render_pages=true`、
`render_scale=1.0`。不要求 pypdfium2 填写其不消费的 threaded 参数。

公式增强只产生待核查候选。后续 adapter 必须将 orig、生成 text 和区域定位分开，
保留源 charspan，支持 PDF 裁切核查；生成字符不冒充逐字符 PDF 事实。未核查公式
不得支持主要发现、评分和复用建议；无法转写仍提供明确定位占位。本票不实现这些
解析、canonical、evidence 或人工核查功能，也不将配置开关当作门禁通过。

## 公共语义与历史

`RuntimeConfigSnapshot.extraction` 为 `ExtractionSemantics | None`，是不可变对象：
`backend` 的中立身份与组件版本、按阶段排列的 `model_artifacts`（冻结 file 元组）、
`backend_config_json` 的规范 JSON、`normalization_version`。另提供自动派生的
`backend_config_hash` 与 `model_artifacts_hash`（无模型的未来 backend 可为 `None`）；
它们是配置内容身份，均不是包含 PDF 的 extraction fingerprint。
声明 version、toolchain 标签、原 YAML 哈希和本机路径不进入纯语义。

完整快照记录 selector、原字节/哈希、声明标签和补全后的配置。更换声明版本、注释或
文件排列可以生成不同快照而保持相同语义；实际 backend、模型字节或策略变化才改变
对应语义。`normalization_version` 是受控算法身份，不参与独立字节登记，不能作为
普通声明标签剔除；同算法版本下的代码漂移仍需评审和冻结纪律约束，A2 无法自动检测。

extraction 配置就绪只要求所选材料合法且完整，不依赖 Profile、LLM、PDF、其他阶段、
本机模型或 fixture gate。无选择时为 `not_ready` / `extraction_config`；有选择但
文件或字段缺失时是非法配置，不能保存假就绪。独立 extraction 语义整体是 A2-08
校准基线的一个分量，不嵌入 reuse/Read；A2-08 的投影、diff 和校准门禁不在本票实现。
V1 `backend_id=docling`，不预建 backend 注册表、自动 fallback、A/B 或论文路由。
后续 artifact 目录、失败记录、fixture 期望与规范化接缝仍遵循 draft §4.9 的中立契约。

参见 [运行配置服务](runtime-config.md)、[ADR-0025](../adr/0025-allow-local-formula-candidates-with-source-review.md)
和 [`settings-extraction.yaml`](../../examples/config/settings-extraction.yaml)。示例是合成
工程验收材料，哈希不代表真实模型文件，不能用其开展正式校准或 PDF 解析。
