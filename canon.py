import json
import math
from copy import deepcopy
import re
import os
import tempfile
from npc_fixture import SUPPORTED_DISPOSITIONS

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


def set_npc_disposition(state, entity_id, attribute, value):
    """Persist one explicit state assignment without asserting an event or cause."""
    npc = state.get("npc")
    validate_npc_state(npc)
    if not isinstance(entity_id, str) or entity_id not in npc["entities"]:
        raise ValueError("Unknown NPC ID")
    if attribute not in SUPPORTED_DISPOSITIONS:
        raise ValueError("Unsupported NPC disposition")
    entity = npc["entities"][entity_id]
    previous = entity.get(attribute) if isinstance(entity, dict) else None
    for label, number in ((f"Existing {attribute}", previous), (f"New {attribute}", value)):
        if type(number) not in (int, float) or not 0 <= number <= 1 or not math.isfinite(number):
            raise ValueError(f"{label} must be a finite number in [0, 1]")
    result = {"entity_id": entity_id, "attribute": attribute,
              "previous": previous, "value": value, "changed": previous != value}
    if not result["changed"]:
        return result
    pending = deepcopy(state)
    pending["npc"]["entities"][entity_id][attribute] = value
    _save_npc_commit(pending)
    state.update(pending)
    return result


def set_npc_irritability(state, entity_id, value):
    """Compatibility entry point for the original disposition setter."""
    return set_npc_disposition(state, entity_id, "irritability", value)


def commit_npc_transition(state, proposal):
    """Validate a fixed-policy proposal, then use the state-only atomic setter."""
    from behavior import evaluate_transition, get_transition_policy

    fields = {"status", "policy_id", "reasons", "entity_id", "episode_id",
              "attribute", "previous", "value", "basis"}
    if (
        not isinstance(proposal, dict) or set(proposal) != fields
        or proposal["status"] != "proposed"
        or get_transition_policy(proposal["policy_id"]) is None
        or any(type(proposal[k]) not in (int, float) for k in ("previous", "value"))
    ):
        raise ValueError("Invalid NPC transition proposal")
    npc = state.get("npc")
    validate_npc_state(npc)
    if not isinstance(proposal["basis"], dict) or proposal["basis"] != npc:
        raise ValueError("Stale or missing NPC transition basis")
    authorized = evaluate_transition(npc, proposal["policy_id"])
    if authorized["status"] != "proposed" or proposal != authorized:
        raise ValueError("Unauthorized NPC transition proposal")
    return set_npc_disposition(state, proposal["entity_id"], proposal["attribute"], proposal["value"])


def commit_npc_resolution(state, proposal):
    """Commit one authorized proposal and its event together, keyed by episode ID.

    Existing identical resolutions are no-ops. No event-text lookup determines
    identity. Validation and disk failure leave the caller's state unchanged.
    """
    from npc_episode_rules import OUTCOMES, validate_resolution

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
    validate_resolution(npc, proposal)
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


def commit_disagreement_initiator(state, proposal):
    """Commit only an authorized actor ID; preserve episode truth and its event."""
    from behavior import evaluate_disagreement_initiator

    fields = {"episode_id", "status", "disagreement_initiator", "sampled", "reused", "reasons", "basis"}
    if (
        not isinstance(proposal, dict) or set(proposal) != fields
        or proposal["status"] != "proposed" or proposal["sampled"] is not True
        or proposal["reused"] is not False or not isinstance(proposal["reasons"], list)
        or not isinstance(proposal["episode_id"], str)
        or not isinstance(proposal["disagreement_initiator"], str)
        or not isinstance(proposal["basis"], dict)
    ):
        raise ValueError("Invalid disagreement initiator proposal")
    npc = state.get("npc")
    validate_npc_state(npc)
    episode_id, actor = proposal["episode_id"], proposal["disagreement_initiator"]
    evaluation = evaluate_disagreement_initiator(npc, episode_id)
    if evaluation["status"] == "resolved":
        if evaluation["allowed_outcomes"] != [actor]:
            raise ValueError("Conflicting disagreement initiator")
        return {"committed": False, "reused": True, "disagreement_initiator": actor}
    if proposal["basis"] != npc:
        raise ValueError("Stale or missing disagreement initiator basis")
    if (
        evaluation["status"] != "possible" or actor not in evaluation["allowed_outcomes"]
        or evaluation["weights"].get(actor, 0) <= 0
        or proposal["reasons"] != evaluation["reasons"]
    ):
        raise ValueError("Unauthorized disagreement initiator")
    pending = deepcopy(state)
    pending["npc"]["resolutions"][episode_id]["disagreement_initiator"] = actor
    _save_npc_commit(pending)
    state.update(pending)
    return {"committed": True, "reused": False, "disagreement_initiator": actor}


def establish_npc_decision_window(state, window_id, window):
    """Explicit host lifecycle operation; never called by load or evaluation."""
    from npc_opportunity_rules import valid_id, valid_window, opportunity_state

    npc = state.get("npc")
    validate_npc_state(npc)
    if not valid_id(window_id) or not valid_window(window):
        raise ValueError("invalid_decision_window")
    if "opportunities" in npc:
        data = opportunity_state(npc)
        current = data["current_window"]
        if window_id == current and window == data["windows"][current]:
            return {"changed": False, "window_id": window_id}
        if window_id in data["windows"] or window[0] < data["windows"][current][1]:
            raise ValueError("cannot_reopen_or_overlap_decision_window")
    else:
        data = {"version": 1, "current_window": window_id, "windows": {}, "decisions": {}}
    pending = deepcopy(state)
    extension = deepcopy(data)
    extension["current_window"] = window_id
    extension["windows"][window_id] = deepcopy(window)
    extension["decisions"][window_id] = {}
    pending["npc"]["opportunities"] = extension
    opportunity_state(pending["npc"])
    _save_npc_commit(pending)
    state.update(pending)
    return {"changed": True, "window_id": window_id}


def commit_npc_opportunity(state, proposal):
    """Persist a decision/claim only; episode truth requires its own commitment."""
    from npc_opportunity_rules import (opportunity_state, validate_opportunity_proposal_shape,
                                       validate_opportunity_decision)

    validate_opportunity_proposal_shape(proposal)
    npc = state.get("npc")
    data = opportunity_state(npc)
    window_id, npc_id = proposal["window_id"], proposal["npc_id"]
    existing = data["decisions"].get(window_id, {}).get(npc_id)
    if existing is not None:
        if existing["choice"] != proposal["choice"] or existing["episode_id"] != proposal["episode_id"]:
            raise ValueError("conflicting_opportunity_decision")
        return {"committed": False, "reused": True, "decision": deepcopy(existing)}
    validate_opportunity_decision(npc, proposal)
    episode_id = proposal["episode_id"]
    record = {"version": 1, "npc_id": npc_id, "window_id": window_id,
              "window": deepcopy(data["windows"][window_id]), "policy": "initiation_v1",
              "choice": proposal["choice"], "episode_id": episode_id,
              "episode": deepcopy(npc["episodes"][episode_id]) if episode_id is not None else None}
    pending = deepcopy(state)
    pending["npc"]["opportunities"]["decisions"][window_id][npc_id] = record
    opportunity_state(pending["npc"])
    _save_npc_commit(pending)
    state.update(pending)
    return {"committed": True, "reused": False, "decision": deepcopy(record)}


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

def commit_player_action(state, proposal, world_inputs):
    """Commit one independently authorized ordinary action as an atomic unit.

    Events always append; matching prose is not occurrence identity. No automatic
    retry: a failed/uncertain save requires host reconciliation before retrying.
    Caller-owned state/configuration must be current and calls serialized.
    """
    from player_action_rules import validate_player_action

    def result(status, reason=None, facts=None, block=None):
        return {"version": 1, "status": status, "reason": reason,
                "facts": deepcopy(facts or []), "rule_block_text": block}

    try:
        effects, block = validate_player_action(state, proposal, world_inputs)
        if "npc" in state:
            validate_npc_state(state["npc"])
    except (ValueError, TypeError, KeyError, RecursionError) as error:
        return result("rejected", str(error))

    pending = deepcopy(state)
    committed = []
    for effect in effects:
        text, kind = effect["text"], effect["type"]
        slot = fact_slot(text, kind)
        if kind == "state":
            active = [f for f in pending["facts"]
                      if f.get("status", "active") == "active"
                      and f.get("type", "state") == "state"]
            if any(normalize_fact(f["text"]) == normalize_fact(text) for f in active):
                continue
            for fact in active:
                if slot is not None and fact_slot(fact["text"], "state") == slot:
                    fact["status"] = "superseded"
        fact = {"id": pending["next_fact_id"], "text": text,
                "status": "active", "type": kind}
        pending["facts"].append(fact)
        pending["next_fact_id"] += 1
        committed.append(fact)
    if not committed:
        return result("no_change", block=block)
    try:
        # Reuse only atomic snapshot infrastructure, not NPC authorization.
        _save_npc_commit(pending)
    except (OSError, ValueError, TypeError) as error:
        return result("failed", "Persistence failed; reconcile before retry: " + str(error))
    state.update(pending)
    return result("committed", facts=committed, block=block)


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