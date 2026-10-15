# V1 范围

## 失败成本顺序

权衡产品行为时按此排序（ADR-0021）：

`attention_overload > missed_relevant > wasted_full_read > review_backlog`

## V2 能力

以下能力属于 V2，只在任务明确要求时实现：

- Web、桌面或移动端 UI。
- OCR 或多模态文档理解。
- 模型或 Provider 自动 fallback（ADR-0004）。
- 基于引用量的排序或综合 Rank（ADR-0013）。
- Embedding、向量检索或主动关键词搜索。
- 超过一层的递归参考文献扩展。
- PostgreSQL、远程 API、多用户或权限系统。

