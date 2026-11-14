# normalization v2 工程回归

范围：跨标签重复页边、尾部独立事项层级与普通文本中的行内短符号重复风险。
仅合成 SDK export、HTTP transport、Pi RPC、模型声明与 PDF renderer/worker 边界替身；
实际 mapper、normalize、持久制品、证据回查、版式 HTML 与 Read 接收器均执行。
不执行真实 SDK/PDF 解析，不访问实验运行根或真实模型/凭据，不代表 live 质量通过。

## 诊断与修复

- 跨标签页边红例：相同原文/位置跨页出现，一页 page_header、一页 section_header，
  旧检测仅纳入 text，后一页进入 evidence/层级。v2 以合法视觉页边和相同相对 bbox
  聚合可用文本标签，保留源字符但排除重复页边。上下边缘对称，因此“原点单独导致漏检”
  的假设不成立；v2 显式统一原点，并以位置区分不同边缘/不同位置的普通重复。
- 层级红例：mapper 已保留上游 level/parent；输入没有字体、行或 span 数据，
  不能归因于丢失了可恢复字体。旧 normalize 仅盲 clamp。v2 对可分类、同父、
  有一级锚的连续独立尾部事项组作有限对齐；缺证据及真实子节保持。
- 行内红例：orig==text 的普通 text/caption 已含重复，旧坏码点规则不会标记 ASCII
  符号风险。无隐藏格式可恢复。v2 仅对局部变量样重复标为 unreliable，保留原文与
  evidence/provenance；真实 Read v2 消费后生成 restricted_source_reference 程序警告。
  不推造正确符号，也不声称穷尽其他错序或损坏。

规则唯一权威：[规范正文](../contracts/fulltext-extraction.md#normalization-v2)。

## 全新独立 D1

| 模块 | 节点数 | 消费行为 |
| --- | ---: | --- |
| `tests/test_extraction_normalization_repair.py` | 34 | 混标签与双原点页边；同页/异位置/非页边/相反边缘保留；尾部组正负例与显式父子层级；单一符号重复、长段单次重复与普通重复词；源字符/页码/bbox/charspan、Read 警告；v1/v2 无 SDK 冷恢复及成员字节不变 |
| `tests/test_extraction_normalization_cli.py` | 5 | CLI 实际提取到版式 HTML/Read 警告；新版本新指纹/预算与旧否决保留；两后端新合成配置冷 CLI；未知版本字段拒绝 |
| 合计 | 39 | 不加入历史 A1–A10 固定分母或新建验收组 |

## 相关验证与边界

开发验证以 `uv run --offline --locked …` 执行，源码来自独立工作树的安装环境。
完整离线门禁未运行、未授权；不发布正式回执。

- 首轮相关模块发现旧“v2 未知版本”负例与新版本发布冲突；另有执行器基础环境缺 extra
  导致 dependency_missing。没有把这些失败跳过或计作成功。
- 实际锁定 extra 安装后，原 `tests/test_docling_executor.py` 23 节点通过，使用实际
  发行包元数据 probe 和其既有合成 worker；不加载真实 SDK 或解析 PDF。
  临时人工库存边界组合另行运行，不能代替这一原模块验证。
- 配置、StageInput、工具链、冻结 Schema 与两个新 D1 的相关组合 229 节点通过；
  随后增加一个异边缘负例，由最终独立 D1 覆盖。历史 fulltext/Read/body 消费子集
  154 节点通过；CLI 兼容组合 59 节点通过。精确最终命令、后续集成树重验及日志见外部交接。
- 全部触及 Python（含新 tests 和变更的旧负例模块）执行 Ruff、format、strict mypy。

## 历史与敏感变化

v1 算法、旧制品读取、原四角色/三元组、既有工具链/模型文件与全部 migration 保留。
生产从配置显式传 normalization_version，审计、manifest、evidence-map 一致；
低层历史调用仍默认 v1。新的 v2 配置声明改变 extraction 指纹，不复用旧预算或清除旧否决。

唯一旧测试变化经所有者主会话逐字授权：
`tests/test_config_extraction_validation.py` 的未知 normalization 参数从 v2 改为 v3；
82 节点、字段路径与隐私断言不变。旧文件 SHA-256
`613071380962f23d802a90dc8a778246c6cb3b36665891f6a9ee43405aed3c9d`，
新文件 SHA-256 `18bfcdd1c3e6bfb0905cabb1fb403bc0089f896d7260ab7bf0d2f62161178a0a`。
此敏感变化须由最终固定范围集成按实际 HEAD/全部受影响组登记，不能沿用历史确认。
没有修改冻结向量、fixture、已发布证据或旧 migration 来取得通过。

新同 PDF 多成功在未选择时仍安全拒绝。显式正文选择由独立工程切片提供，
其迁移、授权、领取/恢复及组合行为以所属契约和台账为准，本台账不扩张该切片的结论。

## 未验证

真实 PDF 对这些规则的适用性、其他语言/刊物、真实符号保真、四刊覆盖、资源阈值及真实
模型调用均未验证。下一次真实运行必须新配置/指纹重新提取、显式正文选择后重新进行
所有者六项核查；旧否决不可覆盖。正文选择本身不授予人工质量或 Read 许可。
