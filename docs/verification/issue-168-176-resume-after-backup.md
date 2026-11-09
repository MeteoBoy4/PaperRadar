# #176 before-revoke backup之后的独立同盘续行

本补充处理已完成前两次人工证据激活、已产生原4保护文件、尚未完成product_log_probe的精确状态。
它不改已部署39源码、v4清单／runtime、旧包、历史台账、既有scope／中央hash，不触发新cutover／receive或业务预算变化。
实际原plan/RID/保护文件及预算仅由主代理只读提供约束索引；普通JSON不是grant权威，root新程序须回到保护来源核验。

## 真实无root red与适配

/tmp合成replacement与worktree.scratch内0555目录的synthetic target位于不同文件系统。
实际replace与hardlink均先得到EXDEV=18，原probe的EACCES／EPERM断言因此red，target原字节不变。
不能把EXDEV当保护通过。新程序验证既有标准临时目录/var/tmp的类型、root:root、1777，以及与保护日志相同device和fdinfo mnt_id；
仅作用域设cached tempfile.tempdir，调用原冻结v4 probe，finally还原。真实普通用户fork模型证明子进程清env后仍使用所选同盘目录。
原6个实际syscall、严格EACCES／EPERM和NNP helper失败检查全部保留，不动态改源码或放开日志祖先。

## 续行边界

独立包由非特权生成器内嵌新workflow/config/卸载脚本字节；显式经典sudo、正常TTY、一次密码，root不打开用户可换链来源。
先核原runtime完整闭包、payload／manifest／原owner/config SHA、保护链、入口和sudoers，再仅从root新冻结副本运行。
preflight读取原exact4保护文件与backup并核SHA，使用原show_plan权威核digest、窗口、预算零／单轮与两种plan_stopped来源，
保护RootSnapshot核当前原RID两组raw active集合／无其他active／无revoke，保护否定日志须有效pending0，原锁须空闲。
原初始／drill检查点必须证明同一集合，业务预算必须与保护business-before全部一致；刷新原观察后再核资格／预算。

只从probe继续：helper失败意图持久化→原checkpoint→原helper revoke→原restore（复用原backup，不再backup）→最后本人boundary ID一次。
原4文件／backup不改并最终复核，前两次授权不重放。共享投影、不可逆撤销与恢复权威直接复用原v4，不能靠约束JSON或总布尔放行。
只在最终原非空集合active/qualified、临时格仍撤销、预算不变时写保护安全回执，记录续行与实际probe结果及原事件／主张。
失败输出精确stage／受控reason并新增恢复工具failure检查点，不吞成generic；不写completed、不自动修复、删除或grant。
卸载只原样归档本新工具，保原全部部署／数据／checkpoint／backup／日志；不在失败时自动卸载。

## 独立未绑定覆盖

| 模块 | 人工节点数 | 覆盖 |
| --- | ---: | --- |
| `tests/test_owner_resume_after_backup.py` | 27 | cached同盘清env1、真实临时Ledger/原API续行只末次确认1、起始变化11、probe失败2、temp/mount失信4、锁1、精确失败检查点1、restore失败1、封印换链/归档2、device mismatch1、普通CLI1、刷新预算变化1 |

没有镜像许可常量；临时Ledger、保护log、原CLI／helper解析／restore／共享投影均真实执行，只有OS/子进程边界为fixture。
真实站点与syscalls由owner未来执行，离线模型不自证本机保护通过。原4文件字节保留、只最后boundary CLI、其他失败不进入mutating tail均有断言。
新模块27单列，与先前32／495的当前人工并集可列33模块522节点，不追溯扩大旧分母或required。

当前新模块＋原D7六＋预算17＋链接四共**54passed／2.70s**；
新增三Python的Ruff／format及mypy（带原service解析）通过，collect核对27，最终原D7／链接核对通过，git diff --check通过。
没有执行实际sudo、root、收紧／恢复／激活、认证／模型／网络或读取真实业务DB／侧文件；没有改原4文件、backup、log或预算。
新root包仍须最终主树重建并绑定明确SHA后由owner完整审阅执行，当前实际24 raw active／pending0不由这些fixture代签完成。
原39/v4字节保持，真正兼容／scope授权／完整门禁仍由主代理串行，未关闭#176/#168。
