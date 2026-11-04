# Docling 轻量运行依赖探测 Contract

## 用途与范围

`paper_radar.docling_runtime.probe_docling_runtime(toolchain, pdf_backend, *, requested, enabled)`
为 doctor 与 Body 提供同一 stdlib-only 前置检查。输入来自本次显式选择并已通过
check/load 的配置材料；安装事实不反推 extraction 已启用。模块 import 不探测现场，
不导入 Docling、torch、cv2、模型或其他 SDK。

## 规则

### 显式意图与结果

`toolchain` / `pdf_backend` 使用[受控工具链](extraction-config.md#受控工具链)的
`ToolchainId` / `PDFBackend`。`enabled` 表示已验证材料明确选择 extraction，
不是包存在、配置 readiness 或自动精读门禁。`requested` 是调用方本次明确请求探测的意图。
二者任一为 false 时不读取平台或包库存。工具链和后端必须同时来自同一已验证材料；
调用方不得从非法材料取部分字段、猜默认选择或自动切换后端。

返回不可变 `RuntimeProbe`：

| 字段 | 含义 |
| --- | --- |
| `requested`、`enabled`、`toolchain`、`pdf_backend` | 原显式意图及选择，不随安装情况变化。 |
| `reason` | `RuntimeReason` 受控判断，见下表。 |
| `platform` | `PlatformFacts` 或未探测时的 null；包括 system、machine、implementation、三段 python_version、libc、两段 libc_version、gil_disabled 与 reason。未知事实保留 null。 |
| `dependencies` | `DependencyFact` 元组；逐项提供 distribution、顶层 module、expected_version、installed_version、discoverable 与 reason。 |
| `missing`、`mismatched` | 缺失发行包名；版本不符或发现/metadata 不一致的发行包名。平台拒绝仍单独保留。 |
| `passed` | 仅 reason 为 `dependencies_discoverable` 时为 true。 |
| `next_step` | `RuntimeNextStep` 结构化行动；中文终端展示由 doctor 投影，Body 不解析终端文本或退出码。 |

| reason | 含义 | next_step |
| --- | --- | --- |
| `runtime_not_requested` | 未明确请求，不探测 | `request_runtime_check` |
| `extraction_unselected` | 已请求但未选择 extraction，不探测 | `configure_extraction` |
| `runtime_selection_invalid` | enabled 但缺少工具链或后端 | `configure_extraction` |
| `platform_unknown` | 无法确认关键平台事实 | `prepare_supported_platform` |
| `platform_unsupported` | 已知范围外平台 | `prepare_supported_platform` |
| `platform_supported` | 仅 `PlatformFacts.reason`：平台子项元数据匹配，不是 `RuntimeProbe.reason` 返回值 | 无（平台子项不提供 `next_step`） |
| `dependency_missing` | 顶层模块与 metadata 均缺失 | `sync_locked_extra` |
| `dependency_inconsistent` | 二者不一致，或发现/metadata 无法读取 | `repair_environment` |
| `dependency_version_mismatch` | 现场版本不等于所选清单的精确版本 | `match_selected_toolchain` |
| `dependencies_discoverable` | 所检依赖可发现且版本匹配 | `consumer_runtime_checks` |

必要平台范围为 Linux x86_64、glibc >=2.28、普通 GIL-enabled CPython 3.12–3.14。
libc 由本机 `CS_GNU_LIBC_VERSION` 读取；不运行外部命令。GIL ABI 读取
`Py_GIL_DISABLED` 与解释器 ABI 标志；CPython 3.12 不存在 free-threaded 构建，
其缺省标志按该解释器保证处理。free-threaded 构建即使临时启用 GIL 也拒绝。
系统、架构、libc 或 ABI 的未知关键事实阻止 passed；marker 跳过不能充当成功依据。

`paper_radar.docling_runtime.docling_platform_facts()` 按需返回上述 `PlatformFacts`，
供 probe 与显式安装 smoke 共用平台分类；不读取依赖库存、不导入 SDK。
模块导入仍不读取现场。安装 smoke 复用平台拒绝原因，在 SDK import 前拒绝
不支持或关键事实未知的平台，成功 JSON 的 `gil_enabled` 来自同一构建 ABI 事实。

包版本来自 `backend_identity` 展开的实际消费组件，以及 `toolchain_supply` 的
`cli_constraints`，不维护第二份版本清单。两个后端都需要 pypdfium2；仅 threaded
要求 docling-parse，pypdfium2 不受未消费 parse 的安装或版本影响。v1 仍按原 core
检查，不由 v2 现场组件重新解释；Typer 只按所选供给约束检查，不进入 extraction 语义。
TableFormer 另要求 `opencv-python-headless` metadata 与顶层 `cv2`；具体版本由产品锁约束，
不另造 extraction 语义版本。模块只做顶层 `find_spec`，不使用带点名称以免导入父包。

平台错误优先决定总 reason；支持平台中，发现不一致/版本不符优先于缺失。
逐项结果完整保留，不能只凭总 reason 推断所有组件的状态。

### doctor 投影

[doctor](doctor.md) 的 `--scope docling-runtime` 将相同结果放在既有
`docling_fixture` 类中，检查名为 `docling_fixture.selection`、`.platform`、
`.dependency.<distribution>`。缺包和未选择为 missing；版本不符、发现不一致、
不支持或未知平台为 invalid；必要项全部通过才是范围 passed / 退出 0。
中文下一步点名组件、要求版本及安装或选择修复方式，不回显原始配置和异常内容。
模型、native ABI、质量/fixture、资源分别以 `.models`、`.native_abi`、`.quality`、
`.resources` 列为非必要 not_assessed，不阻止仅依赖范围成功。整个 Docling fixture
类别仍为 not_assessed；安装子项通过不产生 fixture gate、executable 或 Read/reuse 资格。
此范围只展示基础、选择、平台、依赖和 Docling 的未验项；其他阶段 readiness、Profile
及外发说明由 `config` 范围展示。

## 错误与拒绝

调用方先处理配置错误；doctor 保留 `ConfigReason`，配置非法时不调用探测。
历史快照只提供声明身份，不包含或恢复旧机器环境；历史有效而现场 mismatch 是合法组合。
不安装、不联网、不下载模型、不修复环境、不猜 enable、不执行 parser 或自动 fallback。
缺依赖指向显式锁定 extra 安装；历史版本不符要求准备符合旧清单的隔离环境，或显式声明
新配置并重新 check/compile，不能靠诊断改写历史。

## 不提供／不证明

passed 只描述此刻的模块发现与版本，不证明随后 import 必定成功、native ABI 兼容、
模型已取得、模型可运行、PDF 可解析、fixture 合格或资源足够。环境在探测后可变化。
Body 只有在明确请求且必要检查通过后才可延迟 import SDK；仍须处理 import、ABI、
模型和解析异常，不能把探测当作永久执行许可，也不能因失败自动 fallback。
后续生产转换、模型缓存、逐文档质量与资源验收由[Body/F](../roadmap.md#module-body)承接。

## 相关

依据：[Extra #150](https://github.com/MeteoBoy4/PaperRadar/issues/150)、
[公共诊断 #153](https://github.com/MeteoBoy4/PaperRadar/issues/153)。
实现：[`docling_runtime.py`](../../src/paper_radar/docling_runtime.py)；
[D1 覆盖](../verification/issue-153-docling-runtime.md)。
