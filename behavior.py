"""Pure NPC possibility evaluation. No sampling, facts, persistence or narration."""

import math
from copy import deepcopy
from npc_fixture import NPC_TRANSITION_POLICIES, SUPPORTED_DISPOSITIONS, DISAGREEMENT_INITIATOR_EPISODE
from npc_episode_rules import OUTCOMES, _episode_constraints, episode_factors


def _result(feasibility, weights, reason):
    return {
        "feasibility": feasibility,
        "allowed_outcomes": list(weights),
        "weights": weights,
        "reasons": [reason],
    }


def evaluate_episode(npc, episode_id):
    """Compatibility view of baseline possibilities or validated committed truth."""
    try:
        episode_factors(npc, episode_id)
    except ValueError as error:
        return _result("unresolved", {}, str(error))
    if episode_id in npc["resolutions"]:
        result = _result("resolved", {}, "already_resolved")
        result["allowed_outcomes"] = [npc["resolutions"][episode_id]["outcome"]]
        return result
    from npc_baseline import evaluate_baseline_episode
    evaluation = evaluate_baseline_episode(npc, episode_id)
    return {k: evaluation[k] for k in ("feasibility", "allowed_outcomes", "weights", "reasons")}


def validated_transition_policies():
    """Validate the entire explicit collection before lookup or dispatch."""
    if not isinstance(NPC_TRANSITION_POLICIES, (tuple, list)):
        raise ValueError("invalid_policy_collection")
    policy_ids, targets = set(), set()
    for policy in NPC_TRANSITION_POLICIES:
        if (
            not isinstance(policy, dict)
            or set(policy) != {"policy_id", "entity_id", "episode_id", "required_outcome", "attribute", "value"}
            or any(not isinstance(policy[k], str) or not policy[k].strip()
                   for k in ("policy_id", "entity_id", "episode_id"))
            or policy["required_outcome"] != "disagreement" or policy["attribute"] not in SUPPORTED_DISPOSITIONS
            or type(policy["value"]) not in (int, float) or not 0 <= policy["value"] <= 1
            or not math.isfinite(policy["value"])
        ):
            raise ValueError("invalid_policy")
        target = (policy["episode_id"], policy["entity_id"], policy["attribute"])
        if policy["policy_id"] in policy_ids:
            raise ValueError("duplicate_policy_id")
        if target in targets:
            raise ValueError("duplicate_policy_target")
        policy_ids.add(policy["policy_id"])
        targets.add(target)
    return tuple(NPC_TRANSITION_POLICIES)


def get_transition_policy(policy_id):
    """Return one registered policy, or None; invalid registration fails closed."""
    policies = validated_transition_policies()
    if not isinstance(policy_id, str):
        return None
    return next((policy for policy in policies if policy["policy_id"] == policy_id), None)


def evaluate_transition(npc, policy_id):
    """Pure fixed-policy proposal; committed history is input, not a causal claim."""
    result = {"status": "unresolved", "policy_id": policy_id, "reasons": []}
    try:
        policy = get_transition_policy(policy_id)
    except ValueError as error:
        result["reasons"] = [str(error)]
        return result
    if policy is None:
        result["reasons"] = ["unsupported_policy"]
        return result
    evaluation = evaluate_episode(npc, policy["episode_id"])
    if evaluation["feasibility"] != "resolved":
        result["reasons"] = ["missing_or_invalid_committed_prerequisite"]
        return result
    episode = npc["episodes"][policy["episode_id"]]
    if policy["entity_id"] not in episode["participants"]:
        result["reasons"] = ["target_not_participant"]
        return result
    previous = npc["entities"][policy["entity_id"]][policy["attribute"]]
    if evaluation["allowed_outcomes"] != [policy["required_outcome"]]:
        result.update(status="no_change", reasons=["prerequisite_outcome_not_matched"])
    elif previous >= policy["value"]:
        result.update(status="no_change", reasons=["target_already_met"])
    else:
        result.update(status="proposed", reasons=["policy_authorized"],
                      entity_id=policy["entity_id"], episode_id=policy["episode_id"],
                      attribute=policy["attribute"], previous=previous,
                      value=policy["value"], basis=deepcopy(npc))
    return result


def evaluate_disagreement_initiator(npc, episode_id):
    """Current irritability weights a requested refinement, not historical cause.

    Existing truth is reused without requiring current disposition inputs.
    Absence remains unresolved until an explicitly requested collapse commits.
    """
    def result(status, reason, weights=None):
        return {"status": status, "allowed_outcomes": list(weights or {}),
                "weights": weights or {}, "reasons": [reason]}

    if (
        not isinstance(npc, dict) or type(npc.get("version")) is not int or npc["version"] != 1
        or any(not isinstance(npc.get(k), dict) for k in ("entities", "episodes", "resolutions"))
        or episode_id != DISAGREEMENT_INITIATOR_EPISODE
    ):
        return result("unresolved", "invalid_or_unauthorized_episode")
    constraints = _episode_constraints(npc["episodes"].get(episode_id), npc["entities"])
    if constraints is None:
        return result("unresolved", "invalid_episode_constraints")
    participants, _, overlap = constraints
    if any(not isinstance(npc["entities"][p], dict) for p in participants):
        return result("unresolved", "invalid_participant")
    resolution = npc["resolutions"].get(episode_id)
    if (
        not isinstance(resolution, dict) or resolution.get("outcome") not in OUTCOMES
        or type(resolution.get("event_id")) is not int or resolution["event_id"] < 1
        or (not overlap and resolution["outcome"] != "no_interaction")
    ):
        return result("unresolved", "missing_or_invalid_committed_episode")
    if "disagreement_initiator" in resolution:
        actor = resolution["disagreement_initiator"]
        if resolution["outcome"] != "disagreement" or not isinstance(actor, str) or actor not in participants:
            return result("unresolved", "invalid_stored_initiator")
        resolved = result("resolved", "already_resolved")
        resolved["allowed_outcomes"] = [actor]
        return resolved
    if resolution["outcome"] != "disagreement":
        return result("not_applicable", "episode_not_disagreement")
    weights = {}
    for actor in sorted(participants):
        value = npc["entities"][actor].get("irritability")
        if type(value) not in (int, float) or not 0 <= value <= 1 or not math.isfinite(value):
            return result("unresolved", "missing_or_invalid_irritability")
        weights[actor] = 1.0 + value
    return result("possible", "current_irritability_weights", weights)
