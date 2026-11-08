# #167 T1：双向过滤无凭据合成机制通过并恢复

## 授权、材料与结论

所有者执行了[待审合成包](issue-167-duplex-preparation.md)，随后回复“已完成”。本轮限于该包的H1范围，不含后续真实Pi调用许可。run=`a73d9c02e651`；review-seal SHA256为 `2ea3df160bc9c06c7f224b5bb3c48698c3f6ea923d30307886a8cb7779f1ec21`，manifest为 `ae332e1ce6d43d4e914ecfac3ac62ff5c4d883f58f478da2c23974e931decae1`，driver为 `3d7b798f640ed0c3433551d32e06a3b292a16398995bd1c5d703f9f7e57a351c`，均未漂移；10个成员逐字节核对一致。

受控 `results/owner-run.json` 为43593bytes，SHA256 `c99b5445994af06e021469e385e568eddd911474627a4445c4b333ae55caf4c9`。结果为 **observed_expected_and_restored**，owner_exit_status=0，role_failures为空。主代理与fresh独立只读复核一致；没有重新执行服务、规则或探针。

## 实际正负对照

client与peer均UID/GID1000、零core、NoNewPrivileges；client位于独立目标CG，peer及其control位于该CG之外。仅IPv4 loopback固定端口、2个active connect/2个accept；应用send实际10、上限12，应用重试0，Pi/Node/认证/刷新/模型及外部DNS/TLS均0。

| 阶段 | 实际观察 |
| --- | --- |
| baseline allow | 主连接双向A到达，尾buffer为空；CG外同UID control双向成功 |
| transaction stall | 完整INPUT与OUTPUT阶段规则由一次nft批次切换；独立binding和phase引用完整 |
| negative | client有效观察1.494240818秒、peer 1.494395759秒，均覆盖共同结束时点；两端新增payload与尾buffer均0、B未到；CG外control双向成功 |
| experimental resume | 一次事务恢复allow后，原B双向到达，应用不重发；CG外control再次成功 |

留存的7份完整kernel_state逐份通过纯verify_state重算，与回执counts一致；4段deny0→allow1→stall2→allow3通过verify_references。独立CG dev30/inode859571，table handle31，常驻和动态handle及完整规则仅留本地回执。

| 阶段 | allowed in/out（packet） | dropped in/out（packet） |
| --- | --- | --- |
| created deny / transaction allow | 0 / 0 | 0 / 0 |
| baseline complete / transaction stall | 3 / 4 | 0 / 0 |
| negative complete / transaction resume | 3 / 4 | 4 / 4 |
| before exit | 6 / 7 | 4 / 4 |

negative的dropped bytes分别300/304；所有unexpected packet/byte均0。packet不是应用请求数或TCP重传次数。两方向drop、双端持续读零增量、同UID不同CG正例与原B恢复到达共同支持本例机制结论；不能仅凭超时或计数自称真实Pi挂起。

## 收尾、独立核查与证据限制

封印控制器报告严格controller退出、CG空、owned peer零退出并回收；随后对独立归属和完整规则执行verify_quiescent，六类packet及byte必须与before_exit完全相等，才撤表、卸单元并清两树。恢复和artifact字段均精确成功，永久单次记录保留。

最终post-stop原始nft快照及resume gate完整正文未存入该回执。因此，7份留存快照和4段引用链可独立再计算；最终quiescent及resume gate时序只采用封印控制器严格检查后的完成声明，不能描述为留存原始值已独立再算。后续真实待审包须将post-stop完整快照一并保存，不改本轮历史回执。

主代理另以普通用户只读lstat，确认本次 `/etc` 与 `/run` 精确unit文件、CG、code/runtime两树均缺失；具名单元manager为not-found/inactive/dead、MainPID0，CG/fragment/drop-in/User/Group空。永久记录为root:root、0600、nlink1、43482bytes、inode1052846；只读元数据，未读取其内容或计算实际文件内容摘要。table absent来自封印控制器的受控恢复回执，本轮未另外提权读取全机规则。

## 证明范围与后继

本轮通过只限该IPv4 loopback合成机制，不证明未来fake-IP/TCP443、外部TLS、实际Pi公共300秒、自然供应商迟延或真实供应商错误；IPv6仍not_assessed。实验resume是机制正对照，不是允许真实300秒前解除DROP的许可。旧单向OUTPUT材料没有被追认成INPUT覆盖。

按所有者T1，下一步可离线准备新的单格H1/H2/H3待审包：最多1 auth CLI＋1 prompt/model、条件刷新0或1、不沿用E01旧过期声明；保持公共300秒起点、持续pump与S/DB/host/目录收尾，提前完成或早期错误/缓冲未触发不补跑、不加任务、不退款。恢复失败或late packet仍unknown并保留，交所有者仅恢复。具体现场和新调用另批，本次无此许可。

本轮验证为材料哈希、schema/完整规则/引用重算及独立只读状态核查；准备阶段111项不登记为本轮重跑，未重复合成KI或300秒控制、未运行完整离线门禁。新增材料沿D1，不改变历史分母、required或正式回执；旧unknown、K2的实际直接注入not_assessed、H5草稿及普通产品缺证据阻断保持。
