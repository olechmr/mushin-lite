"""Ordinary-action conformance: python -m unittest -v test_player_action."""
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
import map_data
import packet_interpreter
import rules
from player_action_rules import POLICY, validate_player_action
from test_fixture import TEST_FACTS
from world import ENTITY_DEFINITIONS, build_entity_state, build_world_state, resolve_entity_reference

ROOT = Path(__file__).resolve().parent


class PlayerActionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'state.json'
        redirect = patch.object(canon, 'STATE_FILE', str(self.path))
        redirect.start()
        self.addCleanup(redirect.stop)
        self.state = {'facts': [dict(f, id=i, status='active')
                               for i, f in enumerate(TEST_FACTS, 1)],
                      'next_fact_id': 6, 'npc': canon.empty_npc_state()}
        self.config = {'policy': POLICY, 'entities': deepcopy(ENTITY_DEFINITIONS),
                       'exits': deepcopy(map_data.BASE_EXITS)}
        canon.save_state(self.state)

    def proposal(self, action='take', target='book'):
        packet = packet_interpreter.normalize_packet({'action': action, 'target': target})
        entities = build_entity_state(self.state['facts'])
        if packet['action'] != 'move':
            packet['target'] = resolve_entity_reference(packet['target'], entities,
                                                       entities.get('player', {}).get('whereabouts')) or target
        effects = packet_interpreter.facts_from_packet(packet, self.state['facts'])
        with patch.object(map_data, 'EXITS', self.config['exits']):
            effects = rules.apply_rules(packet, effects, entities, build_world_state(self.state['facts']))
        return {'version': 1, 'action': packet['action'], 'target': packet['target'],
                'effects': effects, 'basis': deepcopy(self.state),
                'configuration_basis': deepcopy(self.config)}

    def commit(self, action='take', target='book'):
        return canon.commit_player_action(self.state, self.proposal(action, target), self.config)

    def reject(self, proposal):
        before, saved = deepcopy(self.state), self.path.read_bytes()
        with patch.object(canon, '_save_npc_commit') as save:
            result = canon.commit_player_action(self.state, proposal, self.config)
            save.assert_not_called()
        self.assertEqual(result['status'], 'rejected', result)
        self.assertEqual(result['facts'], [])
        self.assertIsNone(result['rule_block_text'])
        self.assertEqual(self.state, before)
        self.assertEqual(self.path.read_bytes(), saved)

    def test_valid_actions_and_movement(self):
        for action, target in [('take', 'book'), ('open', 'book'), ('close', 'book'),
                               ('drop', 'book'), ('take', 'lantern'), ('light', 'lantern'),
                               ('extinguish', 'lantern'), ('move', 'north')]:
            with self.subTest(action=action):
                result = self.commit(action, target)
                self.assertEqual(result['status'], 'committed', result)
                self.assertIsNone(result['rule_block_text'])
                self.assertEqual(canon.load_state(), self.state)
        self.assertEqual(build_entity_state(self.state['facts'])['player']['whereabouts'], 'in the hallway')

    def test_aliases_and_canonical_suffix_resolution(self):
        foundation = deepcopy(self.state)
        for alias, action in packet_interpreter.ACTION_ALIASES.items():
            if action not in {'take', 'drop', 'move', 'light', 'extinguish'}:
                continue
            with self.subTest(alias=alias):
                self.state = deepcopy(foundation)
                target = 'north' if action == 'move' else ('lantern' if action in {'light', 'extinguish'} else 'book')
                if action in {'drop', 'light', 'extinguish'}:
                    canon.add_fact(self.state, f'The player is holding the {target}.')
                p = self.proposal(alias, target)
                self.assertEqual(p['action'], action)
                self.assertNotEqual(canon.commit_player_action(self.state, p, self.config)['status'], 'rejected')
        canon.add_fact(self.state, 'The brass key is in the hallway.')
        canon.add_fact(self.state, 'The player is in the hallway.')
        p = self.proposal('grab', 'key')
        self.assertEqual(p['target'], 'brass key')
        self.assertEqual(canon.commit_player_action(self.state, p, self.config)['status'], 'committed')
        p = self.proposal('take', 'brass key'); p['target'] = 'key'
        self.reject(p)

    def test_possession_access_and_required_state(self):
        for action, target in [('drop', 'book'), ('light', 'lantern'), ('extinguish', 'lantern'), ('take', 'player'), ('break', 'book')]:
            self.reject(self.proposal(action, target))
        canon.add_fact(self.state, 'The book is in the study.')
        self.reject(self.proposal())
        canon.add_fact(self.state, 'The book is in the foyer.')
        self.state['facts'] = [f for f in self.state['facts'] if f['text'] != 'The book is closed.']
        self.reject(self.proposal('open'))
        canon.add_fact(self.state, 'The player is holding the book.')
        self.state['facts'] = [f for f in self.state['facts'] if 'The player is in the' not in f['text']]
        self.reject(self.proposal('drop'))

    def test_blocks_and_rule_precedence(self):
        self.commit()
        result = self.commit()
        self.assertEqual(result['rule_block_text'], 'The player is already holding the book.')
        self.commit('open')
        canon.add_fact(self.state, 'The book is broken.')
        self.assertEqual(self.commit('open')['rule_block_text'], 'The book is already open.')
        self.commit('close')
        self.assertEqual(self.commit('open')['rule_block_text'], 'The player tried to open the book, but it is broken.')
        self.assertEqual(self.commit('close')['rule_block_text'], 'The book is already closed.')
        self.commit('take', 'lantern')
        self.assertEqual(self.commit('extinguish', 'lantern')['rule_block_text'], 'The lantern is already extinguished.')
        self.commit('light', 'lantern')
        self.assertEqual(self.commit('light', 'lantern')['rule_block_text'], 'The lantern is already lit.')

    def test_drop_open_object_requires_closing_consequence(self):
        self.commit(); self.commit('open')
        p = self.proposal('drop'); p['effects'].pop()
        self.reject(p)
        result = self.commit('drop')
        self.assertEqual([f['text'] for f in result['facts']], [
            'The player dropped the book.', 'The book is in the foyer.', 'The book is closed.'])

    def test_movement_authorization_and_blocks(self):
        p = self.proposal('move', 'north'); p['effects'][0]['text'] = 'The player is in the study.'
        self.reject(p)
        self.assertIn('no exit', self.commit('move', 'west')['rule_block_text'])
        canon.add_fact(self.state, 'The passage is unavailable.')
        self.assertIn('passage is unavailable', self.commit('move', 'north')['rule_block_text'])
        self.state['facts'] = [f for f in self.state['facts'] if 'player is in' not in f['text'] and 'passage is' not in f['text']]
        self.assertIn('location is unknown', self.commit('move', 'north')['rule_block_text'])

    def test_forged_extra_omitted_malformed_proposals(self):
        base = self.proposal()
        variants = [None, {}, [], dict(base, version=True), dict(base, eligible=True),
                    dict(base, action=[]), dict(base, target=None), dict(base, effects=None),
                    dict(base, effects=[]), dict(base, effects=list(reversed(base['effects'])))]
        for effects in [base['effects'][:1], base['effects'] + [{'type': 'event', 'text': 'Invented.'}],
                        [{'type': 'state', 'text': 'The player is holding the book.'}]]:
            variants.append(dict(base, effects=effects))
        p = deepcopy(base); p['effects'][0]['authorized'] = True; variants.append(p)
        for p in variants:
            with self.subTest(proposal=p): self.reject(p)

    def test_matching_bases_do_not_grant_authorization(self):
        p = self.proposal()
        self.config['entities']['book']['interactions'] = []
        p['configuration_basis'] = deepcopy(self.config)
        self.reject(p)
        self.config['entities']['book']['interactions'] = ['take']
        canon.add_fact(self.state, 'The book is in the study.')
        p['basis'] = deepcopy(self.state); p['configuration_basis'] = deepcopy(self.config)
        self.reject(p)

    def test_stale_state_configuration_and_replayed_proposal(self):
        p = self.proposal(); self.commit('open'); self.reject(p)
        p = self.proposal(); self.config['exits']['foyer']['east'] = 'study'; self.reject(p)
        p = self.proposal(); result = canon.commit_player_action(self.state, p, self.config)
        self.assertEqual(result['status'], 'committed'); self.reject(p)

    def test_invalid_storage_and_configuration_fail_closed(self):
        self.state['facts'].append(dict(self.state['facts'][0], id=6))
        self.state['next_fact_id'] = 7
        self.reject(self.proposal())
        self.state['facts'].pop()
        for field, value in [('policy', 'unknown'), ('entities', {}), ('exits', None)]:
            config = deepcopy(self.config); self.config[field] = value
            # Build valid effects before applying the malformed trusted inputs.
            p = {'version': 1, 'action': 'take', 'target': 'book', 'effects': [],
                 'basis': deepcopy(self.state), 'configuration_basis': deepcopy(self.config)}
            self.reject(p); self.config = config

    def test_atomic_failure_at_each_write_stage(self):
        p = self.proposal()
        for target in ['canon.json.dump', 'canon.os.fsync', 'canon.os.replace']:
            with self.subTest(stage=target):
                before, saved = deepcopy(self.state), self.path.read_bytes()
                with patch(target, side_effect=OSError('injected failure')) as failing:
                    result = canon.commit_player_action(self.state, p, self.config)
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['facts'], [])
                self.assertIsNone(result['rule_block_text'])
                self.assertEqual(self.state, before)
                self.assertEqual(self.path.read_bytes(), saved)
                failing.assert_called_once()
                self.assertEqual(list(self.path.parent.glob('.npc-commit-*')), [])

    def test_uncertain_write_does_not_retry_or_publish_in_memory(self):
        before = deepcopy(self.state)
        replace = os.replace
        def uncertain(source, destination):
            replace(source, destination)
            raise OSError('acknowledgment lost')
        with patch('canon.os.replace', side_effect=uncertain) as write:
            result = self.commit()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['facts'], [])
        self.assertEqual(self.state, before)
        self.assertNotEqual(canon.load_state(), before)
        write.assert_called_once()
        self.assertIn('reconcile', result['reason'])

    def test_new_occurrences_append_events_without_rewriting_history(self):
        first = self.commit()['facts'][0]
        self.commit('drop')
        second = self.commit()['facts'][0]
        self.assertEqual(first['text'], second['text'])
        self.assertNotEqual(first['id'], second['id'])
        self.assertIn(first, self.state['facts'])
        self.assertEqual(canon.load_state(), self.state)
        self.assertEqual(build_entity_state(self.state['facts'])['book']['whereabouts'], 'held by player')
        # Legacy developer add_fact remains deduplicated.
        self.assertFalse(canon.add_fact(self.state, first['text'], 'event'))

    def test_no_change_state_only_action(self):
        self.config['exits']['foyer']['south'] = 'foyer'
        before, saved = deepcopy(self.state), self.path.read_bytes()
        result = self.commit('move', 'south')
        self.assertEqual(result['status'], 'no_change')
        self.assertEqual(self.state, before); self.assertEqual(self.path.read_bytes(), saved)

    def test_validation_pure_and_results_detached(self):
        p = self.proposal(); before = deepcopy((self.state, p, self.config))
        validate_player_action(self.state, p, self.config)
        self.assertEqual((self.state, p, self.config), before)
        result = canon.commit_player_action(self.state, p, self.config)
        result['facts'][0]['text'] = 'forged'
        self.assertNotIn('forged', [f['text'] for f in self.state['facts']])

    def test_commit_without_producer_renderer_model_or_rules(self):
        p = self.proposal()
        script = '''
import builtins, json
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name in {'main', 'packet_interpreter', 'rules', 'renderer', 'llm_adapter', 'collapse', 'random', 'map_data'}:
        raise AssertionError('unexpected dependency: ' + name)
    return original(name, *args, **kwargs)
# Infrastructure modules are already loaded before testing the stage boundary.
import canon
builtins.__import__ = guarded
state, proposal, config = json.loads(input())
assert canon.commit_player_action(state, proposal, config)['status'] == 'committed'
'''
        result = subprocess.run([sys.executable, '-c', script], input=json.dumps([self.state, p, self.config]),
                                text=True, capture_output=True, cwd=self.path.parent,
                                env=dict(os.environ, PYTHONPATH=str(ROOT)), timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def run_cli(self, packets, commands, failure=False):
        adapter = ModuleType('llm_adapter'); adapter.EXTRACTION_MODE = 'local'
        adapter.chat = Mock(side_effect=packets); adapter.log_final_state = Mock()
        previous = os.getcwd(); output = io.StringIO()
        try:
            os.chdir(self.path.parent)
            with patch.dict(sys.modules, {'llm_adapter': adapter}), \
                    patch('builtins.input', side_effect=commands), redirect_stdout(output):
                if failure:
                    with patch('canon.os.replace', side_effect=OSError('failure')):
                        namespace = runpy.run_path(str(ROOT / 'main.py'), run_name='__main__')
                else:
                    namespace = runpy.run_path(str(ROOT / 'main.py'), run_name='__main__')
        finally:
            os.chdir(previous)
        return namespace, output.getvalue(), adapter

    def test_cli_actions_blocks_and_narration_handoff(self):
        packets = [{'action': a, 'target': t} for a, t in
                   [('grab', 'book'), ('open', 'book'), ('open', 'book'), ('drop', 'book'), ('go', 'north')]]
        namespace, output, adapter = self.run_cli(packets, ['grab book', 'open book', 'open book', 'drop book', 'n', '/quit'])
        self.assertEqual(canon.load_state(), namespace['state'])
        self.assertIn('already open', output)
        self.assertEqual(adapter.log_final_state.call_count, 5)
        self.assertEqual(build_entity_state(namespace['state']['facts'])['player']['whereabouts'], 'in the hallway')

    def test_cli_rejects_forged_effects_without_fallback_or_presentation(self):
        before, saved = deepcopy(self.state), self.path.read_bytes()
        with patch.object(rules, 'apply_rules', return_value=[
                {'type': 'state', 'text': 'The player is in the study.'}]), \
                patch('renderer.build_presentation_context', side_effect=AssertionError('must not present')):
            namespace, output, adapter = self.run_cli(
                [{'action': 'take', 'target': 'book'}], ['take book', '/quit'])
        self.assertEqual(namespace['state'], before)
        self.assertEqual(self.path.read_bytes(), saved)
        self.assertIn('could not be committed', output)
        adapter.log_final_state.assert_not_called()

    def test_memory_changes_only_after_complete_snapshot_is_saved(self):
        before = deepcopy(self.state)
        save = canon._save_npc_commit
        pending_snapshots = []
        def inspect(pending):
            self.assertEqual(self.state, before)
            self.assertEqual(canon.load_state(), before)
            pending_snapshots.append(deepcopy(pending))
            save(pending)
            self.assertEqual(self.state, before)
        with patch.object(canon, '_save_npc_commit', side_effect=inspect) as writer:
            result = self.commit()
        writer.assert_called_once()
        self.assertEqual(result['status'], 'committed')
        self.assertEqual(len(pending_snapshots[0]['facts']), len(before['facts']) + 2)
        self.assertEqual(pending_snapshots[0], self.state)
        self.assertEqual(canon.load_state(), self.state)

    def test_existing_resolved_facts_and_traits_are_preserved(self):
        self.state['facts'].extend([
            {'id': 6, 'type': 'event', 'text': 'An earlier event.', 'status': 'resolved'},
            {'id': 7, 'type': 'trait', 'text': 'An established trait.', 'status': 'active'}])
        self.state['next_fact_id'] = 8
        history = deepcopy(self.state['facts'][-2:])
        self.assertEqual(self.commit()['status'], 'committed')
        for fact in history:
            self.assertIn(fact, self.state['facts'])

    def test_cli_failure_stops_without_unchecked_fallback(self):
        before, saved = deepcopy(self.state), self.path.read_bytes()
        namespace, output, adapter = self.run_cli([{'action': 'take', 'target': 'book'}], ['take book'], True)
        self.assertEqual(namespace['state'], before)
        self.assertEqual(self.path.read_bytes(), saved)
        self.assertIn('reconciliation', output)
        adapter.log_final_state.assert_not_called()


if __name__ == '__main__':
    unittest.main()
