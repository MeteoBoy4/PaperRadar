# #184 AppArmor 精确内核 I/O：独立 D1 台账

本台账仅覆盖新增的封印 AppArmor policy 内核 I/O 模块，不扩充既有组成员、历史分母或
现场资格。独立未绑定模块 `tests/test_live_apparmor_kernel.py`：**57 项**。

| 公共接缝 | 覆盖与保证 | 证明边界 |
| --- | --- | --- |
| `SealedPolicy` / `AppArmorKernel.load` | 独立封印整包摘要、源码摘要、ABI 与精确 name/attach 清单；标准 zstd cache 在第一次内核改动前拒绝；未知同名包、同包额外 profile 或重复 attachment 拒绝；只 add 精确未压缩 binary，完整 exact 状态幂等 | 上层必须先核 source/binary/build manifest 的关联及未压缩构建参数；本模块不编译源码，不把源码摘要或单 profile `sha256` 与整包 raw hash 混用 |
| `AppArmorKernel.check` | 初装只读区分 absent/exact；默认拒 partial，显式恢复才返回 partial；每个现存项必须 exact，未知 bytes/模式/额外 attachment 或读失败始终拒绝 | 不调用 parser 或 writer 授权；不是放置或现场资格 |
| `AppArmorKernel.verify` | name、enforce、attach、raw ABI、整包 raw SHA256 与内核已解压 `raw_data` bytes 全部精确一致；确认缺失或不符为 drift；权限不足、接口未知、revision/身份变化为 unavailable | 合成 policy 树与 OS fixture；没有从上游源码推定本机内核必然实现同一语义 |
| `AppArmorKernel.remove` | 默认要求完整 exact 集合；显式 `allow_partial=True` 只允许已缺部分成员的已知恢复；每次写入前重核剩余 exact 集合，逐个精确名字移除并确认缺失；未知 bytes 拒绝，保留其他 profile | 固定 `.remove` syscall fixture；多次移除不是一个内核事务，失败保留部分状态供显式恢复，不吞错误 |
| `LinuxKernelPolicyIO` | 固定 `/sys/kernel/security/apparmor/policy`；识别合法 policy 根 magic-link 布局并限制其下目录及 raw 链接；revision 用新 fd、O_NONBLOCK、单次128字节读取，关闭整个身份回读窗口；无任意 root 读取路径参数 | 临时文件系统和 syscall fixture；只读探针确认当前主机 policy 根与 revision 流形状，未读到特权 raw bytes |
| 固定 parser 写边界 | 非 root、缺 parser、工具摘要/所有权不符拒绝；固定 `/usr/sbin/apparmor_parser --config-file=/dev/null --add --binary --skip-cache --abort-on-error`，stdin 只含封印 binary；固定 cwd/env，15秒、合计64KiB输出上限，失败只输出受控 reason | 替换 parser 子进程入口后以无权限本地 Python worker 验证成功/拒绝/超时/输出超限，未调用真实 parser 加载 |

快照枚举最多4096个 profile、嵌套深度32、单 blob 16MiB、整次读取64MiB；超过预算为
unavailable。全树元数据扫描用于识别同包额外 profile 和精确 attachment 冲突，不能退化为
只看 name/enforce。revision 与前后 profile inode/raw 链接身份用于拒绝不稳定观察，不宣称
抵抗恶意 root；root 本身可替换内核策略仍是既有信任边界。

红绿切片包含未知同名策略、writer 预检期间变化、合法 policy 根 symlink、整次读取预算、
最后身份回读中的 revision 变化及压缩 cache；新增只读 check 的11项回归覆盖初装、恢复与
未知现存策略拒绝。其余回归覆盖 complain/ABI/attach、源码与
单 profile hash 错配、额外 profile、ABA、读权限不足、partial 恢复、parser 失败及幂等。
开发验证为上述57项 pytest、两个新增 Python 文件 Ruff/format/mypy 全通过，不代替
完整离线门禁；没有修改旧 Schema、scope、guards、pins 或历史向量。

本切片尚未接线 installer/observer；未知同名磁盘资源、source/build 关联校验和 E7 映射由
#184 集成承接。未执行真实策略加载/卸载、sudo、namespace/mount、scope、认证、模型、
网络、receive 或激活；实际 raw ABI、EXPORT_BINARY/读权限、profile attach 与内核回读
仍须在所有者审阅新封印字节后现场验证。#177/#184 的开放状态、Live 门禁和 B 依赖保持。
