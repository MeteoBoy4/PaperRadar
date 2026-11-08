# #167：项目服务网络验证通过并恢复

所有者批准并执行[已封印的单次网络包](issue-167-service-network-preparation.md)，随后报告「已运行」。本轮只读接收回执、复核本表完整快照及宿主恢复元数据；没有重跑、追加解析/TLS、Node/Pi、认证/模型或崩溃。旧 unknown、历史消耗和原证据字节保留。

## 身份和有限结论

| 材料 | 身份 |
| --- | --- |
| run | `f287c9ad630e` |
| review-seal.json SHA256 | `292ee4f3bbdda1cd216eeaaf157e1c338074163b9ca37f7b7ebe93a9918e989d` |
| core manifest SHA256 | `336e927f59eab59a2568017e2d3f8bb771ba271d197326f7c05d9f053ef097cd` |
| driver SHA256 | `6961d7be4eb3dc9f6e3da0767e4f4e9f11d6b7cd9de0a54fe4d0560131f53107` |
| results/owner-run.json SHA256 | `e12027ae45d535bf2acda5a3413a8de7fd89b65c2413a5b75c2093003c63e115` |

outer/inner 均为 `observed_expected_and_restored`。fresh 只读核对33个封印成员、18个映射源码、两份 entry、driver/unit、工具及 Case 绑定；ready/result 通过既有验证器，六份规则快照按原独立 binding 完整重验，未发现阻断项。外部配置确认来源仍是所有者运行时的显式 flag，不是程序独立检查路由器。

这支持本次项目服务、固定目标的代表性 TCP/UDP 拒绝、显式 Python DNS/TLS 正例及所报恢复。不是任意流量或所有规则分支的穷尽证明，不进入历史覆盖/分母、required、正式产品回执，也不激活产品。

## 分阶段流量及 DNS/TLS

worker UID1000、cap 空、NNP、core[0,0]、实际 cgroup 与私有 resolver 匹配。独立 live cgroup2 binding 为 dev30/inode848072、table handle27；其来源和稳定 handles 随回执保留。

| 本表阶段 | allowed packets | rejected packets | 有限解释 |
| --- | --- | --- | --- |
| created_deny | 0 | 0 | 初始完整 deny |
| deny_1 | 0 | 1 | 一次 router:53 TCP connect 未建立连接，socket 已关闭 |
| deny_2 | 0 | 2 | 一次 api UDP A 未取得响应，socket 已关闭 |
| activated | 0 | 2 | 完整允许集合激活，无额外流量 |
| positive_complete | 31 | 2 | 六步正例完成且无新增 reject |
| post_stop | 31 | 2 | 进程退出/停止后的完整核验仍一致 |

两项拒绝均有独立本表 counter 增量，不仅依赖 timeout/errno。31/2 是 packet 数，不是 DNS、HTTP、认证、模型请求数，也不主张内核重传数量。操作上限仍以受审程序为依据：deny TCP1（无 DNS payload）、deny UDP A1；active UDP A2、TCP A2、TLS2。HTTP/auth CLI/model prompt/Node/Pi/IPv6 探测/崩溃均0，没有重试、备用地址或额外域名。

active 两域的 UDP/TCP 各取得一致唯一池内 A，TTL 均为1秒；api 为28.0.5.94，auth 为28.0.5.167。这是同轮快照，不构成未来地址允许清单或可复用 TTL。两次 TLS1.3 均完成证书链和固定 hostname 检查，没有发送 HTTP。

| 角色 | 两份 DNS 最早截止（monotonic） | TLS 调用开始 | TLS 调用返回后 | 距截止余量约 |
| --- | --- | --- | --- | --- |
| api | 4656139.526678829 | 4656138.531804015 | 4656139.094682879 | 0.432s |
| auth | 4656140.096484716 | 4656139.101407563 | 4656139.669903975 | 0.427s |

每个区间均在两份 DNS 收到之后、最早 TTL 失效之前。这里是包含 CA 核验、TCP、握手及 close 的保守调用区间，不能称为握手内部精确瞬间，也不能延长这1秒的适用窗口。

API/auth 共用冻结池，ACL 不证明两类目标隔离；域名由受审 collector 限制。无 TLS 中间人的事实来源仍是所有者陈述。上游映射、最终 IP/线路由软路由决定，本机不核验或主张出口身份。IPv6 保留 not_assessed。

## 恢复和独立检查

恢复五字段完整：host_policy_restored、global_resolver_unchanged、ledger_retained、table_absent、unit_absent；restoration_stage=complete。resolver_check 来自本次 root0600 持久基线及恢复后读取，同 run 的 before/after 均为 `841c38da2013c6dbcb38c5949622b084ab8372c4115ba71ad377a2288b3e3acf`。artifacts=successful_artifacts_removed，永久 ledger 保留。

普通用户独立查询该 unit 为 not-found/inactive/dead、MainPID0、fragment/drop-in/cgroup 空；精确 unit 文件、CG 目录、代码/runtime 均 absent。本表 absent 由已审 root 程序确认，没有为了复核追加 root nft 枚举。

永久记录仅 lstat：宿主 UID/GID0、0600、nlink1、17453 bytes，未读内容。默认工具沙箱将 UID/GID 映射为65534，随后同一普通用户宿主检查得到真实0；两种来源分别记录。本轮当前 resolver 的普通用户只读 SHA 与回执一致，只是额外当前快照。派生检查在本包 results/post-run-readonly.json、post-run-systemctl.json、host-ledger-lstat.json。

## 后继及验证范围

本轮只有纯元数据重验和只读宿主核对，不重跑该已消费网络案例。准备阶段的相关测试149项、旧 resolver 兼容96项及静态检查见[准备证据](issue-167-service-network-preparation.md)，不把它们写成本轮重跑。新增结果按独立未绑定 D1 材料处理，不修改固定登记；链接/diff 与本轮最终 scope 含 collect 审计另记回记，未运行完整离线门禁。

此 Python worker 未使用模型 Landlock，不能据此证明模型 TCP53、Node 默认 lookup 或固定 Pi 兼容。下一步须按真实调用路径冻结无秘密兼容验证的调用/解析预算；一次 lookup 不能冒充一次 DNS 查询。真实凭据、认证/模型、供应商能力/故障、H5 和产品激活仍需各自授权和证据。旧 c591 的缺失基线不会因本例成功而补齐，Live/B 与产品缺证据阻断保持。

内部配置、进程/内核详情、回执及相关哈希只留本地，不发布 GitHub。
