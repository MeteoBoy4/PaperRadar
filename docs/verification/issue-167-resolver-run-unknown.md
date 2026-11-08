# #167：resolver/window 整例 unknown、仅恢复完成与前瞻修复

本轮复核所有者已运行的[无网络H1包](issue-167-service-observation.md)，优先处理恢复残留。没有补跑原案例、自动退款或新增DNS/TLS、Node/Pi、真实凭据/认证/模型/崩溃。内部配置、内核和进程细节仅留本地。

## 原案例的实际通过部分

run=`c591eb6ad204`，原seal=`021c03cec08e4f4f3fec2eeb03e577fbebbd96d899635ac16d11a69e83333c1d`。owner-run.json SHA=`a0eec245a46a9efadcd1a39d7940e61385f6562aa32a5e920372e6206a8af18a`；owner_result及inner整例结果均unknown，restoration_error=restoration_unknown、artifacts=null，不标成整体通过。

受审root程序已接受worker明细：UID1000、NNP/cap空、core[0,0]、实际cgroup匹配和私有resolver SHA；worker与root-caller的mnt链接不同、PID namespace相同。namespace来源不是实际handler，不执行Apport或重新制造core。

两个synthetic Python exec各1；12个chain布尔均true，包括原FD继承/共享offset、父close后独立EX拒绝、子退后EX允许、匿名marker传递、子core/CG/resolver/NNP和不同session。真实inotify加kernel-own CG门槛的窗口为window_complete：mutation_events3、terminal_regular_files1/other_entries1、独立directory_deleted=true、post_terminal_mutation_events0、reasons空。不是实际Pi或production prepare_launch组合，不外推任意逃逸或全部写入渠道。

原Root回执保留5份已验本表kernel JSON：created_deny、activated、cleared、reactivated、post_stop，允许/拒绝packet均0。原独立live cgroup2 binding和稳定handles保留；source profile/namespace/CG信息可复核。规则结构通过不等于允许/拒绝流量对照。network_operations、Node/Pi、真实auth/model计数均0。

## 恢复失败的位置不能唯一回填

post_stop只在stop、CG空及bound全表核验通过后追加，因此可定位到其后。后续delete、inventory、scope检查或reset-failed等不同失败点，都能留下“post_stop已到、unit仍在”的状态；fresh只读审阅用真实restore调用点加纯mock分别复现三种情况。原stderr被丢弃且没有恢复子阶段，不能认定真实原因必然是reset/GC。

普通用户观察到原unit loaded但inactive/dead、MainPID0/CG空，fragment尚存；实际CG目录absent。没有为了诊断调用reset/start/stop，未读日志或原异常。

另一个确定的证据缺口：原global_resolver_sha仅在旧root进程内存，没有写入runtime/ledger/result。Case.resolver_sha256是私有绑定文件，不能替代原全局baseline；当前读到的配置或源代码“不写全局”也不能回填一条不存在的before/after测量。

## 所有者已执行仅恢复，原整例仍unknown

审阅包 `.scratch/issue-167/resolver-recovery-c591-v1/`，seal SHA=`dc57078b7ac74ad28a82c4b6fd9753279b1b1f46d89ada42075f3552d6d93833`。所有者报告「已执行仅恢复脚本」。该脚本只用原Root source/core、Root600原ledger/binding、固定profile/unit字节与状态核对归属；现表若存在才按enabled=True、原独立ID/稳定handles和counter0全验后删除，再精确unlink unit/reload。没有start/stop/reset或重新exec合成角色，不需要numeric例外。

原publisher格式从已有envelope派生预期ledger SHA=`22d174ef487684a5278d09796ebd495239e7fbb83b3a3b5a86c60c02ab999330`、binding SHA=`96c0998f0d4db4c3a628346e8166cdafd67d9b94e9d57fe25df06d4560a2781c`；普通用户没有直接读取root600内容，实际匹配由owner Root代码完成。原记录在恢复前后保持相同SHA，未改写unknown或删除旧消耗。

recovery-result SHA=`c8a27582244e4edcef9168e37c9e4b5b6b23764fbf31e7133442b8e457b80a38`：restoration_result=project_resources_removed、original_experiment_result=unknown、original_global_resolver_baseline=unavailable_not_reconstructed、ledger unchanged、code/runtime retained、network/synthetic_reexecs0。回执确认表已不在，未记录恢复入口时表是否存在；不能据此唯一断言原删表失败或本次实际删过表。

普通用户独立复核unit not-found/inactive/dead、MainPID0、fragment/dropin/CG空；unit文件和CG目录absent，原代码/runtime仍在。恢复前后当前全局resolver只读SHA相同；明确该比较只覆盖本次仅恢复，不覆盖原实验。记录在恢复包results/pre-recovery-readonly.json和post-recovery-readonly.json。原完整H1仍unknown，项目残留策略已移除，两者分开。

仅恢复source新增未绑定D1 `test_issue167_resolver_recovery.py`9项通过；fresh审阅另做7个纯mock表路径。三成员/源代码/字面stdin逐字与seal一致，bash-n/语法通过，root动作由所有者执行，agent未代执行。

## 前瞻修复，不修改已执行字节

workspace owner源码为未来案例增加：

- reserve在安装/启动前原子保存Root0600 resolver-baseline.json，严格run/SHA/mode/nlink，恢复时读回再比较；缺失、坏值或漂移均unknown。
- 闭集restoration_stage及真实before/after resolver_check及来源进结果/ledger，成功finish删runtime后也不只剩布尔。
- unit已inactive/dead且PID/CG空时不调用reset-failed；只有failed态才reset并复核。此修复不被当作旧真实原因的证明。

原恢复五字段成功条件、scope先验、CG空后bound核表、永久记录保留均不变。新增独立 `test_issue167_resolver_restore_regression.py`16项通过；旧未绑定owner49项仅适配fake状态/真实形状的基线，节点数/原断言范围不变，不加生产fallback。Root安装、原seal包、旧ledger均不动。

已准备修复后的额外单次无网络待审包 `.scratch/issue-167/h1-resolver-window-v3/`，run=`d840a7e2c619`；新标识不自带余额，不执行前一轮的剩余许可。原c591仍unknown、已消费、不退款。

| 身份 | SHA256 |
| --- | --- |
| review-seal.json | `104f6b7f0d886f3e93c5ceb5927871684bcb2576dddfa9b7f8864ff930d85a74` |
| core manifest | `835b9c34567c845b08c74b9b5fff3bfc90eefa48e254bf5743b3f97f94dd3f45` |
| driver | `f11c0342274065a9631eeb2a993657782a73c0516127ab69dccf0df8646053b4` |

范围仍1个具名unit/项目表、本次只读resolver视图与受保护code/runtime/永久ledger；合成Python角色各1、实际CG/inotify/OFD/规则结构与恢复，DNS/TLS/HTTP/Node/Pi/真实auth/model/崩溃/IPv6探测全0。临时Root owner为sudo管理进程，worker cap空。当前没有新H1执行或预占；须审阅新字节并另获一次授权，root仍由所有者亲自执行，不能以原部分通过推免重验或降低成功条件。

本轮相关组合183项通过，包括owner49、worker18、bundle4、恢复回归16、仅恢复9、服务规则50、观察纯逻辑21/真实kernel4、合成公共启动3、bootstrap8和FIFO1。涉及本轮修改的6个Python文件mypy、Ruff及format检查通过。新增恢复回归与仅恢复模块均独立未绑定，不扩历史分母/required/正式回执。

fresh终审另核对27个core成员、14个复制源码、工具SHA、Case/unit、生成入口与seal；results为空，bash-n通过。基于旧受控快照构造的新成功envelope为14670 bytes，低于driver的131072-byte上限；纯mock证明成功finish后永久ledger仍保留resolver_check。该审阅未执行root/service/nft/network或新现场案例。

本地链接与git diff --check通过；显式base/target的固定scope含collect审计退出0，issues/affected_groups空、collection_skipped/deselected均0，不改旧登记。未运行完整离线门禁。真实Pi/认证模型、H5和产品激活仍未由本轮授予，read_evidence=None及Live/B门槛保持。
