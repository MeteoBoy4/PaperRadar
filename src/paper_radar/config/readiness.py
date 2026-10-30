"""已验证快照的业务缺项查询。不检查运行环境。"""

from paper_radar.config.compile import RuntimeConfigSnapshot


def configuration_missing(snapshot: RuntimeConfigSnapshot) -> tuple[str, ...]:
    missing = {
        reason.value for stage in snapshot.stages.values() for reason in stage.missing
    }
    if snapshot.profile_status.value != "configured":
        missing.add("profile")
    missing.update(
        "model:" + slot
        for slot, state in snapshot.model_slots.items()
        if state.value != "configured"
    )
    return tuple(sorted(missing))
