"""固定非秘密 socket worker;仅由同一 PlacedProcess 放置执行。"""

import json
import socket
import sys
from pathlib import Path


def main() -> int:
    if sys.argv[1:]:
        return 2
    case = sys.stdin.buffer.readline(64).decode("ascii").strip()
    configuration = json.loads(
        Path(
            "/usr/libexec/paperradar/live-evidence-runtime/model-manifest.json"
        ).read_bytes()
    )["network"]
    choices = {
        "outside-tcp443": (configuration["outside"], 443, socket.SOCK_STREAM),
        "nonrouter-udp53": (configuration["nonrouter"], 53, socket.SOCK_DGRAM),
        "nonrouter-tcp53": (configuration["nonrouter"], 53, socket.SOCK_STREAM),
        "udp443": (configuration["udp443"], 443, socket.SOCK_DGRAM),
    }
    if case not in choices:
        return 2
    address, port, kind = choices[case]
    attempted = response = False
    try:
        with socket.socket(socket.AF_INET, kind) as connection:
            connection.settimeout(0.3)
            attempted = True
            if kind == socket.SOCK_STREAM:
                connection.connect((address, port))
                response = True
            else:
                connection.sendto(
                    b"PaperRadar fixed negative control\n", (address, port)
                )
                connection.recvfrom(256)
                response = True
    except OSError:
        pass
    print(json.dumps({"attempted": attempted, "response": response}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
