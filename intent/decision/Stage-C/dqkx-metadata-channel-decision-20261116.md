# 《大气科学》元数据通道裁决与实施清单

- 裁决日期：2026-11-16
- 裁决者：所有者（用户）
- 状态：**已裁决，未实施**
- 范围：仅 `dqkx`（《大气科学》）的元数据取得通道；不改变 AIES / JGR / QJRMS 的既有结论
- 调查基线：PaperRadar 仓库 `main` @ `27a30ca`，工作树干净
- 文档性质：过渡记录，**不是正式 ADR**。按 `docs/agents/documentation.md`，决策应进 `docs/adr/`，规格改写进 `intent/draft.md`，现状边界进 `docs/contracts/`。本文只承载「裁决依据 + 注意点 + 改动清单」，落地时须拆分为新 ADR、规格改写、契约改写，并删除或归档本文件。
- 位置说明：本文档位于仓库之外（`/home/meteoboy4/Projects/`），不属于固定验收材料；落地时若需进入仓库，须按固定范围规则显式分类登记。

---

## 一、裁决内容

1. **`dqkx` 元数据主路 = Feed**（`https://www.iapjournals.ac.cn/dqkx/rss/current.xml`）：负责发现与摘要。
2. **出版者页 = 限速回填的权威字段来源**（`https://www.iapjournals.ac.cn/dqkx/article/doi/{doi}`）：负责 Feed 不提供的书目字段，必须配套监测与防护措施（第六节）。
3. **不引入 ISTIC**：不实现 ISTIC 内容协商适配器，不把 `agency_unsupported` 变成可用路线。
4. **不为 ISTIC 扩展已冻结出站集合**（ADR-0050）：不新增 host、不新增端口、不新增明文 HTTP 信任类。
5. **CAPTCHA 命中不算「访问限制」**：视为**速率信号**（`rate_limited`），按限速与退避处理；既不升级为「永久不可用 / access_denied」，也不作为穿透验证码的理由。

---

## 二、前因（实测证据）

### 2.1 四刊的 DOI 注册机构覆盖面

| 刊物 | `doiRA` | Crossref | DataCite |
| --- | --- | --- | --- |
| AIES / JGR / QJRMS | Crossref | 命中，`type=journal-article` | 404 |
| 《大气科学》 | **ISTIC** | **整刊未注册**（ISSN 1006-9895 → 404） | 404 |

即：DataCite 在四刊零适用；第四刊只有 ISTIC，而 ISTIC 落在此前裁决的「不支持机构」区间。

### 2.2 ISTIC 可行但代价不可接受

- 技术可行：`doi.org` + `Accept: application/vnd.citationstyles.csl+json` 对 ISTIC 返回可用 JSON，近期 14/14 篇有题名与中文摘要（摘要与出版者 `dc.description` 逐字相同）。
- 但：`type=article-journal`（不在 A10 类别依据封闭表）、**作者只给 1 个**、无 license、无 references、`publisher=null`。
- 且：端点只能明文——`http://122.115.55.36:8000`（IP 字面量、非 443 端口、`Server: Werkzeug/3.1.6`）；`:443` 无 TLS 握手；`www.chinadoi.cn` 无 HTTPS。
- 结论依据：为一条无完整性保护的通道去扩展冻结出站集合并新增「明文」信任类，收益（作者/许可仍拿不到）不抵代价 → **不引入**。

### 2.3 出版者页的门禁是「限速闸」，不是「禁止自动化」

同一台机器、诚实 UA、真实 DOI 的实测：

| 节奏 | 结果 |
| --- | --- |
| 同一秒连发 3 次 | 3/3 → 302 至 `/dqkx/captcha/page?lang=cn` |
| 间隔 5 s | 200 → 302 → 302 |
| 间隔 10 s | 200 → 200 |
| 间隔 15 s × 10 篇不同文章 | **10/10 → 200** |
| 间隔 20 s × 4 篇 | 4/4 → 200 |
| 被拦后冷却 60 s | 首次即恢复 200 |
| 浏览器 UA（对照） | 连发也 200（白名单，**不使用**该路径） |
| PDF 端点（诚实 UA，单次） | 200，13 MB 正常下载 |
| `robots.txt` / `sitemap.xml` / OAI-PMH | 均不存在 |
| 文章页许可 | `dc.rights` = CC-BY 3.0 |

验证页自述为「您的**访问频率**较高，请完成安全验证」，且内容本身是 CC-BY → 该闸门保护的是服务器负载，不是内容使用权。这是「CAPTCHA 不算访问限制」的事实基础。

### 2.4 Feed 与出版者页的字段差异（21 条 RSS + 2 篇文章页实测）

出版者页有、Feed 没有：

| 字段 | 出版者页 | Feed |
| --- | --- | --- |
| 作者 | `dc.creator` / `citation_author`，4–5 个有序 | **`dc:creator` 21/21 全空白** |
| 关键词/主题 | `dc.keywords` + `dc.subject` ×5 | 无 |
| 许可 | `dc.rights` = CC-BY 3.0（2/2） | `dc:rights` = `Personal use only, all commercial or other reuse prohibited`（21/21） |
| PDF 直链 | `citation_pdf_url` | 无 |
| ISSN / 语言 | `citation_issn`、`dc.language`（条目级） | 仅 channel 层 |
| 页码 | `Pages: 1017-1032` | `prism:startingPage` = `1327-1342`（字段名与内容语义错位） |
| 刊名 | `dc.source` 含完整刊名 | `. 2026 50(5): 1327-1342.` |
| 日期语义 | `citation_online_date` 与 `citation_publication_date` 分开 | 只有 `prism:publicationDate` |

Feed 有、出版者页没有：

| 项 | 说明 |
| --- | --- |
| 发现身份 | 条目 URL/guid、首次 `observed_at`、到达率（ADR-0030） |
| 目录级覆盖 | 一次请求拿整期 21 条；出版者页必须先知道 DOI |
| A10 类别依据 | `dc:type=article`（出版者给「论文」，两者并列） |
| 原始题名语言 | ADR-0035 的 `original_title_is_zh` 由首发 Feed 归属决定 |

### 2.5 为什么主路选 Feed

一次请求覆盖整期、TLS、当前对诚实 UA 无门禁、摘要在三种来源中同源且无截断。出版者页单篇 300–390 KB、无缓存能力，天然不适合当发现或轮询通道。

---

## 三、通道分工（与 §4.3 仲裁顺序对齐）

规格 §4.3 的字段仲裁顺序是：**出版者 > DOI 注册机构 > Feed > 人工修正（可覆盖）**。因此本裁决中的「主路」只对**发现**成立，权威字段仍以出版者页为准。

| 字段类 | 权威来源 | 说明 |
| --- | --- | --- |
| 发现、到达率、条目身份、`observed_at` | Feed | 唯一发现来源 |
| 原始题名语言、`dc:type=article` 类别依据 | Feed | ADR-0035 / A10 |
| 摘要（兜底与主供） | Feed，缺失/疑似截断时取出版者页 | 三源实测同源 |
| 作者、关键词、许可、ISSN、页码、语言、日期语义、PDF 直链 | **出版者页**（限速回填） | §4.3 第一优先 |
| 注册机构事实 | 无（ISTIC 不接入） | 记为 `agency_unsupported`，仅披露 |

---

## 四、注意点（实施必须守住的边界）

### 4.1 身份与发现

1. Feed 是**唯一**发现来源，且是**滑动窗口**（当期约 21 条）。停机超过一个期次，那期文章从 Feed 永久消失，而 `dqkx` **没有 Crossref、也不引入 ISTIC**，因此**没有自动兜底**。必须明确：这类缺口只能人工补 DOI 或从目录页补，且要向用户披露，不能静默计数为「未到达」。
2. 幂等靠「Feed ID + 上游条目 ID + 条目内容指纹」（既有 A6 规则）；内容未变只更新 `last_seen`，不生成新观察、不生成新论文。
3. 同刊条目日期存在语义分歧（Feed `prism:publicationDate` vs 出版者 `dc.date` / `citation_online_date`），必须按规格「发布日期另存语义与精度」分别保存，不能互相覆盖。

### 4.2 字段仲裁细节

1. **许可冲突必须保存双方观察**：Feed 说「仅个人使用、禁止商用复用」，出版者说 CC-BY 3.0。按仲裁顺序取出版者，但冲突证据要留，并在校准/复用路径上披露。取错方向代价不对称（误信 Feed 会把 OA 全文判成不可用；忽略冲突则可能越权使用）。
2. **`dc:creator` 恒空**：`dqkx` 的 Feed 永远没有作者 → 「无强标识时按题名+作者+年份生成 duplicate candidate」对第四刊**永久退化**为仅题名相似。写成已知限制，不要把它当成「作者缺失」去触发 `metadata_unobtainable`。
3. **`prism:startingPage` 语义错位**：字段名暗示起点，内容却是页码范围，不得直接当 `start_page` 使用，须作为「页码范围」解析并记录原始值。
4. **类别依据不冲突**：`dc:type=article`（Feed）与 `dc.type=论文`（出版者）在 A10 中并列为有效依据，两者同时存在不构成冲突。

### 4.3 与规格/契约的既有冲突（必须原地改写）

1. 阶段 C 实施项「支持 ETag、Last-Modified、304 与独立健康状态」对 `dqkx` **不可达成**（Feed 与文章页均无 validator）→ 改为「有则使用、无则记录能力缺失并按策略轮询」（见第五节）。
2. 阶段 C 的「每刊最低 4 篇」与本裁决**不冲突但未被解除**：见第九节阻断项。
3. `docs/contracts/feed-metadata.md` 目前把「机构适用性未知或不支持」写进最低完整 → 与第九节直接相关。

### 4.4 伦理与合规姿态

- 本裁决基于**行为推断**（低频通过、突发被拦、无 robots/条款、内容 CC-BY），**不是书面许可**。策略版本中须写明这一点，并坚持「最保守可行速率 + 可随时人工接管」。
- 不得以伪装 UA、穿透验证码、复用 cookie 会话等方式换取通过率；一旦命中 302，只能降速。

---

## 五、「没有 304 能力」的应对方案

**事实**：`dqkx` Feed 与文章页都没有 `ETag` / `Last-Modified`，且 `Cache-Control: no-cache, no-store`；实测 `If-None-Match` / `If-Modified-Since` 均返回 200 全量（Feed 115 KB／文章页 300–390 KB）。

**关键判断**：304 缺失影响的是**成本**，不是**正确性**——幂等已由「上游条目 ID + 内容指纹」保证，重复拉取不会产生重复论文、重复观察或重复任务。因此应对方案的目标是「把带宽与请求数压到可忽略」，而不是伪造条件请求。

| 编号 | 方案 | 要点 |
| --- | --- | --- |
| S1 | **能力事实显式化** | 每个 Feed 记录 `conditional_get` / `validator` 能力（本刊为 `none`）；健康状态区分 `no_validator`（正常但不可缓存）与 `unavailable`（失败），二者不得混同 |
| S2 | **本地「软 304」** | 保存上次响应内容指纹；指纹相同 → 只更新 `last_seen`，不写新观察、不触发下游任务；把「软 304 命中率」作为一等监测指标 |
| S3 | **自适应轮询** | 基础频率 ≤ 1 次/天（chain 层声明 `syn:updatePeriod=day`、`syn:updateFrequency=15` 语义不可靠，只作上限参考）；连续 3 次软 304 且已超过一个期次窗口 → 退避至 1 次/2 天；硬上下限 1 次/天 ~ 1 次/3 天；出现任何内容变化立即回到基础频率 |
| S4 | **响应与解析预算** | 响应大小上限（Feed 建议 ≤ 512 KB）、超时、解析失败阈值；关键字段数量骤降 → 走「parser 升级前固定样本回归并声明关键字段减少」流程，同时**降频**而不是重试 |
| S5 | **复查排程不得绕开限速** | 「发现满 7 天的延迟复查」与显式 retry 一律进队列 + 令牌桶，不允许直接打出版者页 |
| S6 | **无 304 的幂等验收** | 测试须证明：连续两次相同响应只产生一条观察、`last_seen` 前进、无新论文、无新任务 |
| S7 | **缺口披露** | 停机造成的期次缺失（4.1 第 1 条）必须在周报与 `metadata_unobtainable` 之外单独披露为「发现缺口」，不能与「摘要取不到」混为一类 |

同样适用于出版者页：不周期性重取（见 6.4），只按需取。

---

## 六、出版者页监测与防护措施

### 6.1 限速器（硬约束）

- **单一 host 令牌桶，全项目共享**：元数据回填与 PDF 取得**共用同一个桶**（同一主机，互相踩踏会同时触发限速）。
- 默认最小间隔 **≥ 15 s**（实测 10 s 可过；留 50% 余量）。
- **并发 1**，单轮上限 20 篇，每日上限 120 次（初始保守值，全部进 `acquisition_strategy_version`）。
- 参数变更即提升策略版本，旧记录不重算。

### 6.2 302 → CAPTCHA 的分类与反应

- 识别：`Location` 含 `/captcha`（当前为 `http://.../captcha/page?lang=cn`）。
- **分类必须在 scheme 校验之前**：该跳转是 `http://`，若先跑「只允许 https」会误判为 `disallowed_scheme`；因此解析顺序为「先识别人机验证 → 记 `rate_limited`」，其余非 https 目标仍按 `disallowed_scheme` 处理。
- 反应：立即停止本轮；退避 60 s → 120 s → 300 s；**连续 2 次即熔断当日**，转入人工队列。
- 语义：`rate_limited` **不是** `access_denied`，**不是** `metadata_unobtainable`，**不**影响 paper 的 eligibility 事实；它只是一条执行事实。
- 禁止：改 UA、改指纹、透传验证码、复用人机会话 cookie。

### 6.3 请求头与指纹固定

如实 `User-Agent`（含 §4.3 联系邮箱）+ 站内 `Referer` + `Accept-Language: zh-CN`；不轮换、不伪装。头部组合属于版本化的获取策略事实，随取得记录保存。

### 6.4 按需取数（省请求就是省风险）

只在三种情况打出版者页：元数据不完整、当前版本变化、用户显式 retry。字段齐全即停；同论文同日不重复；不做周期性全量重取。

### 6.5 体积与超时

响应上限（建议 ≤ 1 MB／文章页实际 300–390 KB）、超时 30 s；PDF 单独上限（实测 13 MB）与独立子预算，但**共享同一 host 令牌桶**。

### 6.6 监测指标（须进 health/doctor 与报告）

每分钟请求数、302 率、软 304 命中率、字段解析命中率、P95 延迟、单轮完成率。任一指标越阈 → **自动降频 + 健康降级**，而不是重试或换通道。

### 6.7 出口共享风险

限速按 IP 计。同一网络出口的其他客户端会消耗我们的配额，表现为「站点突然挂掉」。需要用自有请求日志（时间戳 + 状态码）区分「我方触发」与「他人触发」，出现 302 时先降频、再归因。

### 6.8 熔断与人工接管

熔断状态必须出现在健康报告与工作日志中，并转入人工队列；不得静默重试、不得后台无限排队。

### 6.9 隐私

`JSESSIONID` 不持久化、不入数据库、不入日志与报告；只保留结构化执行事实（时间、状态码、字节数、摘要指纹）。

---

## 七、安全性注意点（横向汇总）

1. **不伪装、不穿透**：这是本裁决的底线；命中验证码只能降速，不能换身份。
2. **出站面不变**：本裁决不新增任何出站目标（ADR-0050 的冻结集合不变），ISTIC 的 `:8000` 明文端点永久排除。
3. **完整性**：出版者页与 Feed 均为 TLS（Sectigo DV，至 2027-01），不使用任何明文元数据来源。
4. **内容校验**：解析失败按「早失败 + 降频 + 报警」处理，不猜测字段、不把空值当事实。
5. **日志最小化**：邮箱不入普通日志；响应正文只在形成来源快照时按内容寻址保存（ADR-0009 / 0027）。
6. **固定材料**：新增 fixture（302 验证码响应、无 validator 响应、软 304 幂等）须按固定验收范围规则分类登记。

---

## 八、额外工作（落地清单）

**规格（`intent/draft.md`，原地改写、不重编号、不加日期日志）**

- §4.3：写入三源分工（Feed 发现/摘要兜底、出版者权威字段、ISTIC 明确不接入）；写入许可冲突裁决（CC-BY 胜出 + 冲突保存）；保留 A10 双类别依据。
- §11 C：把「支持 ETag、Last-Modified、304」改写为按 Feed 记录能力事实；新增 `dqkx` 的限速回填、验证码=`rate_limited`、缺口披露条目。
- §13.2：ISTIC 只读预检注记补一句「已裁决不接入」。

**契约**

- `docs/contracts/feed-metadata.md`：新增 `rate_limited` 分类、per-feed `validator` 能力事实、出版者回填通道与预算约束；同步改写最低完整定义。
- `docs/contracts/fixture-audit.md`：`rate_limited` 的结算语义（不计入失败率分母的理由）。
- `docs/contracts/eligibility-visibility.md`：仅当第九节采纳 A/B 时改动。

**ADR**

- 新增一条 ADR（编号顺延）：记录「dqkx 主路 Feed + 出版者限速回填、不引入 ISTIC、不扩展出站集合、CAPTCHA=速率信号」。本文落地后归档删除。

**代码**

- `feed_metadata`：host 级令牌桶（与 PDF 共享）、302 验证码识别与 `rate_limited` 分类、按需触发、退避/熔断。
- `feed_ingestion`：软 304（内容指纹）与自适应轮询；per-feed 能力事实。
- `health`/`doctor`：`no_validator`、`rate_limited`、熔断状态进健康输出。
- `fixture_audit`：请求身份与策略版本携带限速参数（避免跨策略合并分母）。

**测试（离线）**

- 注入时钟验证令牌桶时序：15 s 通过、5 s 命中 302、冷却 60 s 恢复、连续 2 次熔断。
- CAPTCHA 302 分类优先于 `disallowed_scheme`。
- 软 304 幂等：两次相同响应 → 一条观察、`last_seen` 前进、零新任务。
- 无 validator Feed 的健康状态为 `no_validator` 而非 `unavailable`。
- 元数据与 PDF 共享桶（交叉请求不得突破间隔）。
- 固定样本回归：`dqkx` Feed 字段损失（`dc:creator` 空、`startingPage` 语义）为已知声明。

**证据**

- `docs/verification/` 新增本轮探测记录（时间、请求数、节奏、结果、污染声明）。

---

## 九、必须追加裁决的阻断项（不解决则 C 阶段 DoD 永久不达标）

本裁决只回答「字段从哪来」，**没有解除**《大气科学》的元数据就绪门禁：

```
doiRA → ISTIC → agency_unsupported → 计入 missing
      → minimum_complete = False → metadata_incomplete
      → 不进 Screening、不进 waiting_calibration
```

- 代码事实：`src/paper_radar/feed_metadata/projection.py:77-78`（写入 `missing`）、`:92`（`minimum_complete=not missing`）；`src/paper_radar/eligibility/rules.py:76`（→ `metadata_incomplete`）。
- 契约事实：`docs/contracts/feed-metadata.md:59-60`（最低完整要求「机构适用性不是未知或不支持」）。
- 实测复现：出版者路线完全取得（题名/摘要/URL 齐全）、Feed 齐全，结果仍是 `missing=('agency_unsupported',)`、`minimum_complete=False`。

后果：§4.6 的「总计 32、每刊最低 4 篇」对第四刊**不可达**；而本裁决明确不引入 ISTIC，所以这条门禁不会因为新通道而自动解除。

可选路径：

| 选项 | 内容 | 代价 |
| --- | --- | --- |
| A | 把 `agency_unsupported` 从 metadata-ready 阻断项降为「披露缺口」 | 改写最低完整定义 + §4.3 表述，需说明不构成静默降级 |
| B | `registry_applicability` 不参与 `minimum_complete`，仅作披露字段 | 同上，影响面更小但语义更绕 |

我个人倾向于 B，具体可由 Agent 选择

---

## 十、影响面与风险

**影响**：阶段 C 的实施项文字、`feed-metadata` 契约、健康状态语义、测试与证据；不影响另三刊的既有结论。

| 风险 | 说明 | 缓解 |
| --- | --- | --- |
| Feed 滑动窗口 + 无兜底 | 停机超过一个期次即**永久**丢失该期发现 | S7 缺口披露；缩短停机容忍度；人工补 DOI |
| 出版者页无 validator | 平台改版只能靠解析失败发现 | 字段解析命中率监测 + 固定样本回归 |
| 限速参数来自单次实测 | 长期配额未知，阈值可能变化 | 保守参数、自适应降频、熔断 |
| 出口共享 | 他人消耗配额导致我方「莫名被拦」 | 自有日志归因；先降频后判定 |
| 观测污染 | 本轮约 60 次探测请求可能已影响站点阈值 | 在证据文档中声明；上线后按新基线观测 |

---

## 十一、未验证（不要当成已证明）

1. `dc.rights` 是否**全刊**为 CC-BY（只验 2 篇）。
2. `dc.date` / `citation_online_date` / `citation_publication_date` 的确切语义（可能分别是收稿/在线/印刷）。
3. 长期每日/每月配额，以及阈值随时间是否变化。
4. PDF 端点的批量限额（只测单次）。
5. `dc:creator` 空白是平台缺陷还是长期行为（若是缺陷，将来可能修好，适配器不应硬编码「永远无作者」）。
6. 本轮所有观测均来自单一出口 IP 的单次探测窗口。
