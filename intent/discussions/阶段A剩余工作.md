## 结论

严格按 `intent/draft.md` §11「阶段 A」的实施清单和 DoD 对照，A1–A10 已经把**工程底座主体**做完，但阶段 A 还没有完成。当前还剩：

- **实现项**：Docling slim 可选依赖组、共享 eligibility、calibration visibility、结构化日志、完整 doctor（现只有 `--scope pi-supply` 切片）。
- **验收项**：四刊各 5–10 篇的真实摘要审计尚未执行；A10 只交付了离线工程与工具。
- **ADR-0035 新增的生产接线**：原题名语言事实的 Feed 归属派生、策略版本持久化与 value 任务登记集成尚未交付。

A4/A8 提到的真实 Pi 安装、真实 RPC、模型/凭据/OS 隔离，按 §11 属于**阶段 B 的前置**，不是阶段 A 测试的必需项；但 A4/A8 确实都还是“离线工程通过、live 未验收”。

## 逐项对照

| 阶段 A 实施项 | 状态 | 依据 |
|---|---|---|
| uv、lockfile、质量与测试命令 | 已完成 | A1；`./scripts/check-offline` |
| Docling slim 可选依赖组 | **未实现** | `pyproject.toml` 没有 `[project.optional-dependencies]`/`docling` 组；`docs/contracts/extraction-config.md` 明确“本票不新增解析依赖” |
| 配置编译、提示词、快照、阶段/校准投影 | 已完成 | A2 |
| 有界 Pi RPC adapter、固定资源与策略身份 | **离线协议完成，生产启动器未交付** | A8；`docs/contracts/pi-rpc.md` not_assessed |
| Pi 固定供给、校验、原子激活、保留/清理 | **离线工程完成，live_install 未验收** | A4；`docs/verification/a4-requirements.md` |
| Screening Schema/原因权威/冻结契约 | 已完成 | A1、A9 |
| 数据模型、迁移、repository 边界 | 已完成 | A1/A2/A3/A6/A7/A10 |
| 内容寻址 blob/artifact store | 已完成 | A3 |
| 阶段输入指纹、版本字段、attempt/lease | 已完成 | A5、A7 |
| 共享 eligibility 与 calibration visibility | **未实现** | 代码中没有 `eligibility.py` 或 `calibration/visibility.py`；A7 明确其查询“不是完整 eligibility”；A6 明确“不创立近似 eligibility” |
| 结构化日志、CLI 骨架、doctor | **CLI 完成；日志未实现；doctor 仅供给切片** | 根 CLI 已注册契约/config/paper/fixture/audit/backup/restore/pi；`src` 中没有 logging 模块；`paper-radar doctor` 帮助写“目前仅支持 pi-supply” |
| 根命令和首批命令组中文 `--help` | 已完成 | `tests/test_cli_help.py` 等 |
| 本机 SQLite 快照与隔离恢复 | 已完成 | A3 |
| 四刊 Feed/摘要/参考文献/PDF fixture 注册格式 | 已完成 | A10；`fixtures/a10/historical-v1.json` 已登记 6 条 references、4 条 pdf，feed/abstract_audit 格式已支持 |
| 四刊各 5–10 篇真实摘要审计 | **未执行** | `docs/verification/a10-requirements.md`、`docs/contracts/fixture-audit.md` 均说明当前只跑离线子集，真实四刊 live 未运行 |

## 剩余能力与实现条件

### 现在已经具备条件、可以直接做

1. **四刊真实摘要审计（http-only）**
   - A10 已交付计划、固定选样、HTTP 取件、resume/replay、矩阵、恢复和 `audit run`。
   - 需要用户提供显式联系邮箱、网络和可写的数据库/制品根；`--count` 支持 5–10。
   - 当前只能审计已交付的 `http` 通道。若出版者页面需要 JS 渲染、授权会话或官方 API，A10 会记为 `channel_not_installed`/受阻；按 draft §4.3，渲染通道留到阶段 F 以新策略版本补跑，不应当场改写成成功。
   - 因此“审计执行”已就绪，但“某刊主路径是否稳定、是否阻断阶段 B/校准”还需要 `docs/contracts/fixture-audit.md` 提到的 **B 稳定性/降级判据裁决**，以及 AMS 403、渲染/授权通道策略的事实与决策。

2. **结构化日志**
   - 现在没有任何 logging 模块，只有 CLI 输出。
   - §8.7 已固定允许字段和禁止内容，技术上可直接做一个最小的脱敏结构化日志 seam，并补“API key/Profile/摘要/正文不进入输出”的测试。
   - 需要先定一个很小的实现口径：日志字段、落盘位置（`logs/`）、保留/清理边界；不依赖真实模型或外部来源。

3. **完整 doctor 的“基础工程/配置”切片**
   - 现有 `doctor --scope pi-supply` 已能列出 `configuration_missing` 和 `not_assessed`，但必须给数据库和快照，且不能单独回答“基础工程是否可运行”。
   - 可复用现有 `db upgrade` head、配置快照加载、各阶段 readiness 和供给诊断，增加基础/配置范围；真实模型、凭据、Pi 参数生效仍可继续列为未验收。
   - 需要固定 doctor 的 scope 名称、输出字段和退出码。

4. **原题名语言事实的生产接线**
   - ADR-0035 已裁决来源表：`dqkx=true`，AIES/JGR/QJRMS=`false`，无 Feed 归属的 Paper 没有该事实。
   - 现有 `feeds`/`feed_discoveries` 已保存 Feed URL 与发现事实，`PaperFacts` 也能读当前/历史版本，具备离线实现条件。
   - 还需要固定两个实现口径：多 Feed 发现同一 Paper 时“首发”的确定性判定；策略版本如何持久化。ADR 已授权由生产接线票决定，不需要重新裁决大方向。
   - 当前没有真实 Feed 写入，所以只能先做离线派生 + 登记集成，不能宣称真实 value 任务已接通。

### 部分具备，但需要事实探索或额外环境

5. **Docling slim 可选依赖组**
   - 受控版本清单已在 `src/paper_radar/config/extraction_toolchain.py` 固定，但依赖本身不在 `uv.lock`。
   - 要真正声明 `paper-radar[docling]`，需要联网解析/锁定依赖，并验证 Python 3.12–3.14、torch/docling-slim 组合与最小安装兼容性；这会改变 lockfile，属于需要一次真实安装探测的事项，不能只改 `pyproject.toml`。
   - 阶段 F 才真正消费它，所以不急，但阶段 A 的“声明可选依赖组”确实还空着。

6. **真实 Pi 供给/RPC/模型执行**
   - A4 的供给生命周期实现是真实的（下载/校验/激活/清理），但 `live_install` 仍为 false；A8 只有协议内核和测试任务接线，没有生产启动器。
   - 还缺生产启动器、凭据/模型认证、OS 文件/进程/网络隔离、参数映射、真实 provider retry/cache 抑制和真实用量。
   - 这是阶段 B 的前置，不是阶段 A §11 测试的必需项；如果要“完整阶段 A”按 A10 的 not_assessed 口径，它仍会被列为未验收。

### 尚不具备、依赖后续阶段

7. **共享 eligibility Interface**
   - 现在只有 `screening_tasks` 的任务级 `applicability=current/historical/undeterminable`，不是跨阶段的业务资格。
   - 完整 eligibility 需要 `metadata_ready`、7 天复查/`metadata_unobtainable`、人工决定、PDF/全文、报告/积压、每日配额等事实；这些表和规则属于阶段 C/D。
   - 现在建只能得到空壳或近似规则，A6/A7 已明确反对这样做。建议等 C/D 的事实模型落地后再建，让 `paper trace`、调度和积压列表共用。

8. **Calibration visibility Interface**
   - 当前没有 calibration batch/member/evaluation 表，也没有 `waiting_calibration` 状态。
   - 可见性规则必须围绕未揭晓批次/成员和所有展示面实现；展示面（日报、`review queue`、`calibration review`）本身也属于阶段 D/H。
   - A7 的 not_assessed 已明确保留“校准可见性”。现在实现没有真实消费者，也无法验证盲评隔离。

9. **reuse/Read 的会话隔离与执行器**
   - A8 只接线了 boundary/value；A9 只交付 Read 契约与离线校验。
   - `intent/draft.md` §11 阶段 A 测试中的“跨 reuse、Read map/reduce 的会话隔离”目前无法完整覆盖，因为没有 reuse/Read 运行时；这依赖阶段 D/G。

## 常被混为“阶段 A 剩余”的项

- **强身份冲突观察持久化**：是阶段 C 接入真实 Feed 前的硬门禁，不是 A10 的真实摘要审计所需；A10 不写 Paper，因此没有丢失窗口。
- **真实 Feed 适配器、版本/合并、metadata_ready**：阶段 C。
- **Docling 解析、PDF/Docling fixture 实际样本与质量门槛**：阶段 F；阶段 A 只要求注册格式。
- **run-due、每日 20/20/3 配额、积压调度、screening failures/retry 产品 CLI**：A7/A8 明确留给首张产生真实任务的票，整体属阶段 H。
- **NAS、无人值守**：阶段 I。

## 本次验证

- 未修改代码；只读了 `intent/draft.md`、`GLOSSARY.md`、`docs/adr/`、`docs/contracts/`、`docs/verification/`、`src/paper_radar/`、`fixtures/a10/`，并核对了 Issue #1/#15/#29/#36/#47/#67/#76/#85/#92/#100 的范围说明。
- 最新完整离线门禁 `verification-runs/ab9a895…terminal.json` 在 `a8a8ad8` 上通过：5274 passed，A1–A10 必需组全部通过，控制方退出 0。
- 当前 HEAD 是 `d99b51a`（在 `a8a8ad8` 之上改文档、scope 脚本和验收用例标签），尚未重跑完整门禁；我跑了相关子集：
  - `pytest -q tests/test_cli_help.py tests/test_a10_acceptance.py` → 8 passed
  - `pytest -q tests/test_a7_acceptance.py tests/test_a8_acceptance.py tests/test_a9_acceptance.py` → 8 passed
- 未执行真实网络审计、真实 Pi/Node、Docling、模型调用或 NAS；这些仍是未验证的 live 行为。

**建议顺序**：先跑 http-only 四刊 live 审计并保存结论（不需要新代码）；并行补结构化日志、doctor 基础切片和语言事实生产接线；Docling extra 与安装探测放到阶段 F 前；eligibility/visibility 等阶段 C/D 的事实模型落地后再做，避免现在造近似规则。

## 复核意见与建议执行顺序（2026-10-27）

本节是对以上梳理的追加复核，不改写原结论，也不代表已经批准调整 `draft.md` 的阶段范围。核对基线为 `d99b51a071d22a746247e5dec6345e09389dc4e6`；读取了指定的十个主 Issue 的正文、评论、标签和状态，未展开子 Issue 正文，并交叉检查了现行规格、领域文档、公共 Contract 和实现。

**总体判断：缺口识别大体准确，延期依据和最迟交付节点需要修正。** 当前确实没有 Docling extra、共享业务资格/校准可见性实现和运行级结构化日志，doctor 也确实只提供供给切片；A10 没有完成四刊 live 审计。但“某张 A 系列 Issue 明确不做”只说明这张票的范围，不能据此认定整个阶段 A 已获准删掉该要求。反过来，后续阶段的完整能力也不必一次塞进 A：应分开安排“共享接口与可验证规则”“首个真实消费者所需实现”“后续扩展”。模块文件名只是检索线索，不能单凭缺少 `eligibility.py` 等名字判断能力不存在；这里的未交付判断同时有 Contract 的明确边界和现有调用路径支持。

目前最需要纠正的排序依据是：**B 已要求真实 JGR Feed → 两阶段 Screening → 人工 accepted → PDF → Docling → Read → evidence → 最小日报**。因此不能把真实 Feed、Docling 安装、最小 Read 执行、人工决定和最小报告一概放到 C/F/G/H 才开始；这些阶段负责扩展和完整验收，B 要先取得所需的最终接口切片。

### 对九项剩余能力的逐项建议

1. **四刊 http-only 真实摘要审计：赞成优先执行，但把“执行完成”和“具备继续资格”分开。**

   这是当前最值得先取得的外部事实，不必等待新增日志、doctor、生产 Feed 导入或模型配置。A10 已有显式执行、恢复、回放及按路线统计能力；邮箱、网络、独立审计数据库和制品根准备好后即可安排单独的 live 任务。本次仅评审，不执行 live。

   首轮保持已冻结的选样和 http 策略；受阻、未知类别、样本不足都如实记录，不能为了凑够每刊 5–10 篇换历史 DOI 或挑成功论文。审计失败仍有诊断价值，但不足样本不等于达成了“每刊 5–10 篇”的验收要求；`complete` 也不等于来源稳定。结果应通过现有登记/回放能力成为可追溯的依据，而非只有一份手写命中率。

   原文正确指出尚缺 **B 稳定性/降级判据**，建议把它单独列为审计之后、B 真实验收之前的决策任务：依据真实矩阵，由用户裁决什么障碍阻断哪个范围、允许怎样的降级输入、如何保存批准依据及后续披露。不得自行发明通过率，亦不能假定 JGR 一篇成功就自动消解四刊问题。AIES 的身份/类别取得受阻尤其要与“有样本但缺摘要”分开；#100 已允许后续采用合规通道，但没有解决首轮 AMS 403。渲染、授权等运行时按当前裁决仍放 F，以新策略留新记录；若 B 的必要路线因此无法继续，需明确裁决前移所需通道或批准降级，不能拿“F 以后会解决”作为当前放行依据。依据：[§4.3](../draft.md#43-元数据与来源仲裁)、[#100 评论](https://github.com/MeteoBoy4/PaperRadar/issues/100)、[fixture/audit Contract](../../docs/contracts/fixture-audit.md)。

2. **结构化日志：赞成现在做，留在 A 收口；不要求先造全管线日志平台。**

   现有 CLI、异常、repr 和执行事实已采用受控输出，不能把“没有统一 logging 模块”等同于“目前没有脱敏措施”。真正缺的是统一运行事件出口及实际接线。建议只固定必要字段、输出方式、`logs/` 落点与有限保留规则，先接现有审计/任务服务边界，再让 B 的真实执行复用；不为此引入遥测后端、通用事件总线或全文日志检索。

   验收需捕获真实日志出口、stdout/stderr 和失败路径，证明 §8.7 禁止的凭据、完整 Profile/Prompt、摘要、正文、模型响应及完整 RPC/session 不会泄漏。允许字段清单比事后对任意文本打码更可靠；日志不能替代数据库中的来源、决定和任务审计事实。字段名、scope 和保留数量属于实现票可具体化的小范围选择，不必笼统当作必须另行请用户决策的前置。后续阶段只追加必要事件，不重做底座。

3. **doctor：赞成现在补 A 所需的基础/配置诊断，不赞成以“完整 doctor”作为一张大票。**

   A 的 DoD 是能区分“基础工程可运行”和“Profile/模型未配置而不能校准”。建议先复用数据库 revision、配置校验/历史加载、阶段 readiness、供给诊断及审计结构化结果，明确区分缺失、非法、已检查通过和未验收。没有 Profile 或供给安装，不应掩盖基础工程检查结果；配置齐全也不代表校准就绪。

   最低完成形态应能诊断尚未初始化或尚未配置的环境，并给出具体下一步，但不必现在实现所有生产探测。B 首次模型调用前补固定执行环境、认证、参数和隔离准入；F 补 Docling/模型材料与 fixture；D 补正式校准条件；H 补积压/容量；I 补无人值守和 NAS 状态。只读诊断不得偷偷建库、安装、激活或调用模型；需要联网的检查应有显式边界。当前要求传数据库与快照本身并非错误，问题是现有命令尚不能覆盖 A 的完整区分能力。依据：[阶段 A DoD](../draft.md#阶段-a契约与可恢复数据底座)、`src/paper_radar/pi_supply/cli.py::doctor_command`。

4. **原题名语言事实生产接线：赞成尽快做，硬截止是 B 的第一个真实 value 任务；“首发”解释须纠正。**

   [GLOSSARY](../../GLOSSARY.md) 的“首发期刊”指 V1 主动订阅的四种期刊，不是时间上最先发现论文的期刊。因此 ADR-0035 没有要求按 `first_seen` 或到达顺序选一个“首发 Feed”；不能把原文提出的“首发确定性判定”实现成未经裁决的 first-wins 规则。

   建议以已有数据库 Feed 身份及发现关系确定受支持期刊归属，再应用封闭的 v1 映射，保存派生所依据的来源与策略版本，并接入真实 value 登记前置。不要另建与规范 Feed URL 竞争的身份权威。多个同刊 Feed 映射一致；若出现跨刊归属矛盾而影响 bool，现有 ADR 未给出择一规则，应保留冲突并拒绝新的不确定登记，交由用户裁决，不能自行按时间、DOI 前缀或题名字符猜测。

   必须覆盖无 Feed 归属不登记、人工加入后获得 Feed 归属、重复登记、旧预算/retry 继承、策略变化不改历史与恢复回放。同预算范围的 bool 仍不可更正，策略版本不进 A5 指纹，不能借改策略重置次数。当前事实服务足够支持离线实现，但真实接通要等 B 的生产 Feed 与任务来源一起验收。对没有 Feed 归属的人工论文及未来历史候选，继续保持“不得登记 value”的现有边界；后续入口若需要扩大支持，应另行裁决，不能默认为非中文。依据：[ADR-0035](../../docs/adr/0035-feed-derived-original-title-language-fact.md)、[Screening tasks Contract](../../docs/contracts/screening-tasks.md)。

5. **Docling slim 可选依赖：未交付判断准确，不同意推到 F 才处理。**

   §11 A 明确要求声明可选依赖，B 已经消费真实 Docling。建议放入 A 收口或紧接其后的 B 前置工作：在隔离安装环境中验证实际 slim/CPU 组合、锁定依赖及模型取得方式，再交付 extra；普通环境不安装 extra 仍须能运行完整离线检查。现有 `config/extraction_toolchain.py` 只是受控身份清单，不能把清单中的版本字符串当作已安装兼容证明。

   原文对“不能只改 pyproject、不更新和验证 lockfile”的提醒正确。需核对项目声明的 Python `>=3.12,<3.15` 与 optional dependency 的实际兼容面，但不必无限扩展为所有 OS/硬件矩阵；遇到不兼容要显式限定并说明支持范围或提出新的工具链版本，不能静默改掉旧清单。依赖变化还会影响固定 scope 中的 lockfile/依赖绑定，实施票应包含必要的兼容重审，不能仅刷新哈希使门禁变绿。

   F 负责完整获取链、四刊质量闭环和后续扩展；B 必需的 parser、canonical、正文规范化、evidence 生产及质量验证要先有可消费切片。四刊 fixture 的更严格前置见下文“规格衔接”，不能因把安装提前就宣称解析质量已经通过。

6. **真实 Pi 供给/RPC/模型执行：生产缺口判断正确，建议拆成 A 的工程收口与 B 的真实准入。**

   A 的 fake RPC/供给测试不应被要求使用真实模型或用户凭据；缺配置不能阻止其离线工程证明。不过“真实运行不是 A 测试前置”不等于“生产启动器等实现已经完成”。A8 只交付协议内核、管道会话及 test 接线，生产启动器、权限隔离与任务接收仍应列明未交付，不能仅写成等待运行一次 live。

   建议尽早实现有界生产启动器及可离线验证的权限/资源构造，再按明确版本完成真实安装、认证与 RPC/模型验证，全部在 B 第一笔真实模型任务前完成。既有 A4 有 Pi 1.3.0 的机制 spike，但其主 Issue 已明确不产生生产 install_check/A4 live/RPC 结论；A8 当前协议档案只支持 1.4.0。应选定一致的生产供给与协议支持组合，不能把各自成功的不同版本拼成一份兼容证明。

   除原文列出的隔离、参数、隐含 retry/缓存活动抑制，还要补**生产执行来源接收**：`SuccessCandidate`/`SuccessReceipt` 当前只有 `executor_kind="test"`，`build_call` 只支持 boundary/value，现成接线在测试支撑中；不能把真实进程直接塞进去，再让生产建议/校准消费 test 制品。生产来源、真实用量审计、权威接收、恢复校验及执行前预检要一起闭合。预检在领取预算前做，执行后仍走既有严格接收；复用 A7/A8，不另造次数和成功权威。

   [Pi RPC Contract](../../docs/contracts/pi-rpc.md) 与 [ADR-0026](../../docs/adr/0026-control-pi-through-a-bounded-rpc-adapter.md) 明确要求常量 cwd 的具体值在真实调用前回到所有者确认，这是已有裁决要求，不能由本次排序建议替代。专用提交工具、自动模型 fallback 和执行环境脱网重建均不因此加入范围。

7. **共享 eligibility Interface：同意不提前实现全量业务，不同意整体等到 C/D。**

   A7 的 current/historical/undeterminable 只回答成功制品对输入的适用性，不能证明 `metadata_ready`、人工决定或自动 Read 资格。但 §5.7/§10 明确把 eligibility 定义为“消费已加载事实、返回资格与原因”的共享规则边界，建立它并不要求先建齐全部未来数据库表。A6/A7 禁止的是用输入映射或任务状态冒充完整资格、创建无消费者空表，并非禁止建立可测试的纯规则接口。

   建议 A 收口定义并验证当前能严谨表达的事实输入/原因边界，随后与 **B 的真实来源和人工决定一起实现第一批消费者**：最低元数据（含可靠 URL、适用路线已尝试）、两阶段衔接、有效人工 accepted、PDF/解析/Read 前置及校准未启用时禁止系统建议触发自动 Read。事实缺失应返回阻断原因，不能用“后续尚未实现”默认通过；也不要创建一个永远返回 false、却宣称完整的接口。

   C 增补七天复查、版本/合并和等待校准；F 增补完整正文资格；D 增补建议、校准门禁与复用升级；E/G 增补参考文献与自动选读；H 增补报告等待和容量。各阶段只扩展同一权威，trace、队列与调度共同消费。若决定把 A 中该接口的实现全部移出，必须明确作为阶段范围变更提交用户裁决，不能仅以“现在没有全部事实表”为由把 A 的原要求视为已满足。

8. **Calibration visibility Interface：尚未实现属实，不能推到 D/H 才开始。**

   §11 C 已要求从真实四刊积累开始机械保留 `waiting_calibration`，并让 paper show/trace、普通日报及决定/精读入口遵守隔离。若先展示结果、到 D 才补可见性，已经暴露的样本无法重新变成盲样，损失不是事后补一个过滤器就能恢复。

   建议 A 收口建立可用合成事实验证的共享可见性规则；B 的展示明确记录纵向样本/已暴露依据，供后续机械排除；**最迟在 C 的样本保留器开始真实积累前**，把 waiting、保留依据、未揭晓状态和查询/写入口限制作为同一交付切片落地。D 再扩展固定批次、盲评提交、揭晓及 evaluation，H 扩展新增报告和复核面。没有必要为 A 先造完整 evaluation 表，但也不能用“展示面还没做”忽略已经存在的 paper show/trace、任务查询和未来 B 最小日报。

   可见性不只是不显示分数字段，还应防止速览、理由、中文显示题名、错误详情等旁路泄漏；普通 `set-decision`/`read request` 的禁止写入则由共享事实和业务准入执行。现有查询只显示安全回执是良好起点，但没有校准事实时还不足以证明完整盲评隔离。依据：[阶段 C](../draft.md#阶段-c四刊发现身份版本与来源)、[ADR-0002](../../docs/adr/0002-calibrate-before-automatic-fulltext-reading.md)。

9. **reuse/Read 会话隔离与执行器：缺口属实，应按 B、D、G 分拆，不宜一并推到 D/G。**

   B 至少需要短文单次 Read 的真实执行链，包括 Read 输入身份、任务/预算、独立调用描述与会话、A9 权威接收、analysis/evidence 持久化及恢复。A9 的 Schema、给定上下文校验和 reduce 允许集合不能代替这些运行能力；A5 也明确没有实现 Read/suggestion/report 指纹，不能因为“阶段指纹已完成”漏掉 Read 的输入身份。

   reuse 的摘录选择、任务和专属会话放 F 正文能力之后、D 正式使用升级之前；长文 map 输出契约、分块指纹、候选链和 map/reduce 执行放 G。若 B 的实际论文超出单次安全上下文，则应提前实现所需分块，不能截断全文冒充精读。模型阶段各自保留独立会话、有限尝试与原始成功响应，绝不把 Screening 会话续接成 Read。

   A 所列跨 reuse/Read map/reduce 的隔离要求，可先验证通用会话工厂的隔离机制，再在真实阶段接线时验证其输入、隐藏信息与预算边界；但通用 fake 测试不能声称已覆盖尚不存在的生产接线。建议明确拆分 A 的机制验收与 B/D/G 的消费验收；这是对 §11 A 当前测试归属的调整建议，尚需用户确认后同步规格，不能静默把未完成项变成 passed。

### 对“常被混为阶段 A 剩余”的五类工作的修正

- **强身份冲突观察持久化：A10 审计不需要，第一条真实 Feed 导入需要。** 原文前半句正确，因为审计不写 Paper；但 B 也会导入 JGR，不能机械等到字母 C 才补。#67 用户 D4 将延期成立的唯一依据明确为“尚无真实 Feed 写入”，并禁止直接把 A6 拒绝路径用于生产。建议把这项及必要的 parser 固定样本/字段损失检查前移至 B 的 Feed 写入票；C 扩展至四刊和完整身份能力。它是维持既有安全前置，不是趁机把全部 merge/undo 搬进 A/B。

- **真实 Feed、版本和 metadata_ready：B 最小切片，C 全量扩展。** B 必须保存真实发现、当前版本与必要来源，机械确认最低元数据，再进入 Screening；已有 A6 事实底座可复用，A10 解析/审计结果可作为材料依据，但不可直接把审计库结果当生产 ready。C 完成四刊、条件请求/健康、完整来源仲裁、版本关系、合并/undo、七天复查及样本积累。无需重建 A6 已有能力，也不能把整个领域数据模型标为完成：决定、校准、正文、分析和报告等实际持久化仍随消费者交付。

- **PDF/Docling fixture：A 的注册格式与 F 的完整能力划分正确，但 B 的实际消费不能悬空。** B 至少要有合法 PDF 取得或人工附加、内容验证、版本关联、parser/canonical/normalize/evidence 的可恢复链路。`fixtures/a10/historical-v1.json` 的声明不是已有 PDF 或质量通过记录。完整自动获取、授权通道、摘录、失败队列与 GC 仍由 F 扩展；真实 Read 的通用质量门槛另见下文，不能默认 B 豁免。

- **run-due、每日配额、failures/retry CLI：不能整体归 H。** A7 D4 将 Screening failures/retry 与 trace 组合交给“首张产生真实任务事实的 RPC/run-due 票”，因此 B 的生产任务应有相应可操作入口。B 可用明确的人工触发完成纵向路径，不必先做全量日调度；但不应靠私有 Python 调用维持长期产品使用。首次自动调度时就必须有持久配额与重复运行防超额，不能先无配额运行、等 H 再补。D 已直接测试 run-due、每日 Screening 20/升级 20 及校准预留 5；G 负责自动 Read 3 个名额和人工请求例外；H 汇总完整 CLI、积压与报告；I 再交付 timer 与并发故障验收。每输入两次 attempt 预算、每日配额和报告容量是三种不同约束，不能互相替代。

- **NAS、无人值守：赞成留 I。** 当前本机快照/隔离恢复能力继续复用，新业务事实每次增加都同步验证恢复闭包，不等 I 才发现缺表、缺制品或门禁无法重建。I 再做 NAS 传输、真实恢复演练、正式 timer 和跨阶段故障矩阵；A4 安装清理已完成不意味着 F 的业务 artifact GC 也完成，更不需要现在补通用清理平台。

### 原梳理未充分展开的规格衔接与验收缺口

**第一处：B 的真实 Read 与四刊 fixture 门槛存在前置张力。** §11 把 F 放在 B/C 之后，但 §4.9 规定任何正文制品先通过同一套四刊 fixtures 才能成为当前制品，ADR-0010 也要求关键 fixture 失败时禁止 Read/复用升级。现有文档没有明确授权“B 只验 JGR 就可运行生产 Read”。因此不能一边建议所有四刊 fixture 延期至 F，一边保证 B 可以按现有门槛完成。

我的优先建议是：**把满足该通用门槛所必需的四刊代表 PDF、解析/证据及 fixture 切片前移至 B 真实 Read 之前，F 保留完整获取链与质量闭环的扩展和再验收。** 如果这一前移过重，另一条路线是由用户明确裁决 B 的受限实验范围、隔离方式和证据声称，再同步修改相关规格；不能自行把“实验性 B”当作既有豁免。在裁决前继续保持现有质量门槛，不将单篇成功标为四刊就绪。

**第二处：正文生产格式还有会影响 B 接线的未决边界。** #47 C1/`stage-inputs.md` 明确禁止 normalize 悄悄消费未进入 extraction 格式 1 的论文元数据，优先只用正文/版面信号；确需纳入题名、DOI、摘要时须以 fixture 证明必要、提升格式并再次请用户裁决。#92 又把 charspan 回放用 `orig` 的哈希归属留给正文生产票，Read 规则身份是否进入输入指纹留给 Read StageInput 票。只要 B 开始生产正文和 Read，这些“原定 F/G 解决”的边界就必须在首个消费者前处理，不能暂时借合成 A9 上下文绕过内容身份与恢复校验。依据：[stage-inputs 的 C1](../../docs/contracts/stage-inputs.md#c1-已知未决问题封面识别的论文元数据依赖)、[Read Contract](../../docs/contracts/read-validation.md)。

**第三处：B 所需的业务衔接比“启动模型”更多。** A7/A8 没有两阶段编排、确定性建议或生效人工决定；A9 没有分析业务持久化。B 还要把 boundary 的停止/继续条件、人工 accepted 审计、校准门禁关闭、PDF/正文/分析引用和最终 report run/entry 契约接通，且具备重复运行和故障恢复验收。完整建议/校准规则继续放 D，完整报告放 H，但人工决定与最小报告不能到那时才第一次建模。阶段 B 样本及其暴露事实应可追溯，以便 C/D 机械排除，不能依赖操作者记住哪篇用过。

**第四处：A1–A10 通过不是完整阶段 A 的逐条验收闭包。** 既有离线 scope 的 `not_assessed` 是各组的历史证明边界；其中的 NAS、正式校准、真实模型等并不自动成为 A 必须跑的测试，也不能因这些历史字段始终为 false 就说 A 永远无法结束。反向同样成立：十张主 Issue 已关闭，不表示 §11 A 剩余的接口、日志、doctor、真实摘要审计和跨阶段消费断言已经通过。建议最后补一份按 §11 A 每条实施/测试/DoD 对照的收口清单：链接本次实际证据，明确尚未验证项，以及经用户接受后转移的责任节点。保留旧结论原字节，不把 A10 离线结论改为 live；机器结论的新增只服务于这个明确缺口，不再重建一套通用验收框架。

### 建议采用的工作顺序

1. **先取得来源事实**：安排四刊 http-only live 审计，保存原策略结果和样本分母；紧接着裁决 B 稳定性/降级规则。与之独立的工程工作可继续，不必让网络或邮箱准备阻塞全部开发。
2. **收口 A 的窄工程缺口**：结构化日志、基础/配置 doctor、Docling extra 与安装探测、eligibility/visibility 的共享规则边界；同时准备语言事实接线。跨阶段测试归属如需调整，明确列出并由用户裁决，不预先宣布 A 完成。
3. **补齐 B 的真实前置**：冲突观察留存和生产来源准入 → JGR 发现/最低元数据与语言事实；固定供给/生产启动器/隔离/生产成功来源 → 真实 Screening；合法 PDF/正文生产身份与适用质量门槛 → 最小 Read。前两条工程链可独立推进，到真实 value 与 Read 时分别汇合。
4. **完成 B 的真实纵向验收**：最终接口下的两阶段调用、人工 accepted、PDF/Docling/Read/evidence、最小报告、恢复和脱网回放；明确排除该样本的正式盲评资格，不开启自动 Read。
5. **C 与 F 按现有依赖推进**：C 扩四刊并在积累开始前接好保留器与 visibility；F 与样本积累并行，补完整获取/解析/摘录与四刊验收，消费审计暴露出的通道缺口。
6. **D → E/G → H → I**：D 完整 Screening/reuse/校准及相应配额；E 参考文献，G 长文与自动选读；H 完整日常交互、报告与容量；I NAS、无人值守和最终验收。每个阶段新增事实时即扩展共享资格、可见性和恢复验证，而非再各造一套规则。

以上是推荐的任务切片与最迟交付节点，不是擅自改成新的阶段完成标准。尤其是 A 的跨阶段接口测试、B/F 的四刊质量门槛、首次真实 Feed 的冲突门禁，以及审计后来源稳定性/降级批准，需要在对应实施票中明确衔接。默认保留现有安全行为；本次只追加讨论，不修改 `draft.md`、ADR、代码或 GitHub Issue。

本次复核验证：运行 `uv run --offline --locked pytest -q tests/test_cli_help.py tests/test_a10_acceptance.py tests/test_a7_acceptance.py tests/test_a8_acceptance.py tests/test_a9_acceptance.py`，**16 passed（5.83s）**；仅将 uv 缓存位置指定到可写的临时目录。该子集核对帮助与验收接线/证明边界，不代表完整业务或阶段 A 验收。本文为文档追加，未重跑 `./scripts/check-offline`，不把原文引用的历史全门禁当作本次运行。未执行四刊 live、真实 Pi/模型、Docling 或 NAS；上述真实行为及需要用户裁决的范围仍未验证/未获批准。
