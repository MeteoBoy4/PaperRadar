# #167：六格遗留目录仅清理结果

## 授权与身份

所有者对[后续取舍](../../intent/review/issue-167/live-six-exit-decision.md)明确裁决「H4：A，采用有限事实」，并确认执行了本次H1仅清理包。采用的是六格正常调用的有限事实；[原现场批次](issue-167-live-six-result.md)仍unknown，成功退出缺口独立保留，已消费六格不退款/重发，不推定H5或产品准入。

包 `.scratch/issue-167/live-six-e93-artifact-cleanup-v1/` 的review-seal SHA256为 `6a6ecea81fd76275fc9784e5c5c7edf5b432d2f18ae5a525c7be6cdba3f278f9`，与[离线交付](issue-167-live-six-exit-followup.md)相同。owner-cleanup.json SHA256为 `8d615fd935fb007487aa25c38e4fc2afac572e3f8bdad3f6cc59a308f53d66b5`。execution-started绑定原manifest，manifest/三成员/driver/嵌入source和config一致；本轮不是新的认证/模型批次，也不新增实验调用额度。

## 结果与独立只读复核

受控清理回执为 `code_runtime_removed`、owner_exit_status0、removed_members_including_roots240，恰为原代码42与runtime198节点（均含顶目录）；original_experiment_result仍unknown、original_ledger_unchanged=true。auth_model_reexecs、network_operations、database_operations、service_mutations、nft_mutations、budget_refund全部0。

普通用户只读lstat独立确认 `/home/paperradar-probes/issue167-e93f7b82c461` 和 `/run/paperradar-issue167-e93f7b82c461` 均不存在；原永久账本仍在，dev66306/inode1052843、普通0600、nlink1、109292bytes及mtime/ctime与封印身份相同。工具sandbox把host root UID/GID映射为65534，不能把该映射值写成实际宿主owner。agent只核元数据，没有读取账本正文或计算其实际字节SHA；字节未变来自所有者root入口的前后核验回执。

原 `.scratch/issue-167/h1-live-six-v1/results/owner-run.json` SHA仍为 `50816d0838ef645196165d7943bb2b0d02382ce98c430b4fc6ab28e9d1cf7750`，内外层unknown和原failure字段不变。按公开preflight_result及旧write_ledger格式派生的109292bytes预期SHA与清理封印一致，不冒充读取过root账本。原现场包、单次记录、认证目录和已有缓存均保留。

fresh独立只读复核得到相同结论，无root/live动作、无凭据/日志/core/进程环境读取。清理执行权限和实际动作来自所有者；agent没有sudo或追加删除。

## 后继边界

该结果只闭合两棵遗留目录的清理，不补原监督退出证据，不把原run改为passed。按H4 A继续离线准备无认证、无模型的监督收尾验证，具体新unit/路径、计数、停止和恢复仍须封印后另交H1；本次清理许可不授权它的执行。

其余参数效力、日期模型/订阅限额、外部中断与真实墙钟/网络挂起、供应商错误、H5与产品接收/激活仍待。普通产品缺证据阻断和Live待探索保持。
