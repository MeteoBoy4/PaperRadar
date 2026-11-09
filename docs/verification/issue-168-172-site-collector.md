# #168 / #172：β站点采集与封印部署覆盖

本台账覆盖非特权封印构建、固定root采集入口、当前站点回执和部署/卸载边界。
新增测试独立未绑定，不扩大历史required、组回执或固定分母；旧scope和中央成员/哈希不动。
本票没有执行sudo、真实root部署/collector/激活、历史导入、认证、模型或网络。
所有者对确切脚本字节的G2审阅尚待完成，#172不因此台账提前完成或关闭。

## 公共seams与独立分母

| 独立新增模块 | 人工预期节点数 | 责任 |
| --- | ---: | --- |
| `tests/test_site_collector.py` | 14 | receive兼容回执、首失败/unknown、零参数、来源receive/show与原时点保持、合成隔离逐项标准、失败计划持久停止、三项配置负例、产品uid先决、六格210主张、root实树拒绝伪造expected、失败刷新撤销与SQLite写失败/观察屏障 |
| `tests/test_site_deployment.py` | 8 | sudoers最小授权、脚本位置/零参数/保留账本、冻结Python污染环境冷启动/无链接包/脚本语法、无root部署卸载恢复幂等、篡改包/软链/可写目标拒绝、纯本地构建帮助 |
| `tests/test_site_tree_identity.py` | 5 | 实际文件tree-v1同值/内容改变漂移、外链/硬链/错误属主拒绝、扫描时换链不跟随 |
| 合计 | 27 | 独立未绑定工程覆盖 |

两个新增support只提供私有临时fixture与无root文件系统模型，不是当前站点值。
脚本模型仅替换固定宿主路径、uid/chown/install/visudo这些OS边界；实际执行生成的shell逻辑，
不会使用sudo、写真实系统目录或把模拟所有权当真实特权证明。真实root/等价root权限仍须G2现场验证。
正常合成Landlock检查使用临时空cwd/安装/attempt及公开合成文件，
不访问真实业务/凭据目录；不支持的内核得到明确失败案例，不以skip冒充通过。

## 采集对齐与当前上下文

必需集合与β覆盖的权威对齐表见[live-evidence Contract](../contracts/live-evidence.md#β-站点采集与封印部署)，
不在此另复制一份能力分类。当前安装整树不只采信业务库manifest：
acquire_install本身已先经inspect_instance重算实际tree_hash并比对expected_tree，再yield；
新root采集还从私有配置固定安装路径，使用fd/O_NOFOLLOW逐文件重新算tree-v1，
核产品属主/单链接regular成员/内部软链/稳定元数据，独立实测摘要须与产品uid结果一致。
扫描中换链、外国属主/硬链或实际字节不匹配均停止，不把产品可写库声明当root观测。
root从不执行安装里的用户可写程序；Node --version和合成隔离均以降权产品uid执行。

本次所有者明确选择当前普通配置及数据库既有activation/snapshot，要求六格站点事实。
私有site.json由只读公共API派生，不compile、不写业务库、不重建/重装；不读取auth/cache/日志正文或旧protected记录。
具体路径/标识留私有包，不进入公开台账或回执。产品观察也只读复核冻结的snapshot/供给/安装仍为当前选择。
同轮只有一套内容无关站点测量，向六格分别记录35能力共210条主张；
CurrentObservation仍是当前activation/snapshot的low声明上下文，并非六份真实模型观察。
高档消费者重算自己的MODEL_TUPLE；站点能力只按自身依赖适用。
六格模型/RPC/IPv4出站/observer均unknown，不表示完整high或任何格已可执行。

AUTH_CACHE_BASELINE是专用credentials全根的递归stat清单，
auth.json、exp2-installation-id、models-store.json、node-compile-cache及全部后代均在内，
没有正常写入例外。dev/ino/mode/uid/gid/nlink/size/mtime/ctime与目录成员变化都参与。
宿主认证helper未设置NODE_COMPILE_CACHE，HOME/TMPDIR=credentials；当前安装入口调用enableCompileCache()，
其正常编译缓存会落在credentials/node-compile-cache。RPC的TMPDIR则在每attempt临时根。
正常认证cache写入或auth.json刷新也使基线漂移，准备后检查拒绝，不产生attempt/预算消耗。
不为连续运行而排除成员或削弱D3；新基线须经新受信计划采集、重新审阅封印字节、人工激活。
成功计划的重跑只刷新60秒当前观察，不覆盖原回执或续verified_at；首失败计划持久stopped。
支持连续运行的缓存布局/允许演进保护由Live后继承接，需另行裁决和必要的策略升版。

## 红绿与开发验证

按AC公共边界垂直推进，缺collector/runtime/deployment/root-tree模块、缺受保护计划来源、
缺G2 REVIEW材料及失败计划可重试均先红后绿；没有改旧冻结测试来弱化预期。
新增25节点首次实测通过；与既有current-binding、D7、receipt、ledger、CurrentObservation、
stat基线与tightening组合为81 passed in5.38s，退出0。后续新增源收紧后的25节点复跑也通过，
没有skip/deselect/incomplete。收尾自查补充两个失败刷新回归：先激活成功站点证据，再令刷新失败，
先红后绿证明mode000观察当场拒绝、同安装所有已接收用途经既有tighten持久收紧，
原receipt/verified_at保持。只读SQLite模拟实际落账失败，未落账时不声称revoked；
观察仍不可读、待收紧保留，后续重放落账后仍stopped，不自动重试探针，普通产品入口不能解封。
最终独立分母为27；与共享loader和CurrentObservation的最终组合为38 passed in4.23s，退出0。
相关3个变更Python文件的Ruff/格式与strict mypy再次通过。collect-only用于核对上述人工分母，不从生产登记或实际结果反填预期。
CLI compatibility为59 passed in72.08s，入口总耗时72.72s，退出0。
新增10个Python文件的Ruff、格式与strict mypy通过；新入口帮助与冻结Python隔离导入在独立模块覆盖。
本票不运行完整check-offline、不写正式run_id，不发布A1–A10结论。

## 封印包与后继责任

非特权构建入口、规范与卸载范围见Contract。Python/stdlib/明确运行依赖/源码/入口一起冻结，
排除主树可能另装的Docling/dev包、editable/.pth与bytecode。
payload无链接/设备/绝对或逃逸成员，模式规范为0644/0755，不携带setuid/setgid权限。
宿主动态链接器/系统共享库仍属OS信任边界，离线包不声称防范root或系统升级。
collector_sha256标识冻结运行闭包；deploy另外绑定整个payload SHA256。
REVIEW.md列确切脚本SHA、一次owner sudo复制/复核/从root副本部署与固定计划接收动作；不自动激活。
放宽owner入口不在NOPASSWD中；G3仍须所有者逐格审阅回执、短ID确认，短时观察不续原能力。
默认卸载保留账本/回执/计划/失败历史/stopped/staging，仅移除本包入口/策略/runtime及本部署创建的空cwd。

build-identity.json记录源HEAD/tree/dirty、绝对build-worktree、Python/lock、冻结源码与payload身份。
feature包只是候选；合入integration后应从最终主树非特权重建正式包并打印新SHA。
迁移前须比较identity字段与实际payload字节，不能沿用不适用身份；私有包保存在主工作树ignored目录，
不依赖待清理的feature worktree。owner尚未审阅具体字节时不能提前关闭#172。

新模块/脚本/三个测试与两个support、本台账和新增Contract消费闭包交#176显式登记。
开发scope审计只读，既有cli.py、contracts/schema.py、pi_supply/cli.py三项mechanical漂移仍由#176收口；
准入policy-v2、33源码D7清单及只追加摘要锚、v1向量、旧scope/中央哈希均原字节保持。
G2真实脚本/权限核对、G3实际激活、后继唯一review与G4完整门禁均未由离线测试替代。
