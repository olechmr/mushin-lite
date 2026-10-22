"""Bounded host orchestration; no window lifecycle or canonical write authority."""
from copy import deepcopy

from npc_activation import activate_npc_opportunity
from npc_opportunity_rules import opportunity_inputs, opportunity_state, valid_id


def _followup_status(result):
    if result.get("episode_status") != "activated":
        return "not_requested"
    episode = result.get("episode", {})
    if episode.get("reused"):
        return "unknown"
    transitions = episode.get("transitions")
    if not isinstance(transitions, list):
        return "unknown"
    for transition in transitions:
        if (not isinstance(transition, dict) or "error" in transition
                or transition.get("status") not in ("no_change", "proposed")
                or (transition["status"] == "proposed" and transition.get("committed") is not True)):
            return "failed"
    return "completed"


def process_npc_decision_window(state, expected_window_id, npc_ids, rng=None):
    """Process a host-retained roster; completion never advances the window.

    Preflight checks shared authorization inputs without producing possibilities.
    Only canon commits; existing decisions are the sole durable progress record.
    See ARCHITECTURE.md for partial failure, unknown history, and recovery rules.
    """
    requested = list(npc_ids) if isinstance(npc_ids, (list, tuple)) else None
    result = {"version": 1, "status": "rejected", "window_id": expected_window_id,
              "requested_npc_ids": deepcopy(requested), "processing_order": [],
              "processed_npc_ids": [], "unprocessed_npc_ids": deepcopy(requested),
              "results": [], "decisions_complete": None, "processing_complete": False}
    try:
        if (not isinstance(state, dict) or not isinstance(state.get("facts"), list)
                or type(state.get("next_fact_id")) is not int or state["next_fact_id"] < 1):
            raise ValueError("invalid_canonical_storage_envelope")
        npc = state.get("npc")
        data = opportunity_state(npc)
        if not valid_id(expected_window_id) or expected_window_id != data["current_window"]:
            raise ValueError("expected_window_not_current")
        if requested is None or any(not valid_id(n) for n in requested):
            raise ValueError("invalid_npc_roster")
        if len(set(requested)) != len(requested):
            raise ValueError("duplicate_npc_id")
        for npc_id in requested:
            if not isinstance(npc["entities"].get(npc_id), dict):
                raise ValueError("unknown_npc")
        order = sorted(requested)
        for npc_id in order:
            if npc_id not in data["decisions"][expected_window_id]:
                opportunity_inputs(npc, npc_id)
    except Exception as error:
        result.update(error=str(error), error_type=type(error).__name__)
        return result

    result.update(status="completed", processing_order=order, unprocessed_npc_ids=order.copy())
    for npc_id in order:
        try:
            diagnostic = activate_npc_opportunity(state, npc_id, rng=rng)
        except Exception as error:
            # Do not retry an uncertain dependency failure or undo its writes.
            diagnostic = {"npc_id": npc_id, "decision_status": "failed",
                          "episode_status": "failed", "error": str(error),
                          "error_type": type(error).__name__}
        diagnostic = deepcopy(diagnostic)
        diagnostic["followup_status"] = _followup_status(diagnostic)
        result["results"].append(diagnostic)
        result["processed_npc_ids"].append(npc_id)
        result["unprocessed_npc_ids"] = order[len(result["processed_npc_ids"]):]
        if ("error" in diagnostic or diagnostic.get("decision_status") not in ("committed", "reused")
                or diagnostic.get("episode_status") not in ("not_requested", "activated")
                or diagnostic["followup_status"] == "failed"):
            result["status"] = "stopped"
            break
    # Read current canonical records, not cached preflight data or proposed outcomes.
    decisions = state["npc"]["opportunities"]["decisions"][expected_window_id]
    result["decisions_complete"] = all(npc_id in decisions for npc_id in order)
    result["processing_complete"] = result["status"] == "completed"
    return result
