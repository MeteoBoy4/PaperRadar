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
        "26422479dbc776ebbce3622b8d79a1973d6d9b67d756992256c8988de597ad71",
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
        "4eec768c780dc5959233870bebd54a3a248ec1215e2292e26c64c1afe522d67b",
    ),
    (
        "src/paper_radar/config/cli.py",
        "730c44c29c442dddd763ed1feae70a1f6ad7a31a9b62e295478371e53fff011c",
    ),
    (
        "src/paper_radar/config/compile.py",
        "31ad130c39199f25a7f29302da36e47e0d5ca40202503726b0949c7d9bb89464",
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
        "af7a01153b0c351f5329c3e0c95d11559122293ecb75c7b170a7e86ee2ca6bcc",
    ),
    (
        "src/paper_radar/config/service.py",
        "45f44acee254d8aab679dd86ec5d466285484cddbbd10e5059c794c41e91dc3e",
    ),
    (
        "src/paper_radar/config/yaml_loader.py",
        "675f759157a32a9eef4d42d2c24dca15e2e14deaf82e501bdd22dd351ef05f02",
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
        "565ef8859f1823856d9bf31fcd995a59a55e9a8854ef1d8740e830944faae7ae",
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
    "topics",
    "journals",
    "models",
    "prompts",
    "frozen_contract_selection",
    "escalation",
    "extraction",
    "stage_config_projections",
    "calibration_baseline",
    "config_diff",
    "stage_input_fingerprints",
    "automatic_fulltext_reading",
)
