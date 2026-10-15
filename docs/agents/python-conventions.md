# Python 编码约定

- 确定性逻辑与 I/O 分离。
- Network、Publisher、LLM、Docling 和 GROBID 的访问放在可替换接口之后，测试时注入 fixture / mock。
- 部分成功会破坏业务语义的操作放在同一事务中，保证原子性。
- 用明确的领域类型和受控 enum / reason 表达状态与原因。
- 新依赖只在能明显简化当前需求时引入，并同步提交 `uv.lock`。
