"""D1:冷进程禁SDK、网络和解析的基础入口/只读重建。"""

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.body_support import prepared


def test_cold_public_import_query_and_context_do_not_load_sdk(tmp_path: Path) -> None:
    saved, service, parser = prepared(tmp_path / "source")
    extracted = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    assert extracted.artifact_id and extracted.identity
    expected = {
        "database": str(saved.database),
        "root": str(saved.data_root),
        "artifact": extracted.artifact_id,
        "fingerprint": extracted.fingerprint,
        "reading": extracted.identity.reading_sha256,
        "evidence": extracted.identity.evidence_map_sha256,
    }
    script = """import importlib.abc,json,sys
from pathlib import Path
class DenySDK(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  denied={'docling','docling_core','torch','transformers','torchvision',
          'pypdfium2','docling_parse','huggingface_hub'}
  if fullname.split('.')[0] in denied:
   raise RuntimeError('SDK import forbidden')
sys.meta_path.insert(0,DenySDK())
def guard(event,args):
 if event.startswith(('socket.','subprocess.','os.exec','os.spawn')):
  raise RuntimeError('execution forbidden')
sys.addaudithook(guard)
from paper_radar.docling_executor import DoclingParser,DoclingRun
from paper_radar.body import BodyService
from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.reading.context import ExtractionIdentity
facts=json.loads(sys.argv[1])
DoclingParser(DoclingRun(model_root=Path('/missing'),timeout_seconds=1.0,memory_limit_bytes=2**34))
service=BodyService(Path(facts['database']),Path(facts['root']))
result=service.extraction(facts['fingerprint'])
assert result and len(result.attempts)==1
loaded=FulltextArtifacts(service.store).load(facts['artifact'],expected_identity=ExtractionIdentity(facts['fingerprint'],facts['reading'],facts['evidence']))
assert loaded.context.replay()[1].text=='Exact source α = 2.'
service.validate_all()
print('cold import and read without SDK')
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, json.dumps(expected)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "cold import and read without SDK"
