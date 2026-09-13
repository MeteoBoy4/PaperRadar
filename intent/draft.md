# PaperRadar 第一版方案

> 状态：经 Q1–Q89 逐项校准后的实施规格
> 目标用户：单个研究者
> 核心目标：每天从持续到达的论文中找出真正值得精读的工作，并给出能够回到原文核查的精读结果
> 本文是第一版范围和验收依据；与早期设想冲突时，以本文、根目录 CONTEXT.md 和已记录 ADR 为准。

## 一、第一版要证明什么

PaperRadar 第一版不是通用文献管理平台，也不是多源学术搜索引擎。它要证明一条个人研究管线能够长期运行：

1. 从四个指定期刊持续、幂等地发现新论文；
2. 根据同一份 Research Profile 预测论文的研究价值和复用可行性；
3. 先经过盲评校准，再让筛选建议自动控制昂贵的全文精读；
4. 只为真正值得看的论文取得和解析全文；
5. 把主要发现、可复用内容与关键局限指回原 PDF 的证据位置；
6. 用每天不超过五项的 Markdown 日报和可积压的 CLI 队列支持约三十分钟人工复核；
7. 保存足以追溯、重算和恢复的事实，同时避免把 V2 功能提前建成平台。

### 1.1 核心成功标准

第一版只有同时满足以下条件才算完成：

- 四个 Feed 均能幂等运行并保留各自发现事实；
- 32 篇初始盲评样本完成，且 Screening 同时通过四项门槛；
- 四刊代表 PDF 的 Docling fixture 均通过正文边界、阅读顺序、章节、降级和 evidence 回查验收；
- 至少一篇中文论文和一篇英文论文分别完成“发现—筛选—PDF—精读—证据—日报”闭环；
- 普通日报始终不超过五项，其中全文分析不超过三项；
- 单篇或单个外部来源失败不阻断同批其他论文；
- 本机一致性快照可恢复，启用无人值守运行前完成一次 NAS 恢复演练。

### 1.2 服务目标与容量

- 正常容量下，摘要级速览在发现后一天内产生；
- 正常容量下，自动接受论文的全文精读在一周内产生；
- 每个自然日最多自动 Screening 20 篇、自动精读 3 篇；
- 用户显式请求的精读不占自动名额，也不设每日数量上限；
- 每个模型阶段对同一输入指纹最多自动尝试两次；
- 超额任务留在队列，系统不为追赶服务目标而突破自动配额；
- 预测积压会使服务目标超时时，日报和 doctor 必须显示容量告警。

### 1.3 明确不进入第一版

- Web、桌面或移动管理界面；
- 可直接编辑展示内容的前端；
- OCR 和扫描 PDF 自动精读；
- 公式 LaTeX 精确恢复、表格精确数值恢复或图片理解；
- 用多模态或专门 AI Agent 复核版面内容；
- 使用浏览器登录态、机构权限、验证码或反爬绕过自动下载 PDF；
- 自动跨模型或跨供应商 fallback；
- OpenAlex、Semantic Scholar、OpenCitations 和被引次数；
- 综合 Rank、紧急性评分、自由标签；
- 主动关键词搜索、向量检索、embedding 召回；
- 超过一层的参考文献递归扩展；
- 正文解析器自动 fallback；
- PostgreSQL、多用户、远程 API 或协作权限系统。

OCR、AI 精确版面解析、登录态辅助下载和可编辑前端可以在第二版以后分别验证；它们不能静默改变第一版的证据契约。

## 二、输入、输出与使用边界

### 2.1 首发 Feed

第一版主动订阅：

|期刊|Feed|
|---|---|
|Artificial Intelligence for the Earth Systems|https://journals.ametsoc.org/journalissuetocrss/journals/aies/aies-overview.xml|
|Journal of Geophysical Research: Atmospheres|https://agupubs.onlinelibrary.wiley.com/action/showFeed?jc=21698996&type=etoc&feed=rss|
|Quarterly Journal of the Royal Meteorological Society|https://rmets.onlinelibrary.wiley.com/feed/1477870x/most-recent|
|大气科学|https://www.iapjournals.ac.cn/dqkx/rss/current.xml|

Feed 条目只要最终解析为 journal-article 就进入 Screening，不在之前继续区分研究论文、综述、社论或勘误。Feed 自己明确提供的原始文章类别仍原样保存。该选择会带来非目标初筛噪声，但避免因不同出版平台的子类型缺失或不一致漏掉论文。

在线优先、EarlyView 或优先发表属于正式期刊版本。正式期刊版本出现后优先成为论文的当前版本。

### 2.2 人工输入

第一版只提供三类人工入口：

- DOI；
- 论文 URL；
- 向既有论文附加 PDF。

PDF 可以显式附加到 paper ID。系统若从 PDF 中检测到 DOI，只能提出匹配候选，用户确认后才能附加；不得只凭文件名、题名相似度或模型抽取结果静默创建或合并论文。

人工加入并接受的论文可以取得全文和精读，但只有被 Feed 发现且接受的论文能够展开一层参考文献。

### 2.3 面向用户的输出

- 校准期待评 Markdown；
- 校准期揭晓 Markdown；
- 普通每日 Markdown；
- 已成功精读论文的单篇 Markdown；
- CLI 中的复核、积压、全文缺失、模型失败、重复候选、解析失败和备份状态；
- SQLite 中完整的事实、历史和用户行为。

Markdown 是只读数据库投影。用户反馈、笔记和行为通过 CLI 追加到数据库，再由报告渲染；直接修改 Markdown 不受保存保证。

### 2.4 外部 LLM 数据边界

第一版允许向用户明确配置的外部 LLM 发送：

- Screening：题名、摘要和 Research Profile；
- Read：Research Profile、论文元数据和合法取得的正文提取物。

doctor 必须明确显示数据会离开本机。日志不得记录全文、完整提示词、认证信息或密钥。开始校准前必须冻结一个 Screening 模型和一个 Read 模型。校准后若 Screening 模型、关键提示词、Research Profile、输出契约、评分语义或建议规则发生变化，系统先生成待分级变更；由用户附理由判定为 minor 或 major 后才能继续，不能自动决定是否沿用既有校准。

## 三、领域模型与不变量

### 3.1 论文、版本与发现

论文表示一项学术工作，拥有稳定 UUID。预印本和后来发表的正式版本属于同一篇论文；每个具体公开形态是论文版本。

- 一篇论文只有一个当前版本；
- 正式期刊版本优先于预印本；
- 正式版尚无卷期页码不妨碍它成为当前版本；
- 当前版本的书目信息、全文和参考文献代表当前事实；
- 旧版本、旧分析和旧来源作为历史保留；
- 当前版本变化只使受影响阶段的制品过期，不抹除历史。

每个 Feed 条目形成独立 Feed 发现记录，至少保存 Feed、上游条目 ID、发现时间、原始条目和解析结果。一篇论文可以有多条发现记录。重复 Feed 发现补充来源或版本事实，不重复 Screening 未变化的当前版本。

### 3.2 身份、重复与合并

只有以下证据可以自动合并论文或版本：

- 规范 DOI、arXiv ID、PMID 等强标识相同；
- 出版者、DOI 注册机构、arXiv 或其他权威来源明确声明版本关系。

题名、作者、年份、URL 和模糊相似度只能产生重复候选。人工合并前必须预览受影响的版本、发现记录、筛选、全文、分析和引用关系。

每次合并是可撤销事件：

- 记录存活论文、被吸收论文、证据、操作者和时间；
- 被吸收记录不删除，默认查询沿合并链解析到当前论文；
- 引用边和报告成员不因合并重复；
- undo 恢复原有可见性和关系；
- 已发布历史报告不重写，只在查询时显示当前身份。

### 3.3 不使用论文主状态

论文没有 new → accepted → analyzed → delivered 这样的单一主状态。以下事实分别保存：

- 元数据是否足以 Screening；
- 当前筛选建议及其输入；
- 当前生效筛选决定及其来源；
- 参考文献列表取得情况；
- 参考文献身份解析情况；
- PDF 取得情况；
- 正文提取情况；
- 正式精读分析；
- 用户行为与笔记；
- 报告是否首次发布；
- 自动任务尝试与失败。

任务资格由这些事实共同推导。例如 accepted 论文可以并行取得 PDF 与参考文献；参考文献失败不阻塞精读。

### 3.4 阶段输入指纹

每个模型或解析阶段保存规范输入指纹：

- Screening：规范题名、摘要、Research Profile、模型、提示词、输出契约；
- Docling：PDF SHA-256、Docling/core/parse 版本、PDF 后端、模型制品哈希、完整解析配置；
- Read：正文提取物、Research Profile、模型、提示词、输出契约；
- 确定性决定：Screening 原始输出和规则版本；
- 报告：固定成员及其具体筛选或分析制品。

只有实际进入某阶段语义输入的事实变化才使制品过期。卷期页码或普通 URL 等书目补充不触发模型重跑。旧人工筛选决定继续生效但标记为基于旧输入并提示复核；旧系统决定由新建议替换。

阶段输入指纹只回答“哪些制品需要重算”，不能自行回答“既有校准门禁是否仍有效”。任何被检测为可能改变 Screening 语义或建议边界的配置差异，都必须形成待用户分级的校准变更记录：未分级时暂停自动精读；minor 继承门禁并重算受影响制品；major 关闭门禁，等待基于既有人工标签重算或开始新校准。

### 3.5 研究价值与复用可行性

两项核心维度并列保存和展示，不合成总分。

研究价值：

1. 与当前研究无关；
2. 只有微弱价值；
3. 可作为有用背景或局部参考；
4. 对当前方法、解释或方向有实质推进；
5. 足以改变当前方法、解释框架或研究方向。

复用可行性：

1. 在当前条件下无法复用；
2. 成本或前置条件近乎不可承受；
3. 经过显著改造后可以复用；
4. 在可接受工作量内可行；
5. 几乎可以直接采用。

受控价值类型固定为：

- 方法；
- 数据；
- 代码/工具；
- 理论/机制；
- 证据/结论；
- 问题/假设；
- 综述/知识地图。

可以多选；预测或正式研究价值达到 3 时至少一类。没有 other，也没有自动或人工自由标签。

### 3.6 两条阅读队列

- 可转化成果：研究价值至少 3，复用可行性至少 4；
- 认知增益：研究价值至少 4，复用可行性不高于 3。

每天自动精读最多三篇。两条队列都非空时各保留至少一个名额；剩余名额从两条队列的帕累托前沿选择。若仍无法区分，依次比较等待时间、期刊信誉和发现时间。

期刊信誉只有 preferred、normal、low 三档，只作最后的次级排序，不进入 Agent 输入，不改变价值评分和筛选决定。V1 不保存紧急性，也不计算被引次数或综合 Rank。

人工显式精读请求不占自动名额且不限量，但仍按单篇串行执行，并受每个模型阶段最多两次尝试约束。若论文当前为 pending 或 denied，请求与一条来源为用户、原因为 `manual_read_request` 的 accepted 决定事件在同一事务中追加；这样任何进入 Read 的论文仍都有当前 accepted 决定。

### 3.7 筛选建议与生效决定

Screening Agent 只产生结构化语义判断。程序以版本化规则生成建议：

~~~text
if missing abstract or invalid model output:
    suggestion = pending
elif boundary == out_of_scope:
    suggestion = denied(reason=out_of_scope)
elif boundary == uncertain:
    suggestion = pending
elif predicted_research_value >= 4:
    suggestion = accepted
elif predicted_research_value == 3 and predicted_reuse_feasibility >= 4:
    suggestion = accepted
elif predicted_research_value <= 2:
    suggestion = denied(reason=low_value)
else:
    suggestion = denied(reason=low_reuse)
~~~

建议和生效决定分开：

- 校准期建议只用于对比，人工盲评决定生效；
- 校准通过并显式启用后，当前系统建议可以生效；
- 人工决定始终高于系统建议；
- 用户对 pending 或 denied 论文请求精读时，系统自动追加人工 accepted 决定，原因固定为 manual_read_request，再建立精读请求；
- accepted 表示值得进入全文精读；
- pending 表示证据不足或留待复核；
- denied 表示停止新的自动下游任务，并保存原因；
- 后来改为 denied 不删除已存在的 PDF、引用、分析或报告历史。

### 3.8 用户行为

用户行为与处理事实分开，采用只追加事件：

- reviewed：已经复核；
- saved：收藏；
- read：实际阅读过原文；
- reuse_planned：计划复用；
- reused：已经复用；
- dismissed：不再处理；
- note：附加结构化笔记。

用户行为不冒充任务完成状态，也不修改已发布历史报告的成员。

## 四、端到端工作流

### 4.1 单一日常入口

常驻运行只需要一个有界、幂等的日常入口：

~~~bash
paper-radar run-due --date YYYY-MM-DD
~~~

它按任务资格推进，但不把所有阶段塞进一个数据库事务：

1. 抓取到期 Feed；
2. 写入发现事实并解析身份；
3. 补足 Screening 所需最低元数据；
4. 在每日配额内运行 Screening；
5. 为生效 accepted 的 Feed 论文推进一层参考文献；
6. 为生效 accepted 的论文定位或等待 PDF；
7. 解析已取得 PDF；
8. 领取自动精读名额并运行 Read；
9. 规划并发布当日只读报告；
10. 写入运行摘要和容量告警。

每篇论文、每个阶段独立提交。外部网络和模型调用期间不持有 SQLite 写事务。单篇失败记录自己的 task attempt，不取消同批其他论文。

备份由独立每日 timer 运行，不拆成十余个高频 stage timer。各阶段命令仍可以手动调用和测试。

### 4.2 Feed 抓取

每个 Feed 保存 ETag、Last-Modified、最近成功时间、连续失败数和最近错误。请求使用条件头；304 只记录成功检查，不复制响应体或生成发现记录。

处理规则：

- 以 Feed ID + 上游条目 ID 保证同一条目幂等；
- 原始 Feed item 作为发现证据永久保留；
- 相同 DOI 的多个条目可以映射同一论文或不同版本；
- Feed 条目不能直接覆盖权威非空书目信息；
- Feed 新 URL、卷期或分类只补充来源事实；
- 当前版本的 Screening 输入未变化时不重新调用模型；
- Feed 适配器失败不阻断其他 Feed。

四个 Feed 的冻结响应必须进入脱网契约测试。在线 smoke test 只确认端点仍可访问和解析，不把网络稳定性当单元测试前提。

### 4.3 元数据与来源仲裁

第一版只接入：

- 四刊出版者页面或结构化接口；
- Crossref 与 DataCite DOI 路由；
- Unpaywall 全文位置；
- 条件式 GROBID 参考文献提取。

不接 OpenAlex、Semantic Scholar、OpenCitations 或引用指标。

Screening 最低元数据要求：

- 规范题名；
- 非空摘要；
- 至少一个可靠来源 URL；
- 已经尝试适用的 DOI 与出版者路线。

摘要缺失时论文保留在元数据待补队列，不允许只用标题假装完成“题名 + 摘要”筛选。

字段仲裁采用当前版本优先、字段级来源：

1. 当前正式版本出版者结构化事实；
2. 对应 DOI 注册机构；
3. 当前版本 Feed；
4. 人工明确修正。

人工修正优先级最高，但不删除原始观察。冲突必须保存参与仲裁的来源快照和所选依据。

只有实际贡献字段、参考文献或冲突证据的成功响应形成内容寻址来源快照；相同内容只存一次。304、限流、重复空响应和失败只保存结构化执行事实。

### 4.4 版本变化

新发现强标识或权威版本关系时：

1. 找到或创建论文版本；
2. 根据“正式期刊版本优先”重算当前版本；
3. 保存旧当前版本；
4. 逐阶段比较输入指纹；
5. 只让受影响的建议、参考文献、正文或精读分析过期；
6. 保留旧分析并从当前投影中退出；
7. 若存在旧人工决定，继续执行但显示待复核提示。

当前版本的 PDF 或正文变化会产生新的待精读资格；普通卷期页码补全不会。

### 4.5 两阶段 Screening Agent

阶段一只接收题名、摘要、完整 Research Profile、提示词和输出 Schema：

~~~python
class ResearchBoundaryOutput(BaseModel):
    verdict: Literal["in_scope", "out_of_scope", "uncertain"]
    reason: str
~~~

out_of_scope 停止；in_scope 与 uncertain 进入阶段二，以便 pending 论文仍有速览：

~~~python
class ValuePredictionOutput(BaseModel):
    research_value: int  # 1..5
    research_value_reason: str
    reuse_feasibility: int  # 1..5
    reuse_feasibility_reason: str
    value_types: list[ValueType]
    topic_ids: list[str]
    abstract_brief_zh: str
    why_might_matter_zh: str
~~~

Agent 不知道期刊信誉和最终建议规则，也不输出最终决定、权重、紧急性、自由标签、priority 或数值置信度。程序验证主题 ID、价值类型、枚举和分数完整性；未知、重复、缺失或截断输出不能进入成功缓存。

模型输出、供应商、模型名、提示词版本与哈希、Profile 版本与哈希、输入指纹、原始响应、验证结果和规则版本全部保存。相同成功指纹可以复用；缓存命中仍重新检查当前任务资格。

### 4.6 盲评校准

初始样本为四刊各自连续 8 篇，共 32 篇，不按标题挑选。每批最多 5 篇并按四刊轮转；批次生成后固定，上一批未全部提交和揭晓时不生成下一批。用户可以隔几天处理，不要求连续日历日。

待评报告只显示固定编号、题名、摘要和来源，不显示 Agent 预测。CLI 读取同一批：

~~~bash
paper-radar review submit --batch <batch-id>
~~~

CLI 默认只显示编号和短题名，用户输入 accepted、pending 或 denied；输入 ? 时重显摘要。最后一项提交后才生成揭晓报告，展示人工决定、系统建议、两项预测及差异。

四项启用门槛：

1. 系统 accepted 中人工 accepted 的比例至少 80%；
2. 人工 accepted 中至少 90% 没有被系统判为 denied；
3. 系统明确给出 accepted 或 denied 的样本至少 16 篇；
4. 系统 accepted 至少 5 篇。

如果前两项不达标，校准未通过。允许依据揭晓结果调整 Profile、提示词、模型、契约或规则，然后复用同一组 32 篇人工标签重新产生 Screening 制品、建议和门槛指标；每轮必须保存完整运行组合、结果和前一轮关系，并标记 `reused_revealed_labels`。这种结果可以作为第一版自动精读门禁依据，但它是对已揭晓调优样本的拟合后复算，不得称为新样本独立验证。如果后两项不足，结果是“校准不确定”，在语义组合不变时按四刊各连续 2 篇的平衡批次继续，直到分母充分。

校准通过后，可能影响 Screening 语义或建议边界的变化由系统检测、用户分级：

- 待分级：自动精读暂停，直到用户明确选择 minor 或 major 并填写理由；
- minor：继承既有门禁，但受影响论文仍由阶段输入指纹重新产生制品和建议；
- major：关闭门禁，用户可以选择在既有揭晓标签上重算，或建立新的盲评校准；
- 系统可以显示差异和风险提示，但不能替用户决定等级；每次分级及之后的门禁变化都只追加保存。

校准按期刊和语言分别报告，但门槛使用总体样本。人工 accepted 的论文无需等待全局门禁，可以继续 PDF、参考文献和 Read；自动建议不能在通过并由用户显式启用前触发全文精读。

### 4.7 一层参考文献发现

只有当前生效决定为 accepted、且拥有 Feed 发现记录的论文是参考文献种子。每个当前版本只展开一次活动参考文献；当前版本变化时可以产生新一轮观察。由参考文献发现的历史论文即使后来 accepted，也不继续展开自己的参考文献。

参考文献取得顺序：

1. 当前版本出版者结构化列表；
2. Crossref 返回的完整原始 reference 数组；
3. 合法取得 PDF 上的条件式 GROBID processReferences。

DataCite 用于 DOI 身份与元数据路由，不假设它一定提供参考文献。所有来源分别形成参考文献列表记录和原始观察，不能让一个聚合来源的空数组覆盖其他来源的非空列表。

列表完整性和身份解析严格分开：

- complete：当前版本出版者明确提供完整列表，或 PDF 提取经过完整性验证；
- usable：列表非空，且两个可比来源条目数差距不超过 20%；
- partial：已经取得条目，但无完整性证据、已知截断，或可比来源差距超过 20%；
- unavailable：所有已尝试来源均没有取得条目；
- resolved / unresolved：每条引用是否已经高置信映射到论文身份。

只有 unavailable 或高风险 partial 才调用 GROBID。高风险指来源自报数量与实际保存数量不一致，或可比来源数量差距超过 20%。普通 partial 不触发 PDF 兜底。出版者已经确认完整时，不因 Crossref 为空再次运行 GROBID。

所有观察保存原始引用字符串。程序从结构化字段及原始字符串中规范 DOI，包括 URL 包装和 Unicode 连字符；只有 DOI 或其他强标识精确命中才自动建立规范引用边。模糊题录保持 unresolved 或重复候选。

历史候选晋级规则：

- 尚未晋级时只保存原始引用、来源位置和可直接取得的强标识；
- 只有强标识确认相同时，多篇种子的引用才合并计数；
- 只统计当前有效 accepted RSS 种子；
- 种子决定变化可以使未晋级计数下降；
- 被至少两篇不同 accepted RSS 种子直接引用，或用户明确选择时晋级；
- 一旦晋级，不因计数下降自动降级；
- 晋级后才调用外部元数据路线并进入 Screening。

这条路线接受无强标识历史论文的漏召回，以换取引用身份正确性和有限外部调用。

### 4.8 PDF 取得与人工队列

accepted 论文可以独立推进全文取得，不等待参考文献完成：

1. 复用已验证的当前版本本地 PDF；
2. 检查 Feed、出版者和 DOI 元数据中的合法开放 PDF；
3. 有 DOI 时请求 Unpaywall；
4. 检查无需登录的合法机构仓储位置；
5. 否则进入人工 PDF 队列。

自动下载必须：

- 无需用户登录、机构会话或验证码；
- 遵循重定向、连接/读取/总超时和最大体积；
- 验证 HTTP 状态、Content-Type、PDF 文件签名、页数和最小体积；
- 先写同文件系统临时文件，计算 SHA-256，fsync 后原子移动到内容寻址路径；
- 保存来源 URL、取得方式、时间、许可或开放状态证据；
- 把 403_antibot、not_open_access、not_found、invalid_file 和 transient_error 分开。

系统不绕过 Cloudflare 等访问控制；403 不能解释为非开放获取。

人工命令：

~~~bash
paper-radar paper needs-pdf
paper-radar fulltext attach <paper-id> /path/to/paper.pdf
paper-radar fulltext inspect-candidate /path/to/paper.pdf
~~~

inspect-candidate 可以检测 DOI 并建议既有论文，但必须由用户确认。不同 SHA-256 的 PDF 作为不同全文制品保留，不能覆盖旧文件。

### 4.9 Docling 正文提取

V1 唯一通用正文解析器是锁定版本及模型制品的 Docling，不运行 PyMuPDF/PyMuPDF4LLM fallback，也不把 GROBID 当正文解析器。

运行配置：

- 精简本地 PDF 依赖组合；
- CPU，单论文串行；
- OCR 关闭；
- 公式、图片、图表 enrichment 关闭；
- 远程和外部插件关闭；
- 表格结构识别开启；
- 模型预取并以 commit 和文件 SHA-256 冻结；
- 单篇超时和内存峰值进入解析清单。

每次成功解析生成：

~~~text
source/<pdf_sha256>.pdf
docling/<extraction_fingerprint>/
  parse-manifest.json
  document.json
  reading.md
  evidence-map.json
~~~

parse-manifest 至少包含 PDF 哈希、Docling/core/parse/PDF 后端版本、模型哈希、配置哈希、开始结束时间、耗时、峰值内存、警告和结果。

document.json 保存不嵌入 base64 图片的 DoclingDocument，保留原始 page_no、bbox、charspan、orig/text 和 content layer。reading.md 是供 Read Agent 使用的规范阅读制品；evidence-map 把稳定块 ID 映射回一个或多个原 PDF provenance。

确定性后处理只做：

- 用规范题名、DOI、摘要或首个正文节识别并排除仓储封面、授权页、出版者推荐页；
- 过滤重复页眉页脚；
- 根据可靠编号和版面事实修复标题层级；
- 保留原 PDF 页码，不重新编号；
- 为公式、图片和不可信表格内容加入明确占位；
- 不静默猜测或修复疑似错误字符。

已知受限内容：

- 公式只显示“公式未转写；PDF 第 N 页”和 bbox；
- 表格可以用于理解结构，但每表标注精确数值需核对 PDF；
- 科学符号、单位、范围和跨行数字可能失真；
- 任何依赖精确公式、数值或符号的结论不得作为未复核的主要发现、评分理由或复用建议；
- 无可靠文本层的扫描稿记为 extraction_failed，保留 PDF，不调用 Read。

四刊 fixture 至少验证：

- 正文起点和前置杂页排除；
- 真实版式下的阅读顺序，不强迫每刊都是双栏；
- 预期一级、二级标题及顺序；
- 页眉页脚不重复进入正文；
- 中英文关键字符和无 U+FFFD；
- 每个规范块的页码、bbox 和字符区间可回放；
- 公式和受限表格显式降级；
- Markdown 不含 base64；
- 同一输入与配置产生稳定 artifact hash 和 evidence ID。

解析器、后端、模型制品或配置变化使旧正文制品过期并重新运行全部 fixtures。失败制品不能成为当前制品，也不能调用 Read。

### 4.10 Read Agent

Read 只处理：

- 当前生效决定为 accepted；
- 当前 PDF 已验证；
- 当前 Docling 制品通过质量门槛；
- 当前 Read 输入指纹没有成功分析；
- 或用户显式请求重跑。

`paper-radar reading request` 是一次有审计记录的人工筛选决定，而不是绕过筛选门禁的后门。对当前 pending 或 denied 论文，命令必须原子追加 `accepted(source=user, reason=manual_read_request)` 和精读请求；若任一步失败则两者都不提交。已经 accepted 的论文只新增精读请求。随后用户若再明确改为 denied，尚未开始的下游任务不再取得资格，历史请求和决定仍保留。

最终结构契约：

~~~python
class EvidenceRef(BaseModel):
    evidence_id: str

class SupportedStatement(BaseModel):
    statement_zh: str
    evidence: list[EvidenceRef]

class ReusablePoint(BaseModel):
    item_zh: str
    how_to_reuse_zh: str
    evidence: list[EvidenceRef]

class ReadAnalysisOutput(BaseModel):
    one_sentence_conclusion_zh: str
    research_question_zh: str
    methods_summary_zh: str
    data_summary_zh: str
    main_findings: list[SupportedStatement]
    research_value: int  # 1..5
    research_value_reason_zh: SupportedStatement
    reuse_feasibility: int  # 1..5
    reuse_feasibility_reason_zh: SupportedStatement
    required_adaptations_zh: list[str]
    reusable_points: list[ReusablePoint]
    key_limitations: list[SupportedStatement]
    open_questions_zh: list[str]
    value_types: list[ValueType]
    why_it_matters_zh: str
    next_action_zh: str
    degraded_content_warnings_zh: list[str]
~~~

主要发现、两项正式评分理由、可复用内容和关键局限都必须引用 evidence ID。程序检查：

- ID 属于当前正文提取物；
- 页码存在；
- bbox 在页面边界内；
- charspan 可以回放；
- 支持片段非空；
- 受限版面内容没有被冒充精确证据。

程序不调用第二个模型判断语义蕴含。Read 质量通过用户少量抽查发现，但不是自动精读启用门禁。

短论文在安全上下文内单次调用。长论文按页与章节形成不跨页最小块：

1. map 阶段只从各块提取候选结论及 evidence ID；
2. reduce 阶段只能使用 map 已经定位的候选与证据；
3. 最终分析只能引用当前 evidence-map 中存在的 ID；
4. 不使用向量 RAG，也不截断论文尾部。

Read Agent 不输出紧急性、priority、Rank、自由标签或无证据的精确公式/表格值。所有输出原则上为中文；术语或证据翻译会损坏原义时保留必要原文。

### 4.11 报告与复核

普通日报每天最多五项：

- 成功全文分析最多三项；
- 其余名额用于有摘要速览的 pending 论文；
- 全文分析不足三项时 pending 可以补足；
- 可转化成果和认知增益分栏，不给出跨栏总顺序；
- 尚未发布的分析留在报告等待队列；
- 每个筛选制品和分析制品只在普通日报首次发布一次；
- 积压项目不因未处理而重复出现；
- 当天无新结果仍生成空日报。

运行摘要健康时只显示抓取、筛选、精读和积压数量；存在 Feed、模型、PDF、解析或备份异常时才展开告警。空日报必须区分“确实没有新结果”和“因故障没有结果”。

单篇报告只为成功分析生成，固定引用具体 analysis ID、PDF 哈希、正文制品和 evidence。新版本分析生成新修订，不改写历史日报。

发布流程：

1. 在数据库固定 report run 和成员；
2. 渲染到同目录临时文件；
3. 校验链接、成员数量、evidence 和路径；
4. flush、fsync、原子替换；
5. 成功后标记 published；
6. 重跑同一天使用相同固定成员，不重新抽样或调用 LLM。

报告路径只使用受控日期和 UUID，不使用论文题名拼接路径。

## 五、逻辑数据模型

物理表名可以在阶段 A 调整，但下列事实边界不得重新压回 papers，也不得恢复单一主状态。

### 5.1 发现与身份

|逻辑实体|核心内容|关键约束|
|---|---|---|
|feeds|Feed URL、期刊、ETag、Last-Modified、健康信息|规范 URL 唯一|
|feed_discoveries|原始条目、上游 entry ID、item fingerprint、首次/最近发现时间、解析版本、paper/version 指向|feed_id + entry ID + item fingerprint 唯一；内容未变只更新 last_seen|
|papers|一项学术工作的稳定 UUID|不放题名、DOI、当前版本或任何流程字段|
|paper_versions|版本类型、题名、摘要、作者、发布日期、卷期页码、来源 URL|同一 paper 可有多版本；当前版本不存于本表|
|current_version_selections|paper、version、选择原因、时间|只追加；当前版本取最新有效选择|
|external_identifiers|DOI、arXiv ID、PMID 等规范标识及其所属 paper/version|scheme + normalized_value 全局唯一|
|manual_intakes|用户提交的 DOI、URL 或 PDF、解析候选和确认结果|PDF 检测身份确认前不附加|
|duplicate_candidates|两个候选 paper、匹配特征、人工结论|题名相似不能自动合并|
|merge_events|存活/吸收 paper、证据、操作者、时间、撤销信息、受影响关系摘要|事件可撤销；被吸收记录不删除|

当前版本、规范论文别名和常用列表字段可以建立可重建投影，但当前事实必须能追溯到选择事件、paper_versions 和来源。任何投影都不是历史事实的唯一存储位置。

### 5.2 来源与执行

|逻辑实体|核心内容|关键约束|
|---|---|---|
|source_snapshots|提供方、用途、查询键、时间、内容哈希、响应位置|只保存贡献事实或冲突证据的成功内容；哈希去重|
|field_provenance|当前规范字段、采用的快照、原始路径、仲裁依据|字段级追溯；不把缺失当空事实|
|runtime_plans|编译后的配置、Profile、主题、期刊、模型、提示词、规则和解析器哈希|每次任务引用固定计划|
|tasks|阶段、主体、来源、输入指纹、幂等键、父任务和终态|自动失败不每天复活；显式 retry 建新 task|
|task_attempts|阶段、主体、输入指纹、尝试序号、结果、错误类别、耗时、用量|同一模型输入最多两个自动 attempt|
|daily_quota_claims|本地日期、auto_screening/auto_read、paper、task|短事务领取；分别不超过 20/3|
|backup_runs|快照、完整性、NAS 目标、恢复演练结果|用于无人值守门禁和日报健康摘要|

304、限流和失败不创建响应体快照，但 task_attempts 保存状态、时间、查询键和重试资格。

### 5.3 Screening 与校准

|逻辑实体|核心内容|关键约束|
|---|---|---|
|screening_artifacts|阶段一、阶段二结构输出，模型/提示词/Profile/契约版本及原始成功响应|输入指纹唯一成功结果；预测值不可冒充正式值|
|screening_suggestions|artifact、规则版本、建议三态、原因|纯函数可重算；Agent 不直接写建议|
|screening_decision_events|人工或系统决定、依据 suggestion/artifact、原因、时间|只追加；当前有效决定按优先级派生|
|calibration_batches|批次编号、固定成员、创建/揭晓时间、状态|最多五篇；上一批未揭晓不能新建|
|calibration_members|paper、顺序、题名摘要快照、隐藏 suggestion、人工三态和提交时间|提交前查询不能泄漏系统结果|
|calibration_evaluations|样本集合、runtime plan、各指标分子分母、结果、评估依据、前一轮|每次重算只追加；复用揭晓标签必须标记 reused_revealed_labels|
|calibration_changes|前后 runtime plan、差异摘要、待分级/minor/major、用户理由、时间|检测后先待分级；只有用户能确定 minor/major|
|automatic_read_gate_events|enable/disable、所依据 evaluation、用户、理由、时间|只追加；enable 要求门槛通过且无待分级或未解决 major 变更|

当前筛选建议和当前有效决定使用查询或物化镜像派生，但历史事件不覆盖。

### 5.4 参考文献

|逻辑实体|核心内容|关键约束|
|---|---|---|
|reference_lists|citing version、来源、条目数、自报数、完整性、快照或 TEI|同一来源重跑版本化；完整性不等于解析率|
|reference_observations|列表内序号、原始字符串、结构化字段、强标识、解析结果|保留原文；观察指纹去重|
|reference_resolutions|observation、resolved/unresolved/review_required、强标识或人工依据、cited paper|只追加；禁止模糊自动解析|
|promotion_events|历史候选、触发种子或人工原因、触发时间|晋级只追加且不自动撤销|

当前规范引用边由当前版本、当前参考集合和每条 observation 的最新有效 resolution 去重派生；可以建立物化缓存，但缓存不是引用事实源。未晋级历史候选可以由强标识占位 paper 表达，但不得触发普通元数据补全和 Screening。没有强标识的观察保持 unresolved，不创建虚假 paper。

### 5.5 全文、解析与分析

|逻辑实体|核心内容|关键约束|
|---|---|---|
|fulltext_files|paper version、PDF 哈希、来源、取得方式、许可证据、文件位置、验证结果|内容哈希去重；原 PDF 永久保留|
|extraction_artifacts|PDF、解析输入指纹、Docling/模型配置、manifest/document/reading/evidence-map 路径、质量结果|只有通过质量门槛的制品可成为当前|
|analyses|Read 输入指纹、模型/提示词/Profile/契约、完整结构输出、原始成功响应|同一指纹一个成功分析；历史不覆盖|
|analysis_evidence|analysis 内字段路径、evidence ID、支持片段|必须能解析到该分析使用的 evidence-map|
|analysis_reviews|用户对 Read 的两项评分、重大误述、证据问题和笔记|只用于抽查，不构成门禁|

大体积 Docling 块和 bbox 以版本化 sidecar 为主，数据库保存制品身份、哈希和必要索引；不把整篇 document JSON 塞进 SQLite。

### 5.6 用户与报告

|逻辑实体|核心内容|关键约束|
|---|---|---|
|user_events|reviewed、saved、read、reuse_planned、reused、dismissed、note|只追加；不修改处理事实|
|read_requests|paper、请求时间、触发决定事件、取消时间、完成 analysis|每篇最多一条未完成请求；pending/denied 请求必须关联 manual_read_request accepted；不写自动配额|
|report_runs|种类、日期或 calibration batch、固定成员、输入指纹、发布结果|重跑不重新选成员|
|report_entries|report、artifact_kind、artifact_id、paper、栏位、顺序和 first-publication key|普通筛选制品和分析制品分别最多首次发布一次|

report_entries 的唯一性不能只有 report_date + paper_id，因为同一论文的摘要筛选制品和后来全文分析都是独立可发布的新结果。

### 5.7 派生任务查询

以下概念用 repository 查询或数据库 view 推导，而不是 papers.status：

- metadata_ready；
- canonical_paper；
- current_version；
- current_screening_artifact；
- current_screening_suggestion；
- effective_screening_decision；
- decision_basis_stale；
- needs_reference_harvest；
- reference_list_completeness；
- needs_pdf；
- needs_extraction；
- extraction_failed；
- eligible_for_auto_read；
- requested_manual_read；
- model_failure_queue；
- waiting_calibration；
- waiting_review；
- waiting_report；
- capacity_warning。

所有领取查询必须在短事务内原子声明任务所有权，避免同一 task 被两个进程重复执行；外部调用完成后再以输入指纹核对当前资格并提交结果。

## 六、制品与目录契约

推荐布局：

~~~text
config/
  settings.yaml
  feeds.yaml
  journals.yaml
  research_profile.yaml
  topics.yaml
prompts/
  screening/boundary-v1.md
  screening/value-v1.md
  reading/v1.md
data/
  paperradar.sqlite3
  blobs/sha256/
  artifacts/docling/<extraction_fingerprint>/
  artifacts/grobid/<reference_fingerprint>/
  cache/
  tmp/
  backup-staging/
reports/
  daily/YYYY-MM-DD.md
  papers/<paper_uuid>/<analysis_id>.md
  calibration/<batch_id>-pending.md
  calibration/<batch_id>-reveal.md
logs/
~~~

blob 和 artifact 路径只由哈希、UUID 与受控枚举构造。数据库保存相对路径；根目录由配置决定，以便 NAS 恢复到不同挂载点。

永久保留：

- Feed 发现原始事实；
- 有效来源快照；
- 原始 PDF；
- 模型原始成功响应；
- 正式分析；
- 被正式分析引用的 Docling 制品；
- GROBID TEI 及其被采用的原始引用观察；
- 用户事件与已发布报告成员。

可以清理：

- 失败下载临时文件；
- 到期 HTTP 缓存；
- 没有被分析引用、已被新版取代且验证可重建的 Docling 派生制品；
- 不含诊断价值的失败解析临时输出。

清理必须 dry-run、按明确 artifact ID 执行，不能接受宽目录递归删除。

## 七、配置与 Agent 契约

### 7.1 Research Profile

research_profile.yaml 必须包含六个独立段落：

~~~yaml
version: profile-v1
background: |
  ...
core_questions: |
  ...
transferable_methods: |
  ...
available_data_and_tools: |
  ...
theory_and_cognitive_interests: |
  ...
constraints_and_exclusions: |
  ...
~~~

真实内容允许在方案完成后填写，但占位模板不能开始正式校准。每次调用保存文件版本和实际内容 SHA-256。

### 7.2 主题

~~~yaml
version: topics-v1
topics:
  - id: stable-id
    name: 中文名称
    description: 语义描述
    enabled: true
~~~

主题只能由用户创建、修改和停用。Agent 只能返回已启用 ID；零匹配且仍有价值时标记 unclassified_value。主题没有权重，不进入决定公式，也不是检索关键词。

### 7.3 期刊信誉

~~~yaml
version: journals-v1
journals:
  <ISSN-L>:
    name: ...
    tier: preferred  # preferred | normal | low
~~~

以规范 ISSN/ISSN-L 匹配，刊名只展示。冲突显示为配置错误，不由 Agent 决定。期刊信誉只在二维候选仍无法区分时破同。

### 7.4 Screening 输出

~~~python
class BoundaryOutput(BaseModel):
    boundary: Literal["in_scope", "out_of_scope", "uncertain"]
    reason_zh: str

class ValuePredictionOutput(BaseModel):
    research_value: int  # 1..5
    research_value_reason_zh: str
    reuse_feasibility: int  # 1..5
    reuse_feasibility_reason_zh: str
    value_types: list[ValueType]
    topic_ids: list[str]
    abstract_brief_zh: str
    why_it_may_matter_zh: str
~~~

阶段一和阶段二是可独立恢复的调用。out_of_scope 不运行阶段二；in_scope 和 uncertain 运行阶段二，以便 pending 也有可复核速览。Agent 不读取期刊信誉，不输出最终决定、紧急性、置信分、权重或标签。

Pydantic Schema 通过后仍要执行业务校验：

- 1–5 范围；
- 研究价值至少 3 时 value_types 非空；
- 所有 topic ID 已启用且无重复；
- 中文必填字段非空；
- 不允许占位文本或截断修复；
- 结构化输出无效时最多再尝试一次；
- 两次失败后进入模型失败队列。

### 7.5 模型配置

~~~yaml
models:
  screening:
    provider: REQUIRED
    model: REQUIRED
  reading:
    provider: REQUIRED
    model: REQUIRED
~~~

没有默认 fallback 列表。PydanticAI 只隔离供应商接口和结构化输出差异，不承诺模型可互换。实际 provider/model、提示词、Schema、Profile 和输入哈希进入每次制品。

模型格式能力可以在 json_schema、json_object 和 prompt_only 之间做同一模型的有限协议适配，但无效内容不能靠切格式伪装成功。

运行计划与最近一次门禁所依据的计划存在校准相关差异时，doctor 和 run-due 必须列出差异并要求用户分级。系统不得仅依据文件名、版本号或 diff 大小自动判定 minor/major；用户选择和理由形成审计事件。minor 不阻止门禁继承，major 才关闭既有门禁，但待分级期间自动精读保持暂停。

## 八、CLI、任务与运行语义

### 8.1 必备 CLI

~~~text
paper-radar doctor
paper-radar run-due --date YYYY-MM-DD

paper-radar feed list
paper-radar feed fetch <feed-id>

paper-radar paper add-doi <doi>
paper-radar paper add-url <url>
paper-radar paper show <paper-id>
paper-radar paper trace <paper-id>

paper-radar duplicate list
paper-radar merge preview <paper-a> <paper-b>
paper-radar merge confirm <candidate-id>
paper-radar merge undo <merge-event-id>

paper-radar calibration create-batch
paper-radar review submit --batch <batch-id>
paper-radar calibration reveal <batch-id>
paper-radar calibration status
paper-radar calibration recalculate --evaluation <evaluation-id>
paper-radar calibration classify-change <change-id> --as <minor|major> --reason ...
paper-radar calibration enable-auto-read --evaluation <evaluation-id>
paper-radar calibration disable-auto-read --reason ...

paper-radar screening failures
paper-radar screening retry <paper-id>
paper-radar screening set-decision <paper-id> <accepted|pending|denied> --reason ...

paper-radar references show <paper-id>
paper-radar references unresolved
paper-radar references promote <observation-or-paper-id>

paper-radar paper needs-pdf
paper-radar fulltext inspect-candidate <path>
paper-radar fulltext attach <paper-id> <path>
paper-radar extraction failures
paper-radar extraction verify <artifact-id>

paper-radar reading request <paper-id>
paper-radar reading failures
paper-radar reading retry <paper-id>

paper-radar action add <paper-id> <action>
paper-radar note add <paper-id>

paper-radar report render-daily --date YYYY-MM-DD
paper-radar report rebuild <report-id>
paper-radar report verify <report-id>

paper-radar backup create
paper-radar backup verify <snapshot>
paper-radar restore verify <snapshot> --target <empty-directory>
~~~

命令名可以在实现时统一风格，但必须覆盖这些用户能力，且不得重新暴露主状态、综合 Rank、主题权重或自由标签。

`calibration recalculate` 复用指定 evaluation 的人工标签，生成新的 Screening 制品、建议和 evaluation，不覆盖原轮次；输出必须直接显示“复用已揭晓标签，不是独立验证”。`calibration classify-change` 只能由用户执行，缺少非空理由时拒绝写入。自动精读只能由用户用一个已通过的 evaluation 显式 enable；major 变更后的新 evaluation 不静默恢复旧 enable。

### 8.2 盲评交互

待评 Markdown 固定 R1–R5 编号，包含题名、摘要、期刊、版本和原文链接，不显示建议、预测分、价值类型、主题映射或 Agent 理由。

~~~bash
paper-radar review submit --batch <batch-id>
~~~

CLI 只显示编号和短题名并收集 accepted、pending、denied；输入 ? 才重新显示摘要。提交写入后不可通过普通命令读取隐藏建议，直到整个批次完成。最后一项提交成功后生成 reveal 报告。

reveal 显示人工决定、系统建议、两个预测维度、理由、价值类型、主题以及差异，不改变已经生效的人工决定。

### 8.3 模型失败

同一输入指纹的模型阶段：

1. 第一次调用；
2. 若超时、协议失败或内容未通过 Schema/业务校验，最多修正重试一次；
3. 仍失败则写入模型失败队列；
4. 以后 run-due 不自动再试；
5. 用户显式 retry，或输入、模型、提示词、Schema 变化产生新指纹后，才重新获得尝试预算。

模型失败不等同于 pending 决定。若没有合法 Screening 制品，程序投影为 pending/需要处理，但必须保留真实失败原因。

### 8.4 HTTP 与外部来源失败

HTTP 请求可以对连接错误和 429/5xx 做同一次任务内的短暂退避，但不能无限重试。长期恢复资格按来源和用途分别保存：

- 304_not_modified；
- not_found；
- rate_limited；
- transient_error；
- invalid_response；
- provider_incomplete；
- access_blocked_403；
- not_open_access；
- invalid_pdf。

空结果只描述该来源本次没有数据，不能覆盖其他来源事实。错误页面不进入永久 source snapshot。

### 8.5 任务领取与幂等

task attempt 的业务键至少包含：

- stage；
- subject ID；
- input fingerprint；
- 自动或人工来源；
- 调度日或显式请求 ID。

领取使用短事务和带过期时间的租约。完成提交时再次检查当前输入指纹；若运行期间当前版本变化，结果保存为历史但不能成为当前制品。

同一天重复运行 run-due：

- 不重置 20/3 自动配额；
- 不重复 Feed 发现；
- 不重复成功模型调用；
- 不重复引用边、晋级或报告成员；
- 可以恢复中断的 planned 报告和已过期租约。

### 8.6 用量与成本

每个模型 attempt 保存：

- provider 和 model；
- 输入与输出 token；
- 调用次数；
- 供应商返回的 request ID；
- 已知单价下的实际或估算成本；
- 耗时与结果。

每周报告按 Screening、Read map、Read reduce 分开汇总。第一版先使用工作数量和重试次数限制；月度金额上限在获得真实用量后由用户配置。

### 8.7 日志与隐私

结构化日志可以包含 task、paper UUID、stage、fingerprint 摘要、attempt、耗时和错误码，不得包含：

- API key、cookie、Authorization；
- 完整 Research Profile；
- 完整提示词；
- 摘要或正文全文；
- 模型完整原始响应；
- 带临时凭据的 URL。

paper trace 从数据库事实和审计事件重建过程，普通日志不是唯一证据。

## 九、备份、恢复与清理

### 9.1 本机一致性快照

从阶段 A 开始，用 SQLite 在线 backup API 把活动数据库复制到 backup-staging。快照完成后验证：

- PRAGMA integrity_check；
- PRAGMA foreign_key_check；
- 所有永久制品路径存在；
- 抽样哈希与清单一致；
- report entries 可以重新渲染。

数据库快照与所引用永久制品作为同一备份批次记录。复制过程中产生的新事实属于下一批，不用伪造跨文件系统事务。

### 9.2 NAS

NAS 增量备份包括：

- 已验证数据库快照；
- 永久 blob 和制品；
- 配置、Profile、主题、期刊与 Feed；
- 提示词；
- 只读报告；
- 迁移与版本清单。

排除 API 密钥、临时下载、HTTP 缓存和可清理失败文件。保留策略由配置决定，但不得删除仍被正式分析引用的制品。

启用无人值守 timer 前，必须把 NAS 快照恢复到一个空隔离目录，并在不读取原数据目录的情况下完成数据库检查、制品哈希、CLI 查询和报告重建。

### 9.3 清理

清理分两步：

~~~bash
paper-radar artifacts gc --dry-run
paper-radar artifacts gc --execute <plan-id>
~~~

计划显式列出 artifact ID、路径、未被引用证据和可重建依据。执行只接受已保存计划 ID，不接受目录或 glob。原 PDF、正式分析、模型成功原始响应、有效来源快照以及被分析引用的 Docling 制品永不进入计划。

## 十、代码模块边界

建议工程结构：

~~~text
src/paper_radar/
  domain/
    papers.py
    screening.py
    references.py
    fulltext.py
    reports.py
  storage/
    models.py
    repositories/
    migrations/
    artifacts.py
  sources/
    feeds/
    publishers/
    crossref.py
    datacite.py
    unpaywall.py
  identity/
    identifiers.py
    resolver.py
    merges.py
  screening/
    boundary_agent.py
    value_agent.py
    decision.py
    calibration.py
  references/
    collect.py
    completeness.py
    resolve.py
    grobid.py
    promotion.py
  fulltext/
    acquire.py
    import_pdf.py
    docling_parser.py
    normalize.py
    evidence.py
  reading/
    schema.py
    chunking.py
    agent.py
    select.py
  reports/
    queries.py
    render.py
    publish.py
  orchestration/
    eligibility.py
    leases.py
    run_due.py
    backup.py
  cli/
~~~

边界原则：

- domain 不导入数据库、HTTP、Docling 或 LLM SDK；
- screening/decision.py 是只消费结构数据的纯函数；
- references/completeness.py 不做身份匹配；
- identity/resolver.py 不根据引用次数改变筛选；
- fulltext/normalize.py 不产生研究结论；
- reading 只消费已通过质量门槛的正文契约；
- reports 不写业务事实、不调用 LLM；
- orchestration 只组合资格查询和服务接口，不重新实现领域规则；
- 外部适配器不直接更新 papers 当前事实，必须先形成来源观察并经仲裁。

SQLite 是唯一事实源，文件系统保存大制品。建议使用 Python、uv 锁依赖、Pydantic/PydanticAI、SQLModel/SQLAlchemy 2 风格持久化、Alembic、Typer、httpx、feedparser 和 Docling slim；具体版本在阶段 A 锁定并进入验收证据。

## 十一、九阶段实施与验收

每阶段保留三类证据：

1. 离线确定性测试：使用冻结 Feed、HTTP、PDF 和模型响应，进入普通测试套件；
2. 真实来源验收：由显式命令运行，记录时间、代码、配置、输入和输出哈希，不要求普通 CI 联网；
3. 阶段验收清单：生成机器可读结果，阶段 I 聚合，而不是口头宣布完成。

### 阶段 A：契约与可恢复数据底座

实施：

- 初始化 uv 项目、锁文件、代码质量与测试命令；
- 建立配置编译、提示词版本和 RuntimePlan；
- 建立逻辑数据模型、Alembic 初始迁移和 repository 边界；
- 建立内容寻址 blob/artifact store；
- 实现阶段输入指纹和任务 attempt/lease；
- 建立结构化日志、CLI 骨架和 doctor；
- 建立本机 SQLite 一致性快照及隔离恢复命令；
- 固化四刊 Feed、参考文献和 PDF fixture 注册格式。

测试：

- 空目录迁移后数据库可打开，外键、唯一约束和索引生效；
- Schema 中不存在 papers.status、Rank、citation、自由标签或被引指标；
- 相同规范输入生成相同指纹；
- 改变卷期页码不使 Screening/Read 指纹变化；
- 改变摘要只使 Screening 及下游相关制品过期；
- 改变 PDF 只使 Docling/Read 过期；
- 在“文件已落盘、数据库未提交”和“数据库事务中断”处故障注入，重启不产生半条成功事实；
- 日志 fixture 中的 API key、完整 Profile、摘要和正文不会出现在输出；
- WAL 活跃时建立本机快照，隔离恢复后通过 integrity、foreign key 和清单检查。

DoD：

- 全部底座测试脱网通过；
- 从本机快照恢复的副本可由 CLI 查询；
- doctor 能区分“基础工程可运行”和“因 Profile/模型尚未配置不能校准”；
- 后续阶段无需重写身份、指纹、制品和事务基础。

### 阶段 B：JGR Feed 第一条真实纵向闭环

固定路径：

~~~text
JGR: Atmospheres Feed
→ Feed 发现
→ 论文与版本
→ 最低元数据
→ 两阶段 Screening 制品
→ 用户人工 accepted
→ 合法自动或人工 PDF
→ Docling
→ Read
→ evidence
→ 最小 Markdown 日报
~~~

实施：

- 只泛化完成该路径必需的最终接口，不搭建日后推倒的临时状态机；
- 校准门禁保持关闭，系统建议不能自动触发 Read；
- 由用户人工 accepted 形成有效决定；
- 若出版者 PDF 受阻，可以向已确认论文附加合法 PDF；
- 最小日报使用最终 report run/entry 数据契约；
- 保存一次真实验收记录，并冻结相应 Feed、元数据、PDF 和模型响应用于离线回放。

测试：

- 同一 JGR Feed fixture 重放两次只产生一条发现事实；
- 建议 accepted 在校准关闭时不产生自动 Read 任务；
- 人工 accepted 后 PDF、Docling 和 Read 各自取得资格；
- 每个持久化边界故障后重跑不会重复 paper、version、analysis、evidence 或 report entry；
- Agent 字段缺失、越界或 evidence 不存在时不能写成功制品；
- evidence ID 可以反查 PDF 页码、bbox、章节和支持片段；
- 最小日报重复渲染不增加成员。

真实验收：

- 从当前 JGR Feed 取得一篇真实论文；
- 使用真实 Research Profile 和已配置模型运行 Screening；
- 用户人工接受；
- 使用无需登录的合法 PDF 或人工确认的合法 PDF；
- 生成一份真实英文精读和最小日报；
- 保存所有配置、模型、PDF、Docling 和报告哈希。

DoD：

- 冻结路径可以完全脱网重放；
- 真实非 mock 英文纵向闭环成功；
- 该结果不替代阶段 D 的正式校准，也不替代阶段 I 对最终契约的重新验证。

### 阶段 C：四刊发现、身份、版本与来源

实施：

- 完成 AIES、JGR、QJRMS、《大气科学》四个 Feed 适配器；
- 支持 ETag、Last-Modified、304 与独立健康状态；
- 完成四刊出版者元数据和 Crossref/DataCite DOI 路由；
- 保存多 Feed 发现记录和原始条目；
- 实现 paper/version/current version；
- 实现正式版、在线优先版和预印本优先级；
- 实现强标识解析、重复候选、合并预览、确认和 undo；
- 实现字段级来源仲裁和有事实价值的来源快照；
- 实现版本变化的分阶段失效。

测试：

- 四刊各有冻结 Feed fixture，连续导入计数稳定；
- 同一 DOI 的 URL 大小写、协议、尾部参数变体命中同一标识；
- 同一论文从不同 Feed 到达时增加发现记录而不是 paper；
- 无强标识但题名作者年份相似只生成 duplicate candidate；
- 在线优先视为正式版；
- 预印本后来出现正式 DOI 时切换当前版本并保留历史；
- 合并前能预览，合并后默认只见存活 paper，undo 恢复全部关系；
- 合并和 undo 不改写历史报告；
- 304、限流、重复空响应只产生执行事实；
- 实际贡献字段或冲突的响应形成哈希去重 snapshot；
- journal-article 不做子类型预过滤。

真实验收：

- 四个 Feed 各成功拉取一次；
- 随后立即重跑，结果为 304 或幂等 200；
- 没有重复论文或重复发现记录；
- 每个规范字段可以追溯到 Feed 或 source snapshot。

DoD：

- 四个适配器的离线契约测试通过；
- 四个真实 Feed 健康验收通过；
- 身份、版本、来源和合并历史都可由 paper trace 解释。

### 阶段 D：完整 Screening 与盲评校准

实施：

- 完成 BoundaryOutput 与 ValuePredictionOutput；
- 完成两个阶段的独立恢复与成功缓存；
- 完成版本化纯函数建议规则；
- 完成建议与有效决定分离；
- 完成用户维护主题与三档期刊信誉；
- 完成双队列和反弃权门槛；
- 完成最多五篇、四刊轮转的固定校准批次；
- 完成待评 Markdown、盲评 CLI 和揭晓 Markdown；
- 完成同一揭晓标签上的版本化重算及非独立验证标记；
- 完成校准相关变更检测、用户 minor/major 分级和门禁转移；
- 完成自动精读显式 enable/disable 事件；
- 完成模型失败队列、显式 retry 和配置失效；
- 允许真实校准未完成时继续开发 E–H，但保持自动精读门禁关闭。

测试：

- 覆盖 boundary 三态；
- out_of_scope 不调用第二阶段；
- uncertain 即使价值高也产生 pending；
- 覆盖研究价值 2/3/4 与复用可行性 3/4 的决定边界；
- 同样的两个预测值在不同期刊产生相同建议；
- 未知或重复 topic ID 使输出失败；
- 研究价值至少 3 而 value_types 为空时失败；
- 同一指纹两次模型失败后，次日 run-due 不自动再试；
- 显式 retry 和新指纹重新获得预算；
- 待评文件和未揭晓 CLI 不包含或泄漏 Agent 字段；
- 批次成员不随 Feed、元数据或队列变化；
- 初始样本恰好四刊各连续 8 篇；
- 构造混淆矩阵分别验证四项门槛；
- 反弃权不足时只产生 calibration_inconclusive，并按四刊各 2 篇继续；
- 80% 或 90% 不达标后，复用同一 32 篇标签重算并保留新旧 evaluation、runtime plan 和指标；
- 复用揭晓标签的 evaluation 明确标记 reused_revealed_labels，任何输出都不称其为独立验证；
- 发现校准相关差异后，未分级时暂停自动精读；
- 用户标为 minor 时继承门禁，但新输入指纹使受影响 Screening 制品重算；
- 用户标为 major 时关闭门禁，直到既有标签重算通过或新校准通过；
- 系统风险提示不能自行写入 minor/major，分级缺少用户理由时失败；
- major 后即使新 evaluation 通过也不自动复用旧 enable，必须由用户再次启用；
- 校准关闭时自动 Read 资格始终为空，人工 accepted 仍可继续。

指标使用明确整数分子分母：

~~~text
5 * true_system_accepts >= 4 * system_accepts
10 * human_accepts_not_system_denied >= 9 * human_accepts
system_accepts + system_denieds >= 16
system_accepts >= 5
~~~

工程 DoD：

- 功能和构造数据测试全部通过；
- 可以开始 E–H；
- 真实校准未通过时门禁仍关闭。

运行门禁：

- 真实 32 篇以及必要追加批次完成；
- 当前 runtime plan 对应的 evaluation 四项指标通过；重算门禁允许使用 reused_revealed_labels，但必须显著展示其非独立性质；
- 当前计划不存在待分级或 major 尚未重新通过的校准变更；
- 用户针对当前有效 evaluation 显式启用自动精读；
- 阶段 I 再次验证当前计划与 evaluation、变更分级和门禁事件能够形成完整审计链。

### 阶段 E：accepted RSS 论文的一层参考文献

实施：

- 只为当前有效 accepted 且有 Feed 发现记录的当前版本创建参考文献采集资格；
- 完成出版者和 Crossref 列表采集；
- 实现 complete、usable、partial、unavailable；
- 把列表完整性与引用身份解析分开；
- 保存原始字符串和来源位置；
- 从结构化字段与原始串规范强标识；
- 只为 unavailable 或高风险 partial 运行 GROBID；
- 实现规范引用边唯一性；
- 实现未晋级历史候选、当前 accepted 计数和 promotion event；
- 确保历史候选晋级后也不展开第二层。

测试：

- 出版者完整而 Crossref 为零时仍为 complete 且不调用 GROBID；
- 非空但无完整性证据为普通 partial，不调用 GROBID；
- 两个可比来源差距恰好 20% 为 usable；
- 差距大于 20% 或来源自报不一致触发 GROBID；
- GROBID 输出保留 TEI 和原始引用；
- DOI URL 和 Unicode 连字符被规范，原始字符串不变；
- 多来源相同引用只形成一条规范边；
- 同一强标识被两个 accepted RSS 种子引用时计数为 2；
- 相同题名但无强标识不自动合并计数；
- 种子从 accepted 改为 denied 后，未晋级计数下降；
- 已晋级候选不自动降级；
- pending/denied RSS 论文不采集、不计数；
- 当前版本变化产生新列表，旧观察保留；
- 单篇 GROBID 失败不阻断其他论文和全文链。

真实验收：

- 使用已审计的 AIES、QJRMS 和《大气科学》样本覆盖 Crossref 空、原始 DOI、Wiley 列表和中文出版者列表；
- 至少一篇样本走出版者完整路径；
- 至少一篇样本走高风险 GROBID 路径；
- 每条规范边可以回到一个或多个原始观察。

DoD：

- 三种采集路径均有冻结端到端 fixture；
- 完整性、解析率、历史候选和晋级证据可分别查询；
- 重跑不重复观察指纹、规范边或晋级事件。

### 阶段 F：全文取得与 Docling 质量闭环

实施：

- 完成出版者、合法仓储和 Unpaywall OA 定位；
- 实现下载验证、内容寻址归档和人工附加候选；
- 区分 access_blocked_403、not_open_access、not_found、invalid_pdf 与暂时错误；
- 锁定 Docling、PDF 后端、模型制品和配置；
- 生成 manifest、document、reading 与 evidence-map；
- 实现正文起点、仓储封面、推荐页、重复页眉页脚和标题层级处理；
- 对公式、表格精确值、科学符号和图片显式降级；
- 建立 AIES、JGR、QJRMS、《大气科学》黄金 fixture；
- 实现 extraction verify 和安全 artifact GC。

测试：

- HTML、截断文件、错误 magic 和哈希不符均拒绝；
- 下载链不发送浏览器 cookie 或机构凭据；
- 403 与无 OA 形成不同事实；
- PDF DOI 检测只产生候选，确认前不附加；
- 无文本层 PDF 失败并证明未调用 OCR；
- 所有规范块 provenance 在页边界内且 charspan 可回放；
- 公式产生明确占位；
- 表格带精确值核对警告；
- reading.md 不含 base64 图片；
- 同一输入配置产生稳定 artifact/evidence ID；
- 解析器或模型变化自动要求重跑 fixtures；
- 任何 fixture 失败阻断新 Read；
- GC 永不选择原 PDF、分析引用制品或不可替代成功响应。

黄金 fixture 至少包括：

- AIES 正式排版双栏和跨栏表格；
- AIES 长篇 online-first 章节及公式占位；
- JGR 真实右侧正文与左侧元数据版式、仓储封面、标题层级及范围符号风险；
- QJRMS 出版版/accepted manuscript 的仓储页、双栏和编号小节；
- 《大气科学》中文双栏、出版者推荐页和中文章节。

DoD：

- 四刊代表 fixture 在锁定环境全部通过；
- 合法自动 PDF、403、无 OA、人工附加和 extraction_failed 路径均可查询恢复；
- 任一解析结果只有通过门槛后才能成为当前 Read 输入。

### 阶段 G：正式精读与并列队列

实施：

- 完成 ReadAnalysisOutput 和业务校验；
- 完成短文单次读取；
- 完成长文 page/section map-reduce；
- 完成 evidence 存在性和 provenance 验证；
- 阻止受限内容成为未经核对的关键证据；
- 保存正式研究价值、复用可行性和七类价值类型；
- 实现两条队列、帕累托前沿与破同规则；
- 实现每日三个自动名额和不限量人工请求；
- 实现人工请求对 pending/denied 原子追加 manual_read_request accepted 决定；
- 实现 Read 失败队列、显式重试与少量人工抽查。

测试：

- 所有必填字段和两个 1–5 范围；
- 价值至少 3 时必须有 value type；
- 主要发现、两个评分理由、复用内容和关键局限必须有 evidence；
- 未知 evidence、错误页码、越界 bbox 或空片段使分析失败；
- reduce 引用 map 未产生的 evidence 时失败；
- 未人工核验的受限公式或表格块不能支撑关键字段；
- 相同成功指纹不重调模型；
- PDF、正文、Profile、模型、提示词或 Schema 变化生成新分析并保留旧分析；
- 研究价值和复用可行性从不生成隐式总分；
- 构造二维候选验证帕累托选择；
- 两队列均非空时自动名额至少各一；
- 人工请求五篇可以串行完成且不消耗自动计数；
- pending/denied 的人工请求只有在 accepted 决定事件和请求同时提交后才获得 Read 资格；
- 请求事务失败时既不留下 accepted 决定也不留下孤立请求；
- 人工请求后再次明确 denied 会阻止尚未开始的 Read，但保留审计历史；
- 当日普通日报仍最多发布三份分析；
- 中文优先，必要术语和证据保留原文。

真实验收：

- 至少一篇短文和一篇长文成功；
- 至少一篇中文和一篇英文分析接受人工抽查；
- 抽查结果保存，但不成为正式 Read 门禁。

DoD：

- 短文、长文、证据、受限内容、队列和人工请求测试通过；
- 自动选择只有在阶段 D 真实门禁打开时产生；
- 分析可以完整追溯到模型、提示词、Profile、PDF 和 evidence。

### 阶段 H：日常 CLI 与只读报告

实施：

- 加固待评、揭晓、普通日报和单篇报告；
- 实现普通日报固定成员、首次发布和报告等待队列；
- 实现可转化成果/认知增益分栏；
- 实现健康运行摘要和容量告警；
- 实现 reviewed、saved、read、reuse_planned、reused、dismissed 和 note；
- 实现 paper show、trace、各失败/积压查询；
- 实现纯渲染、原子发布、verify 和 rebuild；
- 明确 Markdown 手工编辑不保存。

测试：

- 3 分析 + 2 pending 为五项；
- 2 分析 + 3 pending 为五项；
- 五份新分析只发布三份，其余进入等待队列；
- 同一筛选或分析制品跨日不重复；
- 同一论文的新分析制品以后可以再次发布；
- 校准报告不占普通日报名额；
- 两条价值队列分栏且无跨栏总排名；
- 健康空日报写“今日无新结果”；
- 故障空日报明确故障来源；
- 渲染中断保留旧文件和 planned 成员；
- 手改 Markdown 后 rebuild 以数据库为准；
- CLI note 和用户事件可以重现；
- 恶意标题不能产生路径穿越；
- 报告生成从不调用模型。

DoD：

- 四类报告边界明确且全部可从 SQLite/永久制品重建；
- 任意组合普通日报总数不超过五、全文分析不超过三；
- CLI 能回答每篇论文为什么没有进入下一步。

### 阶段 I：无人值守、NAS 恢复与最终验收

实施：

- 安装一个每日 run-due 用户级 service/timer；
- 安装一个独立每日 backup service/timer；
- 实现进程互斥、租约过期恢复和每日配额不重置；
- 实现 Feed、模型、PDF、Docling、GROBID 和报告故障隔离；
- 实现每周模型用量/成本摘要；
- 完成 NAS 增量备份、保留策略和隔离恢复；
- 聚合九阶段机器可读验收证据；
- 验证校准 evaluation、同标签重算标记和变更分级审计链；
- 只有最终 gate 全部通过才启用自动精读。

故障注入：

- 四 Feed 中一个超时，其他 Feed 与已入库任务继续；
- 20 篇中一篇元数据异常，其他论文继续；
- Screening 或 Read 两次返回无效结构，只影响该论文；
- 坏 PDF 或 extraction_failed 不阻断其他 PDF；
- GROBID 失败不阻断 Read；
- 报告写入中断不修改论文或分析；
- NAS 不可达不损坏本机数据并产生告警；
- 两个并发 run-due 不重复领取；
- 在各任务边界终止进程，重启可恢复且无重复副作用；
- 同日重复 run-due 不突破 20/3 自动配额。

最终 DoD：

1. 四个真实 Feed 在发布候选版本上成功运行并通过重复抓取幂等验收；
2. 当前 Screening runtime plan 具有通过四项门槛的真实 evaluation；若复用揭晓标签，界面和记录均明确其不是独立验证；不存在待分级或未重新通过的 major 变更；
3. 锁定四刊 Docling fixtures 全部通过；
4. 最终发布候选至少完成一篇英文、一篇中文全流程；
5. 普通日报组合测试和真实日报均满足总数不超过五、全文分析不超过三；
6. NAS 恢复到隔离目录后，SQLite、永久制品哈希、CLI 查询和报告重建全部通过；
7. 单篇失败和单 Feed 失败不阻断同批其他任务；
8. 用户显式开启自动运行，系统才安装或启用正式 timer。

## 十二、跨阶段验收矩阵

|场景|必须结果|
|---|---|
|同一 Feed item 重放|不新增发现记录或论文|
|同一论文从第二个 Feed 到达|新增发现事实，复用论文 UUID|
|同 DOI、不同 URL|命中同一强标识|
|同题名作者年份、无强 ID|只生成重复候选|
|预印本后来有正式 DOI|正式版成为当前版本，旧版本与旧分析保留|
|online-first 到达|视为正式版本|
|卷期页码补全|不使 Screening 或 Read 过期|
|摘要变化|新 Screening 制品待生成；旧人工决定继续有效并提示复核|
|PDF 变化|新 Docling/Read 待生成，旧分析保留|
|合并后 undo|身份、版本、引用和可见性恢复；历史报告不重写|
|摘要缺失|不调用 Screening，进入元数据待补队列|
|boundary out_of_scope|不调用价值阶段，建议 denied|
|boundary uncertain 且价值很高|建议仍为 pending，但保存速览|
|研究价值 4、复用 1|accepted，进入认知增益|
|研究价值 3、复用 4|accepted，进入可转化成果|
|研究价值 3、复用 3|denied，原因 low_reuse|
|两个预测相同、期刊不同|建议相同|
|模型连续两次无效|进入失败队列，次日不自动重试|
|校准批次未完成|不能揭晓、不能创建下一批|
|大量 pending|触发反弃权不确定，不启用自动精读|
|80% 或 90% 校准门槛失败后调优|可复用原 32 篇人工标签重算；保留每轮结果并标记非独立验证|
|校准相关变更尚未分级|暂停自动精读，不能由系统猜测 minor/major|
|用户把校准相关变更标为 minor|继承既有门禁；受影响制品仍按新指纹重算|
|用户把校准相关变更标为 major|关闭门禁，直到既有标签重算或新校准通过|
|校准门禁关闭|系统建议不能自动 Read；人工决定可以|
|普通 partial 引用列表|可用于发现，不调用 GROBID|
|两个来源差距大于 20%|标记高风险 partial，PDF 可用时调用 GROBID|
|出版者 complete、Crossref 空|保持 complete，不调用 GROBID|
|引用没有强标识|保留原始 unresolved，不创建规范边|
|两 accepted RSS 种子引用同 DOI|未晋级计数为 2并触发一次 promotion|
|种子决定撤回|未晋级计数下降；已晋级不降级|
|历史候选 accepted|可以精读，但不扩展第二层参考文献|
|自动 PDF 返回 403|记录 access_blocked，进入人工队列，不标非 OA|
|人工 PDF 检出 DOI|只生成附加候选，确认前不关联|
|扫描 PDF|extraction_failed，不运行 OCR 或 Read|
|Docling 返回文本但 fixture 错序|质量门槛失败，不调用 Read|
|公式被检测|生成页码/bbox 占位，不做 LaTeX 增强|
|表格含精确数值|显示人工核对警告，不作为未核对关键证据|
|Read 引用未知 evidence|结构输出失败|
|长文 reduce 引用 map 外证据|结构输出失败|
|两队列都有候选|三个自动名额至少各一|
|人工请求五篇精读|分别原子确保人工 accepted 后串行执行五篇，不消耗自动三个名额|
|对 denied 论文请求精读|同一事务追加 reason=manual_read_request 的人工 accepted 和 read request|
|当天五份分析完成|日报最多发布三份，其余等待以后首次发布|
|筛选制品已发布后仍 pending|以后普通日报不重复|
|同论文后来有新全文分析|新分析可以再发布一次|
|健康且无论文|生成明确的健康空日报|
|Feed 故障且无结果|空日报明确故障，不冒充无新论文|
|Markdown 被手工编辑后 rebuild|以数据库事实重建，不保存文件修改|
|NAS 不可达|本机事实不受损，备份告警|
|同日运行两次 run-due|不重置自动配额，不重复副作用|

## 十三、真实来源与冻结样本

### 13.1 Feed

- AIES：AMETSOC RSS；
- JGR: Atmospheres：Wiley/AGU eTOC RSS；
- QJRMS：Wiley most-recent RSS；
- 《大气科学》：期刊 current RSS。

每个真实响应只作为验收输入，普通测试使用去除无关和敏感内容后的冻结 fixture。fixture 保存抓取时间、URL、HTTP 条件头、响应哈希和解析器版本。

### 13.2 参考文献样本

已核查的代表情况：

- AIES 可以出现出版者/PDF 有大量参考文献而 Crossref 为零；
- Crossref reference 的 DOI 可能只存在于 unstructured 原始字符串；
- QJRMS 可以有出版者和 Crossref 条目总数一致，但结构化 DOI 覆盖不完整；
- 《大气科学》可以由出版者提供参考文献而 Crossref DOI 查询缺失；
- Wiley PDF 的 403 代表访问受阻，不代表论文不是开放获取。

因此 fixture 必须同时断言列表完整性、原始字符串保存、强标识规范和 PDF 获取失败分类。

### 13.3 Docling 样本

锁定至少以下代表特征：

- AIES：正式双栏、跨栏图表、长篇 online-first、公式空文本；
- JGR：机构库封面、左侧元数据栏、标题层级、范围字符风险；
- QJRMS：机构库权利页、双栏、编号小节和复杂宽表；
- 《大气科学》：中文双栏、出版者推荐封面、中文章节和公式。

公开仓库只提交许可允许的整篇 PDF、许可代表页或合成 fixture；其他 PDF 在 fixture registry 中记录合法来源和本地 SHA-256，由真实验收环境提供，不把版权受限全文提交到仓库。

## 十四、上线前必须由用户提供的配置

方案和工程实现可以先完成，但以下内容缺失时不能开始正式校准：

- 六段式真实 Research Profile；
- 用户维护的主题列表；
- 四刊期刊信誉档位；
- 固定 Screening provider/model；
- 固定 Read provider/model；
- 外部 LLM 数据发送确认；
- Unpaywall 联系邮箱；
- NAS 目标和保留策略；
- 日常运行时间与时区。

doctor 分别报告：

- 基础工程 readiness；
- Feed readiness；
- 校准 readiness；
- 自动精读 gate；
- Docling fixture gate；
- backup/restore gate；
- unattended automation gate。

## 十五、第二版以后候选

这些事项只进入 backlog，不在第一版留下半实现开关：

- OCR 与中英文扫描稿质量校准；
- 公式、表格和图片的 AI Agent 精确解析；
- 页面截图与多模态证据复核；
- 用户控制的浏览器登录态 PDF 获取；
- 可编辑前端以及反馈、笔记和行为的可视化；
- 新 Feed、会议、预印本、学位论文和数据集；
- OpenAlex、Semantic Scholar、OpenCitations 或其他图谱；
- 主动检索、向量召回和多层引用探索；
- 本地模型或额外模型的显式校准；
- 多用户、远程 API 和 PostgreSQL。

任何第二版能力必须说明它改变了哪个领域契约、需要哪些新 fixture，以及是否使既有校准失效。

## 十六、校准失败、重算与变更纪律

反弃权门槛不足时，只要 Screening 语义和建议规则未改变，就按四刊各 2 篇连续增加盲评样本并累计指标；这仍是原校准活动的扩样，不是调优后的重算。

若 80% 精确率或 90% 防漏判指标不达标，可以依据已揭晓结果调整模型、提示词、Research Profile、输出契约或建议规则，并复用原 32 篇人工标签重新计算。每次调整先由用户附理由分类为 minor 或 major，再生成新的 runtime plan、Screening 制品、建议和 calibration evaluation。旧轮次不可覆盖。重算通过后，第一版允许用户据此开启自动精读，但所有状态页、报告和最终验收都必须明确标记：该结果拟合并复用了已经揭晓的标签，不是新论文上的独立验证。

minor 变更继承既有门禁状态，但不能绕过阶段输入指纹，受影响的制品仍要重算。major 变更立即关闭既有门禁，只有同标签重算或新盲评校准通过、并由用户针对新 evaluation 再次显式启用后才能开启；系统不静默恢复旧 enable。任何可能影响校准语义的变化在用户完成分级前只暂停自动精读，不由系统根据差异大小自行归类。
