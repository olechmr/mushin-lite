"""Serialized host activation of installed episodes, not autonomous NPC behavior.

No import-time state loading or presentation. Canon retains all write authority.
See ARCHITECTURE.md, Lite Host Activation Boundary, for results and retry rules.
"""

from behavior import evaluate_transition, validated_transition_policies
from canon import commit_npc_resolution, commit_npc_transition
from collapse import collapse_npc_episode


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
    proposal = collapse_npc_episode(state.get("npc") if isinstance(state, dict) else None, episode_id, rng=rng)
    diagnostic = {key: value for key, value in proposal.items() if key != "basis"}
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
