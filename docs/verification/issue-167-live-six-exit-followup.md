# #167：监督退出前瞻诊断与仅清理离线材料

## 证明边界

[原现场批次](issue-167-live-six-result.md)仍unknown。此处新增两个独立未绑定D1模块，既不进入旧分母/required/正式回执，也不修改原执行包、结果或永久单次记录。无新Node/Pi、网络、认证/刷新/模型、root、真实库写入、安装锁或崩溃；合成树和错误注入仅在临时目录。

## 监督退出诊断

`scripts/issue167_live_owner.py` 前瞻区分 exit_gate 与 exit_wait，保存封闭枚举的 gate写入检查点、publication、manager状态与cgroup空投影。发布后目录fsync失败只表示write_intent/publication，不能冒充函数完成或持久性成立。缺字段、重复/未知枚举、畸形数值、非零退出、中断与观察失败仍unknown；成功仍要求原有严格manager成功退出及cgroup空，不增加宽松成功分支。

`tests/test_issue167_live_exit_diagnostics.py` 独立 **38项**：包含真实run_owner→phase_gate链在/tmp的发布后fsync失败、纯mock manager查询失败、严格成功控制，以及状态拒绝、恢复与诊断失败路径。修前已观察回归失败，修后与原batch67组合 **105 passed**；fresh独立复核同为105 passed。输出不保存任意stderr、异常原文、PID或cgroup路径。

这些改动只改善未来可诊断性，不证明已找出或修复原e93实际原因。未封印或执行新的监督现场重验；其具体材料和H1仍待。

## 遗留目录仅清理

新的 `scripts/issue167_live_artifact_cleanup.py` 只供所有者按新H1执行，精确绑定原run的代码/runtime两树、旧manifest40成员与工具、永久账本身份及公开回执所派生预期SHA、固定控制记录、完整metadata清单。旧账本由root核验不导出内容，不写或删。服务/规则/cgroup须已撤且只读复核；不通过调用原finish改判结果，不启动/停止服务或修改nft。

所有树先完整检查并持有逐层NoFollow目录FD；读取固定公开控制元数据通过pinned dir_fd，实际打开的FD身份在任何read之前核对。其余后代仅看metadata，删除只用相对unlink/rmdir；拒绝alias、陌生成员/owner、跨设备与挂载。所有目标两阶段核验后才删除，后验仍须原账本不变和host停态。删除中途失败可留下部分树，继续unknown且不自动重试。

fresh审阅发现初版固定控制记录读取只保护末级，已用/tmp合成外部文件重现可写祖先符号链接反例；交付版已修复逐层及打开窗口替换，不把读后hash拒绝当作读取安全性。`tests/test_issue167_live_artifact_cleanup.py` 独立 **29项**通过，覆盖祖先替换前/后和open窗口替换均在body read前拒绝；fresh独立重跑29项并终审无剩余阻断。

最终本地待审包 `.scratch/issue-167/live-six-e93-artifact-cleanup-v1/`；review-seal SHA256为 `6a6ecea81fd76275fc9784e5c5c7edf5b432d2f18ae5a525c7be6cdba3f278f9`，manifest为 `8dba79fe8d160dcb7a4590725742be683b51f2d7ca92db4465eb960ae7d7665b`，driver为 `4da83b5f239ff4d006bc284a2f742d811557739a096a57f5dfe7e6b3afa77f2b`。三成员、workspace源码、root字面stdin的source/config逐字节一致；清单code42/runtime198节点，均含顶目录。bash-n及移除唯一main调用后的封印loader加载控制通过；results仅有offline-validation.json，没有execution-started或owner-cleanup，未预占、未执行。H1获批后所有者入口为 `bash .scratch/issue-167/live-six-e93-artifact-cleanup-v1/owner-cleanup.sh`，只有一次sudo TTY密码；不自动重试，删除中途失败仍可留下部分树并报unknown。

新D1为exit38、cleanup29，与既有batch67相关组合 **134 passed**；四文件mypy（MYPYPATH=src）、Ruff check/format通过。链接/diff通过，固定scope含collect审计退出0、issues/affected_groups空、skip/deselect0，未运行完整离线门禁。所有新包、metadata、绑定和回执只留本地；本文件不授予root执行、额外调用或产品准入。
