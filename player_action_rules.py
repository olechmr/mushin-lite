"""Pure ordinary-action authorization. No proposal producer or persistence calls."""
import json

from canon import fact_slot
from world import build_entity_state, build_world_state, interaction_supported, action_already_satisfied

POLICY = "player_action_v1"
ACTIONS = {"take", "drop", "open", "close", "light", "extinguish", "move"}


def _identity(value):
    return (isinstance(value, str) and value == value.strip().lower()
            and bool(value) and value not in {"none", "unknown"}
            and all(c.isalnum() or c in " _-" for c in value))


def _json(value):
    # Typed JSON comparison (True must not compare equal to version/id 1).
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))


def validate_action_inputs(state, world_inputs):
    """Reject malformed storage/configuration rather than manufacture defaults."""
    if not isinstance(state, dict) or not isinstance(state.get("facts"), list):
        raise ValueError("Invalid canonical state")
    ids = []
    for fact in state["facts"]:
        if (not isinstance(fact, dict) or type(fact.get("id")) is not int
                or fact["id"] < 1 or not isinstance(fact.get("text"), str)
                or not fact["text"].strip()
                or fact.get("type", "state") not in {"state", "event", "collapse", "trait"}
                or fact.get("status", "active") not in {"active", "superseded", "resolved"}):
            raise ValueError("Invalid canonical fact")
        ids.append(fact["id"])
    if (len(ids) != len(set(ids)) or type(state.get("next_fact_id")) is not int
            or state["next_fact_id"] <= max(ids, default=0)):
        raise ValueError("Invalid canonical fact allocation")
    if (not isinstance(world_inputs, dict)
            or set(world_inputs) != {"policy", "entities", "exits"}
            or world_inputs["policy"] != POLICY
            or not isinstance(world_inputs["entities"], dict)
            or not isinstance(world_inputs["exits"], dict)):
        raise ValueError("Invalid installed action configuration")
    for entity, definition in world_inputs["entities"].items():
        if (not _identity(entity) or not isinstance(definition, dict)
                or not isinstance(definition.get("interactions"), list)
                or any(not isinstance(a, str) for a in definition["interactions"])
                or len(set(definition["interactions"])) != len(definition["interactions"])):
            raise ValueError("Invalid installed entity definition")
    for room, exits in world_inputs["exits"].items():
        if (not _identity(room) or not isinstance(exits, dict)
                or any(not _identity(d) or not _identity(dest) for d, dest in exits.items())):
            raise ValueError("Invalid installed exits")
    _json(state)
    _json(world_inputs)


def authorized_action_effects(state, action, target, world_inputs):
    """Specify the complete permitted effects under the bounded policy.

    This is an authorization specification, not a call to interpretation/rules
    processing. Eligibility uses the same pure predicate as the upstream gate.
    """
    validate_action_inputs(state, world_inputs)
    if not isinstance(action, str) or action not in ACTIONS or not _identity(target):
        raise ValueError("Unsupported action or noncanonical target")
    relevant = {"whereabouts:player", "world_state:passage"}
    if action != "move":
        relevant.update(f"{category}:{target}" for category in
                        ("whereabouts", "open_state", "light_state", "broken_state"))
    seen = set()
    for fact in state["facts"]:
        if fact.get("status", "active") == "active" and fact.get("type", "state") == "state":
            slot = fact_slot(fact["text"], "state")
            if slot in relevant:
                if slot in seen:
                    raise ValueError("Ambiguous canonical state slot")
                seen.add(slot)
    entities = build_entity_state(state["facts"])
    world = build_world_state(state["facts"])
    player_location = entities.get("player", {}).get("whereabouts")
    room = (player_location[len("in the "):] if isinstance(player_location, str)
            and player_location.startswith("in the ") else None)

    def block(text):
        return [{"type": "event", "text": text}], text

    if action == "move":
        if world.get("passage") == "unavailable":
            return block("The player tried to move, but the passage is unavailable.")
        if not room:
            return block("The player tried to move, but their current location is unknown.")
        destination = world_inputs["exits"].get(room, {}).get(target)
        if not destination:
            return block("The player tried to move, but no exit is established in that direction.")
        return [{"type": "state", "text": f"The player is in the {destination}."}], None

    obj = entities.get(target)
    if (target == "player" or obj is None or not interaction_supported(
            target, action, obj, player_location, world_inputs["entities"])):
        raise ValueError("Action is not independently eligible")
    if action == "take" and action_already_satisfied(action, obj):
        return block(f"The player is already holding the {target}.")
    if action == "open" and action_already_satisfied(action, obj):
        return block(f"The {target} is already open.")
    if action == "close" and action_already_satisfied(action, obj):
        return block(f"The {target} is already closed.")
    if action == "open" and obj.get("broken_state") == "broken":
        return block(f"The player tried to open the {target}, but it is broken.")
    if action == "light" and action_already_satisfied(action, obj):
        return block(f"The {target} is already lit.")
    if action == "extinguish" and action_already_satisfied(action, obj):
        return block(f"The {target} is already extinguished.")

    verb, text = {
        "take": ("picked up", f"The player is holding the {target}."),
        "drop": ("dropped", f"The {target} is in the {room}."),
        "open": ("opened", f"The {target} is open."),
        "close": ("closed", f"The {target} is closed."),
        "light": ("lit", f"The {target} is lit."),
        "extinguish": ("extinguished", f"The {target} is not lit."),
    }[action]
    effects = [{"type": "event", "text": f"The player {verb} the {target}."},
               {"type": "state", "text": text}]
    if action == "drop" and obj.get("open_state") == "open":
        effects.append({"type": "state", "text": f"The {target} is closed."})
    if target == "door" and action in {"open", "close"}:
        effects.append({"type": "state", "text": "The passage is " +
                        ("available." if action == "open" else "unavailable.")})
    return effects, None


def validate_player_action(state, proposal, world_inputs):
    """Authorize exact effects against fresh canon and separately trusted inputs."""
    if (not isinstance(proposal, dict) or set(proposal) != {
            "version", "action", "target", "effects", "basis", "configuration_basis"}
            or type(proposal["version"]) is not int or proposal["version"] != 1):
        raise ValueError("Malformed action proposal")
    if (not isinstance(proposal["basis"], dict)
            or not isinstance(proposal["configuration_basis"], dict)
            or not isinstance(proposal["effects"], list)
            or any(not isinstance(effect, dict) or set(effect) != {"type", "text"}
                   or not isinstance(effect["type"], str)
                   or not isinstance(effect["text"], str)
                   for effect in proposal["effects"])):
        raise ValueError("Malformed action effects")
    if _json(proposal["basis"]) != _json(state):
        raise ValueError("Stale canonical basis")
    if _json(proposal["configuration_basis"]) != _json(world_inputs):
        raise ValueError("Stale configuration basis")
    effects, block = authorized_action_effects(state, proposal["action"], proposal["target"], world_inputs)
    if _json(proposal["effects"]) != _json(effects):
        raise ValueError("Unauthorized or incomplete action effects")
    return effects, block
