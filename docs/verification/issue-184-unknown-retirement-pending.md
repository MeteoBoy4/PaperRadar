# #184 未知退休临时记录独立 D1 覆盖

本轮 Spec 审阅发现：新的一跳恢复只核对已知临时文件，未知第三 payload 的
`placement-retirement-v1-*.json.new` 未被阻断。按
[ADR-0066](../adr/0066-recover-preparing-placement-across-source-payloads.md)，
仅新增 `preparation_recovery` 接缝在认领与任何写入前拒绝这一类目录项；
不读取未知正文、不遍历其链接目标、不删除或自动恢复记录。原默认入口保持既有语义。

| 独立未绑定模块 | 节点数 | 公开接缝及覆盖 |
| --- | ---: | --- |
| `tests/test_preparation_recovery_pending.py` | 16 | `FailedPreparationRetirement.check/prepare`：8 个新恢复负例（两个入口各核对未知普通文件、指向 ledger 外目录的软链、目录、非法摘要名）；4 个原来源默认入口兼容例（每例同时执行 check/prepare）；4 个精确 own/source 临时日志受控原因及保全回归 |

合计 16 个独立节点，未扩大原 83 节点台账、历史固定分母、旧 required 集合或旧组回执。
各拒绝例断言 `failed_preparation_pending_file`、无 own journal、零 kernel 写入、
idle/preflight 均未触发。全合成树比较包含原日志、snapshot、ledger、inbox、MAIN、
未知目录项及目录外软链目标的 bytes/link target、mode、uid、gid、链接数、size、mtime、ctime；
只排除只读操作可能改变的 atime。默认入口允许既有 own journal/共享 marker 正常推进，
其余内容与元数据继续保全。

修前公开入口 8 个负例实际全部因未抛出预期拒绝而失败。开发期树外启动器显式验证当前
worktree/src 导入，使用 v22 显式 84 成员及当前字节摘要，保留原 `assert_source_guard`
算法；不修改历史向量或 pin。此结果仅证明离线模型行为，最终 v23 冻结后必须由原 pytest
入口重跑全部新增节点。未进行完整门禁或真实 root、kernel、namespace、scope、认证、
模型、网络、receive、安装或激活操作，不证明现场恢复成功。
