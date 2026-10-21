"""Provider-independent episode input and candidate authorization rules.

These validators do not propose, sample, persist, or invoke a provider.
"""
import math
from copy import deepcopy
import npc_fixture
from npc_fixture import SUPPORTED_DISPOSITIONS

OUTCOMES = ("no_interaction", "conversation", "disagreement")


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


def episode_factors(npc, episode_id):
    if (
        not isinstance(npc, dict)
        or type(npc.get("version")) is not int
        or npc["version"] != 1
        or any(not isinstance(npc.get(k), dict) for k in ("entities", "episodes", "resolutions"))
        or not isinstance(episode_id, str)
        or not episode_id.strip()
    ):
        raise ValueError("invalid_npc_state")
    entities, episodes, resolutions = (npc[k] for k in ("entities", "episodes", "resolutions"))
    constraints = _episode_constraints(episodes.get(episode_id), entities)
    if constraints is None:
        raise ValueError("missing_or_invalid_episode_constraints")
    participants, window, overlap = constraints
    dispositions = {attribute: [] for attribute in SUPPORTED_DISPOSITIONS}
    for participant in participants:
        entity = entities[participant]
        for attribute in SUPPORTED_DISPOSITIONS:
            value = entity.get(attribute) if isinstance(entity, dict) else None
            if type(value) not in (int, float) or not 0 <= value <= 1 or not math.isfinite(value):
                raise ValueError("missing_or_invalid_disposition")
            dispositions[attribute].append(value)

    prior_disagreement = False
    for resolved_id, resolution in resolutions.items():
        prior = _episode_constraints(episodes.get(resolved_id), entities)
        if (
            prior is None
            or not isinstance(resolution, dict)
            or resolution.get("outcome") not in OUTCOMES
            or (not prior[2] and resolution["outcome"] != "no_interaction")
        ):
            raise ValueError("invalid_or_contradictory_resolution")
        if (
            resolved_id != episode_id
            and set(prior[0]) == set(participants)
            and prior[1][1] <= window[0]
            and resolution["outcome"] == "disagreement"
        ):
            prior_disagreement = True

    return participants, overlap, dispositions, prior_disagreement


def policy_snapshot(npc, participants):
    if any(npc["entities"][p].get("archetype") != "interaction_v1" for p in participants):
        raise ValueError("missing_or_unknown_archetype")
    registry = npc_fixture.NPC_ARCHETYPES
    config = registry.get("interaction_v1") if isinstance(registry, dict) else None
    expected = {"version": 1, "no_interaction": 1.0, "conversation": 2.5,
                "disagreement": 1.0, "history_bias": 1.0}
    if (not isinstance(config, dict) or config != expected
            or type(config.get("version")) is not int
            or any(type(config[k]) not in (int, float) for k in expected if k != "version")):
        raise ValueError("invalid_archetype_configuration")
    return deepcopy(config)


def validate_possibilities(npc, episode_id, candidate):
    """Check the full envelope against current state and the declared policy.

    Arithmetic here constrains provider output; no winning outcome is chosen.
    """
    participants, overlap, dispositions, prior = episode_factors(npc, episode_id)
    config = policy_snapshot(npc, participants)
    if (not isinstance(candidate, dict) or not isinstance(candidate.get("reasons"), list)
            or any(not isinstance(reason, str) for reason in candidate["reasons"])):
        raise ValueError("invalid_possibilities")
    if (type(candidate.get("version")) is not int or candidate["version"] != 1
            or candidate.get("archetype") != "interaction_v1"
            or candidate.get("episode_id") != episode_id or candidate.get("basis") != npc
            or candidate.get("policy_basis") != config):
        raise ValueError("stale_or_missing_possibility_basis")
    feasibility = "possible" if overlap else "impossible"
    weights = {"no_interaction": config["no_interaction"]}
    if overlap:
        weights.update(conversation=config["conversation"] + sum(dispositions["sociability"]),
                       disagreement=config["disagreement"] + sum(dispositions["irritability"])
                       + config["history_bias"] * int(prior))
    supplied = candidate.get("weights")
    if (episode_id in npc["resolutions"] or candidate.get("feasibility") != feasibility
            or candidate.get("allowed_outcomes") != list(weights)
            or not isinstance(supplied, dict) or supplied != weights
            or any(type(w) not in (int, float) or not math.isfinite(w) for w in supplied.values())):
        raise ValueError("unauthorized_possibilities")
    return feasibility


def validate_resolution(npc, proposal):
    if proposal.get("basis") != npc:
        raise ValueError("Stale or missing NPC proposal basis")
    feasibility = validate_possibilities(npc, proposal["episode_id"], proposal.get("possibilities"))
    candidate = proposal["possibilities"]
    outcome = proposal.get("outcome")
    if (proposal.get("feasibility") != feasibility or proposal.get("reused") is not False
            or outcome not in candidate["allowed_outcomes"]
            or candidate["weights"].get(outcome, 0) <= 0
            or proposal.get("sampled") is not (feasibility == "possible")):
        raise ValueError("Unauthorized NPC resolution proposal")
