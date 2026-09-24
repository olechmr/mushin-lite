from world import build_entity_state, entities_in_room, get_entity_data
from collapse import is_observation_collapsed
import map_data
import json

def build_presentation_context(user_input, packet, facts):
    entities = build_entity_state(facts)

    player = entities.get("player", {})
    whereabouts = player.get("whereabouts")

    if not whereabouts or not whereabouts.startswith("in the "):
        room = None
    else:
        room = whereabouts[len("in the "):]

    present = []
    exits = {}

    room_obj = None

    if room:
        present_ids = [
            entity for entity in entities_in_room(entities, room)
            if entity != "player"
        ]

        present = [
            get_entity_data(entity_id, entities.get(entity_id, {}))
            for entity_id in present_ids
        ]

        exits = map_data.EXITS.get(room, {})

        room_obj = map_data.get_room_data(room)

    return {
        "user_input": user_input,
        "action": packet.get("action", ""),
        "target": packet.get("target", ""),

        # Transitional fields
        "room_id": room,
        "room": room_obj,

        "entities": present,
        "exits": exits,
        "facts": facts,
    }

def entity_base_name(entity):
    return entity.get("display_name", entity.get("id", "Unknown"))


def entity_status(entity):
    state = entity.get("state", {})

    if state.get("light_state") in ["lit", "not lit"]:
        return state["light_state"]

    if state.get("open_state") in ["open", "closed"]:
        return state["open_state"]

    return None


def entity_display_name(entity):
    name = entity_base_name(entity)
    status = entity_status(entity)

    if status:
        return f"{name} ({status})"

    return name

def format_presentation(ctx):
    data = {}

    room = ctx.get("room")
    room_id = ctx.get("room_id")

    room_name = room.get("display_name", room_id) if room else room_id

    action = ctx["action"]
    target = ctx["target"]

    if not room_id:
        return {
            "movement": "You are somewhere uncertain."
        }

    if action in ["go", "move", "walk", "enter"]:
        data["movement"] = f"You are in the {room_name}."
    elif action == "take":
        data["movement"] = f"You take the {target}."
    elif action == "drop":
        data["movement"] = f"You drop the {target}."
    elif action == "open":
        data["movement"] = f"You open the {target}."
    elif action == "close":
        data["movement"] = f"You close the {target}."
    elif action == "light":
        data["movement"] = f"You light the {target}."
    elif action == "extinguish":
        data["movement"] = f"You extinguish the {target}."
    else:
        data["movement"] = f"You act: {ctx['user_input']}"

    entities = ctx["entities"]

    entity_names = [
        entity_display_name(entity)
        for entity in entities
    ]

    if entity_names:
        if len(entity_names) == 1:
            data["objects"] = f"{entity_names[0]} is visible."
        else:
            names = ", ".join(entity_names[:-1]) + f" and {entity_names[-1]}"
            data["objects"] = f"Visible objects are {names}."

    exits = list(ctx["exits"].keys())

    if len(exits) == 1:
        data["exits"] = f"An exit leads {exits[0]}."
    elif len(exits) == 2:
        data["exits"] = f"Exits lead {exits[0]} and {exits[1]}."
    elif len(exits) > 2:
        data["exits"] = "Exits lead " + ", ".join(exits[:-1]) + f", and {exits[-1]}."

    return data


def render_presentation_sentences(presentation):
    lines = []

    for key in ["movement", "description", "objects", "exits"]:
        if key in presentation:
            lines.append(presentation[key])

    return "\n".join(lines)


def render_response(user_input, packet, facts):
    ctx = build_presentation_context(user_input, packet, facts)
    presentation = format_presentation(ctx)
    return render_presentation_sentences(presentation)

def render_room(ctx):
    room = ctx.get("room")
    room_id = ctx.get("room_id")

    if not room_id:
        return "You are somewhere uncertain."

    room_name = room.get("display_name", room_id) if room else room_id

    lines = []

    lines.append(f"ROOM: {room_name}")

    lines.append("")

    present = ctx["entities"]

    if present:
        lines.append("Present:")
        for entity in present:
            name = entity.get("display_name", entity.get("id", "Unknown"))
            lines.append(f"  {name}")
    else:
        lines.append("Present: none")

    observation_spaces = room.get("observations", []) if room else []
    facts = ctx.get("facts", [])

    if observation_spaces:
        lines.append("")
        lines.append("Observation Spaces:")

        for space in observation_spaces:
            observation_id = space.get("id")
            name = space.get(
                "display_name",
                observation_id or "unknown",
            )
            icon = space.get("icon", "")

            verbs = space.get("verbs", [])

            heading = f"{icon} {name}".strip()
            lines.append(f"  {heading}")

            if description := space.get("description", ""):
                lines.append(f"    {description}")

            for verb in verbs:
                status = (
                    "collapsed"
                    if is_observation_collapsed(
                        facts,
                        observation_id,
                        verb,
                    )
                    else "available"
                )

                lines.append(f"    {verb}: {status}")

    lines.append("")
    lines.append("Exits:")

    exits = ctx["exits"]

    if exits:
        for direction in exits:
            lines.append(f"  {direction}")
    else:
        lines.append("  none")

    return "\n".join(lines)

def render_place(room_data):
    if not room_data:
        return "No current room."

    return json.dumps(
        room_data,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )

def render_inventory(entities):
    held = []

    for entity_id, state in entities.items():
        if state.get("whereabouts") == "held by player":
            held.append(get_entity_data(entity_id, state))

    if not held:
        return "Inventory: empty"

    lines = ["Inventory:"]

    for entity in held:
        lines.append(f"  {entity_display_name(entity)}")

    return "\n".join(lines)

def narrate_state(ctx, scene, presentation):
    from llm_adapter import narrate_scene

    narration_payload = {
        "presentation_context": ctx,
        "presentation": presentation,
        "rendered_text": scene,
        "rules": [
            "Rewrite the rendered text in natural prose.",
            "Do not add objects.",
            "Do not add exits.",
            "Do not add furniture.",
            "Do not add room features.",
            "Do not add weather.",
            "Do not add history.",
            "Do not add mood unless present in the context.",
            "Use only facts present in presentation_context, presentation, or rendered_text.",
            "Use the word exits, not paths, routes, choices, options, or ways.",
            "Use plain physical language. Avoid poetic or dramatic phrasing.",
        ],
    }

    return narrate_scene(narration_payload)