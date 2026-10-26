# A10 scope 审阅记录

旧组漂移与 `4ec450f` 原字节逐项比对；下表仅重绑有明确行为变化的文件或拓扑传播。既有required、直接前置、依赖清单和测试分母均保留；A2-01仍非必需。A1四契约/全产品五份Frozen/lockfile/A6规则与Stage fingerprint不变。

全部旧组真实临时迁移期待由a704调整为唯一a1001，A3备份revision同调；历史迁移文件、旧JSON与历史格式解释不改。A10固定fixture_audit全包、真实migration、实际复用A6规则及公开CLI/SQLite/ArtifactStore/backup的导入闭包；静态导入范围宽于能力直接前置，不改变运行DAG。

旧测试仅head期待更新、schema模块显式注册、A8/A9正常输出份数更新；函数和参数化未变。A8 entry仍9例、A9 entry仍10例，A9发布失败前已完成九组的原时序不变；A10中断则保留十组。合成receipt只做协议负例，真实全部执行另由本次receipt证明。

完整旧/新hash如下；本文件不记录自身hash、A10 scope字节或未知最终run_id以免形成自哈希环。最终run_id与原始14份JSON由验收输出及工作树外运行记录保存；任何最终树变化都须新run。

| Scope | 路径 | 旧 SHA-256 | 新 SHA-256 | 必要原因 |
| --- | --- | --- | --- | --- |
| scripts/a2_scope.py | tests/test_config_service.py | ccd7cea316e16348e14bcea400d392568954d5377b5f6a8a5bc36a0c4cad2d98 | 709e6e64338a15ad99844144f4adb26592601f1300b638b415e8ffc31e09b5f1 | #101 schema对比先显式注册全部真实table模块以消除collection顺序依赖；分母不变。 |
| scripts/a2_scope.py | tests/test_a2_acceptance.py | 862d629d962f7b04037baba01ccddf17c75a96f71420e1fe9fbd572844abf1bb | def2184ac25d517658f3fa040991b315d0f8d888eeb8d26ace93546df2ca1883 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a2_scope.py | src/paper_radar/cli.py | b5bf7b9f643fc84dcccf1227af608d8602deec167f5aeedff7efdd02d536cb66 | 47eff2ad8955e2e42f2f76033031334e61d1be4f6535f9d103c44e755887aa3a | #101/#103 仅新增 fixture/audit 子命令公开入口。 |
| scripts/a2_scope.py | scripts/check-offline | 7da9535adf65a7ae809242d556d40412f65851602d6a4cde84426038ec364382 | 41a205087015281e5a8a921f20815f0828ef8457c57445d40f95be2bdb6d99d8 | #108 中文help同步十二主要输出/十四JSON；六项执行计划不变。 |
| scripts/a2_full_scope.py | tests/test_a2_acceptance.py | 862d629d962f7b04037baba01ccddf17c75a96f71420e1fe9fbd572844abf1bb | def2184ac25d517658f3fa040991b315d0f8d888eeb8d26ace93546df2ca1883 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a2_full_scope.py | tests/test_a2_full_acceptance.py | dddced8dc74d42e6655d8b17fac8312cf07b022264f1b6b06e979822b8600bff | ff70beead1d601759c8bae3c826b71a470022b9efdce09a92491d39a8806c297 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a2_full_scope.py | tests/test_config_service.py | ccd7cea316e16348e14bcea400d392568954d5377b5f6a8a5bc36a0c4cad2d98 | 709e6e64338a15ad99844144f4adb26592601f1300b638b415e8ffc31e09b5f1 | #101 schema对比先显式注册全部真实table模块以消除collection顺序依赖；分母不变。 |
| scripts/a2_full_scope.py | scripts/a2_full_acceptance.py | b90a29fb1b645c47960f7f1ca9db816495225a68d1b6ac60a6e43096f0d40840 | ea761e76debed029efb9b37022c2d5dac78fccd32d31184015696618c5a9a204 | #108 末尾追加required A10，直接前置A1/完整A2/A3/A6；旧登记不变。 |
| scripts/a2_full_scope.py | scripts/a2_test_receipt.py | 795596859f24d1241c589afd3d28902cbc148724b0aaa25fdbfafeaec4bd1593 | 38b0fcea6a0028c3652dfc272829f5ac76c201430fcd2d4d187c629db85032e5 | #108 真实receipt登记A10全部模块；没有改变既有模块计数语义。 |
| scripts/a2_full_scope.py | scripts/check-offline | 7da9535adf65a7ae809242d556d40412f65851602d6a4cde84426038ec364382 | 41a205087015281e5a8a921f20815f0828ef8457c57445d40f95be2bdb6d99d8 | #108 中文help同步十二主要输出/十四JSON；六项执行计划不变。 |
| scripts/a2_full_scope.py | src/paper_radar/cli.py | b5bf7b9f643fc84dcccf1227af608d8602deec167f5aeedff7efdd02d536cb66 | 47eff2ad8955e2e42f2f76033031334e61d1be4f6535f9d103c44e755887aa3a | #101/#103 仅新增 fixture/audit 子命令公开入口。 |
| scripts/a3_scope.py | tests/test_storage_migrations.py | 4bcf7f7c699910e99f72e1b2c383ff3af80891c3097d0aa37fa8a791e5cc033d | d2c5f415b85e354f5c37f22db8045ac6d8c33ffa2eb4e5d1251c6ca34ca1a663 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a3_scope.py | tests/test_backup_failures.py | 1a6653f63fbf6b7f0af2603e8186e684f9df7d9187485731da407e44a4870497 | f90857b9aac84fd0c3706f1f8abcb0aba579f78418c368c15ddc62a43248d08c | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a3_scope.py | src/paper_radar/backup/manifest.py | db4d7286fa1c9431ceae5bb8ad9491103bb1a10c3969b4fdc7567b5d30aff4f4 | a56dfe8e3964a31479d342d164fbba1b02ee6a595aec651786d78be3f9d2c35f | #101 当前备份数据库 revision 为真实 a1001；格式1不变。 |
| scripts/a3_scope.py | src/paper_radar/backup/service.py | e6fa39228f4acb1b86c7ebc33f0e2ce4bd962bd9c749145b7faa6ea888413857 | 077f7c1690885f80f06bb88fb134bd486017ab2a1fd32f977cdf82a179be547c | #101 verify_contents 新增 FixtureAudit.validate_all 闭包；Paper/Task 原核验保留。 |
| scripts/a3_scope.py | tests/test_restore_service.py | 83843f03da5b74cbfc9114dc60d7f17f3a3d236d056e8690dd00bf81953b42d2 | 39986dbf303176963bf3ddcc79589dc00536bfc4fcea17b5e54f33b9d8d5bc50 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a3_scope.py | tests/test_a3_acceptance.py | dcb106988f651094e454f7f0cdbf2f7fac6fab42ff57e1aa204af6957bb05050 | 6be5a928c2afcffcac15f49abeac68d638909a798e976f5cd943273aae6e1b4b | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a3_scope.py | scripts/a2_full_acceptance.py | b90a29fb1b645c47960f7f1ca9db816495225a68d1b6ac60a6e43096f0d40840 | ea761e76debed029efb9b37022c2d5dac78fccd32d31184015696618c5a9a204 | #108 末尾追加required A10，直接前置A1/完整A2/A3/A6；旧登记不变。 |
| scripts/a3_scope.py | scripts/a2_test_receipt.py | 795596859f24d1241c589afd3d28902cbc148724b0aaa25fdbfafeaec4bd1593 | 38b0fcea6a0028c3652dfc272829f5ac76c201430fcd2d4d187c629db85032e5 | #108 真实receipt登记A10全部模块；没有改变既有模块计数语义。 |
| scripts/a3_scope.py | scripts/a2_full_scope.py | 8022620adb20868eb7d006285baafb04991ce8e40e282d3de85b4b38b96b28e7 | 44383d7a39da7e1601a0a0f876c212a68e04b1e5df936bbaf9f573d9cd597f81 | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a3_scope.py | scripts/check-offline | 7da9535adf65a7ae809242d556d40412f65851602d6a4cde84426038ec364382 | 41a205087015281e5a8a921f20815f0828ef8457c57445d40f95be2bdb6d99d8 | #108 中文help同步十二主要输出/十四JSON；六项执行计划不变。 |
| scripts/a3_scope.py | src/paper_radar/cli.py | b5bf7b9f643fc84dcccf1227af608d8602deec167f5aeedff7efdd02d536cb66 | 47eff2ad8955e2e42f2f76033031334e61d1be4f6535f9d103c44e755887aa3a | #101/#103 仅新增 fixture/audit 子命令公开入口。 |
| scripts/a4_scope.py | tests/test_pi_supply_activation_history.py | 6ad090a594e4e2731b0834e828a01de11307b2820f6dbea389ff4433f2c119ef | abc8ad4cd52b5faa9359563ce73885030d7a59fa5811f343babd2adc28357fef | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a4_scope.py | tests/test_pi_supply_cleanup_execute_history.py | aeeff46f8974c92bc8dbecdee54163cb71098e4d7e0072202f9b6de44cd0e6c3 | 77670fa74794a7addcbcd1a18c14f0502e9a753d9735c889add3e3b935845e3f | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a4_scope.py | tests/test_pi_supply_cleanup_history.py | f097096d2d134cc7008a47f8364559ea3c7cf772b7eb671f7533b8959b713802 | 801cdb17d25b5fcc1eb33a9df2e4ea5d6236f8be274f772612ac6e354431e8f5 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a4_scope.py | tests/test_pi_supply_history.py | 26fad8c1462b2f727e2767e8e27515de7e2b799d9f5ad15000df71d5344c2a75 | e7cbcd1f4c01edd98746fab6a4dcafda293633a1e168548b8ddffa6d18225699 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a4_scope.py | tests/test_pi_supply_rebuild_history.py | f4958af52035ff234e5abc802c7f9342d49dedec57695bf9b9626b1822509d41 | 636d4c4a6905ea7e18673af5c1e7a5021ca693bbff01b6266a9c139e935b5579 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a4_scope.py | tests/test_a4_acceptance.py | 12d62354b1e98bfe0ab1e3332a2a02c7322b9f6cc08fdb4e3d9e8e11cdf36a75 | 63600313ccbc1c5b46f62db9bc17d8d1bd8af6e27d6ea6a0e96de7780a20aa1f | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a4_scope.py | src/paper_radar/backup/manifest.py | db4d7286fa1c9431ceae5bb8ad9491103bb1a10c3969b4fdc7567b5d30aff4f4 | a56dfe8e3964a31479d342d164fbba1b02ee6a595aec651786d78be3f9d2c35f | #101 当前备份数据库 revision 为真实 a1001；格式1不变。 |
| scripts/a4_scope.py | src/paper_radar/cli.py | b5bf7b9f643fc84dcccf1227af608d8602deec167f5aeedff7efdd02d536cb66 | 47eff2ad8955e2e42f2f76033031334e61d1be4f6535f9d103c44e755887aa3a | #101/#103 仅新增 fixture/audit 子命令公开入口。 |
| scripts/a4_scope.py | scripts/a3_scope.py | 3738ed6011aacbf1ce22307dc456c4168caf8a5bef57c07536a014b1451354f3 | 8efe0301841c50ae5e0708d16d4ebba613eee56e988636b66e764e72e5058cb9 | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a4_scope.py | scripts/a2_full_scope.py | 8022620adb20868eb7d006285baafb04991ce8e40e282d3de85b4b38b96b28e7 | 44383d7a39da7e1601a0a0f876c212a68e04b1e5df936bbaf9f573d9cd597f81 | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a4_scope.py | scripts/a2_full_acceptance.py | b90a29fb1b645c47960f7f1ca9db816495225a68d1b6ac60a6e43096f0d40840 | ea761e76debed029efb9b37022c2d5dac78fccd32d31184015696618c5a9a204 | #108 末尾追加required A10，直接前置A1/完整A2/A3/A6；旧登记不变。 |
| scripts/a4_scope.py | scripts/a2_test_receipt.py | 795596859f24d1241c589afd3d28902cbc148724b0aaa25fdbfafeaec4bd1593 | 38b0fcea6a0028c3652dfc272829f5ac76c201430fcd2d4d187c629db85032e5 | #108 真实receipt登记A10全部模块；没有改变既有模块计数语义。 |
| scripts/a4_scope.py | scripts/check-offline | 7da9535adf65a7ae809242d556d40412f65851602d6a4cde84426038ec364382 | 41a205087015281e5a8a921f20815f0828ef8457c57445d40f95be2bdb6d99d8 | #108 中文help同步十二主要输出/十四JSON；六项执行计划不变。 |
| scripts/a5_scope.py | tests/test_a5_acceptance.py | 67e7bb7532bf7495f17e26bc13c5f77c35402fd299c0d1d07ca2f9d27214df5a | 9d3fcede88c46f9c61081a1afe230b72f7d64f6c5d816ff64fb71c33c828c2bf | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a5_scope.py | scripts/a2_full_scope.py | 8022620adb20868eb7d006285baafb04991ce8e40e282d3de85b4b38b96b28e7 | 44383d7a39da7e1601a0a0f876c212a68e04b1e5df936bbaf9f573d9cd597f81 | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a5_scope.py | scripts/a3_scope.py | 3738ed6011aacbf1ce22307dc456c4168caf8a5bef57c07536a014b1451354f3 | 8efe0301841c50ae5e0708d16d4ebba613eee56e988636b66e764e72e5058cb9 | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a5_scope.py | scripts/a4_scope.py | 51f1d264fa5e092d0745cd50155072d67e6a4c2d723f05ea40994f585d927d37 | f88eb0fb9a301a3ed13788600ed740f840645b25c0844f8e74d52f3b537011dd | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a5_scope.py | scripts/a2_full_acceptance.py | b90a29fb1b645c47960f7f1ca9db816495225a68d1b6ac60a6e43096f0d40840 | ea761e76debed029efb9b37022c2d5dac78fccd32d31184015696618c5a9a204 | #108 末尾追加required A10，直接前置A1/完整A2/A3/A6；旧登记不变。 |
| scripts/a5_scope.py | scripts/a2_test_receipt.py | 795596859f24d1241c589afd3d28902cbc148724b0aaa25fdbfafeaec4bd1593 | 38b0fcea6a0028c3652dfc272829f5ac76c201430fcd2d4d187c629db85032e5 | #108 真实receipt登记A10全部模块；没有改变既有模块计数语义。 |
| scripts/a5_scope.py | scripts/check-offline | 7da9535adf65a7ae809242d556d40412f65851602d6a4cde84426038ec364382 | 41a205087015281e5a8a921f20815f0828ef8457c57445d40f95be2bdb6d99d8 | #108 中文help同步十二主要输出/十四JSON；六项执行计划不变。 |
| scripts/a6_scope.py | tests/test_feed_migrations.py | 5a6f740951d102ccc8c6d79aabf22044cfa8e37437273f2b1bcbf29d8b56e5d1 | 37b673960e97aaa365672371815e4ca0e4c1407839c437d4151072e529e3458b | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a6_scope.py | tests/test_paper_migrations.py | 09161e405c7cdfa4d758904421611d9ff470e224a3762b3287a6c15e71a76ad1 | 0f23e08ee0198fe5dbc280788763438d26822a2c3c456e4ffd6cacdb39122851 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a6_scope.py | tests/test_source_backup.py | 523a6657daf69ef15f6dd365e0b65084f2e87de3ff5def2a2fe86c91dc514c5b | a8ecf00dd9895299460b5ae488ca8928038aa5efdecc873058a784f1feaa572a | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a6_scope.py | tests/test_source_migrations.py | 58c7ff8e3e51c0bcc1dd4f5dd34e32933bed4302be23ee92e94966c15e3a08c5 | c21ed45f16753f17fe02eeecc6d13edb7007fd552cd9c34cf213a4351ae0108e | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a6_scope.py | tests/test_version_relation_migrations.py | 2fdf28a1fe73af337b0c00e72ddc4e6701d88eddb120f96c19d160d05a5b7628 | 8664a7bd575cba49e380b03e6d24dc22dc1e5837b46f82b2f3fd328227f37129 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a6_scope.py | tests/test_a6_acceptance.py | ebf39c0d52023ece04fce366ef72dd1ecc6d29caba43ed1f410781ad5084d767 | 486561e357eee50198b0fdb2b185f9dee929e81bb9ff2da5a3eed489d42f2cb1 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a6_scope.py | tests/test_a6_integrity.py | d104ede782057f79e62407cdb97444cfadf0a9d603b354d975ad33293643f582 | 59ebe49aa65721d1b1afb095d19b683d4a7aa8e38645c068e21b53a394481cd0 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a6_scope.py | scripts/a2_full_acceptance.py | b90a29fb1b645c47960f7f1ca9db816495225a68d1b6ac60a6e43096f0d40840 | ea761e76debed029efb9b37022c2d5dac78fccd32d31184015696618c5a9a204 | #108 末尾追加required A10，直接前置A1/完整A2/A3/A6；旧登记不变。 |
| scripts/a6_scope.py | scripts/a2_full_scope.py | 8022620adb20868eb7d006285baafb04991ce8e40e282d3de85b4b38b96b28e7 | 44383d7a39da7e1601a0a0f876c212a68e04b1e5df936bbaf9f573d9cd597f81 | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a6_scope.py | scripts/a2_test_receipt.py | 795596859f24d1241c589afd3d28902cbc148724b0aaa25fdbfafeaec4bd1593 | 38b0fcea6a0028c3652dfc272829f5ac76c201430fcd2d4d187c629db85032e5 | #108 真实receipt登记A10全部模块；没有改变既有模块计数语义。 |
| scripts/a6_scope.py | scripts/a3_scope.py | 3738ed6011aacbf1ce22307dc456c4168caf8a5bef57c07536a014b1451354f3 | 8efe0301841c50ae5e0708d16d4ebba613eee56e988636b66e764e72e5058cb9 | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a6_scope.py | scripts/a5_scope.py | ab247f370816520d8147fcf16c5d93330efb24254e580c55f87ab12af750bc4d | a970107ec870a31d88d96642e9fb2cfb5e65a7911811312302f3c04bad1cf2cf | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a6_scope.py | scripts/check-offline | 7da9535adf65a7ae809242d556d40412f65851602d6a4cde84426038ec364382 | 41a205087015281e5a8a921f20815f0828ef8457c57445d40f95be2bdb6d99d8 | #108 中文help同步十二主要输出/十四JSON；六项执行计划不变。 |
| scripts/a6_scope.py | scripts/verification_status.py | 4db5d49e411b45777a2b32a2ac1d739b746274c1cdf7115e62c50c96640630a7 | 081a13f82706ebc16aee21138c40bcf6620ad8daeb8efa6338a1512f07edd1c5 | #108 增加a10格式1历史支持；已有格式表均保留。 |
| scripts/a6_scope.py | src/paper_radar/backup/manifest.py | db4d7286fa1c9431ceae5bb8ad9491103bb1a10c3969b4fdc7567b5d30aff4f4 | a56dfe8e3964a31479d342d164fbba1b02ee6a595aec651786d78be3f9d2c35f | #101 当前备份数据库 revision 为真实 a1001；格式1不变。 |
| scripts/a6_scope.py | src/paper_radar/backup/service.py | e6fa39228f4acb1b86c7ebc33f0e2ce4bd962bd9c749145b7faa6ea888413857 | 077f7c1690885f80f06bb88fb134bd486017ab2a1fd32f977cdf82a179be547c | #101 verify_contents 新增 FixtureAudit.validate_all 闭包；Paper/Task 原核验保留。 |
| scripts/a6_scope.py | src/paper_radar/cli.py | b5bf7b9f643fc84dcccf1227af608d8602deec167f5aeedff7efdd02d536cb66 | 47eff2ad8955e2e42f2f76033031334e61d1be4f6535f9d103c44e755887aa3a | #101/#103 仅新增 fixture/audit 子命令公开入口。 |
| scripts/a7_scope.py | tests/test_a7_registration_migrations.py | df4cbb45f75aee872a45ee9cb7240ddb88767857c22db633b36863e9763621ae | 796c204f65d5306b9afdf7275b973a6ac6758074a4bcac394f954c65bd78ddb5 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a7_scope.py | tests/test_a7_attempt_migrations.py | 18dbc3fe4fb44ee1b10226a64df1a08d9d14ccdbd4c42fcdf2e141110d8ed538 | b33a1bba6563a33d0e186f54dee7f3d674bf6f10aafcf5fd9c0f0e3e1f3cb738 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a7_scope.py | tests/test_a7_success_migrations.py | 0c629257aa82d6056cb3724e0dacae75e32d5e55b23b9e319fbed51fdc603c1b | 7f593e34e3e2d7d864b87f0d053c7d7cf0ad9f5a9fc4ba63d26ee0a8789ccb5a | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a7_scope.py | tests/test_a7_retry_migrations.py | da625889ea25e06e439aad8c09a58bcdb5ba2caf35d0120ff8f8bbb5973afdf3 | f21aa2e5c3f0912364655a4776f169f3299e5d47ae8de708192f497c631da5f3 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a7_scope.py | tests/test_a7_acceptance.py | 35e5f5f312e1079bc6663f928300a1f931f3c9fb1a777c7c49f6608b38fb597b | 3611faf8230e99155dbdc3d4e756f4c742349c9e3f1c86ff0d022396ce3ba5ec | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a7_scope.py | tests/test_a7_integrity.py | 728a75c626a4edf5e71a57017a1d1d211231a63b8be424d40fe03b1445c6d603 | b321307db00ec244566f95e67f22db89c08b610f3b7b2594a7427cbe9a3a947f | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a7_scope.py | scripts/a2_full_acceptance.py | b90a29fb1b645c47960f7f1ca9db816495225a68d1b6ac60a6e43096f0d40840 | ea761e76debed029efb9b37022c2d5dac78fccd32d31184015696618c5a9a204 | #108 末尾追加required A10，直接前置A1/完整A2/A3/A6；旧登记不变。 |
| scripts/a7_scope.py | scripts/a2_full_scope.py | 8022620adb20868eb7d006285baafb04991ce8e40e282d3de85b4b38b96b28e7 | 44383d7a39da7e1601a0a0f876c212a68e04b1e5df936bbaf9f573d9cd597f81 | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a7_scope.py | scripts/a2_test_receipt.py | 795596859f24d1241c589afd3d28902cbc148724b0aaa25fdbfafeaec4bd1593 | 38b0fcea6a0028c3652dfc272829f5ac76c201430fcd2d4d187c629db85032e5 | #108 真实receipt登记A10全部模块；没有改变既有模块计数语义。 |
| scripts/a7_scope.py | scripts/a3_scope.py | 3738ed6011aacbf1ce22307dc456c4168caf8a5bef57c07536a014b1451354f3 | 8efe0301841c50ae5e0708d16d4ebba613eee56e988636b66e764e72e5058cb9 | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a7_scope.py | scripts/a5_scope.py | ab247f370816520d8147fcf16c5d93330efb24254e580c55f87ab12af750bc4d | a970107ec870a31d88d96642e9fb2cfb5e65a7911811312302f3c04bad1cf2cf | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a7_scope.py | scripts/a6_scope.py | 36363c351ff407b1fe746c4df37b599395e8c87341367d0f63c7c9307222a5cf | 48a18ddac4f5e7fffcf093f3c88da4e35995423aae1e65d50766ab1a56cc363e | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a7_scope.py | scripts/check-offline | 7da9535adf65a7ae809242d556d40412f65851602d6a4cde84426038ec364382 | 41a205087015281e5a8a921f20815f0828ef8457c57445d40f95be2bdb6d99d8 | #108 中文help同步十二主要输出/十四JSON；六项执行计划不变。 |
| scripts/a7_scope.py | scripts/verification_status.py | 4db5d49e411b45777a2b32a2ac1d739b746274c1cdf7115e62c50c96640630a7 | 081a13f82706ebc16aee21138c40bcf6620ad8daeb8efa6338a1512f07edd1c5 | #108 增加a10格式1历史支持；已有格式表均保留。 |
| scripts/a7_scope.py | src/paper_radar/backup/manifest.py | db4d7286fa1c9431ceae5bb8ad9491103bb1a10c3969b4fdc7567b5d30aff4f4 | a56dfe8e3964a31479d342d164fbba1b02ee6a595aec651786d78be3f9d2c35f | #101 当前备份数据库 revision 为真实 a1001；格式1不变。 |
| scripts/a7_scope.py | src/paper_radar/backup/service.py | e6fa39228f4acb1b86c7ebc33f0e2ce4bd962bd9c749145b7faa6ea888413857 | 077f7c1690885f80f06bb88fb134bd486017ab2a1fd32f977cdf82a179be547c | #101 verify_contents 新增 FixtureAudit.validate_all 闭包；Paper/Task 原核验保留。 |
| scripts/a8_scope.py | tests/test_a8_acceptance.py | cded954f82704e3cf982292c6ec5bf0138ad84d508f6146a6f420d7d16a18cab | 14ef2c0f21320393a95df27b722e3ae9646dce8380fddd489ff5d3e8ab567d0f | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a8_scope.py | tests/test_a8_integrity.py | 724441b4e5198c00519ee6f1a18c12a8f76d209a7c87b92a46fda7a52ff730cc | bc4241a064a463e9819baa14e9d81a7e8931ba294c675c21c6b62e9c57bf71e9 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a8_scope.py | tests/test_a8_entry.py | 673c06d68d92d90b30439dc4ac8bd29d266d6a7a3d84af3c786ced4aa585ecf2 | 148090d5270b8a1989ee4681ff52f6a5e1d5a38fe0faf8414c0a769c4fa5d604 | #108 正常JSON数13→14；原发布失败时序和原参数化保持。 |
| scripts/a8_scope.py | tests/a8_acceptance_support.py | 2a4516dc9d4f462d4f2a7f6c3106b5b0631e605f9c656e4c91e0fe96b12bd057 | 2bc2b90eaa623493b9b4b2ac449d72e8b6e82e0790893146103abada5e2e64fe | #108 合成成功receipt补A10模块，仍仅用于协议测试、不作真实执行证据。 |
| scripts/a8_scope.py | scripts/a2_full_acceptance.py | b90a29fb1b645c47960f7f1ca9db816495225a68d1b6ac60a6e43096f0d40840 | ea761e76debed029efb9b37022c2d5dac78fccd32d31184015696618c5a9a204 | #108 末尾追加required A10，直接前置A1/完整A2/A3/A6；旧登记不变。 |
| scripts/a8_scope.py | scripts/a2_test_receipt.py | 795596859f24d1241c589afd3d28902cbc148724b0aaa25fdbfafeaec4bd1593 | 38b0fcea6a0028c3652dfc272829f5ac76c201430fcd2d4d187c629db85032e5 | #108 真实receipt登记A10全部模块；没有改变既有模块计数语义。 |
| scripts/a8_scope.py | scripts/a2_full_scope.py | 8022620adb20868eb7d006285baafb04991ce8e40e282d3de85b4b38b96b28e7 | 44383d7a39da7e1601a0a0f876c212a68e04b1e5df936bbaf9f573d9cd597f81 | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a8_scope.py | scripts/a3_scope.py | 3738ed6011aacbf1ce22307dc456c4168caf8a5bef57c07536a014b1451354f3 | 8efe0301841c50ae5e0708d16d4ebba613eee56e988636b66e764e72e5058cb9 | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a8_scope.py | scripts/a5_scope.py | ab247f370816520d8147fcf16c5d93330efb24254e580c55f87ab12af750bc4d | a970107ec870a31d88d96642e9fb2cfb5e65a7911811312302f3c04bad1cf2cf | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a8_scope.py | scripts/a6_scope.py | 36363c351ff407b1fe746c4df37b599395e8c87341367d0f63c7c9307222a5cf | 48a18ddac4f5e7fffcf093f3c88da4e35995423aae1e65d50766ab1a56cc363e | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a8_scope.py | scripts/a7_scope.py | c8044cbca5252649366400a9c253c5719781df4c2304e963ebfc7b45857c0d79 | 9f1d21c34b3e8c3f211b9917160cf5c8de9c5708b7147a4f3a1f978b22d6b993 | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a8_scope.py | scripts/check-offline | 7da9535adf65a7ae809242d556d40412f65851602d6a4cde84426038ec364382 | 41a205087015281e5a8a921f20815f0828ef8457c57445d40f95be2bdb6d99d8 | #108 中文help同步十二主要输出/十四JSON；六项执行计划不变。 |
| scripts/a8_scope.py | scripts/verification_status.py | 4db5d49e411b45777a2b32a2ac1d739b746274c1cdf7115e62c50c96640630a7 | 081a13f82706ebc16aee21138c40bcf6620ad8daeb8efa6338a1512f07edd1c5 | #108 增加a10格式1历史支持；已有格式表均保留。 |
| scripts/a8_scope.py | docs/contracts/verification-status.md | ccd6c5f223cee2c7eb4d3f5d65fcc2c056293f6e50210942e7020273dcac1739 | 2678cca8a20454cdf01b0758bea5a904140a0ab065e573f14e9e527863d3705d | #101–#108 文档加入声明/HTTP/恢复/回执及诚实未验边界；保持历史格式解释。 |
| scripts/a8_scope.py | docs/verification/offline-evidence.md | 145f4881829af1f140b3d63dfa7bd1cdccb80b07a12fbf92f7580ed54891e612 | 7e3aec1a3b9742792df7e29e0ba151f29775c5f70ca456f1db48ac30e9946813 | #101–#108 文档加入声明/HTTP/恢复/回执及诚实未验边界；保持历史格式解释。 |
| scripts/a8_scope.py | README.md | 72c8dc720dba8fa7a8ba76101461ab785b55c1988a3efa3e0670425bc70440a9 | 9c21c0726ee8b270bebcfbd4c0636656354416089059299f4ea214e15d397173 | #101–#108 文档加入声明/HTTP/恢复/回执及诚实未验边界；保持历史格式解释。 |
| scripts/a9_scope.py | tests/test_a9_acceptance.py | 1483065b3e865f785cd742305630a3b99275418f6f25795652059284a745beb8 | 2093600321efca8b9eb4a0088fbac299f88362a0f0c9864dbdf1532730860c71 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a9_scope.py | tests/test_a9_integrity.py | 3c2d2ba27a9cb5def957bb363b359402d9e08d4ceb4e10ab41478c619391b723 | 061f76e57ef097e33b5e4318172ea75cb76f2faeaf2d639f7a2115abb4412fda | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a9_scope.py | tests/test_a9_entry.py | 04847c7e69e85248b45721f178723a3d8c660cef2e1edd5bd44ddf915bf08fe3 | 87d9cde4deef8d3c4fdd21c002c1502569daac2274683dd6f9c35ec2574e1f81 | #108 正常JSON数13→14；原发布失败时序和原参数化保持。 |
| scripts/a9_scope.py | src/paper_radar/cli.py | b5bf7b9f643fc84dcccf1227af608d8602deec167f5aeedff7efdd02d536cb66 | 47eff2ad8955e2e42f2f76033031334e61d1be4f6535f9d103c44e755887aa3a | #101/#103 仅新增 fixture/audit 子命令公开入口。 |
| scripts/a9_scope.py | src/paper_radar/backup/service.py | e6fa39228f4acb1b86c7ebc33f0e2ce4bd962bd9c749145b7faa6ea888413857 | 077f7c1690885f80f06bb88fb134bd486017ab2a1fd32f977cdf82a179be547c | #101 verify_contents 新增 FixtureAudit.validate_all 闭包；Paper/Task 原核验保留。 |
| scripts/a9_scope.py | src/paper_radar/backup/manifest.py | db4d7286fa1c9431ceae5bb8ad9491103bb1a10c3969b4fdc7567b5d30aff4f4 | a56dfe8e3964a31479d342d164fbba1b02ee6a595aec651786d78be3f9d2c35f | #101 当前备份数据库 revision 为真实 a1001；格式1不变。 |
| scripts/a9_scope.py | scripts/a2_full_scope.py | 8022620adb20868eb7d006285baafb04991ce8e40e282d3de85b4b38b96b28e7 | 44383d7a39da7e1601a0a0f876c212a68e04b1e5df936bbaf9f573d9cd597f81 | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a9_scope.py | scripts/a3_scope.py | 3738ed6011aacbf1ce22307dc456c4168caf8a5bef57c07536a014b1451354f3 | 8efe0301841c50ae5e0708d16d4ebba613eee56e988636b66e764e72e5058cb9 | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a9_scope.py | scripts/a2_full_acceptance.py | b90a29fb1b645c47960f7f1ca9db816495225a68d1b6ac60a6e43096f0d40840 | ea761e76debed029efb9b37022c2d5dac78fccd32d31184015696618c5a9a204 | #108 末尾追加required A10，直接前置A1/完整A2/A3/A6；旧登记不变。 |
| scripts/a9_scope.py | scripts/a2_test_receipt.py | 795596859f24d1241c589afd3d28902cbc148724b0aaa25fdbfafeaec4bd1593 | 38b0fcea6a0028c3652dfc272829f5ac76c201430fcd2d4d187c629db85032e5 | #108 真实receipt登记A10全部模块；没有改变既有模块计数语义。 |
| scripts/a9_scope.py | scripts/verification_status.py | 4db5d49e411b45777a2b32a2ac1d739b746274c1cdf7115e62c50c96640630a7 | 081a13f82706ebc16aee21138c40bcf6620ad8daeb8efa6338a1512f07edd1c5 | #108 增加a10格式1历史支持；已有格式表均保留。 |
| scripts/a9_scope.py | scripts/check-offline | 7da9535adf65a7ae809242d556d40412f65851602d6a4cde84426038ec364382 | 41a205087015281e5a8a921f20815f0828ef8457c57445d40f95be2bdb6d99d8 | #108 中文help同步十二主要输出/十四JSON；六项执行计划不变。 |
| scripts/a9_scope.py | tests/a9_acceptance_support.py | 3e854f52b3fdbf6d39fbbde856018cdc479fa1c495e696d0239d38456c2cdbf8 | 475e1413ca1779429e1955c7c0f23fbc96af10989e38302e282e1c83a620b3db | #108 合成成功receipt补A10模块，仍仅用于协议测试、不作真实执行证据。 |
| scripts/a9_scope.py | tests/a8_acceptance_support.py | 2a4516dc9d4f462d4f2a7f6c3106b5b0631e605f9c656e4c91e0fe96b12bd057 | 2bc2b90eaa623493b9b4b2ac449d72e8b6e82e0790893146103abada5e2e64fe | #108 合成成功receipt补A10模块，仍仅用于协议测试、不作真实执行证据。 |
| scripts/a9_scope.py | tests/test_a2_full_acceptance.py | dddced8dc74d42e6655d8b17fac8312cf07b022264f1b6b06e979822b8600bff | ff70beead1d601759c8bae3c826b71a470022b9efdce09a92491d39a8806c297 | #101 已合入测试仅将真实当前head或未来head前驱移到a1001；函数/参数化不增删。 |
| scripts/a9_scope.py | scripts/a4_scope.py | 51f1d264fa5e092d0745cd50155072d67e6a4c2d723f05ea40994f585d927d37 | f88eb0fb9a301a3ed13788600ed740f840645b25c0844f8e74d52f3b537011dd | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a9_scope.py | scripts/a5_scope.py | ab247f370816520d8147fcf16c5d93330efb24254e580c55f87ab12af750bc4d | a970107ec870a31d88d96642e9fb2cfb5e65a7911811312302f3c04bad1cf2cf | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a9_scope.py | scripts/a6_scope.py | 36363c351ff407b1fe746c4df37b599395e8c87341367d0f63c7c9307222a5cf | 48a18ddac4f5e7fffcf093f3c88da4e35995423aae1e65d50766ab1a56cc363e | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a9_scope.py | scripts/a7_scope.py | c8044cbca5252649366400a9c253c5719781df4c2304e963ebfc7b45857c0d79 | 9f1d21c34b3e8c3f211b9917160cf5c8de9c5708b7147a4f3a1f978b22d6b993 | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a9_scope.py | scripts/a8_scope.py | abf2f980b219b94afdf68690fb9c4d39040b90f5791e21b81eab4e9cc16da76f | c865344a083765e906a0eddf0907ef16e8479c732ca9df4c68be2e7a3d976152 | 按拓扑固定已经审阅的上游scope新字节；运行直接前置未扩大。 |
| scripts/a9_scope.py | README.md | 72c8dc720dba8fa7a8ba76101461ab785b55c1988a3efa3e0670425bc70440a9 | 9c21c0726ee8b270bebcfbd4c0636656354416089059299f4ea214e15d397173 | #101–#108 文档加入声明/HTTP/恢复/回执及诚实未验边界；保持历史格式解释。 |
| scripts/a9_scope.py | GLOSSARY.md | d667630bf2457b453be99dbf56f5b456843c24466ed5570c8ab312095b3b6802 | 5836a32db8fd2ba67dc4c088db62e589cc5976e82e742ae3e46a0c18c7f91c01 | #101–#108 文档加入声明/HTTP/恢复/回执及诚实未验边界；保持历史格式解释。 |
| scripts/a9_scope.py | intent/draft.md | a39e712727b6d83b6e97fc5116ac4c026b1d429ce8ed2e1fff24eb78690e816f | dfcdfb740e38e493b069867b90280f11a96c62f078cc377bef09db01fa9016bb | #101–#108 文档加入声明/HTTP/恢复/回执及诚实未验边界；保持历史格式解释。 |
| scripts/a9_scope.py | docs/contracts/verification-status.md | ccd6c5f223cee2c7eb4d3f5d65fcc2c056293f6e50210942e7020273dcac1739 | 2678cca8a20454cdf01b0758bea5a904140a0ab065e573f14e9e527863d3705d | #101–#108 文档加入声明/HTTP/恢复/回执及诚实未验边界；保持历史格式解释。 |
| scripts/a9_scope.py | docs/contracts/backup-restore.md | c8184ad1419f8d0f2840861a838b8c9ccd299e9ee7e655f758029bf5b0c5dfd1 | 90e0c2aab31996c5581eeefe720880c6a6fb7569cd22d93f9e90c09867ecb01c | #101–#108 文档加入声明/HTTP/恢复/回执及诚实未验边界；保持历史格式解释。 |
| scripts/a9_scope.py | docs/verification/offline-evidence.md | 145f4881829af1f140b3d63dfa7bd1cdccb80b07a12fbf92f7580ed54891e612 | 7e3aec1a3b9742792df7e29e0ba151f29775c5f70ca456f1db48ac30e9946813 | #101–#108 文档加入声明/HTTP/恢复/回执及诚实未验边界；保持历史格式解释。 |
| scripts/a2_full_scope.py | tests/test_verification_run.py | 65196031de305c040b73b3f7ae832813e1eb2af12db10b10ffe0493393c9a6ab | 6b8d8b0de2cbb768c9c6987a52f7dd9b12d42ce1838873ff52e26854b7cda620 | #108当前完整registry增加A10后，当前输出计数/历史stdout新组过滤必要兼容；原函数和参数化/早期发布点不变。 |
| scripts/a2_full_scope.py | tests/test_verification_compatibility.py | 77ddd42b829b2ea9c4cbff486ca54da3d40c9eefc3e27b4682e560841cd7b17d | 33adb6c58a86acb91f81309fd603c51ae04e8ebd0738e2d28027fa5b53313897 | #108当前完整registry增加A10后，当前输出计数/历史stdout新组过滤必要兼容；原函数和参数化/早期发布点不变。 |
| scripts/a2_full_scope.py | tests/test_a2_full_entry.py | 170e631f6d67bbb1d904d61ecc6a712b1884e1d8407d22dc70458c95485fa16b | f335f488299732292d94f7931dcdc91e0367c5798e5d67aa5689454da17da192 | #108当前完整registry增加A10后，当前输出计数/历史stdout新组过滤必要兼容；原函数和参数化/早期发布点不变。 |
| scripts/a4_scope.py | tests/test_a4_entry.py | 48ab0e4eccee9ed0f641b183fe3721c0f52da75e3e5bf9cf0997fcdfdba220f7 | 4ed30b5a4bfee215a6c926f375a5cc865289157ed3a0d11a16fc652e2cd45278 | #108当前完整registry增加A10后，当前输出计数/历史stdout新组过滤必要兼容；原函数和参数化/早期发布点不变。 |
| scripts/a4_scope.py | tests/test_a2_full_entry.py | 170e631f6d67bbb1d904d61ecc6a712b1884e1d8407d22dc70458c95485fa16b | f335f488299732292d94f7931dcdc91e0367c5798e5d67aa5689454da17da192 | #108当前完整registry增加A10后，当前输出计数/历史stdout新组过滤必要兼容；原函数和参数化/早期发布点不变。 |
| scripts/a4_scope.py | tests/test_verification_run.py | 65196031de305c040b73b3f7ae832813e1eb2af12db10b10ffe0493393c9a6ab | 6b8d8b0de2cbb768c9c6987a52f7dd9b12d42ce1838873ff52e26854b7cda620 | #108当前完整registry增加A10后，当前输出计数/历史stdout新组过滤必要兼容；原函数和参数化/早期发布点不变。 |
| scripts/a4_scope.py | tests/test_verification_compatibility.py | 77ddd42b829b2ea9c4cbff486ca54da3d40c9eefc3e27b4682e560841cd7b17d | 33adb6c58a86acb91f81309fd603c51ae04e8ebd0738e2d28027fa5b53313897 | #108当前完整registry增加A10后，当前输出计数/历史stdout新组过滤必要兼容；原函数和参数化/早期发布点不变。 |
| scripts/a5_scope.py | tests/test_a5_entry.py | c2964e07e423525bc23a7f3c992ad169640f00727b7e716370eaf425c74b8027 | 0b4cde834b9fee665da07f4c00f6403584749c955bf23b61d8c6d70e632fe8a6 | #108当前完整registry增加A10后，当前输出计数/历史stdout新组过滤必要兼容；原函数和参数化/早期发布点不变。 |
| scripts/a6_scope.py | tests/test_a6_entry.py | 0163e7a0e965421f4f20133f0dc6616a238574b26662e64d5b99d47296e4bc0c | 1b4f67c9e37a74f087ab74a4a64578f53ba353b6be3c19dee3536d7e70f9bff1 | #108当前完整registry增加A10后，当前输出计数/历史stdout新组过滤必要兼容；原函数和参数化/早期发布点不变。 |
| scripts/a7_scope.py | tests/test_a7_entry.py | d1d0d074380da63ba1aab8145ba0fc210e2aa692820000cfb5ed32ef4d9710df | e59861bb282e5dfb07a5254ec7849ea9aad93885e0833bfef83ef8187dc9ede1 | #108当前完整registry增加A10后，当前输出计数/历史stdout新组过滤必要兼容；原函数和参数化/早期发布点不变。 |

A10测试分母来自源码函数和显式参数化的独立静态计数；只读 `audit-verification-scope --collect` 仅核对收集，不代表执行或验收通过。最终固定模块与分母见 `scripts/a10_scope.py`。新增测试及具体要求由完整需求台账解释，不以数量替代覆盖。

A10显式固定Alembic动态消费的env与base→head全部历史migration字节；旧revision仅登记而不修改。恢复种子中的Pi包由已固定helper字面量构造，不把未消费的旧fixture文件纳入实际材料。CLI脚本、实际worker、reader与禁网sitecustomize都按具体路径登记。

A10不固定仅属optional A2-01的 `scripts/a2_scope.py` 预期字节；它不被A10直接消费，其本次真实字节仍受RunIdentity绑定。仅A2-01失败仍独立记失败，不能因此升级为required或令A10失败；该范围回归由A10真实入口用例保护。

两处全树format门禁必需整理均不改用例分母或生成材料字节：

| 文件 | 原 SHA-256 | 新 SHA-256 | 原因 |
| --- | --- | --- | --- |
| tests/test_a10_isolation.py | fcacc057f7b1ed737331152ad80ec7827c8a7c9c0be04c5f9fccf6971e125013 | eeb601ec91837408596ad581787426777f6a2141339a3bd8fc000c2e77814c91 | 函数注解纯折行 |
| tests/test_audit_sampling_feed_safety.py | 2cbf77aa213aa4004c40a0b79880f846a83a32e866da081b75d78c0512439efd | ba4a7a3226f29ed8ac1a390159ce952e318eabcfb99771e686406f663a563178 | 052f79f (#104) cp037向量纯引号规范化，生成字节不变 |

首轮完整执行发现七份旧完整入口断言仍按A9份数。按真实当前产物将正常13→14、无receipt失败12→13、附加合成组14→15、help十一→十二；历史stdout过滤仅追加A10新增行，原transcript与早期局部发布点不改。七文件函数和参数化完全保持，A10现37模块425例；表中保留最初旧hash并更新最终new hash及必要DAG传播。失败run不覆盖，修复后新提交重新完整执行。

首轮完整门禁的CLI共同故障是fixture包/CLI提前导入服务，使既有禁I/O帮助的socket替身在SQLAlchemy→asyncio→ssl导入链中失败。复用papers包既有延迟导出模式，CLI服务移到实际调用内；不更改禁网/SQLite守卫、不改公共服务或执行语义。新增七条真实安装帮助向量，A10 isolation从2→9例，总418→425，其余模块分母不变。

| 文件 | 首轮提交原 SHA-256 | 修复 SHA-256 | 原因 |
| --- | --- | --- | --- |
| src/paper_radar/fixture_audit/__init__.py | 62ca4edb4cbe9f438b35af89bf54069831de6a1301a836326c5ccae6a114f7fe | f48b5256ad1b729775953ef46326713d3336f7abb143acac9ab9ed8caa9f92a9 | 公共服务延迟导出/命令执行时加载，保留help纯本地边界 |
| src/paper_radar/fixture_audit/cli.py | 1f061fe401007e357fbc01bdb805a8d45dc505adab9cd3f8b205d7cd71a87c0c | b7a2736f6d58cc2064abf97c3c652866a8c86922d5714628f134757b8bdc84c6 | 公共服务延迟导出/命令执行时加载，保留help纯本地边界 |
| tests/test_a10_isolation.py | eeb601ec91837408596ad581787426777f6a2141339a3bd8fc000c2e77814c91 | b53e9972f960cbde722e739385e7a37b765802efbf982998b47588d18b57b25c | 七个禁网络/SQLite帮助向量，2→9例 |
