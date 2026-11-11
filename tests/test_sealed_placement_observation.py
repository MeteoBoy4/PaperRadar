"""D1: fixed trusted directory handoff reads fresh atomic snapshots, without root."""

import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest


@pytest.mark.parametrize("change", ["refresh", "expired", "mixed", "target", "symlink"])
def test_inherited_directory_reads_new_snapshot_and_rejects_drift(
    tmp_path: Path,
    change: str,
) -> None:
    # A cold test adapter replaces only the proc/cgroup paths and pre-verified
    # root directory provenance. Actual fds/openat/inodes/JSON/time checks execute.
    script = tmp_path / "adapter.py"
    script.write_text(r"""
import hashlib, os, sys
from pathlib import Path
from datetime import UTC, datetime, timedelta
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from paper_radar.pi_execution import placement as p
from paper_radar.live_evidence import ledger
from paper_radar.live_evidence.observation import CurrentObservation, RefreshStatus
from paper_radar.live_evidence.receipt import canonical_bytes
from paper_radar.live_evidence.types import BindingComponent as B
root=Path(sys.argv[3]); change=sys.argv[4]
inbox=root/'inbox'; inbox.mkdir(mode=0o755)
proc=root/'proc'; cgroups=root/'cgroups'
(cgroups/'paperradar.slice').mkdir(parents=True)
unit='paperradar-'+'a'*32+'.scope'
for pid, group in ((os.getpid(), '/paperradar.slice/'+unit),
                   (123, '/paperradar.slice/paperradar-anchor.service')):
    directory=proc/str(pid); directory.mkdir(parents=True)
    (directory/'stat').write_text(
        f'{pid} (controlled peer) S 1 123 123 0 -1 4194304 '
        '1 0 0 0 0 0 0 0 20 0 1 0 777 0\n')
    (directory/'cgroup').write_text('0::'+group+'\n')
ledger.LEDGER_ROOT=root; p._PROC_ROOT=proc; p._CGROUP_ROOT=cgroups
value = p.PlacementTarget.model_validate(dict(
    format_version=1, slice='paperradar.slice',
    ancestors=[dict(path=path,device=node.stat().st_dev,inode=node.stat().st_ino)
               for path,node in (('/paperradar.slice',cgroups/'paperradar.slice'),
                                 ('/',cgroups))],
    anchor_pid=123,anchor_start=777,
    anchor_cgroup='/paperradar.slice/paperradar-anchor.service',
    egress_digest='b'*64,resolver_view='/run/paper-radar/resolv.conf',resolver_digest='c'*64))
(inbox/p.TARGET_FILENAME).write_bytes(canonical_bytes(value))
(inbox/p.TARGET_FILENAME).chmod(0o644)
now=datetime.now(UTC)
def publish(at, *, mixed=False):
    observation=CurrentObservation(observed_at=at,binding={b:'b'*64 for b in B},
                                   checked_components=tuple(B))
    raw=canonical_bytes(observation)
    digest='f'*64 if mixed else hashlib.sha256(raw).hexdigest()
    status=RefreshStatus(recorded_at=at,result='available',snapshot_sha256=digest)
    for name,data in (('current-observation.json',raw),
                      ('observation-refresh.json',canonical_bytes(status))):
        source=inbox/(name+'.new'); source.write_bytes(data); source.chmod(0o644)
        os.replace(source,inbox/name)
publish(now-timedelta(seconds=2))
fd=os.open(inbox,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
if fd != 5: os.dup2(fd,5); os.close(fd)
assert p.verify_inherited_placement() == value
old=(inbox/'current-observation.json').stat().st_ino
if change=='refresh': publish(now)
elif change=='expired': publish(now-timedelta(seconds=61))
elif change=='mixed': publish(now,mixed=True)
elif change=='target':
    replacement=value.model_copy(update={'egress_digest':'d'*64})
    (inbox/p.TARGET_FILENAME).write_bytes(canonical_bytes(replacement))
else:
    (inbox/'current-observation.json').unlink()
    (inbox/'current-observation.json').symlink_to(root/'outside')
if change=='refresh':
    assert (inbox/'current-observation.json').stat().st_ino != old
    assert p.verify_inherited_placement(close=True) == value
else:
    try: p.verify_inherited_placement(close=True)
    except p.ExecutionError as error: assert str(error)=='placement_handshake_invalid'
    else: raise AssertionError('untrusted snapshot was accepted')
""")
    result = subprocess.run(
        (
            sys.executable,
            "-I",
            "-S",
            "-B",
            str(script),
            str(Path(__file__).resolve().parents[1] / "src"),
            sysconfig.get_path("purelib"),
            str(tmp_path),
            change,
        ),
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout == result.stderr == b""
