import json
import re

STATE_FILE = "state.json"


def load_state():

    with open(STATE_FILE, "r") as f:
        state = json.load(f)

    for fact in state["facts"]:

        if "status" not in fact:
            fact["status"] = "active"

    return state

def save_state(state):

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def normalize_fact(text):

    text = text.strip().lower()

    if text.endswith("."):
        text = text[:-1]

    return text

def clean_object_name(text):

    text = text.strip().lower()

    for prefix in ["the ", "a ", "an "]:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break

    return text.strip()


def fact_slot(text, fact_type):
    """
    Tiny current-state slot detector.

    Goal:
    Prevent multiple active current-state facts about the same object.

    This is intentionally simple.
    It is not an entity system.
    It only recognizes a few plain-English state shapes.
    """
    normalized = normalize_fact(text)

    if normalized.startswith("session setup:"):
        return None

    if fact_type != "state":
        return None

    not_holding_match = re.match(
        r"^(the )?(player|user) is not holding (the |a |an )?(.+)$",
        normalized
    )

    if not_holding_match:
        obj = clean_object_name(not_holding_match.group(4))
        return f"whereabouts:{obj}"

    holding_match = re.match(
        r"^(the )?(player|user) is holding (the |a |an )?(.+)$",
        normalized
    )

    if holding_match:
        obj = clean_object_name(holding_match.group(4))
        return f"whereabouts:{obj}"

    holding_match = re.match(
        r"^(.+?) is holding (the |a |an )?(.+)$",
        normalized
    )

    if holding_match:
        obj = clean_object_name(holding_match.group(3))
        return f"whereabouts:{obj}"

    inside_out_match = re.match(
        r"^(the )?(.+) is inside out$",
        normalized
    )

    if inside_out_match:
        obj = clean_object_name(inside_out_match.group(2))
        return f"inverted_state:{obj}"

    has_match = re.match(
        r"^(the )?(player|user) has (the |a |an )?(.+)$",
        normalized
    )

    if has_match:
        obj = clean_object_name(has_match.group(4))
        return f"whereabouts:{obj}"

    taken_by_match = re.match(
        r"^(the |a |an )?(.+) was taken by (the )?(player|user)$",
        normalized
    )

    if taken_by_match:
        obj = clean_object_name(taken_by_match.group(2))
        return f"whereabouts:{obj}"

    taken_match = re.match(
        r"^(the |a |an )?(.+) was taken$",
        normalized
    )

    if taken_match:
        obj = clean_object_name(taken_match.group(2))
        return f"whereabouts:{obj}"

    location_match = re.match(
        r"^(the |a |an )?(.+?) is "
        r"(on|in|at|under|inside|outside|beside|near|behind) "
        r"(the |a |an )?.+$",
        normalized
    )

    if location_match:
        obj = clean_object_name(location_match.group(2))
        return f"whereabouts:{obj}"

    exists_location_match = re.match(
        r"^(the |a |an )?(.+?) exists "
        r"(on|in|at|under|inside|outside|beside|near|behind) "
        r"(the |a |an )?.+$",
        normalized
    )

    if exists_location_match:
        obj = clean_object_name(exists_location_match.group(2))
        return f"whereabouts:{obj}"

    open_match = re.match(
        r"^(the )?(.+) is open$",
        normalized
    )

    if open_match:
        obj = clean_object_name(open_match.group(2))
        return f"open_state:{obj}"

    closed_match = re.match(
        r"^(the )?(.+) is closed$",
        normalized
    )

    if closed_match:
        obj = clean_object_name(closed_match.group(2))
        return f"open_state:{obj}"

    broken_match = re.match(
        r"^(the )?(.+) is broken$",
        normalized
    )

    if broken_match:
        obj = clean_object_name(broken_match.group(2))
        return f"broken_state:{obj}"

    bare_location_match = re.match(
        r"^(the |a |an )?(.+?) "
        r"(on|in|at|under|inside|outside|beside|near|behind) "
        r"(the |a |an )?.+$",
        normalized
    )

    if bare_location_match:
        obj = clean_object_name(bare_location_match.group(2))
        return f"whereabouts:{obj}"

    room_lighting_patterns = [
        r"^the room is illuminated$",
        r"^the room is dark$",
    ]

    for pattern in room_lighting_patterns:
        if re.match(pattern, normalized):
            return "world_state:room_lighting"

    light_state_patterns = [
        (r"^the (.+) is lit$", "lit"),
        (r"^the (.+) is not lit$", "not_lit"),
    ]

    for pattern, value in light_state_patterns:
        match = re.match(pattern, normalized)

        if match:
            obj = match.group(1)
            return f"light_state:{obj}"

    passage_state_patterns = [
        r"^the passage is available$",
        r"^the passage is unavailable$",
    ]

    for pattern in passage_state_patterns:
        if re.match(pattern, normalized):
            return "world_state:passage"

    location_patterns = [
        r"^the player is in the (.+)$",
    ]

    for pattern in location_patterns:
        match = re.match(pattern, normalized)

        if match:
            return "player_location"

    match = re.match(r"^the (.+) is in the (.+)$", normalized)

    if match:
        obj = match.group(1)
        return f"whereabouts:{obj}"

    return None

def add_fact(state, fact_text, fact_type="state"):

    normalized_new = normalize_fact(fact_text)

    new_slot = fact_slot(fact_text, fact_type)

    for fact in state["facts"]:

        if fact.get("status", "active") != "active":
            continue

        normalized_existing = normalize_fact(fact["text"])

        if (
            normalized_existing == normalized_new
            and (
                fact_type != "collapse"
                or fact.get("type") == "collapse"
            )
            and (
                fact_type != "state"
                or fact.get("type", "state") == "state"
            )
        ):
            return False

    for fact in state["facts"]:

        if fact.get("status", "active") != "active":
            continue

        existing_slot = fact_slot(
            fact["text"],
            fact.get("type", "state")
        )

        if new_slot is not None and existing_slot == new_slot:
            fact["status"] = "superseded"
            
    fact = {
        "id": state["next_fact_id"],
        "text": fact_text,
        "status": "active",
        "type": fact_type
    }

    state["facts"].append(fact)

    state["next_fact_id"] += 1

    save_state(state)

    return True


def forget_fact(state, number):

    for fact in state["facts"]:

        if fact["id"] == number:

            state["facts"].remove(fact)

            save_state(state)

            return fact["text"]

    return None

def forget_all(state):

    state["facts"] = []
    state["next_fact_id"] = 1

    save_state(state)

def resolve_fact(state, number):

    for fact in state["facts"]:

        if fact["id"] == number:

            fact["status"] = "resolved"

            save_state(state)

            return fact["text"]

    return None