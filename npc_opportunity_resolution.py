"""Resolve explicit opportunity possibilities; never invoke their producer."""
from copy import deepcopy
import random

from npc_opportunity_rules import validate_opportunity_possibilities

_opportunity_rng = random.Random()


def resolve_npc_opportunity(npc, npc_id, possibilities, rng=None):
    validate_opportunity_possibilities(npc, npc_id, possibilities)
    candidates = possibilities["candidates"]
    sampled = len(candidates) > 1
    selected = candidates[0]
    if sampled:
        roll = (rng if rng is not None else _opportunity_rng).random()
        if type(roll) not in (int, float) or not 0 <= roll < 1:
            raise ValueError("invalid_opportunity_random_draw")
        threshold = roll * sum(c["weight"] for c in candidates)
        cumulative = 0.0
        selected = candidates[-1]  # finite rounding at the upper endpoint
        for candidate in candidates:
            cumulative += candidate["weight"]
            if threshold < cumulative:
                selected = candidate
                break
    return {"version": 1, "status": "proposed", "npc_id": npc_id,
            "window_id": possibilities["window_id"], "choice": selected["kind"],
            "episode_id": selected["episode_id"], "sampled": sampled,
            "possibilities": deepcopy(possibilities)}
