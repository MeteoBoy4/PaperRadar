"""#191 独立合成认证/RPC 对端,禁止读取凭据与收到 prompt。"""

import json
import os
import resource
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MODE = "__MODE__"
if len(sys.argv) == 1:
    now = datetime.now(UTC).isoformat()
    os.write(
        int(os.environ["PAPERRADAR_AUTH_METADATA_FD"]),
        json.dumps(
            dict(
                format_version=1,
                source_id="pi-auth-refresh-1.4.0-v1",
                pid=os.getpid(),
                started_at=now,
                completed_at=now,
                refresh_called=False,
            )
        ).encode(),
    )
    print("oauth-test-only-sensitive-sentinel")
    raise SystemExit(0)

assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)
assert "NoNewPrivs:\t1" in Path("/proc/self/status").read_text()
assert "NODE_OPTIONS" not in os.environ
assert "XDG_CONFIG_HOME" not in os.environ
assert "--no-session" in sys.argv
agent = Path(os.environ["PI_CODING_AGENT_DIR"])
assert {item.name for item in agent.iterdir()} == {"settings.json"}
assert json.loads((agent / "settings.json").read_text())["cacheWarming"] == "off"
try:
    Path("__DATABASE__").read_bytes()
except PermissionError:
    pass
else:
    raise SystemExit(21)
model = {"provider": "openai", "id": "unselected"}
thinking = "off"
commands: list[str] = []
for line in sys.stdin:
    command = json.loads(line)
    name = command["type"]
    assert name in {
        "new_session",
        "set_auto_retry",
        "set_auto_compaction",
        "set_model",
        "get_available_thinking_levels",
        "set_thinking_level",
        "get_commands",
        "get_state",
    }
    assert "message" not in command
    commands.append(name)
    data: dict[str, Any] = {}
    if name == "new_session":
        data = {"cancelled": False}
    elif name == "set_model":
        assert command["provider"] == "openai"
        assert command["modelId"] in {
            "screening-mapping-model",
            "reading-mapping-model",
        }
        model = {"provider": command["provider"], "id": command["modelId"]}
        data = model
    elif name == "get_available_thinking_levels":
        data = {"levels": ["off"] if MODE == "unsupported" else ["low", "high"]}
    elif name == "set_thinking_level":
        thinking = command["level"]
        assert thinking == (
            "low" if model["id"] == "screening-mapping-model" else "high"
        )
    elif name == "get_commands":
        data = {"commands": []}
    elif name == "get_state":
        data = dict(
            model=model,
            thinkingLevel=thinking,
            autoCompactionEnabled=False,
            isStreaming=False,
            isCompacting=False,
            messageCount=0,
            pendingMessageCount=0,
        )
    print(
        json.dumps(
            dict(
                id=command["id"],
                type="response",
                command=name,
                success=not (name == "set_model" and MODE == "model_rejected"),
                data=data,
            )
        ),
        flush=True,
    )
if MODE == "normal":
    assert commands == [
        "new_session",
        "set_auto_retry",
        "set_auto_compaction",
        "set_model",
        "get_available_thinking_levels",
        "set_thinking_level",
        "get_commands",
        "get_state",
    ]
