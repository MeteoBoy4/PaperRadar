# 只取 VOR 的来源裁决与实施清单

- 裁决日期：2026-11-16
- 裁决者：所有者（用户）
- 状态：**已裁决，未实施**
- 调查基线：分支 `integration/185-stage-b`，HEAD `e11ffb0`，工作树干净
- 文档性质：过渡记录，**不是正式 ADR**。按 [`docs/agents/documentation.md`](docs/agents/documentation.md)，决策应进 `docs/adr/`，规格改写进 `intent/draft.md`，现状边界进 `docs/contracts/`。本文只承载「裁决依据 + 注意点 + 改动清单」，落地时须拆分为 ADR-0072、规格改写与契约改写，并删除或归档本文件。

---

## 一、裁决内容

1. **四刊只取 VOR（version of record）**。AOP / online-first / EarlyView / 优先发表一律不进入发现范围。此决策推广到全部期刊，但**判定方法按刊各自定义**（V1 四刊）。
2. **aies 的 DOI 由 Feed link 路径推导**：`/view/journals/aies/<vol>/<issue>/AIES-D-YY-NNNN.n.xml` → `10.1175/aies-d-yy-nnnn.n`。此路径明确**突破**既有契约与规格中「不从路径推断 DOI」的表述。
3. **aies 断线兜底改用 Crossref 增量流**，不使用 sitemap。
4. **aies sitemap 不进入架构**：不作发现源、不作取证工具、不纳入契约监测。
5. **aies 不抓出版者文章页**。接受文章类型（category）= unknown；日期采用「VOR 上线日」。

---

## 二、前因（为什么这么裁）

1. **aies Feed 元数据过少**：`aies-overview.xml` 共 25 条，条目字段只有 `title / link / description(Volume+Issue) / pubDate`，无 DOI、无作者、无摘要；这 25 条恰好等于当期（5/4）整期目录。
2. **出版者文章页不可依赖**：项目 UA 与 curl 默认 UA 均 403，仅浏览器 UA 200，单篇 1.3 MB。现有 aies 身份路线（抓页面读 `citation_doi`）在 live 条件下实际不可用，长期运行还会面临 WAF 静默失效。
3. **Feed 天然是 VOR-only**：25/25 条均为期次路径、0 条 `/aop/`；当期 15 篇未入期 AOP 一条都不出现。选 VOR-only 的诉求与 Feed 的输出边界完全对齐。
4. **官方通道已查清且都不解决 UA 门**：`robots.txt` 允许 `/view/`（Crawl-delay 5）、`llms.txt` 明写 `allow: /view/journals/`、Crossref 为 361/361 条记录注册了 `intended-application: text-mining` 指向同一 `/view/` 页，但三者都是「授权与入口合法」，仍需伪装 UA。既然只要 VOR，成本可以不付。
5. **sitemap 在 VOR-only 下更低效**：它混合 AOP 与 VOR，且 AOP→VOR 升级表现为**旧桶原地重写**（239 条 VOR 条目中 155 条即 65% 的 bucket 月比 lastmod 月早 ≥2 个月，最大 31 个月），当月+上月轮询看不到升级；反而不如 Feed 直接就是 VOR 目录。
6. **Crossref 足以承担元数据与兜底**：ISSN 2769-7525 共 361 条记录，title 361、author 342（1699 位作者仅 3 位缺单位）、abstract 337（337 篇全部以 `.` 收尾，无截断）、license 342、reference 325；`filter=…,from-created-date=…` 可增量，`volume != null` 可作 VOR 门。
7. **路径↔DOI 双向一致**：Feed 25 条全部命中 Crossref 且标题 25/25 一致；反向验证 342 篇真文章的 Crossref `link` 文件名 == DOI 后缀 342/342。

---

## 三、注意点（实施时必须守住的边界）

1. **路径推导不是"尽力解析"**：只接受受控主机、受控路径前缀与严格形态正则，形态不符（如 `aies-12masthead`、`aies-41cover`）必须显式拒绝，不能兜底拼 DOI。
2. **推导出的 DOI 仍是候选身份**：须与 Crossref 记录的标题/卷期核验一致后才落定，路径本身不成为权威依据。
3. **VOR 判定必须是期刊级声明**，不能做成全局规则：aies 是「Feed 出现即 VOR」，其他三刊（Wiley eTOC / most-recent、`dqkx current.xml`）需逐刊写明，并纳入端点与判定规则的契约监测。
4. **「VOR 上线日」需要落地细则，当前仍有一个必须澄清的分歧**：
   - Feed `pubDate` 实测是**文章首次在线日**（`AIES-D-25-0069.1` = 2026-08-28），**不是**入期日（该期 5/4 实际目录上线日约 2026-11-13）；
   - Crossref `published` 是期次月、且只有月精度；
   - 因此「VOR 上线日」只能取「Feed 该条目的首次 observed_at（日精度）」或「Crossref `published`（月精度）」。**建议取前者并在契约里写清它是"发现时刻"而非出版者公告时刻**，缺值回退后者。这一条需要在写 ADR 时定死。
5. **摘要必须按 `<jats:title>` 切分**：Crossref 的 abstract 在 AMS 有 Significance Statement 时是同一条 JATS 串里的分段；直接当主摘要会混入显著性声明，并与既有截断判定冲突。
6. **Crossref 摘要不保证与页面逐字一致**：实测 1 例首句被改写（`AIES-D-24-0083.1`：页面 `Artificial intelligence (AI)-based…` vs Crossref `AI-based…`）。任何「摘要变化 → 版本变更」的推断必须豁免这种措辞差。
7. **`reference-count == 0` 不能解读为 Crossref 不覆盖**：aies 的 0 引用全部来自未入期条目（15/15），而其中一篇页面有 40 条参考文献。
8. **规格存在直接冲突，必须原地改写**：规格 §2.1 与 §12 矩阵写有「在线优先、EarlyView 或优先发表属于正式期刊版本」；本裁决推翻该条。不改规格就实现会造成代码与规格对立。
9. **类别依据退化**：不抓页面后，aies 只剩 Crossref `type=journal-article` 与 Feed 原值，类别记为 unknown；fixture 审计的类别闭集需要相应说明，不能把 unknown 当冲突。
10. **停机 = 永久丢失**：Feed 是滑动窗口（当期目录，aies 约 4 期/年）。停机超过一个期次，那些 VOR 从 Feed 永久消失 → Crossref 兜底不是可选项，且必须定义回溯窗口。
11. **端点会坏**：同一批 AMS Feed 中 `jcli-overview.xml` 当前返回 500。端点可用性要靠监测暴露，不能靠重试静默掩盖。
12. **本文件是新增文档**：按固定验收范围规则，新文档须显式分类登记，否则默认按固定材料处理。

---

## 四、额外工作（裁决之外的连带义务）

- 新增 ADR（下一个编号 0072），并在 §2.1/§12 改写处标注出处。
- 规格 `intent/draft.md` 多处原地改写（不重编号、不加日期日志）。
- 六份 Feed／审计／事实相关契约改写或收窄。
- 受控 vocabulary 变化：采集路线词表（含 `publisher`）、parser identity 取值。
- Alembic 迁移：若需持久化「DOI 来源」或 parser identity 新值。
- 新增测试模块（D1 独立未绑定测试）+ `docs/verification/` 覆盖台账。
- 固定材料登记：`scope-material-inventory.json`、必要时 `scripts/verification_scope_materials.py` 中央登记与 S3 确认。
- 路线图：模块 C/F 范围、待裁决表增删、承接责任更新。
- `README.md` 能力摘要同步。

---

## 五、可能的仓库改动清单（只读调研结果，仅写文件与大致改什么，为建议性质）

### 文档与决策

| 文件 | 类别 | 大致改什么 |
| --- | --- | --- |
| `docs/adr/0072-*.md` | 新增 ADR | 记录本裁决：VOR-only、路径派生 DOI、Crossref 兜底、sitemap 排除 |
| `docs/adr/0030-*.md`、`docs/adr/0035-*.md` | 状态行 | 与"版本/online-first 语义""Feed 派生事实"相关处加反向指针，正文不动 |
| `intent/draft.md` | 规格 | §2.1 Feed 表与 online-first 语义、§4.2 抓取规则、§4.3 类别与摘要来源、§4.4 版本变化、§11 阶段 C 在线优先版等表述、§12 验收矩阵行、§13.3 fixture 特征、backlog 条目 |
| `GLOSSARY.md` | 术语 | 新增或修订：VOR、在线优先的排除、路径派生身份、VOR 上线日 |
| `README.md` | 能力摘要 | 四刊发现范围与「只取 VOR」的现状描述 |
| `docs/roadmap.md` | 计划 | 模块 C/F 范围与状态、待裁决表增删、依赖与承接责任 |
| `docs/agents/invariants.md` | 不变量 | 若把「只取 VOR」「路径派生身份受控例外」确立为架构约束 |
| `docs/agents/testing.md` | 规范 | 仅当新测试/覆盖台账流程需要说明 |

### 现状契约

| 文件 | 类别 | 大致改什么 |
| --- | --- | --- |
| `docs/contracts/feed-ingestion.md` | 契约 | 期刊参数化、VOR 准入规则、DOI 来源事实 |
| `docs/contracts/feed-metadata.md` | 契约 | aies 路线集合（仅 Crossref）、摘要分段规则、类别 unknown 语义 |
| `docs/contracts/feed-pipeline.md` | 契约 | 四刊组合、VOR 门、停机兜底入口 |
| `docs/contracts/fixture-audit.md` | 契约 | 收窄 aies 出版者身份路线；类别依据；路径派生身份的可核查要求 |
| `docs/contracts/paper-facts.md` | 契约 | Feed 身份/端点相等性按刊定义、DOI 来源与日期语义字段 |
| `docs/contracts/screening-tasks.md` | 契约 | 核对 Feed 归属与语言来源表述（取值不变） |
| `docs/contracts/runtime-config.md`、`docs/contracts/config-snapshots.md` | 契约 | 仅当 journals 配置新增每刊 VOR 策略声明时更新 |
| `contracts/`（冻结导出目录） | 冻结材料 | 仅当权威 Pydantic Schema 变化才需重新 export / check |

### 代码

| 文件 | 类别 | 大致改什么 |
| --- | --- | --- |
| `src/paper_radar/sources/feeds.py` | 声明 | 期刊→端点之外，补每刊 VOR 判定与 DOI 来源声明 |
| `src/paper_radar/feed_ingestion/parser.py` | 解析 | aies item 解析、路径推 DOI、移除 publisher 路线构造 |
| `src/paper_radar/feed_ingestion/service.py` | 服务 | 期刊参数化、VOR 门、停机兜底入口 |
| `src/paper_radar/feed_ingestion/models.py` | 模型 | parser identity 取值扩展（Literal）与条目字段 |
| `src/paper_radar/feed_ingestion/repository.py` | 持久化 | 端点/journal 校验由硬编码改为按刊 |
| `src/paper_radar/feed_metadata/service.py` | 服务 | 期刊参数化、aies 路线裁剪、VOR 门 |
| `src/paper_radar/feed_metadata/models.py`、`projection.py` | 模型 | 缺项/类别 unknown 的表达 |
| `src/paper_radar/feed_pipeline/service.py` | 组合 | 每刊组合与兜底串联 |
| `src/paper_radar/fixture_audit/acquisition_policy.py` | 采集策略 | 移除 aies 出版者路线及其 URL 白名单 |
| `src/paper_radar/fixture_audit/sampling_parser.py` | 解析 | 去掉 aies `publisher_url` 分支 |
| `src/paper_radar/fixture_audit/sampling_selection.py` | 选择 | aies 不再经出版者取 DOI |
| `src/paper_radar/fixture_audit/abstract_rules.py` | 规则 | aies 摘要/类别来源收窄到 Feed 与 Crossref |
| `src/paper_radar/fixture_audit/source_validation.py` | 校验 | `citation_doi`/`dc.identifier.doi` 识别范围收窄 |
| `src/paper_radar/fixture_audit/acquisition_models.py` | 词汇 | `Route` 与 `publisher_url` 字段适用范围收窄 |
| `src/paper_radar/papers/`（feed/doi/日期字段所在模型） | 事实 | DOI 来源溯源、`online_date`/`print_date` 语义填充 |
| `src/paper_radar/experiment/feed.py`、`experiment/candidates.py` | 实验路径 | 核对实验入口仍限 JGR、不受新策略影响 |
| `src/paper_radar/storage/migrations/versions/<新迁移>` | 迁移 | 若新增 DOI 来源/VOR 标记/parser identity 新值 |
| `src/paper_radar/screening_tasks/language.py` | 策略 | 核对 aies 语言取值来源不变（本裁决不改语言） |
| `src/paper_radar/papers/cli.py` 等只读入口 | CLI 输出 | 若日期语义或身份来源进入展示文本 |

### 测试

| 文件 | 类别 | 大致改什么 |
| --- | --- | --- |
| `tests/test_feed_ingestion.py`、`test_feed_identity.py`、`test_feed_discovery.py`、`test_feed_registration.py` | 单测 | 期刊参数化与 VOR 准入 |
| `tests/test_feed_arbitration.py`、`test_feed_conflicts.py`、`test_feed_inputs.py`、`test_feed_process.py` | 单测 | 身份冲突、来源仲裁与路径派生 DOI 的边界 |
| `tests/test_feed_metadata.py`、`test_feed_metadata_recovery.py`、`test_feed_pipeline.py` | 单测 | aies 路线裁剪、摘要分段、恢复路径 |
| `tests/test_feed_cli.py`、`test_feed_migrations.py` | CLI/迁移 | 新身份与升级路径 |
| `tests/test_feed_language.py` | 语言 | 归属仍由 Feed 决定（核对为主） |
| `tests/test_audit_acquisition*.py`、`test_audit_sampling*.py`、`test_audit_matrix*.py`、`test_audit_reinterpret.py` | 审计 | 移除 aies 出版者路线后的正负例与矩阵边界 |
| `tests/test_fixture_registry.py`、`test_fixture_pdf.py`、`test_fixture_audit_references.py`、`tests/fixtures/a10/sampling-aies.xml`、`tests/fixtures/a10_coverage.json` | fixture | aies 样本、注册表引用与覆盖清单 |
| `tests/test_a10_behavior_coverage.py`、`tests/test_scope_baseline_audit.py` | 覆盖/scope | 成员与计数变化 |
| 新增独立测试模块 | D1 | 新能力的未绑定测试，配合 `docs/verification/` 台账 |

### 登记与门禁

| 文件 | 类别 | 大致改什么 |
| --- | --- | --- |
| `docs/verification/scope-material-inventory.json` | 分类登记 | 本文件、ADR-0072 及改类文档的精确路径登记 |
| `scripts/verification_scope_materials.py` | 中央登记 | 跨组共享材料的新增/计数调整（如触发） |
| `docs/verification/<新覆盖台账>.md` | 证据 | 本裁决的覆盖、验收判据与模块点名数量 |
| `docs/verification/contracts-fixture-audit-history.md` 等历史台账 | 历史 | 不重写；按需在新台账中引用 |

---

## 六、建议实施顺序

1. 写 ADR-0072，同时把「VOR 上线日」的取值细则定死（注意点 4）。
2. 原地改写规格相关小节，并在行内标注出处。
3. 改写六份契约；同步 `GLOSSARY.md`、`README.md`、`docs/roadmap.md`。
4. 代码按 `sources → feed_ingestion → feed_metadata → fixture_audit 收窄` 顺序落地；需要时补迁移。
5. 补测试与覆盖台账；跑相关 pytest 子集。
6. 固定材料登记与 scope 只读审计，按需 S3 确认。
7. 完整离线门禁**仅在用户明确指示时**运行（`./scripts/check-offline`）。

---

## 七、验证建议

- 相关子集：`pytest tests/test_feed_*.py tests/test_audit_*.py tests/test_fixture_*.py`（以实际受改动面为准）。
- 只读：`./scripts/audit-verification-scope --json`（必要时加 `--base/--integration-target`）。
- live 冒烟（不进单测）：四刊 Feed 可达性 + aies 路径推 DOI 抽样核验 + Crossref `from-created-date` 兜底窗口演练。
- 迁移：从上一 revision 升级到当前 head，并覆盖恢复路径。

---

## 八、未验证与开放项

1. **「VOR 上线日」尚未定死取值**（Feed 首次 observed_at / Crossref `published`），需在 ADR 中明确并承认它是发现时刻。
2. **其他三刊的 VOR 判定方法未逐刊实测**；本裁决只对 aies 有实测依据，其余三刊需要各自的判定声明与监测。
3. **Crossref 兜底在限流下的行为**：公共池已观测到 429，需退避与感知策略；礼貌池（`mailto`）连续 12 次为 200，不代表无上限。
4. **未来若要 AOP**：sitemap 与 llms.txt 通道已查清可用，但需重新裁决，不能沿用本次排除结论。
5. **`jcli-overview.xml` 当前 500** 提示同批端点会静默失效，端点监测的告警阈值尚未定义。
