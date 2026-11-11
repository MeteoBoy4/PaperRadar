"""独立标准库 auth/RPC 对端;不导入产品或产品测试消息生成器。"""

import copy
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

MODE = "__MODE__"
args = sys.argv[1:]
agent = Path(os.environ["PI_CODING_AGENT_DIR"])
if not args:
    auth = json.loads((agent / "auth.json").read_text())
    (agent / "auth-observed.json").write_text(json.dumps({"argv": args}))
    if auth.get("mode") == "failure":
        print(auth["token"], file=sys.stderr)
        raise SystemExit(1)
    from datetime import UTC, datetime

    now = datetime.now(UTC).isoformat()
    os.write(
        int(os.environ["PAPERRADAR_AUTH_METADATA_FD"]),
        json.dumps(
            {
                "format_version": 1,
                "source_id": "pi-auth-refresh-1.4.0-v1",
                "pid": os.getpid(),
                "started_at": now,
                "completed_at": now,
                "refresh_called": False,
            }
        ).encode(),
    )
    print(auth["token"])
    raise SystemExit(0)

assert set(p.name for p in agent.iterdir()) == {"settings.json"}
assert "NODE_OPTIONS" not in os.environ
assert "XDG_CONFIG_HOME" not in os.environ
assert "private-sentinel" not in str(dict(os.environ))
settings = json.loads((agent / "settings.json").read_text())
assert settings["cacheWarming"] == "off"
assert settings["retry"]["provider"]["maxRetries"] == 0
for name in ("__DATABASE__", "__CREDENTIALS__"):
    try:
        Path(name).read_bytes()
    except PermissionError:
        pass
    else:
        raise SystemExit(21)
if MODE == "orphan":
    if os.fork() == 0:
        while True:
            time.sleep(1)
    raise SystemExit(0)

model = {"provider": "openai", "id": "real-model"}
thinking = "low"


def send(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")), flush=True)


for line in sys.stdin:
    command = json.loads(line)
    kind = command["type"]
    data: dict[str, Any] | None = None
    if kind == "new_session":
        data = {"cancelled": False}
    elif kind == "set_model":
        model = {"provider": command["provider"], "id": command["modelId"]}
        data = model
    elif kind == "get_available_thinking_levels":
        data = {"levels": ["off", "low", "high"]}
    elif kind == "set_thinking_level":
        thinking = command["level"]
    elif kind == "get_commands":
        data = {"commands": []}
    elif kind == "get_state":
        data = {
            "model": model,
            "thinkingLevel": thinking,
            "autoCompactionEnabled": False,
            "isStreaming": False,
            "isCompacting": False,
            "messageCount": 0,
            "pendingMessageCount": 0,
            "autoRetryEnabled": False,
        }
    elif kind == "prompt":
        if MODE == "timeout":
            time.sleep(5)
        if MODE == "environment":
            raise SystemExit(3)
        data = {"disposition": "started"}
    elif kind == "clear_queue":
        data = {"steering": [], "followUp": []}
    response = {
        "id": command["id"],
        "type": "response",
        "command": kind,
        "success": True,
    }
    if data is not None:
        response["data"] = data
    send(response)
    if kind != "prompt":
        continue
    if MODE == "protocol":
        send({"type": "tool_execution_start"})
        continue
    raw = '{"boundary":"in_scope","reason_zh":"论文研究天气过程。"}'
    if '"stage":"value"' in command["message"]:
        raw = (
            '{"research_value":4,"research_value_reason_zh":"该方法能改进降水诊断。",'
            '"reuse_feasibility":3,"reuse_feasibility_reason_zh":"需要调整数据处理流程。",'
            '"reuse_feasibility_inferable":true,"value_types":["method"],'
            '"topic_ids":[],'
            '"abstract_brief_zh":"研究提出天气诊断方法。",'
            '"why_it_may_matter_zh":"可用于区域降水分析。","display_title_zh":"天气观测研究"}'
        )
    if MODE == "output_invalid":
        raw = "{}"
    cwd = "<cwd>\n" + os.getcwd() + "\n</cwd>"
    if MODE == "cwd_mismatch":
        cwd = "<cwd>\n/other\n</cwd>"
    system = {
        "role": "system",
        "content": "",
        "sections": {"preamble": args[args.index("--system-prompt") + 1], "cwd": cwd},
        "timestamp": 1,
    }
    user = {
        "role": "user",
        "content": [{"type": "text", "text": command["message"]}],
        "timestamp": 2,
    }
    final = {
        "role": "assistant",
        "content": [{"type": "text", "text": raw}],
        "api": "openai-responses",
        "provider": model["provider"],
        "model": model["id"],
        "thinkingLevel": thinking,
        "stopReason": "stop",
        "timestamp": 3,
        "usage": {
            "input": 4,
            "output": 2,
            "cacheRead": 1,
            "cacheWrite": 0,
            "totalTokens": 7,
            "cost": {
                "input": 0,
                "output": 0,
                "cacheRead": 0,
                "cacheWrite": 0,
                "total": 0,
            },
        },
    }
    if MODE == "model_mismatch":
        final["model"] = "other-model"
    partial = copy.deepcopy(final)
    partial.update(content=[], stopReason="pending")
    events: list[dict[str, Any]] = [
        {"type": "agent_start"},
        {"type": "turn_start"},
        {"type": "message_start", "message": system},
        {"type": "message_end", "message": system},
        {"type": "message_start", "message": user},
        {"type": "message_end", "message": user},
        {"type": "message_start", "message": partial},
        {"type": "message_end", "message": final},
        {"type": "turn_end", "message": final, "toolResults": []},
        {"type": "agent_end", "messages": [system, user, final], "willRetry": False},
        {"type": "agent_settled", "aborted": False},
    ]
    for event in events:
        send(event)
