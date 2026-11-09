# 最终所有者方案：v4 cutover、新证据与持久收紧演练（尚未执行）

本方案须按最终主树重建私有包，审阅全部新字节后由所有者执行。代码／离线授权与ADR-0056接受
不授权代理设置+a、部署、cutover、采集／接收／撤销／恢复／激活或运行完整门禁。
现场v3和旧非空active是历史事实，不证明v4；旧G2/升级/owner候选原字节保留，不能直接重用。

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
预算仅稳定只读主文件的必要ID／指纹／代际／attempt计数，已有WAL／SHM／journal即拒绝，不读payload/token/全文/auth/cache正文。
NNP仅作用子进程，不改root或sudoers；全流程无认证／模型／网络，不刷新预算，进程重读不证明主机重启。

## 中断与恢复边界

每一步把有限检查点保留在root账本下唯一closure目录；未知／失败／中断不写completed安全回执，不自动回滚、删除或授予。
预检拒绝时旧runtime不归档。设置+a前后才发现的支持性或I/O失败，可能已经cutover：旧资格继续撤销，
目录／日志保持部分状态并阻断，由所有者保留现场及准确checkpoint后另行审阅恢复方案；同包不会自动补完或重建。
恢复屏障之后未最终激活时保持无资格，必须本人重新完整审阅有效新证据，不能用旧短ID或旧active报告翻转撤销。
默认卸载／重装保留否定日志、账本、回执与runtime归档；不通过清文件“修复”准入。
最终实际部署／权限／激活及G4完整门禁仍由主代理按各自授权串行完成，未执行时不关闭#176/#168。
