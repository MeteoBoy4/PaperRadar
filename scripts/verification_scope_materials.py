"""跨组共享固定材料的唯一哈希登记; 各组显式保留用途与成员资格。"""

SHARED_MATERIALS = {
    "tests/migration_expectations.py": (
        "cb303a45c7072a6d59b3fc7a60ca6649b0a6eeeacec3d2d29432a98c0a3fb019"
    ),
    "docs/verification/contracts-backup-restore-history.md": (
        "77fdc9ee348bddd16d5c5a694ef52459d2703241efe5e123da8e6742f68ff46e"
    ),
    "docs/verification/offline-evidence.md": (
        "032f9ad1cd91161c36060977075d012e9e03e99e915ce9578c3c431d2ec7e363"
    ),
    "examples/config/adapters/pi-v1.yaml": (
        "4266c0a79632ffb9bfe17ae217893d25f80a0c498690698ebe3e80aaf31ab382"
    ),
    "examples/config/models/models-read-v1.yaml": (
        "e122228e4eb55c61b4dbf85349d75049c309223d83dad0b5edaa5b041c6cd93e"
    ),
    "examples/config/profiles/profile-example-v1.yaml": (
        "bccacc1659b54a36d7da7159616cf276d21558d82036cc9918b46d50d14c38ed"
    ),
    "examples/config/prompts/pi-system-v1.md": (
        "8b0188e425cc6a77059940a6a5c371f39f8eb28346ef504c5a3ec6b247747c25"
    ),
    "examples/config/read/read-v1.yaml": (
        "ff267cfa3280e469b205859a2408c042c4ca7243553c1427971e6ad0d624813d"
    ),
    "examples/contracts/screening/boundary/v1/manifest.json": (
        "5efa0aec0e41329fe8736dcd533706309fd9c3717aeac14ddbf55d05cce0ed0b"
    ),
    "examples/contracts/screening/boundary/v1/schema.json": (
        "9fd5127a8081fb30f62f2b436a4b6067d1b0ae16fea8d4f190c36874ef8805a7"
    ),
    "examples/prompts/reading/v1.md": (
        "674def579de57a15dc71d5a66af1c69725641484b0c79f1c20c2c4b1abfce1fb"
    ),
    "examples/prompts/screening/boundary-v1.md": (
        "7d116290291efcff745119919e6d5f827e2fbc38e20d0f93ac974b7530a33d1c"
    ),
    "pyproject.toml": (
        "282f74be3e1da65a4819f03c441274f9b47442737243f9e9a80f3d18cb7f89f7"
    ),
    "scripts/a1_acceptance.py": (
        "6d823619d4a139c5df7d19be39f7c5ec409af2a7d7d1864d757dcc7fa697b4df"
    ),
    "scripts/a2_acceptance.py": (
        "0843f426d5d59f9d53d718cd7962cee769d0308eda47138d79f0766f43e01c0b"
    ),
    "scripts/a2_full_acceptance.py": (
        "acd3291dc41e4a9947aabce4667e44e13c80b4c2cbe26e2b9c68cf9d8c0c0cdf"
    ),
    "scripts/a2_test_receipt.py": (
        "f3ceca12ce45e3a6bb1669b9d7cae671028224be41c2e2a71d25135a4387e760"
    ),
    "scripts/a3_acceptance.py": (
        "bee7e6b29c2fe1ef4e96311a3c1626e24c7266e440c2e1a685afba1a0448229e"
    ),
    "scripts/a4_acceptance.py": (
        "1fff915ac03183daa659281ad3119e2281bd1f052fe4946a3062d70d454caae2"
    ),
    "scripts/a5_acceptance.py": (
        "ed5517bec34993540c276c6136b7f30e685559f84a0e9dfd9c9fced3769a95d3"
    ),
    "scripts/a6_acceptance.py": (
        "ebd079873bbe3e440ff109d34cc84dc21ab65209a8033dc63e356c3d44ba040d"
    ),
    "scripts/a7_acceptance.py": (
        "2752e1d75cb0ee64efdfe1cf27a1e30c08fb054db20ec25c810e36f791b8a565"
    ),
    "scripts/a8_acceptance.py": (
        "94fd03d97abbe0a92bdd6778c0091264d1dcabede137f7949748c797fee56a0c"
    ),
    "scripts/a9_acceptance.py": (
        "9b566dd59ea82caa62ccaffdf32203627db73af4d7734e8e2ddfbbe8320d8899"
    ),
    "scripts/check-offline": (
        "63aae23251385e656b7c55d493de87204a44973f40ccefbc4d2fde78650c3d89"
    ),
    "scripts/offline_evidence.py": (
        "b520cd09e633219e475fc8bcb71ad2ebb0bda515330850255a8f2831d416ecdd"
    ),
    "scripts/verification-status": (
        "b761281e99e934dfba7949212156ce19f403068414033cb5b194768b684ee4cd"
    ),
    "scripts/verification_checks.py": (
        "f93113dcaa037ed7b5992133320a58d36dcf438c1d82969c94611c54649788bc"
    ),
    "scripts/verification_identity.py": (
        "27ebdd057098256f0419c34cb9dbc410e0c6f0c7a8c3c931f62cc6942ca8d7b5"
    ),
    "scripts/verification_publication.py": (
        "337c9efb7ee906486e9de9bb5ec4d60bd9bde7fe358f60098036862e1ac77072"
    ),
    "scripts/verification_run.py": (
        "a4d08449eb65ac7e2c39d2fe972cccf28ec8af13dcf5d34795ac1c088212ae0a"
    ),
    "scripts/verification_scope_audit.py": (
        "599fa750491e60f8482524266d7a5f771d3007811e120d91968071943db13c9f"
    ),
    "scripts/verification_scope_baseline.py": (
        "8bff210448f4a702b2f8119dcbd47e0fdf80b4a27392ca5e41f8d61fa78a1c4a"
    ),
    "scripts/verification_scope_collection.py": (
        "83f038a2d15c10058bd53bcb2a05808453718bdcf9812cd51a5997b20477b3ad"
    ),
    "scripts/verification_scope_registry.py": (
        "4888eac445d23230783e4f062ae41a2684921b0450c05d19990993802187f83d"
    ),
    "scripts/verification_status.py": (
        "081a13f82706ebc16aee21138c40bcf6620ad8daeb8efa6338a1512f07edd1c5"
    ),
    "src/paper_radar/backup/__init__.py": (
        "b03e71f04496d78aceb9ab27b399945c72d4ac150db3a47f45e52a6696558078"
    ),
    "src/paper_radar/backup/cli.py": (
        "731e05af4659eefa8c52707516525e27244265ae0bdbd4a6a364228fda92d838"
    ),
    "src/paper_radar/backup/cli_support.py": (
        "08b5de8379ea9c357d7ed05c1d4a33f145d56066842e993a8cc0e7301dcb298e"
    ),
    "src/paper_radar/backup/files.py": (
        "8bf4f05fea2085b1e6b25bb0ae426db2c13da47aa314dd695a1cd5c5259d36b8"
    ),
    "src/paper_radar/backup/manifest.py": (
        "226157ce8d52ee9d6f0abea4936efb2fa95cdcd7c0519956b2656d46c6b19da2"
    ),
    "src/paper_radar/backup/restore.py": (
        "13d80b3ce3239dcc8159d02cc91ac50ac6abec1f526a8337b16fad8aba77b46f"
    ),
    "src/paper_radar/backup/restore_cli.py": (
        "d168d5159b481ac48fdeff10c2931052a490cb1eea58b784a8494ce2cf81b6e5"
    ),
    "src/paper_radar/backup/restore_contract.py": (
        "9f251dd2aa193d3a6908361fd813c184d6dbe605aec122a7cf0de0db9262bb13"
    ),
    "src/paper_radar/backup/service.py": (
        "ca0eccbe1b49772e9376172c489e129fef98743a79e12b566a2b6dad33534e4d"
    ),
    "src/paper_radar/cli.py": (
        "584d6560d20ddcd7ca6c8fe2f4a73e5b3fb43f2b2499cf5b96594ee6a7f4b50e"
    ),
    "src/paper_radar/config/__init__.py": (
        "183ae92cde48da098849568b1c84aef187d2487370e7117f1447a9f7e1af418b"
    ),
    "src/paper_radar/config/adapter_loading.py": (
        "8134aa6313a3566be651424db347408d6a0327e2ef1593493251b15cf915ddde"
    ),
    "src/paper_radar/config/adapters.py": (
        "09eba6119e74e25d50e493281d00c4ec978ce4e5e874bed7731d1822d92f1c3a"
    ),
    "src/paper_radar/config/cli.py": (
        "1bbec637e1017146c595f3aba6bf6b616e067bb20df48581b3d1ac28558c986f"
    ),
    "src/paper_radar/config/compile.py": (
        "6da7f52b929c3e0246fe97bee0cb209ef06be2c7d126f9d2cd8d735622c4268b"
    ),
    "src/paper_radar/config/diff.py": (
        "add553638b26d691e1f8ca7fb69261347a5dfff00b5b34288cf8f866f0810b5d"
    ),
    "src/paper_radar/config/errors.py": (
        "b758636b6e568235bbbc26e1b8c2b7e288a2ba30384b9572d43d4c7a387a5928"
    ),
    "src/paper_radar/config/escalation.py": (
        "086813af87547c24fce5b2940e6fb773b276a63f7ac880637311e3b24443d24d"
    ),
    "src/paper_radar/config/extraction.py": (
        "5e40614630817b84fc66aeed221cf65b0aee58012fe7e09148cc1f635bc36c4e"
    ),
    "src/paper_radar/config/extraction_models.py": (
        "a25c95e28eef976d63827959e87da3c09bd1124383bb05b298cb114156768c6b"
    ),
    "src/paper_radar/config/extraction_policy.py": (
        "5598e53bae6e90eeec8bbf5354013b3f8ae0e3291ab87cabef7310170fab0683"
    ),
    "src/paper_radar/config/extraction_toolchain.py": (
        "4f2ae67b03b4ed9d82aba434ca9e30de382804bd73e61217eb8b1559c1f97107"
    ),
    "src/paper_radar/config/identity.py": (
        "ed02a7920df6c7967c034fe06da3f0ee92e172163ba61fa6c2115db562d99a0e"
    ),
    "src/paper_radar/config/journals.py": (
        "8eeb3287a83bd0cfc8c7e7cd64b67b39cbf82b06fbfbd613cb4208f46b65060a"
    ),
    "src/paper_radar/config/material_assembly.py": (
        "5c9c63dd804b6cfe7b28da60ff8ac220d2fb36529ef42768de31e0dc05059482"
    ),
    "src/paper_radar/config/material_names.py": (
        "3b9d6d1317ceb2fcaf6f4a27a03a17a1489856009e18a853c7fa08c5204cc959"
    ),
    "src/paper_radar/config/projections.py": (
        "5e37e316066e22ca42ba46bb560f34d171b74fe7ebc1d108e98e4d8f91fc339a"
    ),
    "src/paper_radar/config/read.py": (
        "f6f3ae3d508ae3d7ecfeb34b22ca47d51990cb123f7047f9474d2487f0a15ae0"
    ),
    "src/paper_radar/config/readiness.py": (
        "5b948021ef13dcc628d56f1e6b9736292b0b121a7f07df7833a5e6f00a098b37"
    ),
    "src/paper_radar/config/schema.py": (
        "84b5cbcc527c5f291cba50bf4cf83aa652c94040a822d051968811541fb5fb7b"
    ),
    "src/paper_radar/config/service.py": (
        "4701cf2b828347671ed6ee939ee1f41743860989d3041331ed9ab37a78424aa9"
    ),
    "src/paper_radar/config/snapshot_cli.py": (
        "b6afba96f094800598419763ef8688bebbe59fd5125dd623e27b404169d19420"
    ),
    "src/paper_radar/config/snapshot_queries.py": (
        "6464b7693dfe69530eebf64db78849889481cd04c8e2f88c5d8838f0347de9e3"
    ),
    "src/paper_radar/config/snapshot_summary.py": (
        "a882ac057edcfded0b31fcb4c06a376590cdbb5e77c7bd058b22e81312b0b379"
    ),
    "src/paper_radar/config/topics.py": (
        "f69f0d0a87f8855ca3db9290c5602f40d34a6189b70cc6b63716626fca6a247a"
    ),
    "src/paper_radar/config/yaml_loader.py": (
        "6af6ec978e54f7e1d375017bf829eb17f850b492cc1802e1855bc096a9a1f815"
    ),
    "src/paper_radar/contracts/__init__.py": (
        "52628464b846a047162d2bf72be82e97fceb767a073834644e33a30f0dc08ec5"
    ),
    "src/paper_radar/contracts/check.py": (
        "7505cd6895e8e7c8ff201a49d8a7a7fa80d36ec1d8314bda95d0ed9a7cda110e"
    ),
    "src/paper_radar/contracts/errors.py": (
        "7aba91e43cd25c5141c9757fd0d0d0d5fb0679f687cf73bc5715b3a5650bf71e"
    ),
    "src/paper_radar/contracts/export.py": (
        "81f7b5fc17df7d89f7617ad5bf2ed79792f5bbda4af336c3aedba86e24f0299e"
    ),
    "src/paper_radar/contracts/schema.py": (
        "f128e20731ece97f672ce50d9fb760a240abcdbd02b9aae63e83f2849fb0dade"
    ),
    "src/paper_radar/contracts/snapshot.py": (
        "a52553e700aa7a06f69c45c90052ffb813db6319c90d4a9fd39173767af3b9d9"
    ),
    "src/paper_radar/llm/models.py": (
        "7f35d52f95900c67061d16c8fb5b6ec9707c676353b2bd2e0bc82c7d5d491742"
    ),
    "src/paper_radar/papers/__init__.py": (
        "2db5994c8f0a7b00bfd205a739e0f32e96b8769a75c185725335710c3c5fec36"
    ),
    "src/paper_radar/papers/cli.py": (
        "a733d4a91ca64608ec4638518373f2c9022d4d287ab9b6b8d92099ff2d455af2"
    ),
    "src/paper_radar/papers/doi.py": (
        "228846911cf806f424da4bbb155062f7b376249696d6625b74c80b6a421c2aee"
    ),
    "src/paper_radar/papers/errors.py": (
        "90764831f8e6c8040350b321110a4bbde46873cf8f7ed8c744bcf390be9d86e5"
    ),
    "src/paper_radar/papers/fact_reads.py": (
        "8e9672ea7217d4f08d692a4ef705ece3e5b5fe48759e39cac5cffefa79f6f603"
    ),
    "src/paper_radar/papers/feed.py": (
        "6212e6b0af9d1d41cf21dc59c85962adcf63402c1d5bb4d7edd9081f50a9722b"
    ),
    "src/paper_radar/papers/feed_queries.py": (
        "06da50e3656af7c30ec441471f623b40fc23fbabda5aa10ba619d8ff6459f522"
    ),
    "src/paper_radar/papers/feed_repository.py": (
        "2a0118675d0093b3cda3492159d2bc5e71d4bc101cc966498cb4afb620b527dc"
    ),
    "src/paper_radar/papers/manual.py": (
        "7a15cf6f464bff49396a710c1560cbde628ef69339f585ad88a56a16a9eecab2"
    ),
    "src/paper_radar/papers/mapping.py": (
        "aa588937228e31d2c8ffd58d565d4f13e08a4e619a89d598614e0284e075ee1e"
    ),
    "src/paper_radar/papers/mapping_models.py": (
        "c1770760154967b1e0d4c7090acb79d61ba4a7df379f16af459f3ee7393e5bde"
    ),
    "src/paper_radar/papers/models.py": (
        "d8803cbae6b3351a3ddbabcd37e0fc5f2a5ae59aa84f132b1c20431213047561"
    ),
    "src/paper_radar/papers/queries.py": (
        "87ec3ef5ebcab6ba48e53ee329957c834c520044cf1d5a90d834076c25db550e"
    ),
    "src/paper_radar/papers/read_checks.py": (
        "12bed5ba5d4e8b2d005da1e03745748265a3882d0f1b174f6c19b3d0a50ccce5"
    ),
    "src/paper_radar/papers/relation_repository.py": (
        "16136ddd024e00983128e00bc24af29f1270ea5ae855f10e6a4315b9e2e53115"
    ),
    "src/paper_radar/papers/relations.py": (
        "c286f4517b7d9b545a1b7446c2c333f65067c22b0850e46b5da1f2ec56ef3efa"
    ),
    "src/paper_radar/papers/repository.py": (
        "b251af530e1b9d23d4772d666a582a89de48db49b4dbdfa89b9bdc02df461473"
    ),
    "src/paper_radar/papers/rules.py": (
        "d6e8ff81e894d926c62c1c90dd1c8edb06cf01d7c50799ed8256ec38544952cf"
    ),
    "src/paper_radar/papers/selection_repository.py": (
        "27579c3eb0bedbbe90f7da5c5326904b6058023cf3fe1a7576a71afde4b9c7f1"
    ),
    "src/paper_radar/papers/service.py": (
        "04473effebe65c5ca44f6765d3d4c5b1d2fc9b7f176ac9e38a6cdfe51b8302f4"
    ),
    "src/paper_radar/papers/tables.py": (
        "b190ff9f7f1d0ded4bfa559246cd07e5fb8b47290e3c7a76a344c886a6311f21"
    ),
    "src/paper_radar/papers/text.py": (
        "4027bfb0b48648f79bdad68b2da3f818c89628a68aae1b06d468d52e898f355f"
    ),
    "src/paper_radar/papers/text_rules.py": (
        "9cebd0175cc0730bd65940339e8dd8d01402c5cbc635afb29641b2aced635e6f"
    ),
    "src/paper_radar/pi_supply/__init__.py": (
        "1c3892fcf511c98a6aa586db02a9153cb6df7bea24530cee1c5e4e152584320f"
    ),
    "src/paper_radar/pi_supply/cleanup.py": (
        "1ddbb2730d089ffd95cf867b2321f5f5883c030b23807b6d19a0413282de8170"
    ),
    "src/paper_radar/pi_supply/cleanup_delete.py": (
        "927c157458db770b0f74a0cc8856d50fa9027fc2d6c8bd4f66c74f37e977e20e"
    ),
    "src/paper_radar/pi_supply/cleanup_execute.py": (
        "c5a26ecd0e5646aa99f12add02f4e7a36447511a539a25ea82799c8e815355f6"
    ),
    "src/paper_radar/pi_supply/cleanup_history.py": (
        "302e864f0c51a8d343282f1ac566995e007aab6cce0191fed1d239f9c057240e"
    ),
    "src/paper_radar/pi_supply/cleanup_models.py": (
        "79d07bb9aea0a0aeb568f050eab1ef261d5db1aec6f44ed283d136f36bdbd392"
    ),
    "src/paper_radar/pi_supply/cli.py": (
        "fdb7dc415f7dffd77689bcd236003222ab114cbb946c9de3a69c2596c50ae1f5"
    ),
    "src/paper_radar/pi_supply/errors.py": (
        "be0cb07450ba8ddd01e534683e079357146261886e85e3402b99893010cd7754"
    ),
    "src/paper_radar/pi_supply/execution.py": (
        "d3e4c2e1733d1304879b46c0431c64a0a2612505f626946cea8738d40b01b4fb"
    ),
    "src/paper_radar/pi_supply/export.py": (
        "c54f8391c6f8c3761d40992aa5798747642cee56829dcbde473302bf6ea3136b"
    ),
    "src/paper_radar/pi_supply/filesystem.py": (
        "350548b02c318fd48561c635a3da270330a23e24f500c06f7886c1700b3abc56"
    ),
    "src/paper_radar/pi_supply/materials.py": (
        "51aca4864e1aadfed9b13dc0cf2577adb95816c4f1a460a6302f6aecb5566d8e"
    ),
    "src/paper_radar/pi_supply/models.py": (
        "3c9d16b75ec97f448e743d4dbccb5c1164021a1d13126f039040513f9fd07afd"
    ),
    "src/paper_radar/pi_supply/protection.py": (
        "515c62247f5bcb989b72a1c2a7a846747ffe5be4f77488adfc237492e9ee436b"
    ),
    "src/paper_radar/pi_supply/repository.py": (
        "8e989a1df579c0892957b8f5fa0f119cf3719874e7a88000a647a43a70ef5464"
    ),
    "src/paper_radar/pi_supply/retention.py": (
        "ef7d2b59419d15865be23903209666b242397b5c68bb10201266cb205c0f79e0"
    ),
    "src/paper_radar/pi_supply/selection.py": (
        "00f6ec83a2b0960b10d64130ae80f0b5a9536a7cecf079abf065e149231068e4"
    ),
    "src/paper_radar/pi_supply/service.py": (
        "e1d6d8641e334685f5371c62e78f1183100a263749bee2b449886ce008479155"
    ),
    "src/paper_radar/pi_supply/source_policy.py": (
        "075b43a8c4d6e1599ebc60458448ecd137f6d028d24be67665d0409e2a262d97"
    ),
    "src/paper_radar/pi_supply/tables.py": (
        "28128ae4e40986d804a6ef2b1eb862965b2e13f1282d81cb70acf24022003a29"
    ),
    "src/paper_radar/pi_supply/transport.py": (
        "cc15d6982ed610a0248a987af6f9faf94743226a71a9f2194224c2d98129c437"
    ),
    "src/paper_radar/reading/__init__.py": (
        "46abc1b703683085ac1b770f0a431304f2784117daff97656e97e7a04e6cb2d4"
    ),
    "src/paper_radar/reading/context.py": (
        "0f6965c0e82b8b2617ff8427c4e3bb3686910c50029378604df09745a51c6094"
    ),
    "src/paper_radar/reading/diagnostics.py": (
        "5776997b330ac4b41fb93ccb98e50302c47feb8f250e91151bc086c27fcea576"
    ),
    "src/paper_radar/reading/errors.py": (
        "8cb6363f973b754b944d3246cb370b3ade43cff8c8ab4f99723e941dc445f50c"
    ),
    "src/paper_radar/reading/numbers.py": (
        "01dc3d2c77472721393a61b3814748c69cdc64c2cb229fc4e47aeb60c9137e5b"
    ),
    "src/paper_radar/reading/parsing.py": (
        "420422b425f9de9cb9d521f4e10bf1f560c06e8f0f5536c4b0ee875072cf24d5"
    ),
    "src/paper_radar/reading/result.py": (
        "e7ad472d2e0676962ef102412923822533c86b222cb1f494b76a877134e294f4"
    ),
    "src/paper_radar/reading/schema.py": (
        "db248a1fa6d0efe848b9e68abfc01e8f988e659a77b5b8e61a1a8235a088b316"
    ),
    "src/paper_radar/reading/validation.py": (
        "82885031c53814fd2775e7aa09bd3be51333afaeb870b19caca4ab443d9c0eb6"
    ),
    "src/paper_radar/reading/value_types.py": (
        "2920ca5f14fba6eba36b7a4b3fd17419bcd611896b762ada4c99249219684ec4"
    ),
    "src/paper_radar/screening/__init__.py": (
        "930c9c05dcd3067898c50b4e3250a816e89c0408504e0b77936a27f97a702b2c"
    ),
    "src/paper_radar/screening/context.py": (
        "a2ab562750e3e68e42facdfddd71922c14a9ecfe1d0af8e44d3081383f86ef37"
    ),
    "src/paper_radar/screening/errors.py": (
        "9f03054ed7de9aae6093914f9de230b961020928bf441e7e25935bf7b3a551a1"
    ),
    "src/paper_radar/screening/schema.py": (
        "3d741ca3876d24fa37df7cb48569b4193fd7c6d24adf47e68e29aa39400635e1"
    ),
    "src/paper_radar/screening/text.py": (
        "77e4ad599a2edbbaf30aa2f134918130f2c630fcc74abb9068190614c0f3cff1"
    ),
    "src/paper_radar/screening/validation.py": (
        "63d26b9b7b5593bb3260a37aacef1d537fa7736f7bbbf7ef25b9198bab17fc62"
    ),
    "src/paper_radar/screening/value_types.py": (
        "7a6d1be2b56745e15d074575b7cc4f9f9ae0e4fed3a8409cf098fac0751b5b85"
    ),
    "src/paper_radar/screening_tasks/__init__.py": (
        "dc13d29177723406c86a03b062ed898b849d798b374b6e8f8a8c4471af49a71d"
    ),
    "src/paper_radar/screening_tasks/attempt_integrity.py": (
        "a1cc83d965132feab740fcc6ebb4302e349166db1ed9f17c98630b33b5a4c0fc"
    ),
    "src/paper_radar/screening_tasks/attempt_models.py": (
        "f2d8bdc4b5a194fda4bc114a63b6717f8d5e71ac14ec0b24459e177b78d77176"
    ),
    "src/paper_radar/screening_tasks/attempt_repository.py": (
        "19d7826a918be7c6ccca2a7412efc04a566aaf1e46b392b3d3b282c350f4faf7"
    ),
    "src/paper_radar/screening_tasks/attempt_rules.py": (
        "23bedeed3bcf6d258ba326c5a08307f8c389b8d90cc3aac3a10586a0052c6dbf"
    ),
    "src/paper_radar/screening_tasks/database_errors.py": (
        "433e727d768e8281fe69fe48cff91eb861e59572b26ae839ed743872547c6630"
    ),
    "src/paper_radar/screening_tasks/errors.py": (
        "6b9fb832adb19ce2394f26c19610e8b6eb0860fa47ae46af55de06163a732970"
    ),
    "src/paper_radar/screening_tasks/execution.py": (
        "cd56a05f6766aad76f0ea723069a8015f863c15d8b1a8b1a7b4ac3fc828559bd"
    ),
    "src/paper_radar/screening_tasks/frozen.py": (
        "1feeec54b063c149788086812cac02ae148004a496ef9a79cc04b5903842438a"
    ),
    "src/paper_radar/screening_tasks/integrity.py": (
        "83bc3d0f53d44ae1c4ee61b2b3173230bd2e96fa91f568c46d995610b89897eb"
    ),
    "src/paper_radar/screening_tasks/models.py": (
        "42c24b28d5d53d4a748ef2bb8d9948348acf83b8470e26e56aa37f11bcafb249"
    ),
    "src/paper_radar/screening_tasks/query.py": (
        "8a5a4c8f07e58e5f3c7414d7cc186788fa3bf13fb8297ff8d1759734aa5605cd"
    ),
    "src/paper_radar/screening_tasks/query_models.py": (
        "a771cf0bc91a6cc4ee961c2c85ebca8b7c7a4f38eaa8e6f64b58e3d3b15f2ad2"
    ),
    "src/paper_radar/screening_tasks/repository.py": (
        "1d72dd519cc8f7ea1a734fc1df0686054ab07351a270e13cb2da30046479cd1c"
    ),
    "src/paper_radar/screening_tasks/retry.py": (
        "7723a0e6cb209215860e7bfff74a8fd2b5e060884045492f9a8a1966be885052"
    ),
    "src/paper_radar/screening_tasks/rules.py": (
        "ad6e02377fbc3cc965a2644a36c8321324a036e63d493232b387566cd3a3a4bd"
    ),
    "src/paper_radar/screening_tasks/service.py": (
        "6e335461c25f4bf01eefa72ab9dec4fa76e7a5a4a64e9e32e8ed234ea7e512d8"
    ),
    "src/paper_radar/screening_tasks/success.py": (
        "ecd723373feb614d3dced2d8c9de09776f42141cb95b2269888e240f6e4eab92"
    ),
    "src/paper_radar/screening_tasks/success_integrity.py": (
        "1ee3ca56fddb35cc64bcc12972eefa89fe3e5361d323435bb2927bb288729770"
    ),
    "src/paper_radar/screening_tasks/success_models.py": (
        "45aa125007f447a348210d4d4b1183240565022ac54bda0f8fae80e68efba9e9"
    ),
    "src/paper_radar/screening_tasks/success_rules.py": (
        "a9a98780f94e9a11bb53bf0f3c26aaac95b19e6912b3ca5d5a182af5e92882a3"
    ),
    "src/paper_radar/screening_tasks/tables.py": (
        "fdd3045c423fa2609bee7303192443d24c020cf36c54cba50710e2cc167b0f51"
    ),
    "src/paper_radar/stage_inputs/__init__.py": (
        "d3a77ae4330d0821ddf84ed6b9f02830292f5b3ba678c69faa48e2bfc7611a87"
    ),
    "src/paper_radar/stage_inputs/service.py": (
        "d2dc724da98760240b6fa95e09619b2ca435e506c68a221976ae8c3ffba382da"
    ),
    "src/paper_radar/storage/__init__.py": (
        "52dd2406b588ddb72767d4621f5bddc12d8b68425e049b562574ca9c1789b236"
    ),
    "src/paper_radar/storage/artifact_contract.py": (
        "ab8284b17b5710fe9e537f6edb88fff7fc84f686417f96e3558405699f1fa999"
    ),
    "src/paper_radar/storage/artifact_repository.py": (
        "e81d40c7330f4a2676524ead4c59bea4c263d81b447deeb32403c0599e7d222b"
    ),
    "src/paper_radar/storage/artifacts.py": (
        "a30949836fd65485df2b3fc477b1027b7deddb405edd90bc4f29c297ade333f5"
    ),
    "src/paper_radar/storage/blob_store.py": (
        "3664854101b7d4e1612118a9dafa2320a879ca48e9ae9273c05c56821662d8e6"
    ),
    "src/paper_radar/storage/database.py": (
        "ed8aba07f31eb6019c6d656a9147c682d74073bbdf4d268cd488bdb79ff3b7b1"
    ),
    "src/paper_radar/storage/errors.py": (
        "a8c859bb0d8a415599887d380218a46490c6e10afa9910c0360a4dda037db19f"
    ),
    "src/paper_radar/storage/filesystem.py": (
        "b0904b630bb476eb4a7286ec9b6623176e83549be8c0a33faec7e29a1480e91e"
    ),
    "src/paper_radar/storage/migrations/env.py": (
        "f22dfaeade1105d7eb46dda731916406fe521051ec0a76b7eeb1e915d42ffd27"
    ),
    "src/paper_radar/storage/migrations/versions/a201_profile_snapshot.py": (
        "a19059f3143dd9d05e550bfd77f7d89f75bc43a23636ba375d4ac7d4ea2c3039"
    ),
    "src/paper_radar/storage/migrations/versions/a302_artifact_store.py": (
        "0f15648cd3a8fc8cbe8938f1890894cfcba801643aff4204826910b35db88610"
    ),
    "src/paper_radar/storage/migrations/versions/a401_pi_supply.py": (
        "056ee1f2d83aa14ccd6cb28fc2b6ba735244a2378697bea040050560ed60abd8"
    ),
    "src/paper_radar/storage/migrations/versions/a402_pi_rebuild_failures.py": (
        "1ffc04c4498325773f773689beadd0b1568254cfcf6a2752760126aabbdd720e"
    ),
    "src/paper_radar/storage/migrations/versions/a403_pi_activation.py": (
        "56c2a029b67c5868e5e5b92e79c54b14eabb8b88b1cf87d67fb794e080d0d2a9"
    ),
    "src/paper_radar/storage/migrations/versions/a404_pi_cleanup_plans.py": (
        "75b091d3d071aded348fdb71ff7a4505bf87adcff900e38770c254d08f712470"
    ),
    "src/paper_radar/storage/migrations/versions/a405_pi_cleanup_execution.py": (
        "2ed24cd0458ad34e2b6f1b681e2a1826c1ed41228d6223939fc4528306dc8eed"
    ),
    "src/paper_radar/storage/migrations/versions/a601_paper_facts.py": (
        "c5fcf3d84b03619f79c6720fd5aad83df7af6ac884c00d1ed5a161b286ad056d"
    ),
    "src/paper_radar/storage/migrations/versions/a602_feed_discovery.py": (
        "94cee1dfaa7879a3ed54633a45c7fcfa3da6fc78947075c62a2c049ac4a5d513"
    ),
    "src/paper_radar/storage/migrations/versions/a603_source_arbitration.py": (
        "e7f62ecd51ac4b4dadb18bd8e8fa55f60e293e05dd88e3bfeeb0c42c4740a9ab"
    ),
    "src/paper_radar/storage/migrations/versions/a604_version_relations.py": (
        "223a7e931d9350f8c42eaaa64ce3204fe9a7ae612c4415e7af326e3041064b9c"
    ),
    "src/paper_radar/storage/migrations/versions/a701_screening_registration.py": (
        "7040fc993c9a8921dd81e3059a5a92e9d0817fe4fa743d5a3aff82461c469d8f"
    ),
    "src/paper_radar/storage/migrations/versions/a702_screening_attempts.py": (
        "d7ceb107d15d4e22b51b375fa2b13493e79e8e16f902bce2ca618d46f28671a2"
    ),
    "src/paper_radar/storage/migrations/versions/a703_screening_success.py": (
        "0f9d61d04cba04a658c4a928394431dff93a75abe13e38f437d20ec19feba9fe"
    ),
    "src/paper_radar/storage/migrations/versions/a704_screening_retry.py": (
        "720b73887f1ef6d048f645e5043fd421a00052951ee3b7b16441714694a55d8b"
    ),
    "src/paper_radar/storage/records.py": (
        "f1e5e7d9ca146fc8439ed8966d6bb3576e838ed7494d831772131731601094ca"
    ),
    "src/paper_radar/storage/repository.py": (
        "91a48152f1f2fdd840471f81c6db13ca87dc533a8ce4fa03f5b396b08019f5bf"
    ),
    "src/paper_radar/storage/schema.py": (
        "291db5e419f3a5a7fd88afab7f369569d0b8e754fa36932210418c0938050a0f"
    ),
    "src/paper_radar/storage/snapshot_queries.py": (
        "e394fb3bbc2e70e5bc92f4c539481e7d9660c026f60d709ef990763022f6acf1"
    ),
    "tests/a2_full_support.py": (
        "c330fadfc4ce9c0cd902b61c126fa6c8580aebf3ebdbb856e2c3ea3d72a3e0e2"
    ),
    "tests/a3_acceptance_support.py": (
        "d89e4dff6834d19562ffd9a3a5fde14c353962ee67a8c1df21113c75979b2545"
    ),
    "tests/a3_process_support.py": (
        "4c0ca963d2513532060c5f122f92b09933e234c4c65e342b78d3fd5d06880d74"
    ),
    "tests/a4_acceptance_support.py": (
        "3e7457b20e193b1076b67c3d8394dcb0b9eebb60fcdc58d3abe44be4d50740cf"
    ),
    "tests/a5_acceptance_support.py": (
        "528ab9bd6e1a71767083eb514378e028420691d0c61a81237cab85163b2ab1f5"
    ),
    "tests/a6_acceptance_support.py": (
        "b6642636b0e57bb76e4bcbbe94a540e7239075ab5d6872a01e04ad046a4f28a9"
    ),
    "tests/a7_acceptance_support.py": (
        "3d9de027d1d9c1a6ffbab594bafb40abdaccb3e8e67297a7b8371ad1021c048d"
    ),
    "tests/a7_registration_support.py": (
        "fb2a8b308364e85acd7bcf3bfa7fe80dff613f28988c6c59f891497c781a09d5"
    ),
    "tests/a7_retry_support.py": (
        "ecd292a60410fe31f243d9ce2a466575b01774ac9c5cfe56f9cc6f135f2a2b81"
    ),
    "tests/a7_value_support.py": (
        "6165a17b98609bd0611cd27d80f09aaf165a8df9e08ad9a2808767b79f324404"
    ),
    "tests/a8_acceptance_support.py": (
        "2bc2b90eaa623493b9b4b2ac449d72e8b6e82e0790893146103abada5e2e64fe"
    ),
    "tests/a9_acceptance_support.py": (
        "475e1413ca1779429e1955c7c0f23fbc96af10989e38302e282e1c83a620b3db"
    ),
    "tests/artifact_support.py": (
        "2771734fb913cb279be6aa9b9518b7d7e2bf70e2b7982f28e47b78be89000664"
    ),
    "tests/backup_support.py": (
        "f1ee3e3febb10bcf68212af621c79d0d25951fa1464cd11e23d2afe139e8cc37"
    ),
    "tests/config_adapter_support.py": (
        "04e71ec7c1a888844a7b55c3a1fe8d2dc3445866f08f3fa8f9481ff5b8a345ce"
    ),
    "tests/config_extraction_support.py": (
        "7798711c15be510330d405d7dcef6cc8110214498c6a50b04c454a3d696097d9"
    ),
    "tests/config_journals_support.py": (
        "639ea499a5d41e3f914c4c1ba36aeff9a6c3502204f0303fc9c76f893dd508bc"
    ),
    "tests/config_projection_support.py": (
        "1a3aa9a7ce2535a9a52c3fde9dc18cde964d1de8b89654e3d50e566aae79ef2a"
    ),
    "tests/config_read_support.py": (
        "e7f862a6959c56301046f18a57cb1524262c5e3e321797b6c00f04e5ff8fbf95"
    ),
    "tests/config_reuse_support.py": (
        "b9f576eb2a4ae3eead274caae1b0de6c63fea30cd65c2f1188c0ba41f450b91d"
    ),
    "tests/config_snapshot_support.py": (
        "454ac40c3cdcb4846ffce9e59dc3e9b075f21100aa9bf0ca952457b19690632b"
    ),
    "tests/config_test_support.py": (
        "1bdd4ec7d1c3a3c2274455cfe184ea5ee7d58971d65adc1ccd532a55c295e840"
    ),
    "tests/config_transaction_support.py": (
        "b34d3a45de0d377f3a78db7d6ceed20ec2616ad36eecdfb7257f0d20a80c1ef7"
    ),
    "tests/deny_external_io/sitecustomize.py": (
        "f0148752ef89a004fcf76048cbc1f070448152683921b6d9d7c452d102a2d48d"
    ),
    "tests/deny_network/sitecustomize.py": (
        "dfce12fb68aaefd9b19ec26f1ff6bfb10b3f726fdafe6f466ec031cc2acc3288"
    ),
    "tests/feed_support.py": (
        "db26ee02a0164e43f116a5d73f5acdd58946f897ac4c2be063722437dd5814a8"
    ),
    "tests/fixtures/verification_transcripts.json": (
        "f746f0dc76acbfb01e2f8f488e49f5db796c0793f425ccb1f76e95c341dcb16a"
    ),
    "tests/paper_recovery_reader.py": (
        "5d88105fbf62502c5a36453a4e1f07b21ffe75a29f1207b4c138ab42ee690ec7"
    ),
    "tests/paper_recovery_support.py": (
        "1ed06b37d511b6b0ca319067737b2d0b629bb7e7efc542a34cccb579d77066ad"
    ),
    "tests/pi_supply_support.py": (
        "083385f8ae08954ae8b02b454704d04700181a443a0878104ae7ad52ada6e479"
    ),
    "tests/restore_support.py": (
        "0ab9a716354d3c7481596a59e2ea20aac453de1602bc88712f119f1bab726736"
    ),
    "tests/test_a1_acceptance.py": (
        "e2bada5b0eb60926426009400ec44dcb9d85a09152f22880f8c3dc8ac0fd966a"
    ),
    "tests/test_a2_acceptance.py": (
        "956c3c35606751d97b01057df5d53c8d00ddcc2a44c0865263a9c4352c54e0c7"
    ),
    "tests/test_a2_full_acceptance.py": (
        "a6aa253c1a3547b56ce734308d16eb96be90266f79115986a86c43bb356148f6"
    ),
    "tests/test_a2_full_entry.py": (
        "5a69ed6cce68efb123ae78c8f35e305d87efa5079a08ce0c09eadd0b26415c53"
    ),
    "tests/test_a7_complete_recovery.py": (
        "864129b5025fb14319a2ef3a61d9386b66d86444fce8a9904425e9d6e3280d7a"
    ),
    "tests/test_boundary_validation.py": (
        "6326cc77cc74bd53077e5d4c1ce78f41355af4b5b5c2ebfd9c03907d9a9cfd7f"
    ),
    "tests/test_cli_help.py": (
        "c03c70471575a50a82ae68bca7fea6c5bf3f885921fbac626403f2ce133e4ff4"
    ),
    "tests/test_config_architecture.py": (
        "9b70e25d85fa0d1368f8d46d912dc14ec059f499c93139d5c95fdd1c43edde20"
    ),
    "tests/test_config_cli.py": (
        "23d07fffec126cdf8a0af7bd5f3ddbabc5f07a0ba3f1d32f7152594d0f0f6ad0"
    ),
    "tests/test_config_service.py": (
        "bbd817eb48f02893999a2a5e5c1c1522d182ea307cb08fb6460c5198ca352e38"
    ),
    "tests/test_config_snapshot_architecture.py": (
        "30b7f1779cc500793fb1920b21c2016e118c395df4d7e13504f49f4bf1e84e49"
    ),
    "tests/test_config_snapshot_cli.py": (
        "d12f1f17109d8695d189b7de8c89fece870a54fb60da42e1b3811d8432db3f37"
    ),
    "tests/test_config_snapshot_queries.py": (
        "69b042430c90b1245a366c333aa69fb384b792ac9eaf36e039e30315501c478c"
    ),
    "tests/test_config_validation.py": (
        "ab38e647e40cc03ff138fa7dbf1676f0ab5bb6758d7556d303f5053628344840"
    ),
    "tests/test_contract_check.py": (
        "35cb36600af73aca3bba4c52bcc2f83a92fe9f36f497f656a44c5394f6a962ae"
    ),
    "tests/test_contract_cli.py": (
        "84b86b8017b4cc94da95311409257fd1fc4ff575f840e3eef90c546893d59eaf"
    ),
    "tests/test_contract_export.py": (
        "49dca04977690856bb2e8a14b9acc063d54e3e26182174b6c2164ac7f0e41f9f"
    ),
    "tests/test_contract_schema.py": (
        "9471333e0ab7df64fa135b2587b289059ca935fd45b53e4cc81d173ab931eb9a"
    ),
    "tests/test_decision_reason_validation.py": (
        "2e0a578ec6daf5877dc64362c8b3a705733b8e742beedb1702488a02e2f0e19d"
    ),
    "tests/test_manual_corrections.py": (
        "ddd5b955b9654de8945518a2d0e4229544104bca3f3d2f79fa16f601c475a77a"
    ),
    "tests/test_offline_evidence.py": (
        "843308e18b62b0115ba149fc8ad6db1db15a5d01679086e91802b5f153dc5d49"
    ),
    "tests/test_paper_mapping.py": (
        "8cf3de3591cbc9b2a19cccc8ac93ea9a16909e44121a32f231838b045f956ea0"
    ),
    "tests/test_paper_service.py": (
        "b0517a8a0058e544258a2f1b130ec3f1d05fcee8b495b8ea35b7409bc8efc6c2"
    ),
    "tests/test_reuse_assessment_validation.py": (
        "eae721185b7a2405b422865feb4370f81bb2aa2608343be9f23f9e914d8bcc07"
    ),
    "tests/test_screening_architecture.py": (
        "459eab67c1077008eb5609f3f7dd21b73e7e8e6b32c9672c54ed3826c113834c"
    ),
    "tests/test_value_prediction_validation.py": (
        "e9bdc89448a22638f3632639f120bcf689a7f93c4d8e80279e2c73a5dafdc173"
    ),
    "tests/test_verification_compatibility.py": (
        "6ea10dc52c601ad5f690adfcd96e2c780cd3ce94c3f25b43ba5fb2b6a6effdbf"
    ),
    "tests/test_verification_integrity.py": (
        "12b2eae45e2652bad29129895b782b5dfca3436a945b74291b61bb5f2d4bde29"
    ),
    "tests/test_verification_run.py": (
        "ba22149fcd05095563ce364260b452d59c9ca3d8400f2fd0a18dc525e64f8aed"
    ),
    "tests/test_version_relations.py": (
        "069aa10cc4cb66405e0f093e00b0503bda09200563113ebfaedbf7230805c74e"
    ),
    "scripts/verification_groups.py": (
        "b970c3857a0809b1f2d970efcfa4c93ed30a8477038944eaf18f105753e5264f"
    ),
    "tests/verification_expectations.py": (
        "f8717737f642b84b10ed600e47348a41e667612374c1989cbe24730e1e7e6f78"
    ),
    "tests/fixtures/verification_group_expectations.json": (
        "99068638177887123b22bdee65f0843e41492dc746ced8e5c3e73f266f4dc7e8"
    ),
}
