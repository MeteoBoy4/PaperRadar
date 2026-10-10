# Issue #20：最新版 Docling 两份 Wiley PDF 实测与配置收口建议

日期：2026-10-09。仓库起始 HEAD：`1841c26754874f560cb2e7a3d314a6f1fe47b5c0`，起始工作树干净。

## 结论

**两份 PDF 均可在 V1 的 CPU、OCR/增强/远程/插件关闭、表格结构开启边界内正常解析。显式选择 Docling 的 pypdfium2 后端后，正文主干、章节定位和 provenance 大致可用，值得作为阶段 F fixture 候选。**

但 **“解析成功”不等于“原始 Markdown 已符合 draft §4.9”**：仍有侧栏/页眉/图注混入正文、未编号章节层级不理想、科学符号重复等问题。不存在此次已验证的单一开关可以全部消除它们，仍须落实既定 normalization 和质量门槛。此次不宣称四刊 fixture gate 通过，不启用 Read/复用升级，也不实现 #20。

#20 无须扩大到 OCR、VLM 或资源配置。需要的是：收口工具链版本的单一权威、把模型身份落实为按阶段的 commit+文件哈希清单，并明确少数实际影响输出的有效解析参数，避免任意独立版本字符串和照搬全部 Docling options。

## 1. 阅读依据与边界

- [#20](https://github.com/MeteoBoy4/PaperRadar/issues/20)：正文及三条工具链、模型、后端澄清评论。
- [#15](https://github.com/MeteoBoy4/PaperRadar/issues/15)：正文、两份实施补充和已确认的版本标签规则。
- 相关 [#16](https://github.com/MeteoBoy4/PaperRadar/issues/16)、[#19](https://github.com/MeteoBoy4/PaperRadar/issues/19)、[#23](https://github.com/MeteoBoy4/PaperRadar/issues/23)。
- `CONTEXT.md` Configuration/Evidence/Processing，`intent/draft.md` §3.4、§4.9、阶段 F，ADR-0008、0010、0017，`docs/contracts/runtime-config.md`。
- 官方当前发行信息：[PyPI docling](https://pypi.org/project/docling/2.135.0/)。API 事实以本次已安装、版本明确的官方源码为依据，而非旧博客或未锁定 main 文档。

冲突的既定裁决：#15 早期评论用切换 OCR 或关闭表格作为测试正例，但 #20 和 draft 更明确地要求 OCR=false、表格=true，继续遵守后者。资源参数和凭据/引用不进入 A2 extraction 文件。extraction 配置投影是 #23 校准基线的独立分量，不能再次嵌入 reuse/Read 配置投影。

此次研究是在生产配置能力之外显式运行的实验，不改变 #20“仅登记，不安装/执行”的交付范围。未修改 GitHub Issue、项目依赖、lockfile、已有配置或数据库。

## 2. 环境、输入与模型冻结

独立环境及全部临时实测材料：`/tmp/paperradar-docling-check/`。

```bash
uv venv --python 3.12 /tmp/paperradar-docling-check/.venv
uv pip install --python /tmp/paperradar-docling-check/.venv/bin/python docling --torch-backend cpu
```

安装时查询 PyPI 的最新版为 **2.135.0**，安装后核对如下：

| 组件 | 本次版本 |
| --- | --- |
| Python | 3.12.14 |
| docling / docling-slim | 2.135.0 / 2.135.0 |
| docling-core | 2.101.1 |
| docling-parse | 7.22.2 |
| docling-ibm-models | 4.0.3 |
| pypdfium2 | 5.14.0 |
| torch / torchvision | 2.14.1+cpu / 0.29.1+cpu |
| transformers | 5.19.0 |

完整安装清单在 `requirements.freeze.txt`。该环境使用标准 docling 发行包（103 个依赖包），**没有验证最小 slim 安装组合**；不能把这次安装量当作生产依赖要求。

| PDF | 原 PDF 页数 | SHA-256 |
| --- | --- | --- |
| `/tmp/paperradar-tdmcheck/qj_70320.pdf` | 21 | `24d8b08c86afbe414d580a7f96269a8f13ae0552e11149ff0f108f82e00669d4` |
| `/tmp/paperradar-tdmcheck/jgra_2026jd046344.pdf` | 24 | `cc84b67c8bf33cdeb62da5a2be4f1fe45ca486dbf6201976a3fe1b02e59882fc` |

只使用给定 PDF，不访问原下载目录中的凭据，也不重新下载论文。

模型先预取到实验专用目录，解析时设置 `HF_HUB_OFFLINE=1`、关闭遥测；下载阶段把远端 revision 解析为 commit 后按该 commit 下载，并对实际模型文件及推理配置逐文件计算 SHA-256：

| 启用阶段 | 模型与仓库 | 实际 commit |
| --- | --- | --- |
| layout | Heron；`docling-project/docling-layout-heron` | `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8` |
| table | TableFormer accurate；`docling-project/docling-models`，原 tag `v2.3.0` | `fc0f2d45e2218ea24bce5045f58a389aed16dc23` |

模型文件身份：

```text
layout/config.json
  fdea30805ce2f5666b147fca941dcdd27ad468e27d6ed21902207d3da056a97d
layout/model.safetensors
  00333a43451945aaf89db8ca9c0a17e75d1537c17db60fdb91aa95f4c7929e0c
layout/preprocessor_config.json
  cd38cd59999e7a95d68e487fbe5132df3d4e5c32a0836add57e6126ba0c4eaf1
table/model_artifacts/tableformer/accurate/tableformer_accurate.safetensors
  2a7d6c924b3cd12fb99a09280ca9c33a89c5d60b93253617d2e088c1a40374d9
table/model_artifacts/tableformer/accurate/tm_config.json
  984e122ceb8ccf84d84c9d2882f6f2302a44b4f1e577babd6289892c36f3cffd
```

这些哈希对应本次下载文件，不是合成占位值；完整仓库相对路径、文件大小、原 revision 和 commit 在 `models-lock.json`。

## 3. 实测配置与对照结果

所有解析均显式固定：CPU，论文之间串行；OCR、code/formula enrichment、picture classification/description、chart extraction、remote services、external plugins 关闭；表格结构开启，TableFormer accurate、cell matching=true；不生成导出用 page/picture/table images；仅允许 PDF 输入。不运行其他正文解析器或自动 fallback。

内部模型/页处理仍可多线程。本次设置 4 个 CPU 推理线程，**“单论文串行”不等于“内部单线程”**。模型内部渲染图像用于 layout/table 推理，不是 V2 图片理解，也不等于向 document.json 嵌入图片。

| 配置组 | PDF | 结果 | 解析耗时¹ | 进程峰值 RSS² | U+FFFD | 主要观察 |
| --- | --- | --- | --- | --- | --- | --- |
| 默认 threaded_docling_parse 后端，其余遵守 V1 | QJRMS | success | 18.20 s | 2477 MiB | 0 | 章节全为 level=1；一条参考文献 charspan 真正越界 |
| 同上 | JGR | success | 27.30 s | 2172 MiB | 71 | 科学符号/范围字符损坏；少量页眉误判标题 |
| 上述配置仅 keep_empty_clusters=true | QJRMS | success | 16.09 s | 2455 MiB | 0 | 仍有同一参考文献越界；公式数量未增加 |
| 同上 | JGR | success | 27.15 s | 2169 MiB | 71 | 字符损坏未改善，公式数量未增加 |
| pypdfium2，keep_empty=true | JGR | success | 27.52 s | 1784 MiB | 0 | 替换字符消失，基本字符区间检查通过 |
| pypdfium2，keep_empty=true，heading hierarchy=true | QJRMS | success | 15.71 s | 1897 MiB | 0 | 编号层级改善，但参考文献仍有一次越界 |
| 同上 | JGR | success | 27.02 s | 1764 MiB | 0 | 编号层级改善；出现一个空标题 |
| **pypdfium2，keep_empty=false，heading hierarchy=true** | **QJRMS** | **success** | **15.93 s** | **1878 MiB** | **0** | 本次选定候选；原始页码/bbox/charspan 基本边界检查通过 |
| **同上** | **JGR** | **success** | **27.39 s** | **1791 MiB** | **0** | 本次选定候选；仍需规范化侧栏/页眉 |
| 候选配置仅关闭 reading-order separators | JGR | success | 27.27 s | 1751 MiB | 0 | 侧栏和表下注释混入段落的问题未消除，不据此建议关闭 |

¹ `converter.convert` 耗时，包括该进程的模型初始化，不含模型下载、Python import 和随后导出。² `/usr/bin/time -v` / Linux ru_maxrss 口径的进程峰值；不是内存上限建议。

所选候选两篇又各在独立进程重复一次，JSON、原始 Markdown、reading-preview 和 evidence-preview 的字节哈希均相同：

| PDF | document.json SHA-256 | raw-reading.md SHA-256 |
| --- | --- | --- |
| QJRMS | `e8c37ef02d5635067bc4396ef57647e09fa98572f569b10907fb645dcb062a63` | `2c62897be03414169fd1f141bd90508ad885400d3fe865bd9145021f8d718d3c` |
| JGR | `5e10b062442c8db889932d1d0fff325ce6be39761d3a3488fe8476727f1e0786` | `7b163c7a23d7d7e414b670c2aa98865972192efef43681820b20931289621a4c` |

这仅证明本机这两次输出一致，不证明跨平台/线程数/不同底层依赖均确定性，更不是正式 normalization v1 或最终 evidence ID 的验收。

## 4. 对照 draft §4.9 的粗略观察

- **正文起点/真实版式**：QJRMS 首页为左侧作者信息+右侧摘要，其后主要双栏；JGR 首页为左侧元数据+右侧正文，其后主要右侧宽正文。本次 PDF 没有仓储封面/推荐页，不能证明这些边界已支持。渲染并抽查 QJRMS 第 1/7/21 页、JGR 第 1/5/21 页，另生成了若干页的可回查图像。
- **章节/摘录**：可定位 QJRMS `2 DATA`（第 5 页）、`3 METHODOLOGY`（第 6 页）、`DATA AVAILABILITY STATEMENT`（第 19 页）；JGR `2. Data and Methodology`（第 3 页）、`Availability Statement`（第 21 页）。未执行项目正式 excerpt selector。
- **标题层级**：Docling 默认 heading hierarchy 关闭，所有标题 level=1；开启后编号章/节/小节大致形成 level=2/3/4。仍须用 normalization 对齐论文自身的层级，不能直接把出版文章类型/作者/侧栏标题作为真正章节。JGR 末尾 `Acknowledgments`/`Conflict of Interest`/`Availability Statement` 被赋不同层级，不能当作可靠树。
- **页眉页脚**：大部分标为 furniture，原始 JSON 保留；仅导出 BODY 并不足够。候选 JGR 的期刊名页眉在第 2/4/9 页仍被标成正文 section_header，必须按重复文本+版面位置处理。
- **阅读顺序**：主体章节大致可读，但 QJRMS 第 8 页图注插入正文段落中间；JGR 第 2 页作者贡献侧栏与正文接续合并，另有第 3 页表下注释被合并到引言。这些是实际输出缺陷，不能通过“无 U+FFFD”忽略。关闭 reading-order separators 的对照未解决这些具体问题。
- **定位**：候选配置所有 texts/tables/pictures 都有 provenance；检查了原页码存在、bbox 在页面范围、字符区间在 source orig/text 范围，无边界错误。但这是结构检查，不证明每个区间语义正确或每个科学符号可信。bbox 常为 BOTTOMLEFT，不能把 `t>b` 当越界。
- **orig/text 不等价**：列表标记从 text 删除、公式 text 为空而 orig 非空；charspan 必须结合源字段解释。初版探针按 text 长度判断，误报 QJRMS 3 个和 JGR 6 个列表越界；`audit.json` 使用 orig 优先重新核对，取代旧 baseline summary 的这部分诊断。默认后端 QJRMS 最末参考文献的一个区间仍是真越界，不得静默夹断。
- **受限内容**：QJRMS 检出 3 个公式/1 个表，JGR 4 个公式/6 个表。公式关闭增强后仍有 bbox/page/原始 orig，不能把 text 空当作无公式。原始 Markdown 只给 `<!-- formula-not-decoded -->`，没有明确页码/bbox，也没有每表数值警告。实验 reading-preview 加了定位占位和表格警告，但不是项目完整 normalization。
- **字符/数值风险**：pypdfium2 消除了本次 U+FFFD，并改善了一些粘连空格，但仍有上下标变量重复等失真，尤其 JGR 的科学符号和表格。没有逐数值核验，不宣称表格数值或公式准确。
- **图像/base64**：全部实测组 JSON/Markdown 未发现 base64 图片。导出策略仍应固定；不要把这次未生成图像推广为任意 exporter 都安全。

因此，本次“可正常解析、结构大致可用”的结论只支持继续做 normalization 与 fixture；**原始导出制品不应直接进入依赖正文的 Agent**。

## 5. 建议对 #20 配置项做的增减/澄清

### 5.1 应修改/补清的核心项

1. **后端选择要明确，建议优先验证 pypdfium2 候选。** 本次默认 threaded 后端的 JGR 有 71 个 U+FFFD，pypdfium2 为 0。pypdfium2 是 Docling 的 PDF backend，不是换正文解析器，更不是运行时自动 fallback。生产最终选择须等四刊 fixtures，不能据两篇永久排除另一后端。
2. **一份受控工具链锁定清单，不让版本各自自由填写。** docling/core 是转换与数据模型身份；docling-parse 与 pypdfium2 分别为后端依赖。后端 package version 从同一清单引用，不再维护可独立冲突的 `backend_version`/`docling_parse_version`。记录真实实现包 docling-slim 和启用推理代码包 docling-ibm-models；底层 torch/torchvision/transformers 等环境锁定身份可随清单/manifest 留档。选择未使用的 parse 包不等于使用 parse 后端，不能将所有已安装但未消费的包无差别塞入语义投影。
3. **模型按启用阶段列出，至少 layout/table。** 每项含模型标识、repo、不可变 commit、实际制品相对路径+文件 SHA-256。layout 的 processor/config、table 的 tm_config 也影响推理，不仅冻结权重。`main` 或 tag 只能是可选来源说明，不能代替 draft 要求的 commit+文件哈希。A2 仅验声明格式/完整性，不联网确认或下载校验。
4. **表格实现、mode 和 cell matching 明确冻结。** 本次使用 `docling_tableformer`、accurate、do_cell_matching=true。#20 评论已覆盖 mode，但 cell matching 也实际改变输出，不能隐藏在随 Docling 更新的默认值里。mode 只在一处登记，与对应模型文件一致；不在模型槽和 options 各维护一份未经一致性检查的值。
5. **明确正文相关有效策略，而不是自由 options 字典。** 至少把 layout 模型/engine、heading hierarchy、keep_empty_clusters、force_backend_text、reading-order separators，以及所选后端实际消费的语义选项固定/登记。此次建议候选：heading hierarchy=true、keep_empty=false、force_backend_text=false、reading-order separators=true。固定值可以在受控 policy 中编译补全，不必把它们全变成用户必填 YAML 开关。已经实验了的 bool 也不意味着全部应开放为生产调参能力。
6. **声明固定安全输出策略。** images generation 关闭、JSON/Markdown 使用不嵌入图片的方式；源 document 保留 provenance、orig/text/content layer，规范 reading/evidence 另行生成。这是 exporter/normalization 契约，不需要增加用户可切换的图像理解功能。

开启 heading hierarchy 能减少编号层级的后处理量，但官方仍有未编号标题错误；若选择完全由 normalization 修复，也可以保持该开关 false，只是需要明确冻结并承担相应 fixture 工作，不能遗漏这个会改变输出的输入。

### 5.2 建议删除重复项/避免新增的项

- 不用“单一全局模型 hash”替代 layout/table 制品清单；可从清单规范生成身份，不再让用户额外手填一个可能矛盾的总 hash。
- 不为已关闭的 OCR、公式/代码模型、图片分类/描述模型、图表模型要求 repo/revision/hash；不因默认 options 带着这些未启用模型就登记为必需项。
- 不接受 GPU/auto、OCR=true、表格结构=false、enrichment/remote/plugins=true。若固定字段允许省略，必须在纯编译层补成明确 V1 字面量并写明 Contract，而非继承 Docling 默认（OCR 默认 true、device 默认 auto）。
- 不新增 timeout、内存上限、峰值、线程/批量/队列、模型本机目录、凭据/password 或凭据引用为 A2 语义字段。它们的执行/manifest/doctor 职责按既定分阶段范围处理。
- 不在 extraction 重复登记 excerpt selector 或 Read chunking；不嵌套整个 reuse/Read 配置。normalization_version 则必须保留，是受控算法语义身份而非自由声明标签。
- 不把“开启 keep_empty_clusters”当作必须项：此次公式本来就保留，开启没有增加公式，反而出现空标题/参考文献区间风险；未来遇到真正空文本公式的 fixture 再评估。
- 不新增“自动删除乱码”“自动修复符号”“忽略质量失败”配置来让样本表面通过。页眉/侧栏/图注/章节规范化属于 normalization 及黄金 fixture，不是不断增长的用户配置表。

### 5.3 必填性收口建议

选择 extraction 内容文件后，必须能得到：与 selector 一致的声明 version、受支持工具链身份、所选 backend、启用 layout/table 的完整模型制品身份、明确有效解析 policy、受控 normalization v1。工具链清单由哪里产生/如何引用、支持哪些组合，需在 #20 实现 Contract 明确。

固定开关和固定 policy 可以省略输入但不可省略编译后的有效值；允许变动的语义选项必须显式/有文档化默认，不能依赖可漂移的上游默认。settings.extraction 缺失/null 仍是合法未配置快照。extraction 配置就绪只依赖本段完整性，不依赖 Profile、PDF、LLM、模型文件是否存在或 fixture gate。

以上是建议，不定义第二份可执行 YAML Schema，不授权任意未验证工具链组合，也不改变 #23 的语义投影规则。

## 6. 官方源码与复现材料

本次官方源码根：`/tmp/paperradar-docling-check/.venv/lib/python3.12/site-packages/`。

- `docling/document_converter.py`：PdfFormatOption 默认 StandardPdfPipeline / ThreadedDoclingParseDocumentBackend，以及显式后端注入。
- `docling/datamodel/pipeline_options.py`：OCR/安全开关默认值，TableStructureOptions、LayoutObjectDetectionOptions、heading_hierarchy_options、force_backend_text、use_reading_order_separators。
- `docling/datamodel/backend_options.py` 与两个 backend 实现：backend options 的类型、环境/线程与实际语义消费者。不要统一要求某后端不消费的参数。
- `docling/models/stages/layout/layout_object_detection_model.py`、`docling/datamodel/stage_model_specs.py`：Heron 实际模型/engine preset。
- `docling/models/stages/table_structure/table_structure_model.py`：accurate/fast 模型路径、读取 tm_config、cell matching，以及默认下载 tag v2.3.0。其下载函数不开放 revision 参数，严格 commit 冻结应预取可信本地制品，而非解析时追 tag。
- `docling/models/stages/reading_order/readingorder_model.py`：跨块 merge/provenance、原文与处理后 text 的关系。不能把 charspan 当作 PDF 原始字节偏移。
- `docling_core/types/doc/document.py`：Markdown / JSON 导出和 image mode；save_as_json 的默认 EMBEDDED 不应无条件照搬。

临时目录包含：

```text
requirements.freeze.txt / docling-pypi.json
models-lock.json / models/                 # 本次模型字节与身份
prefetch.py / parse.py / audit.py           # 可执行实验脚本，非项目 Adapter
issue-{15,20,23}.json / issue-15.md
config-research.md                         # 只读资料核对的补充研究
*-*.log                                   # 安装/模型下载/解析耗时；不写论文全文
visual/                                   # 仅 PDF 渲染回查，不作为另一解析器
outputs/<profile>/<pdf-stem>/
  options.json / parse-manifest.json
  document.json / raw-reading.md
  reading-preview.md / evidence-preview.json / summary.json
audit.json                                # 所有 content layers 的更正结构检查/重复比较
```

复跑候选（模型已经预取，论文逐篇串行）：

```bash
export HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
/tmp/paperradar-docling-check/.venv/bin/python \
  /tmp/paperradar-docling-check/parse.py \
  /tmp/paperradar-tdmcheck/qj_70320.pdf pypdfium-default-hierarchy
/tmp/paperradar-docling-check/.venv/bin/python \
  /tmp/paperradar-docling-check/parse.py \
  /tmp/paperradar-tdmcheck/jgra_2026jd046344.pdf pypdfium-default-hierarchy
/tmp/paperradar-docling-check/.venv/bin/python /tmp/paperradar-docling-check/audit.py
```

实测共 12 次完整解析，均 success；执行了结构审计和重复输出哈希比较，以及实验脚本 py_compile。未执行项目完整离线测试（未改项目行为），未运行中文/AIES PDF、扫描稿、封面、资源失败/重试或正式 evidence/normalization fixture。

**后续事项**：确认 #20 的封闭工具链与有效 policy Contract；阶段 F 把本次缺陷转成 fixture 断言，补齐另外两刊、侧栏/图注/未编号标题规范化，之后才判断能否进入依赖正文的 Agent。`/tmp` 可被清理，实测大文件和脚本不属于永久 fixture registry；本报告保存了关键版本、模型/PDF/输出身份与结论，没有把临时预览冒充正式制品。

## 7. 补充探索：不受 V1 限制时，哪些 Docling 能力确有改善？

本节是用户追加授权的独立研究：允许试验公式增强、OCR 与本地 VLM，不把它们自动纳入生产能力。前文 §2–6 的 12 次解析和结论仍仅对应第一轮 V1 边界实验，本节另进行了 **15 次成功转换、193 页次**（包含同页多种配置对照，不是 193 个不同页面），其中 8 次为整篇转换。未修改 draft、Issue、生产配置或项目 lockfile。

**最值得优先引入的是 Egret medium 版面模型与局部 CodeFormulaV2 公式增强；全页 VLM 有分块收益，但本次不能作为原生文本链的无条件替代；强制全页 OCR 对这些有文本层的 PDF 未显示净收益。** 其中 Egret 本身并不要求放宽 OCR/VLM 边界，只需登记新的版面模型身份并重新做 fixture。

### 7.1 环境与实际测量

沿用 Docling 2.135.0、pypdfium2 后端、本地 CPU 与 4 个推理线程。模型先预取、锁定 commit+文件 SHA-256，再离线解析；没有调用付费/远程模型，也没有发送论文给外部 LLM。

| 新能力 | 模型仓库 | 本次固定 commit |
| --- | --- | --- |
| Egret medium layout | `docling-project/docling-layout-egret-medium` | `77ede7cc7bed96d853c58f319734803d6ea2ea5c` |
| Egret large layout | `docling-project/docling-layout-egret-large` | `fff417c78abd6bab338c87706c95a8d79dc68f1e` |
| 公式增强 | `docling-project/CodeFormulaV2` | `ecedbe111d15c2dc60bfd4a823cbe80127b58af4` |
| 全页 VLM | `ibm-granite/granite-docling-258M` | `982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe` |

VLM/公式模型显式使用 Transformers、float32、CPU，关闭 8-bit 加载、remote code、远程服务和插件。为 OCR 实验，仅在临时 venv 增加 EasyOCR 1.7.2、ONNX Runtime 1.31.0 及所需依赖；Docling/core/后端/torch/transformers 版本未变。英文 EasyOCR 的检测/识别权重也预取并记录 SHA-256。

| 对照能力 | 实际转换范围 | 耗时 | 峰值 RSS | 主要收益或问题 |
| --- | --- | --- | --- | --- |
| 原 Heron 基线 | QJRMS / JGR 整篇 | 15.93 / 27.39 s | 1878 / 1791 MiB | 第一轮候选，作为参照 |
| 仅换 Egret medium | QJRMS / JGR 整篇 | 8.88 / 23.76 s | 1756 / 1664 MiB | JGR 三个误判正文标题的页眉消失；作者贡献与正文分块分离 |
| 仅换 Egret large | QJRMS / JGR 整篇 | 11.14 / 25.93 s | 1833 / 1798 MiB | 页眉改善，但 JGR 作者贡献与正文又被合并；没有优于 medium |
| Heron + CodeFormulaV2 | QJRMS / JGR 整篇 | 29.39 / 53.42 s | 3570 / 3805 MiB | 3/3 与 4/4 独立公式获得非空 LaTeX；并非全部准确 |
| Egret medium + CodeFormulaV2 | QJRMS / JGR 整篇 | 23.10 / 50.46 s | 3477 / 3833 MiB | 两种收益可以同时获得；剩余图注/表下注释污染未解决 |
| EasyOCR 强制全页 | JGR 第 2–3 页 | 33.82 s | 4574 MiB | 原生上下标重复减少，但错字、漏字、数值误识明显增加 |
| Granite-Docling 纯 VLM | JGR 第 2–3 页 | 85.73 s | 3195 MiB | 表下注释与正文分开，但词语/表格内容改错、侧栏漏提取 |
| Granite-Docling + backend text | JGR 第 2–3 页 | 85.44 s | 3234 MiB | 正文恢复原生措辞；表格仍是生成内容，且出现控制字符 |
| Granite-Docling 纯 VLM | QJRMS 第 7–8 页 | 95.75 s | 3264 MiB | 两个公式可读、正文不再混入图注；但 Figure 2 图注实际漏掉 |

耗时仍为 convert 口径，含模型初始化、不含模型下载和 import。各行页数不同，不能直接作为整体吞吐量比较；上述均是一次测量，不声称速度提升比例可跨机器复现。全页 VLM 只试了问题页，没有转换两篇全文。

### 7.2 有明确正收益的能力

**A. 更换版面模型：Egret medium 比继续堆 OCR 更值得先试。**

公共 API 是 `LayoutObjectDetectionOptions.from_preset("layout_egret_medium")`。JGR 基线中第 2/4/9 页的期刊名被误判为 body section_header，medium 与 large 都把这些页眉恢复为 page_header。medium 还将第 2 页 `Writing – review & editing` 侧栏与 `interactions with large-scale dynamics` 正文分为两个有各自 bbox 的块；原生字符没有被生成模型重写。

这是实质改善，但不是整篇“自动清洗完成”：侧栏仍作为独立正文块保留、位置仍需处理；第 3 页表下注释仍被合并到上一页引言，QJRMS 第 8 页 Figure 2 图注仍混入正文 TEXT。large 在作者贡献分离这一具体问题上回退，说明更大的版面模型不必然更好。当前更推荐 **medium 候选**，而非默认直接上 large/xlarge。

**B. 局部公式增强：把“公式占位”提升为“可核查的转写候选”。**

开启 `do_formula_enrichment=True`，使用 `CodeFormulaVlmOptions.from_preset("codeformulav2")`；代码增强保持关闭。两篇共 7 个已检出的公式全部获得非空 LaTeX，分数、偏导数、上下标和括号结构比原生 PDF 字符串明显好。例如 JGR 第 9 页恢复出 `LWP_ad = (1/2) Γ_ad H²`，第 5 页恢复出 ensemble update 的多层上下标，而不是原始文本中的重复变量堆叠。此能力只针对独立 FORMULA 块，不会自动修正文行内变量、表格或图注。

**7/7 非空不是 7/7 准确。** 实际仍发现：

- 默认 `expansion_factor=0.18` 时，QJRMS 第 7 页公式 (2) 多生成了 `\text{for}`；JGR 第 13 页 `z_{t,c}` 被识为 `z_{\imath,c}`。
- 把公式 crop margin 改成 `0.05` 的问题页对照，去掉了前者的多余词，并把后者识回 `t`；但同组 QJRMS 公式 (3) 又将 `MAP_o` 识为 `MAP_0`。
- 另试 `0.10`，QJRMS 公式 (1) 的拉丁 `v` 被识为希腊 `\nu`。不能把某个 margin 宣布为通用正确值，也不能静默凭上下文改回字符。
- JGR 第 5 页生成文本还带有 `& &` 等排版残留；模型加载时有 pad-token/tied-weights 警告，本次未篡改模型权重或配置来隐藏它们。

因此，**可引入“局部公式候选转写+PDF 裁切人工核查”能力，不宜引入“公式已经精确恢复”的承诺**。增强写回 text，但原来的 orig/prov.charspan 仍指向原始区域文本，不是生成 LaTeX 的逐字符对齐；必须分别保留源文本、生成文本和区域定位。

### 7.3 有局部收益，但不能无条件替代的能力

**C. Granite-Docling 全页视觉解析：分块改善伴随内容损失。**

采用独立 `VlmPipeline`，`VlmConvertOptions.from_preset("granite_docling")`，从页面图像生成 DocTags。它不同时运行 StandardPdfPipeline 的 Egret/TableFormer/OCR/公式增强，不能在这条管线上追加相应开关并假定都生效。

JGR 第 2–3 页的表下注释被分为独立块，正文顺序比原先的跨页错误合并更合理；QJRMS 第 7–8 页的两个公式也恢复为 LaTeX。但代价很具体：

- JGR 正文的 `shortwave` 被生成为 `swathive`。
- JGR Table 1 的 `enaswsradC1.b1` 被生成为 `enaursradC1.b1`，Radiosonde 的 Temperature/Humidity 信息丢失，若干参考文献和产品字符串也被漏写/改写。
- JGR 第 2 页作者贡献侧栏没有出现在生成文本里；QJRMS Figure 2 图注也没有出现在输出中。**“图注不再污染正文”在这里不能被解释成完全修复，因为图注本身丢了。**
- 页眉仍可能被生成成正文标题；VLM 输出 bbox/charspan 是生成布局的定位，不是天然的 PDF 逐字符事实。

继续试了混合路线：在 **内层** `vlm_options.force_backend_text=True` 上设置，让 VLM 负责区域/顺序，正文取预测 bbox 内的 PDF 原生文字。它修复了上述正文 `shortwave` 的生成错词，但当前实现只替换 TextItem，**表格内容仍保留 VLM 生成错误**，缺失的布局区域也不会凭空补回；此外正文出现 5 个 U+0002 控制字符。此次 VLM JSON 即使请求 PLACEHOLDER 导出，仍检出内嵌图像，导出处理也须单独审计。

建议把这条能力作为难页的**独立候选/辅助对照**，保留原生输出及覆盖率检查，而非整体替换原文。没有测试更大 VLM、GPU 或远程服务，不能把 258M 的失败推广为所有视觉解析模型无效。

**D. 强制全页 OCR：本次有文本层 PDF 不宜默认启用。**

实际成功测试的是 `EasyOcrOptions(lang=["en"], mode=OcrMode.FULL_PAGE)`，而不是仅开启默认 PDF-aware OCR。它确实重建了文字，但 JGR 第 2–3 页出现 `cloud and/or`→`cloud andlor`、`3%–5%`→`39-5%` 等错字/数值错误，还保留作者贡献与正文混合的问题。虽然部分上下标重复消失，不能用更干净的外观抵消语义损坏。

RapidOCR 未取得质量结果：最新版环境中的 RapidOCR 3.10.0 在模型预取时缺少 Docling 所需 `PP_OCRV6_LANGS`，提示安装 `rapidocr>=3.9.1,<4.0.0`，但现有版本已经在该范围内。该路径记为依赖兼容阻断，未修改第三方源码绕过；随后显式另选 EasyOCR 作独立实验。这不是生产自动 fallback。扫描 PDF 或已坏的文本层仍可能受益于 OCR，但本次没有覆盖这些输入。

### 7.4 这轮实验给出的优先路线

1. **先换 Egret medium**，保持原生文本链；收益明确、成本较低，新增模型身份并重跑 fixtures 即可继续验证。
2. 如果确实需要理解独立公式，**增加 CodeFormulaV2 的局部候选转写**，将裁切核查、生成/源文本分离作为同一能力的一部分；不要顺带声称行内科学符号和表格都被修复。
3. 余下侧栏、表下注释、图注跨块污染，仍要针对块边界和 reading-order merge 做确定性处理。安装源码中未找到 StandardPdfPipeline 的公共“关闭跨块 merge”配置；`use_reading_order_separators` 并非这个开关。不要用全面 OCR 来修复本质上的区域/合并问题。
4. 只有难页才进一步评估 VLM/混合文本；增加漏块、数值/术语变写检查，不能因为输出通顺就直接替换源证据。

实测证据保存在 `/tmp/paperradar-docling-check/advanced-outputs/<mode>/<pdf>-<start>-<end>/` 的 document.json、reading.md、formulas.json、options.json 和 summary.json；汇总为 `advanced-audit.json`，模型清单为 `advanced-models-lock.json` / `easyocr-models-lock.json`，环境为 `requirements.advanced.freeze.txt`，脚本为 `explore-advanced.py`。结构审计确认 15 次转换均 success、全部块有 provenance、bbox 基本边界合法；这些检查不是公式准确率、全文覆盖率或生产质量门槛。本节未做增强配置的重复确定性验证，也未运行项目完整离线测试（没有改项目行为）。

源码依据：`datamodel/pipeline_options.py` / `stage_model_specs.py` 的 Egret、CodeFormula、Granite presets；`models/stages/code_formula/code_formula_vlm_model.py` 的区域增强与 text 写回；`models/base_ocr_model.py` 的 FULL_PAGE cells 替换；`pipeline/vlm_pipeline.py` 的内层 force_backend_text 与 TextItem 替换；`models/stages/reading_order/readingorder_model.py` 的 predict_merges 调用。对应版本均为本次已安装的官方 Docling 2.135.0。
