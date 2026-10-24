"""Standard-library tests for independently authorized observation commitment."""
from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
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
import collapse
import map_data
from observation_activation import activate_observation
from observation_rules import POLICY, observation_candidates, validate_observation

ROOT = Path(__file__).resolve().parent


class ObservationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'state.json'
        redirect = patch.object(canon, 'STATE_FILE', str(self.path))
        redirect.start(); self.addCleanup(redirect.stop)
        self.state = {'facts': [{'id': 1, 'type': 'state', 'status': 'active',
                                 'text': 'The player is in the study.'}],
                      'next_fact_id': 2, 'npc': canon.empty_npc_state()}
        self.config = {'policy': POLICY, 'rooms': deepcopy(map_data.ROOMS),
                       'discoveries': deepcopy(collapse.OBSERVATION_DISCOVERIES)}
        canon.save_state(self.state)
        self.rng = Mock(random=Mock(return_value=0.1))

    def proposal(self, discovery='brass_key', space='study_desk', verb='search'):
        return {'version': 1, 'room_id': 'study', 'observation_id': space, 'verb': verb,
                'discovery_id': discovery, 'basis': deepcopy(self.state),
                'configuration_basis': deepcopy(self.config)}

    def activate(self, space='study_desk', verb='search'):
        return activate_observation(self.state, 'study', space, verb, self.config, self.rng)

    def reject(self, proposal):
        before, saved = deepcopy(self.state), self.path.read_bytes()
        with patch.object(canon, '_save_npc_commit') as save:
            result = canon.commit_observation(self.state, proposal, self.config)
            save.assert_not_called()
        self.assertEqual(result['status'], 'rejected', result)
        self.assertEqual(result['facts'], [])
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), saved)

    def test_valid_commit_derives_reveal_and_marker(self):
        result = canon.commit_observation(self.state, self.proposal(), self.config)
        self.assertEqual(result['status'], 'committed')
        self.assertEqual([f['text'] for f in result['facts']], [
            'The brass key is in the study.', 'The search space study_desk:search collapsed.'])
        self.assertEqual([f['id'] for f in result['facts']], [2, 3])
        self.assertEqual(canon.load_state(), self.state)
        result['facts'][0]['text'] = 'forged'
        self.assertEqual(self.state['facts'][1]['text'], 'The brass key is in the study.')

    def test_desk_weights_and_deterministic_selection_match_legacy(self):
        candidates, _, _ = observation_candidates(self.state, 'study', 'study_desk', 'search', self.config)
        self.assertEqual([(c['id'], c['weight']) for c in candidates],
                         [('brass_key', 1), ('letter_opener', 3), ('ink_bottle', 2)])
        space = self.config['rooms']['study']['observations'][0]
        for draw, expected in [(0, 'brass_key'), (0.16, 'brass_key'), (1/6, 'letter_opener'),
                               (0.6, 'letter_opener'), (2/3, 'ink_bottle'), (0.999, 'ink_bottle')]:
            with self.subTest(draw=draw):
                rng = Mock(random=Mock(return_value=draw))
                self.assertEqual(collapse.resolve_observation_candidates(candidates, rng), expected)
                with patch.object(collapse, '_collapse_rng', rng):
                    legacy = collapse.collapse_observation('study', space, self.state['facts'])
                self.assertEqual(legacy[0]['discovery_id'], expected)

    def test_search_and_inspect_all_installed_spaces(self):
        for space in self.config['rooms']['study']['observations']:
            for verb in ['search', 'inspect']:
                with self.subTest(space=space['id'], verb=verb):
                    result = self.activate(space['id'], verb)
                    self.assertEqual(result['status'], 'committed', result)
                    self.assertEqual(len(result['facts']), 2)
        self.assertEqual(canon.load_state(), self.state)
        self.assertNotIn('cause', str(self.state))
        self.assertIn('Someone searched these shelves recently.', [f['text'] for f in self.state['facts']])

    def test_forged_missing_and_malformed_proposals(self):
        base = self.proposal()
        variants = [None, {}, [], dict(base, version=True), dict(base, extra=True),
                    dict(base, discovery_id='cold_fireplace'), dict(base, discovery_id='invented'),
                    dict(base, discovery_id=[]), dict(base, observation_id=None),
                    dict(base, room_id='foyer'), dict(base, verb='look'),
                    dict(base, effects=[{'text': 'Invented.'}])]
        for key in base:
            p = deepcopy(base); del p[key]; variants.append(p)
        for p in variants:
            with self.subTest(proposal=p): self.reject(p)

    def test_missing_constraints_and_duplicate_ids_reject_before_sampling(self):
        original = deepcopy(self.config)
        for change in ['id', 'constraints', 'required_tags', 'duplicate_space', 'duplicate_discovery', 'verbs']:
            self.config = deepcopy(original)
            space = self.config['rooms']['study']['observations'][0]
            if change == 'required_tags': del space['constraints']['required_tags']
            elif change == 'duplicate_space': self.config['rooms']['study']['observations'].append(deepcopy(space))
            elif change == 'duplicate_discovery': self.config['discoveries'].append(deepcopy(self.config['discoveries'][0]))
            else: del space[change]
            with self.subTest(change=change):
                before = deepcopy(self.state)
                result = self.activate()
                self.assertEqual(result['status'], 'rejected')
                self.assertEqual(self.state, before)
                self.reject(self.proposal())
        self.rng.random.assert_not_called()

    def test_wrong_room_ambiguous_location_and_verb_permissions(self):
        canon.add_fact(self.state, 'The player is in the foyer.')
        self.reject(self.proposal())
        canon.add_fact(self.state, 'The player is in the study.')
        self.config['rooms']['study']['observations'][0]['verbs'] = ['inspect']
        self.reject(self.proposal())
        self.config['rooms']['study']['observations'][0]['verbs'] = ['search']
        self.state['facts'].append({'id': self.state['next_fact_id'], 'type': 'state',
                                    'text': 'The player is in the foyer.'})
        self.state['next_fact_id'] += 1
        self.reject(self.proposal())

    def test_invalid_weights_and_zero_total_are_errors_not_abstention(self):
        for value in [-1, float('nan'), float('inf'), True, '1', None]:
            with self.subTest(weight=value):
                self.config['discoveries'][0]['weight'] = value
                self.reject(self.proposal())
                self.assertEqual(self.activate()['status'], 'rejected')
        for candidate in self.config['discoveries'][:3]: candidate['weight'] = 0
        self.reject(self.proposal(None))
        self.assertEqual(self.activate()['status'], 'rejected')
        self.rng.random.assert_not_called()

    def test_zero_weight_selection_rejected_and_optional_default_preserved(self):
        self.config['discoveries'][0]['weight'] = 0
        self.reject(self.proposal())
        candidates, _, _ = observation_candidates(self.state, 'study', 'study_desk', 'search', self.config)
        self.assertEqual(collapse.resolve_observation_candidates(candidates, self.rng), 'letter_opener')
        candidates, _, _ = observation_candidates(self.state, 'study', 'study_bookshelf', 'search', self.config)
        self.assertEqual(candidates[0]['weight'], 1)

    def test_malformed_reveal_templates_fail_closed(self):
        original = deepcopy(self.config)
        for reveal in [{}, {'type': 'collapse', 'text': 'marker'}, {'type': 'state', 'text': '{secret}'},
                       {'type': 'state', 'text': '{room_id.__class__}'}, {'type': 'state', 'text': '{'},
                       {'type': 'state', 'text': ''}]:
            self.config = deepcopy(original)
            self.config['discoveries'][0]['reveal'] = reveal
            self.reject(self.proposal())

    def test_stale_state_and_configuration(self):
        p = self.proposal(); canon.add_fact(self.state, 'The book is closed.'); self.reject(p)
        p = self.proposal(); self.config['discoveries'][0]['weight'] = 2; self.reject(p)
        p = self.proposal(); self.config['rooms']['study']['observations'][0]['constraints']['required_tags'] = ['fireplace']; self.reject(p)
        # Matching bases still cannot grant permission to a desk discovery.
        self.reject(self.proposal())

    def test_existing_whereabouts_never_relocated(self):
        for text in ['The brass key is in the foyer.', 'The player is holding the brass key.']:
            canon.add_fact(self.state, text)
            self.reject(self.proposal())
        result = self.activate()
        self.assertEqual(result['status'], 'committed')
        self.assertIn('The player is holding the brass key.', [f['text'] for f in self.state['facts'] if f.get('status') == 'active'])
        self.assertNotIn('The brass key is in the study.', [f['text'] for f in self.state['facts']])

    def test_repeat_reload_and_legacy_marker_never_sample_or_reconstruct(self):
        self.activate(); self.state = canon.load_state()
        before = deepcopy(self.state)
        self.rng.random.reset_mock()
        self.assertEqual(self.activate()['status'], 'no_change')
        self.rng.random.assert_not_called()
        self.assertEqual(self.state, before)
        self.reject(self.proposal())
        # Model a legacy save without acquisitions, not damaged modern history.
        del self.state["disclosure"]
        # Legacy marker remains sufficient even without a reveal link.
        self.state['facts'] = [f for f in self.state['facts'] if f['id'] != 2]
        canon.save_state(self.state)
        before = deepcopy(self.state)
        self.assertEqual(self.activate()['status'], 'no_change')
        self.assertEqual(self.state, before)
        self.rng.random.assert_not_called()

    def test_null_only_for_collapsed_or_empty_eligible_catalogue(self):
        self.reject(self.proposal(None))
        for obj in ['brass key', 'letter opener', 'ink bottle']:
            canon.add_fact(self.state, f'The {obj} is in the foyer.')
        before, saved = deepcopy(self.state), self.path.read_bytes()
        self.assertEqual(self.activate()['status'], 'no_change')
        self.rng.random.assert_not_called()
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), saved)
        self.assertFalse(any(f['type'] == 'collapse' for f in self.state['facts']))

    def test_preexisting_reveal_does_not_invent_missing_marker(self):
        canon.add_fact(self.state, 'Someone searched these shelves recently.', 'event')
        before = deepcopy(self.state)
        self.assertEqual(self.activate('study_bookshelf')['status'], 'no_change')
        self.assertEqual(self.state, before)
        self.rng.random.assert_not_called()

    def test_pure_validation(self):
        p = self.proposal(); before = deepcopy((self.state, p, self.config))
        validate_observation(self.state, p, self.config)
        self.assertEqual((self.state, p, self.config), before)

    def test_complete_unit_persists_before_memory(self):
        before = deepcopy(self.state); save = canon._save_npc_commit
        def inspect(pending):
            self.assertEqual(self.state, before)
            self.assertEqual([f['type'] for f in pending['facts'][-2:]], ['state', 'collapse'])
            save(pending)
            self.assertEqual(self.state, before)
        with patch.object(canon, '_save_npc_commit', side_effect=inspect) as write:
            self.assertEqual(self.activate()['status'], 'committed')
        write.assert_called_once()
        self.assertEqual(canon.load_state(), self.state)

    def test_persistence_failures_preserve_memory_disk_and_hide_reveal(self):
        for target in ['canon.json.dump', 'canon.os.fsync', 'canon.os.replace']:
            before, saved = deepcopy(self.state), self.path.read_bytes()
            with patch(target, side_effect=OSError('failure')) as failed:
                result = self.activate()
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['facts'], [])
            self.assertEqual(self.state, before)
            self.assertEqual(self.path.read_bytes(), saved)
            self.assertEqual(list(self.path.parent.glob('.npc-commit-*')), [])
            failed.assert_called_once()

    def test_uncertain_persistence_requires_reconciliation_without_retry(self):
        replace = os.replace; before = deepcopy(self.state)
        def uncertain(source, destination):
            replace(source, destination)
            raise OSError('acknowledgment lost')
        with patch('canon.os.replace', side_effect=uncertain) as write:
            result = self.activate()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['facts'], [])
        self.assertEqual(self.state, before)
        self.assertIn('reconcile', result['reason'])
        write.assert_called_once()
        self.state = canon.load_state()
        self.rng.random.reset_mock()
        self.assertEqual(self.activate()['status'], 'no_change')
        self.rng.random.assert_not_called()

    def test_invalid_randomness_rejected_without_commit(self):
        for draw in [-1, 1, float('nan'), True, None]:
            self.rng.random.return_value = draw
            with patch.object(canon, '_save_npc_commit') as write:
                self.assertEqual(self.activate()['status'], 'rejected')
                write.assert_not_called()

    def test_commit_independent_of_producer_renderer_llm_and_sampling(self):
        script = '''
import builtins, json, canon
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name in {'collapse', 'observation_activation', 'main', 'renderer', 'llm_adapter', 'random', 'map_data'}:
        raise AssertionError('Unexpected dependency: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
state, proposal, config = json.loads(input())
assert canon.commit_observation(state, proposal, config)['status'] == 'committed'
'''
        result = subprocess.run([sys.executable, '-c', script],
                                input=json.dumps([self.state, self.proposal(), self.config]),
                                capture_output=True, text=True, cwd=self.path.parent,
                                env=dict(os.environ, PYTHONPATH=str(ROOT)), timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def cli(self, commands):
        adapter = ModuleType('llm_adapter'); adapter.EXTRACTION_MODE = 'local'
        adapter.chat = Mock(side_effect=AssertionError('No LLM for observations'))
        previous = os.getcwd(); output = io.StringIO()
        try:
            os.chdir(self.path.parent)
            with patch.dict(sys.modules, {'llm_adapter': adapter}), \
                    patch('builtins.input', side_effect=commands), \
                    patch.object(collapse, '_collapse_rng', self.rng), redirect_stdout(output):
                namespace = runpy.run_path(str(ROOT / 'main.py'), run_name='__main__')
        finally:
            os.chdir(previous)
        return namespace, output.getvalue()

    def test_cli_search_inspect_look_listen_and_repeat(self):
        namespace, output = self.cli(['look', 'listen', 'search', 'search desk', 'search desk', 'inspect desk', '/quit'])
        self.assertIn('What do you want to search?', output)
        self.assertIn('You find something: The brass key is in the study.', output)
        self.assertIn('You find nothing new.', output)
        self.assertIn('One of the desk drawers does not sit flush.', output)
        self.assertEqual(self.rng.random.call_count, 2)
        self.assertEqual(canon.load_state(), namespace['state'])

    def test_cli_failure_has_no_reveal_or_unchecked_fallback(self):
        before, saved = deepcopy(self.state), self.path.read_bytes()
        with patch('canon.os.replace', side_effect=OSError('failure')):
            namespace, output = self.cli(['search desk'])
        self.assertIn('reconciliation', output)
        self.assertNotIn('You find something:', output)
        self.assertNotIn('brass key', output)
        self.assertEqual(namespace['state'], before)
        self.assertEqual(self.path.read_bytes(), saved)

    def test_cli_rejection_has_no_unchecked_fallback(self):
        before, saved = deepcopy(self.state), self.path.read_bytes()
        with patch('observation_activation.resolve_observation_candidates', return_value='cold_fireplace'):
            namespace, output = self.cli(['search desk', '/quit'])
        self.assertIn('could not be committed', output)
        self.assertNotIn('You find something:', output)
        self.assertEqual(namespace['state'], before)
        self.assertEqual(self.path.read_bytes(), saved)


if __name__ == '__main__':
    unittest.main()
