# #183 nft 审阅收尾：共享固定规则规格

本轮仅收口 Standards 的 P3 重复代码建议。`nft_rules.py` 内部用有类型的不可变记录
集中四负对照与三允许的地址、协议、端口、comment 和前缀标记；native 与规范 JSON
各自编码，同一 cgroupv2 selector、counter、允许范围、顺序及末尾 drop 保持。
公共规则、双视图读取、generation、恢复、Schema 与 launch v9 均不变。

重构前源码单独保存在树外。对四个 uid、五种合法池写法与四组负对照地址的 80 组
类型校验输入，逐组比较重构前后的完整 native 字节和保留字段顺序的 JSON 编码字节，
结果全部相等。该比较只证明行为保持，不替代独立规则期望；既有逐行 native 字面
正例、source-derived JSON/native fixture 与全部负例测试保持原字节，期望未从共享
生产规格派生。两份 source-derived fixture 的原 SHA256 为：

- `live-nft-1.1.6-source-derived.json`：`67b42862ade92d6ee89acd6902561dae02f1af8863416d4d5be9b04946625d07`。
- `live-nft-1.1.6-source-derived.nft`：`2100cb2b4a7324980796c09906b548844393fcf8dad380029d21572dca2c04b5`。

已提交的 v15 不重绑。新增 admission v16 的 76 文件向量及摘要锚
`f25d67d915172228c310721df0ee22d6bda80497cb41b47f333c1a5a696c315b`，
只有 `nft_rules.py` 和声明当前策略的 `current_binding.py` 源码哈希变化。
v1–v15 向量与全部旧 pins 原字节保留；D7 新增 v15 历史字节参数案例，当前 D7 与
builder 使用 v16。原 [67 项 D1 台账](issue-183-nft-recovery.md) 按次冻结，不回写或扩充
旧组分母；本轮不新增规则测试接缝，也不登记公共 scope。

开发验证包括相关 NFT/observer/recovery/guard/builder/resources 回归、整仓 Ruff、
format、mypy，以及发布产物触发的 compatibility acceptance。逐项实测结果与字节比较
记录保存在树外实施交接；这些结果不替代完整离线门禁。未执行真实 root、namespace、
nft、认证、模型、出站、部署或激活。真实 kernel 回读、GETGEN positive 与新包恢复
仍须所有者审阅新字节后验证；当前 v16 没有现场资格，Live 与 B 的阻断关系保持。
