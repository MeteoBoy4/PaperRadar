# Pi 固定供给 Contract v1

当前交付 `pi supply prepare/verify/rebuild/activate/list/show/export`、`doctor --scope pi-supply` 和公共 Python 服务
`paper_radar.pi_supply.prepare_supply/verify_supply/rebuild_supply/list_supplies/show_supply`，
以及 `activate_supply/activation_history/doctor_supply/export_supply` 和只读 `available_installs(database, supply_id)`。
准备不激活，无需真实 Profile、模型配置或凭据，也不证明 RPC、模型语义或校准。
`SupplyRequest`、`SupplyManifest` 为 `pi_supply/models.py` 的权威 Pydantic 类型。

## 显式输入与请求

```bash
uv run --offline --locked paper-radar pi supply prepare \
  --database data/paperradar.sqlite3 --snapshot <完整ID或唯一8–63位前缀> \
  --adapter-slot screening --request supply.json --install-root .tools/pi \
  --data-root data --config-root config --material-root tools/pi
uv run --offline --locked paper-radar pi supply list --database data/paperradar.sqlite3
uv run --offline --locked paper-radar pi supply show <完整supply_id> --database data/paperradar.sqlite3
```

公共 prepare 的前五个位置参数依次是 database、snapshot_reference、adapter_slot、
request_path、install_root；三个其他实际根为必填 keyword 参数。
可注入 downloader/runner 仅替换网络和外部程序。真实实现为 HttpDownloader/ProcessRunner。
请求严格 YAML/JSON：拒绝未知键、重复键、锚点、合并、多文档、非有限数和任意命令/参数；
整数格式版本严格为 1，布尔不算整数。证据文件相对请求文件所在目录解析，
拒绝绝对路径、任何 `..` 组件和解析后落在该目录外的链接；合法子目录可用。
这是本次对请求读取边界的补强；既有冻结证据仍按库内原字节回放，不重新读取源路径。

```json
{
  "format_version": 1,
  "node_version": "22.19.0",
  "npm_version": "10.9.3",
  "node_source": "nodejs.org",
  "node_sha256": "<64位官方归档SHA-256>",
  "platform": {"os": "linux", "arch": "x86_64", "libc": "glibc"},
  "d5": {
    "decision": "unknown", "basis": "首次供给，无可比基线",
    "baseline_supply_id": null,
    "evidence": [{"kind": "evidence_file", "path": "review.txt"}]
  }
}
```

示例工具链不成为默认值。Pi 版本只取经公共快照加载验证的所选 adapter 材料；
三个程序版本复用 `config.adapters.exact_program_version` 的三段正式版本规则。
允许混合 Pi 版本的快照准备所选槽；准备输出不宣称可激活。
运行时须是 Linux x86_64，`os.confstr("CS_GNU_LIBC_VERSION")` 须给出非空 glibc 版本，
实际值与请求平台匹配并进入清单。engines 仅接受精确版本或单一 `>=X.Y.Z`。

D5 三态为 `no_change/may_change/unknown`，依据必填且非空白，上限 16384 字符；
后两态都需要后续语义评估，不自动决定 minor/major 或开启校准门禁。
show 与 doctor 遇到这两态明确显示「需要后续相关语义评估」「不代表校准兼容」。
baseline_supply_id 可空；非空须指向冻结前已有供给，空基线拒绝 no_change。
证据非空，仅支持以下三种（可用 note 保存非秘密附注，包括 URL）：

| kind | 请求字段 | 冻结与回查 |
| --- | --- | --- |
| evidence_file | path | 上限 4 MiB；保存原字节与完整 SHA-256，不保存源绝对路径 |
| supply_material | material、可选 supply_id | 当前已取得材料或已有供给材料角色；冻结摘要，不允许悬空 |
| supply_record | supply_id、可选 check_id | 已存在供给/其已有 install_check；禁止未来记录、自引用与环 |

纯 URL 不独立成立。库内语义回放检查材料原字节、派生规则、D5 形状/引用闭包和供给身份；
一致重哈希的坏内容不能只靠摘要自洽蒙混过关。备份恢复后仅凭库内事实即可回查。

## 材料、下载与唯一安装路径

Pi 固定来源为 `https://pi.dev/api/installer/releases/<精确Pi版本>`，
以及该端点的 `/package.json`、`/package-lock.json`；Node 地址仅由精确版本推导：
`https://nodejs.org/dist/v<版本>/node-v<版本>-linux-x64.tar.xz`，同目录 SHASUMS256.txt。
请求摘要须在 SHASUMS 中以精确文件名唯一匹配，随后核验归档原字节再安全解包。
HTTPS 官方来源与 SHASUMS 是本轮信任边界，不另交付 GPG。

HTTP 白名单固定 pi.dev 的 release 子路径、registry.npmjs.org、nodejs.org/dist/；
拒绝 userinfo、其他端口、query/fragment。httpx 不继承环境代理，不自动跟随跳转，
每跳重新验证；最多 5 次跳转，连接 10 秒、读写 30 秒；小材料 4 MiB、归档 128 MiB。
显式 --proxy 仅接受无 userinfo 的 http/https URL，不入库、不进入身份；
npm 经本次私有 npmrc 显式使用相同代理，不读取个人 npmrc/cache。

官方三材料配对检查版本、包名、根依赖、engines 和 override，不重新解析依赖。
保留官方锁原字节；只补 integrity 的 `derived-lock-v1` 见 [ADR-0028](../adr/0028-derive-integrity-only-staging-lock.md)。
补充清单 `integrity-supplements.json` 格式 1，记录所补 path/name/version/resolved/integrity；
派生锁和补充清单均用共享规范 JSON（UTF-8、键排序、紧凑分隔、无结尾换行）。
真实 Pi 1.3.0 fixture 的派生锁 SHA-256 固定为
`a342ed1baea205543bdcaf82ec4aed2bfc771a5c2c47b2bacb8238d06513e7c6`。

npm 只使用本次 Node 自带版本，由明确 Node + npm JS 入口执行：
`ci --ignore-scripts --omit=dev --include=optional --no-fund --no-audit --update-notifier=false`。
此策略固定名 `install-policy-v1`；全部 resolved 先检查 registry 来源，再由派生锁逐包 sha512
约束 npm 实际消费的字节。npm 内部重定向不受 Python 逐跳白名单控制，此不对称不作隐藏。
Node 解包逐条 tarfile data filter 和额外路径/链接/设备约束，上限 100000 条与 1 GiB 展开字节。

受控完整环境只含本次 HOME/tmp/cache/agent/session/XDG、独立 Node PATH、固定 locale，
固定 umask=022，进程 240 秒和合计 stdout/stderr 1 MiB 上限。失败、取消或超限终止进程组；
原始输出和 npm debug 日志不永久保存、不回显。Pi 禁用自动更新、遥测、资源发现及会话持久化，
仅运行明确 Node + 包内 bin 解析出的 Pi JS 入口，分别做无模型 --version/--help。
help 的私有空 auth/models 文件允许写在树外；session 写入或运行树改变拒绝。
这是有界启动策略，不声称生产 OS sandbox 或模型运行无网络。

## 清单身份与 tree-v1

清单字段：format_version、pi_version/node_version/npm_version/node_sha256、platform、
libc_version、install_policy、derived_lock_rule、tree_rule、materials（角色→原字节 SHA-256）、
expected_tree、node_entry/npm_entry/pi_entry、d5。
supply_id 为上述规范载荷 SHA-256，不包含自身 ID、时间、位置、快照 ID、随机实例名或代理。
执行审计身份不进入六阶段投影或校准基线。供给固定输入的唯一防重键排除 D5/证据文件、
expected_tree、安装后解析的 pi_entry；保留其余字段及官方/补充/派生材料摘要。
防重键仅防止同一固定输入重冻，不替代 supply_id。

独立清单编码向量见 `tests/fixtures/pi_supply/manifest-vector.json`：用独立 jq -cS
去掉末尾换行后，SHA-256 为
`a68a0964d1913cabfd75b49034162096e24c9a0ee5dc428e69760c3d053f2ea7`。
它仅测试规范编码与身份算法，材料摘要为合成占位，不可登记为已验证安装。

公开纯函数 `paper_radar.pi_supply.filesystem.tree_hash(root)` 实现 tree-v1：
完整 `node/`、`app/`（含派生锁与 npm 元数据）全部计入，无文件排除；cache/HOME/tmp/log 位于树外。
路径为 UTF-8 POSIX `/`，按路径字符串排序，首项为空路径的根目录。
目录项 `{path,kind:"directory",executable}`；普通文件项
`{path,kind:"file",sha256,executable}`；链接项 `{path,kind:"link",target}`。
executable 为任一 x 位的布尔值，目录也计；链接目标保留原文本并须在树内、可解析且非绝对路径。
拒绝特殊文件。规范 JSON 数组的 SHA-256 为树身份；不包含写/读位、mtime、uid/gid 或位置。
实际枚举使用显式目录扫描，不抑制权限、缺失或其他读取错误；不可读子目录不能当作空目录，
全树身份与占用都返回受控无法核验。此完整性检查不改变 tree-v1 的有效树编码与独立向量。

独立向量：根与 `bin/` 可执行，`bin/run` 内容为 `hi\n` 且可执行，`run` 为 `bin/run` 的相对链接，
树摘要为 `3ba7d3e8a26699a27360c5f3575eee704abe8cb77f572e0a21f768a798b96573`。
测试使用固定字面量并验证不同 staging/umask/mtime，以及内容与执行位变化。

## 安装实例、发布与恢复

安装根须与显式 data/config/materials 根两两互不包含，且不能含数据库；路径组件拒绝符号链接。
仅支持本地 ext2/3/4、xfs、btrfs、zfs、tmpfs、overlay，按 Linux 实际挂载点识别；不支持 NFS/CIFS。
mountinfo 路径完整解码三位八进制转义；最长挂载点有多个不同文件系统类型时保守拒绝，不按字串挑选。
512 MiB 可用空间预检只前移空间不足，不能取代后续校验或保证真实安装空间足够。
这是下载前的固定粗略门槛，不是 npm 展开量或峰值估计；发布在同文件系统内改名，
不复制第二份新树。较大的合法归档、npm 包、缓存及并发写入仍可在之后耗尽空间并受控失败。

```text
<install-root>/.paper-radar-install-root       # 本库稳定随机身份与随机根身份
<install-root>/.locks/<install_id>.lock        # 树外持久锁，永不清理
<install-root>/.staging-<随机>/tree/{node,app} # 发布树
<install-root>/.staging-<随机>/work/           # 本次私有临时环境，发布树外
<install-root>/<supply_id>/<install_id>/       # 只读完整实例
```

首次空根通过 flock 串行认领并与数据库稳定 owner 绑定；他库根、非空无主根拒绝。
DB旁发布锁→根锁→固定输入锁在写事务外取得，昂贵下载/安装不持写事务。
协调锁精确位置为 `<database>.pi-supply.lock`、`<install-root>/.root.lock`、
`<install-root>/.prepare-<material_key>.lock`；rebuild 只取前两个。
这些空的持久文件只协调发布/认领，不承载供给或业务事实，不属于备份、导出或清理候选，
不进入供给身份。释放只关闭描述符，正常运行不 unlink，避免仍持旧 inode 的进程
与新建同名锁失去互斥；不能把手工删除锁当作解锁方式。
完整树与发布意图 fsync 后以 Linux renameat2(RENAME_NOREPLACE) 发布，连既有空目录也不覆盖。
Linux 移动目录时顶层短暂保留写位，发布后撤去并 fsync，之后才能短事务原子登记材料/清单/实例/成功检查。
根与意图等本机管理文件不进入供给身份；不把 .staging/.pending 或未登记树当可用安装。
发布后事务失败/强杀只有残留完整树；相同完整意图与预期树重新核验后可重入登记，未知残留不删除。

普通重复 prepare 在再次安装前拒绝并指向 rebuild，即使改 D5 也不能重冻。
同时开始的相同完整请求先提交者胜；输者比对清单和现场树后返回既有 supply_id/install_id，
清理自己的 staging，不登记第二实例。相同固定输入得到不同树或 D5 时受控冲突。
list/show/export 只回查历史，不检查现场，不要求 Node/Pi、网络或受支持的 Pi 部署平台；
export 另需下述安全文件能力。list 明示计数为历史登记、未核验现场，
show 同样披露未核验现场；不能把历史 passed 当作当前可用。声称当前可用的 doctor、
activate 与使用句柄必须现场核验。此区分落实父票后续对历史查询和隔离恢复的要求。
检查 scope 当前唯一为 install_check；不导入任意用户声明成功记录。

数据库 head 为 a405_pi_cleanup_execution；既有 migration 原字节保持，
a404 追加不可变 `pi_cleanup_plans` 及其消费者所需的 `pi_install_retirements` 识别事实；
a405 追加 `pi_cleanup_executions` 与 `pi_cleanup_progress`，执行复用 a404 退役事实；
a403 激活事件与唯一选择、a402 重建失败事实保持不变。
供给小型材料与 D5 证据随数据库备份，backup format 仍为 1，语义回放同时校验供给闭包。
恢复不安装、不下载、不激活。a302 旧批次须先用匹配 A3 程序恢复，再切新程序 db upgrade；
不放宽 head gate。恢复副本共用原根时，旧副本退役前不得 gc execute；flock 仅保护在途进程，
不能区分两个空闲活动副本。

导出固定集合为 package.json、package-lock.json、release.json、supply-manifest.json、
integrity-supplements.json、SHASUMS256.txt 与 d5-evidence/<SHA前16位>.bin；
derived-lock.json 是内部保存的确定性派生材料，不增加到已批准导出集合。
版本控制目标 tools/pi/<supply_id>/，安装树 .tools/pi/<supply_id>/<install_id>/ 被 Git 忽略。
rebuild 重新联网下载固定摘要的 Node/tarball，不承诺脱网重建。

## 固定材料导出

```bash
uv run --offline --locked paper-radar pi supply export <完整supply_id> \
  --database data/paperradar.sqlite3 --target tools/pi
```

`export_supply(database, supply_id, target)` 先经公共 show 完整核验全库材料、身份与引用闭包，
再从数据库原字节导出；不读取原配置、request/evidence、安装树或先前导出目录。
返回不可变 `ExportResult(supply_id, files, created)`：files 为相对供给目录的完整固定集合，
created 只含本次新增项；同字节重复运行 created 为空且不改文件或目录时间、inode、权限。
供给目录为 `target/<完整supply_id>/`；清单为规范原字节，官方锁保持官方原字节。
target 与本库全部已登记安装根（含尚无实例的已认领根）及数据库文件位置作纯路径
双向包含检查，重叠给 `unsafe_root`，不探测或解析原安装现场。原根已缺失也保留隔离规则。
未知的 data/config 根不从 cwd 推断；用户仍须选择分离的材料目录。
顶层恒为前述六个文件，加全部 evidence_file 的原字节；完整摘要重复只输出一次。
supply_material/supply_record 只保留清单中的引用，不递归导出别的供给。
不导出 derived-lock.json、安装树、tarball/Node archive、认证、完整日志或 RPC。
公开纯布局 `pi_supply.export.export_evidence_layout(digests)` 接受完整小写 64 位摘要，
输出按固定短名排序的 `(完整摘要, 相对路径)` 元组；不同摘要前16位相同则
`export_evidence_collision`，不能覆盖、延长摘要或改固定命名。

创建任何目录/文件前先预检整组既存路径：每级目录拒绝链接，既存目标必须为同字节普通文件；
异字节、目录、链接（含断链）或特殊文件拒绝，全组不新增。额外用户文件保留，不计导出集合。
预检后每个新文件先同目录私有临时文件写完并 fsync，再用不覆盖硬链接发布并 fsync 父目录；
目录句柄与 nofollow 防止路径切换导向链接。并发既存文件重新核验，同字节跳过、冲突拒绝。
导出不检查 Pi 部署的 OS/arch/libc，但安全发布需要 Python/文件系统支持目录句柄及 dir_fd、
O_DIRECTORY/O_NOFOLLOW/O_NONBLOCK、普通文件硬链接不覆盖发布与 fsync；缺少能力受控失败，
不退回可被路径替换的普通路径写入。list/show 与库内历史读取不需要这些导出写入能力。
2026-10-18 用户裁决：本次 A4 接受上述必要安全文件能力边界，保持能力不足时的安全拒绝。
原生 Windows 安全导出另由 [#46](https://github.com/MeteoBoy4/PaperRadar/issues/46) 交付与验收，
本次未实现/未验证 Windows 后端；#46 不阻塞已裁定的本次平台范围，#36 仍保持 OPEN。
这不是跨文件事务：运行中 I/O 故障或强杀可留下部分完整项；保留后重试补齐，不删除用户文件。
`export_conflict/export_failed` 均给中文原因和下一步；CLI 成功0、失败2、中断130，配额消耗0。
导出是数据库的版本控制投影，不作为恢复、导入或修复数据库的权威。

## 完整核验与固定材料重建

```bash
uv run --offline --locked paper-radar pi supply verify <完整supply_id> \
  --database data/paperradar.sqlite3
uv run --offline --locked paper-radar pi supply rebuild <完整supply_id> \
  --database data/paperradar.sqlite3 --install-root .tools/pi \
  --data-root data --config-root config --material-root tools/pi
```

`verify_supply(database, supply_id, *, runner=None)` 明确检查该供给全部已登记实例，
返回逐实例 `VerificationResult(install_id, passed, reason)`；单实例失败不停止其他实例。
先核对归属/安全路径与完整树，再用明确 Node/npm/Pi 入口探测精确版本及 Pi --help；
最后再次核对完整树及空 session。verify 不执行 npm ci、不下载、不改变固定材料或安装树。
所有已检查实例均追加 `scope=install_check` 的通过或受控失败事实，旧成功保持不变。
执行门槛要求 Linux x86_64/glibc，且实际 libc 版本严格匹配冻结值；平台拒绝不执行实例。
CLI 逐项输出实例/范围/结果，任一失败返回 2；中断返回 130。

`rebuild_supply(database, supply_id, install_root, *, data_root, config_root, material_root,
downloader=None, runner=None, proxy=None)` 首先完整回放库内材料、SHASUMS、派生策略及 D5，
之后只重新下载固定 Node 归档并让固定 bundled npm 消费历史派生锁取得固定 tarball。
不访问旧 request/evidence 路径、不重新取得 package/lock/release/SHASUMS，不接受新 D5。
与 prepare 共享真实构建规则；精确工具链、libc、入口、package/派生锁字节和完整树必须等于历史预期。
成功生成随机 install_id，supply_id/材料/D5/预期树不变；旧坏树/缺失实例和全部检查原样保留。
可在本库另一个独立安全根重建，同一固定供给仍保持同一 supply_id。

重建发布使用本根独立 `.pending-rebuild-<supply_id>.json` 意图，
只包含完整 supply_id 与随机 install_id，不与首次 prepare 的意图混用。
完整树先不覆盖发布并 fsync，再重新完整核验发布目标，最后短事务仅原子追加实例与成功检查；
事务中再次核对冻结清单。登记前强杀或事务失败不产生半成功实例，重试核对可靠意图与完整目标后
完成同一 install_id；登记后强杀重试也只完成该意图，不重复登记。
登记提交后意图/staging 清理失败仍返回已提交成功，`PrepareResult.residuals=True`，
CLI 明示残留需人工检查；它不会把已登记成功改报为构建失败。只清理本次 staging，未知残留保留。
这不是自动 GC，也不证明强杀时必能追加失败记录。

有可完整回放的目标供给后，受控重建失败追加供给级失败事实（failure_id/reason/created_at），
既有 list/show 可回查；失败不新建实例、不修改其他实例。未知供给或损坏历史无法可靠绑定，直接拒绝。
若失败审计自身不可写，返回 `failure_record_failed` 并保留受控 execution_reason，不声称已保存。
备份/隔离恢复保留全部多实例、逐实例检查和供给级失败；回放拒绝孤儿引用、无时区时间或非受控原因。

`available_installs` 不运行程序、不写检查，依次排除归属/路径/现场全树不符的实例，
剩余按每实例最近通过检查的 `(created_at实际时刻, check_id)` 降序返回。
check_id 全库单调且唯一，时间相同仍确定性破同；最近失败只供审计，不覆盖较早通过。
查询返回空元组表示没有可用实例；这只是选择时事实，不是未来执行的并发保护。

受控错误完整词表及中文下一步由 `pi_supply/errors.py::SupplyReason/GUIDANCE` 定义；
常见组为 request/snapshot/adapter、来源/完整性/工具链、平台/根/树、进程配额、发布/并发和事实损坏。
未知参数、URL/代理、底层异常、子进程输出不直接拼入错误文本。


## 原子激活与只读诊断

```bash
uv run --offline --locked paper-radar pi supply activate <完整supply_id> \
  --database data/paperradar.sqlite3 --snapshot <完整ID或唯一短引用>
uv run --offline --locked paper-radar doctor --scope pi-supply \
  --database data/paperradar.sqlite3 --snapshot <完整ID或唯一短引用>
```

`activate_supply(database, supply_id, snapshot_reference)` 比对显式快照中全部已选择的 adapter 槽，
至少一槽且全部 `pi_version` 必须等于目标供给版本。真正未选择的槽不参与；
已选择但 Prompt 占位的槽仍参与版本比对。混用版本给 `adapter_versions_mixed`，
空选择给 `adapter_missing`，一致但不匹配给 `selection_version_mismatch`；
不修改任何 selector，不提供任意 install_id 激活入口。

目标取该供给最近成功 install_check 且现场可用的实例；成功检查按
`(带时区created_at, 全库单调check_id)` 降序稳定排序。失败检查不抹去历史成功，
现场坏树、缺失、根归属错误、非本地文件系统或完整树不符仍排除。
激活再次做根归属、安全路径、本地文件系统、固定 Node/Pi 入口和全树哈希核验；
只依赖已登记的通过检查，不执行 Node/npm/Pi，不重新检查 RPC。

一个短 `BEGIN IMMEDIATE` 事务追加 activation event 并更新单行 current selection，
完整记录 supply_id、install_id、据以比对的完整 snapshot_id、root_id、当时根的绝对路径与时间。
中断和并发下只会读到完整旧或新选择；没有另一个 symlink 权威。
上述身份都是执行审计，不进入供给身份、六投影、校准基线、预算或 enable。
`activation_history(database)` 回查完整追加历史；当前选择必须指向最新完整事件。
后续执行器必须使用自己持有的快照再次匹配全部已选槽，不能只信过去激活成功。

`doctor_supply(database, snapshot_reference)` 和 CLI 均只读，CLI 必须显式 `--scope pi-supply`，
裸命令、未知 scope 或参数错误返回 2。它完整回放全部库内材料、D5、实例与激活引用闭包，
随后只做现场全树哈希，不执行程序、不联网、不写检查、使用记录或激活事件。
诊断区分三个面：

- 供给范围门槛：当前选择存在、所给快照全部槽匹配、平台/根/入口/全树当前可用，
  当前实例的安装保护可确认，库内全量事实闭包可信，实际已登记安装树占用不超过四棵；
  缺项、损坏、当前保护 unknown 或超限返回 2。
- 业务配置：Profile、模型、Prompt、Read 契约等现有缺项独立列出；这些缺项不阻止供给安装，
  也不让尚未实施的 Read 契约将窄供给范围永久判失败。RPC、真实 provider/model、凭据、
  参数映射、生产隔离、正式校准与自动精读独立标注未实施/未验证，不授予任何资格。
- 历史现场与保留：逐实例披露健康、缺失、坏树和无法确认，历史坏树或失去原根不自动否决
  已显式激活的新根当前匹配；它们仍保留审计，实际存在的坏树仍计入四棵占用。
  无法访问的历史现场计数不可确认，不伪造为健康。库内历史事实损坏始终拒绝，不属于此例外。

0 仅表示所选供给 scope 通过，不表示全项目就绪。
D5 decision 与 basis 原文只读显示，不推断 minor/major 或校准兼容。
库级保留查询按最新激活事件向前去重，保护当前和最近三个不同旧 install_id；
同供给不同实例分别计数，同实例反复激活不扩窗。叠加已实施 scope 最近通过对象，
当前仅有 install_check，RPC 如实未验证；在途保护由下述真实共享锁观察，不伪造成功记录。
未激活但现场存在的已登记完整树也计入实际占用，首次部署不要求补齐三个旧实例。
`retention.protection_reasons(records, history, observations)` 是 doctor 与清理计划共用的纯规则；
`execution.retention_protection(records, history)` 仍提供保留/逐 scope 最近通过对象摘要，
二者共用同一保留窗口与逐 scope 查询；
`selection.match_snapshot` 与 `execution.inspect_instance` 分别提供全部槽匹配和现场核验边界。

当前坏实例的修复路径是 `rebuild` 新实例后显式 `activate`，旧坏实例和历史保留。
回退同样须显式选择匹配供给与快照，不自动 fallback。
恢复库保留激活历史和根的位置；同机原实例完整且现场核验通过可继续使用，无恢复标记。
原根/实例不存在则明确指向 rebuild 后再 activate；重建尚未激活时当前选择保持旧值。
新根激活后旧根可永久缺失，历史诊断仍披露缺项。
恢复活动副本若共用原根，旧副本退役前不得执行后续 gc execute；
共享锁只保护在途进程，不能识别另一个空闲副本的 current。

## 安装使用保护与回收互斥

公共服务 `use_install(database, snapshot_reference)` 返回上下文管理器。
先共享锁、重新读取登记及当前选择、比对调用方快照全部已选槽，再完整核对冻结树；
选择在领取过程中变化给 `selection_changed`，调用方须重新明确领取。
句柄 `InstallUse` 固定 `record/instance/supply_id/install_id/node/npm/pi/pass_fds`，
入口均为已核验绝对路径，退出后不得再使用句柄或 fd；在上下文中切换选择不会改变旧入口。
`acquire_install(database, supply_id, install_id)` 给 verify/activate 等明确实例消费者
同一共享保护与可用性复核，不依赖过去激活时的配置来代替执行器自己的快照。

锁文件位于 `<install-root>/.locks/<install_id>.lock`，不进入树身份或任何删除候选，
只由新实例发布路径安全初始化；已登记实例缺锁时不得补建同名 inode，
否则仍持旧 fd 的子进程无法与新锁互斥。缺锁 unknown，必须 rebuild 新实例。共享持有期间的每次真实程序检查都传递
`Runner.run(..., pass_fds=(fd,))`，`ProcessRunner` 将它原样交给 `Popen`。
只 close，不显式 LOCK_UN；父正常退出或 SIGKILL 后子仍持 fd 就仍受保护。
最后持有者退出才释放，不使用 PID/TTL 或业务 lease。详见
[ADR-0029](../adr/0029-protect-installations-through-inherited-flock.md)。

`probe_install(database, supply_id, install_id)` 只读返回
`ProtectionObservation(state, reason)`：`in_flight` 表示真实排他竞争，`idle` 只代表
本次独立探测瞬间无人持有，`unknown` 表示无法安全确认，须保守保护。
doctor 不创建目录/锁、不写事实；逐实例显示 protection_state/protection_reason，
真实持有追加 `in_flight` 理由，无法确认追加 `protection_unknown`。已有保留窗口与
install_check 保护独立叠加；当前实例 unknown 阻断所选供给 scope，历史实例 unknown
独立披露，不自动否决已显式激活的新当前实例。超过四棵仍报告超限，绝不自动删除。

`exclusive_install(database, supply_id, install_id)` 给 GC 非阻塞排他上下文；
竞争给 `install_busy`，缺失或不安全锁给 `protection_unknown`。
取得后仍须持锁完成复核及移出可用集合，不得把探测过的 idle 当成未来执行许可。
`handle.recheck(database) -> str` 重读登记/归属/安全位置并返回实际 tree-v1；
它允许安全坏树，GC 必须与计划实际 hash 比对。共享执行则严格要求冻结预期树。
保护机制自身不执行退役或删除。所有失败先关闭本次 fd 再返回受控错误，
不回显底层异常、子进程输出、环境或秘密，不提供强制绕过参数。

只支持契约既定本地文件系统；恢复活动副本共用原根时旧副本退役前不得 gc execute。
锁身份不进入清单、六投影、校准基线、预算或门禁，也不声称生产 OS 隔离。

## 不可变安装清理计划

```bash
uv run --offline --locked paper-radar pi supply gc --dry-run \
  --database data/paperradar.sqlite3 --data-root data \
  --config-root config --material-root tools/pi
uv run --offline --locked paper-radar pi supply show-plan <完整plan_id> \
  --database data/paperradar.sqlite3
uv run --offline --locked paper-radar pi supply show-plan <完整plan_id> \
  --database data/paperradar.sqlite3 --canonical
```

`create_cleanup_plan(database, *, data_root, config_root, material_root)` 从本库登记根推导全部目标，
只写不可变计划，不删除树、不改变安装可用性、执行选择、配置、预算或门禁。
`show_cleanup_plan(database, plan_id)` 和 `list_cleanup_plans(database)` 完整回放计划历史；
查询不检查现场、不联网、不运行程序。CLI 生成计划必须显式 `--dry-run`；执行仅接受 `--execute <完整plan_id>`，拒绝路径/glob/force。
`show-plan --canonical` 输出保存的规范 JSON 字节再附终端换行；摘要不包含此终端换行。

权威类型为 `pi_supply/cleanup_models.py::CleanupPlan`：严格格式版本 1、未知键拒绝，
共享 UTF-8/排序键/紧凑分隔/无结尾换行规范 JSON；`plan_id=SHA-256(canonical_bytes)`。
创建时间进入计划字节，同一现场多次计划各自留存；本地数据库归属、实际根位置属于计划审计。
持久化保存原规范字节与 ID，跨进程查询和备份恢复不重生成、改写或刷新旧计划。
计划包含：

- `database_id`、`data_root/config_root/material_root`，规则版本
  `library-install-window-v1`、`tree-v1`、`allocated-inode-v1`。
- `facts` 与 `facts_version`：对数据库归属、根、供给清单摘要、安装实例、全部检查、激活历史、
  当前选择和退役识别事实的完整规范视图取 SHA-256；不以时间或 MAX(id) 代替，不含计划自身。
  生成前后及保存短事务内比较安全事实，变化返回 `cleanup_facts_changed` 并要求重新生成。
- `items` 逐项固定供给/实例/root_id、登记绝对根与受控相对位置、installed/retired_pending、
  曾否激活、瞬时 idle/in_flight/unknown、候选/保护/无法核验/缺失、具体理由和全部保护理由，
  冻结预期 hash、计划时实际 hash、真实逻辑字节与分配占用。实际 hash 不要求等于预期；
  安全坏树仍可候选，断链/越界链接/特殊文件等无法安全核验者排除。
- `manual` 单列需人工处理的 staging、未登记树/未知 trash、不可核验根；可安全核验者
  逐项保存 allocated_bytes/logical_bytes 并参与全计划实际占用去重，不进入预计回收；
  无法安全统计者为 null 并保存 occupancy_reason。
  `retired_pending` 单独投影已登记退役原位或 `.trash/<install_id>` 残留。
- `present_count/over_limit`、去重后的 `allocated_bytes`、`reclaimable_bytes` 估算和
  `occupancy_unknown`，未知占用不伪报为零或完整计数。

窗口按最新激活事件逆序对 install_id 去重，保护当前和最近三个不同旧实例，**全库跨供给竞争四个位置**；
同供给多实例分别计数，反复切换同一实例不多占位置。未激活实例也单独说明并纳入候选/占用。
叠加各适用 scope 最近通过保护（按带时区时间/check_id）、真实在途保护和保护未知。
`install_check` 不覆盖/冒充 `rpc_compatibility`；未来范围只在纯规则合成输入中测试，
生产数据库仍仅接受既有 install_check 记录。doctor 与计划使用同一逐实例保留理由。
超过四棵只报告，不绕过保护；prepare、doctor、计划和恢复均不自动清理。

每个根重查整组 safe_roots、普通 marker 归属与本地文件系统；父路径拒绝符号链接。
他库根或无法确认的根标注原因且不扫描；数据、数据库、配置、固定材料、控制锁不进入候选。
未知 staging/未登记树/未知 trash 不能按名字自动认领，始终人工处理。
已登记退役残留只能从既有实例和退役来源计划推导位置；执行入口见下节；有已完成删除审计的身份重新出现时属于未知材料，不能认领为待删残留。

占用真实遍历 lstat 的 `(st_dev, st_ino)`，同树与跨树去重分配块 `st_blocks*512`，
不跟随链接。稀疏文件分别报告逻辑长度与分配量；文件硬链接数超过候选集合内已知名字数时，
预计回收量不包含其数据块，防止将保留树/树外别名共享块算作必然释放。
reflink/压缩/文件系统元数据及并发占用不可精确归因，所以它是预计回收量，不能用 statvfs 差值
单独证明删除正确性；无法核验条目的占用明确未知；安全可读的未知残留只统计大小，仍需人工处理。

历史完整性与执行适用性分开：新激活、检查或退役可以使旧计划不再适用，
但不会使原规范字节、引用闭包正确的历史计划成为腐坏。query/backup/restore 不要求当前 facts_version
或现场 hash 仍相等；它们拒绝规范字节/ID/格式、受控路径、理由或引用闭包损坏。
执行必须取得非阻塞 EX 后重读安全事实、根归属和实际树 hash；漂移必须新计划，不能刷新旧预期。
瞬时 idle 不是删除授权。仍持有的新句柄必须阻止删除；已完全释放且其他安全事实未变的瞬时句柄历史
无需新增 generation/PID/TTL 记录，flock 不声称追溯已结束持有。
恢复活动副本若仍共用原根，旧副本退役前不得执行清理；本机制不提供生产 OS 隔离。


## 安装清理执行与中断恢复

`execute_cleanup_plan(database, plan_id) -> CleanupExecution` 只接受已保存、完整且可回放的计划 ID。
`list_cleanup_executions(database)` 与 `show_cleanup_execution(database, run_id)` 只读回放全部逐项审计；
CLI `gc --execute <plan-id> --database <db>` 不接受另外的根路径；与 `--dry-run` 互斥。
`show-plan` 显示该计划所有 run_id、逐项 phase/reason；`--canonical` 仍仅输出原计划字节。

每次执行追加一个 run_id（32位小写十六进制）、plan_id、created_at，以及按 event_id 排序的
逐项进展：`not_run → retired → moved → completed`，失败追加 `failed` 与受控原因。
单项核验失败只归因于实际失败候选。库级前置未通过时，同一短事务为所有尚未启动候选
追加 `not_run` 阻断事件，reason 限定为 `cleanup_facts_changed/database_unavailable/operation_interrupted/cleanup_failed`；
CLI 明示库级阻断、候选未运行。此终止批次必须整组同原因，不接受部分追加或后续继续运行。
该语义使用既有 a405 表与受控字段，不改变 plan 格式/原字节或旧事件；旧历史照常回放。
退役提交之后中断按库内实际最后进展记录失败，不回退为 not_run；已 completed/failed 不再追加失败。
强杀可能仅留 `not_run/retired/moved`，如实表示未完成，不能报告成功。
`CleanupExecution.events` 保留全部事件；`items` 投影每个候选最新状态，`passed` 只表示本计划全部候选完成，
不表示未知人工残留也已删除。候选为空不会删除任何对象。无模型、预算、配置或业务制品变化。

先完整回放原计划与材料闭包，比对全部数据库安全事实，再取得所有候选的非阻塞 EX。
持 EX 后重复核验根归属、整组危险路径、本地文件系统、当前位置与计划实际 tree-v1。
安全事实保持原样才进入短 `BEGIN IMMEDIATE`：一次追加全部候选永久退役与 retired 进展。
事务不等待 flock，不执行昂贵哈希。此事务后新共享取得、verify、activate 与 available_installs 都排除退役实例；
probe/GC 仍可按登记身份定位树外锁与退役原位/trash，未复制另一套保护协议。

执行仅允许自己刚提交的精确退役增量；其他激活、检查、根、实例或退役变化均拒绝旧计划。
逐项再核对安全事实和实际树，不通过刷新旧计划预期接纳漂移。安全坏树可删除，实际 hash 与冻结预期不同本身不是拒绝理由。
当前选择、最近三旧、各 scope 最近通过、仍持有的新共享句柄与未知保护不能绕过。
已有共享持有者令 EX 返回 busy，父被强杀后子仍持继承 fd 仍会阻止清理。

退役提交后，使用同文件系统不覆盖原子 rename 进入 `.trash/<install_id>` 并 fsync 两个父目录，
再逐项删除。目录 fd 固定实际 inode；目录打开拒绝链接，删除采用 fd 相对操作，拒绝链接/目录替换。
仅对已确认实例的目录恢复删除所需写位，含跨父改名所需顶层目录写位；
不增加无关执行位，不改变计划 tree-v1 身份；普通文件不 chmod，避免改变树外硬链接。
先按依赖顺序删除 symlink 引用者，再删除被引用的 symlink（含目标路径经过的目录链接），
最后删除普通文件和目录；每次删除后 fsync 父目录，使合法半删除残留仍满足严格 tree-v1。
锁文件、根标记、供给父目录、未知树、staging 与其他项目材料不删除。

退役未移动、已移动未删完均由下一 `gc --dry-run` 的新实际 hash 单列“已退役待删”，须显式执行新计划。
删完但 completed 事件尚未提交时，新计划按可信退役与现场缺失显示 absent/无残留，原执行保留 incomplete，
不会伪造旧执行成功。已完成删除事实存在而路径重新出现时，单列人工未知材料并拒绝执行。
旧计划字节、期望、供给/实例/检查/激活历史均不改写，不重复登记供给或安装事实。

当前备份语义回放验证 plan/run/候选/退役引用、带时区时间、受控 phase/reason 与事件顺序；
非空 a404 升级与包含完整/中断清理历史的 backup/restore 均保留原字节，回查无需原安装根。
恢复不会复制安装树或恢复已退役实例可用性。共用原根的恢复活动副本在旧活动副本退役前不得清理；
flock 无法识别另一个空闲副本的选择。此限制与同用户恶意文件替换不属于生产 OS 隔离承诺。

CLI 参数或失败返回 2，中断返回 130；失败只输出身份、受控原因与新计划恢复步骤，不包含底层路径、秘密或程序输出。
帮助完全本地且不创建文件、数据库、锁或计划。所有普通测试只用临时库与目录；本票未验证新的真实 Node/Pi、RPC、网络或用户安装根删除。


## A4 离线验收边界

唯一 `./scripts/check-offline` 追加必需 `.a4.json`，与基础证据、A1、A2-01、完整 A2、A3
组成六份主要文件，pytest 回执另存第七份。A4 独立绑定本次三份必需前置、执行回执、
固定材料/源码/测试、真实迁移与生产格式、环境及代码身份。十项生命周期 capabilities
全部通过才完整通过，不从机制 spike 或退出零推断覆盖。live_install/RPC/完整阶段 A、
真实来源/NAS/自动精读恒未验收；真实 install_check 仍只能查询用户库本次 prepare 记录。
细则见 [离线证据](../verification/offline-evidence.md)；
正文、各轮裁决和补充的责任见 [逐条归属](../verification/a4-requirements.md)。
