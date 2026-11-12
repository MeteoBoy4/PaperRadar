# 跨源码包恢复同一未完成放置准备

状态：工程实施决定；依据：[#184](https://github.com/MeteoBoy4/PaperRadar/issues/184) 原验收内源码修复、新字节审阅与 owner 安装范围；补充 [ADR-0065](0065-retire-authenticated-failed-placement-preparation.md)。新增恢复语义与封印字节仍须所有者审阅，不把实施授权记作完成审阅。

无秘密预检失败可留下已经退役原策略、加载新策略而尚未安装业务的新候选 preparing 日志。修正 Python 查询会产生另一 payload，即使全部放置成员原字节相同，原退役日志也不属于新 payload。删除原日志、重写归属或重建快照会丢失失败证据；允许新候选自动接受任意旧日志又会开放递归迁移和未知策略替换。

因此只增加一个由三摘要命名的原 preparing 来源：原 payload、原 manifest、原日志原字节。新 payload 仍封印相同完整 failed_preparation 描述；root 从固定 staged/ledger 地址重新认证原保护树、原 v1 日志完整规范字节、原失败策略来源，以及相同 epoch、upgrade pair、owner 输入、窗口和全部十一放置成员。原来源不得自身含恢复描述，不接受自引用、递归、prepared 或 installed 来源；除当前 own journal 和该精确原 journal 外，其他退休日志仍冲突。

首次必须显式 recover，原 snapshot 与 removed marker 保留，原新 marker 必须仍是 preparing，kernel 必须完整 exact。实际 idle 与再次认证之后先提交本 payload 的 preparing，再按原新策略生命周期预检、回读、提交本 prepared；本 preparing 可以接纳同完整身份的 prepared marker，覆盖其提交之后的中断。接续使用不可写的 kernel 边界，只核现存完整策略；即使在本 preparing 耐久提交后发生缺失或 partial，也不能重新加载或移除策略。`.new` 与不明记录继续拒绝。原来源日志、快照和失败策略来源均不改写，本 prepared 之后恢复到正常 MAIN/history/epoch 生命周期。

代价是永久保留一份原日志并维护明确的两阶段恢复来源，且这种恢复只能修复保持全部放置字节的源码问题。它不提供通用迁移链、任意策略升版、自动清理、时钟或预算重置。重新取得现场部署与执行资格仍沿原门禁，离线模型结果不证明真实预检成功。
