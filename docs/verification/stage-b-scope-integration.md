# B 固定范围与必要重绑审阅

本台账记录 B 工程收口的精确材料维护，不发布完整离线门禁或真实链结论。
[机器清单](stage-b-scope-integration.json)逐路径保留原登记与新材料 SHA、用途、实际消费组及审阅理由；
最终身份确认保存在工作树外，绑定实际 base、HEAD、target 与完整工作树，不能复用本台账作确认。

## 封闭白名单与消费边界

输入合并树有 62 条 hash_drift 登记，涉及 24 个实际路径。仅更新 19 个共享中央 SHA
与 5 个单组字面量（RPC 源码、extraction 未知版本负例、三份 trace 恢复测试），不刷新其他材料。
三份 trace 原有字段、完整 JSON 比较及全部旧 assert 保留；18／9／5 节点和损坏、WAL、
幂等及移动恢复断言不减。新增字段以备份前公共 workflow 安全快照参与完整恢复比较。

A6 新增两条实际消费材料：`tests/stage_b_trace_support.py` 为 source/support，
`src/paper_radar/paper_trace.py` 为 source。沿现有 A6→A10 证明依赖消费；不增加旧组测试、
固定分母、required 集合或 scope 哈希边。新增 B D1 的独立模块／计数另见
[工程覆盖台账](stage-b-engineering-closure.md)，不将 D1 加入 A1–A10 回执。

## 敏感变化的逐项审阅依据

- 分类控制数据仅增加两份当前 Contract 的精确路径；未知路径与历史证据仍固定，不按目录豁免。
- 线性 B migration 已推进到人工维护的 b008 head；十份 scope、A3 备份 revision、
  人工预期、生产备份声明、两份 Contract 和两个中央 SHA 的用途分别核对，旧 migration 字节保持。
- 未知 normalization 负例仅 v2→v3，原因是显式新增 v2；82 个参数、字段路径与隐私断言不变。
- 三份 trace 测试新增 workflow 比较与 A6 两条 source/support 消费材料；每份测试及登记变更
  对 A6–A10 的全部影响组分别确认，不因只改哈希省略语义审阅。
- D7 的新 v26 策略和显式源码闭包采用独立新向量；v1–v25 字节、旧解释器与负例保留。
  版本审阅不形成 Live 能力资格，不以同策略键重绑旧摘要。

默认与显式审计、固定分母收集、兼容组合及最终代码审阅的实际结果保存在树外执行报告。
完整门禁仅在所有者明确授权后执行；最终冻结提交须实际退出 0 且同 run 为
passed/verified/same 后才生效，不预填 run_id。工程、真实链与恢复结论分别记录，
不提升 B 的 stage_a_verified、可选严格 Live 或通用生产消费资格。
