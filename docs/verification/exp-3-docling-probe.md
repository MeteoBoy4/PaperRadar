# EXP-3：Docling slim/CPU、Python 兼容与样本质量探测

日期：2026-11-03；依据：[#148](https://github.com/MeteoBoy4/PaperRadar/issues/148)；[已接受结论](https://github.com/MeteoBoy4/PaperRadar/issues/148#issuecomment-6594505204)；[授权收口与移交](https://github.com/MeteoBoy4/PaperRadar/issues/148#issuecomment-6594712046)。
执行起点：`cbe4eeee10ee5f3d1f73dfb9bf5b754c7410064f`，`main`，工作区干净。
**状态：本轮探测完成、剩余工作已移交。用户于 2026-11-03 接受“本机固定组合可受限继续；质量缺口移交 Body/F，不开放 Read/reuse”的结论，并明确授权按本口径收口；#148 已以 COMPLETED 关闭。实验票完成不表示 Extra 完成、EXP-3 全部解除或 B 就绪。**

## 分项结论与证明范围

|问题|本轮结论|
|---|---|
|slim/CPU 能否落地|可提供锁定安装候选；不需要完整 `docling` 元包、OCR 包、GPU 依赖或 `docling-parse`|
|Python 范围|本机 Linux x86_64 的 CPython **3.12.14 / 3.13.15 / 3.14.4** 均通过解析、安装、import、模型加载和最小真实 PDF 转换；不外推其他 patch、平台或全部材料|
|固定模型脱网运行|启用的 layout/table/formula 全文件冻结，网络 syscall 限制下 8 次完整转换成功；缺失和损坏文件在探针的加载前守卫被明确拒绝|
|原始样本质量|章节与定位有可用信号，但封面/侧栏/层级和公式候选仍有风险，**原始导出不能直接交给 Read**|
|生产质量门槛|**未验**；本轮没有生产 parser/canonical/normalize/evidence-map，也没有产品质量准入、预算、重试或 doctor 接线|
|建议|**受限继续** Extra 的工程交付与 Body 的生产链设计；不开放 Read/reuse，不宣称 EXP-3 全部解除、B 就绪或四刊 fixture 通过|

本轮没有调用 Screening、Read 或外部 LLM，没有消费真实 Profile。历史 JGR 回归材料不是 B 当轮纵向样本；仍受 [ADR-0036](../adr/0036-isolate-stage-b-read-experiment.md) 约束。

## 主机、用户确认与私有证据

- Ubuntu 26.04 LTS / Linux 7.0.0-31-generic / x86_64；AMD Ryzen 7 255，8 核 16 线程；物理内存约 28 GiB，初次预检可用约 20 GiB；磁盘可用约 787 GiB。uv **0.12.15**，systemd **259.5**。
- 用户在执行前接受：每项进程树 **10 GiB** 硬内存上限、禁止 swap、**4** 个推理线程、单篇 **600 秒** 超时，触限停止；显式联网供给总下载上限 **5 GiB**，磁盘工作预算 **20 GiB**。本轮没有触发资源/超时上限，未实测 OOM/超时清理。
- 私有根：项目下 `.scratch/exp-3/`，已核验 Git 忽略，权限收紧为 `0700`。不用 tmpfs `/tmp` 存大文件；新 Python 3.13、各环境、缓存、模型均在该根下，不改日常 `.venv`、项目 `pyproject.toml` / `uv.lock` 或生产数据。
- 用户指定快照位置 `.scratch/exp-3/backup/`；备份只选择证据成员，排除备份自身及可重建环境/缓存，避免递归。**同实验根、同盘快照不能防整根删除或磁盘故障，不是 NAS/灾备验收。**
- 真实 PDF、源文本、模型、裁切和原始输出只留上述私有根及本地快照；本文只放脱敏结论、标识、哈希和命令，不发布正文或引文。

私有证据索引（相对 `.scratch/exp-3/`）：

|位置|内容|
|---|---|
|`preflight/preflight.md`、`preflight/supply-result.md`|阶段性预检及当时未验范围，历史原文保留；后续确认以本文和本次用户对话为准|
|`metadata/`|第一方响应、请求时间/哈希、wheel HEAD、模型候选、机构库取得事实|
|`candidate/{pyproject.toml,uv.lock}`|实际三解释器 Docling 独立环境的锁定供给|
|`extra-candidate/{pyproject.toml,uv.lock}`|与当前项目基础依赖约束合并的可选 extra 候选，不是产品依赖变更|
|`models/models-lock.json`|实际取得的 16 个启用推理文件、commit、路径、大小和逐文件 SHA-256|
|`preflight/py{312,313,314}-inventory.json`|各解释器 patch、组件版本及初始 import 事实|
|`scripts/parse_probe.py`、`scripts/run_parse.sh`|显式冻结样本、模型哈希守卫、受限执行、原始输出与资源测量；不是产品 parser|
|`outputs/<run>/`、`logs/<run>.log`|逐次 options、结果、原始文档/Markdown、结构检查、异常及完整警告|
|`preflight/run-summary.json`、`preflight/quality-review.json`|重复比较、资源、冻结预期核对及未验门槛|
|`visual/{publisher,osaka}-replay/`|原文件页码/bbox/源 charspan 的局部回放及裁切哈希；不是正式 evidence ID|
|`backup/`|带成员 SHA-256 清单的时间戳快照及独立校验结果，详见该目录索引|

## 样本与人工预期

两份文件均为 DOI `10.1029/2025JD043927` 的 Wada et al. 论文；文件独立冻结，不把同 DOI 当作同字节证明。

|文件|来源/许可依据|页数|PDF SHA-256|
|---|---|---:|---|
|`2025JD043927.pdf`|用户从出版者网站人工下载；首页 CC BY 声明可视核验；具体下载 URL 未提供，不臆造取得记录|16|`ba37741f012d011aa31c19d22aa8750a6e22c7b09ae8f9619a651daf1f9c2b65`|
|`osaka-103589.pdf`|用户授权从大阪大学机构库取得；handle `11094/103589`，页面及真实封面明示 VoR / CC BY 4.0|17|`32358b8af01781712083d3bd0b99bd27120eac4b0636f46428bde7fcc0792d23`|

在任何 Docling 转换前，用本机 Poppler 26.01.0 的信息/渲染工具查看原 PDF 并固定预期；它只辅助人工核查，不是生产正文链或 fallback。用户确认：

- 出版者文件 p1 开始引言，机构库文件 p1 为应排除的仓储封面、p2 才开始引言；**provenance 保留文件原页码，不重新编号**。
- 出版者文件的 Observation p2、Results p4、Discussion/4.1 p7、4.2 p8、4.3 p11、4.4/Conclusion p13、Availability p15；机构库相应文件页码 +1，解析前已补充核查源页影像。
- 主要右侧宽正文，不强迫双栏；左侧元数据/作者贡献、页眉页脚和下载水印不混入主文。摘要与 Plain Language Summary 的范围字符风险、独立公式和宽表均在解析前列出。
- 出版者 p12 / 机构库 p13 的公式 (1)、出版者 p13 / 机构库 p14 的 Table 1 用于局部定位/降级检查。不能用输出倒推人工正确答案。

## 锁定供给与最小组合

实测起点为现有 `docling-2.135.0-cpu-v1`，没有偷换最新版。最终独立候选：

```toml
"docling-slim[convert-core,format-pdf-pypdfium2,models-local]==2.135.0"
"docling-core==2.101.1"
"docling-ibm-models[opencv-python-headless]==4.0.3"
"pypdfium2==5.14.0"
"torch==2.14.1+cpu"
"torchvision==0.29.1+cpu"
"transformers==5.19.0"
```

- torch/torchvision 显式绑定官方 CPU 索引，不允许 PyPI GPU wheel 代替。传递依赖完整固定，实装含 `opencv-python-headless 4.14.0.94`，独立 Docling 环境各 71 个 distributions；没有启用 OCR/全页 VLM。
- **保留的安装反例**：最初不带 headless extra 时，安装和 converter import 都成功，但 TableFormer 实现 import 因缺 `cv2` 失败。只补上游已有 headless extra 后才通过；初始 lock、错误和修正候选均保留。
- 局部公式实际加载/推理证明本样本不需要引入整个 `models-vlm-inline` extra；不把“这组可运行候选”外推成所有 Docling 功能的数学最小依赖证明。
- 独立候选 lock SHA-256：`bec449cd2fd11612d78cc614f3f720b29a381779eb7cce4d849bebfcac08e48f`。
- 与当前项目六项基础依赖约束合并的 extra 候选 lock SHA-256：`252611f1eedfe35f08c2a26cddf41705463d34d1148487a392dedcd450ff9a8c`。该候选只在 Python 3.14.4 安装核验；不等于产品 extra 已交付或全部项目测试在组合环境通过。
- 组合候选第一次离线 sync 因专用缓存缺 SQLAlchemy 等包明确失败，没有隐式联网。用已授权的单独供给命令补齐 3 个包后，离线锁定重查通过。
- 模型实际传输共 **930,878,676 字节**，加机构库 PDF 为 **935,873,378 字节**。三解释器 wheel 集合保守 payload 上界约 **0.88 GiB**，另有 Python 3.13 的 **33.2 MiB**、少量基础组合补包和元数据；远低于授权上限。解压缓存占用不当下载流量。

|启用阶段|固定仓库 commit|文件数|字节数|
|---|---|---:|---:|
|Egret medium|`77ede7cc7bed96d853c58f319734803d6ea2ea5c`|3|78,316,053|
|TableFormer accurate|`fc0f2d45e2218ea24bce5045f58a389aed16dc23`|2|212,765,448|
|CodeFormulaV2|`ecedbe111d15c2dc60bfd4a823cbe80127b58af4`|11|639,797,175|

下载时校验远端 LFS SHA-256 / Git blob 身份，保存全部文件的本地 SHA-256；每次运行前重新逐文件核验。模型清单文件 SHA-256：`a40f0b3d77e1d19d076a5ebec1d10ce274983ad48eec5b05679c5e9ed47ddb66`。未启用模型不登记、不下载。

## 固定配置、脱网与资源口径

采用 pypdfium2 / Egret medium Transformers / TableFormer accurate、cell matching；heading hierarchy 开启，keep_empty_clusters / force_backend_text 关闭，reading-order separators 开启。CodeFormulaV2 局部候选默认开启、Transformers/float32、裁切扩展 `0.18`；CPU、4 线程、单篇串行、显式关闭编译/量化/remote code。关闭 OCR、代码/图片/图表增强、远程服务和外部插件；输出图片用 PLACEHOLDER，不嵌入 base64。完整有效参数随逐次运行保存。

- 模型参数实际观察为 `DFineForObjectDetection`、`TableModel04_rs`、`Idefics3ForConditionalGeneration`，均在 CPU、float32；不是只检查配置声明。
- 干净环境无代理/认证，HF 专用空缓存、offline/禁遥测；运行前后 IPv4/IPv6/Unix 的 socket 创建均被 seccomp 以 EPERM 拒绝，无继承 socket fd。解析后模型运行缓存和 HOME 仍无文件。
- 用户态 `unshare` 因权限失败；用户级 `PrivateNetwork=yes` 未改变 namespace，**不能充当断网证据**。实际使用 systemd seccomp，拒绝网络 IO syscall，唯一允许的 socket 类创建通道是 uv 信号处理需要的本地 `socketpair`。
- 初次把整个 `@network-io`（含 socketpair）全部禁止时，uv 在启动 Python 前退出 134；最小 uv 命令复现，移除 socketpair 禁令后，uv + 父子隔离探针通过。旧日志保留；不是 Docling/Python 不兼容，也没有放开外网 socket/connect/send 等调用。
- 每次 systemd service 具有 `MemoryMax=10G`、`MemorySwapMax=0`、`RuntimeMaxSec=600s`、进程组清理；实际 cgroup 值/事件保存在 run.json。
- 进程树 RSS 每 **20 ms** 采样；另存单进程 ru_maxrss、`/usr/bin/time -v` 与整个服务 cgroup memory.peak。RSS 可能重复计共享映射，cgroup 为实际计费口径，不能混成同一个指标。采样峰值不是严格连续 RSS 极值。
- “首跑/重跑”均为新进程。没有清空系统页缓存；不声称机器级冷启动或冷模型下载性能。表中总耗时包含脚本内部核验、SDK import、模型初始化、转换和导出，不含 uv 外层启动。

## 兼容矩阵与重复测量

以下各版本均完成依赖解析、slim/CPU 安装、import、冻结模型加载及整篇 PDF 转换。

|Python|样本 / 页数|首跑 / 重跑总秒数|转换秒数（模型已加载）|采样进程树峰值 RSS MiB|cgroup 峰值 MiB|
|---|---|---|---|---|---|
|3.12.14|机构库 / 17|24.40 / 24.11|15.24 / 15.06|2910 / 2923|2703 / 2706|
|3.13.15|机构库 / 17|23.69 / 23.75|15.05 / 15.08|3020 / 2960|2764 / 2686|
|3.14.4|机构库 / 17|23.84 / 23.62|15.62 / 15.34|2992 / 3018|2695 / 2721|
|3.14.4|出版者 / 16|22.76 / 22.70|14.52 / 14.39|2999 / 2948|2719 / 2703|

- **8/8 转换成功**，单次模型初始化约 4.0–4.5 秒，cgroup 无 OOM / max 事件。
- 每组重复的原始 document.json、Markdown、源 orig/provenance 抽取哈希相同；机构库材料在三个解释器下的原始输出也相同。只证明本轮固定平台/依赖/样本，不能外推跨机确定性或正式 evidence ID。
- 原始 options.json **整文件哈希不同**：未启用的图片描述配置中 `supported_engines` 是 set，SDK JSON 展开顺序随进程变化。原文件不改写；只针对该 set 字段排序后，8 次 options 的诊断哈希相同。不得把原始 SDK 参数 dump 的哈希直接当稳定 extraction 语义身份。
- 相同论文的两个 PDF 得到不同公式候选尾部；它们是不同字节输入，不是同输入不稳定，但说明不能跨文件复用公式候选身份。
- 探针模型缺失和哈希不符反例各 1 次，均退出 1、保存明确 `model_missing` / `model_sha256_mismatch`，在 SDK 加载前停止。只证明实验守卫，不冒充产品缺失提示/attempt 机制。

原始输出身份（非 production reading.md）：

|样本|document.json SHA-256|raw-reading.md SHA-256|
|---|---|---|
|出版者|`28b7bdf778ea62227c45bdfad55499f23c4eabbdf693b0600c82daef12b16119`|`47b6a426ca045d981be0b2bd1a5ef1c67692e8300afefdc50902f063e7cf092a`|
|机构库|`f24ae371b48cf4d2efaf63db792615f5985621d11cf29bcf0d94a6c2fa3cd18c`|`7c8149a5c210d0d64bca380a95db646f823f0a54f87d945184c244682d63a645`|

## 质量逐项结果（用户已接受本轮结论）

|检查|原始输出观测|后续责任|
|---|---|---|
|封面/正文起点|机构库原页号保留，主文标题位置正确；**仓储封面仍作为表格/文本导出**，不是已去封面|Body：只用文档/版面信号实现 C1 允许范围；不注入题名/DOI/摘要|
|章节与顺序|已确认的 10 个主文/Availability 标题页码及相对顺序均匹配；首页侧栏保留，未编号尾部章节被赋不同层级，左侧致谢优先导出；不能直接采用整棵原始标题树|Body：主文边界、标题树及版式次序；F：其他版式|
|页眉页脚/水印|两样本各 77 个家具项标成页眉/页脚，主体未见期刊页眉反复充当章节；不是逐页完整语义验收|Body/F：规范制品过滤及覆盖验证|
|字符|两份摘要和 Plain Language Summary 的历史范围字符本次保留，没有复现合并错误；全部原始输出 U+FFFD=0。仍有字词粘连、行内科学符号风险|Body/F：冻结回归与安全降级，不用去乱码规则猜字|
|基本 provenance|出版者 245 项/253 个 prov，机构库 250 项/258 个 prov：页码/bbox 基本边界无错，文本 charspan 在 orig 范围内；抽查原页、裁切及源字符切片可回放|Body/EXP-6：持久源成员哈希、恢复闭包；不能由结构边界检查推定每个字符语义正确|
|公式|各检出 1 个公式，orig/prov 与候选 text 可分开回查；**候选包含原公式没有的额外尾部**，两 PDF 的尾部不同。裁切可见源式，未经人工复核不可支持精确结论|Body/EXP-7：源/候选分离、警告、定位占位及规则身份；不改模型配置/裁切迁就结果|
|表格|Table 1 的 7×6 结构可定位；机构库另有封面表格。未逐数值/单元格核对，原始 Markdown 没有生产要求的逐表数值警告|Body/F：显式降级，不宣称数值恢复|
|摘录|Observation 与 Availability 可按已冻结页码和标题定位，后者段落存在；**没有运行正式 excerpt selector**|Body/F：共享规范制品消费与合法未定位降级|
|受限内容与导出|无嵌入 base64；公式/图片/表格的原始导出尚无完整生产定位/警告，不满足可直接消费要求|Body：normalize/evidence/逐文档门槛|
|重复身份|原始文档与源字段在本轮重复稳定；生产 artifact hash、evidence ID、恢复后回放未验|Body、EXP-6/7；不代替产品契约|

SDK `ConversionResult.errors` 为空不等于无警告：完整日志保留了 CodeFormulaV2 的 pad-token 范围和 tied-weights 警告，未修改冻结模型配置去消除它们。候选文本的额外尾部不能被“有输出/公式更可读”掩盖。

## 基础离线环境与复现

日常环境 `find_spec('docling')` / `find_spec('docling_core')` 均为 None。未安装 extra 时运行如下相关子集：**253 passed，27.32 秒，退出 0**；不是全部 pytest 或完整离线门禁，不扩大历史固定分母。只读 `audit-verification-scope --json` 退出 0，受影响组为空；本轮不改冻结材料登记。私有脚本另做语法及实际运行检查，具体证据随快照保存。

```bash
uv run --offline --locked --no-sync pytest -q \
  tests/test_config_extraction.py tests/test_config_extraction_persistence.py \
  tests/test_config_extraction_architecture.py tests/test_config_extraction_validation.py \
  tests/test_config_extraction_cli.py tests/test_stage_input_extraction.py \
  tests/test_stage_input_extraction_reuse.py tests/test_extraction_artifacts.py
```

私有实验复跑（供给已显式取得，使用新的唯一 run 标签；脚本拒绝覆盖旧输出）：

```bash
bash .scratch/exp-3/scripts/run_parse.sh 14 osaka manual-osaka-r1
bash .scratch/exp-3/scripts/run_parse.sh 14 osaka manual-osaka-r2
# 12 / 13 分别选择既有独立 Python 环境；publisher 选择用户原文件。
uv run --offline --locked --no-sync python \
  .scratch/exp-3/scripts/summarize_runs.py
```

`run_parse.sh` 内部执行 `uv run --offline --locked --no-sync`，并施加上述系统级网络、内存、swap、超时限制。重放需要原私有根/模型/环境和原 PDF 哈希；恢复到其他绝对路径时 options 的本机路径字段变化必须披露，不复用旧运行身份。候选 lock 可供联网重建环境，但本轮**没有承诺或验证解释器/wheel 的脱网重建**。

## 移交与仍未验范围

- **Extra**：将候选变成真实可选依赖、锁文件和安装/缺失提示；核对与产品既有锁及支持平台的集成。不改写既有工具链身份；本轮只提供候选，产品仍没有 extra。
- **Body/B**：生产 parser/canonical/normalize/evidence、C1、逐文档质量与资源门禁；真实 B 样本另从当前 Feed 预选并冻结。当前原始导出不得直接授予 Read 资格。
- **EXP-6**：`orig` 持久成员哈希及真实恢复闭包；**EXP-7**：证据/数值警告规则身份，以及是否需要模型重跑的独立分析。
- **F**：四刊正式 fixture、中文、其他版式、复杂表格、摘录/资源阈值及获取通道；本轮两份同论文英文材料不能替代代表性覆盖。
- 未验：跨平台/其他 patch、扫描或无可靠文本层输入的产品拒绝、资源耗尽/超时/产品重试、正式 selector/证据资格、生产根、完整离线门禁、Pi live、校准和 NAS。不得由本轮成功推定这些能力通过。

用户已核对并接受本节版式/风险结论及“仅本机固定组合受限继续”的支持范围；确认记录随私有证据快照保存。此确认不把原始正文变成合格生产制品，也不授予正常 Read/reuse 资格。路线图保留 EXP-3 的产品供给和生产质量剩余义务，由 Extra 工程、Body/B 与 F 按上述责任继续承接，不重复要求本轮已完成的固定组合探测。

## 本轮收口口径

用户明确授权按“本轮探测完成、剩余工作已移交”关闭 #148 并提交文档。五项实验交付的依据分别为：

|#148 交付|收口依据|
|---|---|
|脱敏实验记录|本文的版本/模型/样本身份、兼容矩阵、资源测量、质量逐项结果、复现命令与私有证据索引|
|slim/CPU 与锁定安装候选|两份候选 pyproject/lock 及三解释器实际运行；未装 extra 的基础环境 253 项相关测试通过|
|分层结论|安装/运行兼容、原始样本风险、生产质量未验分别陈述；建议受限继续，不开放 Read/reuse|
|缺口移交|上述 Extra、Body/B、EXP-6、EXP-7、F 的具体交付责任及路线图承接索引|
|人工核对与裁决|用户已接受固定组合支持范围、版式/风险结论，并授权本轮收口；未验项保留而不改成通过|

关闭的是本轮轻量实验票，不是产品 Extra、四刊 fixture 或生产 Read 验收。没有新增产品依赖、变更旧工具链身份或放松质量/校准门禁；后续消费者仍须完成各自工程和真实验收。#148 的早期评论所述“未获关闭授权”仅描述当时状态，由本次明确授权取代，旧评论不改写。

## 第一方依据

- [V1 §4.9 / §13.3](../../intent/draft.md#49-docling-正文提取)、[ADR-0010](../adr/0010-use-docling-as-the-only-body-parser.md)、[ADR-0025](../adr/0025-allow-local-formula-candidates-with-source-review.md)、[ADR-0036](../adr/0036-isolate-stage-b-read-experiment.md)。
- [Docling slim 2.135.0](https://pypi.org/pypi/docling-slim/2.135.0/json)、[IBM models 4.0.3](https://pypi.org/pypi/docling-ibm-models/4.0.3/json)、[PyTorch 官方 CPU 索引](https://download.pytorch.org/whl/cpu/torch/)。原始元数据在私有索引，源码事实以对应已安装 wheel 为准。
- [Egret 固定 commit](https://huggingface.co/docling-project/docling-layout-egret-medium/tree/77ede7cc7bed96d853c58f319734803d6ea2ea5c)、[TableFormer 固定 commit](https://huggingface.co/docling-project/docling-models/tree/fc0f2d45e2218ea24bce5045f58a389aed16dc23)、[CodeFormulaV2 固定 commit](https://huggingface.co/docling-project/CodeFormulaV2/tree/ecedbe111d15c2dc60bfd4a823cbe80127b58af4)。
- [大阪大学机构库 handle 对应页面与许可](https://ir.library.osaka-u.ac.jp/repo/ouka/all/103589/)。
