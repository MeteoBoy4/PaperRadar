# #167：固定 Node 无秘密诊断通过并恢复

所有者批准并执行[固定 Node 诊断包](issue-167-node-diagnostic-preparation.md)，随后报告「已运行」。本轮只读核对回执、完整规则快照、TTL与宿主恢复状态，没有重跑或追加请求。旧案例的 unknown、记录、消耗与已发布字节不变。

## 身份与接收

| 材料 | 身份 |
| --- | --- |
| run | `b62d4a90e713` |
| review-seal.json SHA256 | `cdad7a9e9bb6ab82b704fe1ec7dfc458262dc4bec78487c1584fb4da371bfdc2` |
| core manifest SHA256 | `5c3a8a434eb161594f63f4fdabf9ee65efdf5a38e8e7b964c8a5d34123c6a5f3` |
| driver SHA256 | `da500581f7e98cbed49edcb64b477d4cc97a67bf1c4e94ce5e2d89eb8ce62e33` |
| results/owner-run.json SHA256 | `b472a476da8c67b2114db9f03d7545fa279a4bf42e800580a369d81d8f554369` |

outer/inner均为 observed_expected_and_restored。fresh只读复核39个成员、22个映射源码、两份entry、driver/unit、四份规则及Case绑定；ready/result/四阶段验证通过，八份kernel快照按原独立binding完整重验，无阻断项。该复核没有执行Node、网络或重新取得真实锁/整树哈希。

## 四阶段实际结论

四个固定Node均报告UID1000、core零、NNP、cap空、CG匹配及原FD继承，子进程已回收。无Landlock的TCP53正例成功；原IsolationBoundary下TCP53为受控EACCES/EPERM拒绝，未增加本表packet。两域默认lookup各一次返回匹配参考的IPv4，随后TLS1.3各一次完成链和hostname检查，未发HTTP。

| 完整快照阶段 | allowed packets | rejected packets |
| --- | --- | --- |
| created_deny | 0 | 0 |
| activated | 0 | 0 |
| node_stage_1 | 4 | 0 |
| node_stage_2 | 4 | 0 |
| node_stage_3 | 20 | 0 |
| node_stage_4 | 36 | 0 |
| diagnostic_complete | 36 | 0 |
| post_stop | 36 | 0 |

独立live CG binding为dev30/inode848506、table handle28，稳定handles与源码绑定随回执保留。36/0只是packet计数，不是DNS/HTTP/认证/模型请求数；TCP53负例是内层拒绝，不能归因nft reject。

| 角色 | 同轮最早参考TTL截止 | 父区间开始 | 父区间结束 | 距截止余量约 |
| --- | --- | --- | --- | --- |
| api | 4658430.414863881 | 4658429.421137035 | 4658430.006143612 | 0.409s |
| auth | 4658431.132689067 | 4658430.137810934 | 4658430.730360543 | 0.402s |

每域UDP/TCP参考TTL均1秒、唯一池内A一致；api为28.0.5.94，auth为28.0.5.167。父区间包含Popen、Node默认查址、TLS、close和退出/回收，分别约0.585s/0.593s，均在参考收到后、最早失效前。这不是精确握手内部瞬间，也不让该1秒TTL延用。

本次执行为Node4、lookup2、显式参考DNS4、TLS2、TCP53正负对照各1。OS内部A/AAAA/NSS查询数、wire QNAME和TCPfallback尝试继续按所有者A保持unknown。HTTP、Pi、认证CLI、模型prompt、IPv6网络连接、崩溃均0，没有应用重试或备用域名。

Node使用原模型文件/端口隔离，但该诊断没有Pi/Undici完整connector、RPC或真实模型，不扩成全部自动选址/流量/进程隔离通过。API/auth共享池的ACL不证明二者分离，无TLS中间人仍取所有者陈述；上游映射、最终IP/线路不核验，本机不主张出口身份。IPv6 not_assessed。

## 原安装保护与后验的来源

该包使用诊断只读投影和原instance SH锁，非完整产品use_install。每个Node的继承FD与元数据一致，公开登记/完整tree-v1/ELF的作用域检查由已审worker源码执行。

worker_result是在保护scope退出前发布的中途证据，不能单独证明后验完成。最终owner成功还要求gate5后的worker正常退出、CG空与恢复；按已审流程，scope后验失败会使该最终条件失败。因此整例成功支持后验未报错，不冒称本代理独立重算了真实整树或完整产品材料/D5/snapshot规则。

## 恢复及独立检查

恢复五字段完整，restoration_stage=complete，artifacts=successful_artifacts_removed、ledger保留。本次持久resolver基线与恢复后同run SHA均为 `841c38da2013c6dbcb38c5949622b084ab8372c4115ba71ad377a2288b3e3acf`。

普通用户独立查询unit为not-found/inactive/dead、MainPID0、fragment/drop-in/CG空；精确unit文件、CG、代码/runtime路径均absent。表absent由已审root程序确认，未追加root nft枚举。永久记录仅lstat：宿主UID/GID0、0600、nlink1、28815bytes，未读内容；默认工具沙箱的65534映射另记，不当成真实owner。当前resolver额外只读SHA相同，不延长旧观察窗口。

派生检查在本包results/post-run-readonly.json、post-run-systemctl.json、host-ledger-lstat.json，原封印和回执字节不改。内部配置、进程/内核详情、回执及相关哈希仅留本地，不发布GitHub。

## 后继与验证口径

本轮只做纯元数据验证及只读检查，未重跑已消费Node/网络案例。此前准备组合217项及8文件静态检查见[准备证据](issue-167-node-diagnostic-preparation.md)，不登记成本轮重跑。新结果独立未绑定，不扩历史分母/required/正式回执；本轮链接/diff与最终固定scope含collect审计另记回记，未运行完整离线门禁。

下一步直接准备真实公共prepare_launch的合成六格正常批次：完整use_install/配置选择、真实资源预arm/终态/删除/历史与认证前合成边界检查仍须具体接线。原实验库的新配置/选择写入及恢复必须列入待审影响，不偷换description.audit_snapshot_id或拿本例窄投影替代完整use_install。所有者已确认下一包的专用认证目录由其维护，仅授权准备；未授权访问内容、认证/刷新或模型请求。真实Pi、供应商能力/故障、H5及产品激活仍保留，产品缺证据阻断不变。
