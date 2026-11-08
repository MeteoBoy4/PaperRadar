# #167：监督probe的18节点仅清理完成

所有者执行了[原范围仅清理包](issue-167-live-exit-cleanup-followup.md)。本地目录 `.scratch/issue-167/live-exit-d5-artifact-cleanup-v1/`，review-seal SHA256为 `17e8fd2be2140de7d1c549fb20653e0977eadbed595f0b03ab69a7371f5f8770`；owner-cleanup.json SHA256为 `34399d1bddc16d0bea2302627496a9d6e8197d89308a99502976b73b1e6b945d`。封印、五成员、driver、字面两源码/config与原scope一致，execution-started绑定原manifest。

受控回执为code_runtime_removed、owner_exit_status0、removed_members_including_roots18，恰为代码13与runtime5节点。original_experiment_result仍unknown、original_ledger_unchanged=true；原账本写入、auth/model或synthetic worker重执行、网络、数据库、服务变更、nft及预算退款全部0。清理不把[原监督run](issue-167-live-exit-probe-result.md)或[六格run](issue-167-live-six-result.md)改判passed。

主代理与fresh独立只读lstat均确认两树已缺失。原账本dev66306/inode1052844、普通0600、nlink1、999bytes、mtime/ctime与封印相同；sandbox的UID/GID65534映射不当作实际宿主owner。agent没有读取账本正文或实际计算其SHA；字节不变来自所有者root入口的前后核验，公开回执派生预期SHA仍匹配。

原d5 owner-run.json SHA `f2b16800fa8078b675cdc863a98c016160879365c4ef0dd6557043eb3f99b59c`、原e93 SHA `50816d0838ef645196165d7943bb2b0d02382ce98c430b4fc6ab28e9d1cf7750`保持，结果均unknown。新只读投影另存results/post-cleanup-readonly.json，不改原字节、永久单次记录、认证目录或消耗。

这次清理闭合两棵遗留目录；本轮没有重跑服务、SIGINT/300秒控制或真实认证/模型，没有访问凭据、进程环境、日志、core或业务数据库。此前修复的176项相关回归见准备材料，本轮不登记为重新运行或扩大旧覆盖。链接/diff与只读固定scope审计按本次收口记录，未运行完整离线门禁。

下一步仅准备独立E01外部SIGINT案例与剩余H4材料。监督退出的有限现场事实和两个原run的unknown分别保留；任何新部署、认证、刷新、模型或故障现场动作仍须具体H1/H2/H3，H5及产品接收/人工激活仍待。普通产品缺证据阻断、Live待探索保持。
