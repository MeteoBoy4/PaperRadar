# OA 论文全文自动获取：实测经验、教训与 V1 改造建议

> 调研日期：2026-10-02 首轮验证，2026-10-09 复验并新增 Wiley TDM API 路线验证。验证方式：AMS 与大气科学沿用前两轮直连抽查结论（每刊 2 篇 × 双格式）；Wiley 两刊本轮改用出版方官方 TDM API，从 Crossref 现查 2026-09-01 以来 CC 许可文章，每刊 3 篇（共 6 篇 PDF，其中 4 篇 curl 直连 API、2 篇经官方 `wiley-tdm` 客户端），逐一验证内容完整性。验证产物暂存 `/tmp/paperradar-tdmcheck/`（6 个 PDF、响应头样本、官方客户端下载产物；作为 fixture 留存前需另行拷贝入库）。
>
> 本文区分三类陈述：**已验证事实**（有产物为证）、**有限观察**（单次或短窗口内的现象，未做压力对照）、**建议**（对 V1 规格的改造方向）。
>
> **决议（2026-10-09，已执行）**：删除 ADR 0014（编号留空，沿用 0007 先例）；新增 ADR《Wiley OA 全文获取采用官方 TDM API》（0024）；`intent/draft.md` §1.3 删除“使用浏览器登录态、机构权限、验证码或反爬绕过自动下载 PDF”排除项，凭证边界移入 §4.8（允许用户自有凭证取得开放全文，禁止自动求解验证码、反爬绕过、机构订阅或他人凭证与付费墙内容；V1 只实现 TDM 通道）；CONTEXT.md Processing 段不变量同步改写；draft 的 §1.3、§2.3、§4.8、§5.2、§8.1、§8.4、§8.7、阶段 B 验收、阶段 F、§13.2、§14、doctor gate 与 §15 同步更新。执行差异见 §6.7。

## 执行摘要

四个首发期刊的 OA 文章均可在本机程序化取得全文 PDF：AMS 与大气科学是普通直连 HTTP；Wiley 两刊（QJRMS 与 JGR-A，后者为 AGU 内容托管于 Wiley 平台）走出版方官方 Text and Data Mining API——用户在 Wiley Online Library 账户上接受点击式 TDM 许可换取 token，程序带 token 请求 API 即得出版级 PDF。该路线无浏览器、无验证码、无 cookie、无反爬对抗，且对 `10.1002`（Wiley）与 `10.1029`（AGU）两类 DOI 统一有效。TDM API 只提供 PDF（无 XML 全文），因此 Wiley 两刊的全文形态在 V1 为 PDF-only。此前基于站点直连 + 人工引导 cookie 的路线已整体放弃并从本文移除（见第 3 节处置说明）。

对 V1 的核心建议：全文获取按“出版方 adapter + 凭证管理”落位，Wiley adapter 走 TDM API 通道并新增一个轻量的**用户 API token** 凭证边界；这不触碰“不自动解验证码、不碰付费墙、不做站点反爬对抗”的红线，但建议以 ADR 明确“出版方官方 API + 用户自有 token”属于允许路径，避免该凭证形态日后被误读进“浏览器登录态”排除项。经与既有决议逐项核查（§6.1）：与 ADR 0014《只自动下载无需用户会话的开放 PDF》及其在 CONTEXT.md Processing 段的不变量镜像存在字面冲突（“无需登录”边界与 403 处置语义）；其余相关决议（ADR 0012、0009、0017、0016、0008、0010、0002）核查无冲突。决议：删除 ADR 0014、放宽 draft §1.3 排除项并以新 ADR 重新界定边界（见文首决议记录）。

## 1. 四刊实测结论速查

| 期刊 | OA 判定方式 | HTML 全文 | PDF | 前提 / 拦截 |
|---|---|---|---|---|
| AIES (AMS) | 全刊开放获取 | 文章页 `.xml` URL 即完整 HTML（含全部章节与段落，首轮样本 161 个长段落） | 同 URL 将扩展名换 `.pdf` | 无 |
| JGR-A (Wiley/AGU) | Crossref license 含 creativecommons（本轮 2026-09-01 以来查询的 100 篇中 47 篇） | TDM API 不提供；V1 接受 PDF-only | `GET api.wiley.com/onlinelibrary/tdm/v1/articles/{DOI}`（见 §2） | 需 TDM token；本轮经家宽直连出口（数据中心出口未验证） |
| QJRMS (Wiley/RMets) | 同上（同期查询 25 篇中 16 篇） | 同上 | 同一端点，与 JGR-A 无差异 | 同上 |
| 大气科学 (IAP) | 全刊免费获取 | `POST /dqkx/data/article/articleFulltextData`（参数 `id`+`language=cn`），返回结构化 JSON（11~16 章节，正文在 `paraContents`） | 文章页内嵌 base64 `article_meta_data` 中的 `filePath`+`pdfFileName` 拼接为直链 | 无 |

本轮 Wiley 6 篇样本全部成功：PDF 均验证 magic bytes、页数（15~29 页）、文件大小（3.3~36.8MB）与首页标题对应；AMS 与大气科学沿用前两轮验证结论。

## 2. Wiley TDM API 关键事实

### 2.1 端点与流程（已验证）

- 端点：`GET https://api.wiley.com/onlinelibrary/tdm/v1/articles/{DOI}`，DOI 需整体 URL 编码（斜杠也编码，如 `10.1002%2Fqj.70320`）。
- 认证头：`Wiley-TDM-Client-Token: <UUID token>`。
- 必须跟随重定向：API 先返回 `302`，`Location` 指向 `alm.wiley.com/alm/api/v2/download/<签名串>` 内容服务器签名 URL，随后 `200 application/pdf`。签名 URL 视为一次性，不缓存复用。
- 示例：
  ```bash
  curl -L -H "Wiley-TDM-Client-Token: $TDM_API_TOKEN" \
    "https://api.wiley.com/onlinelibrary/tdm/v1/articles/10.1002%2Fqj.70320" -o article.pdf
  ```

### 2.2 错误签名（已验证 / 官方文档）

- 缺 token：`400`，空 body。
- token 无效或内容无权限：`403`，空 body。两者不直接可区分；用一篇**已知 OA** 的 DOI 探测即可区分——`200` 说明 token 有效，`403` 说明 token 失效（见 §6.3 生命周期探测）。
- 请求过快：官方文档为 `429`（本轮未触发）。
- `api.wiley.com` 无 Cloudflare challenge、无浏览器指纹/UA 校验，curl 默认 UA 即可；错误响应为空 body 纯文本，与站点侧 challenge HTML 特征完全不同，不会混淆。

### 2.3 限速（已验证 + 官方文档）

- 响应头显式给出配额：`cr-tdm-rate-limit: 60`、`cr-tdm-rate-limit-remaining: <n>`、`cr-tdm-rate-limit-reset: <epoch ms>`。
- 官方限制：最高 3 篇/秒、60 次请求/10 分钟；持续批量建议约 10 秒间隔。
- 取件节奏应读取余量头自适应退避，不做固定间隔的重试轰炸。

### 2.4 覆盖范围与产物质量（已验证）

- DOI 前缀 `10.1002`（Wiley 自有，如 QJRMS）与 `10.1029`（AGU 自有、托管于 Wiley 平台，如 JGR-A）走同一端点均成功——两刊统一通道，无需按刊区分。
- 只提供全文 PDF：无 XML 全文、无 supporting information。Wiley 两刊的 HTML/XML 全文在本路线下不可得。
- PDF 为高分辨率出版级文件（本轮 3.3~36.8MB、15~29 页），利于后续文档解析。

### 2.5 token 与访问模型（已验证 + 官方文档）

- token 获取：WOL 账户在 TDM resources 页面接受点击式 TDM 许可后发放，UUID 格式。
- 官方已知限制：对**权限内容**（非 OA）的访问按**公网 IP** 判定（机构需配置 IP 段访问）。本轮仅取 OA 内容（CC 许可），从家宽 IP 全部成功；OA 场景下对出口 IP 的依赖程度未做对照实验。
- token 的有效期与吊销策略未公开；按“可能随时失效的账户级凭证”设计生命周期管理（§6.3）。

### 2.6 网络前提（已验证 + 未测项）

- `api.wiley.com` 本身无 challenge、无 UA 绑定；出口 IP 只影响权限内容判定（§2.5）。
- 本轮所有 TDM 请求实际经家宽直连出口：软路由对 `wiley.com` 的 DIRECT 规则覆盖了 `api.wiley.com` 子域（Cloudflare 视角出口为家宽 IP、HKG 接入；通用默认出口仍为数据中心 IP）。
- **未测**：数据中心代理出口下 TDM API 是否可用（本机无法强制改道）。部署若走数据中心出口，需先显式验证；家宽直连已验证可用。

## 3. 原站点路线处置说明

Wiley Online Library 文章页直连路径（`/doi/pdfdirect/`、`/doi/full-xml/` 等）受 Cloudflare managed challenge 保护、对非浏览器客户端一律拦截，这一事实多轮实测属实。此前验证过的“人工过验证 + 程序复用站点 cookie”方案虽然可行，但凭证生命周期不可控、需要人工周期性引导，已被 TDM API 路线整体取代；其操作细节、失败路线存档与凭证管理设计已从本文删除，不再作为 V1 候选。若未来需要站点 XML 全文等 TDM 不提供的能力，需另行立项评估,V1 不保留该路线。Feed 抓取路径不受 challenge 影响，发现侧不受此变化影响。决议后 draft §1.3 的凭证边界已放宽：用户人工引导的自有会话与出版方官方 API token 同属允许路径；但 V1 的 Wiley 实现范围仍只有 TDM 通道，站点路线如需启用须另行立项。

## 4. 有效配方（Wiley TDM API 流程）

1. **一次性 token 获取（人工）**：WOL 账户在 TDM resources 页面接受点击式许可，取得 UUID token；以 0600 权限存入凭证区，不写入代码、日志或仓库。
2. **OA 预判**：Crossref license 字段含 creativecommons URL 即候选（判定结果存为 observation，不覆盖 Paper 事实）。
3. **取件**：`GET /onlinelibrary/tdm/v1/articles/{URL编码DOI}` + token 头 + 跟随重定向；或使用官方客户端 `wiley-tdm`（PyPI 1.2.0，仅依赖 requests，token 走 `TDM_API_TOKEN` 环境变量，批量下载内置限速，`api_rate_limit` 建议设 10 秒）。
4. **逐响应校验**：`content-type: application/pdf` + magic bytes（`%PDF-`）+ 页数（pdfinfo）+ 首页文本含论文题名，全部通过才算取得。
5. **批量纪律**：攒批执行；遵守 3 篇/秒、60 次/10 分钟上限，持续场景约 10 秒间隔；读取 `cr-tdm-rate-limit-remaining` 余量；出现 403/429 即停本批并进入诊断（token 失效或权限问题），不做高频重试轰炸。

## 5. 通用注意点

- **Wiley RSS 的 link/title 存在错位**：feed 内 `<link>` 与 `<title>` 的配对不可靠，多轮随机抽取都出现“表面标题”与 DOI 实际文章不符。文章身份一律以 DOI + Crossref 核对为准。
- **大气科学 feed 是 RSS 1.0/RDF**：item 元素带 `{http://purl.org/rss/1.0/}` 命名空间，标准 RSS 2.0 解析会**静默得到 0 条**，必须带命名空间解析。
- **PDF 完整性校验**：magic bytes（`%PDF-`）+ 页数（pdfinfo）+ 首页文本含论文题名。AMS 的 PDF 内部 Title 可能是排版文件名（如 `AIESD250117_proof.pdf`），不能只信元数据。TDM 的 PDF 无此问题，但校验流程统一。
- **OA 判定数据源时效**：Unpaywall 对极新 DOI 可能尚无 `oa_locations` 记录；Crossref 的 `license` 字段（含 creativecommons URL 即视为 OA）更及时。两者都是元数据侧判定，最终仍以下载到的内容为准。Crossref 同一响应的 `link` 字段指向站点端点，本路线不使用（取件统一走 TDM API）。
- **TDM token 是账户级 API 凭证**：按 AGENTS.md 密钥纪律处理——不得写入日志、报告或完整出现在任何输出中；存储需受限文件权限；泄漏等同泄漏该账户的 TDM 访问能力。
- **合规边界**：本路线只触达 OA（CC 许可或出版方免费公开）内容；TDM API 对无权限内容自动拒绝（403），该拒绝即终态，不尝试任何绕过。使用范围遵守点击式 TDM 许可（文本与数据挖掘用途）与官方限速。

## 6. V1 改造建议（目标：V1 内自动获取 OA 全文）

### 6.1 与现行规格、既有 ADR 与 CONTEXT.md 的关系

**（a）`intent/draft.md` §1.3**：该节将“使用浏览器登录态、机构权限、验证码或反爬绕过自动下载 PDF”列入不进第一版的清单。TDM 路线不复用浏览器登录态、不求解验证码、不做反爬绕过，只使用**用户自有账户在出版方官方 API 上换取的 token** 获取 OA 内容，与该排除项的字面与意图均无冲突。

**（b）ADR 0014《只自动下载无需用户会话的开放 PDF》——存在字面冲突（决议：删除，见后）**：
- “无需登录、验证码或用户会话的开放 PDF”：TDM token 由用户在 WOL 账户上一次性登录并接受点击式许可后取得，“无需登录”不再成立；但它不是浏览器登录态、不涉验证码、不是对访问控制的绕过，而是出版方官方 API 的设计用法。
- “Cloudflare 或其他 `403` 记录为访问受阻……送入人工 PDF 队列”：TDM 路线下 `403` 语义必须二分（§2.2、§6.3）——已知 OA 探测返回 `403` = token 失效，是**凭证级**事实，影响全部 Wiley 论文，补救是重新配置 token，不应逐篇送入人工 PDF 队列；候选文章 `403` 且探测证明 token 有效 = 该篇按 API 判定无权限（与 Crossref CC 预判不一致），维持“记录为访问受阻、进入人工 PDF 队列”的既有语义。“Cloudflare”字样随站点路线弃用而失去指称对象，但“403 ≠ 非开放获取”的原则保留。
- 不冲突且继续维持的部分：不绕过访问控制、不复用浏览器登录态（“第二版可重新评估浏览器辅助下载”的表述随删除一并消失，边界改由新 ADR 表达）。

**决议**：不保留修订版，直接删除 ADR 0014，编号留空（沿用 0007 先例）；其仍有效的原则（不绕过访问控制、403 ≠ 非开放获取、人工 PDF 队列）并入新 ADR《Wiley OA 全文获取采用官方 TDM API》。

**（c）CONTEXT.md Processing 不变量段——与 ADR 0014 同源的镜像表述（决议：已按新边界改写）**：“第一版只自动取得无需登录、无需验证码......第一版不使用浏览器自动化或用户登录会话”同（b）冲突。建议改写时在术语层面澄清:**TDM token 是账户级 API 凭证，不是登录会话**;“用户登录会话”禁令的所指（浏览器会话复用）不变，不涵盖出版方官方 API 的用户自有 token。术语对齐:CONTEXT.md 既有“全文受阻”（日报概念）与“人工 PDF 队列”是权威用词，本稿及后续实现一律沿用“全文受阻”,不引入“全文缺失”等平行词汇。

**（d）核查过无冲突、无需改动的决议**：
- ADR 0012 提供方链（CONTEXT.md 同段镜像）：TDM API 是“出版者适配器”的实现通道，不新增数据提供方类别；OA 判定依据 Crossref license、取件走出版者官方端点，仍属“由出版者指向的开放 PDF”。
- ADR 0009 / CONTEXT.md 来源快照：TDM 成功响应承载 PDF，按“原始 PDF”保留制品处理；`400`/`403` 空 body、`429` 与重试只记结构化执行事实，不复制响应体（§6.6 的响应样本仅作离线测试 fixture，不入持久化来源快照）。
- ADR 0017 保留制品：TDM PDF 属“原始 PDF”永久保留类别，高分辨率带来的存储增量按“大型 blob 入文件系统”的既有分工处理。
- ADR 0016 / CONTEXT.md LLM 数据边界：“运行日志不得保存……认证信息或密钥”已覆盖 token，§5 与 §6.3 的 token 纪律与其一致。
- ADR 0008 / CONTEXT.md 阶段输入指纹、ADR 0010 Docling 唯一正文提取器：PDF-only 全文经 Docling 解析、PDF SHA-256 入指纹（§6.5），与既有决议一致。
- ADR 0002 / 校准变更分级：全文获取通道不改变 Screening 语义（输入仍为题名、摘要、Profile），不触发 calibration change workflow；ADR 0022 复用升级消费的是“合法取得的正文提取物”，取得方式变化不改变摘录选择语义。

**结论**：真正的冲突集中在 ADR 0014 及其 CONTEXT.md 镜像段。决议：新增 ADR《Wiley OA 全文获取采用官方 TDM API》并删除 ADR 0014（不保留修订版）；draft §1.3 的整条排除项删除，凭证边界移入 §4.8，允许用户自有凭证（含人工引导的自有会话）取得开放全文，第一版只实现 TDM 通道。

### 6.2 架构落点：出版方全文 adapter

在既有“外部 Adapter 只产生 observation”的边界内新增全文获取 adapter 层：

- 接口形态：`can_fetch(paper) -> 可取/不可取及原因`、`fetch_pdf() -> bytes + 内容校验结果`、`fetch_html() -> 全文结构化文本`。
- **AMS adapter**：无状态。文章页 URL 模式（`.xml`/`.pdf`）直取；HTML 与 PDF 都来自同一 URL 的扩展名变换。
- **IAP adapter（大气科学）**：两步——先取文章页并从 base64 `article_meta_data` 解析 `filePath`+`pdfFileName` 得 PDF 直链与 `articleId`；再 POST `articleFulltextData` 得结构化 JSON 全文。注意 RSS 1.0 命名空间（feed 解析侧）。
- **Wiley adapter**：组合三件事——
  1. **OA 预判**：Crossref license 含 CC 即候选；判定结果连同 DOI 存为 observation（不覆盖 Paper 事实）；
  2. **token 检查**：凭证区无有效 token 时直接返回“待配置凭证”原因，不发无效请求；
  3. **TDM 取件**：`articles/{doi}` + 跟随重定向 + 逐响应内容校验（content-type、magic bytes、页数、标题）；403/429 与限速余量按 §2.2/§2.3 处理。全文形态为 PDF-only（`fetch_html` 对 Wiley 返回“不可得”及原因，而非报错）。

### 6.3 TDM token 凭证管理

- **存储**：文件系统凭证区（0600），存 token 值 + 登记时间 + 来源说明；SQLite 只存凭证状态事实（存在/上次验证/当前判定），**不存值**（与“大型 blob 入文件系统、SQLite 为业务事实源”的既有分工一致，且满足日志不记 secret）。
- **生命周期探测**：doctor 与抓取前用**固定已知 OA DOI** 做一次轻量请求：`200` = token 有效；`403` = token 失效/吊销。用已知 OA 文章探测是关键设计——它把“token 失效”与“候选文章无权限/非 OA”两种 403 区分开。
- **降级行为**:token 缺失或失效时,Wiley OA 论文的全文取得记为**全文受阻**（原因：凭证缺失或失效）--不阻断同批其他论文（既有不变量）,在 CLI 复核队列与日报的“全文受阻”通道提示用户重新配置；凭证级受阻不逐篇进入人工 PDF 队列（与新 ADR 边界一致，见 §6.1(b) 决议）；不自动重试轰炸。
- **幂等**：配置命令重复执行产生新 token 替换旧值（保留历史状态事实）；抓取失败不改变已成功取得的事实；是否重取以系统侧 PDF SHA-256 事实为准，不依赖客户端本地文件缓存（官方客户端 `skip_existing_files` 语义与本系统幂等要求不同，接入时以系统事实源为准）。

### 6.4 CLI 与 doctor

- 新增 token 配置命令（示意名 `paperradar wiley token`）：从参数/环境变量/stdin 读入 token，校验 UUID 格式，用已知 OA DOI 做一次验证后落凭证区；交互输入避免 token 进入 shell 历史。须满足“CLI `--help` 不触发网络/写库”的既有约束。
- doctor 新增检查：token 状态（存在/有效/失效 + 距上次验证时间）；限速配额余量；出口 IP 与上次验证时是否一致（权限内容按 IP 判定，出口变化时保守提示“凭证可用性可能变化”）。
- 部署文档：记录 token 获取步骤（WOL 账户 + 点击式 TDM 许可）；数据中心出口下 API 可用性未验证，列为部署前显式检查项；家宽直连出口已验证可用。

### 6.5 全文事实与阶段指纹

- PDF 取得事实沿用 draft 既有设计（PDF SHA-256 进入 Docling/规范正文阶段输入指纹）。
- Wiley 两刊 V1 全文形态为 **PDF-only**（TDM 无 XML）；规范正文一律从 PDF 解析产出，不引入站点 XML 依赖。若未来需要 XML 需另行决议，本文不保留该路线。
- TDM PDF 为高分辨率出版级文件（3.3~36.8MB/篇），存储预算按“大型 blob 入文件系统”的既有分工处理；PDF 重取（新文件哈希）只使文档解析与 Read 按指纹规则过期；书目信息补全不失效任何阶段的既有规则不受影响。

### 6.6 测试与验收

- **离线 fixture**：本轮 6 个 TDM PDF 入库；400/403 空 body 响应样本、302→alm 签名 URL 重定向链样本入 mock；Crossref license 响应样本入 mock；429 响应合成构造。
- 单元/集成覆盖：OA 判定；token 有效/缺失/失效三分支（含“已知 OA 探测”语义）；403 空 body 与 5xx/超时的区分；重定向跟随；内容校验（防“假成功”）；限速头解析与退避；降级与提示路径；凭证读写权限；幂等（系统事实源优先于客户端缓存）；大气科学两步解析；RSS 1.0 命名空间解析；Wiley RSS title 错位时以 DOI 为准。
- **live 验收**单独显式命令（如 `--live`），不进常规测试；验收清单含：配置 token → 每刊 2 篇 OA 下载 → 内容校验 → 限速余量读取 → 失效模拟（换坏 token → 403 → 降级提示，不轰炸）。

### 6.7 需要的文档/规格变更清单（已执行）

决议于 2026-10-09 执行完毕。实际处置与本节原建议的差异：ADR 0014 未修订而是整体删除；draft §1.3 的排除项整条删除（原建议是补充说明式修订），凭证边界移入 §4.8。

1. 已删除 `docs/adr/0014-only-download-open-pdfs-without-user-sessions.md`（编号留空，沿用 0007 先例）。
2. 已新增 ADR《Wiley OA 全文获取采用官方 TDM API》（0024）：用户自有 token、仅 OA、遵守点击式许可与限速；并入原 0014 仍有效的原则（不绕过访问控制、403 ≠ 非开放获取、人工 PDF 队列）与 403 二分语义（凭证级失效不逐篇入队）。
3. 已修改 `intent/draft.md`：§1.3 删除排除项及第二版“登录态辅助下载”表述；§4.8 补出版者适配器分层、凭证边界、TDM 403 二分、token 生命周期、限速与 `fulltext set-wiley-token` 命令；§2.3 术语对齐“全文受阻”；§5.2 新增 provider_credentials 状态事实实体；§8.4 补凭证级失败归类；§8.7 补出版方 API token 日志禁令；阶段 B 验收与阶段 F 实施测试、§13.2、§14 配置清单、doctor gate、§15 第二版候选同步更新。
4. 已改写 CONTEXT.md Processing 段不变量：允许用户自有凭证取得开放全文 + 403 二分；不新增术语条目，“全文受阻”“人工 PDF 队列”沿用既有概念。
5. 留待实现（不在本次文档修改内）：doctor 出口 IP 一致性检查的实现细则、部署文档（token 获取步骤、数据中心出口验证，见 §2.6 未测项）、`/tmp/paperradar-tdmcheck/` 产物入库 fixture。
6. 本文保留为决议过程记录，后续归档到 `intent/archived_discussions/`。

## 7. 红线（无论 V1/V2 都不做）

- 不获取、不尝试获取付费墙内容；OA 判定必须先于取件；TDM API 对无权限内容的 403 拒绝即终态。
- 不做站点反爬对抗：不自动求解验证码/Turnstile，不投入指纹模拟、headless 对抗等绕过手段。
- 不使用机构订阅、他人凭证或任何非用户本人的凭证与会话。
- 不在日志、报告、错误信息中输出 token 值或完整请求头。
- 请求节奏保持单用户礼貌量级：遵守官方限速（3 篇/秒、60 次/10 分钟），持续场景约 10 秒间隔；攒批、失败即停，不做高频重试轰炸。
- TDM 下载内容的使用遵守点击式 TDM 许可的范围（文本与数据挖掘用途）。
