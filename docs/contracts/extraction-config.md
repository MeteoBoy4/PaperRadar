<a id="正文提取配置a2-05--issue-20"></a>

# 正文提取配置

`settings.extraction` 缺失或 `null` 时合法未配置；非空声明版本选择 settings 所在目录下的
`extraction/<version>.yaml`（通常为 `config/extraction/<version>.yaml`）。权威类型为
[`paper_radar.config.extraction.Extraction`](../../src/paper_radar/config/extraction.py)。
公共 check/compile/load 的数据库前置、严格 YAML、版本登记与原子事务由
[运行配置服务](runtime-config.md)定义。本契约定义 extraction 材料、有效策略与只读语义；
只登记身份和配置，不安装 Docling、下载模型、核验本机模型文件或执行 PDF 解析。

默认选择 pypdfium2、Egret medium、TableFormer accurate，以及 CodeFormulaV2 局部公式候选。
配置就绪不证明四刊 fixture、重复确定性、资源检查或运行就绪。

## 顶层字段

| 字段 | 必填性、默认值与约束 |
| --- | --- |
| `version` | 必填声明标签，格式同 Profile；必须与 selector 完全相同。 |
| `toolchain` | 必填，仅支持 `docling-2.135.0-cpu-v1`，从项目受控清单选择整个组合。 |
| `pdf_backend` | 可省略，默认 `pypdfium2`；另允许显式 `threaded_docling_parse`，不自动 fallback。 |
| `models` | 必填严格对象；必填 `layout`、`table`；公式开启时必须有 `formula`，关闭时必须省略或写 `null`。 |
| `policy` | 可省略或 `{}`，补全下表的显式有效值；`null`、自由 options、未知字段拒绝。 |
| `normalization_version` | 必填代码受控 `NormalizationVersion.V1`（`v1`），非文本和未知算法版本拒绝。 |

超时、内存/峰值、线程/批量/队列、模型本机目录、password、凭据及凭据引用均不是本配置的
输入字段，任何层级出现时按未知字段拒绝并脱敏。PDF 后端包版本从工具链展开，不接受
可独立矛盾的 `backend_version`、`docling_parse_version` 或手填全局模型哈希。
不接受 excerpt selector、Read chunking 或 reuse/Read 配置嵌套。

## 受控工具链

唯一权威是包内 [`config/extraction_toolchain.py`](../../src/paper_radar/config/extraction_toolchain.py)
的不可变版本清单：
`docling-slim=2.135.0`、`docling-core=2.101.1`、`docling-ibm-models=4.0.3`、
`pypdfium2=5.14.0`、`torch=2.14.1+cpu`、`torchvision=0.29.1+cpu`、
`transformers=5.19.0`；threaded 路线另消费 `docling-parse=7.22.2`。
`docling` 是转换器名称，实际实现发行包为 `docling-slim`；core 是文档数据模型，
parse 是所选 PDF 后端包。pypdfium2 路线不把未消费的 parse 包塞入语义；threaded
路线同时使用 pypdfium2 的 PDF 渲染/回查能力。版本不能由用户分别自由填写。

这些版本仅表示受支持声明组合，不证明生产最小 slim 安装兼容或 fixture 已通过。
项目没有 Docling extra；此配置边界不提供解析依赖，执行环境依赖由
[`pyproject.toml`](../../pyproject.toml) 与 [`uv.lock`](../../uv.lock) 声明和锁定。
编译将所选组合的 `backend_id`、`backend_version`、`component_versions` 与完整有效 `backend_config`
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
commit 和文件哈希没有假默认值，不能省略；配置校验只验证声明格式和完整性，不证明所填
字节与 repo 或 mode 的实际内容匹配。关闭的 OCR/图片/代码/全页 VLM 模型不接受为槽。
公式关闭时不能保留未消费的公式模型声明，也不把它加入语义。

## 固定有效 policy

| 字段 | 编译后有效值 |
| --- | --- |
| `device`、`paper_execution` | `cpu`、`serial`（声明论文之间串行；内部线程不属于本配置） |
| `do_formula_enrichment` | 默认 `true`；允许显式 `false`，与 formula 槽一致 |
| `do_table_structure`、`do_cell_matching`、`heading_hierarchy`、`use_reading_order_separators` | 固定 `true` |
| `do_ocr`、`do_code_enrichment`、`do_picture_classification`、`do_picture_description`、`do_chart_extraction` | 固定 `false` |
| `enable_remote_services`、`allow_external_plugins`、`trust_remote_code`、`formula_load_in_8bit` | 固定 `false` |
| `keep_empty_clusters`、`force_backend_text`、`generate_page_images`、`generate_picture_images`、`generate_table_images` | 固定 `false` |
| `json_image_mode`、`markdown_image_mode` | 固定 `placeholder`，不嵌入 base64 图片 |
| `preserve_provenance`、`preserve_source_text`、`preserve_content_layer`、`separate_formula_source`、`formula_pdf_crop_review` | 固定 `true` |
| `formula_evidence` | 固定 `candidate_requires_pdf_review` |

上述固定字段均可省略；布尔字段只接受明确小写 `true`/`false`，数字 `0/1`、
引号内布尔文本和禁止值拒绝；文本字段只接受表中固定文本。
这是封闭策略，不开放任意 Docling options 调参，不读取上游 options 的当前默认值。
所选 PDF 后端的有效选项也归档：pypdfium2 无额外可调语义选项；threaded 固定
`enforce_same_font=true`、`include_bitmap_images=false`、`render_pages=true`、
`render_scale=1.0`。不要求 pypdfium2 填写其不消费的 threaded 参数。

公式策略登记的是待核查候选约束，不是精确恢复或人工复核事实。配置开关不使未核查公式
取得支持主要发现、评分或复用建议的资格，也不证明 orig、候选 text、区域定位与源 charspan
已分离保存或可裁切回查。源/候选分离、生成字符不得冒充源字符及转写失败定位占位的要求见
[规格 §4.9](../../intent/draft.md#49-docling-正文提取)；本配置不执行这些解析与证据功能。

## 公共语义与历史

`RuntimeConfigSnapshot.extraction` 为 `ExtractionSemantics | None`，是不可变对象：
`backend` 的中立身份与组件版本、按阶段排列的 `model_artifacts`（冻结 file 元组，
`stage` 为公共 `ModelStage` enum：`layout` / `table` / `formula`）、
`backend_config_json` 的规范 JSON、`normalization_version`。另提供自动派生的
`backend_config_hash` 与 `model_artifacts_hash`；
它们是配置内容身份，均不是包含 PDF 的 extraction fingerprint。
V1 必需 layout/table 模型，因此 `model_artifacts_hash` 始终为 SHA-256；`None` 仅对应
backend 中立语义对象的空模型清单表示，不开放 V1 的无模型解析配置。
声明 version、toolchain 标签、原 YAML 哈希和本机路径不进入纯语义。

完整快照记录 selector、原字节/哈希、声明标签和补全后的配置。已登记版本的任何字节
变化（包括注释或文件排列）均拒绝，必须新建声明版本并切换 selector；新版本可以生成
不同快照而保持相同语义。backend、模型 commit/文件身份、有效策略或规范化算法身份的
变化改变对应语义。`normalization_version` 是受控算法身份，不参与独立字节登记，不能
作为普通声明标签剔除；同算法版本下的代码漂移仍靠评审和冻结纪律约束，配置服务不自动检测。

extraction 配置就绪只要求所选材料合法且完整，不依赖 Profile、LLM、PDF、其他阶段、
本机模型或 fixture gate。无选择时为 `not_ready` / `extraction_config`；有选择但
文件或字段缺失时是非法配置，不能保存假就绪。独立 extraction 投影属于校准基线分量，
不嵌入 reuse/read；投影与基线的详细身份规则见[单快照重建与 diff](config-projections.md)。
与 PDF 内容组合的输入描述和拒绝边界见[阶段输入契约](stage-inputs.md#extraction-格式-1-与正文来源消费义务)，
配置内容哈希不能代替实际正文/evidence 成员的内容身份。
V1 `backend_id=docling`，不提供 backend 注册表、自动 fallback、A/B 或论文路由。

## 校验错误

`do_ocr: true` 触发受控原因 `v1_ocr_disabled`，CLI/公共服务将其映射为字段路径与
“V1 不支持 OCR；请将 do_ocr 设为 false 或省略；扫描稿需等待 V2”。非布尔 OCR
值仍属于类型或选择错误，不能被误报为已启用禁止能力。其他校验使用脱敏原因，
错误不回显原始值、Pydantic 异常 message、input 或 context。
必填、未知字段与受控值拒绝分别使用“必填字段缺失”“未知字段”“类型错误或取值不受支持”
等中文指引；文本或列表类型错误也可显示“必须为文本”“必须为列表”。模型清单一致性等
未单列校验错误使用“字段缺失、类型错误或不受支持”。只显示首个校验错误；字段错误通常
定位到 `extraction.<字段路径>`，公式开关与模型槽不一致可定位到 `extraction.`。
读取失败、声明版本不匹配、已登记不同字节、历史损坏与数据库失败均为 `ConfigError`，
公共 CLI 的 check/compile 失败返回 2。登记和回放的完整拒绝与恢复规则见
[运行配置服务](runtime-config.md)；历史从 SQLite 原材料回放，不读当前文件、损坏不回退。

## 不提供／不证明

- 不安装或核验解析依赖与模型字节，不证明最小 slim/CPU 组合或 Python 兼容；承接见
  [Extra](../roadmap.md#module-extra)。
- 不执行 parser/canonical/normalize/evidence、PDF 裁切或人工核查，不提供正文质量或消费资格；
  最小生产切片见 [Body](../roadmap.md#module-body) 与 [B](../roadmap.md#module-b)，
  四刊正文与摘录 fixture、资源和确定性门槛见
  [F](../roadmap.md#module-f)。
- 不提供校准门禁或自动精读许可；承接见 [D](../roadmap.md#module-d)。
- [`settings-extraction.yaml`](../../examples/config/settings-extraction.yaml) 及其
  [模型声明](../../examples/config/extraction/extraction-example-v1.yaml)是合成工程材料，
  文件哈希不代表真实模型字节，不能用于正式校准或 PDF 解析。

## 相关

依据：[#20](https://github.com/MeteoBoy4/PaperRadar/issues/20)、
[配置研究 §5](../../intent/discussions/docling-issue-20-live-probe.md#5-建议对-20-配置项做的增减澄清)、
[实测讨论 §7.4](../../intent/discussions/docling-issue-20-live-probe.md#74-这轮实验给出的优先路线)、
[ADR-0025](../adr/0025-allow-local-formula-candidates-with-source-review.md)、
[ADR-0023](../adr/0023-separate-runtime-config-snapshots-from-calibration-baselines.md)。

目标：[规格 §4.9](../../intent/draft.md#49-docling-正文提取)。
组件：[运行配置服务](runtime-config.md)、[配置投影](config-projections.md)、
[阶段输入](stage-inputs.md)。
