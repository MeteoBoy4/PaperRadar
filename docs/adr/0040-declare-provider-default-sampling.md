# 显式声明供应商缺省采样并保留校准语义

状态：已接受；日期：2026-11-01；依据：[#140 最终裁决](https://github.com/MeteoBoy4/PaperRadar/issues/140) 与 [#143](https://github.com/MeteoBoy4/PaperRadar/issues/143)。本记录补充 [ADR-0020](0020-let-the-user-classify-calibration-impacting-changes.md)、[ADR-0023](0023-separate-runtime-config-snapshots-from-calibration-baselines.md) 和 [ADR-0026](0026-control-pi-through-a-bounded-rpc-adapter.md)；责任模块归并由 [ADR-0046](0046-consolidate-pi-readiness-under-live.md) 补充，采样语义与证据门槛不变。

订阅通道不能通过静默删掉已有采样参数得到执行资格。models-v2 要求用户显式选择
采样声明，区分完整显式参数与接受供应商缺省。格式、字段和验证细则唯一由
[运行配置 Contract](../contracts/runtime-config.md#models-格式-2-与采样声明)维护。
配置结构合法、语义可回放和本次执行能力是三层判断；当前显式映射表为空，因此
合法 explicit 仍在领取前拒绝。provider_default 不代表温度零、可复现输出或参数能力
已经验收，仍需绑定实际模型/通道/策略的 Cwd/Live 证据。产品当前缺这些证据。

采样属于实际消费者的适配器语义，随模型槽进入阶段投影与输入指纹。Screening/reuse
变化进入校准基线和现有差异分级，纯 Read 变化只影响 Read；由用户决定 minor/major，
不自动继承门禁。旧模型默认值、编译值及快照/投影身份保持。新声明不重写历史事实，
也不把非 test 成功来源提升为正常生产、正式校准或 Read 用途资格。
