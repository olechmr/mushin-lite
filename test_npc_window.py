"""Host roster regression tests; standard library and temporary persistence only."""
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
import npc_opportunity
import npc_window
from npc_opportunity_rules import validate_opportunity_handoff

WINDOW = "fixture_morning_window"
EPISODE = "fixture_morning"


class WindowProcessingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "state.json"
        redirect = patch.object(canon, "STATE_FILE", str(self.path))
        redirect.start()
        self.addCleanup(redirect.stop)
        self.state = {"facts": [], "next_fact_id": 1, "npc": npc_fixture.build_npc_fixture()}
        canon.save_state(self.state)
        self.rng = Mock(random=Mock(return_value=.99))

    def process(self, roster=("heidi", "chris"), window=WINDOW):
        return npc_window.process_npc_decision_window(self.state, window, roster, self.rng)

    def test_invalid_window_and_roster_reject_before_evaluation_sampling_or_write(self):
        cases = [(None, ["heidi"]), ([], ["heidi"]), ("wrong", ["heidi"]),
                 (WINDOW, None), (WINDOW, "heidi"), (WINDOW, {"heidi"}),
                 (WINDOW, ["heidi", "heidi"]), (WINDOW, ["chris", "outsider"]),
                 (WINDOW, ["chris", []]), (WINDOW, ["chris", None]),
                 (WINDOW, ["chris", " "]), (WINDOW, ["chris", "Heidi"])]
        before, disk = deepcopy(self.state), self.path.read_bytes()
        with patch.object(npc_window, "activate_npc_opportunity") as activate, \
                patch.object(npc_opportunity, "evaluate_npc_opportunities") as evaluate, \
                patch.object(canon, "_save_npc_commit") as save:
            for window, roster in cases:
                with self.subTest(window=window, roster=roster):
                    result = self.process(roster, window)
                    self.assertEqual(result["status"], "rejected")
                    self.assertEqual(result["processed_npc_ids"], [])
                    self.assertIsNone(result["decisions_complete"])
            activate.assert_not_called()
            evaluate.assert_not_called()
            save.assert_not_called()
        self.rng.random.assert_not_called()
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), disk)

    def test_entire_roster_authorized_before_first_member(self):
        initial = deepcopy(self.state)
        for change in ({"archetype": "unknown"}, {"sociability": None}):
            self.state = deepcopy(initial)
            self.state["npc"]["entities"]["heidi"].update(change)
            with patch.object(npc_window, "activate_npc_opportunity") as activate:
                self.assertEqual(self.process()["status"], "rejected")
                activate.assert_not_called()
        self.rng.random.assert_not_called()
        self.assertEqual(canon.load_state(), initial)

    def test_missing_storage_and_window_fail_closed(self):
        for state in (None, {}, {"npc": npc_fixture.build_npc_fixture()},
                      {"facts": [], "next_fact_id": True, "npc": npc_fixture.build_npc_fixture()}):
            result = npc_window.process_npc_decision_window(state, WINDOW, ["heidi"], self.rng)
            self.assertEqual(result["status"], "rejected")
        del self.state["npc"]["opportunities"]
        self.assertEqual(self.process()["status"], "rejected")
        self.assertNotIn("opportunities", self.state["npc"])
        self.rng.random.assert_not_called()

    def test_empty_roster_is_noop(self):
        before = deepcopy(self.state)
        result = self.process([])
        self.assertTrue(result["decisions_complete"])
        self.assertTrue(result["processing_complete"])
        self.assertEqual(self.state, before)
        self.rng.random.assert_not_called()

    def test_stable_order_fresh_state_and_participant_conflict(self):
        observed = []
        evaluate = npc_opportunity.evaluate_npc_opportunities
        def record(npc, actor):
            observed.append((actor, deepcopy(npc)))
            return evaluate(npc, actor)
        with patch.object(npc_opportunity, "evaluate_npc_opportunities", side_effect=record):
            result = self.process()
        self.assertEqual(result["requested_npc_ids"], ["heidi", "chris"])
        self.assertEqual(result["processing_order"], ["chris", "heidi"])
        self.assertEqual(result["processed_npc_ids"], ["chris", "heidi"])
        self.assertEqual([a for a, _ in observed], ["chris", "heidi"])
        self.assertEqual(observed[0][1]["resolutions"], {})
        self.assertEqual(observed[1][1]["resolutions"][EPISODE]["outcome"], "disagreement")
        self.assertEqual(observed[1][1]["entities"]["heidi"]["irritability"], .5)
        self.assertEqual(result["results"][1]["decision"]["choice"], "no_initiation")
        self.assertEqual(self.rng.random.call_count, 2)
        self.assertTrue(result["processing_complete"])
        self.assertTrue(result["decisions_complete"])
        self.assertEqual(len(self.state["facts"]), 1)
        self.assertEqual(canon.load_state(), self.state)

    def test_repeated_reload_and_provider_removal_reuse_without_sampling(self):
        self.process()
        self.state = canon.load_state()
        before, disk = deepcopy(self.state), self.path.read_bytes()
        self.rng.reset_mock()
        with patch.dict(sys.modules, {"npc_opportunity": None, "npc_baseline": None}), \
                patch.object(npc_fixture, "NPC_INITIATION_POLICY", None), \
                patch.object(npc_activation, "activate_npc_episode") as episode:
            result = self.process()
            episode.assert_not_called()
        self.assertEqual([r["decision_status"] for r in result["results"]], ["reused", "reused"])
        self.assertEqual(result["results"][0]["followup_status"], "unknown")
        self.assertTrue(result["processing_complete"])
        self.rng.random.assert_not_called()
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), disk)

    def test_persistence_failure_preserves_prefix_and_reload_continues(self):
        self.rng.random.return_value = 0  # two independent abstentions
        save = canon._save_npc_commit
        count = 0
        def fail_second(pending):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("disk failure")
            save(pending)
        with patch.object(canon, "_save_npc_commit", side_effect=fail_second):
            result = self.process()
        self.assertEqual(result["status"], "stopped")
        self.assertFalse(result["decisions_complete"])
        self.assertFalse(result["processing_complete"])
        self.assertEqual([r["decision_status"] for r in result["results"]], ["committed", "failed"])
        self.assertEqual(list(self.state["npc"]["opportunities"]["decisions"][WINDOW]), ["chris"])
        self.assertEqual(canon.load_state(), self.state)
        self.state = canon.load_state()
        self.rng.reset_mock()
        resumed = self.process()
        self.assertEqual([r["decision_status"] for r in resumed["results"]], ["reused", "committed"])
        self.rng.random.assert_called_once()
        self.assertTrue(resumed["processing_complete"])
        self.assertEqual(self.state["facts"], [])

    def test_first_write_failure_leaves_later_npc_unprocessed(self):
        before, disk = deepcopy(self.state), self.path.read_bytes()
        with patch("canon.os.replace", side_effect=OSError("disk failure")):
            result = self.process()
        self.assertEqual(result["processed_npc_ids"], ["chris"])
        self.assertEqual(result["unprocessed_npc_ids"], ["heidi"])
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), disk)

    def test_episode_failure_stops_and_explicit_recovery_is_required(self):
        with patch.object(npc_activation, "commit_npc_resolution", side_effect=OSError("episode failure")):
            result = self.process()
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["unprocessed_npc_ids"], ["heidi"])
        self.assertEqual(result["results"][0]["decision_status"], "committed")
        self.assertEqual(self.state["facts"], [])
        self.state = canon.load_state()
        self.rng.reset_mock()
        with patch.object(npc_activation, "activate_npc_episode") as episode:
            repeat = self.process()
            episode.assert_not_called()
        self.assertEqual(repeat["results"][0]["episode_status"], "recovery_required")
        self.rng.random.assert_not_called()
        record = repeat["results"][0]["decision"]
        episode_id = validate_opportunity_handoff(self.state["npc"], record)
        npc_activation.activate_npc_episode(self.state, episode_id, self.rng)
        self.assertTrue(self.process()["processing_complete"])

    def test_decision_completion_is_distinct_from_episode_success(self):
        with patch.object(npc_activation, "activate_npc_episode", side_effect=RuntimeError("failed")):
            result = self.process(["chris"])
        self.assertTrue(result["decisions_complete"])
        self.assertFalse(result["processing_complete"])
        self.assertEqual(result["results"][0]["episode_status"], "failed")
        self.assertEqual(canon.load_state(), self.state)

    def test_transition_failure_stops_roster_without_replay(self):
        with patch.object(npc_activation, "commit_npc_transition", side_effect=OSError("transition failure")):
            result = self.process()
        self.assertEqual(result["results"][0]["followup_status"], "failed")
        self.assertEqual(result["results"][0]["episode_status"], "activated")
        self.assertEqual(result["unprocessed_npc_ids"], ["heidi"])
        self.assertFalse(result["processing_complete"])
        self.state = canon.load_state()
        with patch.object(npc_activation, "process_npc_transitions_for_episode") as transitions:
            repeat = self.process()
            transitions.assert_not_called()
        self.assertEqual(repeat["results"][0]["followup_status"], "unknown")
        self.assertTrue(repeat["processing_complete"])
        self.assertTrue(repeat["decisions_complete"])
        self.assertEqual(len(self.state["facts"]), 1)

    def test_unresolved_transition_is_failure_but_no_change_is_not(self):
        with patch.object(npc_activation, "evaluate_transition", return_value={"status": "unresolved", "reasons": ["invalid"]}):
            result = self.process(["chris"])
        self.assertEqual(result["results"][0]["followup_status"], "failed")
        self.assertTrue(result["decisions_complete"])
        self.assertFalse(result["processing_complete"])

    def test_no_interaction_no_change_and_no_implicit_advancement(self):
        windows = deepcopy(self.state["npc"]["opportunities"]["windows"])
        self.rng.random.side_effect = [.99, 0]
        with patch.object(canon, "establish_npc_decision_window", side_effect=AssertionError("must not advance")):
            result = self.process()
        self.assertEqual(result["results"][0]["episode"]["outcome"], "no_interaction")
        self.assertEqual(result["results"][0]["followup_status"], "completed")
        self.assertTrue(result["processing_complete"])
        self.assertEqual(self.state["npc"]["opportunities"]["windows"], windows)
        self.assertEqual(self.state["npc"]["opportunities"]["current_window"], WINDOW)
        canon.establish_npc_decision_window(self.state, "later", [1, 2])
        self.assertEqual(self.process()["status"], "rejected")

    def test_unprocessed_existing_decision_counts_toward_completion(self):
        npc_activation.activate_npc_opportunity(self.state, "heidi", Mock(random=Mock(return_value=0)))
        with patch.object(npc_activation, "activate_npc_episode", side_effect=RuntimeError("failed")):
            result = self.process()
        self.assertEqual(result["unprocessed_npc_ids"], ["heidi"])
        self.assertTrue(result["decisions_complete"])
        self.assertFalse(result["processing_complete"])

    def test_import_and_processing_without_player_or_presentation(self):
        script = '''
import sys
for name in ("main", "renderer", "llm_adapter", "openai", "requests", "map_data"):
    sys.modules[name] = None
import canon
canon.STATE_FILE = sys.argv[1]
from npc_window import process_npc_decision_window
from npc_fixture import build_npc_fixture
from types import SimpleNamespace
from pathlib import Path
assert not Path(canon.STATE_FILE).exists()
state = {"facts": [], "next_fact_id": 1, "npc": build_npc_fixture()}
result = process_npc_decision_window(state, "fixture_morning_window", ["heidi", "chris"], SimpleNamespace(random=lambda: .99))
assert result["processing_complete"], result
assert len(state["facts"]) == 1
'''
        result = subprocess.run([sys.executable, "-B", "-c", script, str(self.path.parent / "isolated.json")],
                                cwd=Path(__file__).resolve().parent, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
