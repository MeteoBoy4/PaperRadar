# Pi 固定供给 Contract v1

当前交付 `pi supply prepare/verify/rebuild/list/show` 和公共 Python 服务
`paper_radar.pi_supply.prepare_supply/verify_supply/rebuild_supply/list_supplies/show_supply`，
以及供后续激活选择使用的只读 `available_installs(database, supply_id)`。
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
整数格式版本严格为 1，布尔不算整数。证据文件相对请求文件解析。

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

独立向量：根与 `bin/` 可执行，`bin/run` 内容为 `hi\n` 且可执行，`run` 为 `bin/run` 的相对链接，
树摘要为 `3ba7d3e8a26699a27360c5f3575eee704abe8cb77f572e0a21f768a798b96573`。
测试使用固定字面量并验证不同 staging/umask/mtime，以及内容与执行位变化。

## 安装实例、发布与恢复

安装根须与显式 data/config/materials 根两两互不包含，且不能含数据库；路径组件拒绝符号链接。
仅支持本地 ext2/3/4、xfs、btrfs、zfs、tmpfs、overlay，按 Linux 实际挂载点识别；不支持 NFS/CIFS。
512 MiB 可用空间预检只前移空间不足，不能取代后续校验或保证真实安装空间足够。

```text
<install-root>/.paper-radar-install-root       # 本库稳定随机身份与随机根身份
<install-root>/.staging-<随机>/tree/{node,app} # 发布树
<install-root>/.staging-<随机>/work/           # 本次私有临时环境，发布树外
<install-root>/<supply_id>/<install_id>/       # 只读完整实例
```

首次空根通过 flock 串行认领并与数据库稳定 owner 绑定；他库根、非空无主根拒绝。
DB旁发布锁→根锁→固定输入锁在写事务外取得，昂贵下载/安装不持写事务。
完整树与发布意图 fsync 后以 Linux renameat2(RENAME_NOREPLACE) 发布，连既有空目录也不覆盖。
Linux 移动目录时顶层短暂保留写位，发布后撤去并 fsync，之后才能短事务原子登记材料/清单/实例/成功检查。
根与意图等本机管理文件不进入供给身份；不把 .staging/.pending 或未登记树当可用安装。
发布后事务失败/强杀只有残留完整树；相同完整意图与预期树重新核验后可重入登记，未知残留不删除。

普通重复 prepare 在再次安装前拒绝并指向 rebuild，即使改 D5 也不能重冻。
同时开始的相同完整请求先提交者胜；输者比对清单和现场树后返回既有 supply_id/install_id，
清理自己的 staging，不登记第二实例。相同固定输入得到不同树或 D5 时受控冲突。
list/show 只回查历史，不检查现场，不要求 Pi、网络或受支持平台，不能把历史 passed 当作当前可用。
检查 scope 当前唯一为 install_check；不导入任意用户声明成功记录。

数据库 head 为 a402_pi_rebuild_failures；a401 原 migration 字节保持，
本次只追加 `pi_rebuild_failures`，不为失败安装创建实例或把失败记到旧实例。
供给小型材料与 D5 证据随数据库备份，backup format 仍为 1，语义回放同时校验供给闭包。
恢复不安装、不下载、不激活。a302 旧批次须先用匹配 A3 程序恢复，再切新程序 db upgrade；
不放宽 head gate。恢复副本共用原根时，旧副本退役前禁止未来 gc execute；flock 仅保护在途进程，
不能区分两个空闲活动副本。

未来导出固定集合为 package.json、package-lock.json、release.json、supply-manifest.json、
integrity-supplements.json、SHASUMS256.txt 与 d5-evidence/<SHA前16位>.bin；
derived-lock.json 是内部保存的确定性派生材料，不增加到已批准导出集合。
版本控制目标 tools/pi/<supply_id>/，安装树 .tools/pi/<supply_id>/<install_id>/ 被 Git 忽略。
rebuild 重新联网下载固定摘要的 Node/tarball，不承诺脱网重建。

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
