# Python 编码约定

- 确定性逻辑与 I/O 分离。
- Network、Publisher、LLM、Docling 和 GROBID 的访问放在可替换接口之后，测试时注入 fixture / mock。
- Pi 供给的 HTTP 使用 httpx：显式超时、流式大小上限、禁用自动重定向并逐跳检查固定白名单；代理须显式传入，关闭环境继承。
- 部分成功会破坏业务语义的操作放在同一事务中，保证原子性。
- 用明确的领域类型和受控 enum / reason 表达状态与原因。
- 新依赖只在能明显简化当前需求时引入，并同步提交 `uv.lock`。
