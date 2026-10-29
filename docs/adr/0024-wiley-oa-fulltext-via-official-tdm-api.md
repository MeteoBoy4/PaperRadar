# Wiley OA 全文获取采用官方 TDM API

状态：决策记录（原文未单列接受状态）；日期：2026-10-25；依据：[基线裁决原文](https://github.com/MeteoBoy4/PaperRadar/blob/91e5d02e199f1921ca8afd2b7bdb8f257e6264f3/docs/adr/0024-wiley-oa-fulltext-via-official-tdm-api.md)；补充／部分取代：[ADR-0032](0032-relax-paper-acquisition-without-evading-access-controls.md)。

2026-10-25：本文“用户人工引导的自有会话凭证仅属允许边界、第一版只实现 TDM 通道”与“机构订阅仍然禁止”两项，已由 [ADR-0032](0032-relax-paper-acquisition-without-evading-access-controls.md) 的授权通道取代（本人合法持有的机构账号、登录会话或订阅权限默认关闭、显式启用、单篇按需；不得使用他人凭证、不得批量下载或分发受限内容的禁止条款不变）。token 凭证管理、`403` 探测分类与“不绕过访问控制、`403` 不解释为非开放获取、人工 PDF 队列”原则本决议继续适用。

PaperRadar 第一版的 Wiley 两刊（QJRMS 与 JGR-A，含 AGU `10.1029` 前缀）开放全文经出版方官方 Text and Data Mining API 取得：用户在 Wiley Online Library 账户接受点击式 TDM 许可换取 token，程序带 token 请求官方端点取得出版级 PDF；TDM 只提供 PDF，无 XML 全文。token 是用户自有的账户级 API 凭证：值存文件系统凭证区（0600），SQLite 只存状态事实；用固定已知 OA DOI 探测区分 token 失效与单篇无权限，凭证级失效记为全文受阻并提示重新配置，不逐篇进入人工 PDF 队列；取件遵守官方限速（3 篇/秒、60 次/10 分钟）。本决议删除并取代 ADR 0014 的"无需登录"边界；自动求解验证码、站点反爬绕过、付费墙内容与机构订阅或他人凭证仍然禁止，"不绕过访问控制、`403` 不解释为非开放获取、人工 PDF 队列"原则保持。用户人工引导的自有会话凭证同属允许边界，第一版只实现 TDM 通道。
