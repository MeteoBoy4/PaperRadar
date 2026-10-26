"""独立手写的声明行为向量。"""

import json


def declaration_bytes(*, version: str = "v1") -> bytes:
    return json.dumps(
        {
            "format_version": 1,
            "declaration_key": "sample-history",
            "declared_version": version,
            "entries": [
                {
                    "key": "aies-reference-one",
                    "purpose": "references",
                    "journal": "aies",
                    "basis": "historical_declaration",
                    "doi": "10.1175/AIES-D-25-0111.1",
                    "declared_date": "2026-09-13",
                    "source_basis": "intent/draft.md §13.2 历史调查",
                    "expectations": {"publisher_count": 77, "registry_count": 0},
                }
            ],
        },
        ensure_ascii=False,
    ).encode()
