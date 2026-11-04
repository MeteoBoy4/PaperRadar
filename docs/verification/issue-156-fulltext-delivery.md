# #156 规范正文与持久证据 D1 覆盖

本台账仅登记 Body 的离线生产与读取切片；`stage_a_verified=false`。
不进入 A1–A10 历史 fixed 分母或 required 集合，不改 A9 v1 源码、规则格式或测试。

## 公共边界与独立覆盖

| 新独立模块 | 用例数 | 公共行为与反例 |
| --- | ---: | --- |
| `tests/test_fulltext_artifacts.py` | 10 | ArtifactStore 登记后重建 ReadContext、精确源回查；三种新增质量失败、空/不完整 provenance、非空白 orig 覆盖、排除块仍需可回放、JSON 转义 base64/U+FFFD、空 orig 不能伪装源展示 |
| `tests/test_fulltext_normalization.py` | 7 | 封面/授权信号、重复边缘文字、章节修复与层级、跨页原点/charspan、公式父源/候选/占位、表格与私用字符、父源块/体积统计、语义重排稳定、partial/failure 无质量事实、候选不能引入锚点、占位仍需 PDF 定位、循环层级拒绝 |
| `tests/test_fulltext_quality.py` | 10 | 新增 QualityFailure 经资格 DTO 透传、中文指引完整；共享 unreliable 谓词的普通/私用/替换/控制字符与 parser 标记 |
| `tests/test_fulltext_restore.py` | 4 | 真实备份/恢复、原根不可用后的冷进程禁 SDK 重建、逐字与原页回查；orig 篡改/成员缺失、同 fingerprint 同 evidence ID 不同正文拒绝 |
| 合计 | 31 | 合成材料只证明上述工程行为 |

TDD 留痕：先观察缺少 fulltext 公共入口的收集失败，再逐项观察并修复自动质量三类缺口、
排除源/未覆盖字符、JSON 转义绕过、候选伪锚点、占位无定位、空 orig 源展示、循环层级。
环境全程使用 `uv run --offline --locked`，不联网、不运行 live 或完整门禁。

兼容验证选取现有资格、A9 上下文/隐私/受限规则与 extraction 四角色/存储身份模块，
只证明现有消费者在本实现下的兼容性，不继承它们的历史回执或扩大其原证明范围。
本票定向组合（上述 31 个新用例加所列现有消费者）结果为 324 passed；
触及的 13 个 Python 文件 Ruff、格式检查与 mypy 均通过。
完整门禁与正式回执未运行；提交身份及其后的 integration 检查由收口报告记录。

## 设计与恢复闭包

- 公共服务：[fulltext-extraction](../contracts/fulltext-extraction.md)。
- EXP-6 方向与权衡：[ADR-0041](../adr/0041-self-contained-evidence-map.md)。
- orig 被 evidence_map_sha256 覆盖；成员文件内不回写最终三元组，document 仅供审计。
- 读取只依赖恢复库和四成员；无额外角色、无新 migration、无 SDK/原路径依赖。
- 自动质量通过不等于人工版式核查或 formal_gate；失败制品保留供审计但不能 load 消费。
- 三个新 QualityFailure 是 Body 对共享资格闭集的增量；EligibilityReason 不变。

## 固定范围与集成承接

本票新增代码、测试、ADR 与本覆盖台账为独立材料；不机械重绑历史组。
已有 `eligibility/models.py` 仅增三枚举，现有 Contract/GLOSSARY/README 只同步当前边界。
新 `fulltext-extraction.md` 的活文档分类与任何实际共享登记，仍须在最终 integration 树按
S3 的具体白名单审阅；不得改 A9 v1 的源码、测试、计数或规则格式来清漂移。

## 未验范围与下游

- #158：PDF/版本关联、质量事实与人工版式记录、根用途/样本/决定持久化；不得把本报告的
  automatic passed 直接写成 formal 或 experiment_document_gate。
- #159：受控 Docling adapter 负责原始字符、阅读路径、分类与完整 canonical；显式传入
  无 base64 的原始 document_json 供审计，并对实际 SDK 的 orig/charspan 保真负责。
- #160/#162/#163：提取/Read 任务、指纹历史权威、预算/租约、成功分析与业务备份验证；
  本票不提供唯一成功索引，调用者必须保存并按明确三元组回查，不能只信 fingerprint。
- #157：v2 接收器消费相同 ReadContext，并从 `paper_radar.content_reliability` 读取共用谓词；
  A9 v1 保持原字节。模型输出限制的判定、警告与丢弃政策不由正文服务实现。
- #164：真实公式父源块类别统计、evidence-map 体积、冷重建和真实 SDK 保真/资源 smoke。
  合成统计不能声称行内或行间公式已有真实覆盖；v1 冻结须考虑 smoke 反馈。
- B/F：真实逐文档人工核查、四刊/中文/复杂版式、裁切展示及代表性资源阈值。
  本票不证明正常生产 Read、四刊 fixture、实际模型调用、NAS 或完整阶段 A/B。
