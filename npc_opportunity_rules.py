"""Shared opportunity schemas and independent authorization; no stage calls."""
from copy import deepcopy
import math

import npc_fixture
from npc_episode_rules import OUTCOMES, _episode_constraints, episode_factors, policy_snapshot


def valid_id(value):
    return isinstance(value, str) and bool(value.strip())


def valid_window(value):
    return (isinstance(value, list) and len(value) == 2
            and all(type(t) is int for t in value) and value[0] < value[1])


def overlaps(left, right):
    return left[0] < right[1] and right[0] < left[1]


def validate_record(record, npc_id, window_id, window):
    fields = {"version", "npc_id", "window_id", "window", "policy", "choice", "episode_id", "episode"}
    if (not isinstance(record, dict) or set(record) != fields
            or type(record["version"]) is not int or record["version"] != 1
            or record["npc_id"] != npc_id or record["window_id"] != window_id
            or not valid_id(npc_id) or not valid_id(record["policy"])
            or not valid_window(record["window"]) or record["window"] != window):
        raise ValueError("invalid_decision_record")
    if record["choice"] == "no_initiation":
        if record["episode_id"] is not None or record["episode"] is not None:
            raise ValueError("invalid_abstention_record")
    elif record["choice"] == "episode":
        episode = record["episode"]
        participants = episode.get("participants") if isinstance(episode, dict) else None
        if not isinstance(participants, list) or any(not valid_id(p) for p in participants):
            raise ValueError("invalid_episode_snapshot")
        constraints = _episode_constraints(episode, dict.fromkeys(participants))
        if (not valid_id(record["episode_id"]) or constraints is None or not constraints[2]
                or npc_id not in participants or episode["window"] != window
                or not valid_id(episode.get("display_name"))):
            raise ValueError("invalid_episode_snapshot")
    else:
        raise ValueError("invalid_decision_choice")


def opportunity_state(npc):
    """Validate retained history without consulting providers or live episodes."""
    if (not isinstance(npc, dict) or type(npc.get("version")) is not int or npc["version"] != 1
            or any(not isinstance(npc.get(k), dict) for k in ("entities", "episodes", "resolutions"))):
        raise ValueError("invalid_npc_state")
    data = npc.get("opportunities")
    if (not isinstance(data, dict) or set(data) != {"version", "current_window", "windows", "decisions"}
            or type(data["version"]) is not int or data["version"] != 1
            or not valid_id(data["current_window"]) or not isinstance(data["windows"], dict)
            or not isinstance(data["decisions"], dict) or not data["windows"]
            or set(data["decisions"]) != set(data["windows"])
            or data["current_window"] not in data["windows"]):
        raise ValueError("missing_or_invalid_opportunity_state")
    windows, decisions = data["windows"], data["decisions"]
    if any(not valid_id(k) or not valid_window(v) for k, v in windows.items()):
        raise ValueError("invalid_decision_windows")
    ordered = sorted(windows, key=lambda k: windows[k][0])
    if (data["current_window"] != ordered[-1]
            or any(windows[a][1] > windows[b][0] for a, b in zip(ordered, ordered[1:]))):
        raise ValueError("overlapping_or_reopened_windows")
    claims = []
    for window_id, window in windows.items():
        if not isinstance(decisions[window_id], dict):
            raise ValueError("invalid_decision_map")
        for npc_id, record in decisions[window_id].items():
            validate_record(record, npc_id, window_id, window)
            if record["choice"] == "episode":
                for previous in claims:
                    if (record["episode_id"] == previous["episode_id"]
                            or (overlaps(window, previous["window"])
                                and set(record["episode"]["participants"]) & set(previous["episode"]["participants"]))):
                        raise ValueError("conflicting_historical_claims")
                claims.append(record)
    return data


def existing_opportunity_decision(npc, npc_id):
    if not valid_id(npc_id):
        raise ValueError("invalid_npc_id")
    data = opportunity_state(npc)
    return deepcopy(data["decisions"][data["current_window"]].get(npc_id))


def initiation_policy():
    config = npc_fixture.NPC_INITIATION_POLICY
    expected = {"id": "initiation_v1", "version": 1, "archetype": "interaction_v1",
                "no_initiation": 1.0, "initiation_base": 1.0}
    if (not isinstance(config, dict) or config != expected
            or type(config.get("version")) is not int
            or any(type(config[k]) not in (int, float) for k in ("no_initiation", "initiation_base"))):
        raise ValueError("invalid_initiation_policy")
    return deepcopy(config)


def opportunity_inputs(npc, npc_id):
    """Return validated eligibility and factors, never a sampled decision."""
    data = opportunity_state(npc)
    if not valid_id(npc_id) or not isinstance(npc["entities"].get(npc_id), dict):
        raise ValueError("unknown_npc")
    if npc_id in data["decisions"][data["current_window"]]:
        raise ValueError("decision_already_committed")
    actor = npc["entities"][npc_id]
    for attribute in npc_fixture.SUPPORTED_DISPOSITIONS:
        value = actor.get(attribute)
        if type(value) not in (int, float) or not 0 <= value <= 1 or not math.isfinite(value):
            raise ValueError("invalid_deciding_npc_disposition")
    config = {"initiation": initiation_policy(), "interaction": policy_snapshot(npc, [npc_id])}
    window = data["windows"][data["current_window"]]
    claims = [r for records in data["decisions"].values() for r in records.values()
              if r["choice"] == "episode"]
    catalogue, identities = {}, set()
    # Validate the entire catalogue; malformed entries cannot silently change odds.
    for episode_id, episode in npc["episodes"].items():
        participants, overlap, _, _ = episode_factors(npc, episode_id)
        policy_snapshot(npc, participants)
        if (not valid_id(episode.get("display_name"))
                or any(not valid_id(npc["entities"][p].get("display_name")) for p in participants)):
            raise ValueError("missing_episode_metadata")
        identity = (tuple(sorted(participants)), tuple(episode["window"]))
        if identity in identities:
            raise ValueError("duplicate_episode_definition")
        identities.add(identity)
        catalogue[episode_id] = (participants, overlap)
    for episode_id, resolution in npc["resolutions"].items():
        if (episode_id not in catalogue or not isinstance(resolution, dict)
                or resolution.get("outcome") not in OUTCOMES):
            raise ValueError("invalid_resolution_history")
    for claim in claims:
        live = npc["episodes"].get(claim["episode_id"])
        if live is not None and live != claim["episode"]:
            raise ValueError("changed_claimed_episode")
    eligible = []
    for episode_id in sorted(catalogue):
        participants, overlap = catalogue[episode_id]
        episode = npc["episodes"][episode_id]
        if (npc_id not in participants or episode["window"] != window or not overlap
                or episode_id in npc["resolutions"]):
            continue
        claimed = any(episode_id == r["episode_id"] or
                      (overlaps(window, r["window"]) and set(participants) & set(r["episode"]["participants"]))
                      for r in claims)
        resolved_conflict = any(overlaps(window, npc["episodes"][rid]["window"])
                                and set(participants) & set(npc["episodes"][rid]["participants"])
                                for rid in npc["resolutions"])
        if not claimed and not resolved_conflict:
            eligible.append(episode_id)
    return data["current_window"], eligible, actor["sociability"], config


def validate_opportunity_possibilities(npc, npc_id, candidate):
    window_id, eligible, sociability, config = opportunity_inputs(npc, npc_id)
    fields = {"version", "status", "npc_id", "window_id", "candidates", "reasons", "basis", "policy_basis"}
    if (not isinstance(candidate, dict) or set(candidate) != fields
            or type(candidate["version"]) is not int or candidate["version"] != 1
            or candidate["status"] != "possible" or candidate["npc_id"] != npc_id
            or candidate["window_id"] != window_id or candidate["basis"] != npc
            or candidate["policy_basis"] != config
            or not isinstance(candidate["reasons"], list)
            or any(not isinstance(r, str) for r in candidate["reasons"])):
        raise ValueError("invalid_or_stale_opportunities")
    candidates = candidate["candidates"]
    expected = [("no_initiation", None, 1.0)]
    if eligible:
        expected.extend(("episode", eid, (1.0 + sociability) / len(eligible)) for eid in eligible)
    if not isinstance(candidates, list) or len(candidates) != len(expected):
        raise ValueError("unauthorized_opportunity_distribution")
    for item, (kind, episode_id, weight) in zip(candidates, expected):
        if (not isinstance(item, dict) or set(item) != {"kind", "episode_id", "weight"}
                or item["kind"] != kind or item["episode_id"] != episode_id
                or type(item["weight"]) not in (int, float) or item["weight"] != weight):
            raise ValueError("unauthorized_opportunity_distribution")


def validate_opportunity_proposal_shape(proposal):
    fields = {"version", "status", "npc_id", "window_id", "choice", "episode_id", "sampled", "possibilities"}
    if (not isinstance(proposal, dict) or set(proposal) != fields
            or type(proposal["version"]) is not int or proposal["version"] != 1
            or proposal["status"] != "proposed" or not valid_id(proposal["npc_id"])
            or not valid_id(proposal["window_id"]) or type(proposal["sampled"]) is not bool
            or proposal["choice"] not in ("no_initiation", "episode")
            or (proposal["choice"] == "no_initiation" and proposal["episode_id"] is not None)
            or (proposal["choice"] == "episode" and not valid_id(proposal["episode_id"]))):
        raise ValueError("invalid_opportunity_proposal")


def validate_opportunity_decision(npc, proposal):
    validate_opportunity_proposal_shape(proposal)
    envelope = proposal["possibilities"]
    validate_opportunity_possibilities(npc, proposal["npc_id"], envelope)
    if (proposal["window_id"] != envelope["window_id"]
            or proposal["sampled"] is not (len(envelope["candidates"]) > 1)
            or not any(c["kind"] == proposal["choice"] and c["episode_id"] == proposal["episode_id"]
                       for c in envelope["candidates"])):
        raise ValueError("unauthorized_opportunity_choice")


def validate_opportunity_handoff(npc, record):
    """Read-only guard for a new handoff or deliberate, reconciled host recovery."""
    data = opportunity_state(npc)
    if (not isinstance(record, dict) or not valid_id(record.get("window_id"))
            or not valid_id(record.get("npc_id"))
            or data["decisions"].get(record["window_id"], {}).get(record["npc_id"]) != record
            or record.get("choice") != "episode"
            or npc["episodes"].get(record["episode_id"]) != record["episode"]):
        raise ValueError("invalid_or_changed_opportunity_handoff")
    for episode_id, resolution in npc["resolutions"].items():
        if episode_id == record["episode_id"]:
            continue
        constraints = _episode_constraints(npc["episodes"].get(episode_id), npc["entities"])
        if (constraints is None or not isinstance(resolution, dict)
                or resolution.get("outcome") not in OUTCOMES):
            raise ValueError("invalid_resolution_history")
        if (overlaps(record["window"], constraints[1])
                and set(record["episode"]["participants"]) & set(constraints[0])):
            raise ValueError("resolved_participant_conflict")
    # Episode commitment will independently validate current dispositions/policy.
    return record["episode_id"]
