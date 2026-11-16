# #185 收口后的文档归属与现状维护

按 `docs/agents/documentation.md`、`docs/agents/roadmap.md` 与固定范围集成规则检查。
基线为 `e11ffb07dbbc0eb055927d7f637f84a4eb9e1704`。所有者提供的该提交完整门禁
已只读核验为 passed/verified/same，六检查通过、固定 5281 测试通过，无 skip/deselect。
具体 run_id、终态与运行身份保存在树外交付记录，不回写冻结材料。

## 归属与修订

- 路线图：GitHub 原生 sub-issue 与 blocked-by 完整计数核对后，#185、#206 和全部
  21 张子票均为 CLOSED。移除已完成 B 事项的待办叙述、旧会期准备及已完成工程的
  并行安排；保留全部模块 ID、依赖、DEC/EXP 和历史索引。C 仍由模块表记录，
  不因 B 完成自动变为可规格化。后续责任按 C/D/E/F/G/H/I 汇总，受限样本、
  可选 Live、正式校准、四刊质量和 NAS 的范围继续分开。
- README：补齐显式 Read、报告、暴露导出和隔离回放导航；真实链、版式与恢复分别
  链接原签收，不扩张原结论；补充 r1/r2 独立工程覆盖入口。细则仍由 Contract 拥有。
- 现状 Contract：Live 源码守卫同步既有代码的 v29/275 文件，旧向量保留；报告契约
  去除票务过程措辞，将暴露读面归入规则；日志契约描述现有实验接线。
- 规格：去除“本票离线通过”的过程措辞，把配置段限定 normalization v1 的旧表述
  改为版本化 normalization；已有 v1/v2 行为、语义身份和历史回放规则不变。
- GLOSSARY、已接受 ADR、现有覆盖／验收台账、历史 JSON、原始审查报告和 vendored
  skills 均保留原字节；本次没有新需求、决策、术语、Schema 或版本语义，无新增 ADR。

## 链接与历史例外

对基线 483 份非 vendored Markdown 扫描本地路径和锚点，并以 CommonMark 解析器
复核真实链接；35 份显式活文档无断链，锚点核对无新增失配。
历史文档有 15 处旧路径引用，另有一处被忽略的本机回执在独立 worktree 中缺失，按[统一迁移的原字节保留边界](../../docs/verification/doc-unification-ledger.md#基线与范围)
和[固定材料规则](../../docs/agents/verification-scope.md#材料与证明边界)保留原件，不伪造历史回执：

| 历史原件 | 次数 | 现行去向或限制 |
| --- | ---: | --- |
| [daily-paper-reader 调研](../archived_discussions/daily-paper-reader.md)中的 `./draft.md` | 2 | 现行规格为 [intent/draft.md](../draft.md) |
| [AIHOT 调研](../discussions/research-aihot-v1-lessons.md)中的 `../docs/adr/…` | 12 | 相对层级应多上一级；决策原件仍在 [docs/adr/](../../docs/adr/) |
| [Pi 文档审阅](pi-agent-v1-document-consistency-review.md)中的 `CONTEXT.md` | 1 | 已更名为 [GLOSSARY.md](../../GLOSSARY.md)，维护规则保留此历史映射 |
| [#61 审阅](issue-61-receipt-isolation-process-group-review.md)指向的本机历史运行 JSON | 1 | 主工作区有该被忽略文件，独立 worktree 不携带；这是本机材料可用性差异，不计入仓库路径断链，也不由文档引用推定该运行已核验 |

首轮正则扫描识别前 15 处；标准解析补出最后一处带代码格式标签的历史回执链接。
核对主工作区与独立 worktree 的差异后，将该本机材料单列。全部引用来自原字节保持的
非活文档，不是本次修订引入；没有补写、重建或解析该历史回执。

## 验证与边界

- `test_live_document_links.py` 与 `test_a10_document_obligations.py`：21 passed。
- `test_scope_material_inventory.py` 与 `test_scope_document_guards.py`：31 passed。
- scope 只读审计：1216 项材料全匹配，无问题；固定分母和登记不改写。
- 比较基线全部 Markdown 摘要，448 份非活文档原字节保持；代码、测试、migration、
  配置／Prompt、fixture、lockfile 和已发布证据均无变更。
- 规格与路线图标题保持，19 个模块 ID 不变；D7 实际 275 个源成员摘要逐一匹配。
- README 新命令导航核对现有 CLI 帮助；差分空白检查通过。

全部 Python 检查使用独立 worktree 环境及 `uv run --offline --locked`，临时材料和
原始输出仅在树外 `/tmp/paperradar-185-doc-maintenance/`。本次未执行完整门禁或 live，
没有访问真实实验根、研究材料或凭据，没有变更 GitHub 状态、启动下一模块或推送代码。
文档修订后，基线门禁仍为历史 passed/verified，适用性为 different；该结果不替代
新文档树的完整门禁结论，也不改变原真实链／恢复签收的证明范围。
