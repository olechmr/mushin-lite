"""Pure observation authorization against separately installed definitions."""
import json
import math
from string import Formatter

from canon import fact_slot, normalize_fact
from world import build_entity_state

POLICY = "observation_v1"


def snapshot_key(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))


def identity(value):
    return (isinstance(value, str) and bool(value) and value == value.strip()
            and value not in {"none", "unknown"}
            and all(c.isalnum() or c in "_-" for c in value))


def string_list(value):
    return (isinstance(value, list) and all(isinstance(v, str) and v for v in value)
            and len(value) == len(set(value)))


def validate_observation_state(state):
    if not isinstance(state, dict) or not isinstance(state.get("facts"), list):
        raise ValueError("Invalid canonical state")
    ids = []
    for fact in state["facts"]:
        if (not isinstance(fact, dict) or type(fact.get("id")) is not int or fact["id"] < 1
                or not isinstance(fact.get("text"), str) or not fact["text"].strip()
                or fact.get("type", "state") not in {"state", "event", "collapse", "trait"}
                or fact.get("status", "active") not in {"active", "resolved", "superseded"}):
            raise ValueError("Invalid canonical fact")
        ids.append(fact["id"])
    if (len(ids) != len(set(ids)) or type(state.get("next_fact_id")) is not int
            or state["next_fact_id"] <= max(ids, default=0)):
        raise ValueError("Invalid fact allocation")
    snapshot_key(state)


def observation_candidates(state, room_id, observation_id, verb, world_inputs):
    """Validate the binding and return eligible reveals, without selecting one.

    Configuration shape: policy, rooms (installed room dictionaries), discoveries.
    Optional descriptive/cause metadata never establishes additional effects.
    """
    validate_observation_state(state)
    if not identity(room_id) or not identity(observation_id) or verb not in ("search", "inspect"):
        raise ValueError("Invalid observation identity or verb")
    if (not isinstance(world_inputs, dict)
            or set(world_inputs) != {"policy", "rooms", "discoveries"}
            or world_inputs["policy"] != POLICY
            or not isinstance(world_inputs["rooms"], dict)
            or not isinstance(world_inputs["discoveries"], list)):
        raise ValueError("Invalid installed observation configuration")
    snapshot_key(world_inputs)
    binding = None
    ids = set()
    for installed_room, room in world_inputs["rooms"].items():
        if not identity(installed_room) or not isinstance(room, dict):
            raise ValueError("Invalid installed room")
        spaces = room.get("observations", [])  # A room may explicitly have no spaces.
        if not isinstance(spaces, list):
            raise ValueError("Invalid observation spaces")
        for space in spaces:
            if (not isinstance(space, dict) or not identity(space.get("id"))
                    or space["id"] in ids or not string_list(space.get("verbs"))
                    or any(v not in ("search", "inspect") for v in space["verbs"])
                    or not isinstance(space.get("constraints"), dict)
                    or set(space["constraints"]) != {"required_tags"}
                    or not string_list(space["constraints"]["required_tags"])):
                raise ValueError("Invalid or duplicate observation definition")
            ids.add(space["id"])
            if installed_room == room_id and space["id"] == observation_id:
                binding = space
    if binding is None or verb not in binding["verbs"]:
        raise ValueError("Unauthorized observation binding")
    active = [f for f in state["facts"] if f.get("status", "active") == "active"]
    locations = [f for f in active if fact_slot(f["text"], f.get("type", "state")) == "whereabouts:player"]
    if (len(locations) != 1 or build_entity_state(locations).get("player", {}).get("whereabouts")
            != f"in the {room_id}"):
        raise ValueError("Player is not unambiguously in the observation room")

    marker = f"The search space {observation_id}:{verb} collapsed."
    collapsed = any(f.get("type") == "collapse" and normalize_fact(f["text"]) == normalize_fact(marker)
                    for f in active)
    candidates = []
    discovery_ids = set()
    for discovery in world_inputs["discoveries"]:
        if (not isinstance(discovery, dict) or not identity(discovery.get("id"))
                or discovery["id"] in discovery_ids or not string_list(discovery.get("tags"))
                or not string_list(discovery.get("verbs"))
                or any(v not in ("search", "inspect") for v in discovery["verbs"])):
            raise ValueError("Invalid or duplicate discovery")
        discovery_ids.add(discovery["id"])
        weight = discovery.get("weight", 1.0)
        if type(weight) not in (int, float) or not math.isfinite(weight) or weight < 0:
            raise ValueError("Invalid discovery weight")
        reveal = discovery.get("reveal")
        if (not isinstance(reveal, dict) or set(reveal) != {"type", "text"}
                or reveal["type"] not in ("state", "event")
                or not isinstance(reveal["text"], str) or not reveal["text"].strip()):
            raise ValueError("Invalid discovery reveal")
        for _, field, spec, conversion in Formatter().parse(reveal["text"]):
            if field is not None and (field != "room_id" or spec or conversion):
                raise ValueError("Unsupported reveal template")
        text = reveal["text"].format(room_id=room_id)
        if verb not in discovery["verbs"] or not all(t in discovery["tags"] for t in binding["constraints"]["required_tags"]):
            continue
        slot = fact_slot(text, reveal["type"])
        if slot is not None and slot.startswith("whereabouts:") and any(
                fact_slot(f["text"], f.get("type", "state")) == slot for f in active):
            continue
        if any(normalize_fact(f["text"]) == normalize_fact(text)
               and (reveal["type"] != "state" or f.get("type", "state") == "state") for f in active):
            continue
        candidates.append({"id": discovery["id"], "weight": weight,
                           "reveal": {"type": reveal["type"], "text": text}})
    if collapsed:
        return [], marker, True
    total = sum(c["weight"] for c in candidates)
    if candidates and (not math.isfinite(total) or total <= 0):
        raise ValueError("No positive eligible observation weight")
    return candidates, marker, False


def validate_observation(state, proposal, world_inputs):
    fields = {"version", "room_id", "observation_id", "verb", "discovery_id", "basis", "configuration_basis"}
    if (not isinstance(proposal, dict) or set(proposal) != fields
            or type(proposal["version"]) is not int or proposal["version"] != 1
            or not isinstance(proposal["basis"], dict)
            or not isinstance(proposal["configuration_basis"], dict)):
        raise ValueError("Malformed observation proposal")
    if snapshot_key(proposal["basis"]) != snapshot_key(state):
        raise ValueError("Stale canonical basis")
    if snapshot_key(proposal["configuration_basis"]) != snapshot_key(world_inputs):
        raise ValueError("Stale observation configuration")
    candidates, marker, collapsed = observation_candidates(
        state, proposal["room_id"], proposal["observation_id"], proposal["verb"], world_inputs)
    selected = proposal["discovery_id"]
    if selected is None:
        if collapsed or not candidates:
            return []
        raise ValueError("Null outcome cannot replace an eligible discovery")
    if not identity(selected) or collapsed:
        raise ValueError("Invalid selection or already collapsed observation")
    candidate = next((c for c in candidates if c["id"] == selected and c["weight"] > 0), None)
    if candidate is None:
        raise ValueError("Discovery is not independently eligible")
    return [candidate["reveal"], {"type": "collapse", "text": marker}]
