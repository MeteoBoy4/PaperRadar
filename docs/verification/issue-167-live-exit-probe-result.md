# #167：监督退出完成、artifact清理未完成

## 身份与总结果

所有者执行了[已封印的单次监督包](issue-167-live-exit-probe-preparation.md)。run=`d5f2a9017c84`，review-seal SHA256仍为 `464ac510a4b082530f7a7624195c743a1bea6a42a77618b3e96dd97f7068ed87`。本地受控results/owner-run.json SHA256为 `f2b16800fa8078b675cdc863a98c016160879365c4ef0dd6557043eb3f99b59c`；manifest、14成员、12个字面安装文件、config及完整driver一致，fresh只读复核得到相同结论。

整轮结果 **unknown**、owner_exit_status1、artifacts=null。退出接缝已有严格成功事实，随后artifact阶段未完成；不自动重验，不把后续仅清理改判为原run通过。[原六格](issue-167-live-six-result.md)和其unknown、消耗、认证目录保持。

## 已取得的有限事实

ready/terminal都为count1、integrity complete、core_zero/NNP/caps_zero成立。原phase_gate(exit7)记录write_complete、gate_published=true；wait_exit记录complete，独立cgroup观察为空。卸载前manager投影为：

| 条件 | 观察 |
| --- | --- |
| ActiveState / SubState / Result | active / exited / success |
| ExecMainCode / ExecMainStatus | 1 / 0 |
| MainPID为0 | true |
| ControlGroup为空 | true |
| cgroup进程集合为空 | true |

这些满足原严格谓词，不使用卸载后的默认Result。运行的是无秘密Python worker，auth_model_calls、network_operations、database_operations、nft_operations全部0，没有Node/Pi、认证或模型请求。它只证明本次未来监督接缝的有限现场事实，不解释旧e93的具体原因、补旧退出证据或替代Pi/网络全链。

## 恢复与遗留物

受控restoration为unit_absent=true、cgroup_empty=true。封印源码只有在restore返回且严格相等后才保存这两个字段；后续remove_artifacts仍在同一try内，因此其失败也会写入旧聚合字段restoration_error=restoration_unknown。不能仅据该字段把已经保存的unit/CG恢复误读为失败。

普通用户只读manager复核为not-found/inactive/dead/MainPID0，Fragment/DropIn/CG/User/Group空；精确本unit文件（/etc与/run）及CG目录缺失。该查询只确认当前停态，不倒推先前退出。

普通用户lstat显示代码12文件及顶目录仍完整，runtime的root/worker/ready.json/terminal.json/gate-exit.json仍完整，共18节点。代码根dev66306/inode42214959，runtime根dev29/inode71800。永久账本dev66306/inode1052844、普通0600、nlink1、999bytes保留。工具sandbox把host root UID/GID映射为65534，不将其当实际宿主owner；agent不读取账本正文、日志、core、凭据或进程环境。

根据公开owner回执删除仅由local driver新增的owner_exit_status字段，再按封印write_ledger的sort_keys JSON加LF派生999bytes，预期SHA256为 `d4e5d06685fcc927a3d2250c82a7163b7549a08fab725bdec210fa862fc14e1f`。这只是供后续root核验的预期字节，不冒充agent读取过私有账本。

## 只读诊断的归因边界

在临时合成树上调用封印真实清理路径，普通绝对root的mountinfo可清理；仅把同条nsfs记录第4字段改为mnt:[数字]，会在首unlink之前以mount_metadata_unknown拒绝并保留整树。现时普通host用户自身mountinfo的3条nsfs记录正是该非路径root形式，第5字段mountpoint仍为绝对路径；默认工具sandbox没有这些记录，因此前轮临时目录正例没有暴露此差异。

仅在内存中允许nsfs+mnt:[数字]的窄例外后，树外目标可清理；同形式但mountpoint位于目标树下仍artifact_mount_unknown、无删除，空/畸形输入、非nsfs标签或相对mountpoint仍unknown。具体红/绿和结构摘要留本地 `.scratch/issue-167/live-exit-d5-cleanup-diagnosis-v1/`，不是新现场执行。

这证明了一处具体实现错误，且与本次“artifact未完成、两树完整”吻合。原sudo执行时的mountinfo字节和原异常没有保存，不能据当前普通用户命名空间采样断言唯一实际根因。前瞻修复及独立D1另登记，不回写原封印/结果。

## 后继

只准备新的18节点artifact清理包：unit/CG须已缺失，不start/stop/reset/reload、不访问nft/resolver或数据库，不重发worker/认证/模型；保留两次原unknown、账本和全部回执。前瞻修复、独立D1与具体封印见[清理续办](issue-167-live-exit-cleanup-followup.md)，fresh审阅后按H1由所有者执行，本文件不授予root删除。

实际Pi中断、实际Pi墙钟/网络挂起、供应商错误、参数效力/日期映射/限额、H5与产品接收/人工激活仍待。普通产品阻断和Live待探索不变，未运行完整离线门禁。
