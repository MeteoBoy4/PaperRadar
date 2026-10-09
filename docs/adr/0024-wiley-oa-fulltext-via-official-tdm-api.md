# Wiley OA 全文获取采用官方 TDM API

PaperRadar 第一版的 Wiley 两刊（QJRMS 与 JGR-A，含 AGU `10.1029` 前缀）开放全文经出版方官方 Text and Data Mining API 取得：用户在 Wiley Online Library 账户接受点击式 TDM 许可换取 token，程序带 token 请求官方端点取得出版级 PDF；TDM 只提供 PDF，无 XML 全文。token 是用户自有的账户级 API 凭证：值存文件系统凭证区（0600），SQLite 只存状态事实；用固定已知 OA DOI 探测区分 token 失效与单篇无权限，凭证级失效记为全文受阻并提示重新配置，不逐篇进入人工 PDF 队列；取件遵守官方限速（3 篇/秒、60 次/10 分钟）。本决议删除并取代 ADR 0014 的"无需登录"边界；自动求解验证码、站点反爬绕过、付费墙内容与机构订阅或他人凭证仍然禁止，"不绕过访问控制、`403` 不解释为非开放获取、人工 PDF 队列"原则保持。用户人工引导的自有会话凭证同属允许边界，第一版只实现 TDM 通道。
