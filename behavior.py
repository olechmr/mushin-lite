"""Pure NPC possibility evaluation. No sampling, facts, persistence or narration."""

import math
from copy import deepcopy
from npc_fixture import NPC_TRANSITION_POLICY


OUTCOMES = ("no_interaction", "conversation", "disagreement")


def _result(feasibility, weights, reason):
    return {
        "feasibility": feasibility,
        "allowed_outcomes": list(weights),
        "weights": weights,
        "reasons": [reason],
    }


def _episode_constraints(episode, entities):
    if not isinstance(episode, dict):
        return None
    participants = episode.get("participants")
    window = episode.get("window")
    places = episode.get("allowed_places")
    if (
        not isinstance(participants, list)
        or len(participants) != 2
        or any(not isinstance(p, str) or not p.strip() or p not in entities for p in participants)
        or participants[0] == participants[1]
        or not isinstance(window, list)
        or len(window) != 2
        or any(type(t) is not int for t in window)
        or window[0] >= window[1]
        or not isinstance(places, dict)
        or set(places) != set(participants)
    ):
        return None
    for participant in participants:
        allowed = places[participant]
        if not isinstance(allowed, list) or not allowed:
            return None
        if any(not isinstance(place, str) or not place.strip() for place in allowed):
            return None
    return participants, window, set(places[participants[0]]) & set(places[participants[1]])


def evaluate_episode(npc, episode_id):
    """Return possibilities only; even 'impossible' does not commit a negative.

    A nonempty intersection permits, but never establishes, an encounter.
    Missing/invalid constraints fail closed. Only explicitly earlier, resolved
    episodes of the same pair influence weights. A prior disagreement adds one
    to disagreement weight (once, not once per inquiry or historical record).
    No latent event, location, relationship change or winning outcome is stored.
    """
    unresolved = lambda reason: _result("unresolved", {}, reason)
    if (
        not isinstance(npc, dict)
        or type(npc.get("version")) is not int
        or npc["version"] != 1
        or any(not isinstance(npc.get(k), dict) for k in ("entities", "episodes", "resolutions"))
        or not isinstance(episode_id, str)
        or not episode_id.strip()
    ):
        return unresolved("invalid_npc_state")
    entities, episodes, resolutions = (npc[k] for k in ("entities", "episodes", "resolutions"))
    constraints = _episode_constraints(episodes.get(episode_id), entities)
    if constraints is None:
        return unresolved("missing_or_invalid_episode_constraints")
    participants, window, overlap = constraints
    irritability = []
    for participant in participants:
        entity = entities[participant]
        value = entity.get("irritability") if isinstance(entity, dict) else None
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            return unresolved("missing_or_invalid_disposition")
        irritability.append(value)

    prior_disagreement = False
    for resolved_id, resolution in resolutions.items():
        prior = _episode_constraints(episodes.get(resolved_id), entities)
        if (
            prior is None
            or not isinstance(resolution, dict)
            or resolution.get("outcome") not in OUTCOMES
            or (not prior[2] and resolution["outcome"] != "no_interaction")
        ):
            return unresolved("invalid_or_contradictory_resolution")
        if (
            resolved_id != episode_id
            and set(prior[0]) == set(participants)
            and prior[1][1] <= window[0]
            and resolution["outcome"] == "disagreement"
        ):
            prior_disagreement = True

    if episode_id in resolutions:
        # Report established truth without offering a new distribution.
        result = _result("resolved", {}, "already_resolved")
        result["allowed_outcomes"] = [resolutions[episode_id]["outcome"]]
        return result
    if not overlap:
        return _result("impossible", {"no_interaction": 1.0}, "disjoint_allowed_places")
    return _result(
        "possible",
        {
            "no_interaction": 1.0,
            "conversation": 3.0,
            "disagreement": 1.0 + sum(irritability) + int(prior_disagreement),
        },
        "prior_disagreement_bias" if prior_disagreement else "compatible_constraints",
    )


def evaluate_transition(npc, policy_id):
    """Pure fixed-policy proposal; committed history is input, not a causal claim."""
    result = {"status": "unresolved", "policy_id": policy_id, "reasons": []}
    policy = NPC_TRANSITION_POLICY
    if (
        not isinstance(policy, dict)
        or set(policy) != {"policy_id", "entity_id", "episode_id", "required_outcome", "attribute", "value"}
        or any(not isinstance(policy[k], str) or not policy[k].strip()
               for k in ("policy_id", "entity_id", "episode_id"))
        or policy["required_outcome"] != "disagreement" or policy["attribute"] != "irritability"
        or type(policy["value"]) not in (int, float) or not 0 <= policy["value"] <= 1
        or not math.isfinite(policy["value"])
    ):
        result["reasons"] = ["invalid_policy"]
        return result
    if not isinstance(policy_id, str) or policy_id != policy["policy_id"]:
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
    previous = npc["entities"][policy["entity_id"]]["irritability"]
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
