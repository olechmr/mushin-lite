"""Pure, versioned baseline interaction policy; no optional Behavior dependency."""
from copy import deepcopy
from npc_episode_rules import episode_factors, policy_snapshot


def evaluate_baseline_episode(npc, episode_id):
    """Produce possibilities only for an explicitly installed, unresolved episode."""
    result = {"version": 1, "archetype": "interaction_v1", "episode_id": episode_id, "feasibility": "unresolved",
              "allowed_outcomes": [], "weights": {}, "reasons": []}
    try:
        participants, overlap, dispositions, prior = episode_factors(npc, episode_id)
        if episode_id in npc["resolutions"]:
            result["reasons"] = ["already_resolved"]
            return result
        config = policy_snapshot(npc, participants)
    except ValueError as error:
        result["reasons"] = [str(error)]
        return result
    weights = {"no_interaction": config["no_interaction"]}
    if overlap:
        weights["conversation"] = config["conversation"] + sum(dispositions["sociability"])
        weights["disagreement"] = (config["disagreement"] + sum(dispositions["irritability"])
                                   + config["history_bias"] * int(prior))
    result.update(feasibility="possible" if overlap else "impossible", weights=weights,
                  allowed_outcomes=list(weights), basis=deepcopy(npc), policy_basis=config,
                  reasons=[("prior_disagreement_bias" if prior else "compatible_constraints")
                           if overlap else "disjoint_allowed_places"])
    return result
