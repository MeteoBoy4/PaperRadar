# EXP-1：新规则 HTTP 补跑与 B 来源交接（#147）

## 结论与用户确认

依据 [#147](https://github.com/MeteoBoy4/PaperRadar/issues/147)、[已交付 v2 规则](issue-146-wiley-abstract-v2.md)、[审阅修复](issue-146-review-followup.md)、[规格 §11 B](../../intent/draft.md#阶段-bjgr-feed-第一条真实纵向闭环)及 [fixture-audit](../contracts/fixture-audit.md)。这是 **2026-11-02 的独立新计划**，不覆盖[首轮 v1 报告](exp-1-http-audit.md)。

| 判断 | 本轮结果 |
| --- | --- |
| v2 服务运行 | 正常返回，退出 0；整计划仍 **partial**，不是四刊通过 |
| JGR 冻结来源判据 | 本轮 selected=5，5/5 均有非疑似截断主摘要；Feed 与 Crossref 分别 5/5，最终来源 registry 5 |
| Wiley 字段修复的 live 证据 | 主摘要来自带 Abstract 标记的 `content:encoded`，不再取卷期说明；QJRMS 缺摘要成员仍留在 5 篇分母中 |
| 非 JGR 暂停 | AIES 未冻结、next_position=1；dqkx 暂停第 2 位；用户确认本轮不再处理，后续阶段遇到时另拟方案 |
| fixture 引用 | partial，**未登记 acquired 完成引用**，没有将其伪装成 complete |
| B 的影响 | 具备该轮 v2 JGR 来源证据；不替代 B 自己的生产路径完整主摘要、样本与其他入口验收 |

[用户确认与移交](https://github.com/MeteoBoy4/PaperRadar/issues/147#issuecomment-6579024650)：执行前明确无代理直连、四刊 N=5、当前提交新建独立库/制品根；重现暂停后确认「AIES / 大气科学 先不管了，到后续阶段碰上了再另寻方案，先向着阶段B前进，其他都同意」。因此本轮停止后续 live、resume=0；不降低 HTTPS/逐跳白名单，不另开通道，不取消后续四刊正式校准前置。

## 身份、入口与隔离

- 新计划：`82d952ffd52ca9a88982c0cae8f37f460138116e5d54fe436775baa81d2db8cd`。
- 关联原计划：`b1719ffade06f8ec575d3e64fbe5fc6f3495787278f77ce9689c196a91b34b04`；没有续跑、迁移或改写原库。
- 执行代码：`ff811705a4e7a156b36edcca4ea994ef2494168c`，建计划时 clean，`basis=installed`、package `0.1.0`。
- 计划创建：`2026-11-02T13:50:17.766897+00:00`；服务运行 13:50:17.757298–13:51:12.163613 UTC。
- `uv.lock` SHA-256：`11aa458753aad1447061e7b8e5ef3adc74e53db4db98ecd36da5d88e14267512`；Python `3.14.4`、SQLite `3.46.1`；完整平台/依赖身份保存在本机 `preflight.json`。
- 只有 `abstract_rules_version=audit-abstract-v2` 升级；其余冻结版本为 `audit-acquisition-v1`、`audit-channels-v1`、`audit-http-v1`、`audit-parser-v1`、`audit-sampling-v1`、`audit-category-v1`、`identified-public-v1`、`audit-truncation-v1`、`audit-matrix-v1`。Feed 结构 parser v1 与主摘要 v2 是不同身份，不混写。
- CLI 仍默认 v1，实际使用已交付 `FixtureAudit.run_audit(abstract_rules_version="audit-abstract-v2", target_count=5, contact_email=...)`；显式注入 `SourceHTTPExecutor(proxy=None)` 与 `FileSink(data_root)`。邮箱只瞬时用于请求标识，不进入本报告、Issue 或本机制品。
- 本机根 `$E=.scratch/exp-1/20261102T134907Z`，数据库 `$E/data/audit.sqlite3`、制品 `$E/data/blobs/`、安全日志 `$E/data/logs/`；没有接触生产库。所有 Python 执行均为 `uv run --offline --locked …`。
- 初始化第一次 `db upgrade` 因独立父目录尚不存在退出 2，尚未创建计划或请求来源；保留失败回执，创建父目录后升级退出 0。没有用失败重试替换 live 计划。

## 固定选样、重叠与暂停

使用规格 §2.1 的四个精确 Feed、同一原位次前 50 规则与封闭身份/类别依据；不按日期、摘要结果或题名换样。没有确定性排除或类别冲突。

| 刊 | 冻结候选 | 考察 | selected | 状态 / next_position | 日期跨度 |
| --- | ---: | ---: | ---: | --- | --- |
| AIES | 未知 | 0 | 0 | blocked_pending / 1；Feed 未冻结 | 不适用 |
| JGR | 19 | 5 | 5 | complete / 6 | 2026-10-30T23:34:28-07:00 至 2026-11-01T20:15:55-08:00 |
| QJRMS | 127 | 5 | 5 | complete / 6 | 2026-10-25T17:54:25-07:00 至 2026-10-31T00:31:55-07:00 |
| dqkx | 21 | 2 | 1 | blocked_pending / 2 | 已选成员 2026-01-18 |

已选成员均有日期。两个受阻刊 shortfall 为未知，不用缺失成员伪造矩阵或 0/5 覆盖率。

- **AIES**：固定 Feed 一次请求 **HTTP 202 / invalid_response**。没有有效 XML、快照或候选；只证明本端点本次返回该状态，不推断验证码、挑战或历史 AMS403。未保存失败正文，未请求其他端点。
- **dqkx 第 2 位**：`10.3878/j.issn.1006-9895.2512.25120` 出版者仍为 **HTTP 302 / disallowed_scheme**。没有跟随不允许协议、静默升级目标或跳过此位；两次 doiRA 均为 ISTIC / agency_unsupported，没有强查 Crossref。
- **JGR 重叠**：本轮与首轮重叠 4 个 DOI，新增 `10.1029/2026jd046774`；原轮 `10.1029/2026jd047703` 现在位于本轮 Feed 第 6 位，未入本轮 N=5，不是因摘要结果剔除。两轮各自分母为 5，不能称为 10 篇独立成功样本或跨轮稳定率。
- QJRMS 本轮 Feed SHA 与首轮相同；重复取得不是新增独立论文或长期稳定性分母。dqkx 保持 RDF Seq 顺序，不能称按日期排序选样。

| 刊 | 本轮整份 Feed payload SHA-256 |
| --- | --- |
| JGR | `c9df425090a9baa5115b7db799c12f239754a98d853481505f1fbb8c22db3288` |
| QJRMS | `a7f183bf03cd044b5fd6719ad2b8dc445d1aebb766de2c0b77f3b614a10277e1` |
| dqkx | `ee0ab6dd73d05a6b374e5cb3c2a3a6e0a72d12db7276c3ffb13e5aa11f231abd` |

AIES 没有有效 Feed，不填假哈希。

## 路线矩阵与逐成员核查

以下全部属于 `audit-acquisition-v1 / http`，只以本轮已选成员为分母。每行适用数=尝试数；没有已交付未尝试路线。选样期的 AIES 和 dqkx 第 2 位失败另列，不从分母中抹去。

| 刊 / 路线 | 适用/尝试 | 有效记录 | 非空主摘要 | 疑似截断 | 错误 |
| --- | ---: | ---: | ---: | ---: | ---: |
| JGR / Feed | 5 | 5 | 5 | 0 | 0 |
| JGR / doiRA | 5 | 0 | 不适用 | 不适用 | 0 |
| JGR / Crossref | 5 | 5 | 5 | 0 | 0 |
| JGR / publisher | 5 | 0 | 0 | 0 | 5 |
| QJRMS / Feed | 5 | 5 | 4 | 0 | 0 |
| QJRMS / doiRA | 5 | 0 | 不适用 | 不适用 | 0 |
| QJRMS / Crossref | 5 | 5 | 4 | 0 | 0 |
| QJRMS / publisher | 5 | 0 | 0 | 0 | 5 |
| dqkx / Feed | 1 | 1 | 0 | 0 | 0 |
| dqkx / doiRA | 1 | 0 | 不适用 | 不适用 | 0 |
| dqkx / publisher | 1 | 1 | 1 | 0 | 0 |

- Wiley 出版者 10/10 均为 403 / access_blocked_403；没有保存失败正文，不由 403 推断非 OA。
- doiRA 仅路由，不作为摘要提供方；Crossref/DataCite 仅按机构适用性查询，本轮无 DataCite 成员。
- `browser_render` 在 JGR/QJRMS/dqkx 各有 5/5/1 个适用成员，全部 channel_not_installed、尝试 0，不记 HTTP 失败或 0/N 成功率。official_api/repository 均无适用成员、执行器未交付。
- 全计划 49 个执行、54 行当前矩阵，**38 次物理请求、0 重定向跟随、0 内部重试、0 未知执行**。共享 Feed 请求不按成员重复计数。

下表长度单位是规范文本 Unicode code point。所有非空主摘要均无机械截断信号；“缺”是 record_without_abstract，不是网络错误，仍计入原分母。

| 刊 / 原位次 / DOI | Feed | Crossref | 出版者 | 最终来源 |
| --- | ---: | ---: | --- | --- |
| JGR 1 / `10.1029/2026jd046774` | 1445 | 1445 | 403 | registry |
| JGR 2 / `10.1029/2025jd045292` | 1410 | 1700 | 403 | registry |
| JGR 3 / `10.1029/2026jd048366` | 1142 | 1183 | 403 | registry |
| JGR 4 / `10.1029/2026jd047220` | 1673 | 1798 | 403 | registry |
| JGR 5 / `10.1029/2026jd047130` | 1647 | 1647 | 403 | registry |
| QJRMS 1 / `10.1002/qj.70311` | 1510 | 1552 | 403 | registry |
| QJRMS 2 / `10.1002/qj.70338` | 2059 | 2100 | 403 | registry |
| QJRMS 3 / `10.1002/qj.70347` | 1795 | 1795 | 403 | registry |
| QJRMS 4 / `10.1002/qj.70349` | 缺 | 缺 | 403 | 无 |
| QJRMS 5 / `10.1002/qj.70335` | 2196 | 2236 | 403 | registry |
| dqkx 1 / `10.3878/j.issn.1006-9895.2601.25109` | 缺 | 不适用（ISTIC） | 560 | publisher |

执行代理通过显式 `read_audit_text` 读取全部 41 个题名/摘要候选，核对实际文本哈希与长度；逐篇阅读 10 个最终主摘要，检查从研究问题/方法到结果/结论的连贯性，不冒充用户签阅或科学完整性证明。JGR 新成员为台风多尺度雷达微物理研究；其余四篇分别为采煤甲烷、开放生物质燃烧、寒潮边界层通量、SAL/GDI，均有闭合主区块，满足本轮 JGR 固定入口判据。

- 九篇同时有 Feed/Crossref 摘要的成员，其主文本在**仅用于检查**的去空白/排版横线与引号等价化后逐篇一致；原上下标空白、数学比较、规范文本与哈希不改写，也不追加新解释。出版者均受阻，不能与其当前 HTML 对照。
- QJRMS 第 4 位的 Crossref DOI 一致、type=journal-article，但没有 abstract；Feed 同样没有可识别主摘要。v2 正确保持缺项，不把旧 v1 的 65 字符卷期说明当主摘要。其他四篇 Feed 的 Abstract 前置段单列排除，不与主摘要拼接。
- dqkx 只读 abstract-cn，560 code point；abstract-en 仅记录存在与定位 `html/node[359]`，不拼接。没有消费 PLS/Key Points/Significance；已取得 Wiley 主材料未记录这些标签，不推断受阻页面也不存在。
- 最终来源继续按既有优先级仲裁，未按长度/截断信号改选；priority_truncation_conflicts=0。JGR 五篇最终都为 Crossref，Feed 成功不放大其成员分母。

## 回放、独立脱网恢复与本机证据

本轮离线操作使用已交付公共服务 `FixtureAudit.replay_audit`、`create_backup`、`verify_backup`、`restore_backup`，由 `$E/offline_phase.py` 串行调用。全过程在 socket `connect/connect_ex/create_connection/getaddrinfo` 拒绝守卫内，**网络尝试 0**；这是 Python 进程内拒绝，不是主机级网络沙箱或 NAS 验收。

先从原库回放并逐候选核对文本，再创建/核验自包含批次；将 `$E/data` 暂移至 `data.offline-source`，确认原路径不存在后，只依赖备份恢复到 `$E/recovery/restored`。恢复没有迁移、resume 或登记任务，最后恢复原目录名。

- 原/恢复完整 AuditReplay（包括计划、执行、选样历史、成员、全部矩阵/候选、来源仲裁、汇总及逐执行证明）相等；41 个候选实际文本逐个相等。
- 15 个恢复文件（SQLite + 14 个 blob）与备份逐文件哈希相等且 inode 独立，不靠硬链接。
- `material_reparsed=14`，`execution_facts_only=35`，未知执行 0。失败、doiRA 路由及未安装通道只能回放结构化事实，不能逐字重现失败页面。
- 原 v1 材料另经已交付 `scripts.compare_wiley_abstracts --check docs/verification/issue-146-field-diff.json` 只读复算，退出 0，原 semantic SHA 与旧差异报告保持；没有对 partial 计划绕过 complete 前置。

| 本机证据（相对 `$E`） | 身份 / 内容 |
| --- | --- |
| `preflight.json`、`experiment.py` | 代码、依赖、规则/策略、直接联网入口；无联系标识值 |
| `receipts/02-audit-run{,-result}.json` | 运行/退出码与完整安全事实 |
| `inspection-safe.json` | 全成员/路线/定位/摘要哈希/长度/截断/仲裁；SHA-256 `4bb57fe089746243a4e3b7e28a6198f8b33d46c05901826b052cb5bd5b9a27bd` |
| `content-inspection.json` | 逐篇内容检查与跨来源对照；SHA-256 `4b396c738c40c04075576d9b1b8bdf4e8348737f8d5be4297e89537a5d96e022` |
| `receipts/03-audit-replay-result.json`、`07-restored-replay-result.json` | 完整原/恢复回放；共同 semantic SHA-256 `b92b1627766775121d142c395fe97e027f428c02289006586a9c24521656cc6a` |
| `receipts/04`–`08` 对应 JSON | 备份、核验、恢复及完整事实比较；比较文件 SHA-256 `d11b00f4160cacc7970e692dd6a399cf14563957ba7d703027cbceb91c5eb1b1` |
| `backups/20261102T135714Z-2ca73958/` | 14 个 source_snapshot，共 1,547,213 字节；独立完整数据库与 blob 闭包 |
| 该批次 `manifest.json` | SHA-256 `aaf717b1026459453f27b5c64145dca42f64092c7c224c8da79608e1f45e28d3` |
| `user-confirmation.md` | 用户确认与后续责任；首次暂停 `checkpoint.md` 保持原字节 |

真实来源字节和完整摘要仅在本机制品中，不上传 Git/Issue。产品备份不含日志/实验脚本；这些附属证据另作本机权威归档，清单与归档哈希记录于 `$E/receipts/11-authority-package.json`。同盘归档不等于 NAS/异机备份，哈希不提供签名或来源认证。

## B 前进方向与后续责任

- **本轮来源工作**：按用户确认停止 AIES/dqkx 探测，保留两个计划的 partial、全部成员/失败和各自暂停位置；不再盲目 resume，不伪造 fixture 引用。
- **B / Body**：若选择 v2，可消费本轮规则身份、JGR 5/5 来源证据及[旧材料差异审查](issue-146-review-followup.md#可复算的保留材料诊断)。仍须在 B 自己的受限实验根经真实生产路径取得完整主摘要、核实字段/entry/语言事实、人工预选当轮样本并冻结；不能复制审计成功充当生产成功。CLI/FeedPipeline.prepare 默认 v1，选择 v2 必须显式使用相应服务版本，不能默认为已切换。
- **B 的其余前置**：Cwd/Live（EXP-2）的固定 Pi 1.4.0 与现场隔离/RPC 实测、Extra（EXP-3，实验票 [#148](https://github.com/MeteoBoy4/PaperRadar/issues/148)）的 Docling 兼容/供给，以及 Body 的生产正文/最小 Read、EXP-6/EXP-7、Profile/模型/合法 PDF 等仍独立承接；本票不使 B 自动进入可规格化前沿。
- **C/F/Abstract**：后续消费遇到 AIES 202、dqkx 第 2 位协议重定向、Wiley 403 和 QJRMS 第 4 位缺摘要时，按当时已交付能力另拟方案；改变策略/通道须新版本/计划，不临时放宽安全规则。完成适用计划后才登记 acquired 引用；最迟 D 正式预热冻结/首批校准前逐刊收口。
- **DEC-1/DEC-3 与 D**：四刊稳定阈值、是否一律非截断、降级披露和附加区块消费语义仍待用户另行裁决；本轮不授予四刊稳定、D 正式校准、自动精读或完整 A 通过。

## 验证边界

本次仅本机实验、验证和文档交接，没有改产品代码、测试、依赖、固定材料登记或既有报告；没有运行 Screening、Pi/RPC/外部模型、生产 Feed 导入、Docling、PDF/Read 或 NAS。没有用户完整门禁指令，未运行完整离线门禁。

文档收尾：`git diff --check` 通过；新报告/路线图 165 个相对链接目标及行尾检查通过；`uv run --offline --locked pytest tests/test_live_document_links.py -q` 为 **4 passed**；`audit-verification-scope --base ff811705a4e7a156b36edcca4ea994ef2494168c --integration-target main --json` 退出 0、`issues=[]`、`affected_groups=[]`。原始安全输出在本机回执保留，不把开发检查改称正式离线验收。
