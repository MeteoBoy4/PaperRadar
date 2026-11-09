# 最终所有者方案：v4 cutover、新证据与持久收紧演练

本次所有者已完成已审v4部署及独立after-backup续行，保护安全回执与正式只读采样的有限事实见
[现场安全验证](../../docs/verification/issue-168-176-owner-safety-verification.md)。最终12项站点资格不补齐模型／RPC缺口，精确登记／compat／S3／G4仍待完成。
下文保留各起始状态下的操作与中断边界；不是要求再次执行已经完成的升级或复用旧候选。
任何后续新root字节仍须按准确主树重建／owner审阅执行；代码／离线授权与ADR-0056接受不授权代理实际root动作或完整门禁。
旧v3、旧G2／owner候选及各阶段检查点原字节保留。

## 构建与审阅

非特权构建采用已明确提供的只读站点配置，保留当前供给／实例和六格主张，不compile或重装Pi。
按所有者审阅的**新7天UTC窗口**生成新单轮、首失败停、认证／模型／网络全0计划，不重启旧stopped计划。
最终生成者核对当前HEAD/tree/dirty、Python/lock/source/payload/manifest及准确旧部署身份；候选不是批准。

```sh
uv run --offline --locked python scripts/seal_site_evidence.py \
  --site OWNER_SITE_JSON --starts-at OWNER_START_UTC --ends-at OWNER_END_UTC \
  --output NEW_REVIEW_DIR --upgrade-from-payload OLD_PAYLOAD_SHA256 \
  --upgrade-from-manifest OLD_MANIFEST_SHA256 --owner-closure
```

完整审阅run-upgrade.sh、upgrade/deploy/uninstall/owner-workflow、入口内嵌字节、
payload的冻结解释器／依赖／源码、owner-closure.py/json、site/plan、sudoers与SHA256SUMS。
只读支持性预检检查已知Linux ABI、CAP_LINUX_IMMUTABLE、挂载只读及属性接口是否可用，尽量在归档／cutover前拒绝；
它不设置或清除任何日志属性，不代表真实+a成功。未知状态不降级。
确认暂停业务和其他准入写入、产品uid无等价root能力后，所有者只运行REVIEW指定的普通用户入口，输入一次sudo密码。
root只从内嵌字节冻结并复核执行，大payload由stdin传输；本人确认仅从/dev/tty读取，绝不管道传ID。

## 固定执行与成功判据

1. 精确核旧runtime／manifest／完整成员／权限、入口与sudoers，只核过才原样归档；保所有账本／回执／失败／stopped／预算。
2. 首次日志cutover先持久封闭目录0700，原子失效旧激活并永久撤销旧全部六格回执；不能因普通pending已删当干净。
   独占写带cutover身份首记录，设root:产品gid0660、FS_APPEND_FL并fsync／复核，之后才公布目录0755。
   既有完整日志只核；缺失、满、损坏、不支持或部分初始化一律阻断，不重建／清空／轮转。
3. 由新冻结runtime按新计划采集当前站点、受信接收；按准确plan_id选择root账本中唯一新回执，不读旧探索记录。
   所有者完整审阅并手输实际短ID，首次激活boundary-low非空站点分项；旧receipt永不再活。
4. 所有者再完整审阅并手输同一新回执ID，临时激活独立value-low，独立新进程复核后备份账本。
5. 冻结代码fork并不可逆降至产品uid，只触碰固定否定日志和无秘密临时文件，真实检查删除／截断／覆盖／替换／硬链接／清旗标
   均返回EACCES或EPERM。任一允许或异常即停止；无root模型不代签此现场结果。
6. 仅该产品子进程设置不可dump与no_new_privs，使固定sudo helper不能提权；经正式request_revocation追加value-low收紧并必须观察helper失败。
   root新进程共享loader核pending且当前active／qualified已拒绝，原raw_active及原核验时间独立保留；不能绕过日志直接evaluate自证。
7. root固定helper不可逆撤销value-low，新进程复核；合并恢复备份，核全部激活失效、日志与撤销仍保留，业务预算身份／计数不变。
8. 所有者第三次完整审阅／手输ID，最终重新激活boundary-low。每次激活前及确认后均真实刷新60秒观察，不续原verified_at。
   最终原非空站点分项集合active且qualified、value-low仍撤销、预算不变，才写受保护安全回执。

安全回执记录原主张／时点、绑定摘要、用途／登记／到期依据、激活事件、产品权限拒绝与helper失败持久性结果。
原始active与当前资格分开；模型／RPC／IPv4／observer缺项仍阻断，不把部分站点激活写成整体可执行。
预算仅稳定只读主文件的必要ID／指纹／代际／attempt计数，保留全部前后比较，不读payload/token/全文/auth/cache正文。
业务任务与其他写入须先暂停；允许无侧文件或可信0字节WAL＋可选可信SHM，journal／非空WAL／单独SHM及失信仍拒绝。
只lstat侧文件，不读其正文，不删除／checkpoint／切journal模式；路径和fd的inode、类型、链接、权限、uid/gid、
大小及纳秒mtime/ctime在打开、各查询前和结束核稳定。atime可受自身只读访问影响，不作内容变化判据。
immutable跳过锁与变化检测，只用于读取主文件；它不保证并发安全，不能代替暂停和显式稳定性复核。
保护账本的hot-journal及其他sidecar拒绝不放宽。
NNP仅作用子进程，不改root或sudoers；全流程无认证／模型／网络，不刷新预算，进程重读不证明主机重启。

## 中断与恢复边界

每一步把有限检查点保留在root账本下唯一closure目录；未知／失败／中断不写completed安全回执，不自动回滚、删除或授予。
预检拒绝时旧runtime不归档。设置+a前后才发现的支持性或I/O失败，可能已经cutover：旧资格继续撤销，
目录／日志保持部分状态并阻断，由所有者保留现场及准确checkpoint后另行审阅恢复方案；同包不会自动补完或重建。
恢复屏障之后未最终激活时保持无资格，必须本人重新完整审阅有效新证据，不能用旧短ID或旧active报告翻转撤销。
默认卸载／重装保留否定日志、账本、回执与runtime归档；不通过清文件“修复”准入。
最终实际部署／权限／激活及G4完整门禁仍由主代理按各自授权串行完成，未执行时不关闭#176/#168。

## 已部署同SHA流程的终端中断后恢复

停止不等于长I/O。若Python为T且存在本人已请求的SIGINT，必须先由所有者按精确进程组处置，
让待处理的中断完成并退出；不能承诺CONT后继续原激活，也不由代理发送信号。
随后只读核验旧链全部退出、closure.lock无持有者，不能重跑已完成的run-upgrade.sh。

仅在这些条件全部满足时，使用已经核过的**同SHA root冻结脚本**复跑：

- payload、manifest、owner-closure.py及完整运行树保护和摘要仍精确匹配本次owner审阅记录。
- 原config的policy、plan、receipt、run_name一致；plan有效且未stopped，新receipt最新、未激活、未撤销，无其他active。
- 当前deny log及cutover身份受信且无阻断该新receipt的意图，保护账本无journal/WAL/SHM，closure.lock空闲。
- 原phase目录尚不存在，业务任务与其他写入继续暂停，当前业务预算采样前提仍满足。

所有者从有正常交互TTY的新终端显式使用已核的经典sudo入口，不改变全局alternatives、sudoers或安装包：

```sh
/usr/bin/sudo.ws -k -- /usr/bin/env -i \
  /usr/libexec/paperradar/live-evidence-runtime/python/bin/python3 -I -S -B \
  /usr/libexec/paperradar/live-evidence-runtime/owner-closure.py
```

该入口只复跑原冻结owner流程，使用原config；不再部署、cutover或接收新证据。
原流程仍会核账本／锁／用途／状态，按原计划真实刷新当前观察，并要求三次本人完整审阅和手输ID。
原终端的输入回显不是证据激活事实，不能复用为自动确认。原verified_at、停止条件和预算均不刷新。
若任何前提不同，或已有部分激活／撤销／phase目录，停止并另审实际检查点，不删除文件、清空日志或自动回滚。
终端模型及外部sudo-rs限制见[诊断台账](../../docs/verification/issue-168-176-owner-terminal-recovery.md)；
诊断模型不证明现场已恢复成功，仍以新的root安全回执和最终人工激活事实为准。

## 已到backup之后的精确续行

若原phase已包含initial.json、business-before.json、drill-active.json和before-revoke.sqlite3，
两格都已本人激活，则禁止重跑前一节入口、前两次激活、backup、部署、cutover或receive。
必须按新root约束记录构建独立待审包：

```sh
uv run --offline --locked python scripts/issue176_resume_after_backup.py \
  --inputs OWNER_ROOT_CONSTRAINTS_JSON --output NEW_REVIEW_DIR
```

普通JSON只声明约束，不自证许可。新包以sudo.ws一次密码从内嵌字节冻结，核完整原runtime／manifest／入口／sudoers及原owner脚本/config，
原phase须exact4文件及全部SHA一致、root所有／只读保护／单链接；plan有效且两种stopped来源都不存在。
原RID最新、两格raw active集合须与原保护检查点完全一致，无其他active、pending或revocation；预算须与business-before全部一致，原锁非阻塞取得。
任何新phase、预算／配置／绑定或保护变化均停，不覆盖、删除或“修正”原文件。

跨设备EXDEV不是权限保护通过。新包只在明确核验/var/tmp为root:root1777、与日志相同device及fdinfo mnt_id后，
作用域设标准库cached tempfile.tempdir，调用同SHA原v4 product_log_probe；子进程清env不改变已缓存位置，finally恢复原值。
不改原probe／NNP／EACCES或EPERM断言，不放开日志任何祖先，不把EXDEV或unknown算合格。

仅执行：同盘probe及NNP helper失败持久性→新检查点→原root helper撤销临时格→原backup恢复→最后boundary本人审阅／手输ID一次。
保留原前两次人工授权；原4文件和backup全过程只读并在结束复核SHA。最后核非空原分项集合active/qualified、临时格仍撤销、预算不变，才写新root安全回执。
每阶段输出受控stage／reason，失败仅新增本恢复工具下的failure检查点，不自动回滚、卸载或继续grant。
新uninstall.sh仅原样归档本次恢复工具，不触碰原runtime／39源码／v4／phase／backup／log／ledger／预算。
全部新root字节和SHA仍须所有者审阅，代理不执行。具体模型及覆盖见[续行台账](../../docs/verification/issue-168-176-resume-after-backup.md)。
