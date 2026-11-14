"""B-E16 独立 D1:本机合成 OS 正反对照;不能替代 CI 或真实现场验收。"""

import errno
import json
import socket
import subprocess
import sys
from pathlib import Path

from paper_radar.replay.isolation import ReplayBoundary, runtime_paths
from tests.replay_support import restored_demo


def test_real_os_controls_read_escape_and_direct_local_connect(tmp_path: Path) -> None:
    root, originals = restored_demo(tmp_path)
    source = originals[2] / "synthetic.txt"
    (root / "views/escape").symlink_to(source)
    probe = Path(__file__).with_name("replay_os_probe.py").resolve()
    local = tmp_path / "local.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(local))
        listener.listen(2)
        results = []
        for restricted in (False, True):
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-B",
                        str(probe),
                        str(root),
                        str(source),
                        str(client.fileno()),
                        str(local),
                    ],
                    env={},
                    cwd=root / "contents",
                    close_fds=True,
                    pass_fds=(client.fileno(),),
                    preexec_fn=ReplayBoundary(root, (*runtime_paths(), probe))
                    if restricted
                    else None,
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
            assert result.returncode == 0, result.stdout + result.stderr
            results.append(json.loads(result.stdout))
    plain, confined = results
    for name in ("restored", "original", "escape", "2", "10", "1", "connect"):
        assert plain[name] == "allowed"
    assert confined["restored"] == "allowed"
    assert confined["original"] == confined["escape"] == errno.EACCES
    assert all(confined[name] == errno.EPERM for name in ("2", "10", "1", "connect"))
    assert confined["no_new_privs"] == 1 and confined["seccomp"] == 2
