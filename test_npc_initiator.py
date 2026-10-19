"""Regression checks for existing initiator refinement.

Run from the repository root: python -m unittest -v test_npc_initiator
Uses only the standard library; all persistence is redirected to temporary files.
This covers the bounded prototype, not autonomous NPC activity or crash safety.
"""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import canon
from behavior import evaluate_disagreement_initiator
from collapse import collapse_disagreement_initiator, collapse_npc_episode
from npc_fixture import build_npc_fixture


EPISODE = "fixture_morning"


class InitiatorRefinementTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "state.json"
        redirect = patch.object(canon, "STATE_FILE", str(self.path))
        redirect.start()
        self.addCleanup(redirect.stop)
        self.state = {
            "facts": [{"id": 1, "type": "state", "status": "active",
                       "text": "The book is in the foyer."}],
            "next_fact_id": 2,
            "npc": build_npc_fixture(),
        }
        canon.save_state(self.state)

    def resolve(self, episode=EPISODE, roll=0.99):
        proposal = collapse_npc_episode(self.state["npc"], episode,
                                        rng=Mock(random=Mock(return_value=roll)))
        return canon.commit_npc_resolution(self.state, proposal)

    def propose(self, roll=0.0):
        return collapse_disagreement_initiator(
            self.state["npc"], EPISODE, rng=Mock(random=Mock(return_value=roll)))

    def assert_rejected_without_write(self, proposal):
        before, saved = deepcopy(self.state), self.path.read_bytes()
        with patch.object(canon, "_save_npc_commit") as save:
            with self.assertRaises(ValueError):
                canon.commit_disagreement_initiator(self.state, proposal)
            save.assert_not_called()
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), saved)

    def test_valid_refinement_preserves_all_other_state_and_history(self):
        self.resolve()
        self.resolve("fixture_afternoon")
        self.assertEqual(self.state["npc"]["resolutions"][EPISODE]["outcome"],
                         "disagreement")
        before, saved = deepcopy(self.state), self.path.read_bytes()
        evaluation = evaluate_disagreement_initiator(self.state["npc"], EPISODE)
        self.assertEqual(evaluation["status"], "possible")
        self.assertEqual(evaluation["weights"], {"chris": 1.75, "heidi": 1.25})
        # Fixed draws exercise both permitted participants, without statistical tests.
        for roll, actor in ((0.0, "chris"), (0.99, "heidi")):
            with self.subTest(actor=actor):
                proposal = self.propose(roll)
                self.assertEqual(proposal["status"], "proposed")
                self.assertEqual(proposal["disagreement_initiator"], actor)
                self.assertEqual(self.state, before)
                self.assertEqual(self.path.read_bytes(), saved)
        result = canon.commit_disagreement_initiator(self.state, proposal)
        self.assertEqual(result, {"committed": True, "reused": False,
                                  "disagreement_initiator": "heidi"})
        expected = deepcopy(before)
        expected["npc"]["resolutions"][EPISODE]["disagreement_initiator"] = "heidi"
        # Exact equality also excludes extra events, causes, whereabouts, changed
        # dispositions, fact IDs, or alterations to either episode's history.
        self.assertEqual(self.state, expected)
        self.assertEqual(canon.load_state(), expected)

    def test_missing_or_unauthorized_history_never_samples_or_invents_activity(self):
        cases = [("unresolved episode", None, EPISODE, "unresolved"),
                 ("unauthorized episode", None, "fixture_afternoon", "unresolved"),
                 ("conversation", 0.3, EPISODE, "not_applicable"),
                 ("no interaction", 0.0, EPISODE, "not_applicable")]
        initial = deepcopy(self.state)
        for label, roll, episode, status in cases:
            with self.subTest(label=label):
                self.state = deepcopy(initial)
                canon.save_state(self.state)
                if roll is not None:
                    self.resolve(roll=roll)
                before, saved = deepcopy(self.state), self.path.read_bytes()
                rng = Mock()
                proposal = collapse_disagreement_initiator(self.state["npc"], episode, rng)
                self.assertEqual(proposal["status"], status)
                self.assertIsNone(proposal["disagreement_initiator"])
                rng.random.assert_not_called()
                self.assertEqual(self.state, before)
                self.assertEqual(self.path.read_bytes(), saved)
                # A caller claiming successful sampling cannot authorize history.
                forged = dict(proposal, status="proposed", sampled=True,
                              disagreement_initiator="chris", basis=deepcopy(self.state["npc"]))
                self.assert_rejected_without_write(forged)

    def test_invalid_proposals_fail_closed(self):
        self.resolve()
        valid = self.propose()
        cases = [None, {}]
        for field in valid:
            missing = deepcopy(valid)
            del missing[field]
            cases.append(missing)
        for changes in ({"status": "resolved"}, {"sampled": False},
                        {"reused": True}, {"basis": None},
                        {"disagreement_initiator": "outsider"},
                        {"episode_id": "fixture_afternoon"},
                        {"reasons": ["invented authorization"]},
                        {"cause": "invented cause"}):
            cases.append(dict(valid, **changes))
        for index, proposal in enumerate(cases):
            with self.subTest(case=index):
                self.assert_rejected_without_write(proposal)

    def test_stale_proposal_rejected_after_persisted_disposition_change(self):
        self.resolve()
        proposal = self.propose()
        canon.set_npc_disposition(self.state, "heidi", "irritability", 0.5)
        self.assert_rejected_without_write(proposal)
        self.assertEqual(canon.load_state(), self.state)

    def test_current_basis_does_not_replace_authorization(self):
        self.resolve()
        proposal = self.propose()
        # Even a matching snapshot must not authorize contradictory constraints.
        self.state["npc"]["episodes"][EPISODE]["allowed_places"] = {
            "heidi": ["foyer"], "chris": ["study"]}
        proposal["basis"] = deepcopy(self.state["npc"])
        self.assert_rejected_without_write(proposal)

    def test_recommit_is_idempotent_and_conflicting_actor_is_rejected(self):
        self.resolve()
        proposal = self.propose()
        canon.commit_disagreement_initiator(self.state, proposal)
        before, saved = deepcopy(self.state), self.path.read_bytes()
        with patch.object(canon, "_save_npc_commit") as save:
            result = canon.commit_disagreement_initiator(self.state, proposal)
            self.assertEqual(result, {"committed": False, "reused": True,
                                      "disagreement_initiator": "chris"})
            save.assert_not_called()
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), saved)
        self.assert_rejected_without_write(dict(proposal, disagreement_initiator="heidi"))

    def test_reload_reuses_history_without_current_weights_or_random_draw(self):
        self.resolve()
        proposal = self.propose()
        canon.commit_disagreement_initiator(self.state, proposal)
        self.state = canon.load_state()
        del self.state["npc"]["entities"]["chris"]["irritability"]
        before, saved = deepcopy(self.state), self.path.read_bytes()
        rng = Mock()
        reused = collapse_disagreement_initiator(self.state["npc"], EPISODE, rng)
        self.assertEqual(reused["status"], "resolved")
        self.assertTrue(reused["reused"])
        self.assertFalse(reused["sampled"])
        self.assertEqual(reused["disagreement_initiator"], "chris")
        rng.random.assert_not_called()
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), saved)

    def test_invalid_random_draws_cannot_be_committed(self):
        self.resolve()
        for draw in (-0.1, 1.0, float("nan"), float("inf"), True, "0.5"):
            with self.subTest(draw=draw):
                proposal = self.propose(draw)
                self.assertEqual(proposal["status"], "unresolved")
                self.assertIsNone(proposal["disagreement_initiator"])
                self.assert_rejected_without_write(proposal)

    def test_persistence_failures_preserve_memory_disk_and_episode(self):
        self.resolve()
        proposal = self.propose()
        before, saved = deepcopy(self.state), self.path.read_bytes()
        for target in ("canon.json.dump", "canon.os.fsync", "canon.os.replace"):
            with self.subTest(failure=target):
                with patch(target, side_effect=OSError("simulated save failure")):
                    with self.assertRaises(OSError):
                        canon.commit_disagreement_initiator(self.state, proposal)
                self.assertEqual(self.state, before)
                self.assertEqual(self.path.read_bytes(), saved)
                self.assertEqual(list(self.path.parent.glob(".npc-commit-*")), [])
        # An explicit retry after a known pre-replacement failure can still commit.
        self.assertTrue(canon.commit_disagreement_initiator(self.state, proposal)["committed"])
        self.assertEqual(json.loads(self.path.read_text()), self.state)


if __name__ == "__main__":
    unittest.main()
