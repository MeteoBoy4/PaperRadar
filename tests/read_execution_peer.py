"""独立Read标准库协议对端;不导入产品或产品测试消息生成器。"""

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

print("STDERR PRIVATE SENTINEL", file=sys.stderr, flush=True)
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


seen: dict[str, int] = {}
for line in sys.stdin:
    command = json.loads(line)
    kind = command["type"]
    seen[kind] = seen.get(kind, 0) + 1
    if kind in {"new_session", "prompt"}:
        assert seen[kind] == 1
    if kind == "prompt":
        assert seen.get("new_session") == 1
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
    request = json.loads(command["message"][command["message"].index("{") :])
    assert request["stage"] == "read"
    if MODE == "require_correction":
        assert request["correction"] is not None
    if request["correction"] is not None:
        assert "BAD PRIVATE ID" not in request["correction"]
        assert "main_findings" in request["correction"]
    reason = {
        "statement": "该方法提供了新的比较方式。",
        "evidence": [{"evidence_id": "e000002"}],
    }
    output: dict[str, Any] = {
        "output_language": "zh",
        "one_sentence_conclusion": "该研究比较了降水预测方法。",
        "research_question": "如何提高预测质量？",
        "methods_summary": "比较独立预测。",
        "data_summary": "使用公开观测数据。",
        "main_findings": [],
        "research_value": 3,
        "research_value_reason": reason,
        "reuse_feasibility": 3,
        "reuse_feasibility_reason": reason,
        "required_adaptations": [],
        "reusable_points": [],
        "key_limitations": [],
        "open_questions": [],
        "value_types": ["method"],
        "why_it_matters": "有助于比较预测方法。",
        "next_action": "检查研究假设。",
        "degraded_content_warnings": [],
    }
    if MODE in {"degrade", "require_correction"}:
        output["main_findings"] = [
            {
                "statement": "独立比较支持结果。",
                "evidence": [{"evidence_id": "BAD PRIVATE ID"}],
            }
        ]
        output["main_findings"].append(
            {"statement": "有效的独立比较。", "evidence": [{"evidence_id": "e000002"}]}
        )
    raw = json.dumps(output, ensure_ascii=False)
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
    if MODE == "retry":
        events[-2]["willRetry"] = True
    if MODE == "compaction":
        events.insert(1, {"type": "auto_compaction_start"})
    if MODE == "extra_turn":
        events.insert(-1, {"type": "turn_start"})
    if MODE == "duplicate_end":
        events.append(events[-1])
    for event in events:
        send(event)
