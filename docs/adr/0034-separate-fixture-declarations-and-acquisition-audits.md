# 分开保管 fixture 声明、取得事实和论文事实

依据 #100，版本化声明唯一目录为 `fixtures/a10/`，git 保管声明来源；显式 register 将原字节和解释只追加冻结到 SQLite，数据库保管已登记历史与本机取得事实，查询和恢复不依赖原文件。文件声明键与版本标识原字节，逻辑样本用（用途、期刊、显式 key）定位；初次登记产生当前项，后续只有显式替换关系才能推进，时间、版本排序和文件位置均不参与选择。实际来源只进入既有 ArtifactStore，声明不能自报假哈希冒充取得证据。

审计和论文事实分离：取得不调用 PaperFacts.submit，不创建生产 Feed、Paper、Screening 或校准成员。只保留有效 Feed 或身份已核验且贡献身份/字段的响应；身份已核验但无摘要的响应也保留，其余失败/挑战页仅保留结构化事实（ADR-0009）。doiRA 是固定 DOI 机构路由而不是新提供方；Crossref/DataCite 各走适用机构，其他 RA 为 agency_unsupported，查询失败为 agency_unknown。代价是失败响应无法逐字重解析，但可安全回放执行事实。

获取能力仍受 ADR-0032 控制；A10 仅交付 http，browser_render/official_api/repository 只有枚举和接口，未注册执行器以 channel_not_installed 结算，凭据类别为空。以后运行时须新策略补跑，不能改写旧审计。通道和策略参与请求身份及分母，不跨策略合并覆盖率。
