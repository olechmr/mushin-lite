import json
import math
from copy import deepcopy
import re
import os
import tempfile

STATE_FILE = "state.json"


def load_state():

    with open(STATE_FILE, "r") as f:
        state = json.load(f)

    for fact in state["facts"]:

        if "status" not in fact:
            fact["status"] = "active"

    state.setdefault("npc", empty_npc_state())
    validate_npc_state(state["npc"])

    return state

def save_state(state):

    if "npc" in state:
        validate_npc_state(state["npc"])

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def empty_npc_state():
    """No NPCs or historical episodes are inferred when migrating an old save."""
    return {"version": 1, "entities": {}, "episodes": {}, "resolutions": {}}


def validate_npc_state(npc):
    """Validate the storage envelope; behavior validates episode constraints."""
    if not isinstance(npc, dict) or type(npc.get("version")) is not int or npc["version"] != 1:
        raise ValueError("Unsupported NPC state version")
    if any(not isinstance(npc.get(key), dict) for key in ("entities", "episodes", "resolutions")):
        raise ValueError("Invalid NPC state namespace")


def reset_npc_state(state, foundation=None):
    """Explicitly replace NPC state only; omit foundation to clear it.

    Pass npc_fixture.build_npc_fixture() to install the isolated prototype.
    This is setup/reset, not an interaction commitment operation.
    """
    npc = empty_npc_state() if foundation is None else deepcopy(foundation)
    validate_npc_state(npc)
    state["npc"] = npc
    save_state(state)


def reset_npc_test_fixture(state):
    """Reset the isolated experiment, including only its keyed historical events."""
    from npc_fixture import build_npc_fixture

    npc = state.get("npc", empty_npc_state())
    validate_npc_state(npc)
    event_ids = {r["event_id"] for r in npc["resolutions"].values()
                 if isinstance(r, dict) and type(r.get("event_id")) is int}
    pending = deepcopy(state)
    pending["facts"] = [f for f in pending["facts"]
                        if not (f.get("type") == "event" and f.get("id") in event_ids)]
    pending["npc"] = build_npc_fixture()
    _save_npc_commit(pending)
    state.update(pending)


def set_npc_irritability(state, entity_id, value):
    """Persist one explicit state assignment without asserting an event or cause."""
    npc = state.get("npc")
    validate_npc_state(npc)
    if not isinstance(entity_id, str) or entity_id not in npc["entities"]:
        raise ValueError("Unknown NPC ID")
    entity = npc["entities"][entity_id]
    previous = entity.get("irritability") if isinstance(entity, dict) else None
    for label, number in (("Existing irritability", previous), ("New irritability", value)):
        if type(number) not in (int, float) or not 0 <= number <= 1 or not math.isfinite(number):
            raise ValueError(f"{label} must be a finite number in [0, 1]")
    result = {"entity_id": entity_id, "attribute": "irritability",
              "previous": previous, "value": value, "changed": previous != value}
    if not result["changed"]:
        return result
    pending = deepcopy(state)
    pending["npc"]["entities"][entity_id]["irritability"] = value
    _save_npc_commit(pending)
    state.update(pending)
    return result


def commit_npc_resolution(state, proposal):
    """Commit one authorized proposal and its event together, keyed by episode ID.

    Existing identical resolutions are no-ops. No event-text lookup determines
    identity. Validation and disk failure leave the caller's state unchanged.
    """
    from behavior import OUTCOMES, evaluate_episode

    npc = state.get("npc")
    validate_npc_state(npc)
    episode_id, outcome = proposal.get("episode_id"), proposal.get("outcome")
    if not isinstance(episode_id, str) or episode_id not in npc["episodes"] or outcome not in OUTCOMES:
        raise ValueError("Invalid NPC episode or outcome")
    if episode_id in npc["resolutions"]:
        existing = npc["resolutions"][episode_id]
        if not isinstance(existing, dict) or existing.get("outcome") != outcome:
            raise ValueError("Conflicting NPC resolution")
        return {"committed": False, "reused": True, "resolution": deepcopy(existing)}
    if proposal.get("basis") != npc:
        raise ValueError("Stale or missing NPC proposal basis")
    evaluation = evaluate_episode(npc, episode_id)
    feasibility = evaluation["feasibility"]
    if (
        proposal.get("feasibility") != feasibility
        or proposal.get("reused") is not False
        or feasibility not in ("possible", "impossible")
        or outcome not in evaluation["allowed_outcomes"]
        or evaluation["weights"].get(outcome, 0) <= 0
        or proposal.get("sampled") is not (feasibility == "possible")
    ):
        raise ValueError("Unauthorized NPC resolution proposal")
    episode = npc["episodes"][episode_id]
    names = [npc["entities"][p].get("display_name") for p in episode["participants"]]
    label = episode.get("display_name")
    if any(not isinstance(text, str) or not text.strip() for text in names + [label]):
        raise ValueError("Missing NPC event metadata")
    verb = {"conversation": "talked", "disagreement": "argued",
            "no_interaction": "did not interact"}[outcome]
    pending = deepcopy(state)
    fact_id = pending["next_fact_id"]
    resolution = {"outcome": outcome, "event_id": fact_id}
    pending["npc"]["resolutions"][episode_id] = resolution
    pending["facts"].append({
        "id": fact_id, "type": "event", "status": "active",
        "text": f"{names[0]} and {names[1]} {verb} during the {label}.",
    })
    pending["next_fact_id"] += 1
    _save_npc_commit(pending)
    state.update(pending)
    return {"committed": True, "reused": False, "resolution": deepcopy(resolution)}


def _save_npc_commit(state):
    """One atomic snapshot containing both structured history and its event."""
    path = os.path.abspath(STATE_FILE)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=os.path.dirname(path),
                                         prefix=".npc-commit-", delete=False) as handle:
            temporary = handle.name
            json.dump(state, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


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
    state["npc"] = empty_npc_state()

    save_state(state)

def resolve_fact(state, number):

    for fact in state["facts"]:

        if fact["id"] == number:

            fact["status"] = "resolved"

            save_state(state)

            return fact["text"]

    return None