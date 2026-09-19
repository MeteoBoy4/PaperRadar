## 概述

PaperRadar 是一个面向单用户的学术论文发现、筛选、全文阅读、证据追踪和每日审阅流水线。

V1 的优先级为：

`attention_overload > missed_relevant > wasted_full_read > review_backlog`

不要把 V1 扩展成通用文献管理平台。

## 项目可读性

1. 架构与目录

主动拆分文件、整理目录、优化整体架构，保持清晰的模块边界，减少循环依赖。目标：Agent 只看目录结构和模块划分，就能快速理解项目的功能分布，不需要通读全部代码

2. 模块解耦

功能模块化设计，让每个模块职责单一、依赖扁平、尽可能不向上依赖。目标：只让 Agent 读取单个模块就能工作，不用加载整个项目的上下文


## 开始编码前

进行非微小改动前，先阅读：

1. `CONTEXT.md`：项目术语和领域概念的权威定义。
2. `intent/draft.md` 中与当前任务相关的内容。
3. 相关 ADR 和 `docs/agents/`。
4. 当前 issue / task，以及受影响的代码和测试。

如果这些来源之间存在冲突，不要自行猜测解决方式。优先保持已有安全行为，并明确指出冲突。

## 范围控制

只实现当前任务明确需要的内容。

除非任务明确要求，不要引入 V2 能力，包括：

* Web、桌面或移动端 UI。
* OCR 或多模态文档理解。
* 模型或 Provider 自动 fallback。
* 基于引用量的排序或综合 Rank。
* Embedding、向量检索或主动关键词搜索。
* 超过一层的递归参考文献扩展。
* PostgreSQL、远程 API、多用户或权限系统。

优先选择满足规格要求的最小改动。

## 核心不变量

以下是架构约束，不是建议。

* SQLite 是业务事实的唯一事实源；大型 blob / artifact 存储在文件系统。
* Markdown 报告只是持久化事实的只读投影。
* Paper 不存在单一 lifecycle / status 字段。
* 保留历史；新事实通过 supersede 旧事实，而不是重写历史。
* 用户行为和决策必须以可审计事件形式追加保存。
* 只有强标识符或权威版本关系可以自动合并论文。
* 标题、作者、年份、URL 相似度只能生成候选，不得静默合并。
* 外部 Adapter 只产生 observation，不直接覆盖 Paper 事实。
* 单篇论文或单个来源失败，不得阻塞同一次运行中的无关任务。
* 相同输入重复运行必须保持幂等。

## 数据与版本控制

影响语义的输入必须可复现。

* 已版本化的 Profile、Prompt、Topic、Contract 和语义配置不可原地修改。
  已被引用的版本需要变化时，创建新版本。
* Frozen Contract 必须从权威 Pydantic Schema 生成，不维护第二份手写 Schema。
* Stage fingerprint 只包含能够改变该阶段语义的输入。
* volume、pages 等书目信息补全不得使 Screening 或 Read 失效。
* PDF 变化只应按需使文档解析或 Read 失效，不影响无关阶段。
* 数据库结构变化必须通过 migration，禁止手工修改用户数据库。

## Calibration 安全

Calibration 是硬门槛。

* Blind calibration batch 揭示前，不得暴露隐藏的 Agent 结果。
* 用户决策优先于系统建议。
* 可能改变 Screening 语义的修改必须遵循 calibration change workflow。
* 不要自动将 calibration 相关修改判断为 minor 或 major。
* 未明确通过规定 gate 前，不得启用自动全文阅读。

## LLM 与证据规则

LLM 负责产生结构化 artifact；确定性代码负责流程控制。

* 模型输出必须同时通过权威 Schema 和业务规则验证。
* Agent 不得自行创建 Topic、最终流程状态、自由标签、Rank、urgency 或规格未定义的 confidence score。
* Screening 阶段不得将期刊声誉作为模型输入。
* Read 阶段需要证据支持的结论必须引用有效 evidence ID。
* 表格、公式、图片或文本不可用时，禁止伪造 evidence。
* 不得在日志中记录 secret、完整 Prompt、完整 Profile、全文或完整 excerpt。

## 依赖与外部服务

项目初始化后统一使用项目管理的 Python 环境和 `uv`。

* 遵守已提交的 lockfile。
* 除非新依赖能够明显简化当前需求，否则不要新增依赖。
* Network、Publisher、LLM、Docling 和 GROBID 行为必须位于可测试接口之后。
* 常规自动化测试必须能够使用固定 fixture / mock 离线运行。
* Live source 验收必须使用显式命令，不得让普通测试依赖实时网络或付费 API。

## 编码流程

修改代码前：

* 检查相关接口、调用方、测试和当前 git diff。
* 保留与当前任务无关的用户修改。
* 不要为了清理工作区使用破坏性 git 操作。
* 不要顺手进行与任务无关的大规模重构。

修改代码时：

* 遵循现有命名、类型、Repository 和事务模式。
* 将确定性逻辑与 I/O 分离。
* 如果部分成功会破坏业务语义，应保证事务操作原子性。
* 行为发生变化时同步新增或修改测试。
* 修复 Bug 时增加一个在修复前会失败的回归测试。
* 优先使用明确的领域类型和受控 enum / reason，避免 magic string。

## 验证

先运行最小范围的相关测试，再运行仓库定义的完整离线验证命令。

涉及持久化时，根据需要额外测试 migration、rollback 或恢复行为。

涉及外部集成时，先使用固定 fixture；只有在明确要求且配置 / credential 可用时，才运行 live acceptance check。

没有实际运行的检查，不得声称其已经通过。

## 面向用户的行为

* CLI help 和常规分析 / 报告文本默认使用中文。
* 原始论文标题、作者、摘要和 evidence 保持来源语言。
* 错误信息应说明可操作的具体原因，不要用模糊状态隐藏失败。
* CLI `--help` 不得触发网络请求或数据库写入。

## 文档维护

以下改动需要同步更新文档：

* 公共 CLI 或配置 Contract。
* 领域不变量或受控 vocabulary。
* 持久化或 Schema 行为。
* Stage fingerprint 或版本语义。
* Calibration 行为。
* 架构决策。

有意偏离既有架构时应新增 ADR，不要把架构决策隐藏在代码实现中。如果行为偏离 `intent/draft.md` 但被允许，也同步修改该文稿相应表述。

## 完成标准

任务只有同时满足以下条件才算完成：

* 请求的行为已经实现。
* 相关离线测试通过。
* 领域边界和模块边界未被破坏。
* 未无必要修改无关行为或文件。
* 必要的 migration、文档和 Contract 已同步更新。
* 尚未验证的 live 行为或已知限制已明确说明。

最终回复应简要说明：修改了什么、运行了哪些验证、还存在哪些风险或后续事项。

## Agent skills

### Issue tracker

Issues and specs are tracked in this repository’s GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default five-role triage label vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

This repository uses a single-context domain documentation layout. See `docs/agents/domain.md`.
