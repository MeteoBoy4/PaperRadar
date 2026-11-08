# #167：nsfs误拒修复与原范围仅清理待审材料

## 历史和证明边界

[本次监督结果](issue-167-live-exit-probe-result.md)的严格退出及unit/CG恢复有据，artifact未完成、整体unknown；[原六格](issue-167-live-six-result.md)的unknown同样不变。本轮不重验服务、不发认证/模型或网络请求、不改旧封印、现场副本、回执或私有账本。所有临时删除控制只作用于/tmp合成树。

## 可复现的缺陷与前瞻修复

本地诊断 `.scratch/issue-167/live-exit-d5-cleanup-diagnosis-v1/reproduce.py` 绑定旧封印source SHA，抽取真实mount_points/remove_flat_tree，14个合成差分断言已运行通过。仅把nsfs第4字段从普通绝对root改为mnt:[数字]，旧函数即在首unlink前拒绝；窄内存谓词对照可清理，而树下mount、空/坏输入等仍阻断。该14对照不是额外D1节点，也不重写旧执行结果。

workspace `scripts/issue167_live_exit_probe.py` 只为已观察的fstype=nsfs、mnt:[无leading-zero正整数]允许非路径root。第5mountpoint仍须严格单次解码和绝对路径；NUL、未知转义、dot components、双前导斜杠、空/畸形观测均unknown，树下挂载仍在删除前阻断。双斜杠的额外反例已在/tmp证实与单斜杠同inode，不能按Path不同anchor误判树外。没有放开未知namespace或忽略挂载观察。

旧restoration_error聚合字段保留兼容，新增cleanup_diagnostics/artifact_error，以封闭枚举区分unit恢复、artifact阶段及原因。任意异常文本、路径及异常对象的自定义__str__都不进入投影；诊断失败不能跳过恢复/永久记录，严格退出成功谓词不变。

独立未绑定 `tests/test_issue167_live_exit_mount_metadata.py` **38项**，包含真实HostOperations.remove_artifacts两树链/runner、原输入红例及删除前拒绝。初轮修前13 failed/15 passed，后续双斜杠3例先红后绿；与旧probe55和exit38相关组合 **131 passed**。最终source SHA256为 `cf3575d53493fd78e44a6197522ceabfb5dd61c7de0346e70a2810123e5190da`。普通host用户对最终源的只读控制：当前60行/3条nsfs mnt，旧sealed拒绝、新parser接受，两目标树下mount=false；没有root、删除或服务动作，不证明旧sudo当时的原始字节或唯一根因。

## 原范围仅清理包

目录 `.scratch/issue-167/live-exit-d5-artifact-cleanup-v1/`。仅删除原代码13节点和runtime5节点，共18；没有新的unit/worker或实验额度。永久999-byte账本及原两轮unknown、回执、认证目录保持。原单次监督入口不可重跑；root清理按#167 H1仍由所有者审阅执行。

| 材料 | SHA256 |
| --- | --- |
| review-seal.json | `17e8fd2be2140de7d1c549fb20653e0977eadbed595f0b03ab69a7371f5f8770` |
| manifest.json | `6d5200b11c58c95bddbd34aa50338b13335ce62087930af07d93789b9ed344ff` |
| owner-cleanup.sh | `4365e8a79250e08ddec11989cc7a4b9fd1c6b681e0275cdb8e6e67c010a1db56` |

五成员为两个标准库源码、original-scope.json、scope.json及review.md；root仅加载先核SHA的字面stdin，不从可写工作区import应用。旧通用helper只复用FD-relative Tree/protected/record/check_mounts/command，不调用其旧main/perform或e93/nft路径。完整源码、config、旧scope和driver与封印逐字一致。

入口绑定原scope12源码/工具、本机、host普通用户lstat取得的实际UID0/1000及完整18节点dev/inode/type/mode/nlink/size/mtime/ctime。原账本预期SHA从公开owner结果移除local owner_exit_status后按原编码派生，size999；agent没有读取0600正文。root执行时反复核其原身份/字节，只读核具名unit、CG、unit文件/dropin缺失，不start/stop/reset/reload、不访问nft/resolver/DB。

两树全部先inspect并持有每层NoFollow目录FD，再重复host/账本/mount/inventory核验；固定公开源码/gate只从pinned FD读取，实际打开FD身份在read前核对，其他runtime文件仅看metadata。随后相对unlink/rmdir，后验两树缺失和账本不变。nsfs窄例外、空/坏输入和树下mount拒绝与修复边界一致。失败仍unknown，可部分删除，不自动重试/退款或回写原结果。

新 `scripts/issue167_live_exit_artifact_cleanup.py` 及独立D1 `tests/test_issue167_live_exit_artifact_cleanup.py` **45项**，与旧通用边界29组合 **74 passed**；包含真实root main的/tmp模拟两树18节点清理、账本保留、仅show命令、前置拒绝零unlink、别名和异常投影。四文件mypy、Ruff check/format通过；bash-n与固定/usr/bin/python3的实际最终literal加载控制通过（AST仅移除唯一main调用，2模块加载、main执行0）。fresh最终审查无剩余阻断；包未预占、未执行，results仅host-metadata/offline-validation材料。

审阅review.md、manifest、scope、original-scope、两源码及driver后，所有者入口：`bash .scratch/issue-167/live-exit-d5-artifact-cleanup-v1/owner-cleanup.sh`。只有一次sudo TTY密码，脚本不读取/保存密码；具体命令由脚本核验执行。这是原H1清理范围的子集，不新增服务重验或真实调用。

## 后继与验证口径

新D1两模块分别38、45项，与旧probe55及exit38相关组合 **176 passed**，保持独立未绑定，不扩历史分母/required/正式回执。链接/diff与固定scope含collect审计随本次收口记录，未运行完整离线门禁；未重复已完成的合成SIGINT/300秒控制。所有内部metadata、配置、绑定/回执和相关SHA只留本地。

本材料不把仅清理结果转成原run passed。实际Pi故障/能力、H4剩余取舍、H5及产品接收/人工激活继续待，普通产品缺证据阻断保持。
