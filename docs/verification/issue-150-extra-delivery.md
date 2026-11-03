# Extra 工程覆盖与最终门禁判据

依据 [Extra #150](https://github.com/MeteoBoy4/PaperRadar/issues/150) 与
[组合收口 #154](https://github.com/MeteoBoy4/PaperRadar/issues/154)。
实施起点为 `main=542265c0971fb0e8bcee4c2a7019295fc9686ac7`；组合功能验证树为
`ac584cb9fee10e4df0f9372a5a59e3b9907bb3ca`，已包含 #151/#152/#153；
测试另包含本票的 ABI 人工事实修正，精确 dirty 身份与材料 SHA 留树外。
本台账冻结工程覆盖、证据适用性与最终判据。完整验收结论待全部合并、独立审阅修复和
身份材料冻结后的树外回执；本文不宣称完整门禁已 passed。

## 交付主张与证据索引

| 父规格主张 | 实现与可审查材料 | 证据适用范围与未证明事项 |
| --- | --- | --- |
| US1、3、16：CPU extra、单锁与三解释器 | `pyproject.toml`、`uv.lock`、[安装台账及库存](issue-152-docling-installation.md) | 3.12.14 / 3.13.15 / 3.14.4 的真实安装、pip check、两个后端、TableFormer/Transformers/cv2/CPU import；支持声明不扩展到其他 patch、平台或 ABI。 |
| US8–12：独立 v2、旧身份、示例与后端语义 | [清单与配置 D1](issue-150-toolchain-config.md)、[extraction Contract](../contracts/extraction-config.md)、[StageInput](../contracts/stage-inputs.md) | 两后端公共 check/compile/load、独立 projection/StageInput 字面量、v1 历史原意。安装包存在不改变语义，不证明生产 parser。 |
| US2、4–7、13–15：显式诊断与基础能力 | [运行依赖 D1](issue-153-docling-runtime.md)、[公共 probe](../contracts/docling-runtime.md)、[doctor](../contracts/doctor.md) | 支持范围/版本/缺包/选择与四态、退出码、只读和无 SDK/网络；passed 仅证明可发现且版本匹配。 |
| US17：最终 extra + dev 完整门禁 | 下节同树、同 run 判据；正式回执与外部前后库存 | 当前开发矩阵、静态检查和兼容组合均不替代；最终 run_id 仅留树外，不回写本台账。 |
| US18：历史边界与独立新增覆盖 | 下节 D1、固定材料审阅与精确重绑 | 不新增验收组、required、旧成员或分母；历史回执、冻结负例和历史证据原字节保持，`stage_a_verified=false`。 |
| US19–20：模型供给与责任 | [安装边界](../contracts/extraction-config.md#cpu-extra-安装与支持面)、下节移交 | 缓存不足时离线拒绝；不自动取得模型，不证明模型加载、正文/证据质量或 Read/reuse。 |

## 独立 D1 与实际组合

| 未绑定测试模块 | 节点数 | 原始登记 |
| --- | ---: | --- |
| `tests/test_docling_toolchain_v2.py` | 15 | #151 |
| `tests/test_docling_extra_supply.py` | 3 | #152 |
| `tests/test_docling_runtime.py` | 36 | #153 原 34；本票补 2 |
| `tests/test_doctor_docling_runtime.py` | 5 | #153 |
| `tests/test_docling_runtime_process.py` | 26 | #153 |
| 合计 | 85 | 不进入 A1–A10 固定回执 |

#154 在公共 probe 边界补 2 个 ABI 节点：真实 3.12 首次补跑发现原负例隐式依赖
宿主 minor；未知 ABI 负例改用显式 3.13，不可读事实分别检查 3.12 的 GIL 构建保证与
3.13/3.14 的 unknown 拒绝。生产行为不变；原 #153 台账保留当次 34/65 的原计数与原字节。
真实安装组合以当前最终产品锁执行；三环境各保有 extra + dev，无 extra 环境只有基础与 dev。
配置材料为合成声明，不含本机模型/PDF。每个环境验证两后端 v2、旧 v1 与 extraction
未选择，均经公共 check/compile/load；basic 单独运行，config/docling-runtime
分别消费 settings 与已保存 snapshot。旧 v1 在新环境仍合法 load，但 core 2.101.1 对
现场 2.105.0 报 mismatch；安装不使未选择变 enabled。删除原配置后仍能历史 load。
冷进程沿用独立哨兵，真实发现平台/包事实，同时禁止 SDK import、网络、子进程和业务写入；
doctor 前后目录字节与逻辑数据库不变，模型/native ABI/质量/资源继续 not_assessed。

实际命令、退出码、解释器与 sys.prefix、editable 来源、完整库存、stdout/stderr 和
前后适用性比较保存在本机树外 `.scratch/issue-150/154-evidence/`。
它们是开发组合材料，绑定上述功能树；最终提交或 merge 身份由最终唯一执行者重新记录。
首次环境选择失误的作废过程单独保留于 `.scratch/issue-150/154-invalid-attempt/`，
不计为通过；后续所有非默认解释器调用显式固定 `--python`。

## 前置证据适用性

#152 原 Markdown/JSON、安装日志和原始库存均保留原字节。复用前逐项比对
`pyproject.toml`、`uv.lock`、权威工具链清单、旧 import 兼容入口、v2 示例及
`scripts/check_docling_imports.py` 的身份；这些供给/语义材料在 #152 提交 `34beefe`
与组合功能树相同。锁 SHA-256 为
`fcd6149e80b961d9bfa3c9b0015f3ddf2835c830f03b956506f300353c0f0905`。
基础六包的完整 package 记录、来源、依赖边、制品和哈希保持；其他既有依赖记录也未变，
仅产品 editable 记录增加 optional 依赖，锁新增 50 个包记录及平台求解 marker，无删除。
旧安装事实适用于相同锁/声明，不被改称当前 HEAD 已安装验收。

#153 新增 probe、doctor 与根 CLI 接线，是行为相关变化，因此本次在每个目标解释器
重新同步当前 editable、核对库存、pip check 与显式 SDK import，并补跑公共组合及相关
pytest；普通 `uv run --offline --locked` 前后核对库存以观察 extra 保留。
没有生产 parser/options 或实质解析变化；EXP-8 模型/选项适用性继续以 #152 的逐文件
核对为依据，没有把 EXP-3 的旧 core 或两后端不同原始输出提升成产品正文验收。

## 固定材料审阅与必要重绑

显式以稳定本地 `main=542265c` 为 base/target 分析；该实施起点审计无漂移。
#151/#152/#153 子票起点出现的继承漂移均为本 spec 的 `current_change`，没有
`baseline_drift`。原候选共 15 条 hash drift，仅按下列五个精确路径修复登记：

| 路径 | 写入位置 | 审阅结论 |
| --- | --- | --- |
| `src/paper_radar/config/extraction_toolchain.py` | 中央单键 | 旧 import 兼容入口转发到 stdlib 权威清单；v1 展开/历史回放保持，v2 独立；source/support 机械哈希。 |
| `src/paper_radar/cli.py` | 中央单键 | 新显式 scope 帮助；不改变已有 scope 默认/拒绝规则；source/support 机械哈希。 |
| `src/paper_radar/pi_supply/cli.py` | 中央单键 | 显式范围注册、参数与薄投影；保留 Pi scope、安全拒绝及 0 的边界；source/support 机械哈希。 |
| `pyproject.toml` | 中央单键 | 完整 A2 为 source、A10 为 fixture，整体敏感；CPU extra、最小特性、marker、三 minor 求解与显式 CPU source；基础依赖/支持面/开发工具和测试配置保持。 |
| `uv.lock` | A10 原单组字面量 | fixture 敏感；同锁添加 CPU 供给且旧包记录保持，旧 A10 fixture/标准/分母不改。 |

`pyproject.toml` 的全部影响组为完整 A2、A3、A4、A5、A6、A7、A8、A9、A10；
分别审阅配置、恢复、供给、指纹、论文事实、Screening、RPC、Read 和摘要审计消费者。
`uv.lock` 影响 A10；`scripts/a10_scope.py` 的 entry 摘要因该单条 fixture 哈希重绑
变化，另作 A10 registration 敏感确认。成员、kind、用途、计数、格式、required 和
41 条显式 refs 均保持，不以 source 更新扩大旧结论。
完整逐路径/逐组人工理由、旧新 SHA 与 entry 摘要留在树外审阅白名单。
身份变化后仅理由可供复核，确认记录必须按最终 HEAD/target/完整树重新生成；不自动全接受。

相关消费者另发现并修正实施起点已有的迁移守卫缺口：main 原审计和本次审计同为
1214 个材料登记，`tests/test_scope_shared_dag.py` 仍只枚举 1175 + 28 + 10 = 1213。
缺项是 [#146 既有授权](issue-146-review-followup.md) 的
`A10/source/src/paper_radar/fixture_audit/abstract_versions.py`，其原新增来源见
[原重绑清单](issue-146-review-rebindings.json)。修前真实失败记录与基线证明留树外；
本次仅在未绑定守卫显式补这一条人工期望，继续逐组核对精确集合、计数和 41 refs，
不从当前生产登记生成答案，不增加生产成员，不修改 #146 原证据。该模块仍为 24 节点。

历史查询/基线 CLI 测试还显式使用 `ROOT/.venv`；首次外置环境运行因本树缺该路径失败。
本次为本树准备独立 extra + dev `.venv` 后重跑，环境前提失败日志保持。
最终执行者同样须在最终工作树准备该环境，并使主门禁的环境选择与之相同。

## 开发验证结果

| 范围 | 实测结果 |
| --- | --- |
| CPython 3.12.14 / 3.13.15 / 3.14.4，extra + dev | 每环境同步/版本库存、pip check、两后端/TableFormer/Transformers/cv2/CPU import、真实配置/doctor 组合通过；各 403 pytest passed，前后 85 包库存相等。 |
| CPython 3.14.4，真实无 extra + dev | 同步、pip check、帮助、配置历史/doctor basic/config/runtime 组合通过；403 pytest passed，35 包且无 Docling/torch/Transformers/pypdfium2/cv2 组件。 |
| scope/重绑/历史迁移/文档消费者 | 108 passed；包括精确材料集合守卫。 |
| `check-compatibility all` | 176 passed，入口退出 0；CLI 与 acceptance 组合均包含。 |
| 全仓静态与锁 | Ruff check、767 文件 format check、766 文件 mypy 与 `uv lock --offline --check` 通过。 |
| 固定范围审计与收集 | 无 hash/baseline 漂移；1214 个登记成员、289 条原计数逐项不变，285 个固定测试模块/5281 节点，collection 为 ok，41 refs 与下游图保持。 |

这些结果只属开发证据；最终 HEAD、target 和完整树的确认在提交/合并后重新绑定，
完整门禁与正式结论遵循下一节，不能由本表推断已 passed。

## 最终冻结与同次门禁

全部票合入并完成双轴独立审阅/修复后，先提交并冻结所有身份约束材料，再由指定的
唯一执行者运行 `./scripts/check-offline`。使用受支持的真实 extra + dev 环境，
固定 `UV_PROJECT_ENVIRONMENT` 与解释器；项目默认 3.14 不得重建另一个 minor 环境。
内部普通 `uv run` 不得同步掉 extra，不使用 `--no-sync` 隐藏漂移，不改变检查集合。
运行前后记录精确 patch、平台/libc/GIL、executable、sys.prefix、editable 来源、
完整发行包/dev/受控组件库存以及最终锁和完整树身份。

门槛为入口实际退出 0，覆盖 lockfile、全仓 Ruff/format/mypy、全部 pytest 和冻结
Contract；同一 run 查询必须为 `status=passed`、`reason=verified`、
`applicability=same`，全部 checks 完成，且无 skip/deselect/incomplete。
同步核对正式材料同 run/身份链接和外部前后库存；失败或中间 run 保留而不混用。
目标移动、材料变化或新 merge commit 后重做受影响证据、审计/确认并重新取得最终 run。
最终 run_id 与状态回执只留树外，避免门禁后写本台账改变身份。

## Body/B/F 承接

- Body：消费结构化 probe，仅在明确请求与必要检查通过后延迟导入 SDK；独立处理
  import/native ABI、模型缓存、转换及资源失败。实现生产 parser/canonical/normalize/
  evidence-map、逐文档质量门禁，落实 StageInput C1、EXP-6 orig 成员身份与 EXP-7 证据规则。
- B：在 ADR-0036 受限实验根接线真实任务，承担 Read 输入/证据身份、预算/租约/retry、
  analysis 持久化与恢复；保留其他前置与 test 来源拒绝，不因 Extra 完成自动进入前沿。
- F：代表性四刊/中文/复杂版式、正式 fixture/摘录、资源阈值与 OOM/超时恢复。
  EXP-3/8 两份同论文材料不构成四刊证明，两后端输出不相等，不直接取得 Read/reuse 资格。

模型加载/正文质量、生产消费链、四刊 fixture、Read/reuse、Pi live、正式校准、NAS 和
完整阶段 A/B 均未由这些安装与工程证据证明。
