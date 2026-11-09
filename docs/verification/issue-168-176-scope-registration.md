# #176 精确范围登记与消费闭包验证

本次按所有者明确「授权」应用两份精确候选；授权对象为integration `1e7805ba0a7873d8ae0b390763558eff3f890c0d` 的审阅包，
包SHA256为 `4e6e168cbdd37e81c6c2de696a17ce7859da2102ed3e46758cfdc60f7bfba914`。
本记录独立冻结该包的142份材料消费闭包与33模块／522节点人工并集，不回写既有台账，不纳入旧required或扩大旧分母。
闭包候选JSON的SHA256为 `8220a96a1ef9f2ccdbe44a2e185e52fe57f5e5049dad62bd9cbcbab030ab3c08`；
本次登记控制文件、精确白名单测试预期与本新增记录是补充变更，不冒充上述142份原候选材料。

## 精确登记原因及影响

中央 `scripts/verification_scope_materials.py` 完整文件SHA256：
`3d140b890ff67d680ccef2c880d0a9aff42a4220fb622d774d5095c3a9da1491` →
`9b18c1ad90142d0d1aad474902e0a2abc6b2ba2c396d0b662a9d531c38c8f69e`。
只更新以下三条已集成普通实现的实际源码摘要，成员及用途不变：

| 源码 | 原SHA256 | 新SHA256 | 直接组 | 含下游的影响组 |
| --- | --- | --- | --- | --- |
| `src/paper_radar/cli.py` | `c53ebe63e06929dcbdeda76b127f4224fbce07399c5f01dc1165f9bca75428a7` | `0024f340e5a611e60b01d074ca13f7f5a4e49740cbe15610d7769c515b4714f5` | A10、A2-01、A3、A4、A6、A9、完整A2 | A10、A2-01、A3、A4、A5、A6、A7、A8、A9、完整A2 |
| `src/paper_radar/contracts/schema.py` | `f128e20731ece97f672ce50d9fb760a240abcdbd02b9aae63e83f2849fb0dade` | `ab0cdf935f5ed2a0b194dac9fcf7972dbad400166f49c692d0c8ca6f1aa951bd` | A9、A10 | A9、A10 |
| `src/paper_radar/pi_supply/cli.py` | `c0707ae2ac1910d94cabfcc1142f6fe6caa287773c473da7ad8cdc8fa23d558d` | `a0b19e2032870ce3e46a55117f0ba96dbd363ec48d184d6d75e952f74c4bbbc4` | A4、A10 | A4、A5、A6、A7、A8、A9、A10 |

三份实现已在准入／只读披露接线中集成；本次只将登记与实际已审源码一致，不修改源码以迁就旧摘要。

分类控制 `scope-material-inventory.json` 完整文件SHA256：
`f9318557091c2f51c8ea75d30efc6cb3c1440f8db21a88ad39cc3f23dabdc4eb` →
`03be2b61751fd444647cbde270a06720488cb0a8457d352e63db92484b691bf6`。
仅在live_documents.exact_paths新增 `docs/contracts/live-evidence.md`、`docs/contracts/read-execution.md`、`docs/roadmap.md`。
这些当前契约／计划按精确路径解除整文件历史绑定；未知文档不获前缀豁免。
分类控制的敏感影响为全部11组：A1、A10、A2-01、A3、A4、A5、A6、A7、A8、A9、完整A2；最终S3须按最终合入身份逐组确认。

未绑定的 `tests/test_scope_material_inventory.py` 只在既有显式authorized_additions集合追加这三路径。
冻结baseline扫描、集合相等、禁止path_prefixes、19条历史迁移及Markdown／JSON／ADR retain断言保持。
该模块的节点不并入下列33／522或旧required；没有更改旧scope成员、计数、格式、用途或历史证据。

## 独立人工模块并集

节点数沿用三份已冻结人工台账的有序并集，不从collect反推：
[集成闭包](issue-168-176-live-admission-closure.md)、[只读预算](issue-168-176-readonly-budget-wal.md)、
[after-backup续行](issue-168-176-resume-after-backup.md)。

| 模块 | 人工节点数 | 本次候选源码SHA256 |
| --- | ---: | --- |
| `tests/test_live_admission_registry.py` | 5 | `cdc85ebb3b58c129f4fa8da426039d57e5e5703c08547cbddb15f612c6f832a6` |
| `tests/test_live_admission_evaluation.py` | 63 | `c274643afc5c866909a3f101d5632c26e442014189526350fb89a5005d54cc07` |
| `tests/test_live_admission_time.py` | 6 | `e37db0567237f7efea48f1a1a348ab26106fdad4bf1c737838572e7b9c4742c4` |
| `tests/test_live_admission_reader.py` | 2 | `51fef391c231313f85caa4a72100e3168830ac7f2cbd7cbad76b166e0db270af` |
| `tests/test_live_evidence_receipt.py` | 14 | `8da0c8e9054732f48c2aab5897029cddd3b69263ce20ae9b0c1dc91b053369e3` |
| `tests/test_live_evidence_ledger.py` | 15 | `c3927b049485c6ab7ab9f8534100139ee8b6e3aafb19f7ab0b5835d467d31b13` |
| `tests/test_live_evidence_contract.py` | 2 | `6cbb66d9afd057f4f0529539a7f3a5573f26696b2627e963e8f6302a9dd4e1ed` |
| `tests/test_live_evidence_cli.py` | 4 | `01693d48d38b6bd45a89d360029bf102d5f304b0ddcece3edb4cb34c8c404571` |
| `tests/test_live_evidence_lifecycle.py` | 36 | `7ba1f9c8209473b1f608b263a77a5896e2887bb05bce06880bbdc6d743d1edbf` |
| `tests/test_live_evidence_loader.py` | 4 | `60f6e477069eca76ba1d96850844b64431fcb281b327679159cbb64c8028cbdf` |
| `tests/test_live_evidence_owner_cli.py` | 7 | `604735a95101624c5c45bcd4bd28b04675d1e8d6210513b616ec362d8113ff07` |
| `tests/test_live_evidence_tightening.py` | 10 | `1a2c3478fc1b2078be40773958da67a73f8d66bed1322eaba389e7fa1d1077dc` |
| `tests/test_live_evidence_observation.py` | 7 | `3bead53145a54044e9944922389c9705c43879edf1b0f8d0a82fce8172dddd2a` |
| `tests/test_live_evidence_baseline.py` | 5 | `c5d2dd03a150e82f1604cc3dcbffd5b197e6b34633754b68ebe51e2689f0b024` |
| `tests/test_site_collector.py` | 14 | `c06793bc6aeac6c0a8e30ee88546308a21c6306fd93d51b3d614419af36c0cd4` |
| `tests/test_site_deployment.py` | 8 | `38f154aa7b2c7c6904fd7a146b8f54715ce2f6383e08633305777bdf899ec015` |
| `tests/test_site_tree_identity.py` | 5 | `3963fa690245cd40cb6b93650b42123637899c38b620ec6a6024ebc0bc596cb1` |
| `tests/test_screening_live_admission.py` | 41 | `679229a2c7a090f01098daede233d82f3852d02ad3394187f4bda77750c6713c` |
| `tests/test_current_execution_binding.py` | 1 | `a40f5319c0a83d57e7b48af7ae7d8e47058c2a6f2ec97b4bba10a155c4fe27e9` |
| `tests/test_live_admission_source_guard.py` | 6 | `fab1188890e2763beb1f69f3b0886da993c803ce6524b817edf93b170656f205` |
| `tests/test_read_live_admission.py` | 53 | `101ffcabbc7a81d9546662257a67822599820651cdcc59e1434eea5310fc6547` |
| `tests/test_consumer_live_admission_consistency.py` | 6 | `a02a9089de16d56e8c17b8779e1234c9ed77ce5c85a23c97ac1131bd1644d91f` |
| `tests/test_doctor_admission_disclosure.py` | 8 | `dd2b34b1212a620f5a6c82f5743e0c834cba695530c83acf38760986499090ee` |
| `tests/test_doctor_live_admission.py` | 9 | `3a15245943d380423d1a5b9d0aacc0072487779979ecb78095182fa90f31a621` |
| `tests/test_site_deployment_checkpoint.py` | 10 | `2e5636560b7ee47026053e512cf1cdbf4052c0337b2e9306e7ab53a6ed4dd0ca` |
| `tests/test_site_g2_entry.py` | 9 | `b504e1bca8ae35b43d963c76364c8d552971f43ce00cfd9ad58866f700f59775` |
| `tests/test_live_evidence_review_freshness.py` | 17 | `54c50d8f24adae1a07ecf86130f00fa7f8792ef20f4b1b9d599583c4a74ee516` |
| `tests/test_site_runtime_upgrade.py` | 27 | `cbcfa38cba34b9358981b10caf23d13aa8331dd1dcbaad551b1acd4a86dbf08a` |
| `tests/test_live_admission_closure.py` | 25 | `7d89b965014fa09b687eac8fb5da9d31d90f16863ed42d436cee8a8e8e4313d7` |
| `tests/test_final_admission_regressions.py` | 20 | `20d7d968b2f2e8f80fa01be568f0d95971f232453701bf0fdb9a5768d445816b` |
| `tests/test_protected_admission_intents.py` | 39 | `8305b2a088769129eb5039ea076355383448b21e2d62c06df725472c4768948c` |
| `tests/test_owner_budget_readonly.py` | 17 | `74fc78cecc40fad910a3afb14037692fdc26d280bf4cab4cd25c88053d589da8` |
| `tests/test_owner_resume_after_backup.py` | 27 | `51781d14eb99b7de1e2525523c29d8fab70b071f1406024b078bf9b6f24d1271` |

合计33模块／522节点；模块字节逐项保持候选摘要。本次只运行登记相关子集与真实兼容组合，
没有将collect、旧开发子集或历史失败冒充本轮522节点全部执行。

## 142份材料消费闭包

下表固定写回前 `1e7805ba0a7873d8ae0b390763558eff3f890c0d` 获授权候选的完整路径与摘要；
登记开始时逐项核对实际字节一致。本轮README／owner活摘要等补充变更另列，不将此历史快照冒充最终树摘要。
类别沿候选，不建立新正式验收组，也不解除既有固定材料约束。

| 路径 | 类别 | SHA256 |
| --- | --- | --- |
| `GLOSSARY.md` | live_document | `e36c552d15292c178d310314925339798b519abdc5681e36cc989f7693827721` |
| `README.md` | live_document | `4f629ab77fb4c0e90e794cdb568a8984b909f0ac70bedcf4d23c1e2987a2ded9` |
| `contracts/live-evidence/live-evidence/v1/manifest.json` | frozen_contract | `838d684e6d4e228a34e21f33de4a0aed0d92ecd2ea0c63be0f68470b7c3dcc2d` |
| `contracts/live-evidence/live-evidence/v1/schema.json` | frozen_contract | `3d84cb21b85cdb2171d071ef11cfaaf00bf2aefdf031f32210c654fe6f76c440` |
| `docs/adr/0052-version-admission-uses-and-capability-requirements.md` | decision | `7274023bb1a197082ff471b8ca30daed547ebe7395a1cb3117534ffb8d2b113f` |
| `docs/adr/0053-expire-capabilities-by-evidence-class-and-coverage.md` | decision | `b67c801c5d18e62cea3c60fb403a4ff462065b71cc94f88a6d57e6d8b0f6503f` |
| `docs/adr/0054-separate-execution-binding-from-call-materials.md` | decision | `0d523a263ae82ecf3893b7064befc4571da02184603b5c4b8758190161806a55` |
| `docs/adr/0055-separate-protected-admission-ledger-from-business-facts.md` | decision | `62ba27804acf7da82750493af57d8b91ad029c4c9e351e249454d25e310b6e4d` |
| `docs/adr/0056-protect-pending-revocations-with-an-append-only-log.md` | decision | `c3ef83f3efb5ff7814a1b96e9cbe94d411322e499cf1cd3c3767fed208f6bdcf` |
| `docs/contracts/doctor.md` | live_document | `c2b1b50e270ed66bca22ff7b637673fe3105f5a46785e238d2da877bcc4bf937` |
| `docs/contracts/frozen-contracts.md` | live_document | `3e213ccfcfe62604266fcc227a3f58048f30bca75d69e2581fdd64616c1691c3` |
| `docs/contracts/live-evidence.md` | live_document | `4e481e3eaed919d0983bb71096e49ae38c2b9e042821a7c24b2c26fd839713e3` |
| `docs/contracts/pi-execution.md` | live_document | `bcd8c540f384c04712882c7cc7543557ddf85ce38c5f93ae23bcc60b145521e1` |
| `docs/contracts/read-execution.md` | live_document | `4c2ad5b5bf757e538a482f9b31240c36d652d698b5317c87bc2174d99ce7ce04` |
| `docs/roadmap.md` | live_document | `3e760e6ca8216535322bcd7d72693d4306cb0e4ded7af852df47a46efb9c88db` |
| `docs/verification/issue-167-index.md` | evidence | `7e5c5f1e354b5e76c05cd34ce028ace76c6f3d303ab655f4e83fc4f97f71e9b7` |
| `docs/verification/issue-168-169-admission-model.md` | coverage | `1048abcd428aff96be6bb84242392ad4d1d59f0dbc332235626faf756bc2262c` |
| `docs/verification/issue-168-170-evidence-ledger.md` | coverage | `edb7d3a578b99d8be9ffe019f9f386fecf2172c67d4b018fb138b2d6b485a6ed` |
| `docs/verification/issue-168-171-evidence-lifecycle.md` | coverage | `42b7596eda99d8f0df13d8e823333ae2f0206e9538d8488b278cc747edbdd0e7` |
| `docs/verification/issue-168-171-review-freshness.md` | coverage | `0e2174bf6010f062849baba5978795a862dd4699c829a184ae090bba453953ef` |
| `docs/verification/issue-168-172-deploy-checkpoint.md` | coverage | `cd41de2dd3d33d6f02d689be1be11abb6b0a122b0d7a73a889b5cc9e077634b4` |
| `docs/verification/issue-168-172-site-collector.md` | coverage | `29fd3cd2a571a2271c52b7ac7503e0273b3194070aeda793605f5797ad38e4c8` |
| `docs/verification/issue-168-173-screening-admission.md` | coverage | `472d6ace1a3e8a1b9f0b32e21998a19f87dd1f1caac683fa4e38fa12dd72254b` |
| `docs/verification/issue-168-174-read-admission.md` | coverage | `766583e39972c777ba941842a3925bfcd8951f0ddf7ca04b7a6e0120cc92e3ba` |
| `docs/verification/issue-168-175-admission-disclosure.md` | coverage | `03dce7a7e8998ff5f36860bb6de785e69b0f0217e85371721e5d2ee064da118e` |
| `docs/verification/issue-168-176-final-review-fixes.md` | coverage | `e615c6bb3d21bc024d46dbcfb8ae1c5e0e878c23c3eed6d50e0fb1c889808c56` |
| `docs/verification/issue-168-176-live-admission-closure.md` | coverage | `db4180ea1e89fe5c52c1b35d719e230996426373128375b0877af8a134b41402` |
| `docs/verification/issue-168-176-owner-safety-verification.md` | coverage | `d841783938e23a43bc8d45f048bb616b04a61b39aff1cb032ff53d94a069da28` |
| `docs/verification/issue-168-176-owner-terminal-recovery.md` | coverage | `31b6592b8f72c67edbbccd21fa2b56144880eb510ae91d949459b5badbd8edcc` |
| `docs/verification/issue-168-176-readonly-budget-wal.md` | coverage | `5b00a27b370f907c67c9fd3224bb0c1a1ca9cc76446145c0a88485d7c270d15d` |
| `docs/verification/issue-168-176-resume-after-backup.md` | coverage | `d3da5955f5111f9ce4a0842e1fd085fe7c1d817fe12d25422eee1ad75be6b6a0` |
| `intent/draft.md` | live_document | `7f04c71597cf8f5a110207c5acc40556e62d9e591840856eb57df8218fb67a3d` |
| `intent/review/issue-168/closure-owner-plan.md` | process_proposal | `5373fbe3bc1e6ba02722d6941d785c6e94830e44c2906a7c483023d7a6734fc8` |
| `scripts/issue176_admission_snapshot.py` | support | `316597c16bd594c66ef57fb6200606ef50a72c7684d22251292f2d62330703f7` |
| `scripts/issue176_closure.py` | support | `979dba25aee6dec3958f99551c95ae38c2d4af7b732fa0a6906ec2d0452ce524` |
| `scripts/issue176_closure_workflow.py` | support | `e6d88f15da60ecca2f735283471aa7b62249fb3874a8ae10b6e20f20abeda2ab` |
| `scripts/issue176_resume_after_backup.py` | support | `0506ca95472beeb27564931d963596d4be6cff09287c46a633e3387162f3cf01` |
| `scripts/issue176_resume_after_backup_workflow.py` | support | `dfb2b7f2ee917c689143a6e61a26352517173641acc887feba58c64b87560bfb` |
| `scripts/seal_site_evidence.py` | support | `7289bb275a60b43600aeb2c7a2827b7e262fe49dcd378b8a226848927cb90077` |
| `src/paper_radar/cli.py` | source | `0024f340e5a611e60b01d074ca13f7f5a4e49740cbe15610d7769c515b4714f5` |
| `src/paper_radar/contracts/schema.py` | source | `ab0cdf935f5ed2a0b194dac9fcf7972dbad400166f49c692d0c8ca6f1aa951bd` |
| `src/paper_radar/doctor/admission.py` | source | `fc6621cb10a4fdbf0a720ec7fd8013d987d69ba86299b28777801656cd0de608` |
| `src/paper_radar/doctor/cli.py` | source | `10020a436c7700bffe05db243fbcded75f7cbe130211a4fd20a03a54951b7589` |
| `src/paper_radar/doctor/pi_exec.py` | source | `685e8f5dbe78fa0c668dd1072f61bdab44a18910c803b9a23a7db7674332ff45` |
| `src/paper_radar/doctor/service.py` | source | `77f39076ef2e561975f8981ccecb82933f56f79d04928cd685b43c2950b68a11` |
| `src/paper_radar/live_evidence/__init__.py` | source | `3867dc3e97733ac78a32e7e23335689757b834ff1837c23571b52f5890ff68a5` |
| `src/paper_radar/live_evidence/baseline.py` | source | `163e6cb8dade93ff8926080889b7d958887bf148af99e169d22bbde3af96a17d` |
| `src/paper_radar/live_evidence/cli.py` | source | `c2542221dfeb7b757c857ce107b365746061506858e5048f5888d46fb60af56b` |
| `src/paper_radar/live_evidence/collector.py` | source | `6d2d8700cdb93d608d8854f90a2a374c330a1e9604c049f4f80fa46af8a46b0f` |
| `src/paper_radar/live_evidence/deployment.py` | source | `ccfec1ce327a6c39a7d82332790a0baba322b5905c787425e251554be0733175` |
| `src/paper_radar/live_evidence/evaluator.py` | source | `51b67b2abc59ddc58840fc3d2b1aa8605e5822f51fbdee19ab743f8b27005738` |
| `src/paper_radar/live_evidence/evidence.py` | source | `113c5d80e96f56bf079f0897d9b45d1dc04295114aeb3b9749d957e67675559a` |
| `src/paper_radar/live_evidence/intents.py` | source | `e749d87adb20481667a9caedf12ed2b9f62ffda04f1ea9eb3c5f085da1e6264d` |
| `src/paper_radar/live_evidence/ledger.py` | source | `fa38c7aeda6690e5f00b6aa23a7928a96fc568dd51308f23be1bde78317c8e1b` |
| `src/paper_radar/live_evidence/lifecycle.py` | source | `a7f7c32713cde82e28bf3b70b4d17118df44793c6f5d94e3824e2f9b77bd9ef1` |
| `src/paper_radar/live_evidence/observation.py` | source | `dfc311d6879087eaa6ccb9a5018a773bb51ed254aa11a047bb5abd43541efd28` |
| `src/paper_radar/live_evidence/reasons.py` | source | `5fa64aa791309abd9c8d671d744f21661a1b36e07ed1b68e5217ce11e516caed` |
| `src/paper_radar/live_evidence/receipt.py` | source | `275dae6a162d33b2d6d214a09d5ac4511868436c1724317f4b218ecb5b376491` |
| `src/paper_radar/live_evidence/registry.py` | source | `cb4b600ed39b6cf6d2ff225727faead4183381a3944b3fa84df48728a2eed284` |
| `src/paper_radar/live_evidence/sealed_runtime.py` | source | `549b9a7111e26f7aace3fbd866858108d16d32f00db163c82f0d80ae631e6126` |
| `src/paper_radar/live_evidence/service.py` | source | `2d41a55d58150330619cade59596d83d2c762510ff95f9b0a6fd4f1b6435e981` |
| `src/paper_radar/live_evidence/site_tree.py` | source | `90a6917a13aee4506929a2c69851d5b1e5581400b32de374f9c93a9756a2630e` |
| `src/paper_radar/live_evidence/tightening.py` | source | `57fd9202cc89a87abfa40512a418320f76268d6001f03345485739f5153e4962` |
| `src/paper_radar/live_evidence/time_policy.py` | source | `9f2c35c08d89343d6108e410e0a33822867caa58ce659c6ee95a3f525954454a` |
| `src/paper_radar/live_evidence/types.py` | source | `a94ad9b13c95d3d352465e77868ba8ec707763cfad4fb61557f690cd22536ffc` |
| `src/paper_radar/llm/__init__.py` | source | `593aded4206190482fceb1646ad1a37804499340f488c3cd87d5f154590e9ced` |
| `src/paper_radar/llm/calls.py` | source | `9a42c0331335e47944a115ae46e411bf4f8bfd8ebd15f447bcbabf8db2d8b477` |
| `src/paper_radar/llm/models.py` | source | `a08af74b01fbec27a6108df73b9a54b5a6f3afe70b58794809be598155442664` |
| `src/paper_radar/llm/rpc.py` | source | `99c6203bf4e02d308d12b2498147fe04c2777d4841308c3e2aed79f27d82adc5` |
| `src/paper_radar/llm/rpc_frames.py` | source | `98628acd0b56b7ac9c1b9896f82abde034aa51120e4d7c08e2c91ffe5cdbae22` |
| `src/paper_radar/llm/rpc_messages.py` | source | `53c244de76943573a7938c8c22a2500c860e5fce63ec0b96ac3f215b6b9600a6` |
| `src/paper_radar/llm/rpc_pipes.py` | source | `d294ca3ab3e1170af072bd7fe2f77387d72adf97b2e49231021213b76b3c3c3a` |
| `src/paper_radar/llm/rpc_types.py` | source | `2b3f15472b6c548854d308a9b20ef566fd52e7cc8e635bf5445f6d356cd4a179` |
| `src/paper_radar/pi_execution/admission.py` | source | `870ece981fab6c25a8284f6e4bf19a532e1efa7b5483313e5af935378b18b50e` |
| `src/paper_radar/pi_execution/admission_guard.py` | source | `5005babd6a12bb1691cffbac4f1629a2da793fc9f8a1965c2b223fb15ffba9bd` |
| `src/paper_radar/pi_execution/auth.py` | source | `485ff8dc76d0ee33f828b527442c4adeb17acea787039a36deed7f03164d9f08` |
| `src/paper_radar/pi_execution/current_binding.py` | source | `6c55e15dc989481ed9cb7a8e07da7e93f9b54a04d1796b4a924eb849fdf1ca3d` |
| `src/paper_radar/pi_execution/isolation.py` | source | `718a649941418d3309bca992238c43026deec67bada878629eba1a80aaa40d31` |
| `src/paper_radar/pi_execution/launcher.py` | source | `48b6c070bb908a1c783e6a357ddc56213806a1baa5ff050a667f74f05c37df56` |
| `src/paper_radar/pi_execution/process.py` | source | `e469cb84103c1722a9a5334b93df938ecacd28150b42bdedb4f68e199c3d80d1` |
| `src/paper_radar/pi_execution/resources.py` | source | `088fc7c08d88d8b0c804153fd20c286c1650a89ad6268371aa300725228ca905` |
| `src/paper_radar/pi_execution/service.py` | source | `08a4d12f3b3ebffe89c2b12633064fe9f4ca1d19a4eb3f58cc540e096e1aa6ba` |
| `src/paper_radar/pi_execution/site_binding.py` | source | `625b5d3b1c1b2f23da321a568a94d3675a7cb337003b69ff48c2e0a2f2860d0b` |
| `src/paper_radar/pi_protocol.py` | source | `08cf23860f6ff345fd9d0d24c031de3cd5d3eee56591dd2995dffcd792f555f3` |
| `src/paper_radar/pi_supply/cli.py` | source | `a0b19e2032870ce3e46a55117f0ba96dbd363ec48d184d6d75e952f74c4bbbc4` |
| `src/paper_radar/read_execution/service.py` | source | `a1acc62b15e4ce90e875c7a8cb401288e8f6b4fbdd13065a0e79d9dbc36ece89` |
| `tests/fixtures/live-admission-source-guard-v1.json` | fixture | `695c4e9bc933b06bb211663796bb1dd89db52d000881c8590e82ac4e57e1a2f0` |
| `tests/fixtures/live-admission-source-guard-v2.json` | fixture | `aa3cb3836b4072a8e6d66b6c99f3181f901f90aa8015e59dc24a3c82d8244ac4` |
| `tests/fixtures/live-admission-source-guard-v3.json` | fixture | `78c7e3f27768e138a9137395cefb71cb0058005020cf3a4d1ac4ad9fc5726fc6` |
| `tests/fixtures/live-admission-source-guard-v4.json` | fixture | `ff8a37321ea097d9d444d4840212f249431d36d2b364f275f7ca1253db7cefc1` |
| `tests/live_admission_closure_support.py` | test_support | `a221c6a3dfaae770ca7bd8c57c74939d0fbc2920d0905f8b6c0db62efd589f9e` |
| `tests/live_admission_support.py` | test_support | `cadc084a0abf3d04745497decc4fcd272b68facbf7f6fca9a31bfc58b43093fa` |
| `tests/live_evidence_ledger_support.py` | test_support | `879224e1d27f65f5d5acd5845cf262a14daef4c39114f959218cd71038174064` |
| `tests/live_evidence_lifecycle_support.py` | test_support | `b0ac64b3c49203cd8dd20d9acf5ea93778e9bb4f0f21a2dfed38ecb783b0b981` |
| `tests/pi_execution_service_support.py` | test_support | `ed982a5192a38ee0e8eb1c1f2901cba41fe4185d19d991cc979657cd99b5f8f9` |
| `tests/protected_intents_support.py` | test_support | `f4fe7794bc5654299ba74e2ee61a5ad045c8768bbbe805f85d668c32c5c4253b` |
| `tests/read_execution_support.py` | test_support | `bc8cbc566c6d617ff9332972434195f70b0f444c1d2954579357562915b32859` |
| `tests/screening_live_admission_support.py` | test_support | `df3fe707ebcad3361c3b736fa5e98619da334a07ec6d7bbb1c05216f6ff9c111` |
| `tests/site_collector_support.py` | test_support | `b93e425316cb2c3a08c1a1db22b936cc2580b6d2e032675c9c5725a7bfb7a5b2` |
| `tests/site_deployment_checkpoint_support.py` | test_support | `5565d741889e54dac8de9015f555e888db5d57823c0c0239184a6d5d6bf9a35e` |
| `tests/site_deployment_support.py` | test_support | `07d76c23d5e6ae06dbeca579a3558f1978b97db1c7264caf06052a1c7e4065de` |
| `tests/site_g2_entry_support.py` | test_support | `5367f7db0bacef12a90556e9b0472a180f26391b7d265c2f66cd67405ff7d8ae` |
| `tests/test_consumer_live_admission_consistency.py` | test | `a02a9089de16d56e8c17b8779e1234c9ed77ce5c85a23c97ac1131bd1644d91f` |
| `tests/test_current_execution_binding.py` | test | `a40f5319c0a83d57e7b48af7ae7d8e47058c2a6f2ec97b4bba10a155c4fe27e9` |
| `tests/test_doctor_admission_disclosure.py` | test | `dd2b34b1212a620f5a6c82f5743e0c834cba695530c83acf38760986499090ee` |
| `tests/test_doctor_live_admission.py` | test | `3a15245943d380423d1a5b9d0aacc0072487779979ecb78095182fa90f31a621` |
| `tests/test_doctor_pi_exec.py` | test | `c96002be91c1aac359e2264039b8bc83bb252ab902bb3f060ea673408fad62ee` |
| `tests/test_final_admission_regressions.py` | test | `20d7d968b2f2e8f80fa01be568f0d95971f232453701bf0fdb9a5768d445816b` |
| `tests/test_live_admission_closure.py` | test | `7d89b965014fa09b687eac8fb5da9d31d90f16863ed42d436cee8a8e8e4313d7` |
| `tests/test_live_admission_evaluation.py` | test | `c274643afc5c866909a3f101d5632c26e442014189526350fb89a5005d54cc07` |
| `tests/test_live_admission_reader.py` | test | `51fef391c231313f85caa4a72100e3168830ac7f2cbd7cbad76b166e0db270af` |
| `tests/test_live_admission_registry.py` | test | `cdc85ebb3b58c129f4fa8da426039d57e5e5703c08547cbddb15f612c6f832a6` |
| `tests/test_live_admission_source_guard.py` | test | `fab1188890e2763beb1f69f3b0886da993c803ce6524b817edf93b170656f205` |
| `tests/test_live_admission_time.py` | test | `e37db0567237f7efea48f1a1a348ab26106fdad4bf1c737838572e7b9c4742c4` |
| `tests/test_live_evidence_baseline.py` | test | `c5d2dd03a150e82f1604cc3dcbffd5b197e6b34633754b68ebe51e2689f0b024` |
| `tests/test_live_evidence_cli.py` | test | `01693d48d38b6bd45a89d360029bf102d5f304b0ddcece3edb4cb34c8c404571` |
| `tests/test_live_evidence_contract.py` | test | `6cbb66d9afd057f4f0529539a7f3a5573f26696b2627e963e8f6302a9dd4e1ed` |
| `tests/test_live_evidence_ledger.py` | test | `c3927b049485c6ab7ab9f8534100139ee8b6e3aafb19f7ab0b5835d467d31b13` |
| `tests/test_live_evidence_lifecycle.py` | test | `7ba1f9c8209473b1f608b263a77a5896e2887bb05bce06880bbdc6d743d1edbf` |
| `tests/test_live_evidence_loader.py` | test | `60f6e477069eca76ba1d96850844b64431fcb281b327679159cbb64c8028cbdf` |
| `tests/test_live_evidence_observation.py` | test | `3bead53145a54044e9944922389c9705c43879edf1b0f8d0a82fce8172dddd2a` |
| `tests/test_live_evidence_owner_cli.py` | test | `604735a95101624c5c45bcd4bd28b04675d1e8d6210513b616ec362d8113ff07` |
| `tests/test_live_evidence_receipt.py` | test | `8da0c8e9054732f48c2aab5897029cddd3b69263ce20ae9b0c1dc91b053369e3` |
| `tests/test_live_evidence_review_freshness.py` | test | `54c50d8f24adae1a07ecf86130f00fa7f8792ef20f4b1b9d599583c4a74ee516` |
| `tests/test_live_evidence_tightening.py` | test | `1a2c3478fc1b2078be40773958da67a73f8d66bed1322eaba389e7fa1d1077dc` |
| `tests/test_owner_budget_readonly.py` | test | `74fc78cecc40fad910a3afb14037692fdc26d280bf4cab4cd25c88053d589da8` |
| `tests/test_owner_resume_after_backup.py` | test | `51781d14eb99b7de1e2525523c29d8fab70b071f1406024b078bf9b6f24d1271` |
| `tests/test_pi_execution_admission.py` | test | `e1dd56340ee472f684208ce781940d0f545812ba6d27b1ece6360550c44cdbeb` |
| `tests/test_pi_execution_feed.py` | test | `5432f11c5bb66c74242041c7aae267f130a11ff48eb379c7f18018676dece2f6` |
| `tests/test_pi_execution_integration.py` | test | `4ab7159c30911e50c49b6e2080d2eacb1c441fdef6762fdf02d7f69c51eba298` |
| `tests/test_pi_execution_service.py` | test | `689897102e738cda65f9b772b0c3a20f3e4a21da21ef76d918bdeccee17f4702` |
| `tests/test_protected_admission_intents.py` | test | `8305b2a088769129eb5039ea076355383448b21e2d62c06df725472c4768948c` |
| `tests/test_read_execution_admission.py` | test | `ae7d69bbfde7df004931950cf32bdf289784a3aefe18f1e27c55d6e1d93f9eb5` |
| `tests/test_read_execution_resources.py` | test | `607d4e00d55f1914ff93b81955c1ae4ba4de00b6d3b8fcab60dbbb91929b9e45` |
| `tests/test_read_live_admission.py` | test | `101ffcabbc7a81d9546662257a67822599820651cdcc59e1434eea5310fc6547` |
| `tests/test_screening_live_admission.py` | test | `679229a2c7a090f01098daede233d82f3852d02ad3394187f4bda77750c6713c` |
| `tests/test_site_collector.py` | test | `c06793bc6aeac6c0a8e30ee88546308a21c6306fd93d51b3d614419af36c0cd4` |
| `tests/test_site_deployment.py` | test | `38f154aa7b2c7c6904fd7a146b8f54715ce2f6383e08633305777bdf899ec015` |
| `tests/test_site_deployment_checkpoint.py` | test | `2e5636560b7ee47026053e512cf1cdbf4052c0337b2e9306e7ab53a6ed4dd0ca` |
| `tests/test_site_g2_entry.py` | test | `b504e1bca8ae35b43d963c76364c8d552971f43ce00cfd9ad58866f700f59775` |
| `tests/test_site_runtime_upgrade.py` | test | `cbcfa38cba34b9358981b10caf23d13aa8331dd1dcbaad551b1acd4a86dbf08a` |
| `tests/test_site_tree_identity.py` | test | `3963fa690245cd40cb6b93650b42123637899c38b620ec6a6024ebc0bc596cb1` |

已部署v4清单 `tests/fixtures/live-admission-source-guard-v4.json` 保持SHA256
`ff8a37321ea097d9d444d4840212f249431d36d2b364f275f7ca1253db7cefc1`；
v1／v2／v3、39份guarded源码、root runtime／payload及所有旧证据原字节保持。
本次没有root、站点、业务数据库、模型、认证、网络或预算操作。

## 环境边界与验证

原环境Git为2.54.0，无gc／maintenance显式配置，亦无GIT_CONFIG_COUNT／KEY／VALUE覆盖。
最初相关72节点为70passed／2failed：一个是获准三路径尚未加入有限测试预期，另一个是shared-DAG子进程缺baseline。
只追加授权路径后，原组合71passed／1failed，仍为shared-DAG另一参数；不能以单节点复跑green替代组合。
原三参数tight loop再次1failed／2passed，trace捕获6次maintenance与6次repack：初始fixture commit的detached repack尚未结束，
紧邻reviewed commit又启动维护。失败副本MIDX仍引用旧对象而pack只余新commit，旧tree／parent缺失。
仅对测试进程设置maintenance.auto=false后，同一原三参数3passed／8.74s，trace为0次maintenance／repack；
原72节点完整组合72passed／83.09s。该隔离不修改Git ancestry／审计规则，不改宿主或仓库配置，不宣称修复Git本身。
旧 `tests/a2_full_support.py`、shared-DAG代码／断言及第四条中央摘要均未改。

所有相关验证使用显式进程级覆盖，原环境没有需要保留的既有Git配置槽位：

```sh
GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=maintenance.auto GIT_CONFIG_VALUE_0=false \
  PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  uv run --offline --locked pytest -p no:cacheprovider -q \
  tests/test_scope_material_inventory.py tests/test_scope_central_registration.py \
  tests/test_scope_document_guards.py tests/test_scope_shared_dag.py
GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=maintenance.auto GIT_CONFIG_VALUE_0=false \
  ./scripts/check-compatibility all
GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=maintenance.auto GIT_CONFIG_VALUE_0=false \
  ./scripts/audit-verification-scope --json \
  --base b133d4eb333530f6c017b821d588a1087d6123ba --integration-target main --collect
```

若后续执行环境已有GIT_CONFIG_COUNT，须保留原键值并追加maintenance.auto=false槽位，不覆盖原配置。
该环境约束须由最终门禁执行进程继承；不靠修改旧固定材料或跳过测试避开后台维护竞争。

相关模块节点单列：material_inventory 4、central_registration 17、document_guards 27、shared_dag 24，共72。
它们不是旧33／522的新成员。主代理独立核对有限白名单差异，原历史／未知材料断言均保持。
文档链接原4节点4passed／0.06s；owner方案4条、新D1三条本地相对链接实际解析全存在。
修改测试的Ruff check／format及mypy通过，git diff --check通过。

真正compatibility all实际收集20模块、去重176节点，**176passed／393.98s**，退出0；
内部耗时394.45s，入口总耗时394.71s，无skip／deselect。原授权写回前65failed／111passed不被反推为本次结论。

显式base／target只读审计1214条材料均ok，baseline_issues为空，旧三源漂移已消失；
退出1仅因分类控制的11组confirmation_required。带--collect同样受控not_run／audit_failed，
未把未运行的收集写成固定分母通过。最终S3确认必须按最终合入身份重建，本记录不提供替代确认。

本次补充变更为两份精确登记控制文件、有限白名单测试预期、新D1，以及README／owner方案的当前摘要和真实断链修复。
142份表固定为写回前1e7805候选快照；登记开始时逐项核对一致，随后活摘要的新字节不冒充表内旧摘要。

本记录不提供正式S3确认或同次完整门禁结论；#176／#168及Live／B完成判据保持。
最终合入后由主代理按精确身份逐组完成S3，冻结后由唯一执行者按已有授权运行G4。
