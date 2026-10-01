"""Issue #16 的固定 A2-01 离线验收范围。"""

from __future__ import annotations

SCOPE = "a2_01_profile_runtime_config_snapshots"
ISSUE = 16
SNAPSHOT_FORMAT_VERSION = 1
MIGRATION_REVISION = "a201_profile_snapshot"

# 哈希在完成本票改动后固定。预期值不能从被检查文件动态生成。
REQUIRED_TEST_MODULES: tuple[tuple[str, str], ...] = (
    (
        "tests/test_config_service.py",
        "ccd7cea316e16348e14bcea400d392568954d5377b5f6a8a5bc36a0c4cad2d98",
    ),
    (
        "tests/test_config_validation.py",
        "ab38e647e40cc03ff138fa7dbf1676f0ab5bb6758d7556d303f5053628344840",
    ),
    (
        "tests/test_config_cli.py",
        "23d07fffec126cdf8a0af7bd5f3ddbabc5f07a0ba3f1d32f7152594d0f0f6ad0",
    ),
    (
        "tests/test_config_architecture.py",
        "9b70e25d85fa0d1368f8d46d912dc14ec059f499c93139d5c95fdd1c43edde20",
    ),
    (
        "tests/test_a2_acceptance.py",
        "b62393bd8e9b906b06feae75e5cc25ad4a8dae7dd712d5248a3eb52340f95743",
    ),
)

REQUIRED_SOURCE_MODULES: tuple[tuple[str, str], ...] = (
    (
        "src/paper_radar/cli.py",
        "4ce1b5a1ba1c01f3062518cc4eb958b720ee627393351233070e065cabcec421",
    ),
    (
        "src/paper_radar/config/__init__.py",
        "4866143ead3b81562409473ce6ad6eaf11a742f7975e0f0d7ff2e1683b984508",
    ),
    (
        "src/paper_radar/config/cli.py",
        "f03944fd58def271f55478b46c363a59d30b82d03171a9df60e3bb45cc36b736",
    ),
    (
        "src/paper_radar/config/compile.py",
        "dbc44d01404f758ccd920440394fd3d57b8012b93d296d53530076caba250934",
    ),
    (
        "src/paper_radar/config/escalation.py",
        "086813af87547c24fce5b2940e6fb773b276a63f7ac880637311e3b24443d24d",
    ),
    (
        "src/paper_radar/config/errors.py",
        "5dbd3f610deafad69a775d389ff1ac3f108550c70dcb611ee107a28de755330f",
    ),
    (
        "src/paper_radar/config/identity.py",
        "ed02a7920df6c7967c034fe06da3f0ee92e172163ba61fa6c2115db562d99a0e",
    ),
    (
        "src/paper_radar/config/schema.py",
        "7f87ac6aaefd748e13ce3597be615e42d2a3aaeef82bf8f4798b263ca4d65e45",
    ),
    (
        "src/paper_radar/config/service.py",
        "38479b8b5a2c1f26ce9434ad17d2dd4d8ea98dc5dce08aa6947f5f45e1adaf19",
    ),
    (
        "src/paper_radar/config/topics.py",
        "f69f0d0a87f8855ca3db9290c5602f40d34a6189b70cc6b63716626fca6a247a",
    ),
    (
        "src/paper_radar/config/yaml_loader.py",
        "cfc0109c3543bd6a1f92c274bc1442da4100edaedf4e3aacdd2ca3eba38ab224",
    ),
    (
        "src/paper_radar/storage/database.py",
        "a39818047f903ebc7674d0f49ed28f4167068c695f7cb1c47fd694cf94de5793",
    ),
    (
        "src/paper_radar/storage/errors.py",
        "de9f19854cb3d4e58a2bd6f6eeeb6f4afff68e9cea4e4896474c9f9389d1c0d3",
    ),
    (
        "src/paper_radar/storage/records.py",
        "f1e5e7d9ca146fc8439ed8966d6bb3576e838ed7494d831772131731601094ca",
    ),
    (
        "src/paper_radar/storage/repository.py",
        "a964954d9b0ea152beb411145c88d21dd8c2149319d77bd48601a271dba98765",
    ),
    (
        "src/paper_radar/storage/schema.py",
        "a6da0e4436a89a4cea105ef7fb3647cb342afcf107aa41ffe7258e1f528d6353",
    ),
    (
        "src/paper_radar/storage/migrations/env.py",
        "f22dfaeade1105d7eb46dda731916406fe521051ec0a76b7eeb1e915d42ffd27",
    ),
    (
        "src/paper_radar/storage/migrations/versions/a201_profile_snapshot.py",
        "a19059f3143dd9d05e550bfd77f7d89f75bc43a23636ba375d4ac7d4ea2c3039",
    ),
    (
        "tests/config_reuse_support.py",
        "b9f576eb2a4ae3eead274caae1b0de6c63fea30cd65c2f1188c0ba41f450b91d",
    ),
    (
        "tests/config_test_support.py",
        "1bdd4ec7d1c3a3c2274455cfe184ea5ee7d58971d65adc1ccd532a55c295e840",
    ),
    (
        "tests/deny_network/sitecustomize.py",
        "dfce12fb68aaefd9b19ec26f1ff6bfb10b3f726fdafe6f466ec031cc2acc3288",
    ),
    (
        "scripts/check-offline",
        "7495bddfdeda7115808bc8fd2bb13325a12bd9c772778fa12825fe76f8993132",
    ),
    (
        "scripts/a2_acceptance.py",
        "bf1bf762bdd8f44c679e429c37afb6e989ab821dd7771e3aee5e8919afbfc85b",
    ),
)

REQUIRED_DEPENDENCIES = ("alembic", "SQLAlchemy", "PyYAML")

NOT_IMPLEMENTED = (
    "journals",
    "prompts_reading",
    "extraction",
    "stage_config_projections",
    "calibration_baseline",
    "config_diff",
    "stage_input_fingerprints",
    "automatic_fulltext_reading",
)
