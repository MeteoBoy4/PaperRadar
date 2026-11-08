"""Independent D1: privileged bootstrap input seam, ordinary temporary FIFO only."""

import os
import subprocess
import sys
from pathlib import Path


def test_source_fifo_is_rejected_before_any_blocking_read(tmp_path: Path) -> None:
    os.mkfifo(tmp_path / "member", 0o600)
    # Separate ordinary child makes the pre-fix blocking open a bounded failure.
    code = """
import os,sys
from scripts.issue167_h1_auto_bootstrap import BootstrapRejected,read_member
fd=os.open(sys.argv[1],os.O_RDONLY|os.O_DIRECTORY)
try:
    try: read_member(fd,'member',os.getuid(),4096)
    except BootstrapRejected as error:
        assert str(error)=='source_metadata_invalid'
    else: raise AssertionError('FIFO must be rejected')
finally: os.close(fd)
"""
    subprocess.run(
        [sys.executable, "-B", "-c", code, str(tmp_path)],
        capture_output=True,
        check=True,
        timeout=2,
    )
