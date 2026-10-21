"""Standard-library regressions for the bounded interaction_v1 decision path."""
from copy import deepcopy
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import canon
import npc_fixture
from npc_activation import activate_npc_episode
from npc_baseline import evaluate_baseline_episode
from collapse import collapse_npc_episode, resolve_npc_episode_possibilities

EPISODE = "fixture_morning"


class BaselineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "state.json"
        redirect = patch.object(canon, "STATE_FILE", str(self.path))
        redirect.start()
        self.addCleanup(redirect.stop)
        self.state = {"facts": [], "next_fact_id": 1, "npc": npc_fixture.build_npc_fixture()}
        canon.save_state(self.state)

    @property
    def npc(self):
        return self.state["npc"]

    def proposal(self, roll=0.5):
        return collapse_npc_episode(self.npc, EPISODE, Mock(random=Mock(return_value=roll)))

    def assert_rejected(self, proposal):
        before, disk = deepcopy(self.state), self.path.read_bytes()
        with self.assertRaises(ValueError):
            canon.commit_npc_resolution(self.state, proposal)
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), disk)

    def test_pure_evaluation_and_no_provider_stage_dependencies(self):
        before = deepcopy(self.npc)
        first = evaluate_baseline_episode(self.npc, EPISODE)
        self.assertEqual(first, evaluate_baseline_episode(self.npc, EPISODE))
        self.assertEqual(first["weights"], {"no_interaction": 1, "conversation": 3.5, "disagreement": 2})
        self.assertEqual(self.npc, before)
        first["basis"]["entities"].clear()
        first["policy_basis"]["conversation"] = 999
        self.assertEqual(self.npc, before)
        self.assertEqual(npc_fixture.NPC_ARCHETYPES["interaction_v1"]["conversation"], 2.5)
        script = '''
import sys
for name in ("behavior", "collapse", "canon", "npc_activation", "renderer", "llm_adapter"):
    sys.modules[name] = None
from npc_baseline import evaluate_baseline_episode
from npc_fixture import build_npc_fixture
assert evaluate_baseline_episode(build_npc_fixture(), "fixture_morning")["feasibility"] == "possible"
'''
        subprocess.run([sys.executable, "-B", "-c", script], check=True,
                       cwd=Path(__file__).resolve().parent, capture_output=True, text=True)

    def test_fixed_draws_and_seeded_results_match_existing_weight_policy(self):
        for roll, expected in [(0, "no_interaction"), (.2, "conversation"), (.99, "disagreement")]:
            with self.subTest(roll=roll):
                self.assertEqual(self.proposal(roll)["outcome"], expected)
        for seed in range(20):
            roll = random.Random(seed).random()
            expected = "no_interaction" if roll < 1 / 6.5 else "conversation" if roll < 4.5 / 6.5 else "disagreement"
            result = collapse_npc_episode(self.npc, EPISODE, random.Random(seed))
            self.assertEqual(result["outcome"], expected)

    def test_history_bias_only_earlier_same_pair_and_not_record_count(self):
        self.npc["resolutions"][EPISODE] = {"outcome": "disagreement", "event_id": 1}
        self.assertEqual(evaluate_baseline_episode(self.npc, "fixture_afternoon")["weights"]["disagreement"], 3)
        self.npc["episodes"]["earlier"] = deepcopy(self.npc["episodes"][EPISODE])
        self.npc["resolutions"]["earlier"] = {"outcome": "disagreement", "event_id": 2}
        self.assertEqual(evaluate_baseline_episode(self.npc, "fixture_afternoon")["weights"]["disagreement"], 3)
        self.npc["episodes"][EPISODE]["window"] = [2, 3]
        self.npc["episodes"]["earlier"]["window"] = [2, 3]
        self.assertEqual(evaluate_baseline_episode(self.npc, "fixture_afternoon")["weights"]["disagreement"], 2)

    def test_missing_unknown_binding_and_invalid_configuration_fail_closed(self):
        del self.npc["entities"]["heidi"]["archetype"]
        self.assertEqual(evaluate_baseline_episode(self.npc, EPISODE)["feasibility"], "unresolved")
        for binding in (None, "unknown", 1):
            with self.subTest(binding=binding):
                self.npc["entities"]["heidi"]["archetype"] = binding
                rng = Mock()
                self.assertEqual(activate_npc_episode(self.state, EPISODE, rng)["activation_status"], "failed")
                rng.random.assert_not_called()
        self.npc["entities"]["heidi"]["archetype"] = "interaction_v1"
        for config in ({}, {"interaction_v1": {}}, None):
            with patch.object(npc_fixture, "NPC_ARCHETYPES", config):
                self.assertEqual(evaluate_baseline_episode(self.npc, EPISODE)["feasibility"], "unresolved")
        self.assertEqual(self.state["facts"], [])

    def test_forged_candidates_rejected_by_resolution_and_commitment(self):
        original = self.proposal()
        mutations = [lambda e: e.update(version=2), lambda e: e.update(archetype="unknown"),
                     lambda e: e.update(episode_id="fixture_afternoon"),
                     lambda e: e.update(allowed_outcomes=["conversation"]),
                     lambda e: e["weights"].update(conversation=999),
                     lambda e: e["weights"].update(no_interaction=True),
                     lambda e: e["weights"].update(disagreement=float("nan")),
                     lambda e: e.update(feasibility="impossible"),
                     lambda e: e.pop("policy_basis"), lambda e: e.pop("basis"),
                     lambda e: e.pop("reasons")]
        for mutate in mutations:
            proposal = deepcopy(original)
            mutate(proposal["possibilities"])
            rng = Mock()
            result = resolve_npc_episode_possibilities(self.npc, EPISODE, proposal["possibilities"], rng)
            self.assertIsNone(result["outcome"])
            rng.random.assert_not_called()
            self.assert_rejected(proposal)

    def test_commitment_does_not_require_proposal_provider(self):
        proposal = self.proposal()
        with patch.dict(sys.modules, {"npc_baseline": None, "behavior": None}):
            self.assertTrue(canon.commit_npc_resolution(self.state, proposal)["committed"])
        self.assertEqual(len(self.state["facts"]), 1)

    def test_current_state_and_policy_changes_invalidate_proposals(self):
        proposal = self.proposal()
        self.npc["entities"]["heidi"]["sociability"] = .2
        self.assert_rejected(proposal)
        self.npc["entities"]["heidi"]["sociability"] = .75
        config = deepcopy(npc_fixture.NPC_ARCHETYPES)
        config["interaction_v1"]["conversation"] = 3.0
        with patch.object(npc_fixture, "NPC_ARCHETYPES", config):
            self.assert_rejected(proposal)
        self.npc["entities"]["heidi"]["archetype"] = "unknown"
        proposal["basis"] = deepcopy(self.npc)
        proposal["possibilities"]["basis"] = deepcopy(self.npc)
        self.assert_rejected(proposal)

    def test_no_interaction_is_committable_but_missing_constraints_are_not(self):
        places = self.npc["episodes"][EPISODE]["allowed_places"]
        places.update(heidi=["study"], chris=["hallway"])
        rng = Mock()
        result = activate_npc_episode(self.state, EPISODE, rng)
        self.assertTrue(result["committed"])
        self.assertEqual(result["outcome"], "no_interaction")
        self.assertFalse(result["sampled"])
        rng.random.assert_not_called()
        self.assertEqual(self.state["facts"][0]["text"], "Heidi and Chris did not interact during the fixture morning.")
        self.npc["episodes"]["fixture_afternoon"].pop("allowed_places")
        self.assertEqual(activate_npc_episode(self.state, "fixture_afternoon", rng)["activation_status"], "failed")
        self.assertEqual(len(self.state["facts"]), 1)

    def test_history_reuse_without_provider_configuration_or_current_attributes(self):
        canon.commit_npc_resolution(self.state, self.proposal())
        for entity in self.npc["entities"].values():
            entity.pop("archetype")
            entity.pop("sociability")
        before, disk = deepcopy(self.state), self.path.read_bytes()
        with patch.dict(sys.modules, {"npc_baseline": None}), patch.object(npc_fixture, "NPC_ARCHETYPES", None):
            rng = Mock()
            result = activate_npc_episode(self.state, EPISODE, rng)
            self.assertEqual(result["activation_status"], "reused")
            rng.random.assert_not_called()
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), disk)

    def test_original_proposal_flags_outcomes_and_metadata_rejections(self):
        original = self.proposal()
        for field, value in [("episode_id", "absent"), ("outcome", "invented"),
                             ("basis", None), ("feasibility", "impossible"),
                             ("reused", True), ("sampled", False), ("sampled", 1)]:
            proposal = deepcopy(original)
            proposal[field] = value
            self.assert_rejected(proposal)
        self.npc["entities"]["heidi"]["display_name"] = ""
        self.assert_rejected(self.proposal())
        self.npc["entities"]["heidi"]["display_name"] = "Heidi"
        self.npc["episodes"][EPISODE]["display_name"] = ""
        self.assert_rejected(self.proposal())

    def test_invalid_inputs_and_contradictory_history_cannot_be_authorized_with_fresh_basis(self):
        original = deepcopy(self.npc)
        mutations = [lambda n: n.update(version=True),
                     lambda n: n["episodes"][EPISODE].update(participants=["heidi", "heidi"]),
                     lambda n: n["episodes"][EPISODE].update(window=[1, 0]),
                     lambda n: n["episodes"][EPISODE].update(allowed_places={}),
                     lambda n: n["entities"]["heidi"].update(irritability=True),
                     lambda n: n["entities"]["heidi"].update(sociability=float("nan")),
                     lambda n: n["resolutions"].update(unknown={"outcome": "conversation"}),
                     lambda n: n["resolutions"].update(fixture_afternoon={"outcome": "invented"})]
        proposal = self.proposal()
        for mutate in mutations:
            self.state["npc"] = deepcopy(original)
            mutate(self.npc)
            forged = deepcopy(proposal)
            forged["basis"] = deepcopy(self.npc)
            forged["possibilities"]["basis"] = deepcopy(self.npc)
            self.assert_rejected(forged)
            self.assertEqual(evaluate_baseline_episode(self.npc, EPISODE)["feasibility"], "unresolved")
        self.state["npc"] = deepcopy(original)
        self.npc["episodes"]["fixture_afternoon"]["allowed_places"] = {"heidi": ["a"], "chris": ["b"]}
        self.npc["resolutions"]["fixture_afternoon"] = {"outcome": "conversation"}
        forged = deepcopy(proposal)
        forged["basis"] = deepcopy(self.npc)
        forged["possibilities"]["basis"] = deepcopy(self.npc)
        self.assert_rejected(forged)

    def test_recommit_conflict_and_persistence_failure_preserve_history(self):
        proposal = self.proposal()
        before, disk = deepcopy(self.state), self.path.read_bytes()
        with patch.object(canon, "_save_npc_commit", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                canon.commit_npc_resolution(self.state, proposal)
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), disk)
        canon.commit_npc_resolution(self.state, proposal)
        history = deepcopy(self.state)
        self.assertTrue(canon.commit_npc_resolution(self.state, proposal)["reused"])
        self.assertEqual(self.state, history)
        proposal["outcome"] = "disagreement"
        self.assert_rejected(proposal)


if __name__ == "__main__":
    unittest.main()
