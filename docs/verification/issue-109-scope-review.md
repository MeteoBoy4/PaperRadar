# Issue #109 scope 审阅记录

基线 `d5812a4b8b231152422adc1733bcc04504ebfc0a`。README 仅新增开发入口导航，
公共参数、退出码、副作用与证据边界另记 `docs/contracts/check-compatibility.md`。
按 A8 → A9 → A10 的真实哈希依赖顺序重审如下六处；业务源码、旧入口/旧测试、
固定测试分母、required 组、直接前置及全部 Frozen Contract 均不改变。
不将开发期入口或新增测试扩大登记到任何独立验收 scope。

| Scope | 路径 | 旧 SHA-256 | 新 SHA-256 | 必要原因 |
| --- | --- | --- | --- | --- |
| `scripts/a8_scope.py` | `README.md` | `9c21c0726ee8b270bebcfbd4c0636656354416089059299f4ea214e15d397173` | `e321939033fb983a9d26a1b372c49d10d95c56df76298315674815f992bf1ef1` | README 新增开发入口说明，验收语义不变 |
| `scripts/a9_scope.py` | `README.md` | `9c21c0726ee8b270bebcfbd4c0636656354416089059299f4ea214e15d397173` | `e321939033fb983a9d26a1b372c49d10d95c56df76298315674815f992bf1ef1` | README 新增开发入口说明，验收语义不变 |
| `scripts/a9_scope.py` | `scripts/a8_scope.py` | `c865344a083765e906a0eddf0907ef16e8479c732ca9df4c68be2e7a3d976152` | `b8213f369c057c4d7329fe762fc7ff8bfb563b0ac9e12393cbb1dfe5d409f166` | 传播已经审阅的上游 scope 字节变化 |
| `scripts/a10_scope.py` | `README.md` | `9c21c0726ee8b270bebcfbd4c0636656354416089059299f4ea214e15d397173` | `e321939033fb983a9d26a1b372c49d10d95c56df76298315674815f992bf1ef1` | README 新增开发入口说明，验收语义不变 |
| `scripts/a10_scope.py` | `scripts/a8_scope.py` | `c865344a083765e906a0eddf0907ef16e8479c732ca9df4c68be2e7a3d976152` | `b8213f369c057c4d7329fe762fc7ff8bfb563b0ac9e12393cbb1dfe5d409f166` | 传播已经审阅的上游 scope 字节变化 |
| `scripts/a10_scope.py` | `scripts/a9_scope.py` | `b54b2590aeceed9cd1e47024c4f8abe5a9cbb5013ee014e2a38967b19a3d0436` | `c190621857a29853c6567d0f519616958d0c2250d0b1e9e657a10bb40e094209` | 传播已经审阅的上游 scope 字节变化 |

使用 `audit-verification-scope` 核对登记与拓扑；完整离线入口仍独立校验真实材料。
最终运行身份、原始证据、组合计时及受控回归记录保存在本地忽略目录，不将 run_id
或最终提交 SHA 回写被哈希材料，也不修改历史原始证据。

## r1 审查修复

基线 `8fd310f00fcf820614c0b16285c16ce2e0e86296`。README 只同步中文帮助与宿主
Python 引导前提；入口/测试本身仍为独立开发范围，不扩大既有固定 scope。
原登记记录保留，按同一 DAG 追加如下六处哈希传播；全部测试分母、成员、前置、
required 和 Frozen Contract 保持原样。复核意见与逐条处置见
`intent/review/issue-109-check-compatibility-review-r1.md`。

| Scope | 路径 | 旧 SHA-256 | 新 SHA-256 | 必要原因 |
| --- | --- | --- | --- | --- |
| `scripts/a8_scope.py` | `README.md` | `e321939033fb983a9d26a1b372c49d10d95c56df76298315674815f992bf1ef1` | `c4d9b87d4abbb77a777e6c90a77ae8892f83b75c8c78adeaf781cc79310eb0d2` | 帮助与宿主引导前提同步，验收语义不变 |
| `scripts/a9_scope.py` | `README.md` | `e321939033fb983a9d26a1b372c49d10d95c56df76298315674815f992bf1ef1` | `c4d9b87d4abbb77a777e6c90a77ae8892f83b75c8c78adeaf781cc79310eb0d2` | 帮助与宿主引导前提同步，验收语义不变 |
| `scripts/a9_scope.py` | `scripts/a8_scope.py` | `b8213f369c057c4d7329fe762fc7ff8bfb563b0ac9e12393cbb1dfe5d409f166` | `8affa58d099bd71eb6cdec08151e8afe63850dad128c32a33ddaa0e9d03d9661` | 传播已审阅的上游文档绑定字节 |
| `scripts/a10_scope.py` | `README.md` | `e321939033fb983a9d26a1b372c49d10d95c56df76298315674815f992bf1ef1` | `c4d9b87d4abbb77a777e6c90a77ae8892f83b75c8c78adeaf781cc79310eb0d2` | 帮助与宿主引导前提同步，验收语义不变 |
| `scripts/a10_scope.py` | `scripts/a8_scope.py` | `b8213f369c057c4d7329fe762fc7ff8bfb563b0ac9e12393cbb1dfe5d409f166` | `8affa58d099bd71eb6cdec08151e8afe63850dad128c32a33ddaa0e9d03d9661` | 传播已审阅的上游文档绑定字节 |
| `scripts/a10_scope.py` | `scripts/a9_scope.py` | `c190621857a29853c6567d0f519616958d0c2250d0b1e9e657a10bb40e094209` | `2a57b3bc0754175bfbf38c5550132f99d2393c37496ffa1079fec3c153348725` | 传播已审阅的上游文档绑定字节 |
