# Screening 只消费主摘要区块，附加区块只保留存在与定位

状态：已接受；日期：2026-11-17；依据：所有者对路线图 DEC-3（附加摘要区块消费语义）的裁决。补充 [ADR-0036](0036-isolate-stage-b-read-experiment.md#未豁免条件与证明边界) 中「附加区块留 C 裁决」的悬置关系；B 只用主区块的实验边界继续适用，[ADR-0036](0036-isolate-stage-b-read-experiment.md) 其余正文不受影响。

## 背景与取舍

[规格 §4.3](../../intent/draft.md#43-元数据与来源仲裁) 与 [ADR-0036](0036-isolate-stage-b-read-experiment.md) 将主区块之外的存在性区块（abstract-en、Significance Statement、Plain Language Summary、Key Points 等附加区块）的消费语义留待 C 裁决，B 实验只消费主区块。附加区块不出现在 Crossref 主摘要或 Feed description（[EXP-1 记录](../verification/exp-1-http-audit.md#b-前进方向与后续责任)），取得依赖出版者全文页通道；该通道对 Wiley 为 403、AMS 受阻，2026-11-17 对近期论文的抽样（JGR-A `10.1029/2026JD048010`、AIES AOP `AIES-D-26-0049.1`）复现了这一拦截。抽样中可取得的 Significance Statement 是主摘要同结论的通俗化复述，不含主摘要之外的新事实、新方法或新限定；Key Points 与 Plain Language Summary 的体裁亦为要点式与通俗化转述，面向非专家读者。

若 Screening 消费附加区块，筛选门禁输入将依赖最贵、最不稳定的出版者页通道；附加区块有无随时点与通道漂移（AOP→正式版、Feed→出版者），须另建降级与披露规则，附加区块与主区块措辞冲突会引入噪声，截断与清洗负担同步放大。对领域专家所有者，复述内容不移动 accept/reject 边界，预期判别增益≈0；为该增益承担通道与一致性成本不成立。代价是放弃附加区块对边界样本的潜在增益，且通俗文本不进入系统判别；若展示面将来需要，须另行裁决。

## 决定

Screening 及正式校准输入只消费主区块。附加区块不进入 Screening 输入、校准标签或自动精读门禁，继续只保留存在与定位；附加区块取得失败不构成摘要取得失败、降级条件或披露事实。C 的元数据扩展只需维护存在及定位投影，不新增附加区块消费语义。展示面（日报、Read 报告）如需通俗摘录另行裁决；即使将来引入，也不得回流 Screening 输入或校准标签。
