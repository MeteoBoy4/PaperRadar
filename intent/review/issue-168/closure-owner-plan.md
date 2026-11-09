# #176 所有者待审：单次真实收紧/恢复与最终激活

本文件是操作提案，尚未执行，也不构成 root 字节审阅、真实恢复或证据激活授权。
当前实际站点分项已由所有者激活；本方案会暂时使全部激活失效，必须完整读完再批准。

1. 保持当前已部署 v3 runtime 原字节与策略；从其原封印包取得 payload SHA 和 manifest 文件 SHA。
   非特权构建：`uv run --offline --locked python scripts/issue176_closure.py --help`。
   明确提供这两个摘要、已接收回执短 ID 和全新私有输出目录；构建不访问真实站点或执行 sudo。
2. 审阅生成目录的 `REVIEW.md`、`config.json`、`workflow.py`、`run-owner.sh` 和 `SHA256SUMS`。
   同时核对最终源码/测试/登记审阅；任何字节改变重新生成并重审。具体本机 ID/摘要只进入私有材料。
3. 暂停其他业务任务及准入写操作。所有者执行 `./run-owner.sh`，只请求一次 sudo 密码。
   root 先核旧 runtime 完整成员、原 payload/manifest、全部摘要、属主/权限/链接、三个入口与 sudoers，
   再从已审入口内嵌的精确字节生成新脚本/配置到新的 root 冻结目录并重核 SHA（root不读取用户可写来源）；不更改 runtime 或新增 sudoers 规则。
4. 初始只接受最终 boundary-low 非空 active 且无其他 active 组；临时 value-low 须未撤销、尚未 active。
   固定 collector 真实刷新后逐项核当前适用性，原 verified_at 不变；条件改变安全拒绝。
5. 所有者完整审阅实际回执后，**本人手输短 ID**临时激活 value-low。
   以独立解释器/连接重读；备份包含该激活的账本，再通过只收紧 helper 不可逆撤销 value-low。
   再以新进程核对撤销持久化。这一临时格不再恢复旧资格。
6. `EvidenceLifecycle.restore` 合并刚才受保护的备份；保留在线尾部撤销、全部历史及水位线，
   追加恢复屏障，所有既有激活失效。新进程必须确认无 active，临时格撤销仍在。
   本流程只验证新进程重读，不声称主机/服务实际重启；若“重启”需真实主机动作，另行裁定范围。
7. 所有者重新完整审阅最终 boundary-low，**本人再次手输短 ID**激活。
   每次激活前/确认后都调用已部署固定 collector；受60秒新鲜度和真实计划窗口约束，不伪造 fresh、重试 stopped 或续期。
   最终新进程必须确认原非空能力集合均 active 且当前适用，临时格仍撤销。
8. 只读比较必要预算标识/指纹、代际、attempt 序号和每日领取标识的前后计数/摘要；
   不查询 payload/token/Prompt/Profile/全文，不写库、不 compile/rebuild/reinstall。
   任务须暂停且无 WAL/SHM/journal，以 immutable 只读连接避免生成 sidecar；存在侧文件直接拒绝，不删文件。
   全部步骤成功才追加 root 安全回执，记录原主张、原时点、激活事件、绑定摘要、用途与登记/期限依据。
   root 检查点、备份和安全回执全部保留；普通用户报告只作为索引。

任一步失败或中断都不自动回滚、清理、生成完成回执或恢复资格；保留 root 阶段文件。
若失败在恢复之后而最终激活之前，当前应保持无 active；恢复路径是所有者核对检查点、重新刷新并完整审阅，
再从现有 root 冻结 owner 入口手动激活 boundary-low：

```text
sudo /usr/libexec/paperradar/live-evidence-owner activate --receipt-id <实际短ID> --use-id boundary-low
```

该命令仍要求本人短 ID，可能因初始观察过期先拒绝；先由固定已审 collector 按原计划刷新，不能自动填入确认。
不要重跑整个演练来“撤回”临时格撤销；已撤销旧资格永不翻转。
本方案不卸载部署、不停止/重启主机服务、不清预算、不认证/调用模型/联网或导入历史探索证据。
当前模型/RPC/IPv4/observer缺口保持；部分 active 不证明 Live/B 完成。
