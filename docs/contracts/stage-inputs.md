# 阶段输入载荷与指纹（#47 / #48）

## 公共边界与交付范围

公共入口从 `paper_radar.stage_inputs` 导入。#48 当前只交付 boundary 格式 **1**；
value、reuse、extraction 随后续票接入，read/suggestion 不属于本次 A5。
未领取的阶段、字符串冒充 `StageName` 或未知阶段均受控拒绝，不产生占位指纹。

| 入口 / 类型 | 契约 |
| --- | --- |
| `ScreeningFacts(title=..., abstract=..., abstract_truncated=...)` | 冻结的精确论文文本与严格布尔事实；未知字段拒绝。 |
| `build_stage_input(snapshot, stage, facts)` | 从已由 check/compile/load 验证的 `RuntimeConfigSnapshot` 选取同阶段 `project_config` 投影，返回不可变 `StageInput`。 |
| `replay_stage_input(payload_bytes, expected_fingerprint, snapshot=None)` | 规范载荷字节与明确期望指纹的严格回放；可选核对明确历史快照。 |
| `compare_stage_inputs(before, after)` | 返回不可变 `StageInputComparison`，只解释组件变化。 |

`StageInput` 只由 build/replay 创建，禁止直接提交未验证字段构造。只读字段为
stage、format_version、projection_format_version、projection_id、facts、payload_bytes；
`fingerprint` 为载荷原始字节完整 SHA-256。没有另一份“载荷 + 指纹”信封格式。
程序持久化时应保留规范字节和独立期望指纹；本票不保存输入文件、不增加表、migration、
artifact kind 或产品 CLI。数据库 revision 保持 `a405_pi_cleanup_execution`。

模块只通过 config 公共面消费快照、StageName、StageReadiness 与 project_config。
编码/哈希、公共头校验、投影核对和比较前置各有一份权威实现；没有公共“投影 + 事实”
构造入口。模块不读取 YAML、数据库、制品库、文件或网络，不调用 Pi/Docling。
既有配置、Screening 输出与存储各自保持权威；本票不修改已有投影、基线或 Frozen Contract。

## boundary 配方与编码

规范对象包含且只包含以下五个键：

```json
{"config_projection":{"format_version":1,"projection_id":"<完整 projection_id>"},"facts":{"abstract":"<精确论文摘要>","abstract_truncated":false,"title":"<精确原题名>"},"format_version":1,"kind":"stage_input","stage":"boundary"}
```

`kind=stage_input` 分离身份域，`stage=boundary` 分离消费者，阶段格式与投影格式分别记录。
载荷只引用本阶段配置投影，不嵌入 Profile/Prompt、完整快照 ID、校准基线、文件哈希、
artifact_id 或执行实例身份。配置实际语义依赖以[配置投影契约](config-projections.md)为准。

题名与论文摘要必须是严格字符串，`str.strip()` 后非空；检查不改变原文，不应用论文占位
词表，因此 `...` 等非空文本在此层不会被当作缺项。保留 Unicode、大小写、所有首尾空白、
CRLF/LF 与次序，不做 NFC/NFD、翻译、清洗、补全或语言识别。截断标记只收 Python bool，
整数 0/1 和字符串均拒绝。孤立代理字符在 typed facts 构造时受控拒绝。

编码由本模块独立拥有：UTF-8、非 ASCII 原样、对象键排序、紧凑 JSON（`,`/`:`）、无结尾换行，
不含浮点或 NaN/Infinity，布尔和整数严格区分。阶段/投影格式是严格整数，当前均为 1。
所有哈希字段只收 64 位小写十六进制字符串，不归一化大写、`0x` 前缀或整数。
本模块不导入配置私有编码器；任何载荷字段/规范化规则/消费者语义配方变化，须提升受影响
阶段的格式，不能静默改变历史含义。

boundary 独立固定向量：完整合成载荷在
[`tests/fixtures/stage_inputs/boundary-v1.json`](../../tests/fixtures/stage_inputs/boundary-v1.json)，
使用已有非空 no-adapter boundary 配置向量（projection 格式 1，
`d67c818c67ecaf6f14361ee4f54cf771a50088c6e2d421031299b35a39c41532`），
合成题名/摘要，其阶段输入格式 1 指纹固定为
`e27f19cc566e80158680aecfcf2b3bd41a3cb07201ef6c3a4cec66b4ba11abb2`。
期望由人工载荷字面量独立核算，不调用被测 builder 更新期望。契约只登记指纹、格式与
合成示例，不记录真实摘要、摘录或 Profile。

## 就绪、回放与身份核对

构造直接沿用 `snapshot.stages[stage]` 的已有 `StageReadiness`；缺项或 placeholder 时
以 `not_ready` 拒绝并携带原就绪事实，不补默认值或人为要求所有阶段就绪。
旧有效快照没有 adapter 时仍按原配置完整性语义判断；此时投影 adapter 为 null。
这不是 RPC 执行就绪，后续执行服务必须另查协议、参数映射、固定环境和凭据。

回放依次严格解析、核对封闭字段/身份域/阶段/格式/事实、重建规范字节、逐字节比较、
重算指纹并核对调用方提供的完整期望指纹。多余键、重复 JSON 键、不同排版、尾随换行、
隐式类型转换及未来阶段格式均拒绝。无法解析的文本和孤立代理字符不保留在错误链中。
回放不推断来源存在、不从当前 selector 补项，也不把自洽哈希当作业务来源证明。

若提供 `snapshot`，只核对该明确快照的同阶段投影：投影格式不受支持或当前程序无法按
同格式核对时为 `projection_format_unverifiable`；同格式 ID 不符为 `projection_mismatch`。
两者不同，不静默改投影、迁移、重新编译或替换历史依据。当前只支持投影格式 1；未来
消费者须保留匹配格式的重建实现或提供显式迁移。回放证明规范身份与可选配置绑定，
不重新授予配置完整性或执行资格；新任务构造必须使用快照门面。

## 比较与受控拒绝

`status` 为 `same/changed/incomparable`。同阶段且阶段/投影格式兼容时，组件固定按
`config_projection`、`title`、`abstract`、`abstract_truncated` 排序，只列发生变化者。
比较不输出原文、旧/新值或自由字段名。不同阶段或格式不兼容返回不可比，细粒度配置
解释由 `compare_config_snapshots` 承担。后续第二阶段接入后覆盖跨阶段实际消费者比较。

构造/回放抛 `StageInputError`；其 `.reason`、`.field` 为封闭 StrEnum，`.readiness`
仅在配置未就绪时携带已有受控配置事实。错误不保存输入值、未知键名或原始异常。
安全位置集合是 `stage/snapshot/facts/facts.title/facts.abstract/facts.abstract_truncated/`
`payload/kind/format_version/config_projection/config_projection.projection_id/`
`expected_fingerprint/inputs`；未知键折叠为所属受控容器位置。

| 面 | 封闭原因 |
| --- | --- |
| `BuildReason` | unsupported_stage、invalid_snapshot、not_ready、invalid_facts、invalid_text、invalid_encoding、invalid_hash |
| `ReplayReason` | invalid_payload、unsupported_stage、unsupported_format、invalid_fingerprint、fingerprint_mismatch、non_canonical、invalid_snapshot、projection_format_unverifiable、projection_mismatch |
| `ComparisonReason` | different_stage、incompatible_format、invalid_input |

事实、结果及其载荷引用不可变，repr 隐藏文本与载荷。载荷内嵌题名和摘要，按敏感业务
数据处理，不得写入 repr、异常、stdout/stderr、普通日志或验收结论。显式 `.payload_bytes`
仅供受控业务消费。后续 RPC 只能渲染已绑定的冻结事实；渲染语义变化需 adapter policy
或阶段格式版本表达，不能额外读取未绑定字段。`original_title_is_zh` 由上游提供，属于
输出验证上下文，不进入 boundary 身份。

相同指纹只证明语义输入相同，不证明缓存存在、成功输出、来源合法性、校准通过或当前
任务资格。changed 不自动调度、刷新预算、判定 minor/major、撤销人工决定或改写历史分析。
指纹不含 Paper 主体；跨 Paper 是否共享成功缓存由后续资格/缓存票决定。书目字段与
执行审计字段不能作为额外事实提交；真实“论文事实 → 阶段输入”映射由后续消费者验收。
