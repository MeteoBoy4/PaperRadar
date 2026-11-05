# 真实 Docling 补充样本工程核验（#164）

本记录冻结 2026-11-05 用户本人执行的第二个本地 PDF smoke 及其后只读审计，依据
[#164 第一条评论](https://github.com/MeteoBoy4/PaperRadar/issues/164#issuecomment-6633904561)的补充材料授权与
[第二条评论](https://github.com/MeteoBoy4/PaperRadar/issues/164#issuecomment-6634192619)的本人执行要求。
这是新增的按次证据；[首次主样本记录](issue-164-docling-smoke.md)保留原字节。
真实 PDF、正文、引文、SDK 原始输出、数据库和恢复副本均只留本机；本文件仅公开安全计数、
身份摘要和工程结论。

## 材料与执行身份

本次材料为用户指定的 `2026JD047706.pdf`，**7,034,995 字节**，SHA-256
`98299ed62736f3877a2d9920e6ae91f0fc487665cb3df49991bfeeed06a645e7`。材料只按用户声明与文件哈希绑定，没有从文件名推断真实 DOI、
新 Feed/HTTP 来源或实际书目发现。独立库使用明确标记的合成论文容器与 experiment 根，
不是 B 当轮 JGR 样本。原实验库与预算保持，本次独立领取一次提取，成功后剩余一次。

本人确认材料、容器及资源后，原始 invocation/result 记录的时间为
`2026-11-05T10:58:40.609002+00:00` 至 `2026-11-05T10:59:06.248039+00:00`。
生产链新执行 Docling adapter → canonical → normalize/evidence → 自动检查 → Body 持久登记，
新产出 evidence-map；没有把第一次或 EXP-3 旧 document 当作本次结果。

| 身份字段 | 本次冻结值 |
| --- | --- |
| commit / dirty | `65a5c124a836b3a6be72d14a022ef244d6eb747f` / false |
| 完整主工作树 SHA-256 | `6142604b9a700b231fecac613916c5476e89b86a80ba7970fb9f00b9bd5bed2c` |
| uv.lock SHA-256 | `fcd6149e80b961d9bfa3c9b0015f3ddf2835c830f03b956506f300353c0f0905` |
| extraction_fingerprint | `952eba7c596ec7436c582b7847e2ae5c1dce63cebcf55a6398934c0ed1638ee2` |
| extraction artifact_id | `40039ecf6a334d5414f84a688b46808f416da0417cce5734f31554a96b8ce99a` |
| backend_config_hash | `c5ab2231b523d646b9766610c262fcc602fc6c6d9b2803bd011c813d3e53adcb` |
| model_artifacts_hash | `9bf7033cd2276ae51d15b3ae561c7931ccfcce948a42ab09b0f547e5ebfb133b` |

准备计划、运行 invocation/result 与审计前当前主树的 commit、dirty、完整树及 lock 均逐字段相同。
后续新增本报告的文档提交不取得该次执行身份或完整门禁结论。
计划内 `docling_executed=false`、`pdf_attached=false` 是执行前准备事实，原字节保留；
实际成功执行与附加情况由本次结果和持久服务核验，不追改准备清单。

本次使用 Python 3.14.4、CPU 工具链 `docling-2.135.0-cpu-v2`、pypdfium2 后端，
docling-slim 2.135.0、docling-core 2.105.0、docling-ibm-models 4.0.3、docling-parse 7.22.2、
pypdfium2 5.14.0、torch 2.14.1+cpu、torchvision 0.29.1+cpu、transformers 5.19.0。
16 个冻结模型文件共 930,878,676 字节，只读复用既有本机部署；没有下载或改写模型。
manifest、attempt 与 invocation 中的运行参数和版本一致。

原始四份逐次记录保留原字节：

| 本地记录 basename | 字节 | SHA-256 |
| --- | ---: | --- |
| `20261105T105838Z-2917815.operator.log` | 511 | `d3667ce3d6b3d22a8e2c60590ed1f64fb2d80adbf728aa329c2a36199f89a5d7` |
| `20261105T105838Z-2917815.resources.json` | 404 | `41252aa1c7e58879d27136e8252ead7f24750c8e1117a168e26382fa1b9d5473` |
| `20261105T105840Z-d0e09f3b.invocation.json` | 2,362 | `b044881ec308bf70e7ee98a7feee19671c0abb08de345e4ce79f600885c0b325` |
| `20261105T105840Z-d0e09f3b.json` | 5,685 | `ce983e4fd4f8bf6ba7d56e8c8dbd9c6208a270935fa170a031a334feba226930` |

## 逐字保真与新制品

通过生产 `BodyService.validate_all()`、`ArtifactStore.read_artifact()` 与
`FulltextArtifacts.load()` 重验登记、内容身份、规范 reading 和自动质量；附加 PDF 与用户原件逐字相同。
四角色共 **718,156 字节**，manifest 内 document/reading/evidence-map SHA、提取指纹、
后端与模型身份闭合；没有增加角色或改变正文三元组。

| 角色 | 字节 | SHA-256 |
| --- | ---: | --- |
| document | 245,275 | `129cd2a246d30ef2029ed5fae8465933728afb638e99a6e22a9488c40d2640af` |
| evidence_map | 400,841 | `ceed46e817bdebad4b9bd1bc12ea1929f7da330d8b5ff138c4c1cd8fa83e6e63` |
| manifest | 1,643 | `b3d48b87d0a8844d86e111ec90a41e60320410c2901f943b53de67887df5c2b3` |
| reading | 70,397 | `6beaf32a35a37e37052936af210f8634364cf597d379b44fd83289b66bc20d98` |

只读审计不导入 SDK：沿保存 document 的 body/furniture 阅读树深度优先遍历，
与规范 reading_blocks 稳定序号逐一配对，核对父子关系、content layer、label 和 role；
逐个核对页尺寸、页码、bbox 原点转换和 charspan，不凭 ref 名称猜顺序。

- **20 页、295 个阅读块、299 条全部 provenance**均与保存的 SDK 导出逐项对应。
- **254 个源块**的 orig/text 逐字相等于 SDK 保存字段，含 **263 条源 provenance**，
  共 **71,330 个源 code point／72,203 个 UTF-8 字节**；被排除的源块也核验完整定位、
  非空切片与非空白源字符覆盖。
- **6 个源块的 orig 与 text 不同**，保留 orig，没有用 text 或生成候选替换。
- **159 个 evidence、168 条非空切片**逐条等于持久 orig 的原始半开区间切片，不作字符归一化。
- 3 个公式生成候选与父源字符分开保存；候选或占位不是 evidence 锚点。

上述结论证明 SDK 已保存字段至持久制品的工程保真，不证明 parser 对真实 PDF 的文字、
公式科学意义、版面或阅读顺序全部判断正确；没有开展人工逐页版式或 LaTeX 正确性审核。

## 公式父源覆盖与两个样本的关系

执行前的 plan 已冻结统计口径：分母为**所有 label=formula 项，包含仅占位／无源项**；
父源分子须同时有逐字 orig、完整页码/bbox/charspan 和非空可回放切片，并覆盖非空白源字符。
独立遍历、持久 map 重算、结果 JSON 与生产 statistics 的计数一致：

| 类别 | label=formula 总数 | 有父源块 | 仅占位／无源块 | 本次结论 |
| --- | ---: | ---: | ---: | --- |
| display（行间） | 0 | 0 | 0 | 未覆盖，不计算百分比 |
| inline（行内） | 0 | 0 | 0 | 未覆盖，不计算百分比 |
| unknown | 3 | 3 | 0 | 此三个未知类别项均可回放父源 |
| 全部 | 3 | 3 | 0 | 仅本补充样本的观测 |
| 行内是否独立成 item | — | — | — | 没有独立 inline item；不能推断 PDF 不存在行内公式 |

本次增加了三个真实 SDK `label=formula` 项的父源、定位与逐字切片证据，仍符合现有“有父源”分支；
unknown 不能凭生成候选或版面先验改称 display/inline。未观测到无父源项，不能据此宣称该分支通过。
支持受限引用不等于已经核对数学内容，后续消费仍遵循[受限源规则](../contracts/read-validation.md)。

| 已冻结观测 | 首次主样本 | 本次补充样本 |
| --- | ---: | ---: |
| 页数 | 16 | 20 |
| 源块／evidence／切片 | 216／139／147 | 254／159／168 |
| evidence-map 字节 | 353,471 | 400,841 |
| unknown 公式总数／父源／无源 | 1／1／0 | 3／3／0 |
| display／inline 类别 | 均未覆盖 | 均未覆盖 |
| 实际运行源码 | `811adfd7` | `65a5c124` |

两个样本的工具链、组件版本、后端配置哈希与模型哈希已逐项核对一致，但**代码执行身份不同**；
它们是两次分别冻结的工程观测，不能称为严格只改变 PDF 的同源码对照，也不能从两份材料
外推四刊、公式整体完整支持或科学质量。分类、图片型公式、复杂版式与裁切展示仍由 B/F 承接，
既有[能力边界](../contracts/fulltext-extraction.md#自动质量与统计)、ADR 与术语不因增加样本改变。

## 资源、预算与质量资格

| 计时／资源口径 | 实测或明确限制 |
| --- | --- |
| manifest.elapsed_seconds（转换，不含发布） | 24.47913169953972 秒 |
| attempt.elapsed_seconds（含发布结算） | 24.606916598044336 秒 |
| result.wall_seconds_including_preparation | 25.54877044260502 秒 |
| worker 峰值：wait4 ru_maxrss KiB × 1024 | 3,281,612,800 字节 |
| result.cgroup_after.memory.peak | 4,074,881,024 字节 |
| cgroup 物理内存上限／swap | 10,737,418,240 字节（10 GiB）／0 |
| SDK RLIMIT_AS 虚拟地址空间上限 | 34,359,738,368 字节（32 GiB） |
| 转换 timeout／外层单元 timeout／threads | 600 秒／720 秒／4 |

result 的 wall 字段计时从 PDF 附加及快照读取之后、DoclingParser 构建之前开始，覆盖其后准备、
提取与结算，不包含前面的身份检查和 PDF 附加；不把它当整个 systemd 单元 wall。
worker 与 cgroup 峰值分别报告，RLIMIT_AS 是虚拟地址空间限制；本次成功未触发实际 OOM 或超时，
不形成 F 的通用资源阈值，也不新增现场失败分支结论。

自动检查通过，根用途仍 experiment；`quality_basis=absent`、failure=null、剩余预算为 1。
没有六项人工版式核查、experiment_document_gate 或 formal_gate，Read 未运行。
自动逐字回放不替代人工核对正文起点、章节或页眉页脚。

## 真正无 extra 的两次隔离恢复

后续核验实际运行于同 Python 3.14.4 的 **35 包 base 环境**，完整发行包库存中无 Docling、
docling-core、docling-slim、torch、transformers 等 SDK；源码指向运行时主树。
没有复制虚拟环境、联网、导入 SDK 或重新解析 PDF。

1. 生产 `create_backup` 创建自包含批次。第一个树外 cwd 的新进程执行 `verify_backup`、
   `restore_backup`、`verify_contents`、Body 重验和 `FulltextArtifacts.load()`，新建并逐字回放 ReadContext。
   在 API 调用前拒绝访问原业务根、共享模型部署、原 PDF 目录与 extra 环境，**4 个拒绝探针实际命中**；
   同时禁止网络、外部进程与 SDK 导入。
2. 在实际移动前，将恢复根的 root_id、正文三元组和 artifact_id 与源预期逐字段比较，
   并已核预算、质量和所有制品身份；随后整体移至第二位置。第二个全新 base 进程再拒绝
   首次恢复位置及备份批次，**6 个拒绝探针实际命中**，只依靠新位置重新验证和回放。
3. 两次都重建 **254 源／159 evidence／168 切片**，完整切片摘要、PDF 与四角色字节相同，
   剩余预算仍 1、质量仍 absent；普通消费保留 `ordinary_consumption_denied` 和 `quality_absent`。
   查询前后文件 SHA/长度/权限库存相同，没有回收租约、激活配置或运行 Read。

备份含 **1 个配置快照、3 个制品、6 个 blob、7,753,257 个 blob 字节**，
备份清单 SHA-256 为 `e62076758a87567298aa09add7803b815de56793b97e15af0a4e77e4096ecb70`。
批次与搬迁后恢复根的完整文件 SHA/长度/权限库存相等；6 个 blob 的源件、备份件与恢复件
分别具有独立 inode 且逐字节一致，不以硬链接依赖源根。

源业务库逻辑 dump 与全目录 SHA/长度/权限库存，在备份前、备份后及两次冷回查后相同。
本次四份原始记录保持；此前主样本的计划、结果、业务文件和共享模型共 **36 个文件**的
SHA/长度/权限也保持。原始证据没有迁移或改写，恢复根的移动在身份比较之后进行。

私有核验材料保存在本机本次补充目录的 verification 子目录：逐项审计、源前后库存、
expected、backup、cold-restore、cold-moved 和 final-local-check；只公开上述安全摘要。

## 验证与证明范围

本次实际成功的人跑解析、原字段逐字核验、两次无 extra 冷恢复与最终库存／inode 检查
均有各自独立记录。旧按次报告及 #165 材料清单不追改，不扩大历史固定分母、required 或旧结论。

本记录追加不改变产品代码、Schema、规则、依赖或既有能力上限。新增文档的链接与固定材料检查
作为本次文档验证单列；完整离线门禁没有在本次追加文档提交上重跑，既有门禁仅适用于其历史
冻结源码身份，不能把本报告的后续提交称为 passed/verified/same。

本次仍不能证明四刊／中文／复杂版式质量、公式 LaTeX 准确性、人工版式质量门禁、B 当轮真实链、
正常生产 Read、Pi 现场、正式校准、NAS 或完整阶段 A/B。新增真实样本增加的是源保存、
可回放父源与恢复工程证据；没有授予上述资格。

相关：[首次主样本](issue-164-docling-smoke.md)、[正文契约](../contracts/fulltext-extraction.md)、
[持久化契约](../contracts/body-persistence.md)、[备份恢复](../contracts/backup-restore.md)、
[路线图承接](../roadmap.md#模块承接索引)。
