"""D1:完整公共服务材料;仅替换外部 worker 进程。"""

import hashlib
import json
import sys
from pathlib import Path

import yaml

from paper_radar.body import BodyService
from paper_radar.config import compile_config
from paper_radar.docling_execution.process import DoclingProcess
from paper_radar.docling_executor import DoclingParser, DoclingRun
from paper_radar.papers import PaperFacts
from tests.a7_registration_support import Archive
from tests.body_support import PDF
from tests.config_projection_support import full_inputs
from tests.test_fulltext_artifacts import document
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation


def prepared_docling(
    root: Path, *, failure: str | None = None
) -> tuple[Archive, BodyService, DoclingParser]:
    settings, database = full_inputs(root)
    config_path = root / "config/extraction/extraction-v1.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["toolchain"] = "docling-2.135.0-cpu-v2"
    model_root = root / "models"
    declarations = []
    repos = {
        "layout": "docling-project/docling-layout-egret-medium",
        "table": "docling-project/docling-models",
        "formula": "docling-project/CodeFormulaV2",
    }
    for stage, model in config["models"].items():
        for member in model["files"]:
            path = model_root / repos[stage].replace("/", "--") / member["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = b"synthetic frozen model file: " + member["path"].encode()
            path.write_bytes(raw)
            member["sha256"] = hashlib.sha256(raw).hexdigest()
        declarations.append(
            {
                "repo_id": repos[stage],
                "commit_sha": model["commit_sha"],
                "files": sorted(model["files"], key=lambda f: f["path"]),
            }
        )
    (model_root / "deployment.json").write_text(
        json.dumps({"format_version": 1, "models": declarations})
    )
    config_path.write_text(yaml.safe_dump(config))
    snapshot = compile_config(settings, database)
    saved = PaperFacts(database, root / "data").submit(
        observation(fields=screening_fields())
    )
    assert saved.paper_id and saved.version_id
    archive = Archive(
        settings,
        database,
        root / "data",
        snapshot.snapshot_id,
        saved.paper_id,
        saved.version_id,
    )
    service = BodyService(database, archive.data_root)
    service.register_root("experiment")
    service.attach_pdf(saved.paper_id, PDF, request_id="pdf")
    payload: dict[str, object] = (
        {"failure": failure}
        if failure
        else {
            "document": document().model_dump(mode="json"),
            "document_json": '{"schema_name":"SyntheticExternalBoundary"}',
        }
    )
    payload["peak_memory_bytes"] = 4096
    script = """import json,os,sys
from pathlib import Path
request=json.loads(Path(sys.argv[1]).read_text())
assert os.environ['HF_HUB_OFFLINE']=='1'
assert os.environ['TRANSFORMERS_OFFLINE']=='1'
assert os.environ['CUDA_VISIBLE_DEVICES']==''
assert os.environ['OPENBLAS_NUM_THREADS']==str(request['threads'])
assert os.environ['OMP_NUM_THREADS']==str(request['threads'])
assert len(list(Path(request['model_root']).rglob('*.safetensors')))==3
Path(request['response_path']).write_text(PAYLOAD)
""".replace("PAYLOAD", repr(json.dumps(payload)))
    parser = DoclingParser(
        DoclingRun(
            model_root=model_root, timeout_seconds=3.0, memory_limit_bytes=2**34
        ),
        executor=DoclingProcess(command=(sys.executable, "-c", script)),
    )
    return archive, service, parser
