"""纯标准库合成 RPC 对端;仅由 A8 测试以最小环境启动。"""

import json
import os
import signal
import sys
from typing import Any

RAW = ' \n{"boundary":"in_scope","reason_zh":"论文研究天气过程。"}\n '


def write(fd: int, data: bytes) -> None:
    while data:
        data = data[os.write(fd, data) :]


def emit(records: list[dict[str, Any]]) -> None:
    write(
        1, b"".join(json.dumps(r, ensure_ascii=False).encode() + b"\n" for r in records)
    )


def events(message: str, system_prompt: str) -> list[dict[str, Any]]:
    system = {
        "role": "system",
        "content": "",
        "timestamp": 1,
        "sections": {
            "preamble": system_prompt,
            "cwd": "<cwd>\n/synthetic-neutral\n</cwd>",
        },
    }
    user = {
        "role": "user",
        "content": [{"type": "text", "text": message}],
        "timestamp": 2,
    }
    assistant = {
        "role": "assistant",
        "content": [{"type": "text", "text": RAW}],
        "api": "openai-completions",
        "provider": "provider-a",
        "model": "real-model",
        "thinkingLevel": "low",
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
    return [
        {"type": "agent_start"},
        {"type": "turn_start"},
        {"type": "message_start", "message": system},
        {"type": "message_end", "message": system},
        {"type": "message_start", "message": user},
        {"type": "message_end", "message": user},
        {
            "type": "message_start",
            "message": {**assistant, "content": [], "stopReason": "pending"},
        },
        {"type": "message_end", "message": assistant},
        {"type": "turn_end", "message": assistant, "toolResults": []},
        {
            "type": "agent_end",
            "messages": [system, user, assistant],
            "willRetry": False,
        },
        {"type": "agent_settled", "aborted": False},
    ]


def main() -> None:
    scenario, system_prompt, status_text = sys.argv[1:]
    status = int(status_text)
    if scenario.startswith("grandchild"):
        pid = os.fork()
        if pid == 0:
            if scenario == "grandchild_closed":
                for fd in (0, 1, 2):
                    os.close(fd)
            write(status, f"G{os.getpid()}\n".encode())
            os.close(status)
            while True:
                signal.pause()
    write(status, b"R\n")
    stream = sys.stdin.buffer
    count = 0
    while True:
        # 第九条命令先取短前缀,让大 stdin 与双输出管道同时承压。
        prefix = os.read(0, 128) if count == 8 and scenario == "backpressure" else b""
        if prefix:
            write(2, b"STDERR_SECRET" * 32768)
            emit(
                [
                    {
                        "type": "response",
                        "id": "rpc-9",
                        "command": "prompt",
                        "success": True,
                        "data": {"disposition": "started"},
                        "padding": "x" * (128 * 1024),
                    }
                ]
            )
        line = prefix + stream.readline()
        if not line:
            break
        command = json.loads(line)
        name = command["type"]
        count += 1
        write(status, f"C{name}\n".encode())
        response: dict[str, Any] = {
            "type": "response",
            "id": command["id"],
            "command": name,
            "success": True,
        }
        data: dict[str, Any] | None = None
        if name == "new_session":
            data = {"cancelled": False}
        elif name == "set_model":
            data = {"provider": "provider-a", "id": "real-model"}
        elif name == "get_available_thinking_levels":
            data = {"levels": ["off", "low", "high"]}
        elif name == "get_commands":
            data = {"commands": []}
        elif name == "get_state":
            data = {
                "model": {"provider": "provider-a", "id": "real-model"},
                "thinkingLevel": "low",
                "autoCompactionEnabled": False,
                "isStreaming": False,
                "isCompacting": False,
                "messageCount": 0,
                "pendingMessageCount": 0,
            }
        elif name == "clear_queue":
            data = {"steering": ["QUEUE_SECRET"], "followUp": ["FOLLOWUP_SECRET"]}
        elif name == "prompt":
            if scenario == "early_exit":
                os._exit(17)
            if scenario == "flood":
                write(2, b"STDERR_SECRET" * 200000)
            data = {"disposition": "started"}
        if data is not None:
            response["data"] = data
        if not (prefix and name == "prompt"):
            emit([response])
        if name == "prompt":
            if scenario in {"hang", "grandchild_holds"}:
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                while True:
                    signal.pause()
            if scenario == "cancel":
                write(status, b"P\n")
                continue
            emit(events(command["message"], system_prompt))


if __name__ == "__main__":
    main()
