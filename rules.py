import map_data
from map_data import add_exit

LAST_RULE = None
LAST_RULE_TYPE = None

def generate_room_name(room, direction):
    return f"{room}_{direction}_room"

def object_is_elsewhere(obj_state, player_location):

    obj_whereabouts = obj_state.get("whereabouts")

    return (
        obj_whereabouts
        and obj_whereabouts.startswith("in the ")
        and player_location
        and obj_whereabouts != player_location
    )

def apply_rules(packet, candidates, world, world_state):

    global LAST_RULE
    global LAST_RULE_TYPE

    LAST_RULE = None
    LAST_RULE_TYPE = None

    action = packet.get("action", "").lower().strip()
    target = packet.get("target", "").lower().strip()
    
    if not action or not target:
        return candidates

    obj_state = world.get(target, {})

    player_location = world.get("player", {}).get("whereabouts")

    if action in [
        "take",
        "inspect",
        "examine",
        "look",
        "open",
        "close",
        "break",
        "light",
        "extinguish"
    ]:

        if object_is_elsewhere(obj_state, player_location):

            LAST_RULE = "object not present"
            LAST_RULE_TYPE = "block"

            return [
                {
                    "type": "event",
                    "text": f"The player tried to {action} the {target}, but it is not here."
                }
            ]

    player_location = world.get("player", {}).get("whereabouts")

    extra_candidates = []

    if action == "take" and obj_state.get("whereabouts") == "held by player":

        LAST_RULE = "already holding"
        LAST_RULE_TYPE = "block"

        return [
            {
                "type": "event",
                "text": f"The player is already holding the {target}."
            }
        ]

    if action == "drop" and obj_state.get("whereabouts") == "on the ground":

        LAST_RULE = "already on ground"
        LAST_RULE_TYPE = "block"

        return [
            {
                "type": "event",
                "text": f"The {target} is already on the ground."
            }
        ]

    if action == "open" and obj_state.get("open_state") == "open":

        LAST_RULE = "already open"
        LAST_RULE_TYPE = "block"        

        return [
            {
                "type": "event",
                "text": f"The {target} is already open."
            }
        ]

    if action == "close" and obj_state.get("open_state") == "closed":

        LAST_RULE = "already closed"
        LAST_RULE_TYPE = "block"

        return [
            {
                "type": "event",
                "text": f"The {target} is already closed."
            }
        ]

    if action == "break" and obj_state.get("open_state") == "open":

        LAST_RULE = "breaking open object closes it"
        LAST_RULE_TYPE = "consequence"

        extra_candidates.append(
            {
                "type": "state",
                "text": f"The {target} is closed."
            }
        )

    if action == "open" and obj_state.get("broken_state") == "broken":

        LAST_RULE = "broken object cannot open"
        LAST_RULE_TYPE = "block"

        return [
            {
                "type": "event",
                "text": f"The player tried to open the {target}, but it is broken."
            }
        ]

    if (
        action == "break"
        and obj_state.get("whereabouts") == "held by player"
    ):

        LAST_RULE = "breaking held object drops it"
        LAST_RULE_TYPE = "consequence"

        extra_candidates.append(
            {
                "type": "state",
                "text": f"The {target} is on the ground."
            }
        )

    if (
        action == "drop"
        and obj_state.get("open_state") == "open"
    ):

        LAST_RULE = "dropping open object closes it"
        LAST_RULE_TYPE = "consequence"

        extra_candidates.append(
            {
                "type": "state",
                "text": f"The {target} is closed."
            }
        )

    if (
        action == "take"
        and obj_state.get("whereabouts") == "on the ground"
    ):

        LAST_RULE = "taking object removes it from ground"
        LAST_RULE_TYPE = "consequence"

    if action == "light" and obj_state.get("light_state") == "lit":

        LAST_RULE = "already lit"
        LAST_RULE_TYPE = "block"

        return [
            {
                "type": "event",
                "text": f"The {target} is already lit."
            }
        ]

    if action == "extinguish" and obj_state.get("light_state") == "not lit":

        LAST_RULE = "already extinguished"
        LAST_RULE_TYPE = "block"

        return [
            {
                "type": "event",
                "text": f"The {target} is already extinguished."
            }
        ]

    if action == "open" and target == "door":

        LAST_RULE = "opening door makes passage available"
        LAST_RULE_TYPE = "consequence"

        extra_candidates.append(
            {
                "type": "state",
                "text": "The passage is available."
            }
        )

    if action == "close" and target == "door":

        LAST_RULE = "closing door makes passage unavailable"
        LAST_RULE_TYPE = "consequence"

        extra_candidates.append(
            {
                "type": "state",
                "text": "The passage is unavailable."
            }
        )

    if action in ["go", "move", "walk", "enter"]:

        passage_state = world.get("passage", {})

        if passage_state.get("world_state") == "unavailable":

            LAST_RULE = "passage unavailable blocks movement"
            LAST_RULE_TYPE = "block"

            return [
                {
                    "type": "event",
                    "text": "The player tried to move, but the passage is unavailable."
                }
            ]

    if action in ["go", "move", "walk", "enter"]:

        destination = None
        room = None

        if world_state.get("passage") == "unavailable":

            LAST_RULE = "passage unavailable blocks movement"
            LAST_RULE_TYPE = "block"

            return [
                {
                    "type": "event",
                    "text": "The player tried to move, but the passage is unavailable."
                }
            ]

        if player_location:
            room = player_location.strip()

            if room.startswith("in the "):
                room = room.replace("in the ", "", 1).strip()

        if not room:
            LAST_RULE = "player location unknown"
            LAST_RULE_TYPE = "block"

            return [
                {
                    "type": "event",
                    "text": "The player tried to move, but their current location is unknown."
                }
            ]

        if world_state.get("passage") == "available":
            LAST_RULE = "passage available allows movement"
            LAST_RULE_TYPE = "consequence"

        destination = map_data.EXITS.get(room, {}).get(target)

        if not destination:
            LAST_RULE = "no established exit"
            LAST_RULE_TYPE = "block"

            return [
                {
                    "type": "event",
                    "text": (
                        "The player tried to move, "
                        "but no exit is established in that direction."
                    )
                }
            ]

        extra_candidates.append(
            {
                "type": "state",
                "text": f"The player is in the {destination}."
            }
        )

    return candidates + extra_candidates