"""Pi 配置只接受固定策略与受控资源。错误不回显输入。"""

from pathlib import Path

import pytest

from paper_radar.config import ConfigError, check_config, compile_config
from tests.config_adapter_support import adapter_inputs


@pytest.mark.parametrize(
    "extra",
    [
        "unknown: PRIVATE_MARKER\n",
        "token: PRIVATE_MARKER\n",
        "api_key: PRIVATE_MARKER\n",
        "credentials: PRIVATE_MARKER\n",
        "provider: PRIVATE_MARKER\n",
        "model: PRIVATE_MARKER\n",
        "protocol: prompt_only\n",
        "temperature: 0.5\n",
        "top_p: 0.5\n",
        "timeout: 10\n",
        "memory: 100\n",
        "command: PRIVATE_MARKER\n",
        "args: [PRIVATE_MARKER]\n",
        "attempt_budget: 10\n",
        "thinking_level: PRIVATE_MARKER\n",  # 重复键
    ],
)
def test_unknown_duplicate_and_execution_fields_are_rejected_without_leak(
    tmp_path: Path, extra: str
) -> None:
    settings, path, db = adapter_inputs(tmp_path)
    path.write_text(path.read_text() + extra)
    for service in (check_config, compile_config):
        with pytest.raises(ConfigError) as error:
            service(settings, db)
        assert "PRIVATE_MARKER" not in str(error.value)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("version: pi-v1", "version: pi-v2"),
        ("pi_version: 1.1.0", "pi_version: latest"),
        ("pi_version: 1.1.0", "pi_version: 1.0"),
        ("adapter_version: transport-v1", "adapter_version: ../outside"),
        ("thinking_level: low", "thinking_level: false"),
        ("thinking_level: low", "thinking_level: PRIVATE_MARKER"),
        ("resources:", "resources: null\nunused:"),
        ("version: v1", "name: PRIVATE_MARKER\n    version: v1"),
        ("version: v1", "kind: extension\n    version: v1"),
        ("version: v1", "version: null"),
        ("version: v1", "version: ../outside"),
        ("version: v1", "version: absent"),
        ("resources:", "resources: []\nunused:"),
        ("thinking_level: low", "backend: other\nthinking_level: low"),
    ],
)
def test_invalid_types_dangling_versions_and_resources_are_rejected(
    tmp_path: Path, before: str, after: str
) -> None:
    settings, path, db = adapter_inputs(tmp_path)
    path.write_text(path.read_text().replace(before, after))
    with pytest.raises(ConfigError) as error:
        compile_config(settings, db)
    assert "PRIVATE_MARKER" not in str(error.value)


@pytest.mark.parametrize(
    "field",
    [
        "version",
        "session",
        "agent_retry",
        "provider_retry",
        "compaction",
        "summarization",
        "session_persistence",
        "resource_discovery",
        "extra_model_turns",
        "mcp",
        "tools",
    ],
)
def test_every_v1_policy_constraint_is_fixed(tmp_path: Path, field: str) -> None:
    settings, path, db = adapter_inputs(tmp_path)
    value = "[bash]" if field == "tools" else "PRIVATE_MARKER"
    path.write_text(path.read_text() + f"policy:\n  {field}: {value}\n")
    with pytest.raises(ConfigError, match=f"adapter.policy.{field}") as error:
        check_config(settings, db)
    assert "PRIVATE_MARKER" not in str(error.value)


@pytest.mark.parametrize("slot", ["screening", "reuse_assessment", "reading"])
@pytest.mark.parametrize("protocol", ["json_schema", "json_object"])
def test_pi_selection_requires_consistent_authoritative_model_protocol(
    tmp_path: Path, slot: str, protocol: str
) -> None:
    settings, _, db = adapter_inputs(tmp_path)
    models = settings.parent / "models/models-v1.yaml"
    if slot == "screening":
        models.write_text(models.read_text().replace("prompt_only", protocol))
    else:
        models.write_text(
            models.read_text().replace(
                f"{slot}: null",
                f"{slot}:\n  provider: provider-a\n  model: model-a\n"
                f"  protocol: {protocol}",
            )
        )
    with pytest.raises(ConfigError, match=f"models.{slot}.protocol"):
        compile_config(settings, db)


def test_resource_hash_mismatch_is_actionable_and_does_not_expose_prompt(
    tmp_path: Path,
) -> None:
    settings, _, db = adapter_inputs(tmp_path)
    (settings.parent / "prompts/pi-system-v1.md").write_bytes(b"PRIVATE_MARKER")
    with pytest.raises(ConfigError, match="系统提示词哈希不匹配") as error:
        check_config(settings, db)
    assert "PRIVATE_MARKER" not in str(error.value)


@pytest.mark.parametrize("duplicate", [False, True])
def test_untrusted_yaml_key_cannot_echo_a_command_or_input_marker(
    tmp_path: Path, duplicate: bool
) -> None:
    settings, path, db = adapter_inputs(tmp_path)
    field = '"PRIVATE_MARKER $(echo never-execute)": ignored\n'
    path.write_text(path.read_text() + field * (2 if duplicate else 1))
    with pytest.raises(ConfigError) as error:
        check_config(settings, db)
    assert "PRIVATE_MARKER" not in str(error.value)
    assert "echo never-execute" not in str(error.value)


@pytest.mark.parametrize(
    ("before", "after", "guidance"),
    [
        ("pi_version: 1.1.0", "pi_version: PRIVATE_MARKER", "精确三段版本"),
        (
            "212c2cd595c12aaf7ca2a4b6783b3f43f85ce077745c2a55f4f18d6c07b9e2d1",
            "PRIVATE_MARKER",
            "64 位小写 SHA-256",
        ),
    ],
)
def test_pin_and_hash_format_errors_explain_the_required_format(
    tmp_path: Path, before: str, after: str, guidance: str
) -> None:
    settings, path, db = adapter_inputs(tmp_path)
    path.write_text(path.read_text().replace(before, after))
    with pytest.raises(ConfigError, match=guidance) as error:
        check_config(settings, db)
    assert "PRIVATE_MARKER" not in str(error.value)
