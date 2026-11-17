# 裁决备忘：DOI 路由覆盖面与参考文献类型限制

状态：已由用户裁决（2026-11-17），**尚未落进规格/契约/代码**；本文件是实施前的依据记录，不是完成声明。
触发问题：阶段 C 实施项「完成四刊出版者元数据和 Crossref/DataCite DOI 路由」是否够用，是否需要更多 DOI 提供商。
范围：本文只裁决 **DataCite 的取舍**与**参考文献类型限制**。《大气科学》的通道选择、ISTIC 处置、以及 metadata-ready 门禁的处置**不在本文**，已由同目录 `dqkx-metadata-channel-decision-20261116.md`（裁决日期 2026-11-16）处理；本文不复述其结论。
本文档后续动作：确认无误后应拆成（a）`docs/adr/` 新 ADR 或对 [ADR-0033](docs/adr/0033-classify-journal-articles-from-explicit-source-types.md) 的补充，（b）`intent/draft.md` §4.3/§4.7/§13.2 与阶段 C 的文字修订，（c）`docs/contracts/` 相应条款修订。

---

## 1. 前因

阶段 C 的实施项与 §4.3 的接入清单都写作「Crossref 与 DataCite DOI 路由」，读起来像是四刊都被这两家覆盖。实际按 `https://doi.org/doiRA/{doi}` 路由，四刊是 3 家 Crossref + 1 家 ISTIC：

- AIES（`10.1175`）、JGR-A（`10.1029`）、QJRMS（`10.1002`）→ Crossref；
- 《大气科学》（`10.3878`）→ **ISTIC**，对 V1 的注册机构链判 `agency_unsupported`；
- DataCite 在四刊论文上 **0 个适用成员**。

于是同一句话里藏着两个不同问题：一是「第四个刊没有可用注册机构」，二是「DataCite 排在清单里但从未被四刊行使」。

## 2. 实验记录（只读网络探测，2026-11-17）

样本：AIES 2 篇、JGR `10.1029/2025JD043927`、QJRMS 4 篇、《大气科学》2 篇固定样本；另从《大气科学》当前目录页取 14 篇近期 DOI；参考文献侧取 4 篇种子论文的 Crossref `reference` 数组。

| 检查 | 结果 |
|---|---|
| `doiRA` | AIES/JGR/QJRMS → Crossref；《大气科学》→ ISTIC（16/16 一致） |
| `api.crossref.org/works/{doi}` | 非《大气科学》样本 8/8 命中且 `type=journal-article`；《大气科学》2/2 **404** |
| `api.datacite.org/dois/{doi}` | **0/8 命中，全 404** |
| `api.crossref.org/journals/{issn}/works` | AIES 361、JGR-A 11635、QJRMS 17312 篇 journal-article；ISSN 1006-9895 **整刊 404（未在 Crossref 注册）** |
| `doi.org` + `Accept: application/vnd.citationstyles.csl+json` | 四刊 8/8 返回 JSON；前三刊 302 到 `api.crossref.org/.../transform`，《大气科学》302 到 `http://122.115.55.36:8000/doi/...` |
| 《大气科学》CSL JSON 质量 | 14/14 有题名 + 中文摘要（247–632 字）；摘要与出版者 `dc.description` 逐字相同（同一样本 532 字，无截断） |
| 《大气科学》CSL JSON 缺陷 | 14/14 **作者只有首位 1 人**（出版者 `dc.creator` 有 4 人）、`publisher=null`、无 license、无 references、`type=article-journal` |
| 《大气科学》出版者页 | `https://www.iapjournals.ac.cn/dqkx/article/doi/{doi}` 200，`dc.title`/`dc.description`/`dc.type=论文` 齐全 |
| `doiRA` 对不存在的 DOI | 返回 `200 + [{"status":"DOI does not exist"}]`（无 `RA` 字段） |
| `chinadoi.cn` / `api.chinadoi.cn` | 本机探测不可达（http 000），不作为路线 |

参考文献侧（4 篇种子，262 条参考文献，224 条带 DOI）：

| 归属 | 类型 | 条数 |
|---|---|---|
| Crossref | journal-article | ~207（含 8 条 AMS/ASCE 老式 DOI） |
| Crossref | proceedings-article / posted-content / book-chapter / monograph | 5 / 2 / 1 / 1 |
| **DataCite** | **Text**（ECMWF 技术备忘录 `10.21957/*`、Zenodo `10.5281/*`） | 4 |
| **DataCite** | **Preprint**（arXiv `10.48550/*`） | 3 |
| **DataCite** | **Dataset**（Mendeley Data `10.17632/*`） | 1 |

**DataCite 占 8/224 ≈ 3.6%，其中 journal-article 为 0 条。** 换一个口径：样本中非 journal-article 共 **17** 条（Crossref 9 + DataCite 8），即**裁决二新纳入的那一类里，DataCite 注册的占 8/17 ≈ 47%**。

## 3. 三个结论

**3.1 DOI 路由的覆盖缺口不在「少一家提供商」。** `doi.org` 本身就是统一解析器，RA 之后各自平台；四刊需要的不是第三个 RA，而是对 ISTIC 的处置决定——该处置已由 `dqkx-metadata-channel-decision-20261116.md` 裁决（不引入 ISTIC）。本文不再展开。补一家新 RA 无助于四刊。

**3.2 DataCite 在「四刊论文」上零适用，但在「这些论文的参考文献」上不是零。** 四刊论文 0/8；参考文献里占 3.6%，但全部是 Preprint/Text/Dataset，按 A10 闭集属显式非 journal-article，因此在裁决二之前它们没有消费者、不进 Screening。**裁决二把这一类的类型变成必须保存、按类型计数的可见字段后，DataCite 从「零消费者」变成「该字段的唯一来源」**（见 §5.1）。另有一处潜在用途是被 `feed_metadata/service.py:177-179` 挡住的——预印本版本（arXiv 是 DataCite）目前根本没有元数据路线，因为服务只接受 `version_kind == "journal"`。

## 4. 裁决一：保留 DataCite，但从阶段 C 的措辞与验收里摘出来

保留依赖的理由：适配器、契约条款、A10 闭集的 `DataCite JournalArticle` 类别值、`tests/test_feed_metadata.py:120-144` 的适用性测试都已存在；删除会与 A10 闭集和 [ADR-0034](docs/adr/0034-separate-fixture-declarations-and-acquisition-audits.md) 冲突，且换来零收益。

要改成「接口就绪、四刊无适用成员」的位置：

| 位置 | 现状 | 应改为 |
|---|---|---|
| `intent/draft.md:1993`（阶段 C 实施项） | 「完成四刊出版者元数据和 Crossref/DataCite DOI 路由」 | 「完成四刊出版者元数据与 DOI 机构路由（Crossref/DataCite 两条适配器就绪；四刊中 Crossref 3 刊、ISTIC 1 刊、DataCite 无适用成员）」 |
| `intent/draft.md:426`（§4.3 第一版接入清单） | 「Crossref 与 DataCite DOI 路由」 | 同上口径，明确 DataCite 是接口而非四刊覆盖 |
| `intent/draft.md:565`（§4.7） | 「DataCite 用于 DOI 身份与元数据路由，不假设它一定提供参考文献」 | 保留，并补一句：四刊论文中 DataCite 成员为 0，**不参与四刊论文覆盖统计**；但参考文献的类型事实会把 DataCite 变成必要来源（见 §5.1） |
| `docs/contracts/fixture-audit.md:196-199` | Crossref/DataCite 适用性矩阵 | 增加「无适用成员」与「不可用」的区分，避免把 0 成员记成 0% 命中率 |
| 阶段 C DoD / 验收文字 | 「Crossref/DataCite DOI 路由」 | 明确验收分母不含 DataCite；DataCite 只验收接口与拒绝路径（`tests/test_feed_metadata.py:156-175` 已有的 mEDRA/404 分支） |

注意：不得因此声称「DataCite 已被四刊验证」；也不得把四刊论文中的 0 成员算进任何命中率分母（与 §4.3「不同策略不合并分母」同源）。但「摘出」只适用于**四刊论文的覆盖统计**：裁决二把参考文献的类型变成一等事实，DataCite 在那里是**唯一来源**（见 §5.1），因此它进入参考文献链路的验收面，而不是被完全排除在验收之外。

## 5. 裁决二：放宽参考文献类型限制，`journal-article` 之外也可引入并计数

**这是本次唯一与现有安全行为直接冲突的裁决，落地前必须收窄解释。** 现有约束：

- [ADR-0011](docs/adr/0011-admit-all-journal-article-records-to-screening.md) 与 A10（`intent/draft.md:418`）把类别依据固定为封闭表，其他明确类型判非 journal-article；
- `src/paper_radar/fixture_audit/sampling_selection.py:192-199`、`sampling_records.py:187` 按 `journal_article` 过滤；
- `docs/contracts/fixture-audit.md:19` 的闭集表述。

**默认采用窄解释（本次按此实施）**：非 journal-article 的参考文献可以被**引入并计数**——即保存原始引用、来源位置与强标识，参与「被至少两篇不同 accepted 种子引用」的晋级计数，并可按类型分别统计；但**不因此获得 Paper 身份、不进入 Screening、不进校准池**。准入仍由 A10 类别依据决定。

取窄解释的原因：宽解释（非 journal-article 也可晋级成 Paper 并进 Screening）意味着把数据集、软件、技术备忘录、预印本推进 Screening 与自动精读，直接改写 ADR-0011 的门槛与 §9 的收口判据，属于另一条独立裁决，不应夹带在本次「放宽类型限制」里。

落地必须满足：

1. **按类型分别计数**，不把 dataset/software/preprint 的引用次数与 journal-article 合成一个比例（与 §4.3、§13.2 的分母纪律一致）；
2. **晋级计数与准入判定分开**：计数可以包含所有类型，准入只看类别依据；两者不得互相推断；
3. **不得静默制造「晋级了但永远不 Screening」的悬空候选**：若某条引用已晋级但类别为非 journal-article，必须有明确落点（停留为历史候选并附类别事实，而非 `metadata_unobtainable`），类型分布是用户可见字段，后续需实现按类型分列的引用计数/报表、“已晋级但非 journal-article”的历史候选落点、种子论文的参考文献总列表，先完善文档和路线图但不用在阶段 C 完成；
4. 原始引用、类型判定来源与原始响应必须可回查（[ADR-0009](docs/adr/0009-retain-only-material-provider-responses.md)、[ADR-0017](docs/adr/0017-retain-only-source-and-analysis-bearing-artifacts.md)）；
5. 量级参考：本样本中非 journal-article 约占参考文献 DOI 的 8%，放宽后这条路径会有真实流量，不能当边角情况处理。

### 5.1 副作用：DataCite 在窄解释下获得唯一消费者（类型事实）

`doiRA` 只给注册机构，不给类型；`A10` 又把类别依据限定在注册机构字段（`Crossref message.type` / `DataCite types.resourceTypeGeneral`），禁止用 DOI 前缀、URL 或位置推断兜底。而 Crossref 的 `reference` 数组本身不含被引条目的类型（实测键集合只有 `DOI`、`doi-asserted-by`、`key`、`article-title`、`author`、`year`、`journal-title`、`volume`、`page` 与 `unstructured`）。因此：**任何 DataCite DOI 的参考文献要得到类型事实，只能向 `api.datacite.org` 问**。裁决二把「非 journal-article」从「没人要的字段」变成「必须保存并按类型计数的可见字段」后，DataCite 就从「零消费者」变成「窄而不可替代的消费者」——在样本里，它一家供给了那类新纳入条目的 47%。

调用面取决于把类型解析放在哪一步（落地时必须二选一）：

| 方案 | 类型解析时机 | 外部调用面（每 4 篇论文 / 224 条带 DOI 引用） | 代价 |
|---|---|---|---|
| T1 记录时 | 每条带 DOI 引用一次注册机构（Crossref ≈ 207 + DataCite 8） | ≈ 224 次 | 能真正按类型分桶；需要引用级缓存、配额与失败分类 |
| T2 晋级/准入时 | 仅在引用晋级或被显式选择时 | 仅晋级候选项，DataCite 侧可能近似 0 | 「按类型分别计数」退化为「按 RA 计数 + 未解析缸」 |
| T3（建议） | 进入晋级候选（首次被引用）时 | 早于 T2、远低于 T1 | 统计分母限定为「已有类型事实的引用」，须在契约里写清 |

我个人建议选 T3, 具体可由 Agent 决定；不论选哪个，必须写死两条语义：DataCite 返回 **404 / 失败 → 类型为 `unknown`，不得当成非 journal-article**（A10：「缺字段为未知」）；`unknown` 与 `非 journal-article` 在计数与准入上不可合并。DataCite 本轮实测到的具体值是 `Text`、`Preprint`、`Dataset`，适配器必须能落下这些值而不是变成 `unknown`。

## 6. 额外工作清单

裁决一相关：

1. 改 §4.3/§4.7/§13.2/阶段 C 措辞（表格见 §4），并在 fixtures/审计汇总中区分「无适用成员」与「命中率为 0」。
2. 为 `doiRA` 的 `200 + {"status":"DOI does not exist"}` 定归类（现契约只写「单机构 404 不证明不存在」，未覆盖这个**全局否定信号**），补契约与测试；否则它落进 `agency_unknown`，语义偏松。
3. 阶段 C DoD 文字去 DataCite 分母；保留 DataCite 拒绝路径的契约测试。

裁决二相关（§4.7 与 A10 的实现尚未开始，可一次做对）：

4. 参考文献记录增加显式类型维度（含「未知」），并保证类型判定有来源定位。
5. 晋级计数与准入判定拆成两个独立投影与独立测试；补「已晋级但非 journal-article」的落点测试。
6. 按类型分别统计的报表字段与契约条款。
7. 选定类型解析时机（§5.1 的 T1/T2/T3）并据此定配额、缓存与分母口径。
8. **DataCite 类型适配器进入实现范围**（窄解释的副作用）：`registry_datacite` 在参考文献链路上只用于取 `types.resourceTypeGeneral`；补「404/失败 → `unknown` ≠ 非 journal-article」与「`Text`/`Preprint`/`Dataset` 正确落地」的契约与测试。这是 DataCite 在 V1 中唯一被四刊实际行使的路径，验收应包含它。

范围分层（避免把报表类工作拉进阶段 C）：第 4、5、7、8 项属于阶段 C 前的契约与最小实现（类型事实、计数/准入分离、解析时机、DataCite 类型适配器）；按类型分列的报表、种子论文参考文献总列表等属文档与路线图先行、后续阶段实现（见 §5 约束 3）。

## 7. 附带发现（对 §4.7 直接有用）

1. **Unicode 连字符是量级问题，不是个例**：224 条参考文献 DOI 里 **41 条含 U+2010**（约 18%）。规格 §13.2 只把它记在 QJRMS 单篇样本的备注里；不规范化会整批丢掉约五分之一的引用边，应升为 fixture。
2. **AMS 老式 DOI 才是规范化的真正边界**：形如 `10.1175/1520-0450(1964)003<0396:ATFMDI>2.0.CO;2`，含 `<` `>` `:`。任何「排除尖括号」的 DOI 正则都会截断它——本次第一版探针就截断了 8 条并误判为「不存在」，复核后确认均为 `journal-article`。建议这类样本进 §4.7 fixture。
3. **Crossref `reference` 数组不含被引条目的类型**（见 §5.1）：类型只能问注册机构，这直接决定了裁决二的外部调用量与 DataCite 的必需性。
3. **`doiRA` 的全局否定信号**（同 §6 第 2 条）：这个信号正好能阻止从原始字符串提取出的伪 DOI 建成引用边，但当前没有任何契约条款使用它。
4. **参考文献的非期刊文章占比约 8%**：这是 §4.7 设计上接受的漏召回，之前没有量级参考；裁决二放宽后它从「漏召回」变成「记录并按类型计数」。
5. **DataCite 在参考文献中的具体形态**：ECMWF 技术备忘录（`10.21957`，`Text`）、Zenodo（`10.5281`）、arXiv（`10.48550`，`Preprint`）、Mendeley Data（`10.17632`，`Dataset`）。自裁决二起，这就是 DataCite 在 V1 里唯一会被实际调用的场景；若日后还支持预印本版本元数据，则是第二个入口。
6. **《大气科学》ISTIC CSL 摘要与出版者页逐字一致但作者只给首位**：该通道已裁决不启用；若将来重议，它只能作题名/摘要候选，绝不能作作者、license、参考文献的权威（`docs/contracts/paper-facts.md:177` 的字段优先级不受影响）。
7. **`chinadoi.cn` 本机不可达**，不要把它写成备选路线；ISTIC 侧可用的是 `doi.org` 内容协商重定向到的 IP 端点。

## 8. 未验证与残留风险

- 参考文献统计基于 4 篇种子（262 条），非四刊整体抽样；RA 与类型分布的代表性未验证。
- 未验证《大气科学》出版者页在正式 `acquisition_strategy_version` 通道下的长期稳定性（本次仅单次普通 UA GET；`exp-1-http-audit-v2.md` 记录过该刊 302 → `disallowed_scheme` 的位置）。
- ISTIC 端点的配额、可用性与是否长期只有明文 IP 形态，均未验证。
- 本次未改任何源码、契约或 fixture；`agency_unsupported` 阻断 metadata-ready 仍是当前实现（其处置见 dqkx 那份文档 §9，按 B，尚未落地）。`tests/test_feed_metadata.py:156-175` 没有覆盖「feed + publisher 完整、仅机构不支持」这一组合（该测试同时缺摘要，无法单独隔离机构条件），落地 B 时须补这个用例。
- §5.1 的 DataCite 类型事实基于 8 个样本（`Text` 4 / `Preprint` 3 / `Dataset` 1）；四刊参考文献整体可能还有其他 `resourceTypeGeneral` 值，适配器不得只做成这三个的查找表。

## 9. 复现方式

- 机构路由：`GET https://doi.org/doiRA/{doi}`；机构元数据：`GET https://api.crossref.org/works/{doi}`、`GET https://api.datacite.org/dois/{doi}`。
- 整刊覆盖：`GET https://api.crossref.org/journals/{issn}/works?rows=1&filter=type:journal-article`。
- 内容协商：`GET https://doi.org/{doi}` 且 `Accept: application/vnd.citationstyles.csl+json`（注意 Crossref 系会 302 到 `api.crossref.org/.../transform`，ISTIC 系会 302 到明文 IP 端点）。
- 参考文献：取 Crossref `message.reference`，DOI 优先用结构化 `DOI` 字段，缺失再从 `unstructured` 提取；提取时先把 U+2010/U+2011/U+2013/U+2014 归一为 `-`，并保留 `<>:` 等历史字符。
- metadata-ready 阻断：用 `tests/test_feed_metadata.py` 的测试床把 `doiRA` 桩设为 `ISTIC`、publisher 桩返回完整题名/摘要/URL，观察 `missing == ('agency_unsupported',)` 与 `minimum_complete is False`。
