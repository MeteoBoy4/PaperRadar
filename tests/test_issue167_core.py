"""独立未绑定 core 可行性探针;不制造崩溃或 core。"""

import json

import pytest

from scripts.issue167_core import decode, probe


@pytest.mark.parametrize("no_new_privs", [False, True])
def test_plain_exec_loses_pre_exec_dumpable_protection(no_new_privs: bool) -> None:
    receipt = probe(no_new_privs=no_new_privs)
    assert receipt.before_exec == 0
    assert receipt.after_exec == 1
    assert receipt.after_reapply == 0
    assert receipt.conclusion == "pre_exec_protection_lost"
    if no_new_privs:
        assert receipt.no_new_privs == 1


@pytest.mark.parametrize(
    "raw",
    [
        b"not JSON",
        b'{"passed":true}',
        b"[]",
        b'{"before_exec":false,"after_exec":1,"after_reapply":0,"no_new_privs":0}',
        b'{"before_exec":0,"after_exec":9,"after_reapply":0,"no_new_privs":0}',
        b"x" * 1025,
    ],
)
def test_invalid_probe_data_never_passes(raw: bytes) -> None:
    with pytest.raises(ValueError, match=r"^probe_output_invalid$"):
        decode(raw)


def test_no_observed_reset_does_not_prove_core_protection() -> None:
    receipt = decode(
        json.dumps(
            {
                "before_exec": 0,
                "after_exec": 0,
                "after_reapply": 0,
                "no_new_privs": 1,
            }
        ).encode()
    )
    assert receipt.conclusion == "not_established"
