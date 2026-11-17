# QJ vs JGRA 摘要与元数据完整性复查（2026-11-16）

主题：Quarterly Journal of the Royal Meteorological Society（QJRMS/QJ）与 Journal of
Geophysical Research: Atmospheres（JGRA/JGR）的 Feed/Crossref 摘要及其他元数据完整性。
对应仓库：`/home/meteoboy4/Projects/PaperRadar`；本文件独立于仓库，产物细节见文末。

## 前因后果

1. **EXP-1 v1**（2026-11-02，issue #145）：四刊首轮 HTTP 审计。JGRA 5/5 有主摘要；
   QJRMS 4/5 —— `10.1002/qj.70349` Crossref 有效但 `record_without_abstract`，
   Feed 也无可识别主摘要。另有 Wiley Feed 字段误取缺陷（v1 把 85 字符卷期说明当摘要），
   修复与 v2 规则见 issue #146。
2. **EXP-1 v2**（2026-11-02，issue #147）：`audit-abstract-v2` 规则补跑。JGRA
   Feed 5/5、Crossref 5/5、最终来源 registry 5；QJRMS Feed 4/5、Crossref 4/5，
   同一篇 `qj.70349` 两路均缺；Wiley 出版者 10/10 全 403。
   - 报告：仓库 `docs/verification/exp-1-http-audit.md` 与 `exp-1-http-audit-v2.md`。
   - 由此形成印象「QJ 的摘要完整性没有 JGRA 好」。
3. **本次复查**（2026-11-16，轻量 live 探针，非冻结审计）：直连无代理、https-only、
   复用仓库 `sampling_parser`/`abstract_parser`（`audit-abstract-v2`），请求间隔 1 秒。
   - 探针一：两刊当前 Feed 原位次前 5。JGRA Feed/Crossref 5/5；QJRMS 5/5——**追平**。
   - 历史缺摘要成员 `qj.70349` 复查：Crossref 仍无 abstract、出版者仍 403、
     该条目仍在 Feed 但已滑至第 55 位（超出前 50 取样窗口）。**查明它是 Correction（勘误）**，
     Feed item 根本无 `content:encoded`，只有 66 字符卷期说明。
   - 探针二：仅 QJRMS，当前 Feed 原位次前 25（全部为新论文）。
     24 篇研究论文 Feed 与 Crossref **双双 24/24** 有主摘要（820–2050 code point，
     中位数约 1379，零截断信号）；唯一缺的是原位次 10 `qj.70348` ——
     **"Issue Information"（卷期信息页）**，Crossref 记录存在但无 abstract，出版者 403。

## 结论

1. **QJRMS 研究论文摘要完整性已与 JGRA 实质持平**（本轮 5/5 与 24/24）；
   早期「QJ 较差」的缺口来自非研究论文条目（Correction / Issue Information），
   它们结构性无摘要，不是 QJ 系统性缺陷。
2. **JGRA Feed 并非干净**：当前 Feed 第 24 位也是 Issue Information
   （`10.1029/jgrd.71134`）。两刊 Feed 都有约 1–4% 非研究论文条目
   （QJRMS 全 Feed 100 条：研究 96、Issue Information 1、Correction 1、
   Invited 1、Review 1），未来取样抽到无摘要成员是随机落点问题。
3. **元数据完整性（QJRMS n=24 研究论文，Crossref）**：title/container-title/
   作者姓名/affiliation/ISSN/publisher/type/license/fulltext link/reference-count/
   issued/deposited 全部 24/24；ORCID 23/24 篇（作者层面 57/109，52%）；
   funder 16/24；**volume/issue 15/24**、**page 0/24**——均为 EarlyView 未入册所致，
   入册后补齐，对 Screening 主流程无影响。
4. **确切文章类别的来源在 Feed 本身**：每条 item 的 `<category>` 与
   `<prism:section>` 逐条完全一致（QJRMS 100/100、JGR 24/24）。
   观测词表：QJRMS `RESEARCH ARTICLE / ISSUE INFORMATION / CORRECTION /
   INVITED ARTICLE / REVIEW ARTICLE`；JGR `Research Article / Issue Information`。
   仓库审计解析器与生产 ingest（`feed_ingestion.FeedItem.raw_categories`）
   均已逐条保存该值。
5. **但类别信号当前不参与判定**：fixture-audit 契约（`audit-category-v1`）明确
   「Wiley category/prism:section 原值仅保存」，判定闭集只有 Crossref
   `message.type=journal-article`（DataCite、dqkx 各有判据），题名启发式、
   og:type 等被排除。Crossref 对勘误/卷期信息同样给 `journal-article`，
   出版者页（可能含 citation_article_type）被 403 挡住——因此现状下这类条目
   以 journal-article 身份进入流程后摘要结构性缺失。

## 用户裁决（2026-11-16）

- **维持**规格 §2.1 的「journal-article 一律进 Screening」，不提前按类别筛除。
- 当 Feed 文章类别**不是** `RESEARCH ARTICLE`（或其小写版）时，因文章类型导致
  摘要或其他元数据不完整：**不视为问题**，流程中可跳过该篇且**不告警**。
- **有摘要的其他类型文章依旧正常走完整流程**（裁决只豁免「类型性缺失」，
  不豁免研究论文的缺失）。
- 该裁决记录于本文件；落地到产品/审计规则（如消费 Feed 类别豁免类型性缺失）
  属后续工作，届时按仓库规则需要新类别规则版本（`audit-category-v2`）、
  新计划与契约更新，并以本裁决为依据。

## 注意点

1. **词表与大小写**：两刊大小写不同（`RESEARCH ARTICLE` vs `Research Article`），
   裁决口径为「RESEARCH ARTICLE 或其小写版」（大小写不敏感匹配）。
   目前仅观测到 5 种取值，跨刊/长窗口可能还有未观测值（如社论、评论）；
   未观测值默认按「非 RESEARCH ARTICLE」处理，出现新值时应补充观测再固化。
2. **类别一致性**：`category` 与 `prism:section` 在两刊均 100% 一致，可互为冗余；
   若未来出现分歧条目，按契约保持「仅保存、矛盾即冲突」的保守口径。
3. **不将题名启发式当判据**：「Correction to …」「Issue Information」等题名模式
   只能作辅助披露，不能替代 Feed `<category>`；契约明确排除题名/DOI 前缀/og:type。
4. **验证边界**：本次为单时点探针（5+5 与 25），与 EXP-1 冻结样本零重叠，
   不能跨轮推断长期稳定率；出版者通道仅个别请求（403），
   browser_render/official_api/repository 未测。
5. **产物位置**：`PaperRadar/.scratch/qj-jgra-metadata-recheck-20261116/`
   （`.scratch/` 不进 Git，仅本机）：`probe.py`（两刊 top5）、
   `probe-qjrms-n25.py`（QJ 前 25）、`artifacts/`（两刊 Feed 快照、
   逐篇 Crossref JSON、`probe-result.json` 为 n25 轮结果，已覆盖探针一汇总，
   探针一数据以本文件与对话记录为准）。
6. **请求量**：全程直连无代理，共 2+2 次 Feed、36 次 Crossref、2 次出版者探测，
   间隔 1 秒；无重定向跟随、无重试绕过。
7. **规格张力已由裁决消解**：规格 §2.1「不提前区分勘误/社论」与「跳过类型性缺失」
   并行不悖——入选照旧，缺失豁免只作用于摘要/元数据完整性评估与告警层面。
