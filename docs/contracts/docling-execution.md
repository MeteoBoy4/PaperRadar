# Docling 显式受限提取

## 用途与范围

`paper_radar.docling_executor.DoclingParser(DoclingRun(...))` 实现 Body 的显式
`CanonicalParser` 边界。通过 `BodyService.extract(paper_id, snapshot_id=..., parser=...)`
执行；构造与 import 不探测现场、不加载 SDK。只处理已附加的 PDF 字节，不接收 URL、
论文题名、DOI、摘要、密码或部分页范围。不提供 parser fallback。

## 规则

### 运行参数与预检

`DoclingRun` 必须明确提供 `model_root: Path`、正有限 `timeout_seconds: float`、
`1..2^63-1` 范围的整数 `memory_limit_bytes`；`threads` 缺省 4，范围 1–32。这些是运行身份，
不改变 extraction StageInput、配置语义或正文消费三元组。

顺序固定为：公共 probe 必要项 → 启用模型部署身份与逐文件 SHA-256 核验 → 根锁 →
复核已有成功、永久失败、预算 → 领取 attempt → 单次 worker。工具链由已验证
`ExtractionSemantics.backend` 与受控清单唯一匹配，后端取同一语义材料的明确选择；
不按现场包版本猜测或切换。probe 的模型/native ABI 仍未评估；doctor 不增加检查项。

模型根采用 SDK 布局：`repo_id.replace('/', '--') / files[].path`。
根内必须提供 UTF-8 `deployment.json`，其唯一格式为：

```json
{"format_version":1,"models":[{"repo_id":"docling-project/docling-layout-egret-medium","commit_sha":"<40位实际commit>","files":[{"path":"config.json","sha256":"<64位实际SHA-256>"}]}]}
```

示例只展示字段；每个启用阶段必须完整登记配置规定的全部推理文件，并按路径排序。
同 repo 不能重复。commit 与 files 必须逐项等于所选配置；文件逐个流式核验。
关闭公式时不核验、复制或加载公式模型；根中未选择的声明不自动启用。
commit 是部署者对文件来源的明确声明；SHA 验证字节身份，不证明 Git 历史。
不能用目录名称或只有裸权重的平铺缓存替代声明。

每次预检把已验证文件复制到独立的私有临时目录，复制过程中计算哈希，文件只读。
worker 只接收该快照，不读取原部署根；原根随后变化不会改变已准备请求。
同一个 parser 的并发请求各有独立准备对象；服务在成功、失败、等待中断或命中已有结果时
均释放本次资源。直接调用 `preflight` 的调用者须对返回对象调用 `close()`；
`DoclingParser.convert` 不提供绕过准备对象的运行通道。预检、哈希与复制不计入 attempt 耗时。
临时快照会额外占用所选模型文件总大小的磁盘空间，容量不足在领取前拒绝。

### worker 与资源口径

父进程启动新 session/process group；worker 先设 `RLIMIT_AS`、禁止 core dump、
建立 Linux x86_64 seccomp，再 import SDK。过滤器继承到后代，禁止网络 socket 系统调用、
io_uring、setsid/setpgid、namespace 逃逸；普通线程及同组子进程保留。
结束、硬超时、异常或取消均对整个组 `SIGKILL` 并等待直接 worker 回收。
原始 stdout/stderr 丢弃，不进入业务日志或异常信息。响应文件最大 128 MiB，坏协议受控拒绝。

`memory_limit_bytes` 是**每进程虚拟地址空间硬上限**，不是 RSS、整组物理内存上限或
cgroup MemoryMax。映射库和 torch 可保留大量虚拟地址；合适数值须由用户 smoke 验证。
不把 EXP-3 样本峰值当通用阈值。整组物理内存与代表性安全余量仍由 F 负责。

`peak_memory_bytes` 固定由父侧 Linux `wait4` 的 worker `ru_maxrss`（KiB）乘 1024，
在回收时取样，硬超时也保留该值；它不是整组 RSS 总和，也不是 cgroup 峰值。
无法启动 worker 时为 0；0 表示没有可用测量，不表示没有内存消耗。
不得与 EXP-3 cgroup 峰值同列比较。总耗时和根锁由 Body 单独管理，不复制等待超时或重试。

exec 环境明确注入 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`、
`HF_HUB_DISABLE_TELEMETRY=1`、`DO_NOT_TRACK=1`、空 `CUDA_VISIBLE_DEVICES`，
并指定私有 HOME/HF_HOME/TMPDIR。OMP/MKL/OpenBLAS/NumExpr 的线程环境值显式等于 threads；
始终提供非空本地 artifacts_path，禁止下载与 fallback。

### SDK 与 canonical

CPU、float32、显式 Transformers engine；不使用自动 engine 或 compile。
所选 layout/formula revision 等于冻结 commit，table mode 取配置；表格结构和 cell matching 开启。
OCR、代码、图片分类、图片描述、图表 enrichment、remote service、external plugin 均关闭。
各 stage batch size=1、queue_max_size=8，SDK 内仍可使用线程；单论文串行由 Body 根锁保证。

标题层级开启，`generate_parsed_pages=False`，维持未保留 parsed page 时的标题信号。
可靠文本层取**同一所选 PDF backend** 在页面存活期间的原生 cell.text 信号，
不依据清理后的空 page.cells 或生成公式文本猜测；不启用 OCR 或第二解析器补足。
只接受 `SUCCESS` 且 input.page_count、result.pages、document.pages 的全页集合和尺寸一致。

映射按 body/furniture 的 children 树 DFS 路径保存阅读顺序，保留结构容器、父关系、
图片子树、全部 provenance、原页号、bbox 原点与逐字符半开 charspan。
标题 level 独立于树深度。未知 content layer、不可达节点、重复/循环引用和缺内容拒绝。
已完成 canonical 中的源 charspan 越界等不修补，由规范正文自动质量永久拒绝；
不 clamp、不重新拼接 orig、不用 text 或候选填源字符。

formula 的 orig/text 分别保留；启用时 text 另存 generated_text 候选，不赋源字符区间。
真实 SDK 没有明确 display/inline 信号时记 unknown。普通 TableCell.text 仅作为受限展示，
不变成 orig/evidence；rich table 的真实源子节点按 table 类型保留。行列结构仍在原始 document
审计 JSON 中。图片本体不取得证据，合法 caption/子文本保留。

原始 `export_to_dict()` 明确移除页面与节点的 image 字段，再拒绝残余嵌入二进制；
不依赖 SDK 的 PLACEHOLDER 导出替代去图。不导出外部图片文件，也不增加第五制品角色。
规范化和恢复不依赖 SDK，沿用[规范正文](fulltext-extraction.md)。

### 持久审计

领取时在 attempt 的可选 `executor_audit_json` 中保存格式 1 静态审计：所选工具链/后端与组件、
模型/配置哈希、normalization、超时、虚拟地址上限、峰值口径、sandbox、线程/batch/queue、
HF 离线变量及原生文本信号。崩溃后的 outcome_unknown 仍能回查本次参数。
旧 attempt 的 NULL 合法，不伪造历史保障。成功四角色 manifest 中的可选 `execution_audit`
必须等于 attempt 审计；恢复核对所选历史语义及二者一致。
旧 manifest 缺该字段时保持原编码字节，不补默认 null，不改角色集合与三元组。

## 错误与拒绝

| 事实与阶段 | 受控结果 | 预算与资格 |
| --- | --- | --- |
| probe 不通过、部署/commit/文件不符、运行参数非法 | `DoclingPreflightError`（参数类型由 Pydantic 拒绝） | 锁前；无 attempt |
| worker 启动、sandbox、SDK import/native ABI、模型初始化失败 | `executor_error` | 已领取；剩余预算内可再请求 |
| 外部硬超时 | `timeout` | 整组回收；已消耗 |
| 明确 MemoryError、OSError ENOMEM、SIGXCPU | `resource_exhausted` | 整组回收；已消耗 |
| 转换阶段 ConversionError/ValueError | `extraction_failed_quality_gate` | 当前输入永久；quality absent |
| FAILURE/PARTIAL_SUCCESS/SKIPPED、缺页/尺寸/内容/完整 canonical | `extraction_failed_quality_gate` | 当前输入永久；quality absent |
| 确认无原生文本层 | `extraction_failed_no_text_layer` | 当前输入永久；quality absent |
| 坏协议、网络失败及白名单外异常（包括单独 SIGKILL） | `executor_error` | 不臆测 OOM；剩余预算内可再请求 |
| 完整 canonical 的证据/字符等自动检查失败 | 规范正文的精确质量失败 | 保存失败制品；永久拒绝消费 |

SDK 内部 timeout 可能产生 PARTIAL_SUCCESS，仍按永久质量失败；只有父侧 hard timeout
记可重试 timeout。执行器内部不重试；跨请求两次预算由 Body 持久管理。
中文预检错误只给原因码与修复方向，不回显模型路径、正文、原始异常或 stderr。

## 不提供／不证明

本边界的工程通过不证明真实模型能加载、真实 PDF 保真、任一公式已精确恢复、四刊质量、
正常生产 Read、外部 Pi、cgroup 资源阈值或 NAS。
真实工程 smoke 由 #164 的用户本人操作，首次 B 前冻结必要语义；四刊与资源覆盖由 F 承接。

## 相关

依据：[#155](https://github.com/MeteoBoy4/PaperRadar/issues/155)、
[#159](https://github.com/MeteoBoy4/PaperRadar/issues/159)。
前置：[轻量 probe](docling-runtime.md)、[提取配置](extraction-config.md)。
组合：[Body 持久服务](body-persistence.md)。
验证与用户 smoke 命令：[独立 D1 台账](../verification/issue-159-docling-execution.md)。
