# Issue #150 Docling Extra 双轴审查（r1）

- 固定点：`main`（`542265c0971fb0e8bcee4c2a7019295fc9686ac7`）
- 审查命令：`git diff main...HEAD`
- HEAD：`bc8ab83f2a78510129d55a11b37cc8d6120103d0`
- 提交：`f6736d2`、`34beefe`、`ac584cb`、`d7172ae`、`6c660c2`、`bc8ab83`
- 规格来源：GitHub Issues #150、#151、#152、#153、#154（含 comments，comments 优先）
- 审查方式：Standards 与 Spec 两个独立 subagent 并行只读审查；均具有 `bash` 权限
- 代码修改：无；commit：无；测试：未运行

## Standards

发现 **2 项硬违规、1 项 judgement call**：

1. **硬违规｜路线图片段写入票级时点状态**  
   `docs/roadmap.md:12-13`：`“Extra 的工程交付…”`、`“审阅修复的新增 D1…”`。这属于特定 ticket/审阅轮次快照，影响前沿信息的稳定推导。违反 `docs/agents/roadmap.md:3,10`：`“票级任务图…只在 GitHub…维护”`、`“不写票号或票范围的时点快照”`。最小修复：删除这两句，仅保留由模块表推导的前沿状态。

2. **硬违规｜README 复制前置条件并承载进度导航**  
   `README.md:61-67`：`“extra 支持 Linux x86_64…”`、`“实际安装点为…”`、`“当前审阅修复…”`。支持矩阵与实测 patch 已在 Contract/证据维护，审阅进度又绕过路线图。违反 `docs/agents/documentation.md:57-58`：`“README 不另维护这些事实的副本”`、`“进度、计划与后续责任链接到路线图”`。最小修复：保留必要命令及 Contract/证据链接，删除复制的事实和审阅进度句。

3. **Judgement call｜Duplicated Code**  
   `scripts/check_docling_imports.py:22-32` 再次硬编码完整 v2 版本表，如 `"docling-core": "2.105.0"`，与 `src/paper_radar/docling_toolchain.py:27-58` 的权威清单重复；升级时可能漂移。最小修复：从 `toolchain_supply("docling-2.135.0-cpu-v2")` 派生组件及 CLI 约束，仅保留锁特有的 cv2 检查。

测试：未运行（只读审查）。

## Spec

**Spec 轴审查结论：无确认问题。**

- **(a) 缺失或部分交付：无。** #150–#154 要求的 v2 身份与历史回放、CPU 单锁 extra、两后端语义隔离、显式 runtime doctor、只读/无 SDK 边界及组合验收均有对应实现、测试和证据。
- **(b) 未要求的行为（scope creep）：无。** A10 锁守卫调整符合 #150「不以全锁文本相等作为判据」；固定范围补登记及路线图移交属于 #154 明确要求。
- **(c) 看似实现但实现错误：无。** 重点核对了平台/ABI 未知拒绝、v1 现场 mismatch、Typer 不进入 extraction 语义、未消费的 parse 不影响 pypdfium2，以及 doctor 四态和退出码。

**验证：未运行测试。** 只读核对了最终回执 `88b314b3f6c4455f9de91ea5eb40775e`：六项检查通过，状态为 `passed/verified/same`；HEAD、锁及工作树哈希与 `bc8ab83` 当前内容一致。

---

汇总：Standards 共 3 项（2 项硬违规、1 项 judgement call），最严重为路线图片段写入票级时点状态（另有同级 README 硬违规）；Spec 共 0 项，无最严重问题。

## 本轮逐项核实与处置

以下为独立实现核实与修复记录；上文审阅原文完整保留，不追溯改写其 HEAD、结论或验证范围。
实施基线是当前分支 `integration/issue-150-docling-extra` 的
`bc8ab83f2a78510129d55a11b37cc8d6120103d0`。原报告字节先保存于树外
`/tmp/paperradar-review-original/issue-150-docling-extra-review-r1.md`，SHA-256 为
`7c0d3e6ea43a4031397791252caf81775af3438d9de54055d2e6cc405e52912f`。
最初 dirty 内容仅为两份用户提供的未跟踪报告，不是既有固定材料漂移。

| 编号 | 结论 | 核实依据与实际处理 |
| --- | --- | --- |
| R1-Standards-1 | 采纳 | 路线图维护规则禁止在前沿重复票级时点快照。删除 Extra 工程交付/本次审阅两句；保留由模块表推导的前沿和原模块状态。 |
| R1-Standards-2 | 采纳 | README 删除平台/实测 patch 副本及当前审阅进度，保留必要安装命令和 Contract、安装证据、路线图导航。 |
| R1-Standards-3 | 采纳 | smoke 从 stdlib `toolchain_supply("docling-2.135.0-cpu-v2")` 的 `component_versions` 与 `cli_constraints` 派生安装版本；仅 cv2 锁特有值单列。保留首包缺失先报 docling-slim、中文失败与成功 JSON 字段。测试人工预期继续独立维护，不由生产清单生成。 |
| R1-Spec（原无确认问题） | 保留历史结论，限定适用性 | 本轮已实际核验上文历史 run 的 14 份正式文件、52 条链接哈希，以及原始摘要的 exit 0、6 项 passed、`passed/verified/same`、85 包前后一致和原冻结身份。该结论证明旧树；两份报告及本轮修改已使当前 applicability 为 different，不据此宣称新树正式通过。详见 r2 的 R2-S1 / R2-Spec-1。 |

其余外部意见逐项见 [r2 本轮处理表](issue-150-docling-extra-review-r2.md#本轮逐项核实与处置)，
包括 ABI、帮助哨兵、sidecar、CLI 输出，以及两项不采纳的架构扩张。

### 本轮验证与边界

按用户已确认的公共 seams 使用 TDD：`probe_docling_runtime`、显式 smoke `main`、
doctor/帮助冷进程及哨兵可观察拒绝；ABI 4 项、无关 sidecar 3 项、runtime 输出 2 项
分别先失败再修复。新增 D1 为 `tests/test_docling_review_regressions.py` 的 15 项，
登记于[独立台账](../../docs/verification/issue-150-external-review-regressions.md)。

- CPython 3.14.4 + extra + dev：七个 Docling D1、doctor 冷进程和 extraction 配置相关子集 **263 passed**。
- `uv run --offline --locked ./scripts/check-compatibility cli`：**59 passed，退出 0**。
- 触及的 8 个 Python 文件：Ruff check / format 与严格 mypy 通过。
- 显式真实 `check_docling_imports.py`：退出 0，85 包，`gil_enabled=true`；模型/PDF 均 `not_assessed`。
- 只读 scope 审计以本轮基线/本地 integration target 运行，exit 0、`issues=[]`、`baseline_issues=[]`；没有旧哈希漂移或新的敏感确认需求，不做哈希重绑，不改变旧 required/成员/分母。
- `--collect` 审计退出 0，1214 成员、289 计数记录、285 固定模块保持；collection 无 skip/deselect。

全部 Python 命令使用 `uv run --offline --locked`，显式固定项目 `.venv`、
`/usr/bin/python3.14` 与既有离线缓存；开发原始日志保存在树外
`/tmp/paperradar-review-original/`。本轮未运行完整 `check-offline` 或全量 pytest，
未重跑三解释器安装矩阵；本轮 ABI 三 minor 使用受控事实验证。旧冻结证据、fixture、
历史台账和正式回执未修改。未验证模型加载、PDF 转换、native 执行兼容、正文质量、
四刊/中文 fixture、资源、Read/reuse、Pi live、正式校准或 NAS。
