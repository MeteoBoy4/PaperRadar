# Pi 1.3.0 固定供给机制 spike

2026-10-18，为 [Issue #37](https://github.com/MeteoBoy4/PaperRadar/issues/37) 执行；依据父票 [#36](https://github.com/MeteoBoy4/PaperRadar/issues/36) 的派生锁与网络裁决，以及将示例版本改为 1.3.0 的更正。结论：**本机正例安装、无模型启动检查与完整性拒绝均已实测通过，可继续 A4 实现**。1.3.0 不成为默认版本；这不是项目供给登记、部署、产品 `install_check`、A4 live 验收或 RPC/模型验收。

## 实测工具链与隔离边界

- Pi `1.3.0`，release `sourceCommit` 为 `71023aec1546d6d677a65669c5665c0927ce0dd0`。
- Node `22.19.0`，自带 npm `10.9.3`，平台 Linux x86_64 / glibc `2.43`。Pi 根材料及实际 Pi 包的 `engines.node` 均为 `>=22.19.0`；实装未出现 engines 不兼容告警。
- 独立目录 `/tmp/paperradar-pi130-spike`；官方材料、Node 发行目录、正负例 app、HOME、agent、session、XDG、npmrc、cache、tmp、日志均在其内。没有读取个人 npmrc/cache、个人 Pi、个人 Node 或用户数据库，没有激活项目安装，没有模型调用。
- 启动 npm/Pi 用完整环境字典，只有本次私有路径、固定 locale 与列出的开关；不继承凭据、`NODE_OPTIONS`、个人配置、代理或其他进程环境。PATH 只指向本次 Node 的 bin；执行明确 Node 与 JS 路径，不依赖 shebang。
- 本次直连成功，未使用代理。下载命令显式 `--noproxy '*' --proxy ''`；npmrc 显式 `proxy=null`、`https-proxy=null`。带 userinfo 代理的生产拒绝规则和可用的显式代理连接未在本次实际连接中验证。

## 一手材料与固定哈希

保存以下端点的响应原字节；本次全部返回 HTTP 200，无重定向：

| 材料 | 官方来源 | 字节数 | SHA-256 |
|---|---|---:|---|
| package | [package.json](https://pi.dev/api/installer/releases/1.3.0/package.json) | 317 | `efa2ca2695c003c92febb3bca40c5de5f94d43a8aa78e1ba88420b30156d5e21` |
| lock | [package-lock.json](https://pi.dev/api/installer/releases/1.3.0/package-lock.json) | 50966 | `65eacda789c30e1c3859a96eee2fd53cf4a18629d27dcf2aa6d7bdb3da02d719` |
| release | [release metadata](https://pi.dev/api/installer/releases/1.3.0) | 2945 | `c4d719422b35fb65d839fe01e4850a1c19a074cf37f8d1d911f9706b4b22c756` |
| Node 校验依据 | [SHASUMS256.txt](https://nodejs.org/dist/v22.19.0/SHASUMS256.txt) | 3777 | `de2602986573174f8815e5c66a157950132166113edddd9124c30784303ede31` |
| Node archive | [node-v22.19.0-linux-x64.tar.xz](https://nodejs.org/dist/v22.19.0/node-v22.19.0-linux-x64.tar.xz) | 30479988 | `c0649af18e6a24f6fe5535a3e86b341dd49a8e71117c8b68bde973ef834f16f2` |
| derived-lock-v1 | 本次从上述原材料确定性生成 | 44388 | `a342ed1baea205543bdcaf82ec4aed2bfc771a5c2c47b2bacb8238d06513e7c6` |

Node archive 的 SHA-256 与所保存的官方 SHASUMS 精确文件名条目一致后才解包。仅验证 HTTPS 官方来源及该摘要；未另做发行签名或独立信任渠道核验。

## 1.3.0 实际包集合与派生规则

官方 lock 为 `lockfileVersion=3`，`packages` **120 条（含 root），实际依赖 119 条**。release metadata 提供 **10 个包**，其中 **7 个**匹配 lock 的缺失 integrity 条目；其余 3 个 release 包不在本次安装依赖图内，不额外安装。lock 中没有标为 `optional` 的条目，本次没有覆盖其他平台的 optional dependency 选择。

缺项均为 `@earendil-works/` 下的 `pi-agent-core`、`pi-ai`、`pi-codemode`、`pi-coding-agent`、`pi-mcp`、`pi-telemetry`、`pi-tui`，版本均为 `1.3.0`。不能沿用 1.1.0 的包数或缺口数。根 package 与 lock 的版本、根依赖、engines 相符，官方 override 保留 `protobufjs=7.6.6`，lock 中该包实际版本也为 `7.6.6`。

本次 `derived-lock-v1` 规则：

1. 以官方 lock 解析对象的深拷贝为起点；root 不需要 tarball integrity。
2. 每个非 root 条目按 `name`（缺省从最后一个 `node_modules/` 后提取）、精确 `version`、精确 `resolved` 三元组匹配 release 条目；release 重复键拒绝。
3. 只给原先没有 integrity 的匹配条目填入 release 的 `sha512`；已有值如与匹配依据冲突则失败，缺项仍无依据也失败。逐条确认去掉本次新增 integrity 后与官方条目完全相等，故 version、resolved、依赖图与其他字段不变。
4. 全部 119 个 resolved 均为 HTTPS `registry.npmjs.org`，无 userinfo、无其他端口；全部非 root 条目最终有 `sha512`。
5. 用 `json.dumps(derived, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")` 序列化，无末尾换行，得到上表字节与哈希。

正例 app 复制官方 package 原字节，`package-lock.json` 使用派生字节；官方 lock 单独保存且不改写。`npm ci` 后 app 的锁文件仍与派生哈希相同。此处派生字节编码是本次可复现向量，后续生产实现应明确采用相同规则或另记不同派生规则版本，不能混称同一字节身份。

## 实际安装与正负例

明确执行入口：

```text
<root>/node-v22.19.0-linux-x64/bin/node
<root>/node-v22.19.0-linux-x64/lib/node_modules/npm/bin/npm-cli.js
<root>/app/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js
```

固定 npm argv 为 `node npm-cli.js ci --ignore-scripts --omit=dev --include=optional --no-fund --no-audit --update-notifier=false`。本次 npmrc 另固定 `registry=https://registry.npmjs.org/`、`audit=false`、`fund=false`、`update-notifier=false`、`ignore-scripts=true`、`fetch-retries=0`、`fetch-timeout=30000`、私有 cache 以及上述空代理。`NPM_CONFIG_USERCONFIG` 指私有 npmrc，`NPM_CONFIG_GLOBALCONFIG` 指本次空文件，`NPM_CONFIG_CACHE` 指私有 cache；cwd 为本次 app，执行超时 240 秒。

| 检查 | 实测结果 | 含义 |
|---|---|---|
| 干净安装 | 退出 0；`added 119 packages in 3s` | 固定派生 integrity 可以被真实 npm ci 使用；保留 override；没有生命周期脚本 |
| 污染 cache，离线重装 | 退出 1；先报 cache/tarball 损坏，尝试刷新，最终 `ENOTCACHED` | npm 丢弃损坏缓存而没有把坏字节安装成功；不能写成 EINTEGRITY，也不能把在线自修复成功算作负例通过 |
| 专属 staging 错误期望摘要 | 真实 npm ci 退出 1，`EINTEGRITY`，27361 bytes | 只在 negative-app 的派生锁把 pi-telemetry integrity 替换为有效编码的全零 sha512，官方材料和正例 app 不动；真实下载的官方字节不符合该错误固定摘要，因此被拒绝 |
| 同版 npm 内置 pacote 的额外检查 | `EINTEGRITY`，algorithm `sha512` | 对保存的同一包正确 tarball 追加受控字节，沿用官方期望摘要，通过本次 npm 自带的 `pacote.tarball.file` 验证路径直接拒绝；与 npm ci 的 cache 负例分开记录 |
| 污染后恢复正例 | 退出 0；重新安装 119 个包 | 只恢复本次临时环境，供后续启动检查 |

直接 npm ci 负例的脱敏关键输出：

```text
npm error code EINTEGRITY
integrity checksum failed when using sha512
wanted sha512-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==
got    sha512-ERGZr+aXjNJzoUbB7ZzHVH3g5otzMHjHLs2Fyizm12By5X+gBEhod9cJXFOk13S7M8a29Am+Mq21zm73mRJFLg==
(27361 bytes)
```

这里的 got 正是 release 为 pi-telemetry 1.3.0 提供的 integrity。正例链条为“官方固定摘要 → staging 派生锁 → 同版 npm 实际 tarball 校验 → 安装”，不是预检一份 tarball 后允许 npm 无摘要另取内容。额外 pacote 检查使用的也是上述官方摘要；输入追加字节后的摘要为 `sha512-nOs0NzwC9C2m/RxDFVjNO87UC6/Y+Qp7nPteWQ1s7EAYSfVqwTDECIupGFVNCpaE+yZDJxasKLGiaIbc5TuxBw==`。

## 无模型 help/version、更新与遥测

依据安装 tarball 内的官方 `docs/environment-variables.md`、`docs/settings.md`、`dist/core/telemetry.js`、`dist/utils/version-check.js` 与 `dist/main.js`：`PI_OFFLINE=1` 关闭自动网络活动，`PI_SKIP_VERSION_CHECK=1` 跳过版本请求，`PI_TELEMETRY=0` 覆盖安装/更新遥测和 provider attribution；私有 settings 另设 `enableInstallTelemetry=false`、`enableAnalytics=false`。包 `@earendil-works/pi-telemetry` 本身提供 vendor-neutral/no-op 合约，不等于 CLI 安装遥测已经关闭。材料归属可从上表 release 链到 [Pi 官方源码固定提交](https://github.com/earendil-works/pi/tree/71023aec1546d6d677a65669c5665c0927ce0dd0/packages/coding-agent)。

执行 `node <Pi JS入口>`，固定附加：

```text
--offline --no-session --no-extensions --no-mcp --no-skills
--no-prompt-templates --no-themes --no-context-files --no-tools
```

然后分别附 `--version`、`--help`；没有 prompt/provider/model。私有 HOME、`PI_CODING_AGENT_DIR`、`PI_CODING_AGENT_SESSION_DIR`、三项 XDG 路径、TMPDIR 均显式传入，cwd 为空的本次私有目录。

- `--version` 退出 0，stdout 为 `1.3.0\n`（6 字节），stderr 为空，无私有文件变化。
- `--help` 退出 0，stdout 10705 字节，stderr 为空。首次运行在私有 agent 目录创建 `auth.json` 与 `models-store.json`，内容均为 `{}`；重复运行无文件变化。**help 并非完全不写文件**，这些目录必须位于发布树外。session 目录始终为空，没有持久会话，也未发现个人资源加载。
- 使用 `strace -f -e trace=network` 观察这两次完整子进程执行，未观察到 socket/connect/send/recv 网络系统调用。初次受限环境禁止 ptrace，经本次授权的独立观测权限运行后成功。

以上是这两个入口的实测，不是 OS 网络封锁；受控参数和一次 strace 观察不能证明任意业务运行都具备 OS 网络隔离。没有实现或扩大生产 sandbox，也没有测试 RPC、取消、模型预算、provider 身份、正式语义或校准。

## 来源与代理纪律的限制

父票白名单为 `pi.dev` release 材料、`registry.npmjs.org` 的精确 resolved，以及 `nodejs.org/dist/`。spike 的官方材料下载没有使用自动跳转；每份请求先检查状态/Location，本次没有需要继续跟随的跳转。若出现白名单外 Location 应立即停止交回父票裁决，不能自行增加来源。本次不构成实际多跳重定向或代理成功/拒绝矩阵的测试。

生产 Python 下载器须禁用自动跳转并逐跳校验目标；npm ci 的内部 HTTP 跳转不能按同样方式逐跳控制。本次 npm 的保证来自预先校验全部 resolved 与逐包固定 integrity，以及上述真实拒绝证据；没有宣称 npm 传输的每一跳都已被 Python 白名单控制。

## 复现与临时证据

普通离线测试不执行本 spike。复现必须显式授权联网，并使用新私有临时根目录，禁止复用个人 cache/npmrc 或用户库。

1. 从上表精确端点下载原字节，禁用环境代理和自动跳转，设置超时与大小上限；先核对响应状态、来源、材料版本及上表摘要。下载 Node archive 并与官方 SHASUMS 精确文件名记录比较。
2. 依上文三元组与编码规则补齐且仅补齐 7 项，生成同哈希派生锁；保留官方 lock。解包精确 Node，分别用明确入口确认 Node/npm 版本。
3. 在新 app 和私有环境中执行固定 npm ci。正例完成后，按 pi-telemetry 官方 SRI 的 sha512 十六进制定位 `cache/_cacache/content-v2/sha512/<前2位>/<次2位>/<余下>`，先独立核对原字节摘要，再翻转一个中间字节，以相同 npm ci 加 `--offline` 记录实际拒绝。
4. 在另一个 negative-app 中保留同一 package 与依赖图，只把 pi-telemetry integrity 改为上文有效编码的错误 sha512，再跑固定 npm ci，要求直接 `EINTEGRITY`。不要篡改官方材料。可另用同版 npm 的 `node_modules/pacote` 对正确 tarball 追加字节做固定期望摘要检查。
5. 重新完成正例安装，在私有 agent settings、环境和空 cwd 下执行上述 help/version，检查输出、文件副作用、session 目录；若可用，用 strace 观察网络系统调用。保留这些观测的实际边界，不将其写成 OS 隔离验收。

本次完整原始材料、安装包、独立工具链与日志仅留在 `/tmp/paperradar-pi130-spike`，不提交 Git，临时目录可能被系统清理。该目录的 `derive.py`、`npm_run.py`、`npm_negative_run.py`、`integrity-negative.cjs`、`startup.py` 保存实际操作；`materials/` 保存原字节及派生/负例材料，`logs/` 保存 HTTP 头、执行状态、npm 完整输出、help/version 与 strace。仓库只保存本脱敏机制记录。

本票没有产品代码或测试变更，因此按 #37 约定不新增产品测试、不重复运行整套离线检查；上述真实机制正负例是本票验证。A4 的公共服务、迁移、安装树身份、原子激活、清理、备份恢复和 live 结论仍须由后续票各自实现与验证。
