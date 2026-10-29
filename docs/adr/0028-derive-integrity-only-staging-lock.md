# 保留官方锁原字节，以仅补 integrity 的派生锁安装 Pi

状态：决策记录（原文未单列接受状态）；日期：2026-10-18；依据：[基线裁决原文](https://github.com/MeteoBoy4/PaperRadar/blob/91e5d02e199f1921ca8afd2b7bdb8f257e6264f3/docs/adr/0028-derive-integrity-only-staging-lock.md)；补充／部分取代：无另列关系；正文边界继续适用。

2026-10-18，依据 Issue #36 的六项裁决及 #37 的 Pi 1.3.0 机制实测。

官方 lockfile v3 的部分包没有 integrity，直接使用它无法证明 npm 实际消费的
tarball 字节符合固定摘要。只在安装前另下载检查一份包也不能约束 npm 后续取用的字节；
依赖 npm 内部隐藏锁则不能提供同样稳定的证据边界。

因此官方 package.json、package-lock.json、release 元数据原字节永久保存；
staging 内使用 `derived-lock-v1`：按 name/version/resolved 精确匹配同 release 的 sha512，
只填缺失 integrity。已有值与 release 冲突、缺少依据、重复匹配或不支持的锁格式都拒绝。
派生锁不改变版本、resolved、依赖图、override 或其他字段；其规范字节与独立补充清单
也随供给冻结，派生字节摘要及规则版本进入供给身份。

npm ci 实际消费原 package 与这份派生锁，以固定 bundled npm 的逐包 integrity
强制约束实际下载内容。代价是只支持已验证的锁/release 形状，格式变化须显式处理。
Python 下载逐跳检查来源；npm 的重定向不能由 Python 逐跳约束，保证边界是 resolved
白名单预检和逐包固定摘要。它不构成 OS 网络隔离或 RPC/模型兼容证明。

这解释了主方案“不原地改写官方锁文件”：权威原件不变，派生文件是安装输入，
不是新的依赖解析权威。具体字段与哈希规则见 [供给 Contract](../contracts/pi-supply.md)。
