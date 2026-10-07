import json
from world import build_entity_state

ACTION_ALIASES = {
    "go": "move",
    "walk": "move",
    "enter": "move",

    "pickup": "take",
    "pick": "take",
    "pick up": "take",
    "grab": "take",
    "acquire": "take",

    "put down": "drop",
    "discard": "drop",
    "set down": "drop",
    "place down": "drop",

    "ignite": "light",
    "lit": "light",
    "activate": "light",
    "turn on": "light",
    "on": "light",

    "put out": "extinguish",
    "douse": "extinguish",
    "snuff": "extinguish",
    "turn off": "extinguish",
    "off": "extinguish",
}

SPLIT_ACTION_PHRASES = {
    ("set", "down"): "set down",
    ("place", "down"): "place down",
}

def current_player_room(facts):
    whereabouts = build_entity_state(facts).get("player", {}).get("whereabouts")

    if (
        isinstance(whereabouts, str)
        and whereabouts.startswith("in the ")
        and bool(whereabouts[len("in the "):].strip())
    ):
        return whereabouts[len("in the "):]

    return None

def recover_intent_json(packet):
    intent = packet.get("intent", "")

    if not isinstance(intent, str):
        return packet

    text = intent.strip()

    if not text.startswith("{"):
        return packet

    try:
        recovered = json.loads(text)
    except json.JSONDecodeError:
        return packet

    if not isinstance(recovered, dict):
        return packet

    action = recovered.get("action")
    target = recovered.get("target")

    if action and target:
        packet["action"] = action
        packet["target"] = target
        packet["intent"] = recovered.get("intent", intent)
        packet["confidence"] = recovered.get("confidence", packet.get("confidence", "medium"))

    return packet

def normalize_packet(packet):
    packet = dict(packet)
    packet = recover_embedded_packet(packet)

    action = packet.get("action", "").lower().strip()
    intent = packet.get("intent", "").lower().strip()
    target = packet.get("target", "").lower().strip()

    action = SPLIT_ACTION_PHRASES.get((action, intent), action)
    action = ACTION_ALIASES.get(action, action)
    packet["action"] = action

    for direction in ["north", "south", "east", "west"]:

        if target == f"{direction}_room":
            packet["target"] = direction
            target = direction

        elif target == f"{direction}ward":
            packet["target"] = direction
            target = direction

        if target == "lantern" and action in ("light", "none", "unknown", "use"):
            if (
                action in ["light", "lit", "ignite", "activate", "on", "turn on"]
                or "light" in intent
                or "ignite" in intent
                or "illuminate" in intent
                or "turn on" in intent
            ):
                packet["action"] = "light"
                return packet

        if action in ("extinguish", "none", "unknown", "use") and (
            action in ["extinguish", "put out", "snuff", "douse", "off", "turn off"]
            or "extinguish" in intent
            or "put out" in intent
            or "not lit" in intent
            or "turn off" in intent
        ):
            packet["action"] = "extinguish"
            return packet

    if action == "go":
        packet["action"] = "move"
        action = "move"

    if action == "use":

        if any(word in intent for word in [
            "open",
            "activate"
        ]):
            packet["action"] = "open"

        elif any(word in intent for word in [
            "close",
            "fold",
            "collapse"
        ]):
            packet["action"] = "close"

    if action in ["none", "unknown"]:

        if "open" in intent:
            packet["action"] = "open"

        elif "close" in intent:
            packet["action"] = "close"

        elif "break" in intent or "destroy" in intent:
            packet["action"] = "break"

        elif "use" in intent and "broken" in intent:
            packet["action"] = "open"

    if action in ["put out", "douse", "snuff"]:
        packet["action"] = "extinguish"

    elif (
        action in ["none", "unknown", "use"]
        and ("extinguish" in intent or "put out" in intent or "not lit" in intent)
    ):
        packet["action"] = "extinguish"

    return packet

def has_active_fact(facts, text):
    text = text.lower().strip().rstrip(".")

    for fact in facts:
        if fact.get("status", "active") != "active":
            continue

        fact_text = fact.get("text", "").lower().strip().rstrip(".")

        if fact_text == text:
            return True

    return False

def facts_from_packet(packet, facts=None):

    facts = facts or []

    action = packet.get("action", "").lower().strip()
    target = packet.get("target", "").lower().strip()
    intent = packet.get("intent", "").lower().strip()

    if action == "use":

        if has_active_fact(facts, f"The {target} is open"):
            action = "close"

        elif has_active_fact(facts, f"The {target} is closed"):
            action = "open"

        else:
            action = "open"

    if not action or not target:
        return []

    if action in ["none", "unknown"] or target in ["none", "unknown"]:
        return []

    candidates = []

    if action in ["take", "pick up", "grab"]:
        candidates.append({"type": "event", "text": f"The player picked up the {target}."})
        candidates.append({"type": "state", "text": f"The player is holding the {target}."})

    elif action in ["drop", "put down"]:
        room = current_player_room(facts)

        candidates.append({"type": "event", "text": f"The player dropped the {target}."})

        if room:
            candidates.append({"type": "state", "text": f"The {target} is in the {room}."})
        else:
            candidates.append({"type": "state", "text": f"The {target} is on the ground."})

    elif action == "open":
        candidates.append({"type": "event", "text": f"The player opened the {target}."})
        candidates.append({"type": "state", "text": f"The {target} is open."})

    elif action == "close":
        candidates.append({"type": "event", "text": f"The player closed the {target}."})
        candidates.append({"type": "state", "text": f"The {target} is closed."})

    elif action == "break":
        candidates.append({"type": "event", "text": f"The player broke the {target}."})
        candidates.append({"type": "state", "text": f"The {target} is broken."})

    elif action in ["invert", "turn inside out"]:
        candidates.append({"type": "event", "text": f"The player turned the {target} inside out."})
        candidates.append({"type": "state", "text": f"The {target} is inside out."})

    elif action == "extinguish":
        candidates.append({"type": "event", "text": f"The player extinguished the {target}."})
        candidates.append({"type": "state", "text": f"The {target} is not lit."})

    elif action == "light":
        candidates.append(
            {
                "type": "event",
                "text": f"The player lit the {target}."
            }
        )
        candidates.append(
            {
                "type": "state",
                "text": f"The {target} is lit."
            }
        )

    elif action == "extinguish":
        candidates.append(
            {
                "type": "event",
                "text": f"The player extinguished the {target}."
            }
        )
        candidates.append(
            {
                "type": "state",
                "text": f"The {target} is not lit."
            }
        )

    elif action == "move":
        pass

    return candidates

def recover_embedded_packet(packet):
    def is_missing(value):
        return value is None or (
            isinstance(value, str)
            and value.strip().lower() in ("", "none", "unknown")
        )

    action_missing = is_missing(packet.get("action"))
    target_missing = is_missing(packet.get("target"))

    if not action_missing and not target_missing:
        return packet

    intent = packet.get("intent", "")

    if isinstance(intent, str):
        text = intent.strip()

        if text.startswith("{"):
            try:
                recovered = json.loads(text)

                if isinstance(recovered, dict):
                    action = recovered.get("action")
                    target = recovered.get("target")

                    if action and target:
                        filled = False

                        if action_missing and not is_missing(action):
                            packet["action"] = action
                            filled = True

                        if target_missing and not is_missing(target):
                            packet["target"] = target
                            filled = True

                        if filled:
                            packet["intent"] = recovered.get("intent", intent)
                            if is_missing(packet.get("confidence")):
                                packet["confidence"] = recovered.get(
                                    "confidence",
                                    packet.get("confidence", "medium")
                                )

                        return packet

            except json.JSONDecodeError:
                pass

    intent = packet.get("intent", "")

    if not isinstance(intent, str):
        return packet

    recovered = dict(packet)

    if '"target": "umbrella"' in intent:
        recovered["target"] = "umbrella"

    if '"action": "open"' in intent:
        recovered["action"] = "open"

    if (
        '"action": "move"' in intent
        or '"action": "go"' in intent
    ):
        recovered["action"] = "move"

    if '"target": "north"' in intent:
        recovered["target"] = "north"

    elif '"target": "south"' in intent:
        recovered["target"] = "south"

    elif '"action": "close"' in intent:
        recovered["action"] = "close"

    elif '"action": "break"' in intent:
        recovered["action"] = "break"

    for obj in ["umbrella", "book", "door", "lantern"]:
        if f'"target": "{obj}"' in intent:
            recovered["target"] = obj

    for act in ["open", "close", "take", "drop", "break", "light", "extinguish", "move"]:
        if f'"action": "{act}"' in intent:
            recovered["action"] = act

    if not action_missing:
        recovered["action"] = packet["action"]

    if not target_missing:
        recovered["target"] = packet["target"]

    return recovered
