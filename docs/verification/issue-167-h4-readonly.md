# #167 H4：四条只读事实与最小观察loader

本轮以所有者明确裁决为边界：core前置过滤器原型未获批准；仅补(a)–(d)只读事实，比较“不外流+可清理+doctor可查”与“全机分发器”的差异化成本，由所有者一次性终局。loader只批准安装树外设计与离线原型，不采用生产启动策略身份，不预定EXP-2重测结论。

本轮开始保留全部前轮未提交工作，基线 `c0bee235f4ebb0a88be4a60c392c96619ec61683`。重读GitHub时原生blockedBy=#140 closed（1/1），subIssues=0/0，仍只有前轮过程回帖；本轮新裁决来自当前会话，优先遵守并回记票中。未闭票或声称Live/B准入完成。

## 四项事实

| 所问 | 本轮结论 | 精确依据与保留限制 |
| --- | --- | --- |
| (a) /var/crash是否在任何备份/同步范围 | **全局unknown**。已核对的PaperRadar默认备份闭包不扫描该目录，已发现dpkg默认备份源也不含它；未找到其被某一通道实际纳入的本轮证据 | [备份范围事实](issue-167-host-crash-facts.md)。不能排除其他用户/root cron、人工任务、根盘镜像或外部快照。rawcore默认另在/var/lib/apport/coredump，不能只核查report目录 |
| (b) whoopsie及任何崩溃上传是否确实关闭 | **已知所列unit当次非活动；全部通道持续关闭仍unknown** | 同一[上传事实](issue-167-host-crash-facts.md)：whoopsie.service/path inactive/dead，path disabled；autoreport三unit inactive/dead，但path/timer enabled、条件marker当次不存在。Apport本地处理active/exited enabled，不把本地生成和上传混同 |
| (c) 固定Node是否先写core再查ignore | 当前/home安装路径判为非打包；默认unpackaged=false常规分支会**在ignore之前调用rawcore函数然后直接return，不再查ignore**；有效limit=0使函数直接不写，非0才尝试写 | [Node分支事实](issue-167-node-auth-facts.md)。不是本轮崩溃实测；未来service uid/有效limit/Apport配置、前置早退与信号仍影响路径。add_proc_info早于该分支，limit0不等于从未采集proc |
| (d) Pi1.4.0是否必须从env取令牌 | **Pi整体并非env唯一**：文档化CLI/runtime及SDK内存入口存在；当前PaperRadar只实现exec env供给，现有RPC无迟交认证命令，秘密迟交整体可行性仍unknown | 同一[Pi文档/源码事实](issue-167-node-auth-facts.md)。先读用户指定docs/docs.json导航，再读相关文档与SDK示例，与项目固定材料逐项13/13 SHA相同。通用API-key示例不直接证明本票ChatGPT短期token迟交可用；不采用argv/文件替代 |

同一普通用户的限定systemctl实时查询跨沙箱读取D-Bus状态成功，不使用sudo/root、不启动服务；初次沙箱EPERM和后补实时证据分列。未查询Environment、StatusText、argv、完整日志或真实进程认证内容。

## loader参考模型与证明范围

[设计与审查标签](../../intent/review/issue-167/loader-design.md)、[离线验证](issue-167-loader.md)。本轮Python原型实际安装/替换合成transport callable，独立peer在发送口维护参照；不是只向事件表手填计数。输出仅category/sequence/count/completeness，缺参照、漏计、重复/晚加载、sink/参照读取故障均unknown并阻断。只在合成窗口完整核对后才complete，不登记为实际HTTP事实或产品通过。

未运行Node/Pi或JavaScript，故真实Node loader的动态覆盖、底层实际HTTP与刷新、事件丢失和可信独立参照仍未验证。已按文档导航核对SDK事件、extension请求hook与custom-provider setup失败语义；不启用生产extension，-ne保持。原型标签只在审查文档，未新增/改动LAUNCH_POLICY_VERSION、pi_protocol或安装树。

## 所有者终局材料

提交[两条core路径成本比较](../../intent/review/issue-167/core-cost-comparison.md)：本地残留/备份排除/上传维持/精确清理与doctor来源完整性的成本，对照全机分发链/根权限新增失败面/非项目透明性与恢复成本。没有推荐或选择方向，未制作分发器。路径一是否满足原core判据、是否接受任何本地短暂残留，以及路径二是否另获范围授权，均由所有者决定；unknown不自行改passed。

是否采用新启动策略身份、采用后EXP-2现场证据重测也留待H4终局。H1/H2/H3/H5与产品独立激活边界继续成立。真实任务仍缺证据阻断，B仍等待完整Live。

## 本轮检查口径

loader新增测试独立D1未绑定，不进入历史分母/required/旧回执。定向pytest、Ruff与mypy、固定范围审计结果在本轮最终回帖记录。未获完整离线门禁指令，未运行。四项事实为有界只读核查，未做备份/同步/上传试运行，没有读取凭据、crash/core或制造崩溃；没有修改宿主、固定安装或产品注册。

本轮最终开发结果（`UV_CACHE_DIR=/tmp/issue167-observation-uv uv run --offline --locked …`）：

- `pytest -q tests/test_issue167_loader.py`：24 passed，仅登记这一新增独立D1模块，不相加旧测试或写入历史分母。
- 定向Ruff check/format通过；`MYPYPATH=src … mypy scripts/issue167_loader.py tests/test_issue167_loader.py`：2 source files通过。
- 独立审阅发现参照Mapping读取异常曾可外传并在恢复参照后重新complete；先写失败回归，再修复为本地快照及不可恢复unknown。items/迭代/索引读取错误与中断已覆盖，中断保留语义并失效。
- 显式base/target的只读固定范围审计含collect退出0，issues/affected_groups为空、skip/deselect=0；未重绑旧登记或改required。
- 新文档本地链接、`git diff --check`通过。`git status --short -- src`为空，产品策略/协议与公共导入链未变，不触发兼容组合。

没有运行完整离线门禁或真实Node/Pi验收。上述通过仅属于合成参考模型与开发审计。
