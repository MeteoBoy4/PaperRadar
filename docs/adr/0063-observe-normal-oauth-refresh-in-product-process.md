# 在产品认证进程观察原策略正常刷新与提交

状态：已接受；日期：2026-11-11；依据：[#177 所有者认证接缝裁决](https://github.com/MeteoBoy4/PaperRadar/issues/177#issuecomment-6784720735)；补充 [ADR-0048](0048-accept-bounded-request-observability.md)、[ADR-0055](0055-separate-protected-admission-ledger-from-business-facts.md)、[ADR-0058](0058-allow-bounded-auth-cache-stat-evolution.md) 与 [ADR-0062](0062-collect-sealed-model-evidence-without-activation.md)。

stat 演进与成功调用无法证明刷新，固定 Pi 1.4.0 的 bearer CLI 又不提供刷新事件。采用仅产品 uid 持密的封印认证入口，经同一固定安装公开的 `ModelRuntime` 和原默认文件存储，在单个 runtime 实例公开返回的 `OAuthAuth.refresh` 上包装观察，再调用一次原 `getAuth`。完整 credential 不透明透传原方法，只检查到期元数据；原锁、OAuth 类型门禁、最低有效期、刷新、后置校验及持久化错误传播保持。该包装依赖已核公开可变类型与精确具体实现，并非 SDK 专门承诺的 observer 扩展点；固定源码改变须重新评审。正式准备和 collector 共用这条路径，不改变 Pi/Node 供给、凭据、时钟、请求或校准语义。

正常刷新定义为原最低有效期策略自主触发、本次原刷新完成且原文件持久调用成功返回；允许正常提前刷新计入验收。Pi 的 `expires` 包含供应商余量，`was_expired_by_pi` 只表示回调时已越过 Pi 存储阈值，供应商真实有效期到点始终披露 `unknown`。只有本次刷新成功及本次完整 `getAuth` 成功，才按这一固定具体 backend 的写错会抛出源码确认提交；这不是通用 CredentialStore、fsync 或断电耐久保证。竞争跳过、取消、写错、后置拒绝或来源丢失不认领提交，不再调用认证来补证。

短期 bearer 仅在产品内存和产品私有管道中。root 只接固定计划／模板／操作、进程／已封印源码身份、UTC 及 `need_refresh`、`was_expired_by_pi`、`refresh_called`、`refresh_succeeded`、`store_committed` 白名单；不接 credential、token、JWT、秘密派生摘要、headers、body 或自由错误。每次认证仍在释放前原子预占 auth1，未知不退款。既有六格中的三个有序成功操作可形成 A→B（刷新1）→C（刷新2）闭环；不同格的模型资格各自独立，仅共享认证通道和完整站点绑定。批间由外部明确选择时点，释放所有轮、锁和持密进程；事件不足持久 `unknown` 停止，不制造过期、自动补跑、延窗或增加额度。六格部署后72小时为目标披露，共同批准窗口仍为硬授权边界。

代价是新增持密代码、独立元数据版本、启动与准入策略升版及封印审阅责任；收益是在有限秘密边界内取得真实事件来源。root 字节由所有者审阅后部署，receive／激活仍独立。完整会话写史、认证全写史／writer、隐藏请求和供应商真实到期等既有未知不因本决定升级。
