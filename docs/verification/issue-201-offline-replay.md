# B 隔离脱网回放工程覆盖

本台账记录独立 D1 和本机 `/tmp` 合成 OS 证明，不扩大 A1–A10 历史固定分母、
required 集合或 CI／现场结论。实施基线为 `5c32c7bdd8ee0093c6ebb290171295e7115268ed`，
不新增 migration／表定义，唯一 head 保持 `b007_exposure`。

## 接缝与行为

- CLI 主接缝：`restore verify --replay-container` 产生精确封装与可检查来源回执，
  根级 `replay` 自证隔离后重验内容；标准恢复、backup verify 和 verify_tree 语义保持。
- 恢复接缝：真实 backup → restore verify 子进程 → 实际受限 exec worker 与后代。
  合成外层实验根内 data/config/material 和 restore/session 并列，移动且重复回放；
  不靠重命名原根、布尔标志或一次 HTTP 失败证明隔离。
- 完整链仅替换已批准 HTTP transport、Pi 合成 RPC、Docling parser、clock 边界；
  所有者授权、选样、Screening、PDF、六项版式核查、Read、报告与暴露走真实产品权威。
  恢复后原配置、材料、安装、模型消失及一个源 blob 删除仍能再次回放。
- 持久 evidence-map 重建 orig／pages／bbox／charspan；两份固定 daily/paper 报告与
  一份暴露清单保持原字节，私有视图保留分析全文，公开 stdout/stderr 不含正文/位置。
  evidence-map 实际坏字节返回 file_corrupt，缺成员返回 file_missing。
- 恢复库物理 bytes、全部表 iterdump、预算/attempt/任务/业务历史与原日志不变；
  无 contents 写权限、WAL/SHM 或日志。Reports/ReadTasks/Exposures 显式注入
  FileSink(恢复 views)，入口静态守卫和实际无日志断言分别覆盖，不默认漏接 NullSink。
- 来源回执缺失/不符、未知内容/输出、软链、硬链、源/运行依赖重叠、原根别名、
  worker 无边界与隔离能力故障均受控拒绝；服务 API 仅用于故障注入。
  成功结果严格枚举/非负计数，参数自由文本和原始异常不能透传，0/2/130 固定。
- 回放后仍能显式 db upgrade 恢复工作库 WAL，不增加永久 replay-only 执行禁令。

唯一现状规则见[备份/恢复 Contract](../contracts/backup-restore.md#隔离脱网回放)。

## 本机实际 OS 正反对照

Linux `7.0.0-31-generic` x86_64、Landlock ABI 8、Python 3.14.4。
与既有探索比对：Pi isolation 原 SHA `718a6499…40d31` 相同，sandbox 基线
`b16e7c6a…369d` 相同；本票仅提取纯 seccomp，当前 `76e28ccc…10af`，
没有复用探索的通过结论作为业务完成证明。

| 操作 | 本次未限制正对照 | 本次受限 exec |
| --- | --- | --- |
| 恢复成员读 | allowed | allowed |
| 合成原件／逃逸软链读 | allowed | EACCES／EACCES |
| AF_INET／INET6／UNIX socket 创建 | allowed ×3 | EPERM ×3 |
| 已打开未连接 fd 的直接本地 UNIX connect | allowed | EPERM |
| no_new_privs／seccomp | 0／0 | 1／2 |

产品 worker 另外在每次回放中自证全部声明来源、contents 写拒绝、views 写成功及后代继承。
生产 pass_fds=()；仅合成对照刻意传一个未连接 socket，以观察 connect syscall 本身。
全部 listener 和材料均在新建 `/tmp`，没有任何互联网请求。
普通工具沙箱不能提供 socket 正对照时，这项合成探针经明确限定的 escalation 执行。
原始 JSON 为仓库外 `201-os-control-results.json`，脚本 `201-os-evidence.py`；
环境与完整源码 SHA 另见 `201-os-identity.json`、`201-os-source-sha256.txt`。

仅证明本次可信代码/安装与普通布局下的内容访问边界；不证明任意 mount alias、
同 UID 恶意并发替换、路径元数据隐藏、通用恶意代码沙箱或其他平台可用。
未执行真实/live 命令，未接触真实实验根、运行专用 checkout、私有准备单／回执或凭据，
未启动 Pi/OAuth、Docling SDK 或模型；不能替代真实现场脱网验收。

## 独立 D1 清单

| 模块 | 节点数 |
| --- | ---: |
| `tests/test_replay_business.py` | 1 |
| `tests/test_replay_container.py` | 1 |
| `tests/test_replay_entry.py` | 2 |
| `tests/test_replay_faults.py` | 23 |
| `tests/test_replay_os.py` | 1 |
| `tests/test_replay_process.py` | 2 |
| 合计 | **30** |

支持为 `tests/replay_support.py` 与 `tests/replay_os_probe.py`，均进入静态检查。
精确节点/数量保存于仓库外 `201-final-d1-collection.txt`、`201-final-d1-counts.json`；
collection 不作为执行证明。

## 实测与集成边界

原始离线开发日志位于仓库外 `/tmp/paperradar-185/201-*.log`，不作正式验收回执。

- TDD 红：冷帮助缺命令、restore 缺封装选项、replay 缺 worker、缺库原因被抹掉、
  成功 stdout 允许自由文本；对应 `201-red-{help,container,process,faults,summary}.log`。
  uv 初始只读 cache 故障不是红灯，使用既有离线 cache 同步，没有联网补包。
- 完整合成业务最终单节点：`201-final-business.log`，**1 passed /178.65s**，
  含第二次移动回放和 evidence-map 篡改／缺失。
  最终新 D1 同次 **30 passed /222.44s**，见 `201-final-d1.log`。
- 公共组件回归：`201-components.log`，**62 passed /203.63s**：备份服务5、恢复服务4、
  恢复故障25、恢复CLI11、备份架构1、正文制品10、暴露历史4、Docling隔离/资源2。
- CLI 兼容：`201-cli-compatibility.log`，**59 passed /87.39s**，入口88.09s；
  独占 TMPDIR 预先创建，不写正式回执。
- 全部 **21** 个改动／新增 Python（含全部新 tests/support）strict mypy、Ruff、format 通过；
  路径并集 `201-static-paths.txt`，最终日志 `201-final-{mypy,ruff,format}.log`。

完成前 merge 最新 integration；实际 commit-range diff-check 和 scope 结果留最终交接。
不机械重绑 source/support，不改旧 trace3 整对象与 D7 两向量；这些继续交 B 收口。
本票不提供 C importer、merge engine、NAS、任务续跑或跨副本执行协调。
重复外发授权、预算和租约风险由 I 评估；恢复内容通过不等于执行环境／真实质量通过。
