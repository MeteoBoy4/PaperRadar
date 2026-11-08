# #167 T1：实际Pi公共300秒与项目诱导双向DROP待审材料

## 前置、身份与当前状态

所有者已选择[K2/T1](../../intent/review/issue-167/post-e01-h4-fault-scope.md)，无凭据双向机制已[通过并恢复](issue-167-duplex-result.md)。本包是其后的独立单格准备，不继承前轮执行许可，不增加E02，不改变产品LAUNCH_POLICY_VERSION或pi_protocol。实际Pi300秒、外部TCP443效果尚未验证。

canonical：`.scratch/issue-167/h1-live-timeout-t1-v1/`；run=`8b31f0a9d672`。最终材料40成员、合成材料23成员；本轮只准备，尚未预占或执行。

| 材料 | SHA256 |
| --- | --- |
| review-seal.json | `b47a6945ed485280180c633b292a66b217bebcd7904ba772b0b7e9db9374673d` |
| manifest.json | `dc4ef368e719c9ceda7940301ba550681c391c6182a05f54f552e081cba3e8e4` |
| owner-wizard.sh | `71d6ce56eb1f832df134678ef3fa8340098e8cc3512c6881eecad33d20b4ba5c` |

新源码分别为[纯规则](../../scripts/issue167_live_timeout_filter.py)、[案例契约](../../scripts/issue167_live_timeout_case.py)、[普通worker](../../scripts/issue167_live_timeout_worker.py)、[owner](../../scripts/issue167_live_timeout_owner.py)、[打包器](../../scripts/issue167_live_timeout_bundle.py)。旧合成/E01源码及封印材料未改。新身份只用于审查目录和本次实验，不是产品启动身份。

## 新H1/H2/H3的具体范围

新增唯一 `paperradar-167-h1net-8b31f0a9d672.service`、`inet paperradar167_8b31f0a9d672`、root-owned code/runtime和永久单次记录。root动作按原票H1由所有者审阅执行；固定七类IPC预检pair7/peer14沿原无凭据范围，不新增类别。Node上限2专指auth/model，不代表全部合成进程数。

最多auth CLI1、显式prompt/model1；value/low、openai/gpt-6.1-sol、prompt_only/provider_default、chatgpt_subscription，temperature/top_p=null。通过公共compiler/build_call生成一个新合成fingerprint，不加大任务或effort强迫触发。应用重试0、外部信号0，不补跑、不加任务、不退款。worker720秒/service780秒/owner900秒；公共auth30秒、model默认真实monotonic300秒及原有有界回收。

本轮H2采用**条件逻辑刷新0或1**，可能联网和持久写回；不读取新expires，不沿E01执行前过期/必刷新声明。模型/刷新HTTP均可证下界0、上界unknown，Pi内部DNS/QNAME/fallback、redirect及隐藏HTTP尝试仍unknown，须本轮明确认可。无新增DNS/TLS预热探针，旧profile的candidate_probe不执行。

专用认证目录仍由owner维护；执行批准须覆盖既定only-openai订阅OAuth、无额外provider/命令型输入及可能持久更新。上次owner确认models-store为空2bytes、models.json缺失的事实保留，不预称后续已有可信cache写回。准备不访问此目录；执行时只由受审metadata接缝记录relative文件集合及mtime/size/inode/ctime的有界稳定pre/post快照，合法新增cache按S记录；实际认证CLI按批准读取/刷新OAuth。失败或轮换未知即停、不回滚auth；usage缺失不是零成本。

允许集合固定应用可见28.0.0.0/8 TCP443和192.168.44.1 UDP/TCP53；owner须确认pool仍为当前配置，已知变化或未确认即停。无TLS中间人采用owner来源，不使用真实供应端IP，不核上游映射/线路/最终IP或主张出口身份；IPv6not_assessed。其他宿主流量不涉及，不改router、全机resolver/core或其它服务。

## 触发、期限和结果判据

完整同批解码后，首个非空assistant text_delta只有在ACK/start完整且无assistant终态、settled、closing、EOF或exit时，才发布一次无正文marker；不等待root，不停pump。system/user消息结束与assistant终态区分，marker和协议序号/计数必须交叉一致。

root核本run/controller/PID生命周期、独立CG及完整表后，用一次nft批次将INPUT+OUTPUT切至stall。只丢弃目标fake-IP TCP443的两方向，DNS仍按固定集合允许；其他项目流量独立计unexpected。完整引用链是deny→allow→stall，未触发可仅deny→allow；不沿合成实验的resume阶段。allowed计数混有DNS，不能据此证明TLS。

300秒起点保持公共run_call在factory之前的默认真实时钟，DROP不重置。记录public/factory/marker/切换意图与确认/返回时点，切换确认必须早于原截止；不拿含认证的外层耗时充数。

- observed_expected_and_restored：有效marker、完整双向事务/引用、两方向DROP packet/byte增量、公共TIMEOUT且真实耗时达到300秒，并有S/公共后验、DB/CG/host/目录完整恢复。
- not_triggered_and_restored：正常提前或缓冲完成须完整候选/EOF/exit0；可确认的SDK错误须受控公共reason和实际assistant error枚举。不把它登记为真实供应商错误通过，不补跑或退款。
- unknown：缺参照、半边切换、错归属、观察/后验失败、不可确认的transport/startup/close错误、恢复失败或late packet。不能统称“未触发”。

仅声明“项目诱导双向丢弃条件下，实际Pi公共monotonic300秒截止与清理”。自然供应商迟延、真实供应商错误、普通产品CLI/租约和全部异常时点不因此通过，也不证明供应商停止计算或零成本。

## 收尾与实际离线核验

保留公共prepare_launch/use_install、零core、NNP/空cap、cwd/OFD和S边界。DB准备绑定当前真实非空选择activation10，执行时重核，以CAS追加并恢复原语义，不能清库/字节回滚或覆盖别人。持久认证目录与模型临时树分别记录。

固定before_exit为独立计数基准，之后包括继承的exit gate在内每次核验均严格不增，不能吸收late packet。真正子进程回收、CG空后留存完整post_stop原始nft、binding、phase_reference、全部packet/byte和比较参照；全部相同才撤表/卸unit，恢复完整后才清两树，永久记录保留。失败可能留下材料，须所有者仅恢复；不为清理放宽判据。

五个独立未绑定D1分别filter77、case33、worker27、owner36、bundle24，组合 **197 passed**；末次仅将测试的别名拒绝断言收紧为errno.ELOOP，owner36项重验通过，封印源码未变。10文件mypy、Ruff check/format通过，fresh分别复核case/worker与owner/bundle及最终组合。user/system终态误拒、marker协议矛盾、delivery旧计数、截止后确认、继承exit gate吸收late、路径别名/短读/父目录替换和非有限JSON等拒绝路径有回归；真实/tmp两树测试先核封闭名字，未知成员不删。

两actual entry只移唯一main调用，用明确synthetic固定prefix/uid保护映射执行原41文件读取和完整hash：owner10模块、worker9模块，main0/主动操作0/app import0，来源均canonical。driver实际ROOT_BOOTSTRAP与封印bootstrap相同字节；普通用户实际source_bytes验证40成员加manifest，main/install/exec0。这些控制不证明真实root权限。两entry、完整source/import闭包、生成cleanup和bash-n均核对。

两个auth快照各接近16KiB、64节点，连同8份完整kernel fixture和全部引用，完整合成owner envelope112213bytes通过实际LOCAL_RESULT往返；原131072byte限制未扩大。新root runtime metadata读取逐祖先FD、固定parent dev/inode、最终FD稳定完整有界读取，短读/别名/重复键/非有限值均拒绝。

原unit在未安装状态直接systemd-analyze verify退出1，唯一诊断为预期install路径的synthetic-python不存在。仅/tmp副本把ExecStart可执行位置替为canonical同字节文件后，普通宿主只读语法核验退出0，无其它改动、无执行/安装。这是语法投影检查，不能记原unit完整部署通过。六个精确部署目标缺失；具名单元manager为not-found/inactive/dead、MainPID0及空CG/加载路径；results无现场预占或回执。

新D1不进入历史分母/required/正式回执，旧unknown和K2合成KI回归保持。本轮未读取真实凭据/cache内容或新expiry，未执行Node/Pi、认证、模型、信号、规则或服务；未重复物理KI/300秒控制，未运行完整离线门禁。固定scope含collect审计退出0，issues/affected_groups为空、skip/deselect均0；五个新D1另行独立收集197项，没有进入固定组收集或分母。后继授权独立登记。普通产品仍缺证据阻断，H5未接收。
