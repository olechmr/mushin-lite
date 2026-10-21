"""Bounded opportunity decisions; standard library, all writes in temporary storage."""
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import canon
import npc_activation
import npc_fixture
from npc_opportunity import evaluate_npc_opportunities
from npc_opportunity_resolution import resolve_npc_opportunity
from npc_opportunity_rules import opportunity_state, validate_opportunity_handoff

EPISODE = "fixture_morning"
WINDOW = "fixture_morning_window"


class OpportunityTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "state.json"
        redirect = patch.object(canon, "STATE_FILE", str(self.path))
        redirect.start()
        self.addCleanup(redirect.stop)
        self.state = {"facts": [], "next_fact_id": 1, "npc": npc_fixture.build_npc_fixture()}
        canon.save_state(self.state)

    @property
    def npc(self):
        return self.state["npc"]

    def evaluate(self, actor="heidi"):
        return evaluate_npc_opportunities(self.npc, actor)

    def proposal(self, actor="heidi", roll=.99):
        return resolve_npc_opportunity(self.npc, actor, self.evaluate(actor), Mock(random=Mock(return_value=roll)))

    def activate(self, actor="heidi", roll=.99):
        return npc_activation.activate_npc_opportunity(self.state, actor, Mock(random=Mock(return_value=roll)))

    def rejected(self, proposal):
        before, disk = deepcopy(self.state), self.path.read_bytes()
        with self.assertRaises(ValueError):
            canon.commit_npc_opportunity(self.state, proposal)
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), disk)

    def add_alternative(self):
        self.npc["entities"]["pat"] = dict(self.npc["entities"]["chris"], display_name="Pat")
        self.npc["episodes"]["alternative"] = {
            "display_name": "alternative encounter", "participants": ["heidi", "pat"],
            "window": [0, 1], "allowed_places": {"heidi": ["study"], "pat": ["study"]}}

    def test_pure_evaluation_without_optional_behavior_or_other_stages(self):
        before, disk = deepcopy(self.state), self.path.read_bytes()
        first = self.evaluate()
        self.assertEqual(first, self.evaluate())
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), disk)
        first["basis"]["entities"].clear()
        first["policy_basis"]["initiation"].clear()
        self.assertEqual(self.state, before)
        self.assertEqual(self.evaluate()["status"], "possible")
        script = '''
import sys
for name in ("behavior", "npc_baseline", "npc_activation", "collapse", "canon", "renderer", "llm_adapter", "main"):
    sys.modules[name] = None
from npc_opportunity import evaluate_npc_opportunities
from npc_fixture import build_npc_fixture
assert evaluate_npc_opportunities(build_npc_fixture(), "heidi")["status"] == "possible"
'''
        subprocess.run([sys.executable, "-B", "-c", script], check=True, capture_output=True,
                       cwd=Path(__file__).resolve().parent)

    def test_host_without_player_presentation_or_llm(self):
        script = '''
import sys
for name in ("renderer", "llm_adapter", "main", "openai", "requests", "map_data"):
    sys.modules[name] = None
import canon
canon.STATE_FILE = sys.argv[1]
from npc_activation import activate_npc_opportunity
from npc_fixture import build_npc_fixture
from types import SimpleNamespace
state = {"facts": [], "next_fact_id": 1, "npc": build_npc_fixture()}
result = activate_npc_opportunity(state, "heidi", SimpleNamespace(random=lambda: .99))
assert result["decision_status"] == "committed", result
assert result["episode_status"] == "activated", result
'''
        result = subprocess.run([sys.executable, "-B", "-c", script, str(self.path)],
                                check=True, capture_output=True, cwd=Path(__file__).resolve().parent)
        self.assertEqual(result.stdout, b"")

    def test_required_state_and_window_identity_fail_closed_without_sampling(self):
        initial = deepcopy(self.state)
        mutations = [lambda n: n.pop("opportunities"),
                     lambda n: n["opportunities"].update(version=True),
                     lambda n: n["opportunities"].update(current_window="missing"),
                     lambda n: n["opportunities"]["windows"].update({WINDOW: [True, 1]}),
                     lambda n: n["opportunities"]["windows"].update({WINDOW: [1, 0]}),
                     lambda n: n["opportunities"].update(decisions={}),
                     lambda n: n["entities"]["heidi"].pop("sociability"),
                     lambda n: n["entities"]["heidi"].update(sociability=10 ** 1000),
                     lambda n: n["entities"]["heidi"].update(archetype="unknown")]
        for mutate in mutations:
            self.state = deepcopy(initial)
            mutate(self.npc)
            before = deepcopy(self.state)
            rng = Mock()
            result = npc_activation.activate_npc_opportunity(self.state, "heidi", rng)
            self.assertEqual(result["decision_status"], "failed")
            self.assertNotIn("decision", result)
            rng.random.assert_not_called()
            self.assertEqual(self.state, before)
        self.state = initial
        for actor in (None, [], "", "outsider"):
            self.assertEqual(npc_activation.activate_npc_opportunity(self.state, actor)["decision_status"], "failed")

    def test_loading_does_not_initialize_opportunities(self):
        del self.npc["opportunities"]
        canon.save_state(self.state)
        loaded = canon.load_state()
        self.assertNotIn("opportunities", loaded["npc"])
        self.assertEqual(npc_activation.activate_npc_opportunity(loaded, "heidi")["decision_status"], "failed")
        canon.establish_npc_decision_window(loaded, "explicit", [0, 1])
        self.assertEqual(loaded["npc"]["opportunities"]["current_window"], "explicit")

    def test_window_lifecycle_is_explicit_forward_only_and_preserves_decisions(self):
        self.activate(roll=0)
        before = deepcopy(self.npc["opportunities"])
        with patch.object(canon, "_save_npc_commit") as save:
            self.assertFalse(canon.establish_npc_decision_window(self.state, WINDOW, [0, 1])["changed"])
            save.assert_not_called()
        for identity, bounds in [(WINDOW, [1, 2]), ("alias", [0, 1]), ("overlap", [-1, 1])]:
            with self.assertRaises(ValueError):
                canon.establish_npc_decision_window(self.state, identity, bounds)
        canon.establish_npc_decision_window(self.state, "afternoon", [1, 2])
        self.assertEqual(self.npc["opportunities"]["decisions"][WINDOW], before["decisions"][WINDOW])
        self.assertEqual(self.evaluate()["candidates"][1]["episode_id"], "fixture_afternoon")
        with self.assertRaises(ValueError):
            canon.establish_npc_decision_window(self.state, WINDOW, [0, 1])
        self.assertEqual(canon.load_state(), self.state)

    def test_exact_weights_draws_and_catalogue_normalization(self):
        self.assertEqual(self.evaluate()["candidates"], [
            {"kind": "no_initiation", "episode_id": None, "weight": 1},
            {"kind": "episode", "episode_id": EPISODE, "weight": 1.75}])
        self.add_alternative()
        candidates = self.evaluate()["candidates"]
        self.assertEqual([c["episode_id"] for c in candidates], [None, "alternative", EPISODE])
        self.assertEqual([c["weight"] for c in candidates], [1, .875, .875])
        self.assertEqual(sum(c["weight"] for c in candidates[1:]), 1.75)
        for roll, expected in [(0, None), (.4, "alternative"), (.99, EPISODE)]:
            self.assertEqual(self.proposal(roll=roll)["episode_id"], expected)
        # IDs are not conflated with the abstention sentinel.
        self.npc["episodes"]["no_initiation"] = self.npc["episodes"].pop("alternative")
        chosen = self.proposal(roll=.99)
        self.assertEqual((chosen["choice"], chosen["episode_id"]), ("episode", "no_initiation"))

    def test_eligibility_membership_disjoint_permissions_and_resolved_conflicts(self):
        self.add_alternative()
        self.assertEqual([c["episode_id"] for c in self.evaluate("chris")["candidates"]], [None, EPISODE])
        self.npc["episodes"][EPISODE]["allowed_places"] = {"heidi": ["a"], "chris": ["b"]}
        self.assertEqual([c["episode_id"] for c in self.evaluate()["candidates"]], [None, "alternative"])
        self.npc["resolutions"][EPISODE] = {"outcome": "no_interaction", "event_id": 1}
        self.assertEqual(len(self.evaluate()["candidates"]), 1)
        self.npc["resolutions"][EPISODE]["outcome"] = "conversation"
        self.assertEqual(self.evaluate()["status"], "unresolved")

    def test_invalid_catalogue_duplicates_history_and_config_are_not_abstention(self):
        initial = deepcopy(self.npc)
        mutations = [lambda n: n["episodes"].update(duplicate=deepcopy(n["episodes"][EPISODE])),
                     lambda n: n["episodes"][EPISODE].pop("allowed_places"),
                     lambda n: n["episodes"][EPISODE].update(participants=["heidi", "heidi"]),
                     lambda n: n["episodes"][EPISODE].update(display_name=""),
                     lambda n: n["resolutions"].update(unknown={"outcome": "conversation"}),
                     lambda n: n["entities"]["chris"].update(irritability=float("nan"))]
        for mutate in mutations:
            self.state["npc"] = deepcopy(initial)
            mutate(self.npc)
            self.assertEqual(self.evaluate()["status"], "unresolved")
        self.state["npc"] = initial
        with patch.object(npc_fixture, "NPC_INITIATION_POLICY", {}):
            self.assertEqual(self.evaluate()["status"], "unresolved")

    def test_persistent_abstention_changes_only_decision_history(self):
        before = deepcopy(self.state)
        rng = Mock(random=Mock(return_value=0))
        result = npc_activation.activate_npc_opportunity(self.state, "heidi", rng)
        self.assertEqual(result["decision_status"], "committed")
        self.assertEqual(result["decision"]["choice"], "no_initiation")
        self.assertEqual(result["episode_status"], "not_requested")
        before["npc"]["opportunities"]["decisions"][WINDOW]["heidi"] = result["decision"]
        self.assertEqual(self.state, before)
        self.assertEqual(canon.load_state(), self.state)
        self.state = canon.load_state()
        with patch.dict(sys.modules, {"npc_opportunity": None, "npc_opportunity_resolution": None}), \
                patch.object(npc_fixture, "NPC_INITIATION_POLICY", None):
            repeat = npc_activation.activate_npc_opportunity(self.state, "heidi", Mock())
        self.assertEqual(repeat["decision_status"], "reused")
        self.assertEqual(self.state, before)
        rng.random.assert_called_once()

    def test_no_eligible_episode_is_deterministic_abstention(self):
        self.npc["episodes"][EPISODE]["allowed_places"] = {"heidi": ["a"], "chris": ["b"]}
        rng = Mock()
        result = npc_activation.activate_npc_opportunity(self.state, "heidi", rng)
        self.assertEqual(result["decision"]["choice"], "no_initiation")
        self.assertEqual(self.npc["resolutions"], {})
        rng.random.assert_not_called()

    def test_selection_claims_both_participants_but_abstention_does_not(self):
        self.add_alternative()
        proposal = self.proposal(roll=.99)
        committed = canon.commit_npc_opportunity(self.state, proposal)
        self.assertEqual(committed["decision"]["episode_id"], EPISODE)
        # Pat's alternative with Heidi is blocked even though Pat did not decide yet.
        self.assertEqual(len(self.evaluate("pat")["candidates"]), 1)
        self.assertEqual(len(self.evaluate("chris")["candidates"]), 1)
        self.state["npc"] = npc_fixture.build_npc_fixture()
        self.activate(roll=0)
        self.assertEqual(self.evaluate("chris")["candidates"][1]["episode_id"], EPISODE)

    def test_independent_commitment_forgery_and_state_policy_freshness(self):
        proposal = self.proposal()
        for field, value in [("npc_id", "outsider"), ("window_id", "unknown"),
                             ("episode_id", "fixture_afternoon"), ("sampled", False), ("sampled", 1)]:
            forged = deepcopy(proposal)
            forged[field] = value
            self.rejected(forged)
        for field, value in [("candidates", []), ("basis", {}), ("policy_basis", {})]:
            forged = deepcopy(proposal)
            forged["possibilities"][field] = value
            self.rejected(forged)
        forged = deepcopy(proposal)
        forged["possibilities"]["candidates"][1]["weight"] = 100
        self.rejected(forged)
        self.npc["entities"]["heidi"]["sociability"] = .5
        self.rejected(proposal)
        self.npc["entities"]["heidi"]["sociability"] = .75
        with patch.object(npc_fixture, "NPC_INITIATION_POLICY", {}):
            self.rejected(proposal)
        with patch.dict(sys.modules, {"npc_opportunity": None, "npc_opportunity_resolution": None,
                                     "behavior": None, "npc_baseline": None}):
            self.assertTrue(canon.commit_npc_opportunity(self.state, proposal)["committed"])

    def test_competing_decisions_rejected_even_with_refreshed_basis(self):
        heidi, chris = self.proposal(), self.proposal("chris")
        canon.commit_npc_opportunity(self.state, heidi)
        self.rejected(chris)
        chris["possibilities"]["basis"] = deepcopy(self.npc)
        self.rejected(chris)
        repeat = canon.commit_npc_opportunity(self.state, heidi)
        self.assertTrue(repeat["reused"])
        heidi.update(choice="no_initiation", episode_id=None)
        self.rejected(heidi)

    def test_invalid_random_draws_do_not_commit(self):
        for value in (-1, 1, True, None, "0.5", float("nan"), float("inf")):
            before = deepcopy(self.state)
            result = self.activate(roll=value)
            self.assertEqual(result["decision_status"], "failed")
            self.assertEqual(self.state, before)

    def test_decision_and_window_persistence_failures_preserve_memory_and_disk(self):
        proposal = self.proposal()
        before, disk = deepcopy(self.state), self.path.read_bytes()
        for target in ("canon.json.dump", "canon.os.fsync", "canon.os.replace"):
            with patch(target, side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    canon.commit_npc_opportunity(self.state, proposal)
                with self.assertRaises(OSError):
                    canon.establish_npc_decision_window(self.state, "later", [1, 2])
            self.assertEqual(self.state, before)
            self.assertEqual(self.path.read_bytes(), disk)
            self.assertEqual(list(self.path.parent.glob(".npc-commit-*")), [])
        with patch.object(canon, "_save_npc_commit", side_effect=OSError("disk failure")), \
                patch.object(npc_activation, "activate_npc_episode") as activate:
            result = self.activate()
        self.assertEqual(result["decision_status"], "failed")
        activate.assert_not_called()

    def test_episode_failure_preserves_selection_and_requires_explicit_recovery(self):
        save = canon._save_npc_commit
        calls = []
        def fail_episode(pending):
            calls.append(deepcopy(pending))
            if len(calls) == 2:
                raise OSError("episode write failed")
            save(pending)
        with patch.object(canon, "_save_npc_commit", side_effect=fail_episode):
            result = self.activate()
        self.assertEqual((result["decision_status"], result["episode_status"]), ("committed", "failed"))
        self.assertEqual(self.npc["resolutions"], {})
        self.assertEqual(self.state["facts"], [])
        self.assertEqual(canon.load_state(), self.state)
        self.state = canon.load_state()
        rng = Mock()
        with patch.object(npc_activation, "activate_npc_episode") as activate:
            repeat = npc_activation.activate_npc_opportunity(self.state, "heidi", rng)
        self.assertEqual(repeat["episode_status"], "recovery_required")
        activate.assert_not_called()
        rng.random.assert_not_called()
        record = repeat["decision"]
        episode_id = validate_opportunity_handoff(self.npc, record)
        self.assertTrue(npc_activation.activate_npc_episode(self.state, episode_id,
                        Mock(random=Mock(return_value=.99)))["committed"])
        self.assertEqual(self.activate()["episode_status"], "activated")

    def test_unexpected_episode_exception_is_partial_success_not_retry(self):
        with patch.object(npc_activation, "activate_npc_episode", side_effect=RuntimeError("dependency failure")):
            result = self.activate()
        self.assertEqual(result["decision_status"], "committed")
        self.assertEqual(result["episode_status"], "failed")
        self.assertEqual(result["error_type"], "RuntimeError")
        self.assertEqual(self.activate()["episode_status"], "recovery_required")

    def test_snapshots_survive_definition_change_and_removal_but_block_recovery(self):
        record = canon.commit_npc_opportunity(self.state, self.proposal())["decision"]
        original = deepcopy(record)
        self.npc["episodes"][EPISODE]["window"] = [4, 5]
        self.assertEqual(self.activate()["decision"], original)
        with self.assertRaises(ValueError):
            validate_opportunity_handoff(self.npc, record)
        self.assertEqual(self.evaluate("chris")["status"], "unresolved")
        del self.npc["episodes"][EPISODE]
        self.assertEqual(self.activate()["decision"], original)
        with self.assertRaises(ValueError):
            validate_opportunity_handoff(self.npc, record)
        self.assertEqual(len(self.evaluate("chris")["candidates"]), 1)

    def test_success_preserves_episode_outcomes_transitions_and_history_reuse(self):
        for entity in self.npc["entities"].values():
            entity.update(irritability=.1, sociability=.1)
        result = self.activate()
        self.assertEqual((result["decision_status"], result["episode_status"]), ("committed", "activated"))
        self.assertEqual(result["episode"]["outcome"], "disagreement")
        self.assertEqual([t["committed"] for t in result["episode"]["transitions"]], [True, True, True])
        self.assertEqual(self.state["facts"], [{"id": 1, "type": "event", "status": "active",
                         "text": "Heidi and Chris argued during the fixture morning."}])
        self.assertNotIn("disagreement_initiator", self.npc["resolutions"][EPISODE])
        before = deepcopy(self.state)
        with patch.object(npc_activation, "activate_npc_episode") as activate, \
                patch.dict(sys.modules, {"npc_opportunity": None, "npc_baseline": None}), \
                patch.object(npc_fixture, "NPC_INITIATION_POLICY", None):
            repeat = self.activate()
        activate.assert_not_called()
        self.assertEqual(repeat["decision_status"], "reused")
        self.assertEqual(self.state, before)
        del self.npc["episodes"][EPISODE]
        self.assertEqual(self.activate()["episode_status"], "activated")

    def test_transition_partial_success_is_preserved_without_replay(self):
        for entity in self.npc["entities"].values():
            entity.update(irritability=.1, sociability=.1)
        save, count = canon._save_npc_commit, 0
        def fail_transition(pending):
            nonlocal count
            count += 1
            if count == 4:  # decision, episode, transition one, transition two
                raise OSError("transition failed")
            save(pending)
        with patch.object(canon, "_save_npc_commit", side_effect=fail_transition):
            result = self.activate()
        self.assertEqual(result["episode_status"], "activated")
        self.assertEqual([t["committed"] for t in result["episode"]["transitions"]], [True, False, True])
        before = deepcopy(self.state)
        with patch.object(npc_activation, "process_npc_transitions_for_episode") as transitions:
            self.activate()
        transitions.assert_not_called()
        self.assertEqual(self.state, before)

    def test_selected_opportunity_can_resolve_no_interaction(self):
        rng = Mock(random=Mock(side_effect=[.99, 0]))
        result = npc_activation.activate_npc_opportunity(self.state, "heidi", rng)
        self.assertEqual(result["decision"]["choice"], "episode")
        self.assertEqual(result["episode"]["outcome"], "no_interaction")
        self.assertEqual(self.state["facts"][0]["text"],
                         "Heidi and Chris did not interact during the fixture morning.")
        self.assertEqual(len(self.state["facts"]), 1)
        self.assertEqual(rng.random.call_count, 2)
        self.assertEqual(len(self.evaluate("chris")["candidates"]), 1)

    def test_explicit_recovery_rejects_new_resolved_participant_conflict(self):
        self.add_alternative()
        record = canon.commit_npc_opportunity(self.state, self.proposal(roll=.99))["decision"]
        self.npc["resolutions"]["alternative"] = {"outcome": "conversation", "event_id": 1}
        with self.assertRaisesRegex(ValueError, "resolved_participant_conflict"):
            validate_opportunity_handoff(self.npc, record)
        # No silent retry or loss of the originally selected opportunity.
        self.assertEqual(self.activate()["episode_status"], "recovery_required")

    def test_corrupt_records_and_overlapping_claims_fail_closed(self):
        record = canon.commit_npc_opportunity(self.state, self.proposal())["decision"]
        initial = deepcopy(self.npc)
        for mutate in (lambda r: r.update(window=[1, 2]), lambda r: r.update(version=True),
                       lambda r: r.update(choice="invented"), lambda r: r["episode"].update(participants=[])):
            self.state["npc"] = deepcopy(initial)
            mutate(self.npc["opportunities"]["decisions"][WINDOW]["heidi"])
            self.assertEqual(self.activate()["decision_status"], "failed")
        self.state["npc"] = initial
        other = deepcopy(record)
        other["npc_id"] = "chris"
        self.npc["opportunities"]["decisions"][WINDOW]["chris"] = other
        with self.assertRaises(ValueError):
            opportunity_state(self.npc)


if __name__ == "__main__":
    unittest.main()
