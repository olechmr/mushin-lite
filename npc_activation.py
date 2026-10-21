"""Serialized host orchestration of episodes and bounded opportunity decisions.

No import-time state loading or presentation. Canon retains all write authority.
See ARCHITECTURE.md, Lite Host Activation Boundary, for results and retry rules.
"""

from behavior import evaluate_transition, validated_transition_policies
from canon import commit_npc_resolution, commit_npc_transition
from collapse import existing_npc_episode, resolve_npc_episode_possibilities


def process_npc_transitions_for_episode(state, episode_id):
    """Process explicit dependencies sequentially; episode truth survives failure."""
    try:
        policies = [policy for policy in validated_transition_policies()
                    if policy["episode_id"] == episode_id]
    except Exception as error:
        return [{"status": "error", "committed": False, "stage": "registry",
                 "error": str(error), "error_type": type(error).__name__}]
    diagnostics = []
    for policy in policies:
        transition = {"policy_id": policy["policy_id"], "status": "error", "committed": False}
        diagnostics.append(transition)
        stage = "evaluation"
        try:
            proposal = evaluate_transition(state["npc"], policy["policy_id"])
            transition.update(status=proposal["status"], reasons=proposal["reasons"])
            if proposal["status"] == "proposed":
                stage = "commitment"
                result = commit_npc_transition(state, proposal)
                transition["committed"] = result["changed"]
        except Exception as error:
            transition.update(stage=stage, error=str(error), error_type=type(error).__name__)
    return diagnostics


def activate_npc_episode(state, episode_id, rng=None):
    """Shared collapse/commit path; proposals alone are never disclosed as truth."""
    npc = state.get("npc") if isinstance(state, dict) else None
    proposal = existing_npc_episode(npc, episode_id)
    if proposal is None:
        from npc_baseline import evaluate_baseline_episode
        evaluation = evaluate_baseline_episode(npc, episode_id)
        proposal = resolve_npc_episode_possibilities(npc, episode_id, evaluation, rng=rng)
    diagnostic = {key: value for key, value in proposal.items() if key not in ("basis", "possibilities")}
    diagnostic["committed"] = False
    if proposal["outcome"] is not None and not proposal["reused"]:
        try:
            result = commit_npc_resolution(state, proposal)
            diagnostic.update(committed=result["committed"], reused=result["reused"])
        except (ValueError, OSError) as error:
            diagnostic["error"] = str(error)
    if diagnostic["committed"]:
        diagnostic["transitions"] = process_npc_transitions_for_episode(state, episode_id)
    diagnostic["activation_status"] = ("committed" if diagnostic["committed"]
                                       else "reused" if diagnostic["reused"] else "failed")
    return diagnostic


def activate_npc_opportunity(state, npc_id, rng=None):
    """Host-only bounded initiation; reuse never retries an episode activation."""
    from npc_opportunity_rules import existing_opportunity_decision, validate_opportunity_handoff
    from canon import commit_npc_opportunity

    result = {"npc_id": npc_id, "decision_status": "failed", "episode_status": "not_requested"}
    npc = state.get("npc") if isinstance(state, dict) else None
    try:
        existing = existing_opportunity_decision(npc, npc_id)
        if existing is not None:
            result.update(decision_status="reused", decision=existing)
            if existing["choice"] == "episode":
                # Reuse history without invoking provider, RNG, activation or follow-ups.
                from copy import deepcopy
                from npc_episode_rules import OUTCOMES
                result["episode_status"] = "recovery_required"
                if existing["episode_id"] in npc["resolutions"]:
                    resolution = npc["resolutions"][existing["episode_id"]]
                    if not isinstance(resolution, dict) or resolution.get("outcome") not in OUTCOMES:
                        raise ValueError("invalid_stored_episode_resolution")
                    result.update(episode_status="activated", episode={"reused": True,
                                  "committed": False, "resolution": deepcopy(resolution)})
            return result
        from npc_opportunity import evaluate_npc_opportunities
        from npc_opportunity_resolution import resolve_npc_opportunity
        possibilities = evaluate_npc_opportunities(npc, npc_id)
        if possibilities["status"] != "possible":
            result["reasons"] = possibilities["reasons"]
            return result
        proposal = resolve_npc_opportunity(npc, npc_id, possibilities, rng)
        committed = commit_npc_opportunity(state, proposal)
        record = committed["decision"]
        result.update(decision_status="committed" if committed["committed"] else "reused",
                      decision=record)
        if record["choice"] == "no_initiation":
            return result
        if not committed["committed"]:
            result["episode_status"] = "recovery_required"
            return result
        result["episode_status"] = "failed"
        episode_id = validate_opportunity_handoff(state["npc"], record)
        episode = activate_npc_episode(state, episode_id, rng)
        result.update(episode=episode,
                      episode_status="activated" if episode["committed"] or episode["reused"] else "failed")
    except Exception as error:
        # Preserve/report partial success, including unexpected dependency failures.
        result.update(error=str(error), error_type=type(error).__name__)
    return result
