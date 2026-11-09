# #168 / #172：G2 三项摘要后停止的诊断与续跑边界

本次覆盖部署检查点诊断与独立owner预配方案；不替代[原β采集台账](issue-168-172-site-collector.md)。
新测试独立未绑定，原27节点、历史台账、旧scope、中央成员/哈希和准入策略v2/33源码守卫保持。
新消费闭包交#176登记；本次不关闭#172，不执行完整门禁、真实sudo、collector、receive或证据激活。

## 独立seams与人工分母

| 独立新增模块 | 人工预期节点数 | 责任 |
| --- | ---: | --- |
| `tests/test_site_deployment_checkpoint.py` | 10 | 完整bootstrap→三SHA→deploy的foreign-cwd受控拒绝及零部署副作用；owner空cwd预配拒绝非空/链接/其他属主/权限/不安全祖先；竞态成员保留；封印owner-workflow组合链及重复执行/卸载保留；runtime.new诊断与保留 |

另有独立`tests/test_site_g2_entry.py`，人工预期9节点：真实run-g2单入口/单sudo -k、
root冻结workflow/阶段/receipt且无G3、包篡改在sudo前拒绝、非空/链接/其他属主/不安全祖先四格拒绝，
collector失败不receive，用户校验后篡改由root二次SHA拒绝。
本次新增合计19节点，与原27节点分开，不扩大旧分母。
原`test_site_deployment.py`8节点保持，artifact集合保留旧7项并追加run-g2/owner-workflow，
REVIEW入口预期按用户最新单入口要求同步；不改历史A1–A10产物/分母。

`tests/site_deployment_checkpoint_support.py`复用原无root模型，仅替换路径、uid/chown/install/visudo等OS边界；
实际运行生成的shell与REVIEW命令。chown替身只记合成标记；不构成真实OS所有权、降权或抗竞态证明。
合成payload不包含真实collector，不接触用户业务库、认证或历史受保护记录。

## 根因与红绿

反馈链先复现用户确切症状：完整bootstrap校验三项SHA均OK，deploy退出2，stderr为空。
最小模型只需合成payload与既有产品uid所有的空cwd；一次约0.7秒，确定性可独立运行。
按diagnosing-bugs先展示四项排序假设，再单变量验证：

- 只把模型cwd属主从产品uid变为root，原链返回0；保留产品uid则返回2。
- 增加cwd内容不改变前面的属主拒绝；root属主但非空会在后面的空目录检查拒绝。
- 篡改payload或留下runtime.new可触发其他停止点，但只读现场没有runtime或runtime.new。
- 直接运行deploy的受控trace最终为`[ 1000 -eq 0 ]`后exit2，排除bootstrap摘要或执行位置导致本次停止。

现场仅只读stat/lstat与目录项：部署祖先保护满足，固定cwd为产品uid/gid、0700且无成员，
入口/runtime/账本尚未出现。宿主路径/详细元数据不放公开工单；不读取auth/cache/日志正文或旧probe记录。
受限视图将root属主映射为65534，另以获准的宿主只读stat核对，未把映射值误判为真实属主。

正确安全行为是拒绝产品所有cwd；产品缺陷为无可操作诊断。正式回归先观察1 failed（stderr空），
最小修复后通过；原完整链复跑保持退出2和三SHA OK，并给出
`protected_owner / stage=preflight / resource=cwd`及所有者下一步，cwd与部署目标不变。
普通deploy的属主、模式、链接、摘要、固定位置和空目录检查均保留。

## owner续跑范围

公共行为以[Live evidence Contract](../contracts/live-evidence.md#β-站点采集与封印部署)为准。
新REVIEW只给一个run-g2.sh普通用户入口；所有者审阅后输入一次sudo密码，其余G2步骤由脚本执行。
Agent只生成、不执行。run-g2先核四SHA，再一次sudo -k复制并复核owner-workflow/deploy/uninstall/payload，
只执行root冻结workflow；无额外read确认或手动命令。持续输出阶段、receive的receipt_id及G3未执行。
既有cwd不由普通部署自动收编。owner预配对非空/链接/非预期属主或权限/不安全祖先均拒绝；
改变所有权后再查空目录，竞态后检失败保留成员并停止，不删除或回滚；预配cwd默认卸载保留。

本次现场只到staging，没有开始采集，可在owner审阅新包与预配动作后从run-g2单入口重新开始。
这是由本次元数据限定的判断，不能推广到其他部分部署：runtime.new保留待owner核对，
不同payload的已装runtime须先沿所属旧脚本审阅卸载，账本/回执/失败/stopped/撤销/预算保留。
已开始或stopped计划不因修复包自动重试；新计划须明确批准，不能重放旧失败或恢复旧激活。
G3仍由owner独立逐格审阅/短ID确认；β的模型/RPC/IPv4/observer缺口保持unknown。

旧g2-final包保持原字节。合入integration后仅从最终主树生成不存在的独立repair目录，
重核HEAD/tree/dirty、source_worktree、345源码清单、lock/Python/collector/payload身份与所有SHA。
候选worktree的身份与测试结果不能替代新主树正式包；脚本/REVIEW字节变化重新审阅，旧SHA授权不迁移。

## 最终开发验证

- 本次19节点、原27节点与D7源码守卫4节点：**50 passed in 7.97s**，退出0，无skip/deselect/incomplete。
- collect-only核对人工10+9节点；六个变更Python文件Ruff、格式与strict mypy全部通过，git diff --check通过。
- 最初完整三SHA反馈链最终复跑：仍退出2保护原cwd，三SHA OK后明确输出受控owner/preflight/cwd诊断。
- 单入口先红（入口生成器缺失），后绿；sudo替身记录严格一次`-k`，实际生成的shell完成四SHA与冻结workflow，
  合成collect→receive两项事件、receipt_id和G3未执行均可观察。用户校验后篡改workflow仍由root二次SHA拦住。
- `check-compatibility all`：**65 failed、111 passed**，176节点，入口406.03秒、退出1。
  首个失败为`test_a2_full_entry.py::test_one_plan_produces_seven_bound_files_and_never_inherits_previous_success[passed]`，
  最小重跑本工作树1 failed/3.34秒，未改integration基线同节点1 failed/3.06秒，均为scope_drift及下游前置拒绝。
  其余兼容失败未逐节点重跑完整基线，交#176继续核对；不能称兼容组合通过。
- 显式base/target只读scope审计退出1，只有原cli.py、contracts/schema.py、pi_supply/cli.py三条
  baseline_drift/source_support，没有current_change登记漂移；不为消警修改旧scope/中央哈希。
- 旧g2-final部署、卸载、payload的三项SHA逐项与原记录相同；宿主cwd仍产品uid/gid0700，staging脚本仍root0644。
  无真实sudo/collector/receive/revoke/activate，无认证/模型/网络调用，无EXP2写库/compile/Pi重建或重装。

这些是工程回归与只读现场定位，不证明真实root权限、实际降权/隔离、当次collector/receive或G3已执行。
