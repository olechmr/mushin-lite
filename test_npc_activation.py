"""Run with python -m unittest -v test_npc_activation (standard library only)."""

from contextlib import redirect_stdout
from copy import deepcopy
import io
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

import canon
import npc_activation
from npc_fixture import build_npc_fixture, NPC_TRANSITION_POLICIES


ROOT = Path(__file__).resolve().parent
EPISODE = "fixture_morning"


class HostActivationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "state.json"
        redirect = patch.object(canon, "STATE_FILE", str(self.path))
        redirect.start()
        self.addCleanup(redirect.stop)
        self.state = {"facts": [], "next_fact_id": 1, "npc": build_npc_fixture()}
        # All three policies will change something, making order observable.
        for entity in self.state["npc"]["entities"].values():
            entity.update(irritability=0.1, sociability=0.1)
        canon.save_state(self.state)
        self.rng = Mock(random=Mock(return_value=0.99))

    def activate(self):
        return npc_activation.activate_npc_episode(self.state, EPISODE, self.rng)

    def test_success_without_player_or_presentation(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = self.activate()
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(result["activation_status"], "committed")
        self.assertTrue(result["committed"])
        self.assertFalse(result["reused"])
        self.assertNotIn("basis", result)
        self.assertEqual(result["outcome"], "disagreement")
        self.assertEqual(len(self.state["facts"]), 1)
        self.assertEqual(self.state["facts"][0]["text"],
                         "Heidi and Chris argued during the fixture morning.")
        self.assertEqual(self.state["npc"]["resolutions"][EPISODE],
                         {"outcome": "disagreement", "event_id": 1})
        self.assertEqual(canon.load_state(), self.state)
        self.rng.random.assert_called_once()

    def test_invalid_or_absent_episode_fails_without_sampling_or_writes(self):
        invalid_constraints = deepcopy(self.state)
        del invalid_constraints["npc"]["episodes"][EPISODE]["allowed_places"]
        cases = [(None, EPISODE), ({}, EPISODE),
                 ({"npc": canon.empty_npc_state()}, EPISODE),
                 (self.state, "not_installed"), (self.state, None),
                 (self.state, []), (invalid_constraints, EPISODE)]
        for state, episode in cases:
            with self.subTest(episode=episode, state=state):
                before, saved = deepcopy(state), self.path.read_bytes()
                with patch.object(npc_activation, "commit_npc_resolution") as commit:
                    result = npc_activation.activate_npc_episode(state, episode, self.rng)
                    commit.assert_not_called()
                self.assertEqual(result["activation_status"], "failed")
                self.assertFalse(result["committed"])
                self.assertFalse(result["reused"])
                self.assertEqual(state, before)
                self.assertEqual(self.path.read_bytes(), saved)
        self.rng.random.assert_not_called()

    def test_repeated_activation_and_reload_do_not_replay(self):
        self.activate()
        self.state = canon.load_state()
        before, saved = deepcopy(self.state), self.path.read_bytes()
        self.rng.reset_mock()
        with patch.object(npc_activation, "process_npc_transitions_for_episode") as dispatch:
            result = self.activate()
            dispatch.assert_not_called()
        self.assertEqual(result["activation_status"], "reused")
        self.assertFalse(result["committed"])
        self.assertTrue(result["reused"])
        self.assertNotIn("transitions", result)
        self.rng.random.assert_not_called()
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), saved)

    def test_episode_save_failure_does_not_mutate_memory_or_dispatch(self):
        before, saved = deepcopy(self.state), self.path.read_bytes()
        with patch("canon.os.replace", side_effect=OSError("save failed")), \
                patch.object(npc_activation, "process_npc_transitions_for_episode") as dispatch:
            result = self.activate()
            dispatch.assert_not_called()
        self.assertEqual(result["activation_status"], "failed")
        self.assertEqual(result["error"], "save failed")
        self.assertFalse(result["committed"])
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), saved)
        self.assertEqual(list(self.path.parent.glob(".npc-commit-*")), [])

    def test_commitment_rejection_is_not_treated_as_success(self):
        before = deepcopy(self.state)
        with patch.object(npc_activation, "commit_npc_resolution",
                          side_effect=ValueError("unauthorized")):
            result = self.activate()
        self.assertEqual(result["activation_status"], "failed")
        self.assertEqual(result["error"], "unauthorized")
        self.assertNotIn("transitions", result)
        self.assertEqual(self.state, before)
        self.assertEqual(canon.load_state(), before)

    def test_transition_order_uses_fresh_state(self):
        observed = []
        evaluate = npc_activation.evaluate_transition

        def record(npc, policy_id):
            observed.append((policy_id, deepcopy(npc["entities"])))
            return evaluate(npc, policy_id)

        with patch.object(npc_activation, "evaluate_transition", side_effect=record):
            result = self.activate()
        ids = [p["policy_id"] for p in NPC_TRANSITION_POLICIES]
        self.assertEqual([p for p, _ in observed], ids)
        self.assertEqual([t["policy_id"] for t in result["transitions"]], ids)
        self.assertEqual(observed[0][1]["heidi"]["irritability"], 0.1)
        self.assertEqual(observed[1][1]["heidi"]["irritability"], 0.5)
        self.assertEqual(observed[2][1]["chris"]["irritability"], 0.5)
        self.assertTrue(all(t["committed"] for t in result["transitions"]))

    def test_failed_transition_preserves_episode_and_is_not_replayed(self):
        save = canon._save_npc_commit
        calls = []

        def fail_second_transition(pending):
            calls.append(deepcopy(pending))
            if len(calls) == 3:  # episode, first transition, second transition
                raise OSError("transition save failed")
            return save(pending)

        with patch.object(canon, "_save_npc_commit", side_effect=fail_second_transition):
            result = self.activate()
        self.assertEqual(result["activation_status"], "committed")
        self.assertEqual([t["committed"] for t in result["transitions"]], [True, False, True])
        failure = result["transitions"][1]
        self.assertEqual(failure["stage"], "commitment")
        self.assertEqual(failure["error_type"], "OSError")
        self.assertEqual(self.state["npc"]["entities"]["chris"]["irritability"], 0.1)
        self.assertEqual(self.state["npc"]["entities"]["heidi"]["sociability"], 0.5)
        self.assertEqual(len(self.state["facts"]), 1)
        self.assertEqual(canon.load_state(), self.state)
        before = deepcopy(self.state)
        with patch.object(npc_activation, "evaluate_transition") as evaluate:
            reused = self.activate()
            evaluate.assert_not_called()
        self.assertEqual(reused["activation_status"], "reused")
        self.assertEqual(self.state, before)

    def test_registry_failure_preserves_committed_episode(self):
        with patch.object(npc_activation, "validated_transition_policies",
                          side_effect=ValueError("invalid registry")):
            result = self.activate()
        self.assertEqual(result["activation_status"], "committed")
        self.assertEqual(result["transitions"][0]["stage"], "registry")
        self.assertFalse(result["transitions"][0]["committed"])
        self.assertEqual(canon.load_state(), self.state)

    def test_unexpected_rng_failure_propagates_without_retry(self):
        self.rng.random.side_effect = RuntimeError("rng failed")
        before = deepcopy(self.state)
        with self.assertRaisesRegex(RuntimeError, "rng failed"):
            self.activate()
        self.rng.random.assert_called_once()
        self.assertEqual(self.state, before)
        self.assertEqual(canon.load_state(), before)

    def test_import_and_activation_without_cli_renderer_or_llm_dependencies(self):
        script = '''
import builtins, sys
real_import = builtins.__import__
def guarded(name, *args, **kwargs):
    if name in {"main", "renderer", "llm_adapter", "openai", "requests", "map_data"}:
        raise AssertionError("unexpected dependency: " + name)
    return real_import(name, *args, **kwargs)
builtins.__import__ = guarded
import npc_activation, canon
from npc_fixture import build_npc_fixture
from types import SimpleNamespace
state = {"facts": [], "next_fact_id": 1, "npc": build_npc_fixture()}
result = npc_activation.activate_npc_episode(state, "fixture_morning", SimpleNamespace(random=lambda: 0.99))
assert result["activation_status"] == "committed"
'''
        env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-c", script], cwd=directory,
                                    env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_cli_resolve_keeps_existing_diagnostic_shape(self):
        # Exercise the actual CLI loop with only the unrelated LLM adapter stubbed.
        adapter = ModuleType("llm_adapter")
        adapter.EXTRACTION_MODE = "local"
        adapter.chat = Mock(side_effect=AssertionError("LLM must not be called"))
        output = io.StringIO()
        previous = os.getcwd()
        try:
            os.chdir(self.path.parent)
            with patch.dict(sys.modules, {"llm_adapter": adapter}), \
                    patch("builtins.input", side_effect=["/npcresolve fixture_morning",
                                                        "/npcresolve fixture_morning", "/quit"]), \
                    patch("collapse._npc_rng", self.rng), redirect_stdout(output):
                namespace = runpy.run_path(str(ROOT / "main.py"), run_name="__main__")
        finally:
            os.chdir(previous)
        adapter.chat.assert_not_called()
        text = output.getvalue()
        self.assertNotIn('"activation_status"', text)
        self.assertIn('"committed": true', text)
        self.assertIn('"reused": true', text)
        self.assertEqual(len(namespace["state"]["facts"]), 1)
        self.assertEqual(canon.load_state(), namespace["state"])


if __name__ == "__main__":
    unittest.main()
