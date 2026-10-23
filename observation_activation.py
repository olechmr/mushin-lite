"""External observation composition, independent of the CLI and presentation."""
from copy import deepcopy
from canon import commit_observation
from collapse import resolve_observation_candidates
from observation_rules import observation_candidates


def activate_observation(state, room_id, observation_id, verb, world_inputs, rng=None):
    basis, configuration = deepcopy(state), deepcopy(world_inputs)
    try:
        candidates, _, _ = observation_candidates(state, room_id, observation_id, verb, world_inputs)
        discovery_id = resolve_observation_candidates(candidates, rng)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        return {"version": 1, "status": "rejected", "reason": str(error),
                "facts": [], "rule_block_text": None}
    proposal = {"version": 1, "room_id": room_id, "observation_id": observation_id,
                "verb": verb, "discovery_id": discovery_id, "basis": basis,
                "configuration_basis": configuration}
    return commit_observation(state, proposal, world_inputs)
