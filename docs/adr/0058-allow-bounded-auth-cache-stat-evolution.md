# 在固定认证基线上允许限定元数据演进

状态：已接受；日期：2026-11-10；依据：[#177 最终裁决 E-3/E-10](https://github.com/MeteoBoy4/PaperRadar/issues/177#issuecomment-6768256547)、[#179 实施澄清](https://github.com/MeteoBoy4/PaperRadar/issues/179#issuecomment-6768784968)，所有者授权 agent 自动创建已决方案 ADR；补充 [ADR-0052](0052-version-admission-uses-and-capability-requirements.md)。 认证事件证明来源与正常刷新语义由 [ADR-0063](0063-observe-normal-oauth-refresh-in-product-process.md) 补充。

对全部 stat 字段要求相等，会把正常订阅刷新和原子替换解释成漂移；每次刷新后自动重定基线又会追认异常成员。采用 `auth-cache-stat-v2` 固定批准基线：成员集合和名称、类型、属主／组、权限、链接数及未豁免 stat 字段必须不变；只豁免根自身和根下 `auth.json`、`models-store.json` 的 size、mtime、ctime、inode。其他成员的全部已登记 stat 字段继续相等。普通文件须单链接，目录链接数按原基线比较；软链、特殊节点、未登记目录和任何 `node-compile-cache` 拒绝。不读取成员正文，有界遍历和本次采样并发复核仍使用完整 stat。

宿主认证 helper 的 HOME／TMPDIR 移入独占受控临时根，保持持久认证根只供 helper 使用；临时根在成功、拒绝、异常后删除并核验，清理失败拒绝模型准备。模型只得到短期 bearer 的环境交接，不能读取持久认证根。布局改变需新启动／执行策略身份和独立源码向量；旧向量与 v1 算法原字节保留，旧证据不能转换为新策略资格。

v2 首份基线仅来自受保护的批准采集及既有接收、显式激活流程；漂移不触发自拍、自动重定或授予。获准演进不要求来自本产品认证窗口，`auth_cache_history`／`auth_cache_writer` 保持披露型，stat 不证明写入者或完整写史。代价是必须维护极小的豁免集合，并接受该集合内容未被 metadata 基线认证的边界；真实自然刷新与持续运行仍须现场验证。
