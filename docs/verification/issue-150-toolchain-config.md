# Extra 配置工具链独立覆盖

依据：[#150](https://github.com/MeteoBoy4/PaperRadar/issues/150)、
[#151 及身份分层补充](https://github.com/MeteoBoy4/PaperRadar/issues/151#issuecomment-6607207118)。
实施起点、integration 起点均为 `542265c0971fb0e8bcee4c2a7019295fc9686ac7`，
分支 `feat/issue-151-docling-toolchain`，独立 worktree，开始时工作区干净。

## 范围与独立覆盖

本切片交付 v2 选择、权威组件与 CLI 供给视图、配置 check/compile/load、
新声明版本的两个完整合成示例、extraction 投影与 StageInput 独立向量。
新增 D1 模块 `tests/test_docling_toolchain_v2.py` 共 15 项，不绑定 A1–A10 required
集合、成员、计数或回执；不扩大历史固定分母，保持 `stage_a_verified=false`。

| 可观察边界 | 新增用例数 | 覆盖 |
| --- | --- | --- |
| 公共 check/compile/load | 2 | 两后端精确解析组件、完整快照回放 |
| stdlib 清单供给入口 | 1 | `-I -S` 冷进程、Typer 与 parse 供给/语义分离 |
| 完整示例与 CLI | 2 | 新声明版本、显式 selector/backend、check/compile/load |
| extraction 投影与 StageInput | 2 | 独立字面量、精确 core/backend 差异、旧快照保留 |
| 声明版本 | 1 | 新字节登记改变快照但不改变语义或输入 |
| 配置拒绝 | 4 | 未知工具链/后端、独立覆盖组件/后端版本 |
| 历史展开一致性 | 2 | v1/v2 伪造 core 后重新计算外层哈希仍拒绝 |
| 历史冷进程回放 | 1 | 删除原配置，拒绝 SDK 导入、依赖库存查询和网络仍可回放旧新快照 |

普通开发回归同时运行既有 extraction 配置、持久化、CLI、StageInput 模块与 CLI
兼容组合；这些是现有消费者回归，不继承其历史验收结论。完整离线门禁与 extra 安装
不在本子票执行范围，组合结论由 #154 收口。

开发期实测（普通未安装 extra 的 Python 3.14.4 环境）：

- 新独立模块 15 项通过；另与 extraction 配置/持久化/CLI/校验、投影和 StageInput
  消费者组合共 281 项通过。
- `./scripts/check-compatibility cli`：59 项通过，退出 0。
- 本次两个生产模块和新增测试模块的 Ruff、格式检查与 mypy 均通过。
- 只读 scope 审计退出 1；无 baseline issue，current_change 仅旧清单兼容入口的
  A2-01、完整 A2、A10 三处 `hash_drift`，属于 source/support mechanical；未做重绑。
  新增 source 的消费闭包与 D1 材料仍由最终组合审阅登记。

首次 v2 两后端测试先因 `extraction.toolchain` 不支持而失败；轻量供给入口测试先因
模块不存在失败；两个新示例先因文件缺失失败；独立向量先因 fixture 缺失失败。
各切片随后完成实现并通过。冷进程额外核对公共 check/compile 与历史 load 不使用 SDK、
现场依赖库存或网络；回放还在删除原配置后再次通过。

## 人工预期依据

`tests/fixtures/docling_v2/` 是新的合成期望，无 PDF 或本机模型字节。
projection 字面量按 Contract 的固定 policy、合成模型声明与 #150 精确组件独立组装，
仅用 stdlib JSON 规范编码和 SHA-256 核算；没有导入生产配置、投影或 builder 生成答案。
同组人工数据在 core 保持 `2.101.1`、pypdfium2 时先核对旧 projection
`b22ab98cea14fa830d125119b94c051403a7c01eced0ec526e172df74ebb0125`。
随后只将 core 改成 `2.105.0`，threaded 另增加 parse 及固定后端选项。
原 `tests/fixtures/stage_inputs/extraction-v1.*`、旧清单值与旧示例原字节保持。

| v2 后端 | projection_id | StageInput fingerprint |
| --- | --- | --- |
| pypdfium2 | `7ae647dbf244f18763bae50d3e8eac13bed4b0daba52cb008d6dbee47e674583` | `d18f4644a81f4d6e27e43c1bded82f6a972d3e9908e5f73c48f12e628e49c754` |
| threaded_docling_parse | `0a6dd3d1fbc4c5f67445255aae0ddf2ccaad356362624f591035a6b1245569bf` | `d2cb93c0f6a76bd18ddf3cf981e5ce93f266eb3c6b0aa86d62b0d099ed6c3a53` |

两者输入事实都为合成 PDF 哈希 `1` 重复 64 次。声明标签不进入这些载荷，
模型身份、policy、normalization 在 core 变化时均保持；Typer 和现场供给不进入语义。

## 消费接口与剩余责任

`paper_radar.docling_toolchain` 可独立用 stdlib 导入：

- `backend_identity(toolchain, pdf_backend)`：所选后端实际消费的解析组件。
- `toolchain_supply(toolchain)`：不可变 `ToolchainSupply`，解析供给的
  `component_versions` 与 CLI 供给的 `cli_constraints` 分列；v1 未冻结 Typer，约束为空。
- 原 `paper_radar.config.extraction_toolchain` 的类型和函数 import 继续可用。

#152 负责产品 extra/单锁与真实安装；#153 消费清单实现显式现场诊断，区分合法历史
与 runtime mismatch；#154 负责组合回归、scope 审计/S3/必要重绑、最终有 extra 完整门禁。
本切片不探测或下载模型，不执行 PDF，不验证 native ABI、正文/证据质量、资源或 Read/reuse
资格；这些边界继续见路线图 Extra、Body/B/F。

固定范围基线无漂移；本切片只读审计报告 current_change，涉及旧
`config/extraction_toolchain.py` source 哈希及新增未绑定覆盖材料，交 #154 按实际集成树
解释和重绑，不机械更改 scope 或旧回执。
