# EXP-1：四刊首轮 HTTP 审计

## 结论与证明范围

依据 [#145](https://github.com/MeteoBoy4/PaperRadar/issues/145)、[规格 §11 B](../../intent/draft.md#阶段-bjgr-feed-第一条真实纵向闭环)及 [fixture-audit](../contracts/fixture-audit.md)。本次为 **2026-11-02 的首轮 HTTP 实测**，不是历史预检、生产 Feed 导入或四刊长期稳定性验收。

| 判断 | 结果 |
| --- | --- |
| `audit run` 退出码 | **0**，只是命令正常返回 |
| 整计划状态 | **partial**：AIES 未冻结 Feed，dqkx 暂停在第 2 位；没有完成计划的 fixture acquired 引用 |
| JGR 固定入口判据 | **5/5，满足**：selected=5，每篇由 Crossref 取得非 `suspected_truncated` 主区块；分母未剔除任何失败成员 |
| Source / B 影响 | 仅解决该轮 JGR 来源入口条件；**不授予 B 整体就绪、生产样本资格、正式校准或完整阶段 A 通过** |
| 首轮责任交接 | [用户已确认](https://github.com/MeteoBoy4/PaperRadar/issues/145#issuecomment-6576278062)保留 partial、不盲目 resume，非 JGR 暂停项交后续实验/C/F；解析修复与新规则实测分开 |

逐篇内容检查由本次**执行代理**完成：显式读取本机保留材料，检查主区块、内容首尾、来源身份及仲裁，并与另一份冻结来源对照；不冒充用户逐篇签阅，也不把机械信号为零称为科学意义的完整性证明。出版者页面 403，无法对照其当前 HTML；这项限制在所有 JGR 成员上保留。

## 冻结条件与身份

- 计划 ID：`b1719ffade06f8ec575d3e64fbe5fc6f3495787278f77ce9689c196a91b34b04`。
- 计划创建：`2026-11-02T11:31:00.323620+00:00`；命令运行：11:30:59.963560–11:31:44.238802 UTC。
- 代码：`bcb3e7de02afccec5d8ace6a41644bcf3ddb8bee`；建计划时工作树 clean，installed / package `0.1.0`。执行前后未修改产品代码、规则或依赖。
- `uv.lock` SHA-256：`11aa458753aad1447061e7b8e5ef3adc74e53db4db98ecd36da5d88e14267512`。
- Python `3.14.4`，SQLite `3.46.1`，Linux `7.0.0-31-generic` / x86_64；完整依赖版本在本机 `preflight.json`。
- 四刊统一 **N=5**；使用规格 §2.1 的四个精确 Feed。按 Feed 原位次、前 50 候选和封闭身份/类别规则，不按日期或摘要成败重排换样。用户明确选择无代理；邮箱仅为临时请求标识，不进入本报告、Issue 或证据文件。
- `resume=0`，无新计划、无追加解释、无其他取得通道。HTTP 使用既有限频、期限、重试与逐跳白名单，未规避 403、跟随 HTTP 降级或伪装客户端。
- 全部冻结版本：`audit-acquisition-v1`、`audit-channels-v1`、`audit-http-v1`、`audit-parser-v1`、`audit-sampling-v1`、`audit-category-v1`、`identified-public-v1`、`audit-abstract-v1`、`audit-truncation-v1`、`audit-matrix-v1`。

本机证据父目录（相对仓库）：`.scratch/exp-1/20261102T113059Z/`，以下称 `$E`。独立数据库 `$E/data/audit.sqlite3`、制品根 `$E/data`、所选根日志 `$E/data/logs/`；未接触生产库。审计锁在数据根外，未作为制品备份。

## 四刊选样与暂停

| 刊 | 冻结候选总数 | 考察 | selected | excluded_deterministic | 选样状态 / 位置 | 最终摘要来源 |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| AIES | 未知，Feed 未冻结 | 0 | 0 | 0 | blocked_pending；next_position=1 | 无成员，不适用 |
| JGR | 18 | 5 | 5 | 0 | complete；原位次 1–5，next_position=6 | registry 5 |
| QJRMS | 127 | 5 | 5 | 0 | complete；原位次 1–5，next_position=6 | registry 4、feed 1（字段误取，见下文） |
| 大气科学（dqkx） | 21 | 2 | 1 | 0 | blocked_pending；第 2 位 / next_position=2 | publisher 1 |

- 无身份/类别冲突，无被确定性排除成员；两个暂停各有原始事件链，不记作排除。未完成刊 shortfall 仍为未知，不虚填 5 或 4。
- JGR 原日期跨度为 `2026-10-30T23:21:22-07:00`–`2026-10-31T11:14:20-07:00`；QJRMS 为 `2026-10-25T17:54:25-07:00`–`2026-10-31T00:31:55-07:00`。dqkx 已选成员为 `2026-01-18`，暂停候选为 `2026-02-11`；保留原顺序，不能称为按日期选择的最新五篇。已选成员无未知日期。
- **AIES**：Feed HTTP **202 / invalid_response**，一次物理请求，无保留正文。未得到 XML，不能断言是挑战页、摘要缺失或历史 AMS403 复现，也不能建立成员摘要覆盖率。
- **dqkx 第 2 位**：`10.3878/j.issn.1006-9895.2512.25120` 的出版者 HTTPS 端点返回 **302 / disallowed_scheme**，未跟随不允许协议，未保留该响应正文。Feed 的 article 依据虽存在，规则仍需出版者类别核查，因此在原位次暂停；不把它剔除或跳至第 3 位。
- dqkx 两次 doiRA 查询均路由到 **ISTIC**，记 `agency_unsupported`；没有强行查询 Crossref。DataCite 在本轮没有适用成员，不记“未尝试的失败”。

冻结整份 Feed payload SHA-256：

| 刊 | SHA-256 |
| --- | --- |
| JGR | `9097d9f76c0a8e77380df187f901fae9959e3bd0c003f14437e84e4ee61ced66` |
| QJRMS | `a7f183bf03cd044b5fd6719ad2b8dc445d1aebb766de2c0b77f3b614a10277e1` |
| dqkx | `d9a3359faa9fad640092be40ff21dd606d5447a20250ebb9fe7f0d2e967fdfdd` |

AIES 无有效 Feed，不虚构 SHA。

## 路线矩阵：策略与通道分开

下表全部为 `audit-acquisition-v1 / http`，**仅以已选成员为分母**；选样期间 AIES Feed 和 dqkx 第 2 位失败另见上一节，不用缺失成员伪造矩阵行。完整 54 行矩阵、49 个执行及选样历史见 `$E/receipts/02-audit-run-result.json`。

| 刊 / 路线 | 适用 | 尝试 | 未尝试 | 有效记录 | 非空摘要 | 疑似截断 | 错误 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| JGR / Feed | 5 | 5 | 0 | 5 | 5 | 5 | 0 |
| JGR / doiRA | 5 | 5 | 0 | 0 | 不适用 | 不适用 | 0 |
| JGR / Crossref | 5 | 5 | 0 | 5 | 5 | 0 | 0 |
| JGR / publisher | 5 | 5 | 0 | 0 | 0 | 0 | 5 |
| QJRMS / Feed | 5 | 5 | 0 | 5 | 5 | 5 | 0 |
| QJRMS / doiRA | 5 | 5 | 0 | 0 | 不适用 | 不适用 | 0 |
| QJRMS / Crossref | 5 | 5 | 0 | 5 | 4 | 0 | 0 |
| QJRMS / publisher | 5 | 5 | 0 | 0 | 0 | 0 | 5 |
| dqkx / Feed | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| dqkx / doiRA | 1 | 1 | 0 | 0 | 不适用 | 不适用 | 0 |
| dqkx / publisher | 1 | 1 | 0 | 1 | 1 | 0 | 0 |

- Feed 的“非空摘要/截断”列忠实保留 **v1 机械解释**，不等于科学主摘要命中；Wiley 两刊的字段误取不能被这张表掩盖。
- doiRA 只作机构路由，摘要分母恒为 0 / 不适用；其有效记录列为 0 不表示请求失败。
- Wiley 两刊 publisher/http 均为 **403 / access_blocked_403**，没有来源快照；不能由此推断论文不是 OA，也未新增通道规避。
- QJRMS `10.1002/qj.70349` 的 Crossref 为有效身份记录但 `record_without_abstract`；不是网络或身份失败。最终落到错误的 Feed 书目信息候选，应按下文缺陷处理，不能称其有可用主摘要。
- dqkx 第 1 位 `10.3878/j.issn.1006-9895.2601.25109`：Feed 无主摘要；出版者只取 **abstract-cn**，560 code point，无机械截断信号。已检查中文主区块；英文摘要只记录存在与定位 `html/node[359]`，没有拼入主摘要。
- `browser_render`：JGR/QJRMS/dqkx 分别适用 **5/5/1**，尝试 0，均 `channel_not_installed`；不是 HTTP 失败，不给 0/N 摘要成功率。AIES 无成员、无虚构适用行。
- `official_api`、`repository`：四刊均 0 适用、执行器未交付，摘要分母不适用。
- 全计划 **39 次物理 HTTP 请求、0 次重定向跟随、1 次内部重试、0 个未知执行**；不能将共享 Feed 请求按成员重复计数，或把未安装通道计成 HTTP 请求。

## JGR 逐成员核查

每个成员都在原位次 1–5，以 Crossref `message.type=journal-article` 选中；doiRA 路由到 Crossref，显式 DOI 身份一致。五个 `message.abstract` 均有唯一 `jats:title=Abstract` 和闭合主段落，代理逐篇阅读确认叙述从研究问题/方法延续到结果/结论，未见突兀截断；原上下标、数学比较与格式空白不改写。

| 原位次 / DOI | member ID 前 12 位 | 主摘要 code point | 机械信号 | 最终来源 | 逐篇内容检查要点 |
| --- | --- | ---: | --- | --- | --- |
| 1 / `10.1029/2025jd045292` | `57df08c8fd67` | 1700 | 无 | registry | 采煤甲烷、InSAR/卫星方法、观测结果与监测结论连续 |
| 2 / `10.1029/2026jd048366` | `e11394d3d306` | 1183 | 无 | registry | 生物质燃烧外场、气溶胶/臭氧结果与污染解释连续 |
| 3 / `10.1029/2026jd047220` | `e0e75e8042aa` | 1798 | 无 | registry | 寒潮边界层通量、机载 wavelet 方法、尺度结果与模式启示连续 |
| 4 / `10.1029/2026jd047130` | `0dfb4d2c050c` | 1647 | 无 | registry | SAL/GDI、再分析方法、时空结果与应用结论连续 |
| 5 / `10.1029/2026jd047703` | `a3d9f55ec539` | 1579 | 无 | registry | 北极混合相云、MOSAiC 观测、微物理结果与维持机制连续 |

每篇证据链的原材料和最终规范文本哈希如下；完整 member/candidate/row/acquisition ID、定位、冻结 Feed 对照及逐篇限制在 `$E/inspection.json`。12 位仅作显示缩写，不代替真实身份。

| 原位次 | Crossref payload SHA-256 | 规范主摘要 text SHA-256 |
| --- | --- | --- |
| 1 | `981476668a0bac25897b19b8ed7eceabf31957c0f877f9ad945255453c7ab4e0` | `c4a5ed234770831d214257f3705b8da813a2a93a65d075b47f728f0c63b2c693` |
| 2 | `23ae51a1e72e6ccd05069c9f72b03d062c4e5ba8ca4e6e8f6f1519f90294167f` | `a5d1a996c2eb0266241fba45e8e3faa17597548dcb1a123097bc767a6d838b28` |
| 3 | `d06ed1e162b76e620a290e018eada2e74eeec9885477106de63c282812c34c8a` | `4cef2d7e8b85ff1c71518305cca18c63b78ae278bd4687b8b30e1550827ac009` |
| 4 | `20633cd914c26b222becbe2e3d6b33a68d0f026ba151608ce767af489a28208c` | `03dbd68a071a1762781abe27c1f88e4026c76847fd2baa23904820f95f99af55` |
| 5 | `69b10c620267b74864b63719dc78c449933be75e29cce139fe2d7b656db1bd87` | `fb6ba956f3237558aee514c6fd994cef2ebfccaf5d8326f73cee804337d5675a` |

附加标签检查及来源仲裁：

- 这五篇已取得的 Crossref 主区块及 Feed `content:encoded` 未发现 PLS、Key Points 或 Significance Statement 标签；只表示这些材料未见，不推断受阻的出版者页面没有附加区块。
- 独立检查 Feed `content:encoded` 的 `h2 Abstract` 主段落，与各篇 Crossref 主摘要在**仅用于检查**的去空白/排版横线及引号等价化后逐篇相等。未将这项对照变成新的审计解释、截断规则或候选，不改变规范文本及哈希。
- 五篇最终来源都为 registry，原始仲裁选择了同一 Crossref 摘要候选；没有为获得长摘要而更改来源优先级，priority_truncation_conflicts=0。出版者失败/未安装仍完整保留。

因此 selected=5、满足数=5，**本轮不触发 DEC-2**。若后续改变规则或样本，仍须有适用证据，不得把本次通过外推为永久豁免。

## 解析缺口与生产路径适用性

### Wiley Feed 的字段误取

JGR 每个原始 item 同时含非命名空间 `description`、`dc:description`、`content:encoded`；前者是同一卷期说明，后两者含文章 Abstract。v1 首先选择前者，导致五条“摘要”都是同一 85 字符书目信息，SHA-256 `e4f1c5c20d6f551f2b76d9251153edca700377f5ab0acc47195154c410a5e2c3`，命中 `short_under_100`。QJRMS 也观察到同类误取。

这是**解析/字段选择缺口**，不能写成来源没有提供主摘要；本轮保持错误解释原样，未修代码或覆盖矩阵。修复见 [#146](https://github.com/MeteoBoy4/PaperRadar/issues/146)，新规则实测见 [#147](https://github.com/MeteoBoy4/PaperRadar/issues/147)。不得将 QJRMS 那一篇最终 Feed 候选当作正常主摘要，亦不允许通过“足够长”替代正向主区块识别。

### 生产路径适用性

- `feed_metadata/service.py` 直接复用 `SourceHTTPExecutor`、`inspect_source`、`parse_material`；Crossref 的主区块与截断规则仍为本轮冻结版本。[生产契约](../contracts/feed-metadata.md)与审计使用同一规则，不是本轮另造一套解析器。
- `feed_ingestion/parser.py::parse_items` 同样调用该解析器，并传入已验证物理 item；RSS 字段误取也影响生产 Feed fallback。共享解析不等于所有候选接收、来源仲裁及资格判断已在真实生产接线通过。
- 当前来源判据由 **Crossref 五篇**满足，不依赖错误 Feed 文本。B 仍须经生产路径真实取得完整主摘要、核实规范获选候选/来源与字段差异，不能复制审计材料或把卷期说明当主摘要。
- #146 若改变解析语义，必须保留历史 v1 并明确新版本，补差异审查/新计划。当前 `reinterpret_audit` 只接受 complete 计划，**不能对本 partial 计划直接追加解释**；修复交付与 #147 新计划不改写本轮事实。

## 回放、备份与本机证据索引

下列命令均统一通过 `uv run --offline --locked …`。live 命令里的联系标识仅临时传参；持久回执只保存占位符。回放/备份/恢复通过同一 CLI main 在 Python socket `connect/connect_ex/create_connection/getaddrinfo` 拒绝守卫下执行，**网络尝试 0**；不是主机级网络沙箱或 NAS 证明。

```bash
uv run --offline --locked paper-radar db upgrade --database "$E/data/audit.sqlite3"
uv run --offline --locked paper-radar audit run --database "$E/data/audit.sqlite3" \
  --data-root "$E/data" --contact-email <临时标识> --count 5 --json
uv run --offline --locked paper-radar audit replay PLAN_ID \
  --database "$E/data/audit.sqlite3" --data-root "$E/data" --json
uv run --offline --locked paper-radar backup create --database "$E/data/audit.sqlite3" \
  --data-root "$E/data" --output "$E/backups"
uv run --offline --locked paper-radar backup verify "$E/backups/20261102T113329Z-31d08821"
uv run --offline --locked paper-radar restore verify "$E/backups/20261102T113329Z-31d08821" \
  --target "$E/recovery/restored"
uv run --offline --locked paper-radar audit replay PLAN_ID \
  --database "$E/recovery/restored/database.sqlite3" --data-root "$E/recovery/restored" --json
```

以上实际命令全部退出 **0**。恢复时将原 `data/` 暂移至 `data.offline-source/`，确认原位置不存在；恢复只依赖批次，未升级、继续或登记任务，最后恢复原目录名。原/恢复成员、矩阵、规范解释、汇总及逐执行证明完全相等。

| 证据 | 相对 `$E` 的位置 / 身份 |
| --- | --- |
| 环境与依赖锁 | `preflight.json` |
| 原始安全输出、命令/退出码 | `receipts/01-db-upgrade.json`、`02-audit-run{,-result}.json` |
| 源材料/业务事实 | `data/audit.sqlite3`、`data/blobs/`；允许保留的 14 个 source_snapshot、1,547,322 字节 |
| 所选根运行日志 | `data/logs/`；仅安全事件，非权威事实，产品 backup 不包含日志 |
| 主区块与逐篇检查 | `inspection.json`；SHA-256 `b944f99b6cd85776841aae7a613ceeaa77d5a85c92bf8d7223672d13728d65f8` |
| 原/恢复回放与比较 | `receipts/03-audit-replay{,-result}.json`、`07-restored-replay{,-result}.json`、`08-recovery-comparison.json` |
| portable semantic SHA-256 | `257965f98447d368dcc402af5e217440d04a41e8de8bba933f6d5f395b9f1ba9`（原/恢复相同） |
| 产品自包含备份 | `backups/20261102T113329Z-31d08821/`，完整 SQLite 与制品闭包 |
| 备份 manifest SHA-256 | `3a56a01cd320adacfc7d783f40eceebca460dcb4c4b7d37de2f3853a74f52857` |
| 阶段检查点 | `checkpoint.md`、`evidence-sha256.json`（首次暂停时快照，保留原字节，不是最终判定） |
| 移交依据 | `handoff-confirmation.md` 及 [Issue 确认](https://github.com/MeteoBoy4/PaperRadar/issues/145#issuecomment-6576278062) |

失败/挑战/身份未核验页不保留正文；doiRA 只有结构化机构事实。回放证明按 `material_reparsed` 与 `execution_facts_only` 分开，不能声称逐字重现 403/202/302 页面。**partial 无 acquired 完成引用，未登记假汇总或覆盖 historical 声明**；完成计划 fixture 登记由后续实测负责。

### 附属材料的备份

产品批次不含日志和实验回执。本机额外权威归档覆盖该批次、环境身份、首轮回执、检查依据及所选根安全日志；归档与内部逐文件 SHA 索引留在本机，不进入 Git。

- `$E/authority-package.tar.gz`：SHA-256 `4e5a595a802f9dafa567ce0654d42b23e0883de451f224565831e130f4e01106`。
- `$E/authority-manifest.json`：SHA-256 `95910ce2a0f9bcd5818dcd5863ebb833b9ec4d2f155a80e3ad74928e20de6587`；归档含清单及其列出的 33 个文件，共 34 个文件，已重新读取归档并逐个核对长度及 SHA-256。
- `$E/receipts/11-authority-package.json` 记录打包与验证结果。审计锁、日志锁、活动库 WAL/SHM 不作为归档成员；产品备份内的独立 SQLite 承担可恢复业务事实。

本机同盘归档不是异机/NAS 备份；Hash 证明字节身份，不提供签名或来源认证。

## 后续责任与边界

- **Audit / Source**：首轮已得到可追溯结论，非 JGR 暂停已获明确移交；保留原 partial，不用模块任务完成冒充数据库计划 complete。JGR 来源条件满足，不新增降级裁决。
- **#146（工程）**：修复字段选择、设计语义版本与 v1 历史回放保护，审计与生产消费者共同回归；不在本次实验临时修改规则。
- **#147（HITL，原生 blocked-by #146）/ C / F**：在新代码/规则身份下用新计划补跑；承接 AIES 202、dqkx 第 2 位协议重定向、Wiley 403 与 QJRMS 缺摘要，分开报告根因。不得为推进而放宽 HTTPS 或新增未交付通道。完成新计划再登记 acquired fixture，保存原轮关联。
- **B**：生产路径完整主摘要、字段/规则差异、真实样本与其他入口条件仍须独立验收；Pi/Cwd/Live、Docling/Body、Profile/模型、隔离根等均未因本轮通过自动就绪。
- **C / F / Abstract / D**：四刊长期稳定证据、DEC-1 阈值与是否一律非截断、降级及披露仍保留，最迟 D 正式预热冻结/首批校准前逐刊收口；DEC-3 附加区块消费语义仍由用户另行裁决。
- 未运行 Screening、Pi/RPC/模型、Docling、PDF/Read、生产 Feed 导入、NAS 或完整离线门禁。仅实验与文档工作，无产品代码/测试或既有固定材料变更，不把原历史离线回执改成完整阶段 A 通过。

## 文档验证

- `git diff --check` 通过；新增报告另作行尾空白、引用和证据哈希核对。
- `./scripts/audit-verification-scope --base bcb3e7de02afccec5d8ace6a41644bcf3ddb8bee --integration-target main --json` 在改动前后均退出 0，`issues=[]`、`affected_groups=[]`；不请求收集，不调整测试分母、绑定或 required 集合。回执保存在本机 `receipts/09-scope-before.json`、`12-scope-final.json`。
- 本次不修代码，不运行 pytest 或完整离线门禁；回放、恢复与文档检查不构成当前树的正式离线验收。
