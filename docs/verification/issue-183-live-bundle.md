# Live 封印审阅包独立工程覆盖

本文件属于新 D1，不扩大历史 required 集合或分母，不替代现场验收。
范围为显式新 Live builder、固定宿主 I/O 和保护部署状态机；旧 v1 模式与 v1–v9 源向量保留原字节。

| 接缝 | 独立模块 | 行为 |
| --- | --- | --- |
| build/derive 与冻结冷入口 | `tests/test_live_bundle.py`（11） | 五字段与空 activation 在输出前拒绝、七计划/严格 β、真实六格材料编译、隔离用户导入 |
| rootless 生命周期/真实 bootstrap | `tests/test_live_bundle_lifecycle.py`（18） | 安装/同 SHA/卸载/恢复、可识别中断、partial/未知成员保留、旧身份与后继 v2 升级、真实 collection 额度/stopped/历史保留 |
| 宿主材料公共投影 | `tests/test_live_bundle_host.py`（15） | 实际层级、四固定 counter、池/规则/handle漂移及 unit 遮蔽/drop-in/额外命令/限额拒绝 |

无 root 模型明确替代宿主 I/O，不证明 systemd、nft、userns/ptrace、真实 cgroup inode 或 OS 权限。
冷入口测试实际复制 Python/stdlib/锁定依赖/源码，在恶意 cwd/PYTHONPATH/PYTHONHOME/.pth/sitecustomize 环境
以 `-I -S -B` 启动，并验证 collect/refresh/model/install 额外参数在任何 root 行为前拒绝。
真实 shell bootstrap 模型核内嵌归档、成员库存和重复运行，不修改生产资源。

三模块共 44 节点。D7 为独立源码守卫 `tests/test_live_admission_source_guard.py`（12 节点），v10 增加新 Live 六个源成员，
旧 v1–v9 向量和原摘要锚保留。新增源码/测试/fixture 的 scope 漂移交最终集成按白名单审阅，
不机械重绑历史登记、不扩大旧计数或放宽冻结负例。

验证命令使用 `uv run --offline --locked pytest` 运行上述三模块、D7、旧 deployment/checkpoint 组合，
并运行 `./scripts/check-compatibility all`。实际计数与结果见本地任务交接；完整离线门禁由父票统一执行。

未执行：sudo/root 部署、cache 迁出、真实网络/auth/model、β/观察/六格、receive/激活、core/Apport 对照。
窗口与所有者网络适用声明尚待精确审阅确认，当前主机 manager degraded 仍阻断。
固定 Pi 缺无秘密自然到期/真实刷新信号，闭环保留 unknown/未验与停止 gate；三次调用不构成证明。
