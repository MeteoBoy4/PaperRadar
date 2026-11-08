# #167 H4-core：(c) 固定 Node 的 Apport 分支与 (d) Pi 令牌来源

本轮仅按所有者新指示做只读核查：已安装公开源码、项目固定Node普通文件的元数据/字节哈希/包归属、当前探针自己的RLIMIT_CORE，以及当前账户已知Apport设置文件是否存在。**未运行Node/Pi、未联网、不读凭据内容/任何真实进程环境/现有core或crash文件，不制造崩溃，不改宿主或产品策略。** 没有访问两个core/report目录的内容；本报告不是现场崩溃实测。

固定供给 `50eb56a3a7fab3c1dcdb3c54ea41a8ff1ca808af65182365368e1b3ef06c6587`、实例 `9b8e342f8bb64a29b1b1b0aa51b68c85`。Node位于该实例 `node/bin/node`，是无symlink的0555普通文件，当前uid所有；本次SHA-256为 `94efd062ed066c1a0b332e18249859c905e920eeada5df55d24c99b919629a90`。未执行版本探测，Pi1.4.0/Node22.23.4版本声明沿用已有固定供给证据。

## (c) 不能把“先写 core 再查 ignore”笼统当作固定 Node 的实际结论

**已知当前安装路径属于 `/home/…`，Apport会将它判为非打包路径。若到达常规process_crash且当前账户保持默认unpackaged=false，它会在ignore检查之前选择“写用户core的回调，然后直接return”，不会再查ignore。该回调在有效core limit=0时立即return而不写core；limit非0时才尝试写独立raw core。** 这是源码分支推导，不能声称本轮实际发生崩溃或落盘。

| 依据/本次观察 | 可证结论 | 保留限制 |
| --- | --- | --- |
| `fileutils.py:129–163` likely_packaged只允许/bin、/boot、/etc、/initrd、/lib、/sbin、/opt、/usr、/var等路径前缀；固定Node当前路径在/home下 | 该绝对路径返回False；该规则本身不查包库 | 后续换安装根/handler身份会改变分支，不能外推 |
| `dpkg-query -S` 针对这一个明确Node绝对路径返回无匹配；Node当前uid匹配 | 独立确认当前dpkg没有登记此文件 | 包归属不是该启发规则唯一来源；不运行Node |
| `fileutils.py:39,499–522` main.unpackaged来自有效uid对应 `~/.config/apport/settings`，默认False；当前账户该明确文件不存在 | 对本轮当前账户配置，默认False成立 | 未来service换uid、该文件出现/变动、handler环境改变都需重查；未扫描其他账户 |
| `apport:1128–1138` 非打包且unpackaged=False时recover_privileges→write_coredump_callback(None)→return；`:1150` check_ignored更晚 | 当前路径的默认常规分支在ignore前调用raw-core写函数，随后直接返回，**不是“先写完再查ignore”** | 到达此分支还须前置一致性检查/容器转发/关闭会话/watchdog等判定允许；这些动态事实本轮未触发 |
| `apport:275–282` write_user_coredump在limit==0立即return；`:286–334` 非0才open目标/读取core流并按限额写入 | 有效limit0不写该独立rawcore，非0会尝试写；权限/目录/磁盘可能令写失败 | 不能由调用函数推定实际文件已创建；没有读目标目录或制造崩溃 |
| 本轮Python只读 `resource.getrlimit(RLIMIT_CORE)` 得soft=0/hard=-1；当前产品launcher.py/auth.py没有设置RLIMIT_CORE | 本轮探针自身soft0；直接继承此限制的子进程可能亦为0，产品源码没有自行保证它 | 不是Pi/Node或未来systemd服务的现场限制实测；不能拿当前shell软限额给所有未来调用背书 |
| `apport:1035–1038` SIGQUIT直接调用write_user_coredump后return | SIGQUIT亦在ignore前离开，仍受上述limit0早退 | 各信号不能混为一条分支 |
| `apport:1140–1153` SIGXCPU/SIGXFSZ可先回调后return；其余路径才查ignore | ignore不是所有core路径的统一早期闸门 | 不是所有信号都实测；信号制造不在本轮许可 |
| `apport:1073` 在常规process_crash之前add_proc_info | 即使limit0使rawcore不写，仍不能据此称collector未读过proc元数据/环境 | report.py会过滤某些环境输出，但过滤呈现不等于没读，不能当无秘密采集证明 |

**raw core和crash report是两类路径。** `fileutils.py:35–36` 默认report_dir=`/var/crash`，core_dir=`/var/lib/apport/coredump`；`:600–637` get_core_path在后者下生成独立rawcore路径。`APPORT_REPORT_DIR`/`APPORT_COREDUMP_DIR`可改变它们，当前handler的全部实际环境未读取，因此这里只确认默认源码位置。

对当前默认非打包分支，独立rawcore可能写在 `/var/lib/apport/coredump`，并非自动生成 `/var/crash/*.crash`；若显式unpackaged=True且其他检查通过，才可能进入ignore、之后创建crash report并将CoreDump写进去，再按core limit另写rawcore（`apport:1155–1223`）。不能只核查 `/var/crash`就推断所有core制品不在备份/同步内；需与(a)(b)并列审阅。此次未读取任何实际两类制品。

## (d) 固定 Pi 1.4.0 并非“只能从启动环境拿令牌”

### 先从全站导航进入，再与固定源码交叉核实

按所有者补充指引，本轮先完整读取指定个人安装的 `docs/docs.json`，从导航进入models/providers、CLI/environment/models configuration、SDK、RPC/RPC commands、CLI integration、security/containerization；再沿SDK的Credentials示例链接读取 `examples/sdk/09-api-keys-and-oauth.ts`。只读公开安装文档和示例，未读个人 `.pi/agent/auth.json` 或任何其他认证文件。

这些材料与项目固定安装的对应文件逐项SHA比较，**13/13字节一致**。这使下表引用具备当前项目字节依据；不是从同名1.4.0版本推定内容相同，也不证明个人安装整树/运行环境等于项目安装。

| 文档/示例依据 | 说明与结论 |
| --- | --- |
| `docs/models.md:17–25` | 明确列runtime `--api-key`、stored auth.json、models.json及env/ambient的优先级，直接否定“上游必须且只能环境变量” |
| `docs/providers.md:10–26,71–85` | 文档说明文件、环境和命令来源；命令延迟求值也涉及凭据配置与新执行面，当前产品禁止，不转化为本轮许可 |
| `docs/sdk.md:96–107,132` → Credentials示例 | 文档允许显式modelRuntime；示例执行 `modelRuntime.setRuntimeApiKey` 后再创建session，**有文档化的内存runtime覆盖使用方法**，不只是一处未公开setter推测 |
| `examples/sdk/09-api-keys-and-oauth.ts:28–34` | 示例面向通用provider API-key覆盖，未独立证明本票ChatGPT订阅短期token、无认证启动/后续模型刷新或全部隔离要求可行；不能把API key示例当订阅认证现场证据 |
| `docs/rpc.md:3–9,18–20` 与 `docs/rpc-commands.md` 全命令标题/认证词检索 | RPC与进程内SDK是不同控制接口；当前完整RPC参考与源码命令集均无显式迟交认证命令。不能把SDK方法误记为已存在的RPC命令 |
| `docs/cli.md:293–316` | auth print-bearer-token输出秘密到stdout，是取出token的宿主命令，不是向已经运行的RPC进程注入token的接口 |
| `docs/environment-variables.md:101` 与 `docs/models-configuration.md:17–20` | 环境是认证来源之一，模型配置还有literal/interpolation/command；后者不因此获准进入沙箱 |
| `docs/security.md:7–23` 与 `docs/containerization.md:21–28` | 文档要求外部文件/进程/网络/凭据边界，环境传入的凭据可见；上游SDK支持不等于满足本票core和宿主安全门槛 |

### 文档对应身份

| 相对pi-coding-agent包路径 | 两份文件共同SHA-256 | 项目/指定文档 |
| --- | --- | --- |
| `docs/docs.json` | `fc0bccd6bf66716ad1067d4fbf7258f674d89c89a12cb0b2587a027b9d7fdc49` | same |
| `docs/models.md` | `c9914f5411db5ddd158b5391ec1da76c1f65788cfaea3a90e1e1555451b3d12e` | same |
| `docs/providers.md` | `bc8798e4cc3209e455e3dc50c6652ae73c057d40122a4a741d8b5b65a041c2f1` | same |
| `docs/cli.md` | `c45e59f31574de71770a71c9a7c9b6ac03bf9cad4928aa31bb6614d661733679` | same |
| `docs/environment-variables.md` | `097f2101e285f51f509be0b176d458825b83b929a635ae29d2a43703168170dd` | same |
| `docs/models-configuration.md` | `1eb60b0f1faad6f9fffd62ea257b545dbc983dbe4c5decc4803b1a241d604155` | same |
| `docs/sdk.md` | `d9034ccbf2219a58712d8dd4fcdf47e687d77131e71dd5d119d8a71e9bd2a2e8` | same |
| `docs/rpc.md` | `37a03d180115460a0a275022f4aeabef1e5345458df6a9b6e8a6de18474de720` | same |
| `docs/rpc-commands.md` | `4deeee367852f4633ef594bc079f9e9fb14640a4e3ba8a69b7c89b6f54740838` | same |
| `docs/cli-integration.md` | `edf8e723a70b4c3c40275db0391219e55d30597936212a9cfdef33963dd37f93` | same |
| `docs/security.md` | `3b1e40a8d28b17c9eb7e496a7ba88fbe04665e3e6ae02873a58b943e325ad504` | same |
| `docs/containerization.md` | `e309fcb9a0a7592c0dba000ef8ee90f2d7ef1e01e6a1ac2f0cd9760dd63dee0c` | same |
| `examples/sdk/09-api-keys-and-oauth.ts` | `d1d2b1bd4e57a3b2ab6f910068e8382759d12a94fbecf1332e96a9ebe4683eb4` | same |

须拆开文档所支持的上游能力、固定源码接线与当前产品边界：

| 层次/入口 | 固定源码事实 | 对秘密延迟供给的意义 |
| --- | --- | --- |
| 当前PaperRadar产品启动器 | `launcher.py:154–187` 将宿主刷新所得短期token放OPENAI_API_KEY后Popen；auth入口从专用凭据目录取得token，当前模型沙箱不开放该目录 | **当前已实现产品路径确实在exec时已带秘密**。本轮不改该env、LAUNCH_POLICY_VERSION或协议注册 |
| Pi首批openai认证解析 | `providers/openai.js:13` envApiKeyAuth绑定OPENAI_API_KEY；`auth/helpers.js:16–25` 先看显式credential.key再查env；`auth/resolve.js:17–37` 支持单次options.apiKey、credential store以及ambient env | env不是底层唯一来源；stored/file路径也存在但不因此获准在沙箱放凭据或落token文件 |
| Pi进程内runtime覆盖 | `core/runtime-credentials.js:8–20` setRuntimeApiKey写内存Map，read时优先返回内存key；`core/model-runtime.js:424–429` 提供setRuntimeApiKey并同步credential状态 | **固定包已有无需将新key持久写入文件的进程内入口**；单从源码不能排除晚于exec后供给的技术可能性 |
| CLI `--api-key` | `main.js:667–675` 解析所得值通过modelRuntime.setRuntimeApiKey安装 | 说明固定实现会调用该内存入口，但argv在exec时仍含秘密且本产品禁止，不能当安全替代 |
| 固定RPC命令集 | `rpc-mode.js:298–540` 与rpc-types.d.ts/docs/rpc.md逐项核对，未见set_auth/set_api_key/credential注入命令；set_model仅切模型 | 当前PaperRadar的RPC路径没有已登记的安全迟交token命令。不能为了延迟供给自行增命令/放宽内核 |
| 默认env取值时机 | `pi-ai/dist/auth/context.js:19–24` 默认ctx.env每次读取当时process.env，而不是此函数中不可变的启动快照 | 仅说明源码取值可晚于启动；外部父进程不能凭此安全改子进程env，也未证明会话初始化可无认证完成或后续model availability会正确更新 |

因此“秘密延迟供给”应记录为**存在文档化SDK运行时内存入口且固定源码支持，当前产品/CLI RPC无已批准接线，整体可行性仍unknown**，不是“必须改Node才可能”或“已经可直接实施”。需要的后续取舍可能包括受控SDK宿主/单独入口、晚于core保护就绪的匿名内存通道、runtime状态/模型选择一致性及初始无秘密阶段行为；全部需要所有者终局裁决和新的具体审阅。本轮不实现这些变化、不运行Node/Pi、不传任何真正或合成token到Pi。

库内存入口也不证明认证宿主安全：auth CLI会读取专用auth内容并可能刷新；controller/认证进程/模型及其后代都必须纳入完整秘密生命周期。仅解决模型晚交token不能让其他持密进程自动合格。

## 本轮验证、材料身份与结论边界

本轮只有静态/元数据事实，没有新增测试、执行Pi或实际崩溃验收。检查一份Node的SHA/owner/type、单个dpkg归属查询、一个明确Apport设置文件存在性、探针自身RLIMIT_CORE；读取上述公开源码并记录行号。文档本地链接和diff检查由主代理集成执行。

下表相对路径的根为本次固定安装的 `app/node_modules/@earendil-works/`；后三项是明确的本机/仓库路径。其身份只供复核本次推导，不追溯扩充历史20项分母或任何现场passed。

| 源码路径 | SHA-256 |
| --- | --- |
| `pi-coding-agent/dist/core/runtime-credentials.js` | `2bf389ca2b04bd4dcee56433ca845cd8d9d96d0ccf84d2d0e9ad2a5e3957bda1` |
| `pi-coding-agent/dist/core/model-runtime.js` | `44d8017928eff6721d5a56b4e71f98bcafb124f5aa6e7d3f016491e11fcf6461` |
| `pi-coding-agent/dist/modes/rpc/rpc-mode.js` | `631697cd35928fc827f4a423538c43ff227b8cbf63c2a2f11060616f55eba6db` |
| `pi-coding-agent/dist/modes/rpc/rpc-types.d.ts` | `68b6dc2e47a3969c09c961a40d0462473407b6786f3bd02715fa035e816e2af1` |
| `pi-coding-agent/dist/main.js` | `08b91f9eb3adf9a5027c18732d1e4de70999bd15c445b65cb0ddd0cd68f2746b` |
| `pi-ai/dist/auth/helpers.js` | `afa67f03895ace888d574c0c86c226cab35521cecc51fe4c0320ba710fb32a97` |
| `pi-ai/dist/auth/context.js` | `5d0ea91a2fd2acf84e3b9717ce59e75006933c68d8efa91873894a9d963d41a0` |
| `pi-ai/dist/auth/resolve.js` | `3fcec09018831324d9c7fb02f4aea707e8a9e4fec5a2bdf1b3d84d716fd3091e` |
| `pi-ai/dist/providers/openai.js` | `9dc3881e858b0280e809ec04b8b17f22580fcb1871da2edf3cfbdfa3c13747b3` |
| `/usr/share/apport/apport` | `e8b57da9924d461fee6d3b392dc184697bc14d2eb8d717c05e1cbf0bd376041e` |
| `/usr/lib/python3/dist-packages/apport/fileutils.py` | `f4237093be3bcfd9e95be2622e721edf1bd21093d080dc8db4cdb7ca18104817` |
| `src/paper_radar/pi_execution/launcher.py` | `48b6c070bb908a1c783e6a357ddc56213806a1baa5ff050a667f74f05c37df56` |

本报告不选core方向，不放宽“不外流+可清理+doctor可查”的任何目标，也不授予全机分发链豁免。
