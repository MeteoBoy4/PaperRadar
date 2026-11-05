# 真实 Docling 单样本工程核验

本记录冻结 2026-11-05 用户本人执行的生产链 smoke 及其后只读审计，依据
[#164](https://github.com/MeteoBoy4/PaperRadar/issues/164) 与
[#155 最终裁决链](https://github.com/MeteoBoy4/PaperRadar/issues/155#issuecomment-6632720328)。
真实 PDF、正文、引文、SDK 原始输出、数据库和恢复副本只保存在本机私有材料目录；
本文仅发布安全计数、身份摘要、资源口径与工程结论。

## 身份与执行范围

用户本人确认材料、合成工程容器和资源后，在 `2026-11-05T06:46:07Z` 启动，
`06:46:30Z` 完成。使用合法持有的 EXP-3 出版者主样本，PDF 为
4,859,363 字节，SHA-256 为
`ba37741f012d011aa31c19d22aa8750a6e22c7b09ae8f9619a651daf1f9c2b65`；
未使用额外对照。论文登记明确为合成容器，只承载用户确认的 PDF，未伪造真实 Feed、
HTTP 来源或元数据发现，不是 B 当轮 JGR 样本。

原始 invocation/result 共同绑定下列身份；后续文档提交不取得该次 smoke 或门禁结论：

| 项目 | 冻结值 |
| --- | --- |
| commit / dirty | `811adfd7dab680e86c55521e2d71e0c8d69d4438` / false |
| 完整主工作树 SHA-256 | `faa6858e04308ded848a0413ee9b6117bf10ce1a108d0dad98ea112a41926fe6` |
| uv.lock SHA-256 | `fcd6149e80b961d9bfa3c9b0015f3ddf2835c830f03b956506f300353c0f0905` |
| extraction_fingerprint | `338b79c931514c980bd4b6a03c8ad87a5c0c04b856b172dc3814e7e52385b3c0` |
| extraction artifact_id | `d26d57c7d5e2fd3836e3b920fec1772237ba79dd04c9bedc23d7ece0d81cede1` |
| backend_config_hash | `c5ab2231b523d646b9766610c262fcc602fc6c6d9b2803bd011c813d3e53adcb` |
| model_artifacts_hash | `9bf7033cd2276ae51d15b3ae561c7931ccfcce948a42ab09b0f547e5ebfb133b` |

主树原始结果身份与当时 HEAD、dirty、完整树及 lock 逐项相等；独立 worktree 的文件权限
可能不同，因此其树摘要不冒充原始执行树。原始四份记录保留原字节：

| 本地记录 basename | 字节 | SHA-256 |
| --- | ---: | --- |
| `20261105T064607Z-0d68bbaf.json` | 5,156 | `3d6127c5cdef89bfac668a7932c9bb2be24daa704b0357b03d4b64160831cd32` |
| `20261105T064607Z-0d68bbaf.invocation.json` | 1,851 | `988fa22cdd3f9656a641534505e63adb567a8b61c17b04270203e4f8ce78873a` |
| `20261105T064602Z-2738714.resources.json` | 399 | `5270cca2f3e3146e0808d57f1b75d0ad61d381dfb69129134c1908f9ef78711b` |
| `20261105T064602Z-2738714.operator.log` | 487 | `2fdcf12b010697d1b869aad592d52a77a955f99e09a49afa224e9c0d6d74212d` |

执行采用 Python 3.14.4、CPU 工具链 `docling-2.135.0-cpu-v2`：docling-slim 2.135.0、
docling-core 2.105.0、docling-ibm-models 4.0.3、docling-parse 7.22.2、pypdfium2 5.14.0、
torch 2.14.1+cpu、torchvision 0.29.1+cpu、transformers 5.19.0、pydantic 2.13.5。
模型部署冻结 16 文件、930,878,676 字节；不下载模型。受控参数及组件版本与
manifest.execution_audit、attempt 和结果一致。生产链为 Docling adapter → canonical →
normalize/evidence → 自动检查 → Body 持久登记，实际新产出 evidence-map；未复用 EXP-3 旧 document。

## 制品与来源保真

通过 `BodyService.validate_all()`、`ArtifactStore.read_artifact()` 与
`FulltextArtifacts.load()` 读取新登记四角色及已附加 PDF；逐成员重新计算长度与 SHA-256：

| 角色 | 字节 | SHA-256 |
| --- | ---: | --- |
| document | 245,748 | `77afb1aff1153ae9dad3d60976bb782e13310f4293c4546e8a5c6a80528a9e06` |
| evidence_map | 353,471 | `0f813e3d97e21e1c38ee21f309b2e2d0701f625f3c296efc574c57b5101bda02` |
| reading | 64,961 | `aab0802d7c5b4fe4b9fa6a37017ff335fd53ae200dc5e094ba5eb31223599d7b` |
| manifest | 1,669 | `eaebc9cd11a19f6bb389ab266b71b57f71e05b4b44a1bbada98498bfdc0c1219` |

已附加 PDF 与用户原文件逐字节相同。manifest 内 document/reading/evidence-map 哈希、
提取指纹、配置和模型身份均闭合；四角色合计 665,849 字节，不增加角色或改三元组。

不导入 SDK 的只读审计沿 document 已声明的 body/furniture 子节点深度优先阅读路径，
与规范 reading_blocks 的稳定序号逐一配对，核对父子关系、content layer 和源类型。
map 不保存 parser 原 ref，核对不依赖 ref 名称猜测顺序。16 页尺寸、248 阅读块的全部
253 条 provenance 与 SDK 导出逐项对应；bbox 原点转换、原页码和 charspan 保留。
216 个源块的 orig/text 全部逐字一致，共 64,981 个源 code point、65,732 个 UTF-8 字节、
224 条源 provenance；所有源块包括被排除块均通过完整非空切片及源字符覆盖检查。
其中 4 块 orig 与 text 不同，未以 text 替代 orig。

139 个 evidence 对应 147 条非空切片，逐条等于持久 orig 的原始半开区间切片，
不作字符归一化。公式生成候选单独保存，源展示仍为 orig，候选和占位没有 evidence 锚点。
生产 load 重算规范 reading、内容身份、源/生成分离与自动质量，自动检查通过。
这些检查证明真实 SDK 导出与持久来源一致，不证明 parser 对 PDF 科学内容或版式判断正确。

## 公式统计与分支

分母沿用执行前已定口径：`label=formula` 项总数；分子要求逐字 orig、完整
页码/bbox/charspan、非空可回放切片及非空白源字符全覆盖。其余归仅占位/无源块，
不在执行后缩小分母。以下由持久 map 重算并与原结果及生产 statistics 一致：

| 分类 | 总数 | 有父源块 | 仅占位/无源块 | 结论 |
| --- | ---: | ---: | ---: | --- |
| display（行间） | 0 | 0 | 0 | 未覆盖，不计算百分比 |
| inline（行内） | 0 | 0 | 0 | 未覆盖，不计算百分比 |
| unknown | 1 | 1 | 0 | 此未知类别样本 1/1 可回放 |
| 全部 | 1 | 1 | 0 | 仅此单样本，不外推各类别 |
| 行内是否独立成 item | — | — | — | 本次没有独立 inline item；不能判断 PDF 是否存在行内公式 |

本次 1 个公式候选与父源字符分离；该公式保持 unknown，不能凭版面先验或候选形状
改称 display。观测到的未知类别符合「有父源块」分支，可受限引用并附未核对警告；
行间/行内类别尚未覆盖，按类别缺口明示，不能宣称公式整体完整支持。
本次未观测到无父源块公式，不伪造该类数量或将其称为已验证。

能力上限仍是：没有可回放父源块的公式不能提供源证据，候选或占位不能补位。
ADR-0041 已接受正文的三分支继续适用；其状态行链接本记录，规格受限内容矩阵与
GLOSSARY 同步表达能力边界。本次没有新决策，不修改已接受 ADR 正文。
类别、图片型公式、四刊/中文/复杂版式覆盖与二次提取、裁切展示由 B/F 承接；
类别缺口不额外阻塞 B 接线，Body 模块最终收口另由集成验收完成。

## 资源与资格

| 口径 | 实测或显式限制 |
| --- | --- |
| manifest 转换耗时（不含发布） | 21.85530440788716 秒 |
| attempt 耗时（含发布结算） | 21.93598016537726 秒 |
| 总 wall（含准备） | 22.857429862953722 秒 |
| worker 峰值：Linux wait4 ru_maxrss KiB × 1024 | 2,883,112,960 字节 |
| 外层 cgroup memory.peak | 3,726,348,288 字节 |
| cgroup 物理内存上限 / swap | 10,737,418,240 字节（10 GiB）/ 0 |
| SDK RLIMIT_AS 虚拟地址空间上限 | 34,359,738,368 字节（32 GiB）|
| 转换 timeout / 外层单元 timeout / threads | 600 秒 / 720 秒 / 4 |

worker 与 cgroup 峰值分别报告；RLIMIT_AS 是虚拟地址空间限制，不能当物理峰值。
本次 1 次 attempt 成功、剩余 1 次，未发生超时或 OOM；失败映射的现场分支未触发。
本次测量不形成通用资源阈值，代表性资源责任仍归 F。

自动质量通过，但没有人工六项版式核查：`quality_basis=absent`、failure=null，
未授予 experiment_document_gate 或 formal_gate，Read 未运行。
原文件逐字保存及自动回放不替代真实版式核查、正文起点/章节/页眉页脚人工判断。

## 无 extra 冷恢复与原根隔离

复用只读实际 base + dev 环境：35 个 distribution，metadata 确认 docling、docling-core、
docling-slim、docling-ibm-models、torch、transformers 均缺失；PYTHONPATH 明确指向本次
独立 worktree 源码。未复制虚拟环境、联网或安装 extra。

1. 生产 `create_backup` 生成自包含批次；随后在 cwd 为树外临时目录的新进程执行
   `verify_backup`、`restore_backup`、`verify_contents`、Body 事实重验、ReadContext 重建
   与逐字回查。审计钩子在 API 调用前拒绝原业务根、原 PDF 目录、模型部署与原 extra 环境，
   4 个拒绝探针实际生效，同时禁止外部进程、网络与 SDK 导入。
2. 将恢复根整体移动到第二个位置；再启动一个新 base 进程，额外屏蔽首次恢复位置及
   备份批次，6 个拒绝探针实际生效。仅凭迁移后的库和成员再次完整重验、重建并回查。
3. 两次都恢复同一 experiment 根、三元组、139 evidence / 147 切片及 216 源块，
   与原回放摘要逐字节相同；剩余预算仍为 1、质量仍 absent，普通消费保留
   `ordinary_consumption_denied` 与 `quality_absent`。没有回收租约、激活配置或调用模型。

恢复根登记 ID 的 UTF-8 SHA-256 为
`e40f0f636eea2a6fc7977093750288454ba28a2364c7af398412c0b1ca92f739`；
原 ID 与具体恢复位置留在私有报告。备份清单 SHA-256 为
`2967458f0ffb9f804aab2521945fb2453ab3ccb1a263395a66ae9da064bcc1ea`。
批次包含 1 个配置快照、3 个制品、6 个独立 blob，共 5,525,318 个 blob 字节。
备份与迁移后恢复根清单/数据库/blob 完整字节一致；6 个 blob 的原件、备份、恢复件
inode 均各自独立，未以硬链接依赖原根。

源业务库逻辑 dump SHA-256 与业务目录逐文件长度、SHA-256、权限库存，在备份前、
备份后和两次冷回查后完全相等；原 PDF 字节保持。备份与恢复根各自查询前后库存也相等。
原始 invocation/result/resources/operator 四文件身份再次核对相等，原始证据未搬迁或改写。

实际只读脚本及报告保存于本机 smoke 的私有 verification 子目录。
下列是执行命令形式；变量值、完整命令与本地输出随私有材料保留，公共记录省略绝对位置：

```bash
UV_PROJECT_ENVIRONMENT="$BASE_ENV" UV_CACHE_DIR="$CACHE" \
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$WORKTREE/src" \
uv run --offline --locked --no-sync --project "$WORKTREE" python "$VERIFY/audit_164.py"
# 以下两条在树外 cwd 中分别启动新进程
UV_PROJECT_ENVIRONMENT="$BASE_ENV" UV_CACHE_DIR="$CACHE" \
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$WORKTREE/src" \
uv run --offline --locked --no-sync --project "$WORKTREE" python "$VERIFY/cold_164.py" restore
UV_PROJECT_ENVIRONMENT="$BASE_ENV" UV_CACHE_DIR="$CACHE" \
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$WORKTREE/src" \
uv run --offline --locked --no-sync --project "$WORKTREE" python "$VERIFY/cold_164.py" moved
```

文档收口的开发验证使用同一 base 环境：

```bash
uv run --offline --locked --no-sync pytest -q \
  tests/test_fulltext_artifacts.py tests/test_fulltext_normalization.py \
  tests/test_fulltext_quality.py tests/test_fulltext_restore.py tests/test_body_recovery.py
uv run --offline --locked --no-sync pytest -q tests/test_live_document_links.py
```

结果分别为 39 passed（19.23 秒）与 4 passed（0.05 秒），无 skip/deselect；
只核验现有生产制品与恢复边界，未新增测试模块或扩大历史分母。

## 不能证明的范围

本次是显式 HITL 单样本工程 smoke，后续 agent 仅核验已保存材料。
没有重新转换 PDF、再次运行模型或对原库写入业务事实。
它不进入 check-offline，不是完整离线门禁、正式质量门禁、四刊通过、正式校准、
B 当轮 JGR 纵向闭环、生产 Read、Pi live 或 NAS 恢复证明。
原始 SDK 导出与来源保存的一致性，不证明科学语义蕴含或 parser 对真实 PDF 的全部保真。
Body 状态仍由[路线图模块](../roadmap.md#module-body)及最终集成验收决定；
B 负责真实选样/版式与产品接线，F 负责未覆盖类别、四刊质量、裁切与资源门槛。

相关：[正文契约](../contracts/fulltext-extraction.md)、[持久化契约](../contracts/body-persistence.md)、
[备份恢复](../contracts/backup-restore.md)、[ADR-0041](../adr/0041-self-contained-evidence-map.md)。
