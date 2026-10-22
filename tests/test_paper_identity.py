"""公共 DOI 边界使用独立固定 JSON 向量。"""

import json
from pathlib import Path

import pytest

from paper_radar.papers import PaperError, normalize_doi

VECTORS = json.loads(Path("tests/fixtures/paper_facts_v1.json").read_text())["doi"]


@pytest.mark.parametrize("vector", VECTORS)
def test_doi_fixed_vector(vector: dict[str, str]) -> None:
    if "reason" in vector:
        with pytest.raises(PaperError, match=vector["reason"]):
            normalize_doi(vector["raw"])
    else:
        assert normalize_doi(vector["raw"]) == vector["expected"]
