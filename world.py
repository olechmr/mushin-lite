from canon import fact_slot

def slot_value(slot, text):

    text = text.strip().rstrip(".")

    if slot.startswith("whereabouts:"):

        if " is on the ground" in text:
            return "on the ground"

        if text.lower().startswith((
            "the player is holding ",
            "player is holding ",
            "the user is holding ",
            "user is holding ",
        )):
            return "held by player"

        if " is in the " in text:
            location = text.split(" is in the ", 1)[1]
            return f"in the {location}"

    if slot.startswith("open_state:"):

        if text.lower().endswith(" is open"):
            return "open"

        if text.lower().endswith(" is closed"):
            return "closed"

    if slot.startswith("broken_state:"):

        if text.lower().endswith(" is broken"):
            return "broken"

    if slot.startswith("inverted_state:"):

        if text.endswith(" is inside out"):
            return "inside out"

    if slot.startswith("light_state:"):

        if text.lower().endswith(" is not lit"):
            return "not lit"

        if text.lower().endswith(" is lit"):
            return "lit"

    return text

def build_object_state(facts):

    objects = {}

    for fact in facts:

        if fact.get("status", "active") != "active":
            continue

        if fact.get("type", "state") != "state":
            continue

        slot = fact_slot(
            fact["text"],
            fact.get("type", "state")
        )

        if slot is None:
            continue

        if ":" not in slot:
            continue

        category, obj = slot.split(":", 1)
        value = slot_value(slot, fact["text"])

        if category == "world_state":
            continue

        if obj not in objects:
            objects[obj] = {}

        objects[obj][category] = value

    return objects

def build_world_state(facts):

    world_state = {}

    for fact in facts:

        if fact.get("status", "active") != "active":
            continue

        if fact.get("type", "state") != "state":
            continue

        slot = fact_slot(
            fact["text"],
            fact.get("type", "state")
        )

        if not slot:
            continue

        if not slot.startswith("world_state:"):
            continue

        name = slot.split(":", 1)[1]

        text = fact["text"].strip().rstrip(".")

        if " is unavailable" in text.lower():
            value = "unavailable"
        elif " is available" in text:
            value = "available"
        elif text.endswith(" is illuminated"):
            value = "illuminated"
        elif text.endswith(" is dark"):
            value = "dark"
        else:
            value = text

        world_state[name] = value

    return world_state

def objects_in_room(objects, room_name):

    present = []

    for obj, data in objects.items():

        whereabouts = data.get("whereabouts")

        if whereabouts == f"in the {room_name}":
            present.append(obj)

    return sorted(present)


def build_entity_state(facts):
    return build_object_state(facts)


def entities_in_room(entities, room_name):
    return objects_in_room(entities, room_name)

ENTITY_DEFINITIONS = {
    "book": {
        "display_name": "Book",
        "tags": ["portable", "readable"],
        "interactions": ["take", "drop", "open", "close"],
        "icon": "📖",
    },
    "lantern": {
        "display_name": "Lantern",
        "tags": ["portable", "light_source"],
        "interactions": ["take", "drop", "light", "extinguish"],
        "icon": "🏮",
    },
    "brass key": {
        "interactions": ["take", "drop"],
    },
    "letter opener": {
        "interactions": ["take", "drop"],
    },
    "ink bottle": {
        "interactions": ["take", "drop"],
    },
    "player": {
        "display_name": "Player",
        "tags": ["player"],
        "interactions": [],
        "icon": "🙂",
    },
}

def get_entity_data(entity_id, entity_state=None):
    definition = ENTITY_DEFINITIONS.get(entity_id, {})

    return {
        "id": entity_id,
        "display_name": definition.get(
            "display_name",
            entity_id.replace("_", " ").title()
        ),
        "state": entity_state or {},
        "tags": definition.get("tags", []),
        "interactions": definition.get("interactions", []),
        "icon": definition.get("icon"),
    }

def resolve_entity_reference(reference, entities, player_whereabouts):
    if not isinstance(reference, str):
        return None

    reference = reference.strip().lower()

    if reference in ("", "none", "unknown"):
        return None

    player_room_known = (
        isinstance(player_whereabouts, str)
        and player_whereabouts.startswith("in the ")
        and bool(player_whereabouts[len("in the "):].strip())
    )

    accessible = [
        entity_id
        for entity_id, entity_state in entities.items()
        if entity_id != "player"
        and (
            entity_state.get("whereabouts") == "held by player"
            or (
                player_room_known
                and entity_state.get("whereabouts") == player_whereabouts
            )
        )
    ]

    if reference in entities or reference in ENTITY_DEFINITIONS:
        return reference if reference in accessible else None

    reference_tokens = reference.split()
    matches = [
        entity_id
        for entity_id in accessible
        if entity_id.split()[-len(reference_tokens):] == reference_tokens
    ]

    return matches[0] if len(matches) == 1 else None


def interaction_supported(entity_id, action, entity_state=None, player_whereabouts=None):
    definition = ENTITY_DEFINITIONS.get(entity_id, {})
    interactions = definition.get("interactions", [])

    if action not in interactions:
        return False

    entity_state = entity_state or {}
    whereabouts = entity_state.get("whereabouts")

    if action in ("open", "close") and entity_state.get("open_state") not in ("open", "closed"):
        return False

    if action in ["take", "open", "close"]:
        if whereabouts == "held by player":
            return True

        return (
            isinstance(whereabouts, str)
            and whereabouts.startswith("in the ")
            and bool(whereabouts[len("in the "):].strip())
            and whereabouts == player_whereabouts
        )

    if action == "drop":
        return (
            whereabouts == "held by player"
            and isinstance(player_whereabouts, str)
            and player_whereabouts.startswith("in the ")
            and bool(player_whereabouts[len("in the "):].strip())
        )

    if action == "extinguish":
        return (
            whereabouts == "held by player"
            and entity_state.get("light_state") in ("lit", "not lit")
        )

    if action == "light":
        return (
            whereabouts == "held by player"
            and entity_state.get("light_state") in ("lit", "not lit")
        )

    return True