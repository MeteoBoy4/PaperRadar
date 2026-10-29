# 用 Docling 作为唯一通用正文解析器

状态：决策记录（原文未单列接受状态）；日期：2026-10-10；依据：[基线裁决原文](https://github.com/MeteoBoy4/PaperRadar/blob/91e5d02e199f1921ca8afd2b7bdb8f257e6264f3/docs/adr/0010-use-docling-as-the-only-body-parser.md)；补充／部分取代：[ADR-0025](0025-allow-local-formula-candidates-with-source-review.md)、[ADR-0036](0036-isolate-stage-b-read-experiment.md)。

2026-10-10：本文公式增强关闭与仅保存公式占位的限制已由 [ADR-0025](0025-allow-local-formula-candidates-with-source-review.md) 取代；以下保留原决策依据。

PaperRadar 第一版只使用锁定版本和模型制品的 Docling 生成供条件式复用升级与 Read Agent 共用的正文提取物，不保留 PyMuPDF 或 PyMuPDF4LLM 运行时兜底。正文链关闭 OCR、公式增强、远程插件和图片增强并串行处理；扫描稿留待第二版，GROBID 仍只负责高风险参考文献缺口。原 PDF 之外保存解析清单、DoclingDocument、规范阅读文本和 evidence map；availability、methods/data 摘录也从同一制品定位，不能为 Screening 建第二套解析器。公式只保存定位占位符，未经人工复核的精确数值和科学符号不得成为关键证据。

单一正文制品契约减少了两套章节、页码和坐标语义造成的分叉，也使项目保持 MIT 授权；代价是条件升级会增加 PDF 取得和解析量。代表样本在 CPU 上约耗时 18–51 秒、峰值内存约 2.5–4.6 GB，因此正式校准前必须用四刊 fixture 同时验证正文与摘录定位。无文本层或质量门槛失败对当前指纹是永久失败，超时或资源耗尽最多自动尝试两次；任何关键 fixture 不通过时，既不能调用 Read，也不能把该正文用于复用升级。

2026-10-28：按 #111，四刊代表性覆盖未完成时仅允许 [ADR-0036](0036-isolate-stage-b-read-experiment.md) 的 B 固定 JGR 实验根窄例外；样本自身质量失败仍禁止 Read，正常消费与 reuse 的通用门槛不变，旧实验结果不复用、不提升。
