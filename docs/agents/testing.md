# 测试

- 修复 Bug 时，先写一个在修复前失败的回归测试。
- 常规测试完全离线：使用固定 fixture / mock，不访问实时网络、付费 API 或用户数据库。
- Live source 验收通过显式命令运行，且只在用户明确要求、配置和 credential 可用时运行。
- 新增或修改 migration 时，测试从上一 revision 升级到当前 revision；涉及快照或恢复的改动，测试恢复路径。
- 完整离线验证入口与证据格式见 `docs/verification/offline-evidence.md`。
