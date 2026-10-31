# 显式基线审计与分级确认：新增能力覆盖

依据：[#132](https://github.com/MeteoBoy4/PaperRadar/issues/132)、
[#126 裁决](https://github.com/MeteoBoy4/PaperRadar/issues/126#issuecomment-6536667331)。
本记录为独立新增能力台账，不修改第一步冻结台账、历史回执、固定测试或分母。
公开接口及确认字段见[审计契约](../contracts/verification-scope-audit.md#显式基线与分级确认)。

`tests/test_scope_baseline_audit.py` 独立未绑定，共 34 项；没有新增 required 组，
不进入旧组回执分母。同次完整 pytest 必须执行这些用例；本记录不替代最终集成门禁。

| 覆盖 | 用例数 | 公共接缝与判据 |
| --- | ---: | --- |
| 普通机械候选与只读保护 | 1 | Python；路径、组、影响、实际 base/target，Git 索引/refs及材料字节保持 |
| 精确敏感确认与 dirty 失效 | 1 | Python；缺确认失败，正确确认只解除确认缺口，未登记文件变动使旧确认失效 |
| 基线既有漂移与本轮变动正交 | 1 | Python；同路径同时输出两种来源，机械等级保持 |
| 未绑定分类规范 | 1 | Python；分类清单变化要求受影响组确认 |
| 目标前移与非祖先 | 1 | 临时 Git；陈旧 base 和非祖先均受控拒绝 |
| CLI 精确确认与外部存放 | 1 | CLI/JSON；外部确认只读，树内输入拒绝、错误不泄漏输入 |
| source 哈希与固定计数分级 | 1 | Python；仅 source 哈希重绑为机械，分母变化为敏感 |
| 各关键字段错误/过期 | 14 | Python；base、HEAD、target、树身份、组、路径、来源、类别、旧新文件/登记摘要、理由 |
| 所有传递影响组确认 | 1 | Python；只确认直接组仍因下游缺确认失败 |
| 恢复并确认不清除敏感基线漂移 | 1 | Python；当前文件全部匹配，基线漂移仍单独失败 |
| 非法确认输入 | 4 | Python；非列表、非对象或无效内容受控拒绝且不回显原文 |
| CLI 参数中文引导 | 5 | CLI；缺少 base/target、孤立确认和缺选项值退出2，提供 --help |
| 历史 blob 原字节 | 1 | 临时 Git；export-subst 属性不改写基线材料 |
| 旧新树各自的 registry/src | 1 | Python；冷进程使用每棵树自己的 src 依赖，scope字节不变的组语义变化仍敏感 |

开发期 CLI 兼容组合 59 项通过。工作树保持子票不重绑规则：
`scripts/verification_scope_audit.py` 的 A8/A9/A10 三条和
`scripts/audit_verification_scope.py` 的 A9 一条登记预计漂移。
验证旧接口与第一步93项时，仅在 `/tmp` 候选副本按这两个实际路径及必要 scope
传播重算；未把候选登记写回实施树，也未修改第一步93项测试或冻结证据。
新增 `scripts/verification_scope_baseline.py` 由本轮工作树身份与独立测试保护；
后续中央登记迁移须把该审计支撑纳入相应消费组，不把未绑定误解为正式冻结证明。

完整门禁及最终登记由第二步收口负责。本票不证明四刊 live、Pi RPC、模型质量、
正式校准、Docling、NAS 或完整阶段 A，也不改变历史状态读者。
