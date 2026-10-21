"""Pure baseline opportunity evaluation, independent of optional Behavior."""
from copy import deepcopy
from npc_opportunity_rules import opportunity_inputs


def evaluate_npc_opportunities(npc, npc_id):
    result = {"version": 1, "status": "unresolved", "npc_id": npc_id, "reasons": []}
    try:
        window_id, eligible, sociability, config = opportunity_inputs(npc, npc_id)
    except ValueError as error:
        result["reasons"] = [str(error)]
        return result
    candidates = [{"kind": "no_initiation", "episode_id": None,
                   "weight": config["initiation"]["no_initiation"]}]
    if eligible:
        weight = (config["initiation"]["initiation_base"] + sociability) / len(eligible)
        candidates.extend({"kind": "episode", "episode_id": eid, "weight": weight} for eid in eligible)
    result.update(status="possible", window_id=window_id, candidates=candidates,
                  basis=deepcopy(npc), policy_basis=config,
                  reasons=["eligible_opportunities" if eligible else "no_eligible_opportunities"])
    return result
